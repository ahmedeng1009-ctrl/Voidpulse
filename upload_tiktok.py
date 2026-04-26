"""
VoidPulse TikTok Uploader
Uses TikTok's official Content Posting API (v2).

SETUP (one-time):
  1. Go to https://developers.tiktok.com and create a Developer App
  2. Enable "Content Posting API" scope
  3. Complete App Review to get production access
  4. Add to .env:
       TIKTOK_CLIENT_KEY=your_client_key
       TIKTOK_CLIENT_SECRET=your_client_secret
       TIKTOK_ACCESS_TOKEN=your_access_token   # from OAuth flow

  Run OAuth flow:
       python upload_tiktok.py auth

Usage:
    python upload_tiktok.py --video video/exports/foo.mp4 --title "Dark Truth About..."
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

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"
TOKEN_FILE      = Path("metadata/tiktok_token.json")

# ── Token management ──────────────────────────────────────────────────────────

def load_token() -> dict | None:
    if TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def save_token(data: dict):
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_access_token() -> str:
    """Return a valid access token, refreshing if expired."""
    # 1. Check env var first (simple mode)
    env_token = os.getenv("TIKTOK_ACCESS_TOKEN")
    if env_token:
        return env_token

    # 2. Check saved token file
    token_data = load_token()
    if not token_data:
        raise EnvironmentError(
            "TikTok access token not found.\n"
            "Run: python upload_tiktok.py auth\n"
            "Or add TIKTOK_ACCESS_TOKEN to your .env file."
        )

    # Check expiry
    if token_data.get("expires_at", 0) > time.time() + 60:
        return token_data["access_token"]

    # Refresh
    return refresh_access_token(token_data)


def refresh_access_token(token_data: dict) -> str:
    client_key    = os.getenv("TIKTOK_CLIENT_KEY")
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
    refresh_token = token_data.get("refresh_token")

    if not all([client_key, client_secret, refresh_token]):
        raise EnvironmentError("Missing TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, or refresh_token.")

    payload = urllib.parse.urlencode({
        "client_key":    client_key,
        "client_secret": client_secret,
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
    }).encode()

    req = urllib.request.Request(
        "https://open.tiktokapis.com/v2/oauth/token/",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    new_token = {
        "access_token":  data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),
        "expires_at":    time.time() + data.get("expires_in", 86400),
        "open_id":       token_data.get("open_id"),
    }
    save_token(new_token)
    print("  TikTok token refreshed.")
    return new_token["access_token"]


# ── OAuth flow ────────────────────────────────────────────────────────────────

def run_oauth_flow():
    """Open browser for TikTok OAuth and save the token."""
    import webbrowser

    client_key    = os.getenv("TIKTOK_CLIENT_KEY")
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET")

    if not client_key or not client_secret:
        print("Error: Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env")
        sys.exit(1)

    redirect_uri = "http://localhost:8080/callback"
    scope        = "video.publish,video.upload"
    state        = "voidpulse"

    auth_url = (
        f"https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={client_key}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&state={state}"
    )

    print(f"\nOpening TikTok authorization in browser...")
    print(f"If it doesn't open automatically, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Simple local server to catch the redirect
    from http.server import BaseHTTPRequestHandler, HTTPServer

    auth_code = [None]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params:
                auth_code[0] = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>VoidPulse: Authorization complete! You can close this tab.</h2>")

        def log_message(self, *args):
            pass  # suppress access logs

    server = HTTPServer(("localhost", 8080), Handler)
    print("Waiting for TikTok to redirect back... (authorize in your browser)")
    server.handle_request()

    if not auth_code[0]:
        print("Error: Did not receive authorization code.")
        sys.exit(1)

    # Exchange code for token
    payload = urllib.parse.urlencode({
        "client_key":    client_key,
        "client_secret": client_secret,
        "code":          auth_code[0],
        "grant_type":    "authorization_code",
        "redirect_uri":  redirect_uri,
    }).encode()

    req = urllib.request.Request(
        "https://open.tiktokapis.com/v2/oauth/token/",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    token_data = {
        "access_token":  data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_at":    time.time() + data.get("expires_in", 86400),
        "open_id":       data.get("open_id", ""),
    }
    save_token(token_data)
    print(f"\n  ✓ TikTok token saved to {TOKEN_FILE}")
    print(f"  open_id: {token_data['open_id']}")


# ── Upload ────────────────────────────────────────────────────────────────────

def api_post(endpoint: str, payload: dict, token: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        f"{TIKTOK_API_BASE}{endpoint}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json; charset=utf-8",
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def upload_video(video_path: Path, title: str,
                 privacy: str = "PUBLIC_TO_EVERYONE") -> str | None:
    """
    Upload a video to TikTok using the File Upload method.
    Returns the publish_id on success, or None on failure.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    token     = get_access_token()
    file_size = video_path.stat().st_size
    chunk_size = 10 * 1024 * 1024   # 10 MB chunks

    print(f"  Uploading to TikTok: {video_path.name}")
    print(f"  Title  : {title[:100]}")
    print(f"  Size   : {file_size / 1024 / 1024:.1f} MB")

    # Step 1: Initialize upload
    init_body = {
        "post_info": {
            "title":            title[:150],
            "privacy_level":    privacy,
            "disable_duet":     False,
            "disable_comment":  False,
            "disable_stitch":   False,
        },
        "source_info": {
            "source":       "FILE_UPLOAD",
            "video_size":   file_size,
            "chunk_size":   min(chunk_size, file_size),
            "total_chunk_count": (file_size + chunk_size - 1) // chunk_size,
        },
    }

    resp = api_post("/post/video/init/", init_body, token)
    if resp.get("error", {}).get("code") != "ok":
        print(f"  ✗ TikTok init error: {resp}")
        return None

    upload_url = resp["data"]["upload_url"]
    publish_id = resp["data"]["publish_id"]

    # Step 2: Upload chunks
    chunks_count = (file_size + chunk_size - 1) // chunk_size
    with open(video_path, "rb") as f:
        for chunk_idx in range(chunks_count):
            chunk_data  = f.read(chunk_size)
            offset_start = chunk_idx * chunk_size
            offset_end   = offset_start + len(chunk_data) - 1

            chunk_req = urllib.request.Request(
                upload_url,
                data=chunk_data,
                headers={
                    "Content-Type":  "video/mp4",
                    "Content-Range": f"bytes {offset_start}-{offset_end}/{file_size}",
                    "Content-Length": str(len(chunk_data)),
                },
                method="PUT"
            )
            with urllib.request.urlopen(chunk_req, timeout=120):
                pass

            pct = int((chunk_idx + 1) / chunks_count * 100)
            print(f"\r  Uploading chunk {chunk_idx+1}/{chunks_count} ({pct}%)", end="", flush=True)

    print(f"\n  ✓ TikTok upload complete! publish_id: {publish_id}")
    return publish_id


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VoidPulse TikTok Uploader")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("auth", help="Run OAuth flow to authorize TikTok access")

    p_up = sub.add_parser("upload", help="Upload a video")
    p_up.add_argument("--video",   required=True,            help="Path to MP4 file")
    p_up.add_argument("--title",   required=True,            help="Video caption/title")
    p_up.add_argument("--privacy", default="PUBLIC_TO_EVERYONE",
                      choices=["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS",
                               "FOLLOWER_OF_CREATOR", "SELF_ONLY"],
                      help="Privacy setting")

    args = parser.parse_args()

    if args.command == "auth":
        run_oauth_flow()

    elif args.command == "upload":
        video_path = Path(args.video)
        try:
            publish_id = upload_video(video_path, args.title, args.privacy)
            if publish_id:
                print(f"\nCheck your TikTok profile — the video should appear shortly.")
        except EnvironmentError as e:
            print(f"\nSetup needed:\n{e}")
            sys.exit(1)

    else:
        parser.print_help()
        print("\nSetup steps:")
        print("  1. Add TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET to .env")
        print("  2. python upload_tiktok.py auth")
        print("  3. python upload_tiktok.py upload --video path.mp4 --title 'Your title'")


if __name__ == "__main__":
    main()
