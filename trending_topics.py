"""
VoidPulse Trending Topics
Fetches today's trending topics using Gemini (Google Search grounding) or
YouTube Trending API, then uses Claude to reframe them as VoidPulse-style
dark/dramatic video topics.

Usage:
    python trending_topics.py              # show trending topics
    python trending_topics.py --pick       # pick best topic and print it
    python trending_topics.py --region us  # specify region (default: US)
    python trending_topics.py --no-gemini  # skip Gemini, use YouTube only

Requires:
    pip install google-genai
    GEMINI_API_KEY=your_key  in .env
"""

import argparse
import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", encoding="utf-8", override=True)

# ── VoidPulse topic categories (for Claude context) ───────────────────────────

VOIDPULSE_THEMES = [
    "money, wealth inequality, billionaires, taxes, financial system",
    "social media, algorithms, tech addiction, surveillance capitalism",
    "environment, pollution, climate, plastic, ocean",
    "food industry, processed food, addiction, health manipulation",
    "government, power, control, fear, propaganda",
    "housing crisis, rent, real estate, homelessness",
    "mental health, loneliness, depression, society",
    "fast fashion, textile waste, sweatshops",
    "pharmaceutical industry, drug prices, healthcare",
    "work culture, burnout, corporate exploitation",
]

# ── Gemini Google Search Grounding — أحسن مصدر للمواضيع الطازجة ─────────────

GEMINI_TOPIC_PROMPT = """You are a topic researcher for VoidPulse — a viral YouTube Shorts channel
that reveals dark, shocking, uncomfortable truths about health, body, food, tech, and daily life.

Search the web RIGHT NOW for the most disturbing recent facts and studies about:
- Things happening inside the human body (toxins, chemicals, microplastics, hormones)
- Everyday products secretly harming people (food, cosmetics, household items, devices)
- Recent studies exposing health risks most people don't know about
- Corporate or government actions affecting people's health/body without their knowledge

Return exactly 8 VoidPulse-style topics based on what you find TODAY.

Rules for each topic:
- One sentence, 10-18 words
- Present tense, second-person ("your", "you")
- Personal threat — something happening to the viewer's body or daily life RIGHT NOW
- Must be based on a real recent fact or study you found
- Format: "How your [thing] is [doing damage] to your [body part] right now"

Return ONLY the 8 topics, one per line, no numbering, no explanation."""


def fetch_topics_with_gemini(count: int = 8) -> list[str]:
    """
    Use Gemini 2.0 Flash with Google Search grounding to find today's most
    shocking health/body topics from real web results.
    Returns a list of VoidPulse-ready topic strings.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("  [Gemini] GEMINI_API_KEY not set — skipping")
        return []

    # Mode 1: with Google Search grounding (requires billing enabled)
    # Mode 2: without grounding — free tier, uses Gemini's built-in knowledge
    ATTEMPTS = [
        ("gemini-2.0-flash",         True),   # grounding ON  — best results
        ("gemini-2.0-flash",         False),  # grounding OFF — free tier fallback
        ("gemini-2.0-flash-lite",    False),  # smaller model, higher free quota
    ]

    PROMPT_NO_GROUNDING = """You are a topic researcher for VoidPulse — a viral YouTube Shorts channel
revealing dark, shocking truths about health, body, food, tech, and daily life.

Generate 8 VoidPulse-style topics about things that are secretly harming people right now.
Focus on: toxins in everyday products, hidden health risks, corporate deception, body chemistry.

Rules for each topic:
- One sentence, 10-18 words, present tense, second-person ("your", "you")
- Personal body threat — something happening to the viewer RIGHT NOW
- Must sound like a real fact (not vague)
- Format: "How your [everyday object] is [damage verb] your [body] right now"

