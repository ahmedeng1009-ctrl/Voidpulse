"""
VoidPulse Smart Topics — Analytics-driven topic generation.

Pulls live YouTube stats for every uploaded video, merges with hook text and
upload age, ranks performers, then asks Claude to spot the patterns that
distinguish winners from losers — and generate fresh topics that match the
winning patterns.

Usage:
    python smart_topics.py                  # full analysis + 5 new topics
    python smart_topics.py --pick           # print one ready-to-use topic
    python smart_topics.py --count 10       # generate 10 topics
    python smart_topics.py --refresh        # ignore cache, recompute now
    python smart_topics.py --report         # only show the performance report

Output:
    metadata/smart_topics.json   ← cached topics + analysis (24h TTL)
    metadata/performance.json    ← raw per-video stats snapshot
"""

import argparse
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", encoding="utf-8", override=True)

# ── Constants ─────────────────────────────────────────────────────────────────

UPLOADED_LOG     = Path("metadata/uploaded_videos.json")
SCRIPTS_DIR      = Path("scripts/drafts")
USED_TOPICS_FILE = Path("metadata/used_topics.txt")
SMART_CACHE      = Path("metadata/smart_topics.json")
PERF_SNAPSHOT    = Path("metadata/performance.json")

CACHE_TTL_HOURS  = 24
MIN_VIDEOS       = 4  # below this, smart topics fall back to trending


# ── Data collection ──────────────────────────────────────────────────────────

