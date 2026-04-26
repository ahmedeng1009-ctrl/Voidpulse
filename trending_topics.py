"""
VoidPulse Trending Topics
Fetches today's trending searches from Google Trends and uses Claude
to convert them into VoidPulse-style dark/dramatic video topics.

Usage:
    python trending_topics.py              # show trending topics
    python trending_topics.py --pick       # pick best topic and print it
    python trending_topics.py --country us # specify country (default: us)

Requires: pip install pytrends
"""

import argparse
import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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

    client   = anthropic.Anthropic()
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
                        use_trends: bool = True) -> str:
    """
    Get the best topic for today's video.
    Tries YouTube Trending first, falls back to evergreen pool.
    """
    used_file = Path("metadata/used_topics.txt")
    used = set()
    if used_file.exists():
        used = set(used_file.read_text(encoding="utf-8").splitlines())

    if use_trends:
        print("  Checking YouTube Trending...")
        trends = fetch_youtube_trending(region=region)
        if trends:
            vp_topics = trends_to_voidpulse_topics(trends, count=8)
            fresh = [t for t in vp_topics if t not in used]
            if fresh:
                topic = fresh[0]
                print(f"  Trending topic selected: {topic}")
                return topic
            print("  All trending topics already used — falling back to evergreen")

    # Evergreen fallback
    available = [t for t in EVERGREEN_TOPICS if t not in used]
    if not available:
        available = EVERGREEN_TOPICS
    topic = random.choice(available)
    print(f"  Evergreen topic selected: {topic}")
    return topic


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse Trending Topics")
    parser.add_argument("--pick",    action="store_true",
                        help="Pick best topic for today and print it")
    parser.add_argument("--region",    default="US",
                        help="YouTube Trending region code (default: US)")
    parser.add_argument("--no-trends", action="store_true",
                        help="Skip YouTube Trending, use evergreen pool only")
    args = parser.parse_args()

    if args.pick:
        topic = get_topic_for_today(
            region=args.region,
            use_trends=not args.no_trends,
        )
        print(f"\nSelected topic:\n  {topic}")
        return

    # Show trending topics without picking
    print(f"\nFetching YouTube Trending ({args.region})...")
    trends = fetch_youtube_trending(args.region)

    if not trends:
        print("Could not fetch trends. Showing evergreen topics instead:")
        for t in EVERGREEN_TOPICS:
            print(f"  • {t}")
        return

    print(f"\nTop trends today:")
    for t in trends[:15]:
        print(f"  • {t}")

    print(f"\nConverting to VoidPulse topics with Claude...")
    vp_topics = trends_to_voidpulse_topics(trends, count=6)

    print(f"\nVoidPulse topics from today's trends:")
    for t in vp_topics:
        print(f"  ▶  {t}")


if __name__ == "__main__":
    main()
