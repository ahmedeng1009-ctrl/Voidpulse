# VoidPulse — Automated YouTube Shorts Pipeline

Fully automated pipeline that generates and uploads a dark-facts YouTube Short every day at **02:00 AM Iraq time (23:00 UTC)**.

## What it does

1. **Picks a topic** — analytics-driven (smart), trending (Google Trends + YouTube), or evergreen pool
2. **Writes a script** — Claude generates a 20-second viral hook-first script
3. **Generates voiceover** — ElevenLabs (premium) with Edge TTS fallback (free, unlimited)
4. **Creates video** — Pexels backgrounds + karaoke text + cinematic SFX + stat overlays
5. **Generates thumbnail** — dramatic hook-text image with Pillow
6. **Uploads to YouTube** — SEO-optimized metadata (title, description, tags) in 8 languages, scheduled publish

## Topic strategy

Topics are strictly **TIER-1 personal/body threat** — things happening to *your* body *right now*.  
Political, financial, and systemic topics are blocked programmatically until 1,000 subscribers.

## Stack

- **AI**: Claude (script + SEO), Gemini (topic research with Google Search grounding)
- **TTS**: ElevenLabs → Edge TTS fallback
- **Video**: MoviePy + Pexels API
- **Upload**: YouTube Data API v3 with OAuth2
- **CI/CD**: GitHub Actions (daily cron at 23:00 UTC)
- **Notifications**: Telegram bot

## Required GitHub Secrets

| Secret | Required |
|--------|----------|
| `ANTHROPIC_API_KEY` | ✅ |
| `ELEVENLABS_API_KEY` | ✅ |
| `PEXELS_API_KEY` | ✅ |
| `YOUTUBE_TOKEN_JSON` | ✅ |
| `YOUTUBE_CLIENT_SECRET_JSON` | ✅ |
| `GEMINI_API_KEY` | optional (enables Google Search grounding) |
| `TELEGRAM_BOT_TOKEN` | optional (run notifications) |
| `TELEGRAM_CHAT_ID` | optional |
| `GH_PAT` | optional (auto-refreshes YouTube token) |

## Local setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys
python run_pipeline.py --smart --skip-upload   # test without uploading
```