def load_uploaded_log() -> list[dict]:
    if not UPLOADED_LOG.exists():
        return []
    try:
        return json.loads(UPLOADED_LOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def fetch_performance_data() -> list[dict]:
    """
    Merge uploaded log with live YouTube stats and hook text.
    Returns one record per video with: id, topic, hook, views, likes, comments,
    days_old, views_per_day, engagement_rate.
    """
    from analytics import fetch_video_stats
    from generate_thumbnail import extract_hook_text

    log = load_uploaded_log()
    if not log:
        return []

    video_ids = [e["id"] for e in log]
    print(f"  Fetching live stats for {len(video_ids)} video(s)...")
    stats = fetch_video_stats(video_ids)
    stats_map = {s["id"]: s for s in stats}

    log_map = {e["id"]: e for e in log}

    now = datetime.now()
    records = []
    for vid_id, entry in log_map.items():
        s = stats_map.get(vid_id)
        if not s:
            continue

        # Hook text from saved script
        topic       = entry.get("topic", s["title"])
        slug        = re.sub(r"[^\w\s-]", "", topic.lower()).strip()
        slug        = re.sub(r"[\s_-]+", "_", slug)[:60]
        script_path = SCRIPTS_DIR / f"{slug}.md"
        hook        = extract_hook_text(script_path) if script_path.exists() else ""

        # Age in days (min 1 to avoid div-by-zero)
        try:
            uploaded_dt = datetime.fromisoformat(entry["uploaded_at"])
            days_old    = max((now - uploaded_dt).total_seconds() / 86400, 1.0)
        except Exception:
            days_old = 1.0

        views = s["views"]
        likes = s["likes"]
        cmts  = s["comments"]

        records.append({
            "id":               vid_id,
            "topic":            topic,
            "hook":             hook,
            "views":            views,
            "likes":            likes,
            "comments":         cmts,
            "days_old":         round(days_old, 1),
            "views_per_day":    round(views / days_old, 1),
            "engagement_rate":  round((likes + cmts) / max(views, 1) * 100, 2),
            "url":              entry.get("url", f"https://youtu.be/{vid_id}"),
            "uploaded_at":      entry.get("uploaded_at", ""),
        })

    # Save raw snapshot for inspection
    PERF_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    PERF_SNAPSHOT.write_text(
        json.dumps({"fetched_at": now.isoformat(timespec="seconds"),
                    "videos": records}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return records


# ── Analysis ──────────────────────────────────────────────────────────────────

def split_winners_losers(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Split videos into top performers and bottom performers by views_per_day.
    Returns (winners, losers) — each is a sorted list (best/worst first).
    """
    if not records:
        return [], []

    sorted_recs = sorted(records, key=lambda r: r["views_per_day"], reverse=True)
    n           = len(sorted_recs)
    cut         = max(n // 3, 1)  # top third / bottom third
    winners     = sorted_recs[:cut]
    losers      = sorted_recs[-cut:][::-1]
    return winners, losers


def print_performance_report(records: list[dict]):
    if not records:
        print("\n  No performance data yet.")
        return

    sorted_recs = sorted(records, key=lambda r: r["views_per_day"], reverse=True)

    sep = "─" * 78
    print(f"\n{'═'*78}")
    print(f"  VoidPulse Performance Report — {datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'═'*78}")
    print(f"  Videos analyzed : {len(records)}")
    print(f"  Total views     : {sum(r['views'] for r in records):,}")
    print(f"  Avg views/day   : {sum(r['views_per_day'] for r in records)/len(records):.1f}")
    print(f"{'═'*78}\n")

    print(f"  {'#':<3} {'V/day':>7} {'Views':>7} {'Eng%':>5} {'Age':>5}  Topic")
    print(f"  {sep}")
    for i, r in enumerate(sorted_recs, 1):
        marker = "🏆" if i == 1 else "  "
        print(
            f"  {i:<3} {r['views_per_day']:>7.0f} {r['views']:>7,} "
            f"{r['engagement_rate']:>4.1f}% {r['days_old']:>4.1f}d  "
            f"{marker} {r['topic'][:48]}"
        )
    print()


# ── Claude: pattern analysis + topic generation ──────────────────────────────

SMART_SYSTEM_PROMPT = """You are a viral YouTube Shorts strategist for VoidPulse — a dark, fact-based channel that exposes uncomfortable truths. The tone is dramatic, conspiracy-core, never humorous. Target audience: global English-speaking viewers (US, UK, India, Europe).

Your job: study the channel's actual past performance, identify what makes the WINNERS win and the LOSERS lose, then generate fresh topic ideas that match the winning patterns.

═══════════════════════════════════════════════════
TOPIC SELECTION RULES — READ CAREFULLY:
═══════════════════════════════════════════════════
✅ PRIORITIZE topics where the threat is PERSONAL and INVISIBLE:
   - Something happening to the viewer's body RIGHT NOW (chemicals, toxins, radiation)
   - Something they do every day that is secretly harming them (eating, sleeping, scrolling)
   - Something inside their home/food/phone/skin that is already there
   Frame: "How YOUR [daily object] is [secretly doing X] to YOU right now"

❌ AVOID systemic/political/financial topics:
   - Central banks, billionaires, the Fed, IPOs, corporate wages
   - These feel distant — the viewer is not personally threatened
   - Low swipe-stop rate = algorithm buries the video

═══════════════════════════════════════════════════
WINNING TOPIC FORMULA:
  "How your [everyday object] is [present-tense damage verb] your [body part] right now"
  Examples that WORK:
  - "How your deodorant is loading your lymph nodes with aluminum right now"
  - "How your plastic cutting board is releasing microplastics into every meal"
  - "How your shower filter is not removing the chlorine destroying your gut"
═══════════════════════════════════════════════════

For each new topic you generate, it must:
- Be ONE sentence (10–18 words), present tense, second-person
- Target personal body/health/daily-behavior threat — NOT systemic/political
- Promise a shocking revelation backed by a real statistic
- Not repeat any topic the channel has already covered
- Match the structural pattern of past winners

Return ONLY valid JSON, no markdown:
{
  "patterns_winning": ["short bullet on what winners share", ...],
  "patterns_losing":  ["short bullet on what losers share", ...],
  "topics": ["topic 1", "topic 2", ...]
}"""


def generate_smart_topics(records: list[dict], count: int = 5,
                          used_topics: set[str] | None = None) -> dict:
    """
    Send performance data to Claude, get back patterns + new topics.
    """
    import anthropic

    used_topics = used_topics or set()
    winners, losers = split_winners_losers(records)

    def fmt(recs: list[dict]) -> str:
        lines = []
        for r in recs:
            lines.append(
                f'- "{r["topic"]}" — {r["views_per_day"]:.0f} views/day, '
                f'{r["engagement_rate"]:.1f}% engagement\n'
                f'    HOOK: "{r["hook"][:120]}"'
            )
        return "\n".join(lines)

    used_block = ""
    if used_topics:
        sample = list(used_topics)[:30]
        used_block = "\nALREADY-COVERED TOPICS (do NOT repeat):\n" + \
                     "\n".join(f"- {t}" for t in sample)

    user_msg = f"""Here is the channel's actual performance data.

🏆 TOP PERFORMERS ({len(winners)} videos):
{fmt(winners) or "  (no data yet)"}

📉 BOTTOM PERFORMERS ({len(losers)} videos):
{fmt(losers) or "  (no data yet)"}
{used_block}

TASK:
1. Identify patterns that distinguish winners from losers — look at topic framing, hook structure, subject matter.
2. Generate {count} brand-new VoidPulse topics that follow the winning patterns and break from the losing patterns.

Return the JSON described in your system prompt."""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=[{"type": "text", "text": SMART_SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  Warning: Claude returned invalid JSON — using empty result")
        return {"patterns_winning": [], "patterns_losing": [], "topics": []}

    # Filter out anything already covered (case-insensitive substring check)
    used_lower = {t.lower() for t in used_topics}
    fresh = []
    for t in data.get("topics", []):
        t_clean = t.strip().strip('"\'')
        if not t_clean or len(t_clean) < 15:
            continue
        if any(u in t_clean.lower() or t_clean.lower() in u for u in used_lower):
            continue
        fresh.append(t_clean)

    data["topics"] = fresh[:count]
    return data


# ── Cache ─────────────────────────────────────────────────────────────────────

def load_cache() -> dict | None:
    if not SMART_CACHE.exists():
        return None
    try:
        cache = json.loads(SMART_CACHE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    cached_at = cache.get("cached_at", "")
    try:
        dt = datetime.fromisoformat(cached_at)
        if datetime.now() - dt > timedelta(hours=CACHE_TTL_HOURS):
            return None
    except Exception:
        return None

    if not cache.get("topics"):
        return None
    return cache


def save_cache(analysis: dict):
    SMART_CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cached_at":        datetime.now().isoformat(timespec="seconds"),
        "patterns_winning": analysis.get("patterns_winning", []),
        "patterns_losing":  analysis.get("patterns_losing",  []),
        "topics":           analysis.get("topics", []),
        "consumed":         [],
    }
    SMART_CACHE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def mark_topic_consumed(topic: str):
    """Mark a smart topic as used so it isn't suggested again."""
    if not SMART_CACHE.exists():
        return
    try:
        cache = json.loads(SMART_CACHE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    consumed = set(cache.get("consumed", []))
    consumed.add(topic)
    cache["consumed"] = list(consumed)
    SMART_CACHE.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Main entry points ────────────────────────────────────────────────────────

def get_smart_topic(refresh: bool = False) -> str | None:
    """
    Returns one ready-to-use topic, or None if not enough data.
    Used by run_pipeline.py — falls back to trending if None returned.
    """
    used_topics: set[str] = set()
    if USED_TOPICS_FILE.exists():
        used_topics = set(USED_TOPICS_FILE.read_text(encoding="utf-8").splitlines())

    # Try cache first
    if not refresh:
        cache = load_cache()
        if cache:
            consumed = set(cache.get("consumed", []))
            for t in cache.get("topics", []):
                if t not in consumed and t not in used_topics:
                    print(f"  [Smart] Using cached topic: {t}")
                    mark_topic_consumed(t)
                    return t
            print("  [Smart] Cache exhausted — regenerating")

    # Fresh generation
    records = fetch_performance_data()
    if len(records) < MIN_VIDEOS:
        print(f"  [Smart] Only {len(records)} video(s) with data — need {MIN_VIDEOS}+; falling back")
        return None

    print(f"  [Smart] Analyzing {len(records)} videos with Claude...")
    analysis = generate_smart_topics(records, count=8, used_topics=used_topics)

    if not analysis.get("topics"):
        print("  [Smart] No topics returned — falling back")
        return None

    save_cache(analysis)
    topic = analysis["topics"][0]
    mark_topic_consumed(topic)
    print(f"  [Smart] New topic: {topic}")
    return topic


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse Smart Topics")
    parser.add_argument("--pick",    action="store_true",
                        help="Print one ready-to-use topic and exit")
    parser.add_argument("--count",   type=int, default=5,
                        help="How many topics to generate (default: 5)")
    parser.add_argument("--refresh", action="store_true",
                        help="Ignore cache, recompute now")
    parser.add_argument("--report",  action="store_true",
                        help="Show performance report only — skip topic generation")
    args = parser.parse_args()

    if args.pick:
        topic = get_smart_topic(refresh=args.refresh)
        if topic:
            print(f"\n{topic}")
        else:
            print("\n(no smart topic available — use trending_topics.py instead)")
        return

    records = fetch_performance_data()
    print_performance_report(records)

    if args.report:
        return

    if len(records) < MIN_VIDEOS:
        print(f"  Need at least {MIN_VIDEOS} videos with stats to detect patterns.")
        print(f"  You have {len(records)}. Keep uploading; come back later.")
        return

    used = set()
    if USED_TOPICS_FILE.exists():
        used = set(USED_TOPICS_FILE.read_text(encoding="utf-8").splitlines())

    print(f"  Asking Claude to find patterns and generate {args.count} new topics...")
    analysis = generate_smart_topics(records, count=args.count, used_topics=used)
    save_cache(analysis)

    print(f"\n{'─'*78}")
    print("  🏆 WINNING PATTERNS:")
    for p in analysis.get("patterns_winning", []):
        print(f"    + {p}")
    print("\n  📉 LOSING PATTERNS:")
    for p in analysis.get("patterns_losing", []):
        print(f"    - {p}")
    print(f"\n  💡 NEW TOPIC IDEAS ({len(analysis.get('topics', []))}):")
    for i, t in enumerate(analysis.get("topics", []), 1):
        print(f"    {i}. {t}")
    print(f"{'─'*78}")
    print(f"\n  Cached to: {SMART_CACHE}")
    print(f"  Use the next topic with: python run_pipeline.py --smart")


if __name__ == "__main__":
    main()
