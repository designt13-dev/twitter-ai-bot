# config/settings.py
import os
import pathlib
from dotenv import load_dotenv

load_dotenv()

# ── بيانات API ──────────────────────────────────────────────
CONSUMER_KEY         = os.getenv("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET      = os.getenv("TWITTER_CONSUMER_SECRET")
ACCESS_TOKEN         = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET  = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
BEARER_TOKEN         = os.getenv("TWITTER_BEARER_TOKEN")
CLIENT_SECRET        = os.getenv("TWITTER_CLIENT_SECRET")
OPENAI_KEY           = os.getenv("OPENAI_API_KEY", "")

# ── المنطقة الزمنية ─────────────────────────────────────────
TIMEZONE = "Asia/Riyadh"

# ── إعدادات النشر اليومي ────────────────────────────────────
# توقيت النشر بـ UTC (السعودية UTC+3)
POST_TIMES_UTC = [
    "06:00",   # 9:00 ص  الرياض
    "09:30",   # 12:30 م الرياض
    "13:00",   # 4:00 م  الرياض
    "17:00",   # 8:00 م  الرياض
    "19:30",   # 10:30 م الرياض
]

DAILY_POST_COUNT     = 5
REPLY_COUNT_PER_RUN  = 5    # ردود لكل تشغيل
REPLY_RUNS_PER_DAY   = 3    # تشغيلات يوميًا → 15 رد/يوم

# ── هاشتاقات البحث للردود (للبحث فقط — لا تُضاف للمنشورات) ─
SEARCH_HASHTAGS = [
    "#ذكاء_اصطناعي",
    "#AI",
    "#تقنية",
    "#رؤية2030",
    "#ChatGPT",
    "#تحول_رقمي",
    "#ابتكار",
    "#مستقبل_التقنية",
    "#SDAIA",
]

# ── مصادر RSS الموثوقة ───────────────────────────────────────
RSS_SOURCES = [
    {
        "name": "MIT Technology Review",
        "url":  "https://www.technologyreview.com/feed/",
        "lang": "en",
    },
    {
        "name": "VentureBeat AI",
        "url":  "https://venturebeat.com/category/ai/feed/",
        "lang": "en",
    },
    {
        "name": "The Verge AI",
        "url":  "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "lang": "en",
    },
    {
        "name": "Wired AI",
        "url":  "https://www.wired.com/feed/tag/artificial-intelligence/rss",
        "lang": "en",
    },
    {
        "name": "TechCrunch AI",
        "url":  "https://techcrunch.com/category/artificial-intelligence/feed/",
        "lang": "en",
    },
    {
        "name": "ZDNET AI",
        "url":  "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",
        "lang": "en",
    },
    {
        "name": "Ars Technica AI",
        "url":  "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "lang": "en",
    },
    {
        "name": "TechRadar AI",
        "url":  "https://www.techradar.com/feeds/articletype/news",
        "lang": "en",
    },
]

# ── كلمات محظورة ────────────────────────────────────────────
BLOCKED_KEYWORDS = [
    # عسكري / دفاع
    "military", "defense", "defence", "weapon", "warfare",
    "missile", "drone strike", "pentagon", "nato", "army",
    "soldier", "combat", "war", "battlefield",
    "عسكري", "دفاع", "سلاح", "حرب", "وزارة الدفاع",
    # أحزاب وسياسة
    "republican", "democrat", "حزب", "انتخابات", "مرشح",
    # دول حساسة
    "iran", "north korea", "russia hacker",
    # محتوى حساس
    "exploit", "deepfake porn", "surveillance state",
]

# ── مسارات الملفات ───────────────────────────────────────────
BASE_DIR         = pathlib.Path(__file__).parent.parent
CONTENT_DIR      = BASE_DIR / "content"
TWEETS_POOL_FILE = CONTENT_DIR / "tweets_pool.json"
THREADS_FILE     = CONTENT_DIR / "threads.json"
USED_TWEETS_FILE = CONTENT_DIR / "used_tweets.json"
LOGS_DIR         = BASE_DIR / "logs"