Return ONLY 8 topics, one per line, no numbering, no explanation."""

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        for model, use_grounding in ATTEMPTS:
            try:
                prompt = GEMINI_TOPIC_PROMPT if use_grounding else PROMPT_NO_GROUNDING
                config_kwargs = dict(temperature=0.8, max_output_tokens=512)

                if use_grounding:
                    config = types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearch())],
                        **config_kwargs,
                    )
                else:
                    config = types.GenerateContentConfig(**config_kwargs)

                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                raw    = response.text.strip()
                topics = [line.strip("•-–*# 1234567890.").strip() for line in raw.splitlines() if line.strip()]
                topics = [t for t in topics if len(t) > 20][:count]

                if topics:
                    mode = "grounding" if use_grounding else "knowledge"
                    print(f"  [Gemini:{model}:{mode}] Found {len(topics)} topics")
                    return topics

            except Exception as e:
                err = str(e)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    print(f"  [Gemini:{model}] Quota exceeded — trying next...")
                    continue
                if "404" in err or "not found" in err.lower():
                    print(f"  [Gemini:{model}] Model not available — trying next...")
                    continue
                if "billing" in err.lower() or "PERMISSION_DENIED" in err:
                    print(f"  [Gemini:{model}] Billing required for grounding — trying without...")
                    continue
                print(f"  [Gemini:{model}] Error: {err[:100]}")
                continue

        print("  [Gemini] All attempts failed — falling back to RSS")
        return []

    except ImportError:
        print("  [Gemini] google-genai not installed — run: pip install google-genai")
        return []
    except Exception as e:
        print(f"  [Gemini] Failed ({type(e).__name__}: {str(e)[:120]})")
        return []


# ── Google Trends RSS (مجاني — بدون API key) ─────────────────────────────────

def fetch_trends_with_rss(region: str = "US", count: int = 20) -> list[str]:
    """
    Fetch real-time trending topics from Google Trends RSS feed.
    100% free, no API key, no billing required.
    """
    import urllib.request
    import xml.etree.ElementTree as ET

    url = f"https://trends.google.com/trending/rss?geo={region}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urllib.request.urlopen(req, timeout=10) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    topics = []
    for item in root.findall(".//item"):
        title = item.findtext("title", "").strip()
        if title and len(title) > 3:
            topics.append(title)

    print(f"  Google Trends RSS: fetched {len(topics)} trending topics")
    return topics[:count]


# ── YouTube Trending fetcher ──────────────────────────────────────────────────

def fetch_youtube_trending(region: str = "US", max_results: int = 25) -> list[str]:
    """
    Fetch trending YouTube video titles using the existing YouTube API credentials.
    Categories: 25=News, 22=People&Blogs, 27=Education, 28=Science&Tech
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        TOKEN_FILE  = "token.json"
        SECRET_FILE = "client_secret.json"
        SCOPES      = ["https://www.googleapis.com/auth/youtube.upload",
                       "https://www.googleapis.com/auth/youtube.readonly"]

        creds = None
        if Path(TOKEN_FILE).exists():
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())

        youtube = build("youtube", "v3", credentials=creds)

        # Fetch overall trending without category filter (most reliable)
        resp = youtube.videos().list(
            part="snippet",
            chart="mostPopular",
            regionCode=region,
            maxResults=max_results,
        ).execute()
        titles = [
            item["snippet"].get("title", "")
            for item in resp.get("items", [])
            if item["snippet"].get("title")
        ]

        print(f"  Fetched {len(titles)} trending YouTube titles")
        return titles

    except Exception as e:
        err = str(e)
        if "insufficientPermissions" in err or "insufficient" in err.lower():
            # Token missing youtube.readonly scope — delete and prompt re-auth
            token = Path("token.json")
            if token.exists():
                token.unlink()
                print("  Token refreshed — run again to re-authenticate with full permissions")
        else:
            print(f"  YouTube Trending error: {e}")
        return []


# ── Claude: trend → VoidPulse topic ──────────────────────────────────────────

def trends_to_voidpulse_topics(trends: list[str], count: int = 5) -> list[str]:
    """
    Use Claude to convert trending searches into VoidPulse-style dark topics.
    Returns a list of ready-to-use topic strings.
    """
    import anthropic

    if not trends:
        return []

    client   = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    themes   = "\n".join(f"- {t}" for t in VOIDPULSE_THEMES)
    trend_list = "\n".join(f"- {t}" for t in trends[:25])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=[{
            "type": "text",
            "text": (
                "You are a viral YouTube Shorts topic strategist for VoidPulse — "
                "a dark, fact-based channel revealing uncomfortable truths.\n\n"
                "VoidPulse themes:\n" + themes
            ),
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": (
                f"Today's trending searches:\n{trend_list}\n\n"
                f"Pick or combine {count} trends and reframe them as dramatic VoidPulse topics. "
                "Each topic should be a shocking, fact-based revelation. "
                "Format: one topic per line, no numbering, no explanation."
            ),
        }],
    )

    raw    = response.content[0].text.strip()
    topics = [line.strip("•-– ").strip() for line in raw.splitlines() if line.strip()]
    topics = [t for t in topics if len(t) > 15][:count]
    return topics


# ── Fallback: curated evergreen topics ───────────────────────────────────────

