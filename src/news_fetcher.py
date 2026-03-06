# src/news_fetcher.py
"""
جلب أخبار يومية حقيقية — مع استخراج الصور من المقالات
النمط: بحث → تصفية → ترجمة → صورة
"""
import feedparser
import random
import re
import requests
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from config.settings import RSS_SOURCES, BLOCKED_KEYWORDS, TIMEZONE
from src.utils import logger, clean_text

# ── User-Agent لتجاوز حجب الـ RSS ──────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ── فحص الكلمات المحظورة ────────────────────────────────────
def _is_blocked(text: str) -> bool:
    text_lower = text.lower()
    for kw in BLOCKED_KEYWORDS:
        if kw.lower() in text_lower:
            return True
    return False


# ── فحص الحداثة (72 ساعة) ────────────────────────────────────
def _is_recent(entry, hours: int = 72) -> bool:
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            pub = datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
            tz  = pytz.timezone(TIMEZONE)
            now = datetime.now(tz).astimezone(pytz.utc)
            return (now - pub) < timedelta(hours=hours)
    except Exception:
        pass
    return True


# ── استخراج صورة من مقالة ────────────────────────────────────
def extract_image_from_entry(entry) -> str | None:
    """
    يحاول استخراج URL الصورة من:
    1. حقل media_content في RSS
    2. حقل enclosures
    3. حقل media_thumbnail
    4. الـ og:image من صفحة المقالة (fallback)
    """
    # 1. media:content
    if hasattr(entry, "media_content"):
        for media in entry.media_content:
            if media.get("medium") == "image" or media.get("url", "").endswith(
                (".jpg", ".jpeg", ".png", ".webp")
            ):
                return media.get("url")

    # 2. enclosures
    if hasattr(entry, "enclosures"):
        for enc in entry.enclosures:
            if "image" in enc.get("type", "") or enc.get("url", "").endswith(
                (".jpg", ".jpeg", ".png", ".webp")
            ):
                return enc.get("url")

    # 3. media_thumbnail
    if hasattr(entry, "media_thumbnail"):
        for thumb in entry.media_thumbnail:
            if thumb.get("url"):
                return thumb["url"]

    # 4. og:image من الصفحة (fallback — أبطأ)
    link = getattr(entry, "link", "")
    if link:
        return _fetch_og_image(link)

    return None


def _fetch_og_image(url: str, timeout: int = 5) -> str | None:
    """جلب og:image من صفحة المقالة"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")

        # og:image
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]

        # twitter:image
        tw = soup.find("meta", attrs={"name": "twitter:image"})
        if tw and tw.get("content"):
            return tw["content"]

        # أول صورة في المقالة
        img = soup.find("img", src=re.compile(r"\.(jpg|jpeg|png|webp)", re.I))
        if img and img.get("src"):
            src = img["src"]
            if src.startswith("http"):
                return src

    except Exception as e:
        logger.debug(f"[Image] فشل جلب og:image من {url}: {e}")
    return None


# ── ترجمة باستخدام deep-translator ──────────────────────────
def translate_to_arabic(text: str, max_len: int = 300) -> str:
    if not text:
        return ""
    try:
        from deep_translator import GoogleTranslator
        text = text[:max_len]
        translated = GoogleTranslator(source="en", target="ar").translate(text)
        return translated or text
    except Exception as e:
        logger.warning(f"[Translate] فشل: {e}")
        return text


# ── جلب المقالات من RSS ──────────────────────────────────────
def fetch_articles(max_per_source: int = 6) -> list[dict]:
    articles = []
    for source in RSS_SOURCES:
        try:
            feed = feedparser.parse(source["url"])
            count = 0
            for entry in feed.entries:
                if count >= max_per_source:
                    break

                title   = clean_text(getattr(entry, "title",   "") or "")
                summary = clean_text(getattr(entry, "summary", "") or "")
                link    = getattr(entry, "link", "") or ""

                full_text = f"{title} {summary}"
                if _is_blocked(full_text):
                    continue
                if not _is_recent(entry, hours=72):
                    continue
                if not title:
                    continue

                # جلب الصورة
                image_url = extract_image_from_entry(entry)

                articles.append({
                    "title":     title,
                    "summary":   summary[:500],
                    "link":      link,
                    "source":    source["name"],
                    "lang":      source["lang"],
                    "image_url": image_url,
                })
                count += 1

        except Exception as e:
            logger.warning(f"[RSS] فشل جلب {source.get('name','?')}: {e}")

    random.shuffle(articles)
    logger.info(
        f"[RSS] {len(articles)} مقالة — "
        f"{sum(1 for a in articles if a.get('image_url'))} بصور"
    )
    return articles


def get_random_article() -> dict | None:
    articles = fetch_articles(max_per_source=8)
    if not articles:
        return None
    return random.choice(articles)


def get_articles_batch(n: int = 5) -> list[dict]:
    """جلب مجموعة من المقالات (للنشر اليومي المتعدد)"""
    articles = fetch_articles(max_per_source=10)
    # أعطِ أولوية للمقالات التي لها صور
    with_images    = [a for a in articles if a.get("image_url")]
    without_images = [a for a in articles if not a.get("image_url")]
    combined = with_images + without_images
    return combined[:n]
