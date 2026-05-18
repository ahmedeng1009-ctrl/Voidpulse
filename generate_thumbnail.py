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
    # ── Water / Ocean / Plastic ───────────────────────────────────────────────
    (["ocean", "plastic", "sea", "marine", "pollution"],
     "dark ocean waves crashing at night, plastic pollution floating, eerie green bioluminescence, cinematic horror"),

    (["water bottle", "tap water", "drinking water", "water"],
     "close-up cracked glass of water with dark murky swirling chemicals, ominous red glow, macro horror cinematic"),

    # ── Body / Chemicals / Toxins ─────────────────────────────────────────────
    (["deodorant", "armpit", "lymph", "aluminum"],
     "dark close-up human body silhouette with glowing toxic red veins, horror anatomy, cinematic"),

    (["sunscreen", "skin", "bloodstream", "chemical", "lotion", "cream"],
     "close-up human skin under dark microscope revealing glowing toxic particles, horror macro cinematic"),

    (["plastic", "microplastic", "bottle", "leach"],
     "dark scene of microscopic plastic particles floating in liquid, eerie red glow, horror macro close-up"),

    (["deodorant", "shampoo", "toothpaste", "soap", "cosmetic", "product"],
     "dark bathroom counter with glowing toxic chemical bottles, ominous red shadows, horror cinematic"),

    (["gut", "microbiome", "digestive", "stomach", "intestine"],
     "dark horror close-up of human gut anatomy with glowing red pathways, medical horror cinematic"),

    (["lungs", "breathing", "inhale", "air", "chlorine", "shower"],
     "dark silhouette of human lungs filling with red toxic smoke, horror anatomy cinematic"),

    (["blood", "artery", "heart", "cardiovascular", "sugar", "oxidize"],
     "dark close-up of blood vessels with ominous glowing red particles, horror macro medical cinematic"),

    (["brain", "neuron", "cognitive", "memory", "scroll", "rewire"],
     "dark close-up glowing human brain with red neural pathways firing in darkness, horror cinematic"),

    (["eye", "vision", "blue light", "screen damage"],
     "dark close-up human eye reflecting a cracked glowing screen, eerie horror cinematic"),

    (["spine", "chair", "sitting", "posture", "compression"],
     "dark horror X-ray of human spine with glowing red compression points, medical cinematic"),

    (["cell", "aging", "dna", "telomere", "cellular"],
     "dark microscopic view of human cells deteriorating with red glow, horror medical cinematic"),

    # ── Food / Eating ─────────────────────────────────────────────────────────
    (["food", "eat", "processed", "addictive", "snack", "cereal", "breakfast"],
     "dark industrial food factory with ominous glowing chemicals being injected into products, cinematic horror"),

    (["sugar", "sweetener", "artificial", "candy", "coca"],
     "dark close-up of sugar crystals dissolving in dark liquid with ominous red glow, horror cinematic"),

    (["cooking oil", "fry", "oxidize"],
     "dark close-up of boiling black oil with ominous smoke and red glow, horror macro cinematic"),

    (["farm", "factory farming", "animal", "meat"],
     "dark industrial factory with ominous smoke, red foggy atmosphere, horror documentary style, cinematic"),

    # ── Phone / Tech / Mind ───────────────────────────────────────────────────
    (["phone", "screen", "scroll", "notification", "app", "algorithm", "dumb"],
     "close-up cracked phone screen glowing in darkness, digital glitch distortion, eerie blue light, cinematic"),

    (["social media", "instagram", "tiktok", "internet", "dopamine"],
     "dark cracked phone screen with glowing social media icons leaking red light, horror cinematic"),

    (["headphone", "hearing", "ear", "sound", "noise"],
     "dark close-up human ear with glowing red soundwaves penetrating tissue, horror anatomy cinematic"),

    (["streaming", "netflix", "sleep cycle", "binge"],
     "dark bedroom with single blue TV glow illuminating a sleeping person, horror atmosphere cinematic"),

    # ── Home / Environment ────────────────────────────────────────────────────
    (["air", "indoor", "home", "dust", "toxic", "off-gas", "furniture"],
     "dark living room with invisible toxic particles glowing red in air, horror cinematic"),

    (["receipt", "paper", "bpa", "absorb"],
     "dark close-up hands holding glowing toxic receipt paper with red chemical absorption effect"),

    (["clothes", "dye", "sweat", "textile", "fashion"],
     "dark smoky textile factory interior, dim red lights, industrial horror aesthetic, cinematic"),

    (["car", "freshener", "carcinogen", "exhaust"],
     "dark interior of a car at night with red glowing toxic particles in the air, horror cinematic"),

    # ── Money / Society ───────────────────────────────────────────────────────
    (["billionaire", "money", "wealth", "rich", "tax", "bank", "finance"],
     "dark skyscraper city at night, rain, neon reflections, ominous red sky, surveillance cameras, cinematic"),

    (["credit card", "debt", "spend", "overspend"],
     "dark close-up glowing credit card with brain wires attached, horror psychology cinematic"),

    (["gym", "membership", "exercise", "fitness"],
     "dark empty gym at night with single red emergency light, horror atmosphere cinematic"),

    (["government", "fear", "control", "power", "surveillance"],
     "ominous surveillance cameras on dark wet city street, red glow, authoritarian aesthetic, cinematic horror"),

    (["house", "rent", "afford", "real estate", "housing"],
     "dark abandoned city skyline at night, rain, broken windows glowing red, dystopian cinematic"),

    (["loneliness", "alone", "isolation", "society"],
     "empty dark rainy city street at night, single person walking, fog, dramatic moody atmosphere"),

    (["amazon", "cheap", "supply chain", "worker", "package"],
     "dark warehouse with infinite shelves disappearing into darkness, single worker silhouette, dramatic"),
]

