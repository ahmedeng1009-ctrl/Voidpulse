"""
VoidPulse SEO Optimizer
Uses Claude to generate YouTube-optimized title, description, and tags
for each video — maximizing discoverability and click-through rate.

Usage:
    python seo_optimizer.py --topic "The dark truth about sleep deprivation"
    python seo_optimizer.py --script scripts/drafts/foo.md
"""

import argparse
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a YouTube SEO expert specializing in dark, viral short-form content
that targets a GLOBAL English-speaking audience (US, UK, Canada, Australia, India, Europe).
Your job is to write metadata that maximizes impressions, CTR, and watch time worldwide.

Rules:
- Title: max 70 chars, starts with a shocking hook word or number, no clickbait lies
- Description: 4–5 lines, first line is the hook, MUST end with hashtags where #Shorts is
  the very first hashtag (critical for YouTube to classify as a Short), followed by
  2-3 English hashtags + 1-2 hashtags in: español, français, deutsch, हिन्दी
  Example ending: #Shorts #VoidPulse #DarkFacts #Facts #Shorts #Hechos #Faits
- Tags: 22–28 tags, lowercase, must include:
    * Broad universal tags: shorts, viral, facts, mindblowing, documentary
    * Topic-specific keywords (3-5)
    * Region/audience tags: usa, uk, india, europe, worldwide
    * Trending niches: psychology, conspiracy, dark truth, hidden facts
    * No country-restrictive tags

Always return valid JSON only — no markdown, no explanation."""

USER_TEMPLATE = """Generate YouTube SEO metadata for this VoidPulse video.

Topic: {topic}
Hook line: {hook}
Style: dark, dramatic, conspiracy-core, fact-based

