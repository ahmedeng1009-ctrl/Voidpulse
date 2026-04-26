"""
VoidPulse Bulk Script Generator
Generates multiple YouTube Shorts scripts using the Claude API with prompt caching.
Each script is saved as a markdown file in scripts/drafts/.

Setup:
    pip install anthropic python-dotenv
    Add ANTHROPIC_API_KEY=your_key to .env

Usage:
    python bulk_generate.py                  # generate all topics in TOPICS list
    python bulk_generate.py "Topic 1" "Topic 2"  # generate specific topics
"""

import re
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

# ── Topics to generate ────────────────────────────────────────────────────────

TOPICS = [
    "How much money billionaires make while you sleep",
    "The dark history of how social media hijacks your brain",
    "How much plastic is inside your body right now",
    "The real reason you can't afford a house",
    "How much food is wasted every second on Earth",
    "The secret life of your credit score",
    "How long it takes to burn off a Big Mac vs how long to eat it",
    "The terrifying scale of ocean plastic",
]

# ── Config ────────────────────────────────────────────────────────────────────

MODEL        = "claude-sonnet-4-6"
OUTPUT_DIR   = Path("scripts/drafts")
MAX_TOKENS   = 2048

# ── Cached system prompt ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a viral YouTube Shorts scriptwriter for the channel VoidPulse.

VoidPulse creates dark, dramatic, fact-based short videos that reveal uncomfortable truths about money, society, and power. The tone is serious, cinematic, and unsettling — never humorous.

SCRIPT FORMAT (follow exactly):
Each script must use this markdown structure:

```
# {TOPIC TITLE} | YouTube Short Script
**Niche:** Scary Real Statistics Visualized
**Duration:** ~50 seconds
**Style:** Dramatic / Conspiracy-core
**Hook Type:** [describe the hook type used]

---

## SCRIPT

---

**[HOOK — 0:00–0:05]**
> *[Stage direction in italics]*

"Spoken line."

"Spoken line."

---

**[BUILD — 0:05–0:20]**
> *[Stage direction in italics]*

"Spoken line with **bold stat**."

"Spoken line."

---

**[TWIST — 0:20–0:35]**
> *[Stage direction in italics]*

"Spoken line."

"Spoken line."

---

**[OUTRO / CTA — 0:35–0:50]**
> *[Stage direction in italics]*

"Closing line."

"**Punchy final line.**"

> *[End card: VoidPulse logo + subscribe prompt]*

---

## PRODUCTION NOTES

| Element | Details |
|---|---|
| **Voiceover pace** | [pacing guidance] |
| **Music** | [music style] |
| **Visuals** | [visual direction] |
| **Text on screen** | [text overlay style] |
| **SFX** | [sound effects] |
| **Hook retention trick** | [specific technique used] |

## STATS SOURCES
- [Source 1 with citation]
- [Source 2 with citation]
```

RULES:
- Hook must grab attention in the first 3 seconds with a shocking stat or question
- All spoken lines must be in double quotes on their own line
- Stage directions in > *[brackets]* are never spoken aloud
- Stats must be real and verifiable — cite sources at the bottom
- The twist should flip the viewer's assumption
- Closing line must be punchy and quotable (gets screenshots/shared)
- Total spoken word count: 100-130 words (fits 50 seconds at dramatic pace)
- No filler words. Every line must earn its place."""

# ── Generation ────────────────────────────────────────────────────────────────

def slugify(topic: str) -> str:
    slug = topic.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:60]


def generate_script(client: anthropic.Anthropic, topic: str, index: int, total: int) -> str:
    print(f"\n[{index}/{total}] Generating: {topic}")

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        # Cache the large system prompt — all requests share the same prefix,
        # so from the 2nd request onward the system prompt tokens are ~90% cheaper.
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f'Write a viral 50-second YouTube Shorts script for VoidPulse about:\n\n"{topic}"\n\nFollow the exact format from the system prompt. Make it dramatic and unsettling.',
            }
        ],
    )

    usage = response.usage
    cached = getattr(usage, "cache_read_input_tokens", 0)
    written = getattr(usage, "cache_creation_input_tokens", 0)
    uncached = usage.input_tokens

    cache_status = (
        f"cache HIT ({cached} tokens saved)"
        if cached > 0
        else f"cache MISS — wrote {written} tokens"
    )
    print(f"    Tokens: {uncached} input + {usage.output_tokens} output | {cache_status}")

    return response.content[0].text


def save_script(topic: str, content: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = slugify(topic) + ".md"
    path = OUTPUT_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    topics = list(sys.argv[1:]) if len(sys.argv) > 1 else TOPICS

    print(f"VoidPulse Bulk Script Generator")
    print(f"Model  : {MODEL}")
    print(f"Topics : {len(topics)}")
    print(f"Output : {OUTPUT_DIR}/")
    print("-" * 50)

    client = anthropic.Anthropic()
    saved = []
    failed = []

    for i, topic in enumerate(topics, 1):
        try:
            script = generate_script(client, topic, i, len(topics))
            path = save_script(topic, script)
            saved.append(path)
            print(f"    Saved : {path}")

            # Brief pause between requests to respect rate limits
            if i < len(topics):
                time.sleep(1)

        except anthropic.RateLimitError:
            print(f"    Rate limited — waiting 30s before retrying...")
            time.sleep(30)
            try:
                script = generate_script(client, topic, i, len(topics))
                path = save_script(topic, script)
                saved.append(path)
                print(f"    Saved : {path}")
            except Exception as e:
                print(f"    FAILED after retry: {e}")
                failed.append(topic)

        except Exception as e:
            print(f"    FAILED: {e}")
            failed.append(topic)

    print("\n" + "=" * 50)
    print(f"Done. {len(saved)} scripts saved, {len(failed)} failed.")
    if failed:
        print("Failed topics:")
        for t in failed:
            print(f"  - {t}")


if __name__ == "__main__":
    main()
