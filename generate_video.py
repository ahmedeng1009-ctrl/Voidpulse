"""
VoidPulse Video Generator
Produces a vertical YouTube Short (1080x1920) with:
  - Multiple topic-specific Pexels clips cycling as background
  - Karaoke-style animated text (phrase by phrase)
  - Dark ambient background music mixed at 25% volume

Usage:
    python generate_video.py --audio audio/voiceover/foo.mp3 \
                             --script scripts/drafts/foo.md \
                             --topic "offshore tax havens"
"""

import argparse
import json
import os
import random
import re
import sys
import tempfile
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)

load_dotenv()

# ── Video config ──────────────────────────────────────────────────────────────

WIDTH, HEIGHT = 1080, 1920
FPS           = 30
BG_COLOR      = (5, 5, 10)

SECTION_TIMES = {
    "HOOK":  (0,   2),
    "BUILD": (2,  15),
    "TWIST": (15, 25),
    "OUTRO": (25, 32),
}

import platform as _platform
if _platform.system() == "Windows":
    FONT_IMPACT   = "C:/Windows/Fonts/impact.ttf"
    FONT_ARIAL_BD = "C:/Windows/Fonts/arialbd.ttf"
else:
    FONT_IMPACT   = "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf"
    FONT_ARIAL_BD = "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf"

SECTION_STYLES = {
    "HOOK":  {"color": "white",   "font_size": 110, "stroke_width": 6, "font": FONT_IMPACT},
    "BUILD": {"color": "white",   "font_size": 68,  "stroke_width": 2, "font": FONT_ARIAL_BD},
    "TWIST": {"color": "#FF4444", "font_size": 74,  "stroke_width": 3, "font": FONT_IMPACT},
    "OUTRO": {"color": "white",   "font_size": 82,  "stroke_width": 4, "font": FONT_IMPACT},
}

# ── 7. Topic → multiple background queries ────────────────────────────────────
# Each topic maps to 6 different Pexels queries for richer visual variety

TOPIC_BACKGROUND_MAP = [
    # ── Drinking water / chemicals / PFAS ─────────────────────────────────────
    (["drinking water", "tap water", "water supply", "forever chemical", "pfas",
      "fluoride", "contaminated water", "blood chemical"],
     ["polluted river dark night", "industrial chemical plant dark", "water treatment plant night",
      "dripping tap close up dark", "chemical barrels industrial dark", "toxic water pollution"]),

    # ── Ocean / plastic / marine pollution ────────────────────────────────────
    (["ocean", "plastic", "sea", "marine", "coral"],
     ["dark ocean waves night", "underwater dark deep", "pollution water dark",
      "stormy sea black", "dead fish ocean dark", "plastic floating sea"]),

    # ── Money / wealth / billionaire / wages / debt ───────────────────────────
    (["billionaire", "money", "wealth", "rich", "financial", "tax", "bank",
      "credit score", "debt", "loan", "mortgage", "wage", "salary", "poverty",
      "inflation", "wall street", "stock"],
     ["dark rain city neon night", "stock market crash dark", "luxury car night city",
      "money burning fire", "wall street dark night", "gold coins falling dark"]),

    # ── Social media / phone / algorithm / streaming / attention ──────────────
    (["social media", "phone", "screen", "algorithm", "internet", "brain",
      "streaming", "netflix", "binge", "scroll", "tiktok", "dopamine",
      "attention", "addic"],
     ["phone screen dark glow", "neon screen glitch dark", "social media addiction dark",
      "scrolling phone late night", "data code matrix dark", "broken screen glitch"]),

    # ── Food / gut / processed / factory farming ──────────────────────────────
    (["food", "eat", "hunger", "farm", "agriculture", "factory", "animal", "meat",
      "gut", "processed", "ultra-processed", "microbiome", "sugar", "obesity",
      "diet", "nutrition", "calorie"],
     ["dark factory smoke night", "industrial machinery dark", "foggy field night",
      "processed food packaging dark", "fast food close up dark", "chemical lab dark"]),

    # ── Sleep / mattress / bed / insomnia ─────────────────────────────────────
    (["sleep", "insomnia", "tired", "dream", "mattress", "bed", "bedroom",
      "eight hours", "rest", "pillow", "foam", "toxic bed"],
     ["dark bedroom shadows night", "alarm clock dark room", "person lying bed dark",
      "chemical factory smoke dark", "industrial foam production dark", "exhausted person dark"]),

    # ── Loneliness / mental health / isolation ────────────────────────────────
    (["loneliness", "alone", "isolation", "society", "mental health",
      "depression", "anxiety", "connection", "community"],
     ["empty street night fog", "person alone dark city", "dark rainy window",
      "empty subway night", "shadow figure rain", "abandoned phone bench"]),

    # ── Fashion / textile / environment ──────────────────────────────────────
    (["fashion", "clothes", "textile", "pollution", "fast fashion", "garment",
      "cotton", "synthetic fiber"],
     ["dark industrial smoke", "factory smoke pollution", "dark city rain",
      "textile factory workers dark", "clothing landfill dark", "sewing machine dark"]),

    # ── Amazon / supply chain / walmart / corporate labor ─────────────────────
    (["amazon", "cheap", "supply chain", "worker", "package", "warehouse",
      "walmart", "corporation", "retail", "delivery", "minimum wage"],
     ["dark warehouse shadows", "shipping containers dark", "industrial night lights",
      "conveyor belt boxes dark", "delivery trucks night", "packaging factory dark"]),

    # ── Government / surveillance / control / privacy ─────────────────────────
    (["government", "fear", "control", "power", "surveillance", "spy",
      "nsa", "propaganda", "censorship", "data collection", "privacy"],
     ["cctv camera dark sky", "dark city surveillance night", "riot police night",
      "barbed wire fence dark", "drone flying dark sky", "hacker computer dark"]),

    # ── Housing / real estate / rent / homeless ───────────────────────────────
    (["house", "rent", "afford", "real estate", "housing", "landlord",
      "property", "homelessness", "evict"],
     ["dark city skyline rain", "empty apartments night", "dark urban street",
      "for sale sign rain", "abandoned house dark", "construction crane night"]),

    # ── Indoor air / household toxins / breathing ──────────────────────────────
    (["indoor", "air inside", "home air", "household", "air quality",
      "air pollution", "breathing", "lung", "dust", "mold"],
     ["dark living room shadows night", "industrial smoke particles dark",
      "air pollution city dark", "dust particles dark light",
      "chemical fumes dark", "factory exhaust dark night"]),

    # ── Cognitive decline / dumber / attention span ───────────────────────────
    (["dumb", "stupid", "cognitive", "dumber", "attention span", "memory",
      "iq", "intelligence", "brain damage"],
     ["dark static glitch screen", "brain scan dark", "neon tech dark",
      "tv static noise dark", "hypnotic spiral dark", "broken phone dark"]),
]

