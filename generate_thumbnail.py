"""
VoidPulse Thumbnail Generator
Creates a dramatic 1280x720 YouTube thumbnail using:
  1. Pollinations.ai — AI-generated background image (free, no API key)
  2. Pillow — hook text + red glow + VoidPulse branding overlay

Usage:
    python generate_thumbnail.py --script scripts/drafts/foo.md --topic "Offshore Tax Havens"
    python generate_thumbnail.py --text "They hide TRILLIONS" --topic "Tax Havens"
    python generate_thumbnail.py --text "They hide TRILLIONS" --topic "Tax Havens" --no-ai
"""

import argparse
import re
import sys
import urllib.parse
import urllib.request
import random
from io import BytesIO
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

THUMB_W, THUMB_H = 1280, 720

import platform as _platform
if _platform.system() == "Windows":
    FONT_IMPACT   = "C:/Windows/Fonts/impact.ttf"
    FONT_ARIAL_BD = "C:/Windows/Fonts/arialbd.ttf"
else:
    FONT_IMPACT   = "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf"
    FONT_ARIAL_BD = "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf"

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?width=1280&height=720&nologo=true&seed={seed}&model=flux"

# ── Topic → AI prompt mapping ─────────────────────────────────────────────────

TOPIC_PROMPTS = [
    (["ocean", "plastic", "sea", "water", "marine", "pollution"],
     "dark ocean waves crashing at night, plastic pollution floating, eerie green bioluminescence, cinematic horror"),

    (["billionaire", "money", "wealth", "rich", "tax", "bank", "finance"],
     "dark skyscraper city at night, rain, neon reflections, ominous red sky, surveillance cameras, cinematic"),

    (["social media", "phone", "screen", "algorithm", "internet", "brain", "dumb"],
     "close-up cracked phone screen glowing in darkness, digital glitch distortion, eerie blue light, cinematic"),

    (["food", "eat", "hunger", "farm", "factory", "animal", "meat"],
     "dark industrial factory with ominous smoke, red foggy atmosphere, horror documentary style, cinematic"),

    (["sleep", "insomnia", "tired", "dream"],
     "dark bedroom with shadows creeping on walls, single lamp light, horror atmosphere, cinematic"),

    (["loneliness", "alone", "isolation", "society"],
     "empty dark rainy city street at night, single person walking, fog, dramatic moody atmosphere"),

    (["fashion", "clothes", "textile", "fast fashion"],
     "dark smoky textile factory interior, dim red lights, industrial horror aesthetic, cinematic"),

    (["amazon", "cheap", "supply chain", "worker", "package"],
     "dark warehouse with infinite shelves disappearing into darkness, single worker silhouette, dramatic"),

    (["government", "fear", "control", "power", "surveillance"],
     "ominous surveillance cameras on dark wet city street, red glow, authoritarian aesthetic, cinematic horror"),

    (["house", "rent", "afford", "real estate"],
     "dark abandoned city skyline at night, rain, broken windows glowing red, dystopian cinematic"),
]

DEFAULT_PROMPT = "dark dramatic cinematic scene, ominous red atmosphere, shadows and light, horror documentary style"


def get_ai_prompt(topic: str) -> str:
    t = topic.lower()
    for keywords, prompt in TOPIC_PROMPTS:
        if any(kw in t for kw in keywords):
            return prompt
    return DEFAULT_PROMPT


# ── Pollinations.ai fetcher ───────────────────────────────────────────────────

