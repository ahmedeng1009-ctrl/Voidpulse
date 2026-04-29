"""
VoidPulse Affiliate Links — توليد روابط أفلييت ذكية حسب الموضوع
يضيف 2-3 روابط مناسبة في وصف كل فيديو تلقائياً.

كيف تربح فلوس:
  1. سجّل في Amazon Associates: https://affiliate-program.amazon.com
     - تأخذ tag مثل "yourname-20"
     - أضف في .env: AMAZON_TAG=yourname-20
  2. سجّل في NordVPN affiliate: https://nordvpn.com/affiliate
     - تأخذ رابط مثل: https://go.nordvpn.net/aff_c?aff_id=XXX
     - أضف في .env: NORDVPN_LINK=<رابطك>
  3. سجّل في Audible: https://www.audibleinc.com/audible-creator-program
     - أضف: AUDIBLE_LINK=<رابطك>

بدون هذه الـ tags، الكود يحط روابط بحث Amazon عادية (مفيدة للمشاهدين بس بدون عمولة).
"""

import os
import re
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()


# ── Affiliate IDs (من .env) ───────────────────────────────────────────────────

AMAZON_TAG    = os.getenv("AMAZON_TAG", "").strip()        # tag مثل "voidpulse-20"
NORDVPN_LINK  = os.getenv("NORDVPN_LINK", "").strip()      # رابط NordVPN affiliate
AUDIBLE_LINK  = os.getenv("AUDIBLE_LINK", "").strip()      # رابط Audible affiliate
PROTONVPN_LINK = os.getenv("PROTONVPN_LINK", "").strip()   # رابط ProtonVPN affiliate


def amazon_search(keywords: str) -> str:
    """Return Amazon search URL with affiliate tag if available."""
    encoded = quote_plus(keywords)
    base = f"https://www.amazon.com/s?k={encoded}"
    if AMAZON_TAG:
        return f"{base}&tag={AMAZON_TAG}"
    return base


# ── Topic → Product mapping ───────────────────────────────────────────────────