Return ONLY this JSON:
{{
  "title": "...",
  "description": "...",
  "tags": ["tag1", "tag2", ...]
}}"""

# ── Core function ─────────────────────────────────────────────────────────────

def generate_seo_metadata(topic: str, hook: str = "") -> dict:
    """Call Claude to generate SEO-optimized YouTube metadata."""
    import anthropic

    client = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": USER_TEMPLATE.format(
                topic=topic,
                hook=hook or topic,
            ),
        }],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        metadata = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: build basic metadata
        print(f"  Warning: Claude returned invalid JSON — using fallback metadata")
        metadata = _fallback_metadata(topic)

    # Enforce title length — 70 chars is the YouTube SEO optimum
    title = metadata.get("title", "")
    if len(title) > 70:
        print(f"  ⚠️  Title too long ({len(title)} chars) — asking Claude to shorten...")
        import anthropic as _anth
        fix_resp = _anth.Anthropic().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": (
                f"Shorten this YouTube title to STRICTLY under 70 characters. "
                f"Keep it shocking and punchy. Return ONLY the new title, nothing else.\n\n"
                f"ORIGINAL: {title}"
            )}],
        )
        short = fix_resp.content[0].text.strip().strip('"')
        metadata["title"] = short[:70] if len(short) > 70 else short
        print(f"  ✅ Title fixed ({len(metadata['title'])} chars): {metadata['title']}")

    # Guarantee #Shorts is in the description — required for YouTube to classify as a Short
    desc = metadata.get("description", "")
    if "#Shorts" not in desc and "#shorts" not in desc:
        metadata["description"] = desc.rstrip() + "\n#Shorts #VoidPulse #DarkFacts"

    # AI disclosure — required by YouTube policy for AI-generated content
    desc = metadata.get("description", "")
    if "AI-generated" not in desc:
        metadata["description"] = desc.rstrip() + "\n\n(AI-generated content)"

    return metadata


def _fallback_metadata(topic: str) -> dict:
    slug = topic.replace(" ", " ").title()
    return {
        "title": f"The Dark Truth About {slug[:50]}",
        "description": (
            f"{topic}\n\n"
            "The truth they don't want you to see. "
            "Dark facts, real statistics, uncomfortable truths.\n\n"
            "#VoidPulse #DarkFacts #Shorts #ScaryTruths #Facts"
        ),
        "tags": [
            "voidpulse", "dark facts", "scary truth", "shorts", "facts",
            "uncomfortable truth", "real statistics", "viral", "youtube shorts",
            "horror facts", "mind blowing", "society", "truth exposed",
            "conspiracy", "documentary", "educational", "shocking",
        ],
    }


# ── Best posting time ─────────────────────────────────────────────────────────

def suggest_post_time(log_path: Path = Path("metadata/uploaded_videos.json")) -> str:
    """
    Analyze upload history and YouTube stats to suggest the best posting time.
    Targets English-speaking audiences (US/UK) — critical for Iraq-based uploaders.
    Returns a human-readable recommendation.
    """
    # Iraq is UTC+3. YouTube Shorts peak viewing for US+UK+India:
    #   02:00 Iraq = 23:00 UK = 18:00 US-Eastern = 04:30 IST  ← US prime time ✅ BEST
    #   23:00 Iraq = 20:00 UK = 15:00 US-Eastern              ← UK evening ✅ GOOD
    #   21:00 Iraq = 18:00 UK = 13:00 US-Eastern              ← US lunch, weak
    # Shorts algorithm rewards consistency — same time every single day matters more
    # than picking the "perfect" hour. Miss one day = algorithmic penalty.
    ENGLISH_AUDIENCE_NOTE = (
        "  [Iraq uploader tip] Upload at 02:00 Iraq time DAILY to reach\n"
        "  US (18:00 Eastern) + UK (23:00) — the highest-CPM Shorts audience.\n"
        "  Best days: Tuesday, Wednesday, Thursday (avoid Sat/Sun — lowest reach).\n"
        "  CONSISTENCY beats timing — post every day at the same hour."
    )

    if not log_path.exists():
        return f"No upload history yet.\n{ENGLISH_AUDIENCE_NOTE}"

    try:
        log = json.loads(log_path.read_text(encoding="utf-8"))
    except Exception:
        return "Could not read upload log."

    if not log:
        return f"No uploads logged yet.\n{ENGLISH_AUDIENCE_NOTE}"

    with_views = [e for e in log if e.get("views", 0) > 0]

    if not with_views:
        return f"Not enough performance data yet.\n{ENGLISH_AUDIENCE_NOTE}"

    best = max(with_views, key=lambda x: x.get("views", 0))

    uploaded_at = best.get("uploaded_at", "")
    try:
        hour = int(uploaded_at[11:13])
        day_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        from datetime import datetime
        dt = datetime.fromisoformat(uploaded_at)
        day = day_map[dt.weekday()]
    except Exception:
        return f"Best performer: could not parse upload time.\n{ENGLISH_AUDIENCE_NOTE}"

    return (
        f"Best performer uploaded at {hour:02d}:00 Iraq time on {day} "
        f"→ got {best.get('views', 0):,} views\n"
        f"  Recommendation: post around {hour:02d}:00–{(hour+2)%24:02d}:00 Iraq time on {day}s\n"
        f"{ENGLISH_AUDIENCE_NOTE}"
    )


# ── Localizations: نشر متعدد اللغات للوصول لجميع الدول ───────────────────────

# ندعم اللغات الأكثر مشاهدة على يوتيوب — يغطي مليارات المستخدمين
TARGET_LANGUAGES = {
    "es": "Spanish",        # Spain + Latin America (500M+ speakers)
    "fr": "French",         # France, Canada, Africa (300M+)
    "de": "German",         # Germany, Austria, Switzerland (130M+)
    "pt": "Portuguese",     # Brazil, Portugal (260M+)
    "it": "Italian",        # Italy (60M+)
    "nl": "Dutch",          # Netherlands, Belgium (25M+)
    "hi": "Hindi",          # India (600M+)
}


def generate_localizations(title: str, description: str) -> dict:
    """
    تترجم العنوان والوصف إلى 7 لغات باستخدام Claude.
    يوتيوب راح يعرض كل ترجمة للمستخدم حسب لغة جهازه/بلده.
    """
    import anthropic

    client = anthropic.Anthropic()

    langs_str = ", ".join(f"{code} ({name})" for code, name in TARGET_LANGUAGES.items())

    prompt = f"""Translate this YouTube Short title and description to multiple languages.