def fetch_ai_background(topic: str) -> "Image | None":
    try:
        from PIL import Image
    except ImportError:
        return None

    base_prompt = get_ai_prompt(topic)
    full_prompt = f"{base_prompt}, no text, no watermark, ultra detailed"
    encoded     = urllib.parse.quote(full_prompt)
    seed        = random.randint(1, 99999)
    url         = POLLINATIONS_URL.format(prompt=encoded, seed=seed)

    print(f"  AI thumbnail: fetching from Pollinations.ai (seed={seed})...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VoidPulse/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        img = Image.open(BytesIO(data)).convert("RGB")
        img = img.resize((THUMB_W, THUMB_H))
        print(f"  AI background received ({len(data)//1024} KB)")
        return img
    except Exception as e:
        print(f"  Pollinations.ai failed ({e}) — using generated background")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_hook_text(script_path: Path) -> str:
    text = script_path.read_text(encoding="utf-8")
    match = re.search(r"\*\*\[HOOK.*?\]\*\*(.*?)(\*\*\[BUILD|\Z)", text, re.DOTALL)
    if not match:
        return script_path.stem.replace("_", " ").upper()

    body = match.group(1)
    quotes = re.findall(r'"([^"]+)"', body)
    if quotes:
        clean = re.sub(r"\*+", "", quotes[0]).strip()
        return clean
    return script_path.stem.replace("_", " ").upper()


def wrap_lines(text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines or [text]


# ── Main generator ────────────────────────────────────────────────────────────

def generate_thumbnail(topic: str, hook_text: str, output_path: Path,
                       use_ai: bool = True) -> Path:
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance
    except ImportError:
        print("  Error: Pillow not installed. Run: pip install Pillow")
        sys.exit(1)

    # ── Background: AI or generated ───────────────────────────────────────────
    ai_img = fetch_ai_background(topic) if use_ai else None

    if ai_img:
        # Darken the AI image so text stays readable
        enhancer = ImageEnhance.Brightness(ai_img)
        img      = enhancer.enhance(0.45)
        # Slight red color tint overlay
        tint = Image.new("RGB", (THUMB_W, THUMB_H), (60, 0, 0))
        img  = Image.blend(img, tint, alpha=0.25)
    else:
        # Fallback: generated dark background
        img  = Image.new("RGB", (THUMB_W, THUMB_H), color=(4, 4, 8))
        draw = ImageDraw.Draw(img)
        for y in range(THUMB_H):
            ratio = y / THUMB_H
            r = int(35 * (1 - ratio))
            draw.line([(0, y), (THUMB_W, y)], fill=(r, 0, int(8 * (1 - ratio))))
        for i in range(0, 200, 4):
            draw.line([(0, i), (i * 3, 0)], fill=(120, 0, 0, 40), width=2)

    # ── Red glow overlay ──────────────────────────────────────────────────────
    glow_layer = Image.new("RGB", (THUMB_W, THUMB_H), (0, 0, 0))
    glow_draw  = ImageDraw.Draw(glow_layer)
    cx, cy = THUMB_W // 2, THUMB_H // 2
    for radius in range(300, 0, -10):
        alpha = int(30 * (1 - radius / 300))
        glow_draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(alpha, 0, 0)
        )
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(40))
    img  = Image.blend(img, glow_layer, alpha=0.5)
    draw = ImageDraw.Draw(img)

    # ── Fonts ─────────────────────────────────────────────────────────────────
    try:
        font_main  = ImageFont.truetype(FONT_IMPACT, 110)
        font_sub   = ImageFont.truetype(FONT_ARIAL_BD, 42)
        font_brand = ImageFont.truetype(FONT_ARIAL_BD, 36)
    except Exception:
        font_main  = ImageFont.load_default()
        font_sub   = font_main
        font_brand = font_main

    # ── Main text (hook) ──────────────────────────────────────────────────────
    hook_upper = hook_text.upper()
    max_text_w = THUMB_W - 120
    lines = wrap_lines(hook_upper, font_main, max_text_w)

    line_h = 120
    total_text_h = len(lines) * line_h
    y_start = cy - total_text_h // 2 - 30

    for i, line in enumerate(lines):
        bbox = font_main.getbbox(line)
        line_w = bbox[2] - bbox[0]
        x = (THUMB_W - line_w) // 2
        y = y_start + i * line_h

        # Multi-layer shadow for depth
        for offset in range(6, 0, -1):
            draw.text((x + offset, y + offset), line, font=font_main, fill=(0, 0, 0))

        # Red stroke version (offset by 2px)
        draw.text((x + 2, y + 2), line, font=font_main, fill=(180, 0, 0))

        # White main text
        draw.text((x, y), line, font=font_main, fill=(255, 255, 255))

    # ── Topic subtitle ────────────────────────────────────────────────────────
    sub_text = topic.upper()
    bbox = font_sub.getbbox(sub_text)
    sub_w = bbox[2] - bbox[0]
    sub_x = (THUMB_W - sub_w) // 2
    sub_y = y_start + total_text_h + 20

    if sub_y + 60 < THUMB_H - 60:
        draw.text((sub_x + 2, sub_y + 2), sub_text, font=font_sub, fill=(0, 0, 0))
        draw.text((sub_x, sub_y), sub_text, font=font_sub, fill=(200, 50, 50))

    # ── VoidPulse brand bar ───────────────────────────────────────────────────
    bar_h = 56
    draw.rectangle([(0, THUMB_H - bar_h), (THUMB_W, THUMB_H)], fill=(12, 0, 0))
    draw.line([(0, THUMB_H - bar_h), (THUMB_W, THUMB_H - bar_h)], fill=(180, 0, 0), width=2)

    brand = "▶  VOIDPULSE"
    bbox = font_brand.getbbox(brand)
    draw.text(
        ((THUMB_W - (bbox[2] - bbox[0])) // 2, THUMB_H - bar_h + 10),
        brand, font=font_brand, fill=(220, 50, 50)
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "JPEG", quality=95, optimize=True)
    print(f"  Thumbnail saved: {output_path}")
    return output_path


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse Thumbnail Generator")
    parser.add_argument("--script", default=None, help="Script markdown (extracts hook automatically)")
    parser.add_argument("--text",   default=None, help="Override hook text manually")
    parser.add_argument("--topic",  default="VoidPulse", help="Topic label shown as subtitle")
    parser.add_argument("--output", default=None, help="Output JPEG path (auto-named if omitted)")
    parser.add_argument("--no-ai",  action="store_true", help="Skip AI background, use generated dark bg")
    args = parser.parse_args()

    if not args.script and not args.text:
        print("Error: provide --script or --text")
        sys.exit(1)

    if args.text:
        hook_text = args.text
        stem = re.sub(r"[^\w]+", "_", args.topic.lower())[:50]
    else:
        script_path = Path(args.script)
        if not script_path.exists():
            print(f"Error: script not found: {script_path}")
            sys.exit(1)
        hook_text = extract_hook_text(script_path)
        stem = script_path.stem

    output_path = Path(args.output) if args.output else Path("thumbnails/exported") / (stem + ".jpg")

    print(f"\nVoidPulse Thumbnail Generator  {'(no-ai mode)' if args.no_ai else '(AI mode)'}")
    print(f"Hook  : {hook_text[:60]}...")
    print(f"Topic : {args.topic}")
    print(f"Output: {output_path}\n")

    generate_thumbnail(args.topic, hook_text, output_path, use_ai=not args.no_ai)
    print("Done!")


if __name__ == "__main__":
    main()
