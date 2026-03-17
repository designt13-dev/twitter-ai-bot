# src/agents/search_agent.py — v6 (AI + فنون + اكتشافات، بدون رياضة)
"""
وكيل البحث والخوارزميات — v6
══════════════════════════════════════════════════════════════════
التحسينات في v6:
  ✅ يدعم ثلاثة محاور: AI + فنون عالمية + اكتشافات علمية حديثة
  ✅ فلتر صارم يحذف: رياضة / ترفيه / مراجعات / عروض تجارية
  ✅ يستخرج image_url من كل خبر ويرفقه مع المقال
  ✅ خوارزمية تقييم محسّنة تناسب المحاور الثلاثة
══════════════════════════════════════════════════════════════════
"""
import re
import sys
import pathlib
from datetime import datetime

import pytz

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from src.news_fetcher import fetch_articles
from src.utils import logger, clean_text

# ══════════════════════════════════════════════════════════════════
# كلمات المحاور المسموح بها
# ══════════════════════════════════════════════════════════════════

# المحور ١: الذكاء الاصطناعي
AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "neural network", "llm", "large language model", "gpt", "gemini",
    "claude", "llama", "chatbot", "chatgpt", "automation", "robot",
    "algorithm", "data science", "openai", "google ai", "microsoft ai",
    "meta ai", "deepmind", "anthropic", "nvidia", "foundation model",
    "generative ai", "diffusion model", "transformer", "agent",
    "ذكاء اصطناعي", "تعلم آلي", "نموذج لغوي", "روبوت", "خوارزمية",
]

# المحور ٢: الفنون والثقافة العالمية
ARTS_KEYWORDS = [
    "art", "museum", "exhibition", "gallery", "painting", "sculpture",
    "architecture", "design", "fashion", "creative", "artist",
    "digital art", "generative art", "ai art", "nft", "culture",
    "film festival", "music", "photography", "illustration",
    "فن", "متحف", "معرض", "لوحة", "نحت", "تصميم", "إبداع",
    "فنان", "فنون رقمية", "ثقافة", "تصوير فوتوغرافي",
]

# المحور ٣: الاكتشافات والعلوم الحديثة
DISCOVERY_KEYWORDS = [
    "discovery", "research", "study", "scientist", "breakthrough",
    "found", "space", "astronomy", "biology", "medicine", "physics",
    "climate", "environment", "archaeology", "ancient", "dna",
    "اكتشاف", "علم", "أبحاث", "دراسة", "فضاء", "طب", "بيئة",
    "آثار", "علماء",
]

# ══════════════════════════════════════════════════════════════════
# كلمات محظورة صارمة (رياضة / ترفيه / ألعاب / تجاري)
# ══════════════════════════════════════════════════════════════════

HARD_BLOCK = [
    # رياضة
    "football", "soccer", "basketball", "nba", "nfl", "cricket",
    "tennis", "golf", "rugby", "hockey", "esports", "t20",
    "world cup", "premier league", "champions league", "fifa",
    "كرة قدم", "كرة سلة", "دوري", "كأس العالم", "كرة",
    # ألعاب وترفيه
    "wordle", "crossword", "puzzle answer", "game hints",
    "connections answers", "nyt connections", "quiz",
    "movie", "tv show", "series", "netflix", "disney",
    "streaming", "episode", "season", "trailer",
    "فيلم", "مسلسل", "حلقة",
    # تجاري خالص
    "best buy", "deal of the day", "discount", "promo code",
    "coupon", "gift card", "sale price", "buying guide",
    "best laptop", "best phone", "best headphone", "vs review",
    # سياسة وعسكري
    "military", "defense", "weapon", "warfare", "missile",
    "drone strike", "pentagon", "nato", "army", "war",
    "republican", "democrat", "election", "حرب", "عسكري", "انتخابات",
]

# ══════════════════════════════════════════════════════════════════
# كلمات لرفع النقاط
# ══════════════════════════════════════════════════════════════════

