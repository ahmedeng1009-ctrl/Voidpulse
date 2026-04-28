"""
VoidPulse Master Pipeline
Full automation: script → voiceover → video → thumbnail → upload

Usage:
    python run_pipeline.py
    python run_pipeline.py --topic "The dark truth about sleep deprivation"
    python run_pipeline.py --platforms youtube tiktok instagram
    python run_pipeline.py --skip-upload    # produce video/thumbnail only
    python run_pipeline.py --no-music       # disable background music
"""

import argparse
import os
import re
import sys
import time
import random
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Always run from the project directory — critical for Task Scheduler
os.chdir(Path(__file__).parent)
load_dotenv()

# ── File logging (writes to logs/YYYY-MM-DD_HH-MM.log) ───────────────────────

def setup_logging() -> Path:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / datetime.now().strftime("%Y-%m-%d_%H-%M.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    class _Tee:
        def __init__(self, stream): self._s = stream
        def write(self, msg):
            self._s.write(msg)
            if msg.strip():
                logging.info(msg.rstrip())
        def flush(self): self._s.flush()
        def isatty(self): return False

    sys.stdout = _Tee(sys.__stdout__)
    sys.stderr = _Tee(sys.__stderr__)
    return log_path

# ── Topics pool — rotated automatically ──────────────────────────────────────

TOPICS = [
    # ── Original 15 ──────────────────────────────────────────────────────────
    "The dark history of how social media hijacks your brain",
    "How much money billionaires make while you sleep",
    "The terrifying scale of ocean plastic pollution",
    "How much plastic is inside your body right now",
    "The real reason you can never afford a house",
    "The secret algorithm that controls what you think",
    "How surveillance capitalism sells your soul",
    "The dark truth about sleep deprivation",
    "How food companies engineer addiction into every bite",
    "The silent epidemic of loneliness destroying society",
    "How fast fashion is poisoning the planet",
    "The hidden cost of your cheap Amazon purchase",
    "How your phone is making you dumber every day",
    "The dark reality of factory farming",
    "How governments use fear to control populations",
    # ── Body & health ─────────────────────────────────────────────────────────
    "How your deodorant is silently poisoning your lymph nodes every day",
    "How your sunscreen is loading your bloodstream with toxic chemicals right now",
    "How your plastic water bottle is leaching hormones into every sip",
    "How sitting eight hours a day is accelerating your cellular aging",
    "How your toothpaste is quietly destroying your gut microbiome",
    "How your morning coffee is slowly wrecking your cortisol levels forever",
    "How your shampoo strips the natural defenses your scalp needs to survive",
    # ── Food & corporations ───────────────────────────────────────────────────
    "How sugar companies paid scientists to blame fat for the heart disease epidemic",
    "How supermarkets are scientifically designed to override your willpower",
    "How your child's school lunch was designed by junk food corporations",
    "How sports drinks are engineered to keep you dehydrated and buying more",
    "How the snack food industry deliberately engineers portion blindness into you",
    # ── Money & debt ──────────────────────────────────────────────────────────
    "How central banks legally print money that silently steals your savings",
    "How your pension fund is quietly betting against your retirement",
    "How grocery loyalty cards sell your health data to insurance companies",
    "How the diamond industry invented a tradition to sell you worthless rocks",
    "How your electric bill hides fees corporations legally steal from you every month",
    "How pharmaceutical companies create diseases to sell you the cure",
    # ── Tech & attention ──────────────────────────────────────────────────────
    "How your streaming service is engineered to destroy your sleep cycle",
    "How your gym membership is designed so you never actually go",
    "How news algorithms are built to keep you anxious and coming back",
    "How your car's air freshener is filling your lungs with carcinogens",
    # ── Power & society ───────────────────────────────────────────────────────
    "How social credit systems are already silently operating in your country",
    "How cosmetic companies sell you solutions to problems they manufactured",
    "How the opioid crisis was deliberately engineered by three pharmaceutical families",
    "How your landlord legally traps you in a lifetime of debt by design",
    "How the education system was redesigned to produce workers not thinkers",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:60]


def log(msg: str):
    print(f"\n{'='*55}")
    print(f"  {msg}")
    print(f"{'='*55}")


def with_retry(fn, label: str, retries: int = 2, delay: int = 15):
    """Run fn — retry up to `retries` times on failure."""
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            if attempt < retries:
                print(f"  [{label}] Attempt {attempt+1} failed: {e}")
                print(f"  Retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise


def pick_topic(use_trends: bool = False, use_smart: bool = False) -> str:
    used_file = Path("metadata/used_topics.txt")
    used_file.parent.mkdir(exist_ok=True)

    def _log_used(t: str):
        with open(used_file, "a", encoding="utf-8") as f:
            f.write(t + "\n")

    # 1️⃣ Smart topics — learn from past performance
    if use_smart:
        try:
            from smart_topics import get_smart_topic
            topic = get_smart_topic()
            if topic:
                _log_used(topic)
                return topic
            print("  [Smart] Insufficient data — falling back to trending")
        except Exception as e:
            print(f"  [Smart] Failed ({e}) — falling back to trending")

    # 2️⃣ Trending topics
    if use_trends or use_smart:
        try:
            from trending_topics import get_topic_for_today
            topic = get_topic_for_today(use_trends=True)
            _log_used(topic)
            return topic
        except Exception as e:
            print(f"  Trending topics failed ({e}) — using static pool")

    # 3️⃣ Static pool fallback
    used = set()
    if used_file.exists():
        used = set(used_file.read_text(encoding="utf-8").splitlines())

    available = [t for t in TOPICS if t not in used]
    if not available:
        used_file.write_text("", encoding="utf-8")
        available = TOPICS

    topic = random.choice(available)
    _log_used(topic)
    return topic


# ── Step 1: Generate Script ───────────────────────────────────────────────────

def step_generate_script(topic: str) -> Path:
    log(f"STEP 1: Generating script\n  '{topic}'")

    import anthropic

    SYSTEM_PROMPT = """You are a viral YouTube Shorts scriptwriter for the channel VoidPulse.

VoidPulse creates dark, dramatic, fact-based short videos that reveal uncomfortable truths about money, society, and power. The tone is serious, cinematic, and unsettling — never humorous.

═══════════════════════════════════════════════════════════════════════
🔥 CRITICAL HOOK RULES (first 2 seconds — most important part):
═══════════════════════════════════════════════════════════════════════
The HOOK must STOP a scrolling viewer in their tracks. Use ONE of these proven patterns:

  A) SHOCKING STAT FIRST: Open with the most disturbing number from the topic.
     ❌ Bad:  "Today we'll talk about plastic in your body"
     ✅ Good: "There's a credit card of plastic in your bloodstream RIGHT NOW."

  B) DIRECT THREAT TO VIEWER: Make it personal, present-tense, about THEM.
     ❌ Bad:  "Some companies engineer addictive food"
     ✅ Good: "Your last meal was designed in a lab to make you eat more."

  C) CONTRADICTION BOMB: State something that breaks their assumption.
     ❌ Bad:  "Sleep is important"
     ✅ Good: "You're sleeping 8 hours and still dying faster than ever."

  D) PATTERN INTERRUPT: A 3-word sharp claim, then explanation.
     ✅ "They lied to you. About everything you eat."
     ✅ "Stop. Don't scroll. This will end your peace of mind."

HOOK MUST BE:
- ≤ 8 words (spoken in under 2 seconds — algorithm judges in first 2s)
- Present tense, second person ("you", "your", "right now")
- One specific number, percentage, or dollar amount
- No filler words, no "today", no "in this video"

═══════════════════════════════════════════════════════════════════════

💬 CTA RULES (last spoken line — drives comments = algorithm boost):
═══════════════════════════════════════════════════════════════════════
The OUTRO must END with one question that forces a comment.

Rules:
- ≤ 8 words, direct, requires a YES/NO or one-word answer
- Must relate to the topic — not generic "subscribe" or "follow"
- Controversial or personal — makes viewer feel their opinion matters

✅ "Did you know this? Comment YES or NO."
✅ "Has your doctor ever warned you about this?"
✅ "Are they hiding this from you? Tell me."
✅ "Drop a 🚨 if this disturbed you."
❌ "Follow for more dark facts."
❌ "Subscribe for more content like this."

═══════════════════════════════════════════════════════════════════════

SCRIPT FORMAT (follow exactly):

# {TOPIC TITLE} | YouTube Short Script
**Niche:** Scary Real Statistics Visualized
**Duration:** ~32 seconds
**Style:** Dramatic / Conspiracy-core

---

## SCRIPT

---

**[HOOK — 0:00–0:02]**
> *[Stage direction]*

"Spoken line — MUST follow the hook rules above. ≤ 8 words."

---

**[BUILD — 0:02–0:15]**
> *[Stage direction]*

"Spoken line with **bold stat**."

---

**[TWIST — 0:15–0:25]**
> *[Stage direction]*

"Spoken line."

---

**[OUTRO / CTA — 0:25–0:32]**
> *[Stage direction]*

"Closing revelation line."

"**[CTA QUESTION — ≤ 8 words, YES/NO or one-word answer]**"

---

## PRODUCTION NOTES

| Element | Details |
|---|---|
| **Voiceover pace** | slow and dramatic |
| **Music** | dark ambient |

## STATS SOURCES
- Source 1"""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content":
            f'Write a viral 50-second YouTube Shorts script for VoidPulse about:\n\n'
            f'"{topic}"\n\nFollow the exact format. Make it dramatic and unsettling.'}],
    )

    script_text = response.content[0].text
    output_dir  = Path("scripts/drafts")
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / (slugify(topic) + ".md")
    script_path.write_text(script_text, encoding="utf-8")

    print(f"  Script saved: {script_path}")
    return script_path


