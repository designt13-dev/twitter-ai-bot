# src/agents/search_agent.py
"""
وكيل البحث والخوارزميات (Search & Algorithm Agent)
══════════════════════════════════════════════════════════════
المهام:
  1. جلب أخبار تقنية حقيقية من RSS بفلترة متقدمة
  2. تحليل الخوارزمية: تقييم قابلية التفاعل لكل خبر (Engagement Score)
  3. ترتيب الأخبار حسب نقاط التفاعل المتوقع
  4. استخراج الكيانات: اسم الأداة/الشركة/الشخصية
  5. تصنيف الأخبار في فئات (novelty / jobs / numbers / KSA-relevant)

معايير نقاط الخوارزمية:
  +4  : خبر عن إطلاق أداة/ميزة جديدة (novelty)
  +3  : خبر يمس الوظائف أو التعليم أو الصحة (KSA relevance)
  +3  : خبر فيه رقم أو إحصاء مميز (shareability)
  +2  : صدر خلال أقل من 24 ساعة (freshness)
  +2  : مصدر موثوق (MIT/VentureBeat/TechCrunch)
  +1  : يذكر شركة كبرى (OpenAI/Google/Meta/Apple/Microsoft/Samsung)
  -2  : مراجعة منتج فقط
  -2  : خبر تقني غير AI/ML (أجهزة، ألعاب، ترفيه)
  -3  : خبر أقدم من 48 ساعة
══════════════════════════════════════════════════════════════
"""
import re
import sys
import pathlib
from datetime import datetime, timedelta

import pytz

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from src.news_fetcher import fetch_articles, translate_to_arabic
from src.utils import logger, clean_text

# ── كلمات مفتاحية لتقييم الخوارزمية ──────────────────────────
NOVELTY_KEYWORDS = [
    "launch", "announce", "release", "introduce", "unveil", "debut",
    "new", "first", "breakthrough", "upgrade", "update", "feature",
    "إطلاق", "إعلان", "جديد", "أول", "طرح", "تحديث", "يستعرض",
]

JOB_KEYWORDS = [
    "job", "employment", "workforce", "career", "hire", "layoff",
    "replace", "automation", "worker", "salary", "skills",
    "وظيف", "عمل", "توظيف", "مهارات", "بطالة", "أتمتة", "مستقبل",
]

NUMBER_PATTERN = re.compile(
    r'\b(\d[\d,]*\.?\d*)\s*(%|billion|million|thousand|x faster|×|أضعاف|مليار|مليون|ألف|%)\b',
    re.IGNORECASE
)

KSA_KEYWORDS = [
    "saudi", "ksa", "riyadh", "vision 2030", "sdaia", "neom",
    "سعودي", "المملكة", "رياض", "رؤية", "2030", "نيوم", "sdaia",
    "تعليم", "صحة", "education", "health",
]

TRUSTED_SOURCES = [
    "MIT Technology Review", "VentureBeat AI", "TechCrunch",
    "The Verge", "Wired AI", "Ars Technica", "Analytics Vidhya",
]

BIG_COMPANIES = [
    "openai", "google", "deepmind", "meta", "apple", "microsoft",
    "amazon", "anthropic", "nvidia", "tesla", "sam altman",
    "elon musk", "sundar pichai",
]

REVIEW_KEYWORDS = [
    "review", "hands-on", "best buy", "should you buy", "price",
    "مراجعة", "سعر", "أفضل", "شراء",
]

NON_AI_PENALTY = [
    "game", "gaming", "movie", "series", "sport", "football",
    "puzzle", "crossword", "headphone", "speaker", "laptop review",
    "ألعاب", "مسلسل", "فيلم", "كرة", "سماعة", "ترفيه",
]


def _score_article(article: dict) -> int:
    """
    يحسب نقاط التفاعل المتوقع للخبر.
    كلما زادت النقاط كلما احتمال التفاعل أعلى.
    """
    score = 0
    title   = (article.get("title",   "") or "").lower()
    summary = (article.get("summary", "") or "").lower()
    text    = title + " " + summary
    source  = article.get("source",  "")

    # ── إيجابيات ─────────────────────────────────────────────
    if any(kw in text for kw in NOVELTY_KEYWORDS):
        score += 4

    if any(kw in text for kw in JOB_KEYWORDS):
        score += 3

    if NUMBER_PATTERN.search(title + " " + summary):
        score += 3

    if any(kw in text for kw in KSA_KEYWORDS):
        score += 3

    if any(s in source for s in TRUSTED_SOURCES):
        score += 2

    if any(co in text for co in BIG_COMPANIES):
        score += 1

    # ── تحقق من حداثة الخبر ─────────────────────────────────
    pub_date = article.get("published_parsed")
    if pub_date:
        try:
            riyadh = pytz.timezone("Asia/Riyadh")
            pub_dt = datetime(*pub_date[:6], tzinfo=pytz.utc).astimezone(riyadh)
            age_hours = (datetime.now(riyadh) - pub_dt).total_seconds() / 3600
            if age_hours < 24:
                score += 2
            elif age_hours > 48:
                score -= 3
        except Exception:
            pass

    # ── سلبيات ───────────────────────────────────────────────
    if any(kw in text for kw in REVIEW_KEYWORDS):
        score -= 2

    if any(kw in text for kw in NON_AI_PENALTY):
        score -= 2

    return score