NOVELTY_KW = [
    "launch", "announce", "release", "unveil", "introduce",
    "new", "first", "breakthrough", "upgrade", "update",
    "open-source", "available", "إطلاق", "إعلان", "جديد", "أول",
]

NUMBER_RE = re.compile(
    r'(\$?\d[\d,\.]*)[\s\-]*(billion|million|thousand|%|x\b|times)',
    re.IGNORECASE
)

TRUSTED_SOURCES = [
    "MIT Technology Review", "VentureBeat", "TechCrunch",
    "The Verge", "Wired", "Ars Technica", "OpenAI Blog",
    "Google AI Blog", "DeepMind Blog", "Hugging Face Blog",
    "Hyperallergic", "Artsy", "Dezeen", "National Geographic",
    "Scientific American", "Nature", "Science News",
]

BIG_NAMES = [
    "openai", "google", "deepmind", "meta", "apple", "microsoft",
    "amazon", "anthropic", "nvidia", "louvre", "moma", "nasa",
]


# ══════════════════════════════════════════════════════════════════
# دوال مساعدة
# ══════════════════════════════════════════════════════════════════

def _is_allowed(article: dict) -> bool:
    """يتحقق إن الخبر ينتمي لمحور مسموح به وليس محجوباً."""
    title   = (article.get("title",   "") or "").lower()
    summary = (article.get("summary", "") or "").lower()
    text    = title + " " + summary

    # حظر صارم أولاً
    if any(kw in text for kw in HARD_BLOCK):
        return False

    # يجب أن ينتمي لأحد المحاور الثلاثة
    in_ai        = any(kw in text for kw in AI_KEYWORDS)
    in_arts      = any(kw in text for kw in ARTS_KEYWORDS)
    in_discovery = any(kw in text for kw in DISCOVERY_KEYWORDS)

    return in_ai or in_arts or in_discovery


def _score(article: dict) -> int:
    """يحسب نقاط الجودة والتفاعل المتوقع."""
    score   = 0
    title   = (article.get("title",   "") or "").lower()
    summary = (article.get("summary", "") or "").lower()
    text    = title + " " + summary
    source  = article.get("source", "")

    if any(kw in text for kw in NOVELTY_KW):
        score += 4
    if NUMBER_RE.search(text):
        score += 3
    if any(kw in text for kw in ["saudi", "ksa", "riyadh", "vision 2030",
                                   "سعودي", "المملكة", "رؤية"]):
        score += 3
    if any(s in source for s in TRUSTED_SOURCES):
        score += 2
    if any(n in text for n in BIG_NAMES):
        score += 1

    # حداثة الخبر
    pub_date = article.get("published_parsed")
    if pub_date:
        try:
            riyadh = pytz.timezone("Asia/Riyadh")
            pub_dt = datetime(*pub_date[:6], tzinfo=pytz.utc).astimezone(riyadh)
            age_h  = (datetime.now(riyadh) - pub_dt).total_seconds() / 3600
            if age_h < 24:
                score += 2
            elif age_h > 48:
                score -= 3
        except Exception:
            pass

    # خصم مراجعات خالصة
    if any(kw in text for kw in ["review", "hands-on", "should you buy", "مراجعة"]):
        score -= 2

    return score


