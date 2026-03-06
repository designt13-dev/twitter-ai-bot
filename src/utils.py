# src/utils.py
"""
أدوات مساعدة عامة للمشروع — نسخة مُحسّنة
"""
import json
import logging
import random
import re
import pathlib
from datetime import datetime
import pytz

import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from config.settings import TIMEZONE, LOGS_DIR, USED_TWEETS_FILE

# ── إعداد الـ Logger ─────────────────────────────────────────
LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("AIBot")


# ── الوقت الحالي بتوقيت الرياض ──────────────────────────────
def now_riyadh() -> datetime:
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz)


def today_str() -> str:
    return now_riyadh().strftime("%Y-%m-%d")


# ── تحميل / حفظ JSON ─────────────────────────────────────────
def load_json(path: pathlib.Path) -> dict | list:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: pathlib.Path, data: dict | list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── إدارة التغريدات المستخدمة ────────────────────────────────
def load_used() -> dict:
    data = load_json(USED_TWEETS_FILE)
    if not isinstance(data, dict):
        return {}
    return data


def mark_used(tweet_id: str) -> None:
    used = load_used()
    used[tweet_id] = today_str()
    save_json(USED_TWEETS_FILE, used)


def is_used(tweet_id: str) -> bool:
    used = load_used()
    return tweet_id in used


def clean_old_used(days: int = 30) -> None:
    used = load_used()
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).date()
    cleaned = {
        k: v for k, v in used.items()
        if (today - datetime.strptime(v, "%Y-%m-%d").date()).days <= days
    }
    save_json(USED_TWEETS_FILE, cleaned)


# ── اختيار هاشتاقات عشوائية ─────────────────────────────────
def pick_hashtags(pool: list, count: int = 3) -> str:
    selected = random.sample(pool, min(count, len(pool)))
    return " ".join(selected)


# ── تنظيف النص ───────────────────────────────────────────────
def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ── حساب طول التغريدة بدقة (Twitter يحسب URLs كـ 23 حرفًا) ──
def tweet_length(text: str) -> int:
    # استبدل كل URL بـ 23 حرفًا
    url_pattern = re.compile(r'https?://\S+')
    urls = url_pattern.findall(text)
    length = len(text)
    for url in urls:
        length = length - len(url) + 23
    return length


# ── ✅ القطع الذكي عند حدود الكلمات ─────────────────────────
def smart_truncate(text: str, limit: int = 270) -> str:
    """
    يقطع النص عند حد الأحرف لكن:
    1. يحترم حدود الكلمات (لا يقطع في منتصف كلمة)
    2. يحترم نهايات الأسطر
    3. لا يُضيف "..." إلا إذا كان هناك محتوى محذوف فعلًا
    """
    if tweet_length(text) <= limit:
        return text

    # قطع عند حد الأحرف الآمن
    safe_limit = limit - 3  # مساحة لـ "..."

    # محاولة القطع عند آخر سطر جديد قبل الحد
    newline_pos = text.rfind('\n', 0, safe_limit)
    if newline_pos > safe_limit * 0.6:  # إذا كان السطر قريبًا من الحد
        return text[:newline_pos].rstrip() + "…"

    # قطع عند آخر مسافة قبل الحد
    space_pos = text.rfind(' ', 0, safe_limit)
    if space_pos > safe_limit * 0.5:
        return text[:space_pos].rstrip() + "…"

    # قطع عند آخر علامة ترقيم (. ، ! ؟)
    for punct in ['؟', '!', '.', '،', '،']:
        punct_pos = text.rfind(punct, 0, safe_limit)
        if punct_pos > safe_limit * 0.4:
            return text[:punct_pos + 1].rstrip() + "…"

    # آخر حل: قطع مباشر
    return text[:safe_limit].rstrip() + "…"


# للتوافق مع الكود القديم
def truncate_tweet(text: str, limit: int = 270) -> str:
    return smart_truncate(text, limit)


def fits_tweet(text: str, limit: int = 280) -> bool:
    return tweet_length(text) <= limit


# ── ✅ تقسيم النص الطويل إلى تغريدات متعددة ─────────────────
def split_into_tweets(text: str, limit: int = 270) -> list[str]:
    """
    يُقسّم النص الطويل إلى تغريدات متعددة بشكل ذكي:
    - يقطع عند نهايات الجمل
    - لا يقطع الكلمات
    - يُضيف ترقيم (1/N) تلقائيًا
    """
    if tweet_length(text) <= limit:
        return [text]

    parts = []
    current = ""

    # قسّم على الأسطر أولًا
    lines = text.split('\n')

    for line in lines:
        test = (current + '\n' + line).strip() if current else line

        if tweet_length(test) <= limit - 10:  # -10 للترقيم لاحقًا
            current = test
        else:
            if current:
                parts.append(current.strip())
            current = line

    if current.strip():
        parts.append(current.strip())

    # أضف ترقيم (1/N)
    total = len(parts)
    if total > 1:
        parts = [f"{p}\n{i+1}/{total}" for i, p in enumerate(parts)]

    return parts


# ── أنماط تساؤلات تفاعلية ───────────────────────────────────
INTERACTIVE_QUESTIONS = [
    "ما رأيك؟ 💬",
    "هل جربته من قبل؟ 🤔",
    "شاركنا تجربتك 👇",
    "ماذا تتوقع بعد؟ 🔮",
    "هل أنت مستعد لهذا التحول؟ 🚀",
    "كيف سيؤثر هذا على مجالك؟ 💡",
    "ما هو تقييمك؟ ⭐",
    "هل وظّفته في عملك؟ 💼",
    "أيهما تفضّل؟ خبّرنا 👇",
    "ما أكثر ما يثير اهتمامك فيه؟ 🌟",
    "رأيك يهمنا 🎯",
    "ما توقعاتك لعام 2025؟ 📅",
    "هل يستخدمه منشأتك؟ 🏢",
]

def random_question() -> str:
    return random.choice(INTERACTIVE_QUESTIONS)


# ── أنماط افتتاحية متنوعة ────────────────────────────────────
OPENERS = [
    "🔵 خبر تقني:",
    "💡 هل تعلم؟",
    "🚀 جديد في عالم الذكاء الاصطناعي:",
    "⚡ لحظة تقنية:",
    "🌐 من عالم AI:",
    "🎯 تقنية تستحق انتباهك:",
    "🔍 اكتشاف جديد:",
    "📌 ملاحظة تقنية مهمة:",
    "🤖 الذكاء الاصطناعي اليوم:",
    "✨ ابتكار لافت:",
    "📊 إحصائية تستوقفك:",
    "🧠 فكرة تقنية:",
]

def random_opener() -> str:
    return random.choice(OPENERS)
