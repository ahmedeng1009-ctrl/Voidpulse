"""
VoidPulse Voiceover Generator
Reads a script markdown file, extracts spoken lines, and generates
a professional AI voiceover using ElevenLabs API.

Setup:
    pip install elevenlabs python-dotenv
    Create a .env file with: ELEVENLABS_API_KEY=your_key_here
    Get a free API key at: https://elevenlabs.io
"""

import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

# Force UTF-8 output on Windows to handle special characters
sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

# ── Config --------------------------------------------------------------──────

SCRIPT_PATH   = Path("scripts/drafts/offshore_tax_havens.md")
OUTPUT_DIR    = Path("audio/voiceover")
OUTPUT_FILE   = OUTPUT_DIR / "offshore_tax_havens.mp3"

# ElevenLabs voice IDs — Adam is deep, dramatic, great for dark content
# Other options: Antoni=ErXwobaYiN019PkySvjV, Josh=TxGEqnHWrfWFTfGW9XjX
VOICE_ID      = "pNInz6obpgDQGcFmaJgB"   # Adam
VOICE_NAME    = "Adam"
MODEL_ID      = "eleven_turbo_v2_5"

# ── Text extraction ───────────────────────────────────────────────────────────

def extract_spoken_lines(md_path: Path) -> str:
    """
    Pulls only the quoted dialogue from the markdown script,
    stripping stage directions, headers, tables, and production notes.
    Handles both single-line and multi-line quoted blocks.
    """
    text = md_path.read_text(encoding="utf-8")

    # Only process the SCRIPT section
    script_match = re.search(r"## SCRIPT(.*?)(## PRODUCTION NOTES|## STATS|$)", text, re.DOTALL)
    if not script_match:
        raise ValueError("Could not find '## SCRIPT' section in the markdown file.")

    script_body = script_match.group(1)

    # Remove stage direction lines (lines that are only > *[...]*  with no speech)
    script_body = re.sub(r'^>\s*\*\[.*?\]\*\s*$', '', script_body, flags=re.MULTILINE)

    # Extract all quoted blocks — handles multi-line quotes
    raw_quotes = re.findall(r'"(.*?)"', script_body, re.DOTALL)

    spoken = []
    for q in raw_quotes:
        # Strip inline stage directions [like this]
        clean = re.sub(r'\[.*?\]', '', q, flags=re.DOTALL)
        # Strip markdown bold/italic markers
        clean = re.sub(r'\*+', '', clean)
        # Collapse internal newlines to spaces, then strip
        clean = re.sub(r'\s+', ' ', clean).strip()
        if clean:
            spoken.append(clean)

    if not spoken:
        raise ValueError("No spoken lines found. Check script formatting.")

    # Join with natural pauses
    full_text = "\n\n".join(spoken)
    return full_text

# ── Voiceover generation ──────────────────────────────────────────────────────

def generate_voiceover(text: str, output_path: Path) -> None:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ELEVENLABS_API_KEY not found.\n"
            "1. Get a free key at https://elevenlabs.io\n"
            "2. Create a .env file in this folder with:\n"
            "   ELEVENLABS_API_KEY=your_key_here"
        )

    client = ElevenLabs(api_key=api_key)

    print(f"  Voice    : {VOICE_NAME}")
    print(f"  Model    : {MODEL_ID}")
    print(f"  Chars    : {len(text)}")
    print(f"  Output   : {output_path}")
    print()
    print("-- Extracted script ------------------------------------------")
    print(text)
    print("--------------------------------------------------------------")
    print()
    print("Generating voiceover... (this may take 10–30 seconds)")

    audio_stream = client.text_to_speech.convert(
        voice_id=VOICE_ID,
        text=text,
        model_id=MODEL_ID,
        output_format="mp3_44100_128",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in audio_stream:
            f.write(chunk)

# ── Entry point --------------------------------------------------------------─

def main():
    script_path = Path(sys.argv[1]) if len(sys.argv) > 1 else SCRIPT_PATH

    if not script_path.exists():
        print(f"Error: Script not found at '{script_path}'")
        sys.exit(1)

    print(f"\nVoidPulse Voiceover Generator")
    print(f"Script : {script_path}")
    print()

    try:
        spoken_text = extract_spoken_lines(script_path)
        generate_voiceover(spoken_text, OUTPUT_FILE)
        print(f"\nDone! Voiceover saved to: {OUTPUT_FILE}")

    except (ValueError, EnvironmentError) as e:
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