def _extract_entities(article: dict) -> dict:
    title   = article.get("title",   "") or ""
    summary = article.get("summary", "") or ""
    text    = title + " " + summary
    t_lower = text.lower()

    # أدوات AI
    AI_TOOLS = [
        "ChatGPT", "GPT-4", "GPT-5", "GPT-4o", "o1", "o3", "o4",
        "Gemini", "Claude", "Grok", "Copilot", "Perplexity",
        "Llama", "DeepSeek", "Sora", "DALL-E", "Midjourney",
        "Stable Diffusion", "Runway", "Mistral", "Gemma",
    ]
    tool = next((t for t in AI_TOOLS if t.lower() in t_lower), "")

    # شركات
    COMPANIES = [
        "OpenAI", "Google", "DeepMind", "Meta", "Apple",
        "Microsoft", "Amazon", "Anthropic", "Nvidia", "Tesla",
        "Samsung", "xAI", "Mistral", "Cohere", "SDAIA",
    ]
    company = next((c for c in COMPANIES if c.lower() in t_lower), "")

    # أرقام
    nums = NUMBER_RE.findall(text)
    key_number = f"{nums[0][0]} {nums[0][1]}" if nums else ""

    # تصنيف
    if any(kw in t_lower for kw in ["art", "museum", "painting", "design",
                                      "فن", "متحف", "تصميم"]):
        category = "arts"
    elif any(kw in t_lower for kw in ["discover", "research", "science",
                                        "اكتشاف", "علم"]):
        category = "discovery"
    elif any(kw in t_lower for kw in ["open-source", "open source"]):
        category = "open_source"
    elif any(kw in t_lower for kw in ["billion", "million", "funding",
                                        "تمويل"]):
        category = "funding"
    elif any(kw in t_lower for kw in ["layoff", "fired", "job loss",
                                        "تسريح"]):
        category = "jobs"
    elif any(kw in t_lower for kw in ["saudi", "ksa", "vision 2030",
                                        "سعودي", "رؤية"]):
        category = "ksa"
    elif any(kw in t_lower for kw in ["risk", "danger", "warning", "ban",
                                        "خطر", "تحذير"]):
        category = "risk"
    else:
        category = "novelty"

    return {"tool": tool, "company": company, "number": key_number, "category": category}


def _get_image(article: dict) -> str:
    """يحاول استخراج رابط صورة من الخبر."""
    # محاولة 1: حقل image_url مباشر
    img = article.get("image_url") or article.get("image") or ""
    if img and img.startswith("http"):
        return img

    # محاولة 2: media_content من feedparser
    media = article.get("media_content", [])
    if media and isinstance(media, list):
        for m in media:
            url = m.get("url", "")
            if url and url.startswith("http"):
                return url

    # محاولة 3: enclosures
    enclosures = article.get("enclosures", [])
    if enclosures:
        for enc in enclosures:
            url = enc.get("url", "")
            if url and ("jpg" in url or "png" in url or "jpeg" in url or "webp" in url):
                return url

    return ""


# ══════════════════════════════════════════════════════════════════
# SearchAgent v6
# ══════════════════════════════════════════════════════════════════

class SearchAgent:
    """وكيل البحث v6 — يجلب أخبار AI + فنون + اكتشافات، بدون رياضة."""

    def __init__(self):
        self.name = "SearchAgent-v6"

    def get_top_articles(self, n: int = 8) -> list:
        logger.info(f"[{self.name}] 🔍 جلب الأخبار من المصادر...")
        raw = fetch_articles()

        # فلترة المحاور المسموحة فقط
        allowed = [a for a in raw if _is_allowed(a)]
        logger.info(
            f"[{self.name}] الكل: {len(raw)} | "
            f"مسموح: {len(allowed)} | "
            f"محجوب: {len(raw) - len(allowed)}"
        )

        # تقييم وترتيب
        for art in allowed:
            art["score"]    = _score(art)
            art["entities"] = _extract_entities(art)
            art["image_url"] = _get_image(art)

        allowed.sort(key=lambda x: x["score"], reverse=True)
        top = allowed[:n]

        for i, art in enumerate(top, 1):
            logger.info(
                f"[{self.name}] #{i} +{art['score']} | "
                f"{art['entities']['category']} | "
                f"{art.get('source','?')} | "
                f"{'🖼️' if art.get('image_url') else '─'} | "
                f"{art.get('title','')[:55]}"
            )

        return top

    def get_best_article(self) -> dict | None:
        top = self.get_top_articles(n=1)
        return top[0] if top else None
