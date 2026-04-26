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
import re
import sys
import tempfile
import urllib.request
import urllib.parse
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
    "HOOK":  (0,  5),
    "BUILD": (5,  20),
    "TWIST": (20, 35),
    "OUTRO": (35, 50),
}

import platform as _platform
if _platform.system() == "Windows":
    FONT_IMPACT   = "C:/Windows/Fonts/impact.ttf"
    FONT_ARIAL_BD = "C:/Windows/Fonts/arialbd.ttf"
else:
    FONT_IMPACT   = "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf"
    FONT_ARIAL_BD = "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf"

SECTION_STYLES = {
    "HOOK":  {"color": "white",   "font_size": 88, "stroke_width": 4, "font": FONT_IMPACT},
    "BUILD": {"color": "white",   "font_size": 68, "stroke_width": 2, "font": FONT_ARIAL_BD},
    "TWIST": {"color": "#FF4444", "font_size": 74, "stroke_width": 3, "font": FONT_IMPACT},
    "OUTRO": {"color": "white",   "font_size": 82, "stroke_width": 4, "font": FONT_IMPACT},
}

# ── 7. Topic → multiple background queries ────────────────────────────────────
# Each topic maps to 3 different Pexels queries for visual variety

TOPIC_BACKGROUND_MAP = [
    (["ocean", "plastic", "sea", "water", "marine"],
     ["dark ocean waves night", "underwater dark deep", "pollution water dark"]),

    (["billionaire", "money", "wealth", "rich", "financial", "tax", "bank"],
     ["dark rain city neon night", "stock market crash dark", "luxury car night city"]),

    (["social media", "phone", "screen", "algorithm", "internet", "brain"],
     ["phone screen dark glow", "neon screen glitch dark", "social media addiction dark"]),

    (["food", "eat", "hunger", "farm", "agriculture", "factory", "animal", "meat"],
     ["dark factory smoke", "industrial machinery dark", "foggy field night"]),

    (["sleep", "insomnia", "tired", "dream"],
     ["dark bedroom night shadows", "night city lights blur", "dark fog storm"]),

    (["loneliness", "alone", "isolation", "society"],
     ["empty street night fog", "person alone dark city", "dark rainy window"]),

    (["fashion", "clothes", "textile", "pollution", "fast fashion"],
     ["dark industrial smoke", "factory smoke pollution", "dark city rain"]),

    (["amazon", "cheap", "supply chain", "worker", "package"],
     ["dark warehouse shadows", "shipping containers dark", "industrial night lights"]),

    (["government", "fear", "control", "power", "surveillance"],
     ["abandoned building dark", "cctv camera dark", "dark city surveillance"]),

    (["house", "rent", "afford", "real estate"],
     ["dark city skyline rain", "empty apartments night", "dark urban street"]),

    (["dumb", "stupid", "brain", "cognitive", "phone", "dumber"],
     ["dark static glitch screen", "brain scan dark", "neon tech dark"]),
]

DEFAULT_BG_QUERIES = ["dark horror atmosphere night", "dark fog forest night", "abandoned dark shadows"]


def get_background_queries(topic: str) -> list[str]:
    t = topic.lower()
    for keywords, queries in TOPIC_BACKGROUND_MAP:
        if any(kw in t for kw in keywords):
            return queries
    return DEFAULT_BG_QUERIES


# ── Pexels multi-clip fetcher ─────────────────────────────────────────────────

def fetch_pexels_video(query: str, output_path: Path) -> Path | None:
    """Download one vertical video from Pexels — exact same approach that worked originally."""
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        return None

    # Try the query, then a safe fallback
    for attempt_query in [query, "dark night", "dark forest", "city night"]:
        encoded = urllib.parse.quote(attempt_query)
        url = (f"https://api.pexels.com/videos/search"
               f"?query={encoded}&orientation=portrait&per_page=5&size=medium")
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

        videos = data.get("videos", [])
        for video in videos:
            for vf in video.get("video_files", []):
                if vf.get("file_type") == "video/mp4" and vf.get("link"):
                    try:
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        dl_req = urllib.request.Request(
                            vf["link"],
                            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.pexels.com/"}
                        )
                        with urllib.request.urlopen(dl_req, timeout=60) as resp:
                            output_path.write_bytes(resp.read())
                        print(f"  Downloaded: {output_path.name}")
                        return output_path
                    except Exception as e:
                        print(f"  Download failed: {e}")
                        continue

    print(f"  Pexels: could not download — using dark background")
    return None