# ── Voice pool — 8 dramatic ElevenLabs voices, one rotated per video ─────────

VOICE_POOL = [
    ("Adam",      "pNInz6obpgDQGcFmaJgB"),  # Deep American male
    ("Antoni",    "ErXwobaYiN019PkySvjV"),  # Well-rounded male
    ("Arnold",    "VR6AewLTigWG4xSOukaG"),  # Crisp serious male
    ("Daniel",    "onwK4e9ZLuTAKqWW03F9"),  # Authoritative British male
    ("Brian",     "nPczCjzI2devNBz1zQrb"),  # Deep narrator male
    ("Bill",      "pqHfZKP75CvOlQylNhV4"),  # Older narrative male
    ("Charlotte", "XB0fDUnXU5powFXDhCwa"),  # Mysterious female
    ("Alice",     "Xb7hH8MSUJpSbSDYk0k2"),  # Confident British female
]


def pick_random_voice() -> tuple[str, str]:
    """Return (name, voice_id) — different voice each video."""
    return random.choice(VOICE_POOL)


# ── Microsoft Edge TTS — free, unlimited fallback ─────────────────────────────
# Used automatically when ElevenLabs quota is exhausted. Voice quality is
# surprisingly close to premium services (Microsoft Cognitive Services Neural).

EDGE_VOICE_POOL = [
    ("Guy",      "en-US-GuyNeural"),       # Mature American male
    ("Davis",    "en-US-DavisNeural"),     # Dramatic American male
    ("Tony",     "en-US-TonyNeural"),      # Deep American male
    ("Roger",    "en-US-RogerNeural"),     # Confident American male
    ("Ryan",     "en-GB-RyanNeural"),      # British male
    ("Thomas",   "en-GB-ThomasNeural"),    # British male
    ("Aria",     "en-US-AriaNeural"),      # American female
    ("Sonia",    "en-GB-SoniaNeural"),     # Mysterious British female
]


