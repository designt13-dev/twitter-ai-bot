# src/content_generator.py
"""
توليد المحتوى — النسخة الجذرية الجديدة
═══════════════════════════════════════════════════════════════
النمط المستهدف (مثال من المستخدم):
─────────────────────────────────
🔴 تخيل تكتب رسالة أو مقال كامل... بدون ما تلمس الكيبورد!

تم إطلاق تطبيق Wispr Flow على أندرويد في فبراير 2026،
وهو تطبيق يعتمد على الذكاء الاصطناعي لتحويل الكلام إلى نص.

الفكرة بسيطة:
🎤 تتكلم فقط
🧠 الذكاء الاصطناعي يفهم كلامك
🤝 ويحوّله مباشرة إلى نص مرتب

[سياق/خلفية]
═══════════════════════════════════════════════════════════════
القواعد:
✅ بحث + توليد ديناميكي — لا محتوى محفوظ
✅ بدون هاشتاقات
✅ بدون ثريدات (مُوقفة مؤقتًا)
✅ طول مضبوط من البداية (لا قطع)
✅ كل تغريدة مع صورة إن وُجدت
"""
import random
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.utils import logger, tweet_length, clean_text
from src.news_fetcher import translate_to_arabic, get_random_article


# ══════════════════════════════════════════════════════════════
#  الإيموجيات الافتتاحية — متنوعة وجذابة
# ══════════════════════════════════════════════════════════════
HOOK_EMOJIS = [
    "🔴", "🚨", "⚡", "🔥", "💡", "🎯", "🌟", "🤯",
    "👀", "📌", "🔵", "💥", "🚀", "🧠", "✨", "🎪",
]

# ── جمل Hook افتتاحية — تُعدَّل لاحقًا بناءً على موضوع الخبر ──
HOOKS = [
    "تخيل {} ... بدون ما يكلفك كثير!",
    "{} — والقصة أكبر مما تعتقد.",
    "أخبار {} تستحق أن تقف عندها.",
    "شيء جديد في عالم {} يستحق انتباهك.",
    "هل سمعت بـ {}؟ القصة مثيرة.",
    "تطور كبير في {} — اقرأ التفاصيل.",
    "{} يغيّر قواعد اللعبة من جديد.",
    "ما حدث في {} هذا الأسبوع مهم جدًا.",
    "خبر {} يفتح نقاشًا حقيقيًا.",
    "إذا تابعت {} فهذا يعنيك.",
]

# ── عبارات تقديم الفكرة ──────────────────────────────────────
IDEA_INTROS = [
    "الفكرة بسيطة:",
    "ما يحدث بالضبط:",
    "التفاصيل المهمة:",
    "لماذا هذا مهم:",
    "الصورة الكاملة:",
    "ما يميّزه:",
]

# ── إيموجيات للنقاط ──────────────────────────────────────────
POINT_EMOJIS = [
    ["🎤", "🧠", "🤝"],
    ["📌", "⚙️", "🎯"],
    ["🔹", "🔸", "✅"],
    ["1️⃣", "2️⃣", "3️⃣"],
    ["🔵", "🟡", "🟢"],
    ["💡", "⚡", "🚀"],
    ["📊", "🔍", "💬"],
]

# ── أسئلة تفاعلية نهائية ────────────────────────────────────
CLOSING_QUESTIONS = [
    "هل تستخدمه أو تفكر في تجربته؟",
    "ما رأيك — هل سيُغيّر طريقة عملنا؟",
    "هل تتوقع أن يصل للسوق السعودي قريبًا؟",
    "كيف تقيّم هذا التطور؟",
    "هل أنت مستعد لهذا التحول؟",
    "ما الذي يثير اهتمامك أكثر في هذا؟",
    "هل جربت شيئًا مشابهًا؟ شاركنا.",
    "ما تأثيره على مجالك؟",
]