EVERGREEN_TOPICS = [
    "The dark truth about how credit card companies trap you forever",
    "How pharmaceutical companies create diseases to sell you cures",
    "The real reason your food is making you sick and addicted",
    "How corporations legally steal billions through stock buybacks",
    "The terrifying truth about what social media does to your brain",
    "How the housing market was rigged against you from the start",
    "The dark secret behind why you're always tired and depressed",
    "How governments use debt to control entire populations",
    "The shocking truth about what's in your drinking water",
    "How corporations manipulate your emotions to make you spend more",
    "The hidden reason why antibiotics are becoming useless",
    "How streaming platforms are making you lonelier and poorer",
]


def get_topic_for_today(region: str = "US",
                        use_trends: bool = True,
                        use_gemini: bool = True) -> str:
    """
    Get the best topic for today's video.
    Priority: Gemini (Google Search) → YouTube Trending → Evergreen pool.
    """
    used_file = Path("metadata/used_topics.txt")
    used = set()
    if used_file.exists():
        used = set(used_file.read_text(encoding="utf-8").splitlines())

    if use_trends:
        # 1️⃣ Gemini + Google Search Grounding — أحسن مصدر، يجيب حقائق اليوم
        print("  [Gemini] Searching web for today's shocking health/body facts...")
        gemini_topics = fetch_topics_with_gemini(count=8)
        fresh = [t for t in gemini_topics if t not in used]
        if fresh:
            topic = fresh[0]
            print(f"  [Gemini] Selected: {topic}")
            return topic

        # 2️⃣ Google Trends RSS — مجاني، بدون API key
        try:
            print("  [RSS] Checking Google Trends RSS...")
            trends = fetch_trends_with_rss(region=region)
            if trends:
                vp_topics = trends_to_voidpulse_topics(trends, count=8)
                fresh = [t for t in vp_topics if t not in used]
                if fresh:
                    topic = fresh[0]
                    print(f"  [RSS] Selected: {topic}")
                    return topic
        except Exception as e:
            print(f"  [RSS] Failed ({e}) — trying YouTube API...")

        # 3️⃣ YouTube Trending API
        print("  [YouTube] Checking YouTube Trending...")
        trends = fetch_youtube_trending(region=region)
        if trends:
            vp_topics = trends_to_voidpulse_topics(trends, count=8)
            fresh = [t for t in vp_topics if t not in used]
            if fresh:
                topic = fresh[0]
                print(f"  [YouTube] Selected: {topic}")
                return topic
            print("  All trending topics already used — falling back to evergreen")

    # 3️⃣ Evergreen fallback
    available = [t for t in EVERGREEN_TOPICS if t not in used]
    if not available:
        available = EVERGREEN_TOPICS
    topic = random.choice(available)
    print(f"  [Evergreen] Topic selected: {topic}")
    return topic


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse Trending Topics")
    parser.add_argument("--pick",      action="store_true",
                        help="Pick best topic for today and print it")
    parser.add_argument("--region",    default="US",
                        help="Region code (default: US)")
    parser.add_argument("--no-trends", action="store_true",
                        help="Skip all trending sources, use evergreen pool only")
    parser.add_argument("--gemini",    action="store_true",
                        help="Show raw Gemini topic suggestions")
    args = parser.parse_args()

    if args.gemini:
        print("\n[Gemini] Fetching fresh topics from Google Search grounding...")
        topics = fetch_topics_with_gemini(count=10)
        if topics:
            print(f"\n{len(topics)} topics found:\n")
            for t in topics:
                print(f"  >> {t}")
        else:
            print("  No topics returned — check GEMINI_API_KEY")
        return

    if args.pick:
        topic = get_topic_for_today(
            region=args.region,
            use_trends=not args.no_trends,
        )
        print(f"\nSelected topic:\n  {topic}")
        return

    # Show all sources
    print(f"\n[Gemini] Fetching topics from Google Search grounding...")
    gemini_topics = fetch_topics_with_gemini(count=6)
    if gemini_topics:
        print(f"\nGemini topics ({len(gemini_topics)}):")
        for t in gemini_topics:
            print(f"  >> {t}")

    print(f"\n[RSS] Fetching Google Trends ({args.region})...")
    try:
        trends = fetch_trends_with_rss(args.region)
        vp_topics = trends_to_voidpulse_topics(trends, count=5)
        print(f"\nRSS topics ({len(vp_topics)}):")
        for t in vp_topics:
            print(f"  >> {t}")
    except Exception as e:
        print(f"  RSS failed: {e}")


if __name__ == "__main__":
    main()