def _extract_entities(article: dict) -> dict:
    """
    يستخرج الكيانات الرئيسية من الخبر:
    - اسم الأداة/المنتج
    - اسم الشركة
    - الأرقام المميزة
    - الفئة (novelty / jobs / risk / ksa / general)
    """
    title   = article.get("title",   "") or ""
    summary = article.get("summary", "") or ""
    text    = title + " " + summary
    t_lower = text.lower()

    # ── اسم الأداة ───────────────────────────────────────────
    ai_tools = [
        "ChatGPT", "GPT-4", "GPT-5", "o1", "o3", "o4",
        "Gemini", "Claude", "Grok", "Copilot", "Perplexity",
        "Mistral", "Llama", "DeepSeek", "Sora", "DALL-E",
        "Midjourney", "Stable Diffusion", "Runway",
    ]
    detected_tool = next(
        (t for t in ai_tools if t.lower() in t_lower), ""
    )

    # ── اسم الشركة ───────────────────────────────────────────
    companies = [
        "OpenAI", "Google", "DeepMind", "Meta", "Apple",
        "Microsoft", "Amazon", "Anthropic", "Nvidia", "Tesla",
        "Samsung", "Huawei", "xAI", "Mistral", "Cohere",
    ]
    detected_company = next(
        (c for c in companies if c.lower() in t_lower), ""
    )

    # ── الأرقام المميزة ──────────────────────────────────────
    numbers_found = NUMBER_PATTERN.findall(text)
    key_number = f"{numbers_found[0][0]}{numbers_found[0][1]}" if numbers_found else ""

    # ── تصنيف الخبر ─────────────────────────────────────────
    if any(kw in t_lower for kw in NOVELTY_KEYWORDS[:8]):
        category = "novelty"
    elif any(kw in t_lower for kw in JOB_KEYWORDS[:5]):
        category = "jobs"
    elif any(kw in t_lower for kw in KSA_KEYWORDS[:5]):
        category = "ksa"
    elif "risk" in t_lower or "danger" in t_lower or "threat" in t_lower:
        category = "risk"
    else:
        category = "general"

    return {
        "tool":     detected_tool,
        "company":  detected_company,
        "number":   key_number,
        "category": category,
    }


def _filter_ai_only(articles: list) -> list:
    """
    يُبقي فقط الأخبار المرتبطة بالذكاء الاصطناعي والتقنية الجوهرية.
    يُزيل: رياضة، ترفيه، ألعاب، مراجعات أجهزة خالصة.
    """
    AI_MUST_HAVE = [
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "neural", "llm", "gpt", "gemini", "claude", "llama", "chatbot",
        "automation", "robot", "algorithm", "model", "data science",
        "openai", "google ai", "microsoft ai", "meta ai", "deepmind",
        "ذكاء اصطناعي", "تعلم آلي", "نموذج لغوي", "روبوت",
    ]
    result = []
    for art in articles:
        title   = (art.get("title",   "") or "").lower()
        summary = (art.get("summary", "") or "").lower()
        combined = title + " " + summary
        if any(kw in combined for kw in AI_MUST_HAVE):
            result.append(art)
    return result


class SearchAgent:
    """
    وكيل البحث والخوارزميات.
    الاستخدام:
        agent = SearchAgent()
        articles = agent.get_top_articles(n=8)
    """

    def __init__(self):
        self.name = "SearchAgent"

    def get_top_articles(self, n: int = 8) -> list:
        """
        يُعيد أفضل n خبر مرتبة حسب نقاط الخوارزمية.
        كل خبر يحمل:
          - score: نقاط التفاعل المتوقع
          - entities: كيانات مستخرجة (tool, company, number, category)
          - title, summary, link, image_url, source
        """
        logger.info(f"[{self.name}] 🔍 جلب الأخبار...")
        raw_articles = fetch_articles()

        # ── فلترة AI فقط ────────────────────────────────────
        ai_articles = _filter_ai_only(raw_articles)
        logger.info(
            f"[{self.name}] المجموع: {len(raw_articles)} | "
            f"AI فقط: {len(ai_articles)}"
        )

        # ── تقييم كل خبر ────────────────────────────────────
        scored = []
        for art in ai_articles:
            score    = _score_article(art)
            entities = _extract_entities(art)
            art["score"]    = score
            art["entities"] = entities
            scored.append(art)

        # ── ترتيب تنازلي حسب النقاط ─────────────────────────
        scored.sort(key=lambda x: x["score"], reverse=True)

        top = scored[:n]
        for i, art in enumerate(top, 1):
            logger.info(
                f"[{self.name}] #{i} نقاط={art['score']:+d} | "
                f"فئة={art['entities']['category']} | "
                f"{art.get('source','?')} | {art.get('title','')[:60]}"
            )

        return top

    def get_best_article(self) -> dict | None:
        """يُعيد الخبر الأفضل نقاطًا"""
        top = self.get_top_articles(n=1)
        return top[0] if top else None
