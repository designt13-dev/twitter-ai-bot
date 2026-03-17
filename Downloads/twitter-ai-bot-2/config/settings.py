# config/settings.py — v6 (AI + فنون + اكتشافات، بدون رياضة)
import os
import pathlib
from dotenv import load_dotenv

load_dotenv()

# ── بيانات API ──────────────────────────────────────────────────
CONSUMER_KEY        = os.getenv("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET     = os.getenv("TWITTER_CONSUMER_SECRET")
ACCESS_TOKEN        = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
BEARER_TOKEN        = os.getenv("TWITTER_BEARER_TOKEN")
CLIENT_SECRET       = os.getenv("TWITTER_CLIENT_SECRET")
OPENAI_KEY          = os.getenv("OPENAI_API_KEY", "")

# ── المنطقة الزمنية ─────────────────────────────────────────────
TIMEZONE = "Asia/Riyadh"

# ── إعدادات النشر اليومي ────────────────────────────────────────
DAILY_POST_COUNT    = 16   # 16 تغريدة يومياً
REPLY_COUNT_PER_RUN = 7    # ردود لكل تشغيل
REPLY_RUNS_PER_DAY  = 3    # تشغيلات يومياً → 21 رد/يوم

# ── هاشتاقات البحث للردود ─────────────────────────────────────
SEARCH_HASHTAGS = [
    "#ذكاء_اصطناعي", "#AI", "#تقنية", "#رؤية2030",
    "#ChatGPT", "#تحول_رقمي", "#ابتكار", "#مستقبل_التقنية",
    "#SDAIA", "#التقنية", "#ريادة_الأعمال",
]

# ══════════════════════════════════════════════════════════════════
# مصادر RSS — ثلاثة محاور: AI + فنون + اكتشافات
# ══════════════════════════════════════════════════════════════════
RSS_SOURCES = [

    # ── المحور الأول: الذكاء الاصطناعي ──────────────────────────
    {"name": "OpenAI Blog",           "url": "https://openai.com/news/rss.xml"},
    {"name": "Google AI Blog",        "url": "https://blog.research.google/feeds/posts/default"},
    {"name": "DeepMind Blog",         "url": "https://deepmind.google/blog/rss.xml"},
    {"name": "Hugging Face Blog",     "url": "https://huggingface.co/blog/feed.xml"},
    {"name": "Anthropic News",        "url": "https://www.anthropic.com/rss.xml"},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/"},
    {"name": "VentureBeat AI",        "url": "https://venturebeat.com/category/ai/feed/"},
    {"name": "TechCrunch AI",         "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "The Verge AI",          "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"name": "Wired AI",              "url": "https://www.wired.com/feed/tag/artificial-intelligence/rss"},
    {"name": "Ars Technica Tech",     "url": "https://feeds.arstechnica.com/arstechnica/technology-lab"},
    {"name": "IEEE Spectrum AI",      "url": "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss"},
    {"name": "AI News",               "url": "https://www.artificialintelligence-news.com/feed/"},
    {"name": "InfoQ AI",              "url": "https://feed.infoq.com/InfoQ/ai-ml-data-eng"},

    # ── المحور الثاني: الفنون والثقافة العالمية ──────────────────
    {"name": "Hyperallergic",         "url": "https://hyperallergic.com/feed/"},
    {"name": "Artsy News",            "url": "https://www.artsy.net/rss/news"},
    {"name": "Dezeen",                "url": "https://www.dezeen.com/feed/"},
    {"name": "Colossal",              "url": "https://www.thisiscolossal.com/feed/"},
    {"name": "Creative Boom",         "url": "https://www.creativeboom.com/feed/"},
    {"name": "It's Nice That",        "url": "https://www.itsnicethat.com/rss"},
    {"name": "The Art Newspaper",     "url": "https://www.theartnewspaper.com/feed"},

    # ── المحور الثالث: الاكتشافات والعلوم ───────────────────────
    {"name": "Science News",          "url": "https://www.sciencenews.org/feed"},
    {"name": "New Scientist",         "url": "https://www.newscientist.com/feed/home/"},
    {"name": "National Geographic",   "url": "https://www.nationalgeographic.com/pages/topic/rss"},
    {"name": "Scientific American",   "url": "https://rss.sciam.com/ScientificAmerican-Global"},
    {"name": "NASA News",             "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss"},
    {"name": "Phys.org",              "url": "https://phys.org/rss-feed/"},
]

# ══════════════════════════════════════════════════════════════════
# كلمات محظورة — فلتر صارم
# ══════════════════════════════════════════════════════════════════
BLOCKED_KEYWORDS = [
    # ── رياضة (كاملة) ───────────────────────────────────────────
    "football", "soccer", "basketball", "nba", "nfl", "nhl", "mlb",
    "cricket", "tennis", "golf", "rugby", "hockey", "boxing",
    "formula 1", "f1", "esports", "t20", "world cup", "premier league",
    "champions league", "la liga", "bundesliga", "serie a", "ligue 1",
    "fifa", "uefa", "nba finals", "super bowl", "wimbledon",
    "كرة قدم", "كرة سلة", "كرة", "دوري أبطال", "دوري",
    "كأس العالم", "رياضة", "لاعب", "مباراة", "ملعب",

    # ── ترفيه وألعاب ────────────────────────────────────────────
    "wordle", "crossword", "puzzle answer", "game hints", "quiz",
    "connections answers", "nyt connections", "connections hints",
    "movie", "film", "tv show", "series", "netflix", "disney+",
    "hbo", "streaming", "episode", "season", "trailer", "box office",
    "فيلم", "مسلسل", "حلقة", "مشاهدة",

    # ── عروض تجارية ─────────────────────────────────────────────
    "best buy", "deal of the day", "discount", "promo code",
    "coupon", "gift card", "sale price", "buying guide",
    "best laptop", "best phone", "best headphone",
    "should you buy", "vs review", "calendar review",

    # ── عسكري / سياسي ───────────────────────────────────────────
    "military", "defense", "defence", "weapon", "warfare",
    "missile", "drone strike", "pentagon", "nato", "army",
    "soldier", "combat", "battlefield", "war crimes",
    "republican", "democrat", "election", "ballot", "campaign ad",
    "حرب", "عسكري", "دفاع", "سلاح", "انتخابات", "حزب",

    # ── محتوى حساس ──────────────────────────────────────────────
    "exploit", "deepfake porn", "surveillance state",
    "iran", "north korea", "russia hacker",
]

# ── مسارات الملفات ───────────────────────────────────────────────
BASE_DIR         = pathlib.Path(__file__).parent.parent
CONTENT_DIR      = BASE_DIR / "content"
TWEETS_POOL_FILE = CONTENT_DIR / "tweets_pool.json"
THREADS_FILE     = CONTENT_DIR / "threads.json"
USED_TWEETS_FILE = CONTENT_DIR / "used_tweets.json"
LOGS_DIR         = BASE_DIR / "logs"
