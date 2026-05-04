"""
VoidPulse YouTube Analytics Dashboard
Fetches views, likes, comments for all uploaded videos and prints a summary.
Video IDs are tracked automatically in metadata/uploaded_videos.json.

Usage:
    python analytics.py              # show all tracked videos
    python analytics.py --top 5      # show top 5 by views
    python analytics.py --add <id>   # manually add a video ID
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

LOG_FILE = Path("metadata/uploaded_videos.json")

# ── Video log helpers ─────────────────────────────────────────────────────────

def load_video_log() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    try:
        return json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_video_log(entries: list[dict]):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def log_upload(video_id: str, topic: str, uploaded_at: str | None = None):
    """Called by run_pipeline.py after each successful upload."""
    entries = load_video_log()

    # Avoid duplicates
    if any(e["id"] == video_id for e in entries):
        return

    entries.append({
        "id": video_id,
        "topic": topic,
        "uploaded_at": uploaded_at or datetime.now().isoformat(timespec="seconds"),
        "url": f"https://youtu.be/{video_id}",
    })
    save_video_log(entries)
    print(f"  Logged video: {video_id}")


# ── YouTube API ───────────────────────────────────────────────────────────────

def get_youtube_client():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    # youtube.upload is sufficient — videos().list() works with any valid OAuth token
    SCOPES     = ["https://www.googleapis.com/auth/youtube.upload"]
    TOKEN_FILE = "token.json"

    creds = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        else:
            raise RuntimeError(
                "token.json is missing or invalid — run the pipeline locally once to re-authorize."
            )

    return build("youtube", "v3", credentials=creds)


def fetch_video_stats(video_ids: list[str]) -> list[dict]:
    """Fetch statistics for a list of YouTube video IDs (max 50 per call)."""
    if not video_ids:
        return []

    youtube = get_youtube_client()
    results = []

    # YouTube API allows max 50 IDs per request
    for chunk_start in range(0, len(video_ids), 50):
        chunk = video_ids[chunk_start:chunk_start + 50]
        response = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(chunk),
        ).execute()

        for item in response.get("items", []):
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            results.append({
                "id":        item["id"],
                "title":     snippet.get("title", "Unknown"),
                "published": snippet.get("publishedAt", "")[:10],
                "views":     int(stats.get("viewCount",    0)),
                "likes":     int(stats.get("likeCount",    0)),
                "comments":  int(stats.get("commentCount", 0)),
                "url":       f"https://youtu.be/{item['id']}",
            })

    return results


# ── Report renderer ───────────────────────────────────────────────────────────

def print_report(stats: list[dict], log: list[dict]):
    if not stats:
        print("  No data returned from YouTube API.")
        return

    # Merge log data (topic) into stats
    log_map = {e["id"]: e for e in log}
    for s in stats:
        s["topic"]       = log_map.get(s["id"], {}).get("topic", "—")
        s["uploaded_at"] = log_map.get(s["id"], {}).get("uploaded_at", "—")[:10]

    stats.sort(key=lambda x: x["views"], reverse=True)

    total_views    = sum(s["views"]    for s in stats)
    total_likes    = sum(s["likes"]    for s in stats)
    total_comments = sum(s["comments"] for s in stats)

    sep = "─" * 72

    print(f"\n{'═'*72}")
    print(f"  VoidPulse Analytics Dashboard  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═'*72}")
    print(f"  Total videos  : {len(stats)}")
    print(f"  Total views   : {total_views:,}")
    print(f"  Total likes   : {total_likes:,}")
    print(f"  Total comments: {total_comments:,}")
    print(f"  Avg views/vid : {total_views // max(len(stats),1):,}")
    print(f"{'═'*72}\n")

    print(f"  {'#':<3} {'Views':>8} {'Likes':>6} {'Cmts':>6}  {'Date':<11}  Topic")
    print(f"  {sep}")

    for i, s in enumerate(stats, 1):
        topic_short = s["topic"][:38]
        print(
            f"  {i:<3} {s['views']:>8,} {s['likes']:>6,} {s['comments']:>6,}"
            f"  {s['uploaded_at']:<11}  {topic_short}"
        )
        print(f"       └─ {s['url']}")

    if stats:
        best = stats[0]
        print(f"\n  🏆 Best performer: \"{best['topic'][:50]}\"")
        print(f"     {best['views']:,} views — {best['url']}")

    print(f"\n{'═'*72}\n")


# ── Daily refresh — used by GitHub Actions analytics workflow ─────────────────

def refresh_performance() -> dict:
    """
    Fetch live YouTube stats for all uploaded videos, save to performance.json,
    and invalidate the smart_topics cache so the next pipeline run re-analyses
    with fresh data.
    Returns a summary dict.
    """
    log = load_video_log()
    if not log:
        print("  No uploaded videos to refresh.")
        return {}

    video_ids = [e["id"] for e in log]
    print(f"  Fetching live stats for {len(video_ids)} video(s)...")

    try:
        stats = fetch_video_stats(video_ids)
    except Exception as e:
        print(f"  ERROR fetching stats: {e}")
        return {}

    log_map = {e["id"]: e for e in log}
    now     = datetime.now()
    records = []

    for s in stats:
        entry    = log_map.get(s["id"], {})
        topic    = entry.get("topic", s["title"])
        days_old = 1.0
        try:
            uploaded_dt = datetime.fromisoformat(entry["uploaded_at"])
            days_old    = max((now - uploaded_dt).total_seconds() / 86400, 1.0)
        except Exception:
            pass

        views = s["views"]
        likes = s["likes"]
        cmts  = s["comments"]

        records.append({
            "id":             s["id"],
            "topic":          topic,
            "views":          views,
            "likes":          likes,
            "comments":       cmts,
            "days_old":       round(days_old, 1),
            "views_per_day":  round(views / days_old, 1),
            "engagement_rate": round((likes + cmts) / max(views, 1) * 100, 2),
            "url":            s["url"],
            "uploaded_at":    entry.get("uploaded_at", ""),
        })

    # Save fresh performance snapshot
    perf_path = Path("metadata/performance.json")
    perf_path.parent.mkdir(parents=True, exist_ok=True)
    perf_path.write_text(
        json.dumps({
            "fetched_at": now.isoformat(timespec="seconds"),
            "videos":     records,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  performance.json updated — {len(records)} videos")

    # Invalidate smart_topics cache so next pipeline run re-analyses with fresh data
    smart_cache = Path("metadata/smart_topics.json")
    if smart_cache.exists():
        try:
            cache = json.loads(smart_cache.read_text(encoding="utf-8"))
            cache["cached_at"] = "2000-01-01T00:00:00"  # force expiry
            smart_cache.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
            print("  smart_topics cache invalidated — will regenerate on next pipeline run")
        except Exception:
            pass

    total_views = sum(r["views"] for r in records)
    best = max(records, key=lambda r: r["views_per_day"]) if records else {}
    summary = {
        "videos":      len(records),
        "total_views": total_views,
        "best_topic":  best.get("topic", ""),
        "best_vpd":    best.get("views_per_day", 0),
    }

    print(f"  Total views: {total_views:,}  |  Best: {best.get('topic','')[:40]} ({best.get('views_per_day',0):.1f} v/day)")
    return summary


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse Analytics Dashboard")
    parser.add_argument("--top",     type=int, default=None, help="Show only top N videos")
    parser.add_argument("--add",     default=None,           help="Add video ID manually to log")
    parser.add_argument("--topic",   default="Manual add",   help="Topic for --add")
    parser.add_argument("--refresh", action="store_true",    help="Refresh performance.json from YouTube API")
    args = parser.parse_args()

    if args.add:
        log_upload(args.add, args.topic)
        print(f"Added video {args.add} to log.")
        return

    if args.refresh:
        refresh_performance()
        return

    log = load_video_log()
    if not log:
        print("\nNo uploaded videos tracked yet.")
        print("Videos are logged automatically when you run run_pipeline.py.")
        print("Or add one manually:  python analytics.py --add <video_id> --topic \"My Topic\"")
        return

    video_ids = [e["id"] for e in log]
    if args.top:
        video_ids = video_ids[-args.top:]

    print(f"\nFetching stats for {len(video_ids)} video(s)...")
    try:
        stats = fetch_video_stats(video_ids)
        print_report(stats, log)
    except Exception as e:
        print(f"\nError fetching YouTube stats: {e}")
        print("\nStored log (no live stats):")
        for e in log:
            print(f"  {e['uploaded_at'][:10]}  {e['topic'][:50]}  {e['url']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