def edge_tts_voiceover(text: str, output_path: Path) -> Path:
    """
    Free fallback TTS using Microsoft Edge's neural voices.
    Unlimited usage, no API key required.
    """
    import asyncio
    import edge_tts

    voice_name, voice_id = random.choice(EDGE_VOICE_POOL)
    print(f"  [Edge TTS fallback] Voice: {voice_name} ({voice_id})")

    async def _run():
        # rate=-5% adds slight slowdown for dramatic delivery
        communicate = edge_tts.Communicate(text, voice_id, rate="-5%")
        await communicate.save(str(output_path))

    asyncio.run(_run())
    return output_path


# ── Step 2: Generate Voiceover ────────────────────────────────────────────────

def step_generate_voiceover(script_path: Path) -> Path:
    log("STEP 2: Generating voiceover")

    import re as _re

    text = script_path.read_text(encoding="utf-8")
    script_match = _re.search(r"## SCRIPT(.*?)(## PRODUCTION NOTES|## STATS|$)", text, re.DOTALL)
    body = script_match.group(1) if script_match else text

    body = _re.sub(r'^>\s*\*\[.*?\]\*\s*$', '', body, flags=re.MULTILINE)
    raw_quotes = _re.findall(r'"(.*?)"', body, re.DOTALL)

    spoken = []
    for q in raw_quotes:
        clean = _re.sub(r'\[.*?\]', '', q, flags=re.DOTALL)
        clean = _re.sub(r'\*+', '', clean)
        clean = _re.sub(r'\s+', ' ', clean).strip()
        if clean:
            spoken.append(clean)

    full_text = "\n\n".join(spoken)
    print(f"  Extracted {len(spoken)} spoken lines ({len(full_text)} chars)")

    output_dir  = Path("audio/voiceover")
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path  = output_dir / (script_path.stem + ".mp3")

    # 1️⃣ Try ElevenLabs first (premium quality)
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if elevenlabs_key:
        try:
            from elevenlabs.client import ElevenLabs

            voice_name, voice_id = pick_random_voice()
            print(f"  ElevenLabs voice: {voice_name}")

            client = ElevenLabs(api_key=elevenlabs_key)
            audio_stream = client.text_to_speech.convert(
                voice_id=voice_id,
                text=full_text,
                model_id="eleven_turbo_v2_5",
                output_format="mp3_44100_128",
            )

            with open(audio_path, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)

            print(f"  Voiceover saved (ElevenLabs): {audio_path}")
            return audio_path

        except Exception as e:
            err_str = str(e)
            if "quota_exceeded" in err_str or "401" in err_str or "credits" in err_str.lower():
                print(f"  ⚠️  ElevenLabs quota exhausted — switching to Edge TTS (free, unlimited)")
            else:
                print(f"  ⚠️  ElevenLabs failed ({type(e).__name__}: {err_str[:120]})")
                print(f"      Falling back to Edge TTS")

    # 2️⃣ Fallback: Microsoft Edge TTS (free, unlimited)
    return edge_tts_voiceover(full_text, audio_path)


