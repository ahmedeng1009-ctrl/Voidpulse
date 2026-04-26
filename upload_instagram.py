"""
VoidPulse Instagram Reels Uploader
Uses Meta's Content Publishing API (Graph API v19+) to post Reels.

SETUP (one-time):
  1. Create a Facebook App at https://developers.facebook.com
  2. Add "Instagram Graph API" product
  3. Connect a Professional (Business/Creator) Instagram account
  4. Generate a Page Access Token with permissions:
       instagram_basic, instagram_content_publish, pages_read_engagement
  5. Add to .env:
       INSTAGRAM_USER_ID=your_instagram_user_id
       INSTAGRAM_ACCESS_TOKEN=your_long_lived_access_token

  Get your User ID:
       python upload_instagram.py whoami

Usage:
    python upload_instagram.py --video video/exports/foo.mp4 --caption "Dark truth..."
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

GRAPH_API = "https://graph.facebook.com/v19.0"

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_credentials() -> tuple[str, str]:
    user_id = os.getenv("INSTAGRAM_USER_ID")
    token   = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    if not user_id or not token:
        raise EnvironmentError(
            "Missing Instagram credentials in .env:\n"
            "  INSTAGRAM_USER_ID=your_id\n"
            "  INSTAGRAM_ACCESS_TOKEN=your_token\n\n"
            "Setup guide:\n"
            "  1. Create Facebook App at developers.facebook.com\n"
            "  2. Add Instagram Graph API product\n"
            "  3. Connect a Professional Instagram account\n"
            "  4. Generate a long-lived token with instagram_content_publish scope"
        )
    return user_id, token


def graph_request(path: str, params: dict, method: str = "GET") -> dict:
    url   = f"{GRAPH_API}/{path}"
    query = urllib.parse.urlencode(params)

    if method == "GET":
        req = urllib.request.Request(f"{url}?{query}")
    else:
        req = urllib.request.Request(
            url,
            data=query.encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method=method
        )

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    if "error" in data:
        raise RuntimeError(f"Graph API error: {data['error']['message']}")
    return data


# ── Who am I ─────────────────────────────────────────────────────────────────

def whoami():
    user_id, token = get_credentials()
    data = graph_request(user_id, {"fields": "id,username,name", "access_token": token})
    print(f"\nInstagram Account:")
    print(f"  ID      : {data.get('id')}")
    print(f"  Username: @{data.get('username')}")
    print(f"  Name    : {data.get('name')}")


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_reel(video_path: Path, caption: str,
                video_url: str | None = None) -> str | None:
    """
    Upload a Reel using Meta's two-step process:
      1. Create a media container (with video URL — must be publicly accessible)
      2. Publish the container

    IMPORTANT: Instagram requires the video to be hosted at a public HTTPS URL.
    Options:
      a) Upload to a cloud host first (S3, Cloudinary, etc.) and pass --url
      b) Use a temporary hosting service

    Args:
        video_path: local video file (used for size info / validation)
        caption:    post caption including hashtags
        video_url:  publicly accessible HTTPS URL to the video file

    Returns:
        Instagram media ID on success, None on failure.
    """
    user_id, token = get_credentials()

    if not video_url:
        print(
            "\n  ⚠️  Instagram requires a public HTTPS URL for the video.\n"
            "  Upload your video to a cloud host and pass --url <public_url>\n\n"
            "  Quick options:\n"
            "    • Cloudinary (free tier): https://cloudinary.com\n"
            "    • AWS S3 public bucket\n"
            "    • Any public HTTPS file host\n\n"
            "  Example:\n"
            "    python upload_instagram.py --video foo.mp4 --caption '...' \\\n"
            "      --url https://your-bucket.s3.amazonaws.com/foo.mp4"
        )
        return None

    print(f"  Uploading Reel to Instagram...")
    print(f"  Caption : {caption[:60]}...")
    print(f"  Video   : {video_url[:60]}...")

    # Step 1: Create media container
    print("  Step 1/2: Creating media container...")
    container = graph_request(
        f"{user_id}/media",
        {
            "media_type":   "REELS",
            "video_url":    video_url,
            "caption":      caption,
            "share_to_feed": "true",
            "access_token": token,
        },
        method="POST"
    )
    container_id = container["id"]
    print(f"    Container ID: {container_id}")

    # Step 2: Poll until ready (video processing takes time)
    print("  Waiting for video processing...")
    for attempt in range(30):
        time.sleep(10)
        status = graph_request(
            container_id,
            {"fields": "status_code", "access_token": token}
        )
        code = status.get("status_code", "")
        print(f"\r    Status: {code} (attempt {attempt+1}/30)", end="", flush=True)
        if code == "FINISHED":
            break
        if code == "ERROR":
            print(f"\n  ✗ Processing failed: {status}")
            return None
    else:
        print("\n  ✗ Timed out waiting for video to process.")
        return None

    # Step 3: Publish
    print("\n  Step 2/2: Publishing...")
    result = graph_request(
        f"{user_id}/media_publish",
        {"creation_id": container_id, "access_token": token},
        method="POST"
    )
    media_id = result["id"]
    print(f"  ✓ Reel published! Media ID: {media_id}")
    print(f"  Check your Instagram profile for the new Reel.")
    return media_id


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse Instagram Reels Uploader")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("whoami", help="Show connected Instagram account info")

    p_up = sub.add_parser("upload", help="Upload a Reel")
    p_up.add_argument("--video",   required=True, help="Path to local MP4 file")
    p_up.add_argument("--caption", required=True, help="Post caption (include hashtags)")
    p_up.add_argument("--url",     default=None,  help="Public HTTPS URL of the video (required)")

    args = parser.parse_args()

    if args.command == "whoami":
        try:
            whoami()
        except EnvironmentError as e:
            print(f"\n{e}")
            sys.exit(1)

    elif args.command == "upload":
        video_path = Path(args.video)
        if not video_path.exists():
            print(f"Error: video not found: {video_path}")
            sys.exit(1)
        try:
            result = upload_reel(video_path, args.caption, args.url)
            if not result:
                sys.exit(1)
        except EnvironmentError as e:
            print(f"\nSetup needed:\n{e}")
            sys.exit(1)
        except RuntimeError as e:
            print(f"\nAPI Error: {e}")
            sys.exit(1)

    else:
        parser.print_help()
        print("\nSetup steps:")
        print("  1. Add INSTAGRAM_USER_ID and INSTAGRAM_ACCESS_TOKEN to .env")
        print("  2. python upload_instagram.py whoami")
        print("  3. Upload video to a public URL (Cloudinary, S3, etc.)")
        print("  4. python upload_instagram.py upload --video path.mp4 \\")
        print("       --caption '#VoidPulse #Shorts' --url https://...")


if __name__ == "__main__":
    main()