DEFAULT_BG_QUERIES = [
    "dark city rain night",
    "industrial smoke pollution dark",
    "abandoned building dark shadows",
    "dark underground tunnel night",
    "stormy clouds dark sky",
    "dystopian city nighttime",
]


def get_background_queries(topic: str) -> list[str]:
    t = topic.lower()
    for keywords, queries in TOPIC_BACKGROUND_MAP:
        if any(kw in t for kw in keywords):
            return queries
    return DEFAULT_BG_QUERIES


# ── Pexels multi-clip fetcher ─────────────────────────────────────────────────
# Anti-duplicate strategy:
#   1. Global registry of every Pexels video ID ever downloaded → never reused
#   2. Each topic's base queries are diversified into 12+ unique queries
#      using random visual modifiers ("aerial", "neon", "drone shot", etc.)
#   3. Pexels search returns up to 15 results per query — we randomly pick
#      from the unused ones (not always the top result)

USED_CLIPS_FILE = Path("metadata/used_clips.json")

QUERY_MODIFIERS = [
    "aerial",        "macro close up",  "slow motion",      "rainy",
    "foggy",         "dystopian",       "noir",             "abandoned",
    "drone shot",    "time lapse",      "atmospheric",      "neon",
    "shadow",        "gritty",          "rain dripping",    "smoke",
    "blurred",       "underground",     "twilight",         "moody",
]

DEFAULT_TARGET_CLIPS_PER_VIDEO = 12  # number of unique clips to fetch per video