# ── Step 3: Generate Video ────────────────────────────────────────────────────

def step_generate_video(script_path: Path, audio_path: Path,
                        topic: str, no_music: bool = False,
                        music_vol: float = 0.15) -> Path:
    log("STEP 3: Creating video")

    sys.path.insert(0, str(Path(__file__).parent))
    import importlib
    gv = importlib.import_module("generate_video")

    output_dir  = Path("video/exports")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (script_path.stem + ".mp4")

    from moviepy import AudioFileClip, CompositeVideoClip

    # Background selection — fetch multiple topic-specific clips
    # Per-video cache dir so each upload gets fresh, never-reused Pexels footage
    bg_queries = gv.get_background_queries(topic)
    topic_slug = re.sub(r"\W+", "_", topic)[:40]
    cache_dir  = Path("video/backgrounds") / topic_slug
    clip_paths = gv.fetch_multiple_clips(bg_queries, cache_dir, topic_label=topic)

    sections       = gv.extract_sections(script_path)
    voiceover      = AudioFileClip(str(audio_path))
    total_duration = voiceover.duration

    # Stat overlays — extract early so SFX ticks can sync to stat reveals
    stats = gv.extract_stats(sections, total_duration)

    # Mix voiceover + music + cinematic SFX timeline (synced to stats)
    if not no_music:
        music_path       = gv.get_music_path(total_duration)
        mixed_audio_path = gv.mix_audio_with_sfx(
            audio_path, music_path, music_vol, total_duration, stats=stats)
        final_audio      = AudioFileClip(str(mixed_audio_path))
    else:
        # Even with no music we still want SFX
        mixed_audio_path = gv.mix_audio_with_sfx(
            audio_path, None, 0.0, total_duration, stats=stats)
        final_audio      = AudioFileClip(str(mixed_audio_path))

    bg         = gv.make_background_clip(clip_paths, total_duration)
    text_clips = gv.make_karaoke_clips(sections, total_duration)
    print(f"  {len(text_clips)} karaoke phrase clips")

    stat_clips = gv.make_stat_overlays(stats)
    print(f"  {len(stat_clips)} statistic overlays: {[s['text'] for s in stats]}")

    layers = [bg, gv.make_red_atmosphere(total_duration)]
    vignette = gv.make_vignette_overlay(total_duration)
    if vignette:
        layers.append(vignette)
    layers.extend(text_clips)
    layers.extend(stat_clips)

    # 🔥 Hook punch — pattern-interrupt flash in first 0.3s
    layers.extend(gv.make_hook_punch(total_duration))

    twist = gv.make_twist_flash(total_duration)
    if twist:
        layers.append(twist)

    # 💬 CTA overlay — drives comments during OUTRO
    layers.extend(gv.make_cta_overlay(total_duration))

    video = CompositeVideoClip(layers, size=(gv.WIDTH, gv.HEIGHT))
    video = video.with_duration(total_duration).with_audio(final_audio)

    video.write_videofile(
        str(output_path),
        fps=gv.FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp_audio.m4a",
        remove_temp=True,
        logger="bar",
    )

    print(f"  Video saved: {output_path}")
    return output_path