DEFAULT_PROMPT = "dark dramatic cinematic close-up scene, glowing red toxic particles in darkness, horror documentary style, ominous atmosphere"


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


def generate_hook_with_claude(topic: str) -> str:
    """Generate a punchy ≤8-word thumbnail hook via Claude when no script exists."""
    try:
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            messages=[{"role": "user", "content": (
                f'Write ONE thumbnail hook line for a dark-facts YouTube Short about:\n"{topic}"\n\n'
                f'Rules: ≤8 words, present tense, second person (you/your), '
                f'one shocking fact or threat, no filler words.\n'
                f'Return ONLY the hook — no quotes, no explanation.'
            )}],
        )
        hook = resp.content[0].text.strip().strip('"').strip("'")
        if hook and len(hook.split()) <= 10:
            return hook
    except Exception:
        pass
    # Fallback: use topic words
    words = topic.split()
    return " ".join(words[:6]).upper()


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

    # ── Dynamic font size — fewer words = bigger text = more readable at thumb size
    word_count = len(hook_text.split())
    if word_count <= 3:
        font_size = 135
    elif word_count <= 5:
        font_size = 115
    elif word_count <= 7:
        font_size = 95
    else:
        font_size = 78

    try:
        font_main  = ImageFont.truetype(FONT_IMPACT, font_size)
        font_brand = ImageFont.truetype(FONT_ARIAL_BD, 36)
    except Exception:
        font_main  = ImageFont.load_default()
        font_brand = font_main

    # ── Main text (hook) ──────────────────────────────────────────────────────
    hook_upper = hook_text.upper()
    max_text_w = THUMB_W - 100
    lines = wrap_lines(hook_upper, font_main, max_text_w)

    line_h     = int(font_size * 1.22)
    total_text_h = len(lines) * line_h
    # Place text in the upper-centre zone — Shorts thumbnails get cropped on mobile
    y_start = max(40, cy - total_text_h // 2 - 50)

    # ── Semi-transparent dark boxes behind each line (readability on any bg) ──
    img_rgba = img.convert("RGBA")
    box_overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    box_draw    = ImageDraw.Draw(box_overlay)

    line_metrics = []
    for i, line in enumerate(lines):
        bbox   = font_main.getbbox(line)
        line_w = bbox[2] - bbox[0]
        line_h_actual = bbox[3] - bbox[1]
        x = (THUMB_W - line_w) // 2
        y = y_start + i * line_h
        line_metrics.append((x, y, line_w, line_h_actual))
        pad_x, pad_y = 22, 10
        box_draw.rectangle(
            [x - pad_x, y - pad_y,
             x + line_w + pad_x, y + line_h_actual + pad_y],
            fill=(0, 0, 0, 165),
        )

    img = Image.alpha_composite(img_rgba, box_overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # ── Draw text lines ───────────────────────────────────────────────────────
    for i, (line, (x, y, _, _)) in enumerate(zip(lines, line_metrics)):
        # Deep shadow
        for offset in range(5, 0, -1):
            draw.text((x + offset, y + offset), line, font=font_main, fill=(0, 0, 0))
        # Red stroke
        draw.text((x + 2, y + 2), line, font=font_main, fill=(200, 0, 0))
        # White main text — first line gets a warm-yellow tint to draw the eye
        color = (255, 240, 80) if i == 0 and len(lines) > 1 else (255, 255, 255)
        draw.text((x, y), line, font=font_main, fill=color)

    # ── Warning badge — top-left corner (pattern interrupt) ───────────────────
    try:
        font_badge = ImageFont.truetype(FONT_ARIAL_BD, 48)
    except Exception:
        font_badge = font_brand
    badge = "⚠"
    try:
        bx, by = 18, 14
        draw.text((bx + 2, by + 2), badge, font=font_badge, fill=(0, 0, 0))
        draw.text((bx, by), badge, font=font_badge, fill=(255, 60, 0))
    except Exception:
        pass  # emoji may not render on all systems — non-critical

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
