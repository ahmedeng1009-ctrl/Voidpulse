"""
One-time script: scan all previously downloaded background clips in
video/backgrounds/ and register them in metadata/used_clips.json so the
new anti-duplicate system never re-downloads them in future videos.

We don't know the original Pexels video IDs for older downloads, so we
fingerprint by filename hash + filesize and seed the registry with those
synthetic IDs. This blocks the exact same files from being treated as
"new," but allows fresh Pexels searches to still return new clips
(because real Pexels IDs won't collide with our synthetic ones).

Usage:
    python seed_used_clips.py
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

BACKGROUNDS_DIR = Path("video/backgrounds")
USED_CLIPS_FILE = Path("metadata/used_clips.json")


def stable_synthetic_id(file_path: Path) -> int:
    """Hash filename+size into a stable synthetic ID that won't collide with real Pexels IDs (which are typically < 30M)."""
    size = file_path.stat().st_size
    digest = hashlib.sha1(f"{file_path.name}:{size}".encode("utf-8")).hexdigest()
    # Use a very large offset so we can't collide with real Pexels video IDs
    return 10_000_000_000 + int(digest[:10], 16)


def main():
    if not BACKGROUNDS_DIR.exists():
        print(f"No backgrounds folder yet at {BACKGROUNDS_DIR}")
        return

    USED_CLIPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if USED_CLIPS_FILE.exists():
        try:
            registry = json.loads(USED_CLIPS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            registry = {}
    else:
        registry = {}

    before = len(registry)
    added  = 0

    for topic_dir in BACKGROUNDS_DIR.iterdir():
        if not topic_dir.is_dir():
            continue
        topic_label = topic_dir.name.replace("_", " ")

        for mp4 in topic_dir.glob("*.mp4"):
            synth_id = stable_synthetic_id(mp4)
            key = str(synth_id)
            if key in registry:
                continue
            registry[key] = {
                "query":      mp4.stem.replace("_", " "),
                "filename":   mp4.name,
                "topic":      topic_label,
                "downloaded": datetime.fromtimestamp(mp4.stat().st_mtime).isoformat(timespec="seconds"),
                "synthetic":  True,  # didn't come from Pexels API directly
            }
            added += 1

    USED_CLIPS_FILE.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Registry seeded.")
    print(f"  Before : {before} entries")
    print(f"  Added  : {added} synthetic entries")
    print(f"  Total  : {len(registry)} entries")
    print(f"  Saved  : {USED_CLIPS_FILE}")
    print()
    print("Note: synthetic entries fingerprint your old files but don't block real")
    print("Pexels IDs. Future videos will get genuinely fresh clips from Pexels.")


if __name__ == "__main__":
    main()