# ── عبارات السياق السعودي/المحلي (اختيارية) ─────────────────
LOCAL_NOTES = [
    "يستحق المتابعة خاصة مع توجهات رؤية 2030.",
    "السوق السعودي من الأكثر استعدادًا لتبني هذا النوع من الحلول.",
    "التطبيق بدأ خارجيًا — لكنه قادم لمنطقتنا حتمًا.",
    "شركات التقنية المحلية بدأت تسير بنفس الاتجاه.",
    "مبادرات SDAIA تهيئ البيئة لهذا النوع من التحول.",
]


# ══════════════════════════════════════════════════════════════
#  الدالة الجوهرية — بناء التغريدة الإبداعية
# ══════════════════════════════════════════════════════════════
def build_creative_tweet(article: dict) -> str:
    """
    يبني تغريدة إبداعية كاملة من مقالة حقيقية.
    النمط: hook → اسم + حدث → فكرة بسيطة → نقاط → سؤال
    الضمان: الطول ≤ 270 حرف من البداية (لا قطع)
    """
    title_en   = article.get("title",   "")
    summary_en = article.get("summary", "")[:200]
    source     = article.get("source",  "")

    # ── ترجمة ───────────────────────────────────────────────
    title_ar   = translate_to_arabic(title_en,   max_len=120)
    summary_ar = translate_to_arabic(summary_en, max_len=200) if summary_en else ""

    title_ar   = clean_text(title_ar)
    summary_ar = clean_text(summary_ar)

    # ── اختيار العناصر البصرية ──────────────────────────────
    emoji      = random.choice(HOOK_EMOJIS)
    idea_intro = random.choice(IDEA_INTROS)
    p_emojis   = random.choice(POINT_EMOJIS)
    question   = random.choice(CLOSING_QUESTIONS)
    add_local  = random.random() < 0.35  # 35% يضيف ملاحظة محلية

    # ── تقسيم الملخص لنقاط ──────────────────────────────────
    points = _extract_points(summary_ar, title_ar)

    # ══════════════════════════════════════════════════════════
    # نحاول بناء التغريدة بمستويات تفصيل متدرجة
    # حتى نصل لنص كامل ≤ 270 حرف
    # ══════════════════════════════════════════════════════════

    # المستوى 1 — كامل مع نقاط + سؤال + ملاحظة محلية
    if add_local and points and len(points) >= 2:
        local = random.choice(LOCAL_NOTES)
        tweet = (
            f"{emoji} {title_ar}\n\n"
            f"{idea_intro}\n"
            f"{p_emojis[0]} {points[0]}\n"
            f"{p_emojis[1]} {points[1]}\n\n"
            f"{local}\n\n"
            f"{question}"
        )
        if tweet_length(tweet) <= 270:
            return tweet

    # المستوى 2 — كامل مع نقاط + سؤال (بدون ملاحظة محلية)
    if points and len(points) >= 2:
        tweet = (
            f"{emoji} {title_ar}\n\n"
            f"{idea_intro}\n"
            f"{p_emojis[0]} {points[0]}\n"
            f"{p_emojis[1]} {points[1]}\n\n"
            f"{question}"
        )
        if tweet_length(tweet) <= 270:
            return tweet

    # المستوى 3 — مع نقطة واحدة + سؤال
    if points:
        tweet = (
            f"{emoji} {title_ar}\n\n"
            f"{p_emojis[0]} {points[0]}\n\n"
            f"{question}"
        )
        if tweet_length(tweet) <= 270:
            return tweet

    # المستوى 4 — عنوان فقط + سؤال
    tweet = f"{emoji} {title_ar}\n\n{question}"
    if tweet_length(tweet) <= 270:
        return tweet

    # المستوى 5 — عنوان مُقلَّص + سؤال قصير
    short_title = _shorten_to(title_ar, 180)
    short_q     = "ما رأيك؟"
    return f"{emoji} {short_title}\n\n{short_q}"


def _extract_points(summary_ar: str, title_ar: str) -> list[str]:
    """
    يستخرج 2-3 نقاط قصيرة من الملخص
    كل نقطة ≤ 50 حرفًا
    """
    if not summary_ar:
        return []

    # قسّم على الجمل
    sentences = re.split(r'[.،؟!]\s*', summary_ar)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    points = []
    for sent in sentences[:4]:
        short = _shorten_to(sent, 55)
        if short and len(short) > 5:
            points.append(short)
        if len(points) >= 2:
            break

    return points


