"""
VoidPulse Notifier — Telegram
يرسل إشعار على Telegram عند نجاح أو فشل كل run.

Setup:
  1. افتح Telegram وابحث عن @BotFather
  2. أرسل /newbot واتبع التعليمات — احفظ الـ Token
  3. ابحث عن @userinfobot وأرسل له /start — احفظ الـ Chat ID
  4. أضف في .env:
       TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
       TELEGRAM_CHAT_ID=123456789

Usage (من أي سكريبت):
    from notify import notify
    notify("تم رفع الفيديو بنجاح!")
"""

import os
import urllib.request
import urllib.parse
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def notify(message: str) -> bool:
    """
    أرسل رسالة Telegram. يرجع True إذا نجح، False إذا فشل بصمت.
    لا يوقف البرنامج إذا فشل الإرسال.
    """
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID",   "").strip()

    if not token or not chat_id:
        return False

    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id":    chat_id,
        "text":       message,
        "parse_mode": "HTML",
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  [notify] Telegram failed (non-critical): {e}")
        return False


# ── Setup helper ──────────────────────────────────────────────────────────────

def setup_wizard():
    """يساعدك على إعداد الـ Telegram bot خطوة بخطوة."""
    print("\n" + "="*55)
    print("  VoidPulse — إعداد إشعارات Telegram")
    print("="*55)
    print("""
خطوات الإعداد:

1. افتح Telegram → ابحث عن @BotFather
2. أرسل: /newbot
3. اختار اسم للبوت (مثال: VoidPulseBot)
4. احفظ الـ Token (مثال: 123456789:AAF...)

5. ابحث عن @userinfobot → أرسل /start
6. احفظ الـ Id (مثال: 987654321)

7. أضف هذين السطرين لملف .env:
   TELEGRAM_BOT_TOKEN=<الـ token>
   TELEGRAM_CHAT_ID=<الـ id>

8. شغّل: python notify.py --test
""")


def test_notification():
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID",   "").strip()

    if not token or not chat_id:
        print("\n  لم يتم إعداد Telegram بعد.")
        setup_wizard()
        return

    print(f"\n  إرسال رسالة تجريبية إلى Chat ID: {chat_id}...")
    ok = notify(
        "✅ <b>VoidPulse</b> — اختبار الإشعارات\n"
        "إذا وصلت هذه الرسالة، الإعداد يعمل بشكل صحيح!"
    )
    if ok:
        print("  تم الإرسال بنجاح!")
    else:
        print("  فشل الإرسال — تحقق من TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID في .env")


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        test_notification()
    else:
        setup_wizard()