TOPIC_AFFILIATES = {
    # Privacy / Surveillance / Government
    "surveillance|government|fear|control|power|spy": [
        lambda: ("🛡️ Protect your privacy", NORDVPN_LINK or "https://nordvpn.com/"),
        lambda: ("📚 'Permanent Record' by Edward Snowden",
                 amazon_search("Permanent Record Edward Snowden book")),
        lambda: ("🔒 Browse anonymously with ProtonVPN",
                 PROTONVPN_LINK or "https://protonvpn.com/"),
    ],

    # Phone / Social Media / Brain
    "social media|phone|algorithm|brain|dumber|screen time|addiction|scrolling|tiktok": [
        lambda: ("📚 'Indistractable' by Nir Eyal",
                 amazon_search("Indistractable Nir Eyal book")),
        lambda: ("👓 Blue light blocking glasses",
                 amazon_search("blue light blocking glasses")),
        lambda: ("📚 'The Shallows' by Nicholas Carr",
                 amazon_search("The Shallows Nicholas Carr book")),
    ],

    # Money / Tax / Wealth / Housing
    "money|tax|billionaire|wealth|rich|housing|afford|rent|real estate": [
        lambda: ("📚 'Rich Dad Poor Dad' by Robert Kiyosaki",
                 amazon_search("Rich Dad Poor Dad book")),
        lambda: ("📚 'The Psychology of Money' by Morgan Housel",
                 amazon_search("Psychology of Money Morgan Housel")),
        lambda: ("📚 'Capital in the 21st Century' by Piketty",
                 amazon_search("Capital 21st Century Piketty")),
    ],

    # Food / Health / Addiction
    "food|eat|engineer|addiction|big mac|sugar|fat": [
        lambda: ("📚 'Salt Sugar Fat' by Michael Moss",
                 amazon_search("Salt Sugar Fat Michael Moss")),
        lambda: ("📚 'Hooked' by Michael Moss",
                 amazon_search("Hooked Michael Moss food")),
        lambda: ("🥗 Whole food meal plans",
                 amazon_search("clean eating cookbook")),
    ],

    # Sleep / Mattress / Bed
    "sleep|insomnia|tired|dream|exhaust|mattress|bed|bedroom|eight hours": [
        lambda: ("📚 'Why We Sleep' by Matthew Walker",
                 amazon_search("Why We Sleep Matthew Walker")),
        lambda: ("🛏️ Organic non-toxic mattress",
                 amazon_search("organic certified non toxic mattress")),
        lambda: ("🌙 Sleep mask + earplugs combo",
                 amazon_search("sleep mask earplugs set")),
    ],

    # Body / Personal care / Chemicals — specific product terms only (avoid "poisoning the planet")
    "deodorant|shampoo|toothpaste|sunscreen|cosmetic|lymph|hormone|pfas|forever chemical|drinking water|tap water|aluminum free|personal care|skincare": [
        lambda: ("🧴 Natural aluminum-free deodorant",
                 amazon_search("natural aluminum free deodorant organic")),
        lambda: ("📚 'Toxic Beauty' by Dawn Mellowship",
                 amazon_search("Toxic Beauty book Dawn Mellowship")),
        lambda: ("🚿 Shower filter (removes chlorine + chemicals)",
                 amazon_search("shower filter chlorine fluoride removal")),
    ],

    # Plastic / Ocean / Environment / Fashion
    "plastic|ocean|pollution|fashion|textile|environment": [
        lambda: ("📚 'The Story of Stuff' by Annie Leonard",
                 amazon_search("Story of Stuff Annie Leonard")),
        lambda: ("♻️ Reusable water bottles",
                 amazon_search("stainless steel reusable water bottle")),
        lambda: ("📚 'Cradle to Cradle'",
                 amazon_search("Cradle to Cradle book")),
    ],

    # Loneliness / Society
    "loneliness|alone|isolation|society|silent epidemic": [
        lambda: ("📚 'Bowling Alone' by Robert Putnam",
                 amazon_search("Bowling Alone Robert Putnam")),
        lambda: ("📚 'Lost Connections' by Johann Hari",
                 amazon_search("Lost Connections Johann Hari")),
    ],

    # Amazon / Supply chain / Workers
    "amazon|cheap|supply chain|worker|labor|package": [
        lambda: ("📚 'The Everything Store' by Brad Stone",
                 amazon_search("Everything Store Brad Stone Amazon")),
        lambda: ("📚 'Bullshit Jobs' by David Graeber",
                 amazon_search("Bullshit Jobs David Graeber")),
    ],
}


# ── Default (يعمل لأي موضوع) ──────────────────────────────────────────────────

DEFAULT_AFFILIATES = [
    lambda: ("📚 Top dark history books",
             amazon_search("dark history conspiracy books bestseller")),
    lambda: ("🎧 Audiobooks free trial",
             AUDIBLE_LINK or "https://www.audible.com/"),
    lambda: ("🛡️ NordVPN — protect your data",
             NORDVPN_LINK or "https://nordvpn.com/"),
]


def get_affiliate_links(topic: str) -> list[tuple[str, str]]:
    """
    يرجع قائمة بـ 2-3 روابط affiliate مناسبة للموضوع.
    Returns: [(label, url), ...]
    """
    t = topic.lower()
    for keyword_pattern, link_funcs in TOPIC_AFFILIATES.items():
        if re.search(keyword_pattern, t, re.IGNORECASE):
            return [fn() for fn in link_funcs[:3]]

    # Fallback to default
    return [fn() for fn in DEFAULT_AFFILIATES[:3]]


def build_affiliate_section(topic: str) -> str:
    """
    يبني قسم 'Resources' لإضافته في وصف الفيديو.
    """
    links = get_affiliate_links(topic)
    if not links:
        return ""

    lines = ["", "━━━━━━━━━━━━━━━━━━━━━━", "📌 RESOURCES (affiliate):", ""]
    for label, url in links:
        lines.append(f"{label}")
        lines.append(f"→ {url}")
        lines.append("")

    if AMAZON_TAG:
        lines.append("(As an Amazon Associate, I earn from qualifying purchases.)")
    return "\n".join(lines)


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "How your phone is making you dumber"
    print(f"\nTopic: {topic}\n")
    print(build_affiliate_section(topic))
