"""
VoidPulse — Retrofix Thumbnails
Generates missing thumbnails for all uploaded videos and applies them via YouTube API.

Requirements:
  - YouTube channel must be phone-verified (youtube.com/verify)
  - Run AFTER verification is complete

Usage:
    python retrofix_thumbnails.py            # generate + upload all missing
    python retrofix_thumbnails.py --dry-run  # show what would happen, no changes
    python retrofix_thumbnails.py --no-ai    # use generated backgrounds (faster, no Pollinations)
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
os_chdir = Path(__file__).parent
import os
os.chdir(os_chdir)

UPLOADED_JSON   = Path("metadata/uploaded_videos.json")
THUMBS_DIR      = Path("thumbnails/exported")
SCRIPTS_DIR     = Path("scripts/drafts")
SCRIPTS_FINAL   = Path("scripts/final")
TOKEN_FILE      = "token.json"
SECRET_FILE     = "client_secret.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "_", s)
    return s[:60]


def find_script(topic: str) -> Path | None:
    """Look for an existing script markdown file matching this topic."""
    slug = slugify(topic)
    for d in [SCRIPTS_FINAL, SCRIPTS_DIR]:
        p = d / (slug + ".md")
        if p.exists():
            return p
    # Fuzzy: find best prefix match
    for d in [SCRIPTS_FINAL, SCRIPTS_DIR]:
        if d.exists():
            for f in d.glob("*.md"):
                if f.stem[:40] == slug[:40]:
                    return f
    return None


def find_thumbnail(topic: str) -> Path | None:
    """Find an already-generated thumbnail for this topic."""
    slug = slugify(topic)
    # Exact match
    p = THUMBS_DIR / (slug + ".jpg")
    if p.exists():
        return p
    # Truncated match (slugify caps at 60, but file may be shorter)
    for f in THUMBS_DIR.glob("*.jpg"):
        if slug.startswith(f.stem) or f.stem.startswith(slug[:40]):
            return f
    return None


def get_youtube_client():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("  Refreshing OAuth token...")
            creds.refresh(Request())
        else:
            print("  Opening browser for Google login...")
            flow = InstalledAppFlow.from_client_secrets_file(SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def set_thumbnail(youtube, video_id: str, thumb_path: Path) -> bool:
    from googleapiclient.http import MediaFileUpload
    try:
        media = MediaFileUpload(str(thumb_path), mimetype="image/jpeg")
        youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
        return True
    except Exception as e:
        print(f"    ✗ API error: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse Retrofix Thumbnails")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan without making changes")
    parser.add_argument("--no-ai",   action="store_true",
                        help="Skip Pollinations AI background (faster)")
    parser.add_argument("--video-id", default=None,
                        help="Fix a single video ID only")
    args = parser.parse_args()

    if not UPLOADED_JSON.exists():
        print("Error: metadata/uploaded_videos.json not found")
        sys.exit(1)

    videos = json.loads(UPLOADED_JSON.read_text(encoding="utf-8"))

    if args.video_id:
        videos = [v for v in videos if v["id"] == args.video_id]
        if not videos:
            print(f"Video ID {args.video_id} not found in uploaded_videos.json")
            sys.exit(1)

    print(f"\nVoidPulse Retrofix Thumbnails")
    print(f"{'─'*50}")
    print(f"  Videos to process : {len(videos)}")
    print(f"  Mode              : {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"  AI backgrounds    : {'no' if args.no_ai else 'yes (Pollinations.ai)'}")
    print(f"{'─'*50}\n")

    # Import thumbnail generator
    sys.path.insert(0, str(Path(__file__).parent))
    import importlib
    gt = importlib.import_module("generate_thumbnail")

    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    if not args.dry_run:
        print("Connecting to YouTube API...")
        youtube = get_youtube_client()
        print("  Connected.\n")

    results = {"ok": 0, "generated": 0, "failed": 0, "skipped": 0}

    for i, video in enumerate(videos, 1):
        vid_id = video["id"]
        topic  = video["topic"]
        # Strip markdown bold if present (e.g. **Title**)
        topic  = re.sub(r"\*+", "", topic).strip().rstrip(".")

        print(f"[{i:02d}/{len(videos)}] {topic[:60]}")
        print(f"       https://youtu.be/{vid_id}")

        # 1. Find or generate thumbnail
        thumb = find_thumbnail(topic)

        if thumb:
            print(f"       Thumbnail : existing → {thumb.name}")
        else:
            print(f"       Thumbnail : MISSING — generating...")
            script_path = find_script(topic)
            if script_path:
                hook_text = gt.extract_hook_text(script_path)
                print(f"       Hook      : {hook_text[:55]}")
            else:
                # No script — generate hook with Claude
                hook_text = gt.generate_hook_with_claude(topic)
                print(f"       Hook      : (claude) {hook_text}")

            slug       = slugify(topic)
            thumb      = THUMBS_DIR / (slug + ".jpg")

            if not args.dry_run:
                try:
                    gt.generate_thumbnail(
                        topic=topic,
                        hook_text=hook_text,
                        output_path=thumb,
                        use_ai=not args.no_ai,
                    )
                    results["generated"] += 1
                    print(f"       Generated : {thumb.name}")
                except Exception as e:
                    print(f"       ✗ Generate failed: {e}")
                    results["failed"] += 1
                    print()
                    continue
            else:
                print(f"       [DRY RUN] Would generate: {thumb.name}")

        # 2. Upload thumbnail to YouTube
        if args.dry_run:
            print(f"       [DRY RUN] Would upload thumbnail to YouTube")
            results["ok"] += 1
        else:
            print(f"       Uploading to YouTube...", end=" ", flush=True)
            ok = set_thumbnail(youtube, vid_id, thumb)
            if ok:
                print("✓")
                results["ok"] += 1
            else:
                results["failed"] += 1
            # Rate limit: YouTube thumbnails API has per-minute quota
            time.sleep(2)

        print()

    print(f"{'─'*50}")
    print(f"Results:")
    print(f"  ✓ Applied successfully : {results['ok']}")
    print(f"  ✦ Thumbnails generated : {results['generated']}")
    print(f"  ✗ Failed               : {results['failed']}")
    print(f"{'─'*50}")

    if results["failed"] > 0 and not args.dry_run:
        print("\n⚠  Some thumbnails failed. Common reasons:")
        print("   • Channel not phone-verified → go to youtube.com/verify")
        print("   • YouTube quota exceeded → wait 24h and retry")
        print("   • Run with --video-id <id> to retry specific videos")


if __name__ == "__main__":
    main()