def fetch_multiple_clips(queries: list[str], cache_dir: Path) -> list[Path]:
    """Fetch one clip per query, cache them locally."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, query in enumerate(queries):
        slug      = re.sub(r"\W+", "_", query)[:40]
        out_path  = cache_dir / f"{slug}.mp4"
        if out_path.exists():
            print(f"  Cached clip {i+1}: {out_path.name}")
            clips.append(out_path)
        else:
            print(f"  Fetching clip {i+1}: '{query}'...")
            result = fetch_pexels_video(query, out_path)
            if result:
                clips.append(result)
            else:
                print(f"  Could not fetch '{query}'")
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
    if 20.0 >= total_duration:
        return None
    flash = ColorClip(size=(WIDTH, HEIGHT), color=(220, 0, 0), duration=0.25)
    return flash.with_opacity(0.45).with_start(20.0)


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


def make_background_clip(clip_paths: list[Path], duration: float):
    """
    Build a background from multiple clips:
    - Each clip plays for its natural duration (cropped to vertical)
    - Clips cycle until total duration is covered
    - Darkened 65% so text stays readable
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

    # Apply subtle zoom to each clip for cinematic feel
    loaded = [apply_subtle_zoom(c) for c in loaded]

    # Cycle clips until we have enough footage
    combined = []
    total    = 0.0
    while total < duration:
        for clip in loaded:
            combined.append(clip)
            total += clip.duration
            if total >= duration:
                break

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
    Generate procedural SFX using numpy/scipy and cache them in audio/sfx/.
    Returns a dict of {name: path}.
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

    # --- heartbeat.wav: low thump at video start ---
    hb_path = sfx_dir / "heartbeat.wav"
    if not hb_path.exists():
        dur = 0.6
        t   = np.linspace(0, dur, int(sr * dur), endpoint=False)
        # Two quick bass pulses
        pulse = np.exp(-t * 18) * np.sin(2 * np.pi * 60 * t)
        pulse2_start = int(sr * 0.28)
        wave = pulse.copy()
        wave[pulse2_start:] += np.exp(-(t[:len(t)-pulse2_start]) * 22) * np.sin(2 * np.pi * 55 * t[:len(t)-pulse2_start]) * 0.7
        wave = wave / np.max(np.abs(wave)) * 0.85
        stereo = np.column_stack([wave, wave])
        wavfile.write(str(hb_path), sr, (stereo * 32767).astype(np.int16))
        print(f"  SFX generated: heartbeat.wav")
    sfx["heartbeat"] = hb_path

    # --- whoosh.wav: section transition sweep ---
    wh_path = sfx_dir / "whoosh.wav"
    if not wh_path.exists():
        dur = 0.5
        t   = np.linspace(0, dur, int(sr * dur), endpoint=False)
        noise = np.random.randn(len(t))
        # Frequency sweep envelope
        sweep = np.sin(2 * np.pi * (200 + 2000 * t / dur) * t)
        env   = np.exp(-t * 5) * (1 - np.exp(-t * 30))
        wave  = (noise * 0.4 + sweep * 0.6) * env
        wave  = wave / np.max(np.abs(wave)) * 0.75
        stereo = np.column_stack([wave, wave])
        wavfile.write(str(wh_path), sr, (stereo * 32767).astype(np.int16))
        print(f"  SFX generated: whoosh.wav")
    sfx["whoosh"] = wh_path

    # --- impact.wav: sharp hit at TWIST reveal ---
    im_path = sfx_dir / "impact.wav"
    if not im_path.exists():
        dur = 0.4
        t   = np.linspace(0, dur, int(sr * dur), endpoint=False)
        noise = np.random.randn(len(t))
        sub   = np.sin(2 * np.pi * 80 * t)
        env   = np.exp(-t * 25)
        wave  = (noise * 0.5 + sub * 0.5) * env
        wave  = wave / np.max(np.abs(wave)) * 0.90
        stereo = np.column_stack([wave, wave])
        wavfile.write(str(im_path), sr, (stereo * 32767).astype(np.int16))
        print(f"  SFX generated: impact.wav")
    sfx["impact"] = im_path

    return sfx


def mix_audio_with_sfx(voiceover_path: Path, music_path: Path | None,
                       music_volume: float, total_duration: float) -> Path:
    """Mix voiceover + music + SFX overlays at section transitions."""
    from moviepy import AudioFileClip, CompositeAudioClip, concatenate_audioclips
    from moviepy import afx

    sfx_dir = Path("audio/sfx")
    sfx     = generate_sfx(sfx_dir)

    vo = AudioFileClip(str(voiceover_path))

    tracks = [vo]

    # Add background music
    if music_path and music_path.exists():
        music = AudioFileClip(str(music_path))
        if music.duration < total_duration:
            loops = int(total_duration / music.duration) + 1
            music = concatenate_audioclips([music] * loops)
        music = music.subclipped(0, total_duration)
        music = music.with_effects([afx.MultiplyVolume(music_volume)])
        tracks.append(music)

    # Overlay SFX at section transitions
    # HOOK start (0s) → heartbeat
    if "heartbeat" in sfx:
        try:
            hb = AudioFileClip(str(sfx["heartbeat"])).with_start(0.0)
            tracks.append(hb)
        except Exception:
            pass

    # BUILD (5s), OUTRO (35s) → whoosh
    for t in (5.0, 35.0):
        if t < total_duration and "whoosh" in sfx:
            try:
                wh = AudioFileClip(str(sfx["whoosh"])).with_start(t)
                tracks.append(wh)
            except Exception:
                pass

    # TWIST (20s) → impact
    if 20.0 < total_duration and "impact" in sfx:
        try:
            im = AudioFileClip(str(sfx["impact"])).with_start(20.0)
            tracks.append(im)
        except Exception:
            pass

    mixed      = CompositeAudioClip(tracks)
    mixed_path = voiceover_path.parent / (voiceover_path.stem + "_mixed.mp3")
    mixed.write_audiofile(str(mixed_path), fps=44100, logger=None)
    print(f"  Audio mixed: voiceover + music + {len(sfx)} SFX")
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
