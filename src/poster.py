# src/poster.py
"""
النشر الرئيسي على X — مع دعم الصور عبر Twitter API v1.1
═══════════════════════════════════════════════════════════════
التدفق:
1. جلب الخبر (news_fetcher)
2. توليد التغريدة الإبداعية (content_generator)
3. رفع الصورة إن وُجدت (v1.1 media_upload)
4. نشر التغريدة مع media_id (v2 create_tweet)
═══════════════════════════════════════════════════════════════
"""
import tweepy
import time
import random
import requests
import tempfile
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from config.settings import (
    CONSUMER_KEY, CONSUMER_SECRET,
    ACCESS_TOKEN, ACCESS_TOKEN_SECRET,
    BEARER_TOKEN,
)
from src.utils import logger, now_riyadh, tweet_length, smart_truncate

# ── حد الطول الآمن ──────────────────────────────────────────
TWEET_HARD_LIMIT = 275

# ── أنواع الصور المدعومة ─────────────────────────────────────
SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png":  ".png",
    "image/webp": ".webp",
    "image/gif":  ".gif",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ══════════════════════════════════════════════════════════════
#  إعداد العملاء
# ══════════════════════════════════════════════════════════════
def get_v2_client() -> tweepy.Client:
    """عميل v2 للنشر"""
    return tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )


def get_v1_api() -> tweepy.API:
    """عميل v1.1 لرفع الوسائط"""
    auth = tweepy.OAuth1UserHandler(
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
    )
    return tweepy.API(auth, wait_on_rate_limit=True)


# ══════════════════════════════════════════════════════════════
#  رفع الصورة
# ══════════════════════════════════════════════════════════════
def upload_image(api_v1: tweepy.API, image_url: str) -> str | None:
    """
    يحمّل الصورة من URL ويرفعها إلى Twitter
    يُعيد media_id_string أو None عند الفشل
    """
    if not image_url:
        return None

    tmp_path = None
    try:
        # تحميل الصورة
        resp = requests.get(image_url, headers=HEADERS, timeout=10, stream=True)
        if resp.status_code != 200:
            logger.warning(f"[Media] فشل تحميل الصورة: HTTP {resp.status_code}")
            return None

        # تحديد الامتداد
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        ext = SUPPORTED_IMAGE_TYPES.get(content_type, ".jpg")

        # حفظ مؤقت
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            for chunk in resp.iter_content(chunk_size=8192):
                tmp.write(chunk)
            tmp_path = tmp.name

        # فحص الحجم (Twitter يقبل حتى 5MB للصور)
        size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
        if size_mb > 5:
            logger.warning(f"[Media] الصورة كبيرة جدًا: {size_mb:.1f}MB")
            return None

        # رفع إلى Twitter
        media = api_v1.media_upload(filename=tmp_path)
        logger.info(f"[Media] ✅ صورة مرفوعة | ID: {media.media_id_string}")
        return media.media_id_string

    except Exception as e:
        logger.warning(f"[Media] فشل رفع الصورة: {e}")
        return None

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ══════════════════════════════════════════════════════════════
#  فحص الطول قبل النشر
# ══════════════════════════════════════════════════════════════
def validate_before_post(text: str) -> str:
    length = tweet_length(text)
    if length > TWEET_HARD_LIMIT:
        logger.warning(
            f"[Validate] ⚠️ {length} حرف > {TWEET_HARD_LIMIT} — قطع ذكي"
        )
        text = smart_truncate(text, TWEET_HARD_LIMIT - 5)
    return text


# ══════════════════════════════════════════════════════════════
#  نشر تغريدة واحدة
# ══════════════════════════════════════════════════════════════
def post_single_tweet(
    client_v2: tweepy.Client,
    text: str,
    media_id: str | None = None,
) -> tweepy.Response | None:
    text = validate_before_post(text)

    try:
        kwargs = {"text": text}
        if media_id:
            kwargs["media_ids"] = [media_id]

        response = client_v2.create_tweet(**kwargs)
        tweet_id = response.data["id"]
        logger.info(
            f"[Post] ✅ نُشرت | ID: {tweet_id} | "
            f"الطول: {tweet_length(text)} | "
            f"صورة: {'✅' if media_id else '❌'}"
        )
        logger.info(f"[Post] النص: {text[:120]}...")
        return response

    except tweepy.errors.Forbidden as e:
        logger.error(f"[Post] ❌ ممنوع (تحقق من صلاحيات Read+Write): {e}")
        return None
    except tweepy.errors.TooManyRequests:
        logger.warning("[Post] ⏳ Rate limit — انتظار 15 دقيقة...")
        time.sleep(900)
        return None
    except tweepy.TweepyException as e:
        logger.error(f"[Post] ❌ فشل النشر: {e}")
        return None


# ══════════════════════════════════════════════════════════════
#  الدالة الرئيسية — تشغيل واحد = تغريدة واحدة مع صورة
# ══════════════════════════════════════════════════════════════
def run_poster():
    from src.content_generator import generate_tweet

    logger.info(
        f"\n{'='*55}\n"
        f"[Poster] 🚀 جلسة النشر — "
        f"{now_riyadh().strftime('%Y-%m-%d %H:%M')} (الرياض)\n"
        f"{'='*55}"
    )

    client_v2 = get_v2_client()
    api_v1    = get_v1_api()
    content   = generate_tweet()

    text      = content.get("text", "")
    image_url = content.get("image_url")

    if not text:
        logger.error("[Poster] ❌ لم يُولَّد محتوى")
        return

    # ── رفع الصورة إن وُجدت ─────────────────────────────────
    media_id = None
    if image_url:
        logger.info(f"[Poster] 🖼️ رفع صورة: {image_url[:80]}...")
        media_id = upload_image(api_v1, image_url)

    # ── النشر ───────────────────────────────────────────────
    post_single_tweet(client_v2, text, media_id)

    logger.info(f"[Poster] 🏁 انتهت الجلسة\n{'='*55}")


if __name__ == "__main__":
    run_poster()