def _shorten_to(text: str, limit: int) -> str:
    """اختصار النص عند آخر مسافة دون تجاوز الحد"""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(' ')
    if space > limit * 0.6:
        return cut[:space]
    return cut


# ══════════════════════════════════════════════════════════════
#  تحليل موضوع الخبر لاختيار hook مناسب
# ══════════════════════════════════════════════════════════════
import re

TOPIC_MAP = {
    "openai":     "OpenAI",
    "chatgpt":    "ChatGPT",
    "gemini":     "Gemini",
    "claude":     "Claude",
    "grok":       "Grok",
    "llm":        "نماذج اللغة الكبيرة",
    "robot":      "الروبوتات",
    "autonomous": "السيارات ذاتية القيادة",
    "investment": "الاستثمار التقني",
    "startup":    "الشركات الناشئة",
    "chip":       "الرقائق الإلكترونية",
    "nvidia":     "Nvidia",
    "microsoft":  "Microsoft",
    "google":     "Google",
    "apple":      "Apple",
    "meta":       "Meta",
    "amazon":     "Amazon",
    "healthcare": "الذكاء الاصطناعي الطبي",
    "education":  "التعليم الذكي",
    "finance":    "التقنية المالية",
    "security":   "الأمن الرقمي",
    "vision":     "الرؤية الحاسوبية",
    "voice":      "الصوت والتحدث",
    "image":      "توليد الصور",
    "video":      "توليد الفيديو",
    "agent":      "وكلاء الذكاء الاصطناعي",
    "model":      "النماذج الجديدة",
}


def _extract_topic(title_en: str) -> str:
    title_lower = title_en.lower()
    for key, val in TOPIC_MAP.items():
        if key in title_lower:
            return val
    return "الذكاء الاصطناعي"


# ══════════════════════════════════════════════════════════════
#  الدالة الرئيسية
# ══════════════════════════════════════════════════════════════
def generate_tweet() -> dict:
    """
    يُعيد: {type, text, is_thread, thread_tweets, image_url}
    ─────────────────────────────────────────────────────────
    100% أخبار حقيقية — لا محتوى محفوظ — لا ثريدات
    """
    article = get_random_article()

    if not article:
        logger.error("[Content] ❌ لم يُعثر على مقالة — fallback")
        fallback = (
            "🔴 لحظة تقنية تستحق التوقف عندها!\n\n"
            "عالم الذكاء الاصطناعي يتحرك بسرعة لا تتوقف — "
            "كل يوم هناك شيء جديد يستحق المتابعة.\n\n"
            "ما آخر خبر تقني لفت انتباهك هذا الأسبوع؟"
        )
        return {
            "type": "fallback",
            "text": fallback,
            "is_thread": False,
            "thread_tweets": [],
            "image_url": None,
        }

    text = build_creative_tweet(article)
    length = tweet_length(text)

    logger.info(
        f"[Content] ✅ تغريدة إبداعية | الطول: {length} | "
        f"صورة: {'✅' if article.get('image_url') else '❌'} | "
        f"المصدر: {article.get('source', '?')}"
    )

    return {
        "type": "news",
        "text": text,
        "is_thread": False,
        "thread_tweets": [],
        "image_url": article.get("image_url"),
    }


def generate_tweets_batch(n: int = 5) -> list[dict]:
    """توليد دفعة من التغريدات اليومية (5 تغريدات)"""
    from src.news_fetcher import get_articles_batch
    articles = get_articles_batch(n)

    results = []
    for article in articles:
        text   = build_creative_tweet(article)
        length = tweet_length(text)
        logger.info(
            f"[Batch] تغريدة {len(results)+1}/{n} | "
            f"الطول: {length} | "
            f"المصدر: {article.get('source','?')}"
        )
        results.append({
            "type": "news",
            "text": text,
            "is_thread": False,
            "thread_tweets": [],
            "image_url": article.get("image_url"),
        })

    return results