def load_used_clips() -> dict:
    """Load global registry of every Pexels video ID we've ever used."""
    if not USED_CLIPS_FILE.exists():
        return {}
    try:
        return json.loads(USED_CLIPS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_used_clips(data: dict):
    USED_CLIPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USED_CLIPS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def diversify_queries(base_queries: list[str],
                      target_count: int = DEFAULT_TARGET_CLIPS_PER_VIDEO) -> list[str]:
    """
    Expand a small pool of base queries into `target_count` unique varied queries
    by mixing in random visual modifiers. Order is randomized per video so two
    videos on the same topic get different sequences.
    """
    seen = set()
    out  = []

    # Start with the base queries (shuffled)
    shuffled = list(base_queries)
    random.shuffle(shuffled)
    for q in shuffled:
        if q not in seen:
            out.append(q)
            seen.add(q)

    # Fill the rest with modifier+base combinations
    attempts = 0
    while len(out) < target_count and attempts < 200:
        attempts += 1
        base     = random.choice(base_queries)
        modifier = random.choice(QUERY_MODIFIERS)
        candidate = f"{modifier} {base}"
        if candidate not in seen:
            out.append(candidate)
            seen.add(candidate)

    return out[:target_count]


def fetch_pexels_video(query: str, output_path: Path,
                       used_ids: set[int]) -> tuple[Path, int] | None:
    """
    Download one vertical Pexels video that has NOT been used before.
    Returns (path, video_id) on success, or None.
    """
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        return None

    # Try the query first, then safe fallbacks
    for attempt_query in [query, "dark night", "dark forest", "city night"]:
        encoded = urllib.parse.quote(attempt_query)
        url = (f"https://api.pexels.com/videos/search"
               f"?query={encoded}&orientation=portrait&per_page=15&size=medium")
        req = urllib.request.Request(url, headers={
            "Authorization": api_key,
            "User-Agent": "VoidPulse/1.0",
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            print(f"  Pexels request failed ({e})")
            continue

        # Filter out videos we've already used in any past video
        videos = [v for v in data.get("videos", []) if v.get("id") not in used_ids]
        if not videos:
            print(f"  All results for '{attempt_query}' already used — trying fallback")
            continue

        # Randomize order so we don't always pick the top result
        random.shuffle(videos)

        for video in videos:
            vid_id = video.get("id")
            if not vid_id:
                continue
            for vf in video.get("video_files", []):
                if vf.get("file_type") == "video/mp4" and vf.get("link"):
                    try:
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        dl_req = urllib.request.Request(
                            vf["link"],
                            headers={"User-Agent": "Mozilla/5.0",
                                     "Referer": "https://www.pexels.com/"}
                        )
                        with urllib.request.urlopen(dl_req, timeout=60) as resp:
                            output_path.write_bytes(resp.read())
                        print(f"  Downloaded: {output_path.name}  (id={vid_id})")
                        return output_path, int(vid_id)
                    except Exception as e:
                        print(f"  Download failed: {e}")
                        continue

    print(f"  Pexels: could not find unused clip for '{query}'")
    return None


def fetch_multiple_clips(queries: list[str], cache_dir: Path,
                         topic_label: str = "",
                         target_count: int = DEFAULT_TARGET_CLIPS_PER_VIDEO) -> list[Path]:
    """
    Fetch unique, never-before-used Pexels clips for this video.
    - Diversifies queries with random modifiers
    - Tracks every downloaded clip ID globally to prevent reuse
    - Returns paths to local mp4 files
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    used_clips_db = load_used_clips()
    used_ids      = {int(k) for k in used_clips_db.keys()}

    # Expand to target_count diversified queries (shuffled)
    queries = diversify_queries(queries, target_count=target_count)
    print(f"  Diversified to {len(queries)} unique queries — anti-duplicate mode")

    clips = []
    for i, query in enumerate(queries):
        slug     = re.sub(r"\W+", "_", query)[:40]
        out_path = cache_dir / f"{slug}.mp4"

        if out_path.exists():
            # Cached from a previous run of THIS topic — safe to reuse here
            print(f"  Cached clip {i+1}/{len(queries)}: {out_path.name}")
            clips.append(out_path)
            continue

        print(f"  Fetching clip {i+1}/{len(queries)}: '{query}'...")
        result = fetch_pexels_video(query, out_path, used_ids)
        if not result:
            continue

        path, video_id = result
        clips.append(path)

        # Register globally so this clip is never reused in future videos
        used_ids.add(video_id)
        used_clips_db[str(video_id)] = {
            "query":      query,
            "filename":   path.name,
            "topic":      topic_label,
            "downloaded": datetime.now().isoformat(timespec="seconds"),
        }
        save_used_clips(used_clips_db)

    print(f"  Total unique clips for this video: {len(clips)}")
    return clips


# ── CTA overlay ──────────────────────────────────────────────────────────────

def make_cta_overlay(total_duration: float) -> list:
    """
    Persistent "💬 Comment below ↓" bar that appears during the OUTRO section.
    Drives comments — the strongest algorithm signal after watch time.
    """
    outro_start, outro_end = SECTION_TIMES["OUTRO"]
    cta_start = min(outro_start, total_duration - 1.0)
    cta_dur   = max(total_duration - cta_start, 0.5)

    clips = []
    try:
        # Semi-transparent dark background pill
        bg = ColorClip(size=(WIDTH, 90), color=(0, 0, 0), duration=cta_dur)
        bg = bg.with_opacity(0.55).with_start(cta_start)
        bg = bg.with_position(("center", HEIGHT - 130))
        clips.append(bg)

        # CTA text
        label = TextClip(
            text="💬  Comment below  ↓",
            font_size=52,
            color="#FFFFFF",
            font=FONT_ARIAL_BD,
            stroke_color="#000000",
            stroke_width=1,
            method="label",
        ).with_duration(cta_dur).with_start(cta_start)
        label = label.with_position(("center", HEIGHT - 125))

        fade = min(0.3, cta_dur / 3)
        label = label.with_effects([vfx.CrossFadeIn(fade)])
        clips.append(label)

    except Exception as e:
        print(f"  CTA overlay skipped: {e}")

    return clips


# ── Visual effects helpers ────────────────────────────────────────────────────

def make_vignette_overlay(duration: float):
    """Black edge vignette to focus attention on center text."""
    try:
        import numpy as np
        from moviepy import ImageClip

        x = np.linspace(-1, 1, WIDTH,  dtype=np.float32)
        y = np.linspace(-1, 1, HEIGHT, dtype=np.float32)
        X, Y = np.meshgrid(x, y)
        strength = np.clip((X ** 2 * 0.55 + Y ** 2 * 0.75) ** 0.75, 0, 1)
        alpha    = (strength * 200).astype(np.uint8)

        rgba = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
        rgba[:, :, 3] = alpha          # black pixels, varying transparency
        return ImageClip(rgba, duration=duration)
    except Exception as e:
        print(f"  Vignette skipped: {e}")
        return None


def make_red_atmosphere(duration: float):
    """Subtle red tint over the whole video for atmosphere."""
    clip = ColorClip(size=(WIDTH, HEIGHT), color=(160, 0, 0), duration=duration)
    return clip.with_opacity(0.07)


def make_twist_flash(total_duration: float):
    """Brief red flash at the TWIST section start (t=20s)."""
    if 15.0 >= total_duration:
        return None
    flash = ColorClip(size=(WIDTH, HEIGHT), color=(220, 0, 0), duration=0.25)
    return flash.with_opacity(0.45).with_start(15.0)


def make_hook_punch(total_duration: float) -> list:
    """
    🔥 Pattern interrupt في أول 0.3 ثانية — يجبر المشاهد يوقف عن الـ scroll:
       - فلاش أبيض ساطع (0.0–0.15s)
       - فلاش أحمر داكن (0.15–0.3s)
    """
    if total_duration < 0.5:
        return []

    layers = []
    # White punch — pure attention grabber
    white_flash = (ColorClip(size=(WIDTH, HEIGHT), color=(255, 255, 255), duration=0.15)
                   .with_opacity(0.85).with_start(0.0))
    layers.append(white_flash)

    # Red bleed-out
    red_after = (ColorClip(size=(WIDTH, HEIGHT), color=(180, 0, 0), duration=0.18)
                 .with_opacity(0.55).with_start(0.15))
    layers.append(red_after)

    return layers


def apply_subtle_zoom(clip, zoom: float = 1.06):
    """Static zoom-in so background feels bigger/more cinematic."""
    zoomed = clip.resized(zoom)
    x1 = (zoomed.w - WIDTH)  // 2
    y1 = (zoomed.h - HEIGHT) // 2
    return zoomed.cropped(x1=x1, y1=y1, x2=x1 + WIDTH, y2=y1 + HEIGHT)


# ── Background builder ────────────────────────────────────────────────────────

def crop_to_vertical(clip: VideoFileClip) -> VideoFileClip:
    """Crop any video to 9:16 vertical ratio."""
    orig_w, orig_h = clip.size
    target_ratio   = WIDTH / HEIGHT
    orig_ratio     = orig_w / orig_h

    if orig_ratio > target_ratio:
        new_w = int(orig_h * target_ratio)
        x1    = (orig_w - new_w) // 2
        clip  = clip.cropped(x1=x1, x2=x1 + new_w)
    else:
        new_h = int(orig_w / target_ratio)
        y1    = (orig_h - new_h) // 2
        clip  = clip.cropped(y1=y1, y2=y1 + new_h)

    return clip.resized((WIDTH, HEIGHT))


def make_background_clip(clip_paths: list[Path], duration: float,
                         segment_min: float = 2.5, segment_max: float = 4.5):
    """
    Build a background from multiple clips with rapid, randomized cuts.
    - Each segment is 2.5–4.5s (random) — way more cuts than before
    - Random start point inside each source clip → same clip looks different on reuse
    - Order is reshuffled every cycle so no pattern repeats
    - Darkened 68% so text stays readable
    Result: a 32s video gets ~8–12 cuts instead of 5 long shots.
    """
    if not clip_paths:
        return ColorClip(size=(WIDTH, HEIGHT), color=BG_COLOR, duration=duration)

    loaded = []
    for p in clip_paths:
        try:
            raw = VideoFileClip(str(p))
            raw = crop_to_vertical(raw)
            loaded.append(raw)
        except Exception as e:
            print(f"  Warning: could not load {p.name} ({e})")

    if not loaded:
        return ColorClip(size=(WIDTH, HEIGHT), color=BG_COLOR, duration=duration)

    combined = []
    total    = 0.0
    indices  = list(range(len(loaded)))

    # Build a sequence of short random segments
    while total < duration:
        random.shuffle(indices)        # different order each cycle
        for idx in indices:
            clip = loaded[idx]

            remaining = duration - total
            if remaining <= 0.1:
                break

            # Random segment length within the configured window
            seg_len = random.uniform(segment_min, segment_max)
            seg_len = min(seg_len, clip.duration, remaining)
            if seg_len < 1.0:
                seg_len = min(clip.duration, remaining)

            # Random start position inside the source clip
            max_start = max(0.0, clip.duration - seg_len)
            start     = random.uniform(0, max_start) if max_start > 0.05 else 0.0

            segment = clip.subclipped(start, start + seg_len)
            combined.append(apply_subtle_zoom(segment))
            total += seg_len

            if total >= duration:
                break

    print(f"  Background built: {len(combined)} cuts across {duration:.1f}s "
          f"(avg {duration/max(len(combined),1):.1f}s per cut)")

    bg = concatenate_videoclips(combined)
    bg = bg.subclipped(0, duration)
    bg = bg.with_effects([vfx.MultiplyColor(0.32)])
    return bg


# ── 1. Background music ────────────────────────────────────────────────────────

def generate_ambient_music(duration: float, output_path: Path) -> Path:
    """Generate a dark ambient drone and save as WAV."""
    try:
        import numpy as np
        from scipy.io import wavfile
    except ImportError:
        print("  Warning: numpy/scipy not available — skipping music")
        return output_path

    sr = 44100
    n  = int(sr * duration)
    t  = np.linspace(0, duration, n, endpoint=False)

    # Dark ambient — audible frequencies (works on phone speakers too)
    wave = (
        0.30 * np.sin(2 * np.pi * 220.0 * t) +   # A3
        0.25 * np.sin(2 * np.pi * 261.6 * t) +   # C4 (minor feel)
        0.20 * np.sin(2 * np.pi * 329.6 * t) +   # E4
        0.15 * np.sin(2 * np.pi * 440.0 * t) +   # A4
        0.10 * np.sin(2 * np.pi * 110.0 * t)     # A2 sub layer
    )

    # Slow pulse at 0.1 Hz
    wave *= (0.85 + 0.15 * np.sin(2 * np.pi * 0.10 * t))

    # Fades
    fi = int(sr * 2)
    fo = int(sr * 3)
    wave[:fi]  *= np.linspace(0, 1, fi)
    wave[-fo:] *= np.linspace(1, 0, fo)

    peak = np.max(np.abs(wave))
    if peak > 0:
        wave = wave / peak * 0.80

    # Stereo (duplicate channel)
    stereo = np.column_stack([wave, wave])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(output_path), sr, (stereo * 32767).astype(np.int16))
    print(f"  Generated ambient music: {output_path.name}")
    return output_path


def get_music_path(duration: float) -> Path | None:
    """Pick a random music file each time — different music per video."""
    import random
    music_dir = Path("audio/music")
    music_dir.mkdir(parents=True, exist_ok=True)

    # Collect all user-provided music files (exclude auto-generated drone)
    user_files = []
    for ext in ("*.mp3", "*.wav", "*.ogg", "*.m4a"):
        user_files.extend(
            f for f in music_dir.glob(ext)
            if f.name != "ambient_drone.wav"
        )

    if user_files:
        chosen = random.choice(user_files)
        print(f"  Music: {chosen.name} (random pick from {len(user_files)} tracks)")
        return chosen

    # Fallback: auto-generate drone (always fresh per video)
    gen_path = music_dir / "ambient_drone.wav"
    if gen_path.exists():
        gen_path.unlink()
    generate_ambient_music(max(duration + 5, 65), gen_path)
    return gen_path if gen_path.exists() else None


def mix_audio_to_file(voiceover_path: Path, music_path: Path | None,
                      music_volume: float = 0.25) -> Path:
    """
    Mix voiceover + music using MoviePy's CompositeAudioClip.
    Returns path to the mixed audio file.
    """
    if music_path is None or not music_path.exists():
        return voiceover_path

    try:
        from moviepy import AudioFileClip, CompositeAudioClip, concatenate_audioclips
        from moviepy import afx

        vo    = AudioFileClip(str(voiceover_path))
        music = AudioFileClip(str(music_path))

        # Loop music to match voiceover length
        if music.duration < vo.duration:
            loops = int(vo.duration / music.duration) + 1
            music = concatenate_audioclips([music] * loops)
        music = music.subclipped(0, vo.duration)
        music = music.with_effects([afx.MultiplyVolume(music_volume)])

        mixed = CompositeAudioClip([vo, music])

        mixed_path = voiceover_path.parent / (voiceover_path.stem + "_mixed.mp3")
        mixed.write_audiofile(str(mixed_path), fps=44100, logger=None)
        print(f"  Audio mixed (MoviePy) at {int(music_volume*100)}% music volume")
        return mixed_path

    except Exception as e:
        print(f"  Music mix failed ({e}) — using voiceover only")
        return voiceover_path


# ── SFX generation & mixing ───────────────────────────────────────────────────

def generate_sfx(sfx_dir: Path) -> dict[str, Path]:
    """
    Generate procedural cinematic SFX using numpy/scipy and cache them in audio/sfx/.
    Returns a dict of {name: path}.

    Library:
      - boom        : Deep cinematic boom (sub-bass drop + click attack) for HOOK + TWIST
      - whoosh      : 0.55s sweep transition for BUILD/OUTRO
      - whoosh_short: 0.22s sharp swoosh for stat reveals
      - riser       : 4s rising tension build before TWIST
      - tick        : 0.10s digital tick for stat overlays (alt: glitch)
      - glitch      : 0.15s digital noise burst for stat overlays
      - heartbeat   : 0.6s double bass pulse (legacy, kept for compatibility)
      - impact      : 0.4s sharp hit (legacy, kept for compatibility)
    """
    try:
        import numpy as np
        from scipy.io import wavfile
    except ImportError:
        print("  Warning: numpy/scipy not available — skipping SFX")
        return {}

    sfx_dir.mkdir(parents=True, exist_ok=True)
    sr = 44100
    sfx = {}

    def _save(path: Path, mono: "np.ndarray", peak: float = 0.9):
        mono   = mono / max(np.max(np.abs(mono)), 1e-9) * peak
        stereo = np.column_stack([mono, mono]).astype(np.float32)
        wavfile.write(str(path), sr, (stereo * 32767).astype(np.int16))

    # --- boom.wav: cinematic deep boom (sub-bass drop) for HOOK + TWIST ---
    boom_path = sfx_dir / "boom.wav"
    if not boom_path.exists():
        dur = 1.6
        t   = np.linspace(0, dur, int(sr * dur), endpoint=False)
        # Sub-bass falling sweep 90Hz → 35Hz with long tail
        freq  = 90 - 55 * (1 - np.exp(-t * 4))
        phase = 2 * np.pi * np.cumsum(freq) / sr
        sub   = np.sin(phase)
        # Click attack at very start (transient punch)
        click_len    = int(sr * 0.012)
        click_env    = np.exp(-np.linspace(0, 5, click_len))
        click        = np.random.randn(click_len) * click_env
        # Body envelope: instant attack, slow tail
        env   = np.exp(-t * 1.4) * (1 - np.exp(-t * 80))
        wave  = sub * env
        wave[:click_len] += click * 0.7
        _save(boom_path, wave, peak=0.95)
        print(f"  SFX generated: boom.wav")
    sfx["boom"] = boom_path

    # --- whoosh.wav: improved 0.55s sweep with high-pass air ---
    wh_path = sfx_dir / "whoosh.wav"
    if not wh_path.exists():
        dur = 0.55
        t   = np.linspace(0, dur, int(sr * dur), endpoint=False)
        # Filtered noise sweep
        noise = np.random.randn(len(t))
        # Rising frequency sweep 300 → 4000 Hz
        freq  = 300 + 3700 * (t / dur) ** 2
        phase = 2 * np.pi * np.cumsum(freq) / sr
        tonal = np.sin(phase) * 0.25
        # Bell-shape envelope (rises then falls)
        env   = np.exp(-((t - dur * 0.45) / 0.18) ** 2)
        wave  = (noise * 0.5 + tonal) * env
        _save(wh_path, wave, peak=0.75)
        print(f"  SFX generated: whoosh.wav")
    sfx["whoosh"] = wh_path

    # --- whoosh_short.wav: 0.22s sharp swoosh for stat reveals ---
    ws_path = sfx_dir / "whoosh_short.wav"
    if not ws_path.exists():
        dur = 0.22
        t   = np.linspace(0, dur, int(sr * dur), endpoint=False)
        noise = np.random.randn(len(t))
        freq  = 800 + 3000 * (t / dur)
        phase = 2 * np.pi * np.cumsum(freq) / sr
        tonal = np.sin(phase) * 0.35
        env   = np.exp(-((t - dur * 0.4) / 0.07) ** 2)
        wave  = (noise * 0.45 + tonal) * env
        _save(ws_path, wave, peak=0.7)
        print(f"  SFX generated: whoosh_short.wav")
    sfx["whoosh_short"] = ws_path

    # --- riser.wav: 4s rising tension build (lead-in to TWIST) ---
    riser_path = sfx_dir / "riser.wav"
    if not riser_path.exists():
        dur = 4.0
        t   = np.linspace(0, dur, int(sr * dur), endpoint=False)
        # Rising sub + filtered noise that opens up
        freq_low  = 110 + 250 * (t / dur) ** 1.3      # 110 → 360 Hz
        phase_low = 2 * np.pi * np.cumsum(freq_low) / sr
        low_tone  = np.sin(phase_low) * 0.35

        noise = np.random.randn(len(t))
        # Simulate opening filter: noise amplitude grows exponentially
        noise_env = (np.exp(t / dur * 2.2) - 1) / (np.exp(2.2) - 1)
        # High whine that creeps in
        whine_freq = 600 + 1200 * (t / dur)
        whine_phase= 2 * np.pi * np.cumsum(whine_freq) / sr
        whine      = np.sin(whine_phase) * 0.12 * (t / dur) ** 2
        # Master envelope: starts quiet, peaks at end
        master_env = (t / dur) ** 1.5
        wave = (low_tone + noise * 0.35 * noise_env + whine) * master_env
        # Smooth fade-in for first 100ms
        fade_in = int(sr * 0.1)
        wave[:fade_in] *= np.linspace(0, 1, fade_in)
        _save(riser_path, wave, peak=0.7)
        print(f"  SFX generated: riser.wav (4s tension build)")
    sfx["riser"] = riser_path

    # --- tick.wav: 0.10s digital tick for stat overlays ---
    tick_path = sfx_dir / "tick.wav"
    if not tick_path.exists():
        dur = 0.10
        t   = np.linspace(0, dur, int(sr * dur), endpoint=False)
        # Bright square-wave click + decay
        click = np.sign(np.sin(2 * np.pi * 1800 * t)) * 0.4
        body  = np.sin(2 * np.pi * 2400 * t) * 0.6
        env   = np.exp(-t * 60)
        wave  = (click + body) * env
        _save(tick_path, wave, peak=0.6)
        print(f"  SFX generated: tick.wav")
    sfx["tick"] = tick_path

    # --- glitch.wav: 0.15s digital noise burst (alt to tick) ---
    glitch_path = sfx_dir / "glitch.wav"
    if not glitch_path.exists():
        dur = 0.15
        t   = np.linspace(0, dur, int(sr * dur), endpoint=False)
        # Bit-crushed noise with rapid amplitude modulation
        noise = np.random.randn(len(t))
        am    = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 60 * t))
        wave  = noise * am * np.exp(-t * 18)
        _save(glitch_path, wave, peak=0.65)
        print(f"  SFX generated: glitch.wav")
    sfx["glitch"] = glitch_path

    # --- heartbeat.wav (legacy) ---
    hb_path = sfx_dir / "heartbeat.wav"
    if not hb_path.exists():
        dur = 0.6
        t   = np.linspace(0, dur, int(sr * dur), endpoint=False)
        pulse = np.exp(-t * 18) * np.sin(2 * np.pi * 60 * t)
        pulse2_start = int(sr * 0.28)
        wave = pulse.copy()
        wave[pulse2_start:] += np.exp(-(t[:len(t)-pulse2_start]) * 22) * np.sin(2 * np.pi * 55 * t[:len(t)-pulse2_start]) * 0.7
        _save(hb_path, wave, peak=0.85)
        print(f"  SFX generated: heartbeat.wav")
    sfx["heartbeat"] = hb_path

    # --- impact.wav (legacy) ---
    im_path = sfx_dir / "impact.wav"
    if not im_path.exists():
        dur = 0.4
        t   = np.linspace(0, dur, int(sr * dur), endpoint=False)
        noise = np.random.randn(len(t))
        sub   = np.sin(2 * np.pi * 80 * t)
        env   = np.exp(-t * 25)
        wave  = (noise * 0.5 + sub * 0.5) * env
        _save(im_path, wave, peak=0.9)
        print(f"  SFX generated: impact.wav")
    sfx["impact"] = im_path

    return sfx


def build_sfx_timeline(sfx: dict[str, Path],
                       stats: list[dict] | None,
                       total_duration: float) -> list[tuple[float, str, float]]:
    """
    Build a list of (start_time, sfx_name, volume) events for the whole video.
    Cinematic event design:
      0.00s  → BOOM (the cinematic hook punch — sub-bass drop)
      0.10s  → whoosh_short (whip into the hook line)
      2.00s  → whoosh (BUILD section transition)
      stat-  → tick or glitch 50ms before each stat overlay
      12.0s  → riser (3s tension build to TWIST)
      15.0s  → BOOM (THE drop — biggest moment of the video)
      25.0s  → whoosh (OUTRO transition)
      30.0s  → whoosh_short (closing punch into final line)
    """
    events: list[tuple[float, str, float]] = []

    def add(t: float, name: str, vol: float = 1.0):
        if t >= total_duration or t < 0:
            return
        if name in sfx:
            events.append((t, name, vol))

    # HOOK PUNCH — cinematic boom + whip
    add(0.00, "boom",         1.00)
    add(0.10, "whoosh_short", 0.65)

    # BUILD transition
    add(2.00, "whoosh", 0.70)

    # Per-stat ticks (alternate tick/glitch for variety)
    if stats:
        for i, stat in enumerate(stats):
            t = stat.get("start", 0) - 0.05
            if t < 0.5:                    # don't double up with hook punch
                continue
            if 14.0 < t < 16.0:            # don't clash with twist boom
                continue
            sfx_name = "tick" if i % 2 == 0 else "glitch"
            add(t, sfx_name, 0.55)

    # TWIST tension build
    twist_t = 15.0
    if twist_t < total_duration:
        # Riser starts 3s before twist (or as much as fits)
        riser_start = max(twist_t - 3.0, 2.5)
        add(riser_start, "riser", 0.60)
        # The drop
        add(twist_t, "boom", 1.00)

    # OUTRO
    add(25.0, "whoosh", 0.70)
    add(30.0, "whoosh_short", 0.55)

    # Sort by start time for cleaner debug output
    events.sort(key=lambda e: e[0])
    return events


def mix_audio_with_sfx(voiceover_path: Path, music_path: Path | None,
                       music_volume: float, total_duration: float,
                       stats: list[dict] | None = None,
                       sfx_volume: float = 0.85) -> Path:
    """
    Mix voiceover + music + cinematic SFX timeline.

    Args:
        stats:      list from extract_stats() — used to time stat-overlay ticks
        sfx_volume: master multiplier for ALL SFX (0.0–1.5). Default 0.85.
    """
    from moviepy import AudioFileClip, CompositeAudioClip, concatenate_audioclips
    from moviepy import afx

    sfx_dir = Path("audio/sfx")
    sfx     = generate_sfx(sfx_dir)

    vo     = AudioFileClip(str(voiceover_path))
    tracks = [vo]

    # Background music
    if music_path and music_path.exists():
        music = AudioFileClip(str(music_path))
        if music.duration < total_duration:
            loops = int(total_duration / music.duration) + 1
            music = concatenate_audioclips([music] * loops)
        music = music.subclipped(0, total_duration)
        music = music.with_effects([afx.MultiplyVolume(music_volume)])
        tracks.append(music)

    # Build cinematic SFX timeline and overlay each event
    events  = build_sfx_timeline(sfx, stats, total_duration)
    applied = 0
    for start, name, vol in events:
        try:
            clip = AudioFileClip(str(sfx[name]))
            # Trim if it would exceed the video
            if start + clip.duration > total_duration:
                clip = clip.subclipped(0, max(total_duration - start, 0.05))
            clip = clip.with_effects([afx.MultiplyVolume(vol * sfx_volume)])
            clip = clip.with_start(start)
            tracks.append(clip)
            applied += 1
        except Exception as e:
            print(f"  SFX skip ({name} @ {start:.1f}s): {e}")

    # Pretty-print the timeline so the user can see what's playing when
    if events:
        print("  SFX timeline:")
        for start, name, vol in events:
            print(f"    {start:5.2f}s  {name:<13} (vol {vol:.2f})")

    mixed      = CompositeAudioClip(tracks)
    mixed_path = voiceover_path.parent / (voiceover_path.stem + "_mixed.mp3")
    mixed.write_audiofile(str(mixed_path), fps=44100, logger=None)
    print(f"  Audio mixed: voiceover + music + {applied}/{len(events)} SFX events")
    return mixed_path


# ── Script parsing ────────────────────────────────────────────────────────────

def extract_sections(md_path: Path) -> dict[str, list[str]]:
    text = md_path.read_text(encoding="utf-8")

    script_match = re.search(r"## SCRIPT(.*?)(## PRODUCTION NOTES|## STATS|$)", text, re.DOTALL)
    if not script_match:
        raise ValueError("Could not find '## SCRIPT' section in the markdown.")
    body = script_match.group(1)

    sections: dict[str, list[str]] = {}
    current = None

    for line in body.splitlines():
        header = re.search(r"\*\*\[(HOOK|BUILD|TWIST|OUTRO)", line)
        if header:
            current = header.group(1)
            sections[current] = []
            continue

        if current is None:
            continue

        line = line.strip()
        if line.startswith(">") or not line:
            continue

        if '"' in line:
            clean  = re.sub(r"\*+", "", line)
            clean  = re.sub(r"\[.*?\]", "", clean)
            quotes = re.findall(r'"([^"]+)"', clean, re.DOTALL)
            for q in quotes:
                q = re.sub(r"\s+", " ", q).strip()
                if q:
                    sections[current].append(q)

    return sections


# ── Stat extraction & big-number overlays ───────────────────────────────────

# نمط لاستخراج الأرقام والإحصائيات المهمة من النص
STAT_PATTERNS = [
    r"\$\s?[\d,]+(?:\.\d+)?\s*(?:trillion|billion|million|thousand|k|m|b)",  # $3 trillion
    r"\$\s?[\d,]+(?:\.\d+)?",                                                # $25,000
    r"\d+(?:\.\d+)?\s?%",                                                    # 92%
    r"\b\d+\s+in\s+\d+\b",                                                   # 1 in 5
    r"\b\d{1,3}(?:,\d{3})+\b",                                              # 1,000,000
    r"\b\d+\s*(?:trillion|billion|million|thousand|years|hours|minutes|times|days)\b",  # 50 years
]


def extract_stats(sections: dict[str, list[str]],
                  total_duration: float) -> list[dict]:
    """
    استخرج الإحصائيات من السكريبت مع توقيت كل واحدة.
    يرجع list of {text, start, duration, section}.
    """
    stats = []
    times = dict(SECTION_TIMES)
    times["OUTRO"] = (times["OUTRO"][0], max(total_duration, times["OUTRO"][1]))

    for section_name, lines in sections.items():
        if section_name not in times:
            continue
        s_start, s_end = times[section_name]
        s_end = min(s_end, total_duration)
        if s_start >= total_duration or not lines:
            continue

        full_text = " ".join(lines)
        section_dur = s_end - s_start

        # Find all stat matches with their position in the text
        matches = []
        for pattern in STAT_PATTERNS:
            for m in re.finditer(pattern, full_text, re.IGNORECASE):
                matches.append((m.start(), m.group().strip()))

        # Deduplicate overlapping matches (keep longest)
        matches.sort()
        clean_matches = []
        last_end = -1
        for pos, text in matches:
            if pos >= last_end:
                clean_matches.append((pos, text))
                last_end = pos + len(text)

        if not clean_matches:
            continue

        # Distribute timing within the section
        for pos, stat_text in clean_matches[:3]:  # max 3 per section
            relative = pos / max(len(full_text), 1)
            stat_start = s_start + relative * section_dur
            stats.append({
                "text":     stat_text.upper(),
                "start":    stat_start,
                "duration": min(2.5, s_end - stat_start),
                "section":  section_name,
            })

    return stats


def make_stat_overlays(stats: list[dict]) -> list[TextClip]:
    """تحوّل الإحصائيات لـ TextClips كبيرة ولامعة تظهر فوق النص الكاراوكي."""
    clips = []
    for stat in stats:
        if stat["duration"] <= 0.3:
            continue

        try:
            # Big bold red stat — يتمركز في أعلى الشاشة عشان ما يخفي الكاراوكي
            clip = TextClip(
                text=stat["text"],
                font_size=140,
                color="#FFE600",          # أصفر لامع للإحصائيات
                font=FONT_IMPACT,
                stroke_color="#990000",   # حافة حمراء داكنة
                stroke_width=8,
                method="caption",
                size=(WIDTH - 80, None),
                text_align="center",
            ).with_duration(stat["duration"]).with_start(stat["start"])

            # موقع: ربع الشاشة العلوي
            clip = clip.with_position(("center", int(HEIGHT * 0.18)))

            # fade in/out + ضربة دخول
            fade = min(0.25, stat["duration"] / 4)
            clip = clip.with_effects([
                vfx.CrossFadeIn(fade),
                vfx.CrossFadeOut(fade),
            ])

            clips.append(clip)
        except Exception as e:
            print(f"  Stat overlay skipped ({stat['text']}): {e}")

    return clips


# ── 2. Karaoke-style text clips ───────────────────────────────────────────────

def make_karaoke_clips(sections: dict[str, list[str]],
                       total_duration: float) -> list[TextClip]:
    PHRASE_SIZE   = 4
    section_order = ["HOOK", "BUILD", "TWIST", "OUTRO"]
    times         = dict(SECTION_TIMES)
    times["OUTRO"] = (times["OUTRO"][0], max(total_duration, times["OUTRO"][1]))

    clips = []
    for name in section_order:
        start, end = times[name]
        end = min(end, total_duration)
        if start >= total_duration:
            break

        lines = sections.get(name, [])
        if not lines:
            continue

        full_text = " ".join(lines)
        words     = full_text.split()
        phrases   = [
            " ".join(words[i:i + PHRASE_SIZE])
            for i in range(0, len(words), PHRASE_SIZE)
        ]
        if not phrases:
            continue

        section_duration = end - start
        phrase_duration  = section_duration / len(phrases)
        style            = SECTION_STYLES[name]

        for i, phrase in enumerate(phrases):
            p_start = start + i * phrase_duration
            p_end   = min(p_start + phrase_duration, total_duration)
            p_dur   = p_end - p_start
            if p_dur <= 0:
                continue

            clip = TextClip(
                text=phrase.upper(),
                font_size=style["font_size"],
                color=style["color"],
                font=style["font"],
                stroke_color="black",
                stroke_width=style["stroke_width"],
                method="caption",
                size=(WIDTH - 120, None),
                text_align="center",
            ).with_duration(p_dur).with_start(p_start)

            clip = clip.with_position(("center", HEIGHT // 2 - clip.h // 2 - 80))

            # Fade in/out for smooth karaoke transitions
            fade = min(0.18, p_dur / 4)
            if fade > 0.05:
                clip = clip.with_effects([
                    vfx.CrossFadeIn(fade),
                    vfx.CrossFadeOut(fade),
                ])

            # 🔥 HOOK gets quick punch-in zoom on the first phrase only
            if name == "HOOK" and i == 0:
                try:
                    clip = clip.resized(lambda t: 1.0 + max(0, 0.12 - t) * 0.8)
                except Exception:
                    pass  # if Resize unavailable, keep static

            clips.append(clip)

    return clips


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse Video Generator")
    parser.add_argument("--audio",     required=True)
    parser.add_argument("--script",    required=True)
    parser.add_argument("--topic",     default=None)
    parser.add_argument("--output",    default=None)
    parser.add_argument("--no-music",  action="store_true")
    parser.add_argument("--music-vol", type=float, default=0.25)
    args = parser.parse_args()

    audio_path  = Path(args.audio)
    script_path = Path(args.script)

    if not audio_path.exists():
        print(f"Error: audio not found: {audio_path}"); sys.exit(1)
    if not script_path.exists():
        print(f"Error: script not found: {script_path}"); sys.exit(1)

    output_dir  = Path("video/exports")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else output_dir / (script_path.stem + ".mp4")
    topic       = args.topic or script_path.stem.replace("_", " ")
    bg_queries  = get_background_queries(topic)

    print(f"\nVoidPulse Video Generator")
    print(f"Topic  : {topic}")
    print(f"BG     : {bg_queries}")
    print(f"Output : {output_path}\n")

    # Fetch/cache background clips
    cache_dir  = Path("video/backgrounds") / re.sub(r"\W+", "_", topic)[:40]
    clip_paths = fetch_multiple_clips(bg_queries, cache_dir)

    # Parse script & load audio
    sections       = extract_sections(script_path)
    voiceover      = AudioFileClip(str(audio_path))
    total_duration = voiceover.duration
    print(f"Duration: {total_duration:.1f}s")

    # Mix music + SFX
    if not args.no_music:
        music_path       = get_music_path(total_duration)
        mixed_audio_path = mix_audio_with_sfx(audio_path, music_path, args.music_vol, total_duration)
        final_audio      = AudioFileClip(str(mixed_audio_path))
    else:
        final_audio = voiceover

    # Build video
    bg         = make_background_clip(clip_paths, total_duration)
    text_clips = make_karaoke_clips(sections, total_duration)
    print(f"{len(text_clips)} karaoke phrase clips")

    # Assemble layers: bg → atmosphere → vignette → text → twist flash
    layers = [bg, make_red_atmosphere(total_duration)]
    vignette = make_vignette_overlay(total_duration)
    if vignette:
        layers.append(vignette)
    layers.extend(text_clips)
    twist = make_twist_flash(total_duration)
    if twist:
        layers.append(twist)

    video = CompositeVideoClip(layers, size=(WIDTH, HEIGHT))
    video = video.with_duration(total_duration).with_audio(final_audio)

    video.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp_audio.m4a",
        remove_temp=True,
        logger="bar",
    )
    print(f"\nDone! {output_path}")


if __name__ == "__main__":
    main()
