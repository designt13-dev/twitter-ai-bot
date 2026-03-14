# src/agents/publisher_agent.py
"""
وكيل النشر الذكي (Smart Publisher Agent)
══════════════════════════════════════════════════════════════
المهام:
  1. استقبال التغريدة من ContentAgent
  2. التحقق من الجودة قبل النشر (audit)
  3. رفع الصورة إذا توفرت
  4. النشر عبر Twitter API v2
  5. تسجيل نتيجة النشر (ID، طول، صورة، وقت)
  6. إدارة حد المعدل (rate limit)
══════════════════════════════════════════════════════════════
"""
import tweepy
import tweepy.api
import requests
import tempfile
import mimetypes
import time
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from config.settings import (
    CONSUMER_KEY, CONSUMER_SECRET,
    ACCESS_TOKEN, ACCESS_TOKEN_SECRET,
    BEARER_TOKEN, LOGS_DIR,
)
from src.utils import logger, now_riyadh, tweet_length

MAX_TWEET_LENGTH  = 275
SUPPORTED_MIMES   = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE_MB = 5


def get_v2_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )


def get_v1_api() -> tweepy.API:
    auth = tweepy.OAuth1UserHandler(
        CONSUMER_KEY, CONSUMER_SECRET,
        ACCESS_TOKEN, ACCESS_TOKEN_SECRET,
    )
    return tweepy.API(auth, wait_on_rate_limit=True)


class PublisherAgent:
    """
    وكيل النشر الذكي.
    يأخذ نتيجة ContentAgent ويقوم بالنشر الكامل.
    """

    def __init__(self):
        self.name       = "PublisherAgent"
        self.v2_client  = get_v2_client()
        self.v1_api     = get_v1_api()

    def _upload_image(self, image_url: str) -> str | None:
        """
        تنزيل الصورة ورفعها على Twitter.
        يُعيد media_id أو None إذا فشل.
        """
        if not image_url:
            return None

        try:
            resp = requests.get(image_url, timeout=15)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
            if content_type not in SUPPORTED_MIMES:
                logger.warning(f"[{self.name}] نوع صورة غير مدعوم: {content_type}")
                return None

            size_mb = len(resp.content) / (1024 * 1024)
            if size_mb > MAX_IMAGE_SIZE_MB:
                logger.warning(f"[{self.name}] الصورة كبيرة جداً: {size_mb:.1f} MB")
                return None

            ext = mimetypes.guess_extension(content_type) or ".jpg"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name

            media = self.v1_api.media_upload(tmp_path)
            logger.info(f"[{self.name}] ✅ صورة رُفعت: media_id={media.media_id}")
            return str(media.media_id)

        except Exception as e:
            logger.warning(f"[{self.name}] فشل رفع الصورة: {e}")
            return None

    def _audit_before_post(self, text: str) -> str:
        """تقليم النص إذا تجاوز الحد"""
        length = tweet_length(text)
        if length <= MAX_TWEET_LENGTH:
            return text

        # قطع عند آخر جملة مكتملة
        import re
        for punct in ['؟', '!', '.', '،']:
            pos = text.rfind(punct, 0, MAX_TWEET_LENGTH - 5)
            if pos > MAX_TWEET_LENGTH * 0.5:
                return text[:pos + 1].strip()

        return text[:MAX_TWEET_LENGTH].strip()

    def publish(self, tweet_data: dict) -> dict:
        """
        ينشر التغريدة ويُعيد نتيجة النشر.

        tweet_data يتضمن:
          - tweet: نص التغريدة
          - image_url: رابط الصورة (اختياري)
          - audit: تقرير الجودة من ContentAgent
        """
        text      = tweet_data.get("tweet", "")
        image_url = tweet_data.get("image_url")
        audit     = tweet_data.get("audit", {})

        if not text:
            logger.error(f"[{self.name}] ❌ نص فارغ — تم التخطي")
            return {"success": False, "error": "empty_text"}

        # ── تحقق أولي ────────────────────────────────────────
        text   = self._audit_before_post(text)
        length = tweet_length(text)

        logger.info(
            f"[{self.name}] 📤 جاهز للنشر | "
            f"{length} حرف | "
            f"جودة: {audit.get('score', '?')}/10 | "
            f"صورة: {'✅' if image_url else '❌'}"
        )

        # ── رفع الصورة ────────────────────────────────────────
        media_id = self._upload_image(image_url) if image_url else None

        # ── النشر ────────────────────────────────────────────
        try:
            kwargs = {"text": text}
            if media_id:
                kwargs["media_ids"] = [media_id]

            response = self.v2_client.create_tweet(**kwargs)
            tweet_id = str(response.data["id"])

            logger.info(
                f"[{self.name}] ✅ نُشر! | "
                f"ID: {tweet_id} | "
                f"{length} حرف | "
                f"{'صورة ✅' if media_id else 'بدون صورة'} | "
                f"{now_riyadh().strftime('%H:%M')}"
            )

            return {
                "success":   True,
                "tweet_id":  tweet_id,
                "length":    length,
                "has_image": bool(media_id),
                "text":      text,
            }

        except tweepy.Forbidden as e:
            logger.error(f"[{self.name}] ❌ Forbidden: {e}")
            return {"success": False, "error": "forbidden", "details": str(e)}

        except tweepy.TooManyRequests:
            logger.warning(f"[{self.name}] ⏳ Rate limit — انتظار 15 دقيقة")
            time.sleep(900)
            return {"success": False, "error": "rate_limit"}

        except tweepy.TweepyException as e:
            logger.error(f"[{self.name}] ❌ خطأ: {e}")
            return {"success": False, "error": str(e)}

    def publish_batch(self, tweets_data: list, delay_seconds: int = 30) -> list:
        """
        نشر دفعة من التغريدات مع تأخير بينها.
        """
        results = []
        for i, td in enumerate(tweets_data, 1):
            logger.info(f"[{self.name}] 🔄 نشر {i}/{len(tweets_data)}")
            result = self.publish(td)
            results.append(result)

            if i < len(tweets_data) and result.get("success"):
                time.sleep(delay_seconds)

        success_count = sum(1 for r in results if r.get("success"))
        logger.info(
            f"[{self.name}] 🏁 الدفعة كاملة: "
            f"{success_count}/{len(tweets_data)} نُشر بنجاح"
        )
        return results