# ── Step 4: Generate Thumbnail ────────────────────────────────────────────────

def step_generate_thumbnail(script_path: Path, topic: str) -> Path:
    log("STEP 4: Generating thumbnail")

    sys.path.insert(0, str(Path(__file__).parent))
    import importlib
    gt = importlib.import_module("generate_thumbnail")

    hook_text    = gt.extract_hook_text(script_path)
    output_path  = Path("thumbnails/exported") / (script_path.stem + ".jpg")
    gt.generate_thumbnail(topic, hook_text, output_path)

    print(f"  Thumbnail saved: {output_path}")
    return output_path


# ── Step 5: Upload to YouTube ─────────────────────────────────────────────────

def step_upload_youtube(video_path: Path, thumbnail_path: Path | None,
                        topic: str) -> str:
    log("STEP 5: Uploading to YouTube")

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    # youtube.upload alone is NOT enough for thumbnails.set — we need force-ssl
    # which grants both video upload + thumbnail set + read access
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.force-ssl",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]
    TOKEN_FILE  = "token.json"
    SECRET_FILE = "client_secret.json"

    creds = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)

    # SEO-optimized metadata via Claude
    try:
        from seo_optimizer import build_youtube_body
        from generate_thumbnail import extract_hook_text
        script_draft = Path("scripts/drafts") / (video_path.stem + ".md")
        hook = extract_hook_text(script_draft) if script_draft.exists() else ""
        body = build_youtube_body(topic, hook)
    except Exception as e:
        print(f"  SEO optimizer failed ({e}) — using basic metadata")
        body = {
            "snippet": {
                "title":                topic[:90],
                "description":          f"{topic}\n\n#VoidPulse #Dark #Facts #Shorts",
                "tags":                 ["voidpulse", "dark facts", "scary truth", "shorts", "horror"],
                "categoryId":           "22",
                "defaultLanguage":      "en",
                "defaultAudioLanguage": "en",
            },
            "status": {
                "privacyStatus":          "public",
                "selfDeclaredMadeForKids": False,
            },
        }

    media    = MediaFileUpload(str(video_path), mimetype="video/mp4",
                               resumable=True, chunksize=5*1024*1024)
    # Include localizations part if body has translations
    parts = "snippet,status"
    if "localizations" in body:
        parts += ",localizations"
    request  = youtube.videos().insert(part=parts, body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"\r  Uploading: {int(status.progress()*100)}%", end="", flush=True)

    video_id = response["id"]
    print(f"\n  Uploaded! https://youtu.be/{video_id}")

    # Set thumbnail if available
    if thumbnail_path and thumbnail_path.exists():
        try:
            thumb_media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
            youtube.thumbnails().set(
                videoId=video_id, media_body=thumb_media
            ).execute()
            print(f"  Thumbnail set!")
        except Exception as e:
            print(f"  Warning: Could not set thumbnail ({e})")

    return video_id


# ── Step 6: Upload to TikTok (optional) ──────────────────────────────────────

def step_upload_tiktok(video_path: Path, topic: str) -> str | None:
    log("STEP 6a: Uploading to TikTok")
    sys.path.insert(0, str(Path(__file__).parent))
    import importlib
    tt = importlib.import_module("upload_tiktok")

    title = f"{topic[:100]} #VoidPulse #DarkFacts #Shorts"
    try:
        return tt.upload_video(video_path, title)
    except EnvironmentError as e:
        print(f"  TikTok skipped — credentials not configured:\n  {e}")
        return None


# ── Step 7: Upload to Instagram (optional) ────────────────────────────────────