Keep the dramatic, dark, viral tone. Keep hashtags in English (don't translate them).
Title max 70 chars in each language.

ORIGINAL TITLE: {title}
ORIGINAL DESCRIPTION: {description}

Languages needed: {langs_str}

Return ONLY valid JSON, no markdown, in this EXACT format:
{{
  "es": {{"title": "...", "description": "..."}},
  "fr": {{"title": "...", "description": "..."}},
  "de": {{"title": "...", "description": "..."}},
  "pt": {{"title": "...", "description": "..."}},
  "it": {{"title": "...", "description": "..."}},
  "nl": {{"title": "...", "description": "..."}},
  "hi": {{"title": "...", "description": "..."}}
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  Warning: Localizations JSON invalid — skipping translations")
        return {}

    valid = {}
    for code, entry in data.items():
        if isinstance(entry, dict) and entry.get("title") and entry.get("description"):
            valid[code] = {
                "title":       entry["title"][:95],
                "description": entry["description"],
            }
    return valid


# ── Apply to YouTube upload ───────────────────────────────────────────────────

def get_next_publish_at() -> str:
    """
    Returns the next 23:00 UTC as an RFC 3339 string.
    23:00 UTC = 02:00 AM Iraq (UTC+3) — peak Shorts audience (US prime time + UK evening).
    If it's already past 23:00 UTC today, schedules for tomorrow.
    """
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    target = now.replace(hour=23, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_youtube_body(topic: str, hook: str, video_id_placeholder: str = "") -> dict:
    """Return the full YouTube API request body with SEO metadata + localizations + affiliates."""
    print("  Generating SEO metadata with Claude...")
    meta = generate_seo_metadata(topic, hook)

    publish_at = get_next_publish_at()
    print(f"  Title      : {meta['title']}")
    print(f"  Tags       : {len(meta['tags'])} tags")
    print(f"  Publish at : {publish_at}  (= 02:00 AM Iraq)")

    # Append affiliate links to description
    try:
        from affiliate_links import build_affiliate_section
        affiliate_section = build_affiliate_section(topic)
        if affiliate_section:
            meta["description"] = meta["description"].rstrip() + "\n" + affiliate_section
            print(f"  Affiliates: added to description")
    except Exception as e:
        print(f"  Affiliates skipped ({e})")

    # Generate translations for global reach
    print("  Generating localizations (7 languages) for global reach...")
    try:
        localizations = generate_localizations(meta["title"], meta["description"])
        if localizations:
            print(f"  Localizations OK: {', '.join(localizations.keys())}")
        else:
            print(f"  Localizations: none generated")
    except Exception as e:
        print(f"  Localizations failed ({e}) — uploading English only")
        localizations = {}

    body = {
        "snippet": {
            "title":                meta["title"],
            "description":          meta["description"],
            "tags":                 meta["tags"][:30],
            "categoryId":           "22",
            "defaultLanguage":      "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus":          "private",
            "publishAt":              get_next_publish_at(),
            "selfDeclaredMadeForKids": False,
        },
    }

    if localizations:
        body["localizations"] = localizations

    return body


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse SEO Optimizer")
    parser.add_argument("--topic",  default=None, help="Video topic")
    parser.add_argument("--script", default=None, help="Script markdown path")
    parser.add_argument("--time",   action="store_true", help="Show best posting time")
    args = parser.parse_args()

    if args.time:
        print("\n" + suggest_post_time())
        return

    if not args.topic and not args.script:
        print("Error: provide --topic or --script")
        return

    topic = args.topic
    hook  = ""

    if args.script:
        from generate_thumbnail import extract_hook_text
        script_path = Path(args.script)
        hook  = extract_hook_text(script_path)
        topic = topic or script_path.stem.replace("_", " ")

    print(f"\nSEO Optimizer — topic: {topic}")
    meta = generate_seo_metadata(topic, hook)

    print(f"\n{'─'*55}")
    print(f"TITLE:\n  {meta['title']}\n")
    print(f"DESCRIPTION:\n{meta['description']}\n")
    print(f"TAGS ({len(meta['tags'])}):\n  {', '.join(meta['tags'])}")
    print(f"{'─'*55}")

    print(f"\n{suggest_post_time()}")


if __name__ == "__main__":
    main()
