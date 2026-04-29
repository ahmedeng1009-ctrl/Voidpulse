"""
VoidPulse YouTube Uploader
Uploads a video to YouTube using OAuth 2.0 authentication.

First run: opens browser for Google login (one time only).
After that: runs fully automatically using saved token.

Usage:
    python upload_youtube.py --video video/exports/my_video.mp4 \
                             --title "Your Video Title" \
                             --description "Your description"
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE         = "token.json"
SCOPES             = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# ── Auth ──────────────────────────────────────────────────────────────────────

def get_authenticated_service():
    """Authenticate and return YouTube API service."""
    creds = None

    # Load saved token if exists
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid token, login via browser (first time only)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing access token...")
            creds.refresh(Request())
        else:
            print("Opening browser for Google login (one time only)...")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future runs
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print("Token saved — future runs will be fully automatic.")

    return build("youtube", "v3", credentials=creds)

# ── Upload ────────────────────────────────────────────────────────────────────

def upload_video(youtube, video_path: Path, title: str, description: str, tags: list[str]):
    """Upload video to YouTube as unlisted (change to 'public' when ready)."""

    print(f"\nUploading: {video_path.name}")
    print(f"Title    : {title}")
    print(f"Status   : unlisted (change to public in YouTube Studio)")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",  # People & Blogs
        },
        "status": {
            "privacyStatus": "unlisted",   # Change to "public" when ready
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=5 * 1024 * 1024,  # 5MB chunks
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    print("\nUploading", end="", flush=True)
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"\r  Progress: {pct}%", end="", flush=True)

    print(f"\n\nDone! Video uploaded successfully.")
    print(f"Video ID : {response['id']}")
    print(f"Watch URL: https://youtu.be/{response['id']}")
    return response["id"]

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse YouTube Uploader")
    parser.add_argument("--video",       required=True,  help="Path to video MP4")
    parser.add_argument("--title",       required=True,  help="Video title")
    parser.add_argument("--description", default="",     help="Video description")
    parser.add_argument("--tags",        default="horror,scary,dark,facts,voidpulse",
                        help="Comma-separated tags")
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Error: Video not found: {video_path}")
        sys.exit(1)

    tags = [t.strip() for t in args.tags.split(",")]

    print("VoidPulse YouTube Uploader")
    print("-" * 40)

    youtube = get_authenticated_service()
    upload_video(youtube, video_path, args.title, args.description, tags)


if __name__ == "__main__":
    main()