def step_upload_instagram(video_path: Path, topic: str,
                          video_url: str | None) -> str | None:
    log("STEP 6b: Uploading to Instagram")
    sys.path.insert(0, str(Path(__file__).parent))
    import importlib
    ig = importlib.import_module("upload_instagram")

    caption = f"{topic}\n\n#VoidPulse #DarkFacts #Shorts #Reels"
    try:
        return ig.upload_reel(video_path, caption, video_url)
    except EnvironmentError as e:
        print(f"  Instagram skipped — credentials not configured:\n  {e}")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse Master Pipeline")
    parser.add_argument("--topic",       default=None,
                        help="Topic (auto-selected if not provided)")
    parser.add_argument("--platforms",   nargs="+", default=["youtube"],
                        choices=["youtube", "tiktok", "instagram"],
                        help="Platforms to upload to (default: youtube)")
    parser.add_argument("--skip-upload", action="store_true",
                        help="Produce video & thumbnail only, skip all uploads")
    parser.add_argument("--no-music",    action="store_true",
                        help="Disable background music")
    parser.add_argument("--music-vol",   type=float, default=0.15,
                        help="Music volume 0.0–1.0 (default 0.15)")
    parser.add_argument("--trending",    action="store_true",
                        help="Pick topic from Google Trends instead of static pool")
    parser.add_argument("--smart",       action="store_true",
                        help="Pick topic via analytics-driven analysis of past performance "
                             "(falls back to --trending then static pool)")
    parser.add_argument("--ig-video-url", default=None,
                        help="Public HTTPS URL for Instagram video (required for Instagram)")
    args = parser.parse_args()

    log_path   = setup_logging()
    start_time = time.time()
    date_str   = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"\n{'#'*55}")
    print(f"  VoidPulse Auto Pipeline — {date_str}")
    print(f"  Log: {log_path}")
    print(f"{'#'*55}")

    topic = args.topic or pick_topic(use_trends=args.trending, use_smart=args.smart)
    print(f"\n  Topic     : {topic}")
    print(f"  Platforms : {', '.join(args.platforms) if not args.skip_upload else 'none (--skip-upload)'}")
    print(f"  Music     : {'off' if args.no_music else f'on ({int(args.music_vol*100)}%)'}")

    from notify import notify

    try:
        script_path    = with_retry(lambda: step_generate_script(topic),    "Script")
        audio_path     = with_retry(lambda: step_generate_voiceover(script_path), "Voiceover")
        video_path     = with_retry(lambda: step_generate_video(
                             script_path, audio_path, topic,
                             no_music=args.no_music, music_vol=args.music_vol), "Video")
        thumbnail_path = with_retry(lambda: step_generate_thumbnail(script_path, topic), "Thumbnail")

        uploaded_ids   = {}

        if not args.skip_upload:
            if "youtube" in args.platforms:
                video_id = with_retry(
                    lambda: step_upload_youtube(video_path, thumbnail_path, topic), "YouTube")
                uploaded_ids["youtube"] = video_id

                from analytics import log_upload
                log_upload(video_id, topic)

            if "tiktok" in args.platforms:
                tt_id = step_upload_tiktok(video_path, topic)
                if tt_id:
                    uploaded_ids["tiktok"] = tt_id

            if "instagram" in args.platforms:
                ig_id = step_upload_instagram(video_path, topic, args.ig_video_url)
                if ig_id:
                    uploaded_ids["instagram"] = ig_id

        import shutil
        final_dir = Path("scripts/final")
        final_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(script_path, final_dir / script_path.name)

        elapsed = int(time.time() - start_time)
        yt_url  = f"https://youtu.be/{uploaded_ids['youtube']}" if uploaded_ids.get("youtube") else ""

        print(f"\n{'#'*55}")
        print(f"  DONE in {elapsed//60}m {elapsed%60}s")
        if yt_url: print(f"  YouTube : {yt_url}")
        print(f"  Video   : {video_path}")
        print(f"  Thumb   : {thumbnail_path}")
        print(f"  Log     : {log_path}")
        print(f"{'#'*55}\n")

        notify(
            f"✅ VoidPulse — فيديو جديد!\n"
            f"📌 {topic}\n"
            f"⏱ {elapsed//60}m {elapsed%60}s\n"
            f"{yt_url}"
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"\n  ERROR: {e}\n{tb}")
        notify(f"❌ VoidPulse — خطأ!\n📌 {topic if 'topic' in dir() else '?'}\n🔴 {e}\nLog: {log_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
