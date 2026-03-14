# src/agents/engage_agent.py
"""
وكيل التفاعل مع أفضل الحسابات التقنية (Engagement Agent)
══════════════════════════════════════════════════════════════
المهام:
  1. اكتشاف أفضل 10 حسابات تتداول أخبار تقنية/AI بالعربية
  2. تحليل كل حساب: معدل النشر، نوع المحتوى، التفاعل المتوسط
  3. التفاعل مع تغريداتهم بلغة تحليلية عميقة — لا كلام مبهم
  4. بناء علاقة حقيقية: تعليقات تُضيف قيمة تقنية حقيقية
  5. حفظ قاعدة بيانات الحسابات المكتشفة وتحديثها دورياً

أسلوب التفاعل:
  ✅ لغة تحليلية سعودية ("لاحظت في نتائج X أن...")
  ✅ إضافة معلومة إضافية أو زاوية مختلفة
  ✅ سؤال تقني حقيقي يستفز التفكير
  ✅ الإشارة لتفاصيل من محتواهم (يظهر أننا قرأنا فعلاً)
  ❌ لا "رائع"، لا "ممتاز"، لا كلام فارغ
  ❌ لا تبعية — رد كـ نظير متخصص
══════════════════════════════════════════════════════════════
"""
import re
import json
import random
import time
import sys
import pathlib

import tweepy

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from config.settings import (
    CONSUMER_KEY, CONSUMER_SECRET,
    ACCESS_TOKEN, ACCESS_TOKEN_SECRET,
    BEARER_TOKEN, LOGS_DIR,
)
from src.utils import logger, load_json, save_json, now_riyadh, tweet_length

# ── ملف قاعدة بيانات الحسابات ────────────────────────────────
ACCOUNTS_FILE = LOGS_DIR / "top_accounts.json"
ENGAGED_FILE  = LOGS_DIR / "engaged_tweets.json"

# ══════════════════════════════════════════════════════════════
#  قاعدة الحسابات الأولية (تُحدَّث تلقائياً)
# ══════════════════════════════════════════════════════════════
# حسابات AI/Tech عربية وسعودية مقترحة للبداية
SEED_ACCOUNTS = [
    # حسابات تقنية/AI عربية بارزة (بدون @)
    "Saudi_SDAIA",
    "futurism",
    "sama_gov_sa",
    "kacst",
    "ai_in_arabic",
]

# كلمات مفتاحية البحث عن حسابات تقنية
TECH_ACCOUNT_QUERIES = [
    "#ذكاء_اصطناعي -is:retweet lang:ar",
    "#AI -is:retweet lang:ar",
    "#ChatGPT -is:retweet lang:ar",
    "#تقنية -is:retweet lang:ar min_faves:50",
    "#التحول_الرقمي -is:retweet lang:ar min_faves:30",
]


# ══════════════════════════════════════════════════════════════
#  تحليل مستوى المحتوى التقني في التغريدة
# ══════════════════════════════════════════════════════════════
def _analyze_content_depth(tweet_text: str) -> dict:
    """
    يحدد عمق المحتوى التقني في التغريدة لاختيار نوع التعليق المناسب.
    """
    t = tweet_text.lower()

    # ── مؤشرات المحتوى العميق ────────────────────────────────
    DEEP_SIGNALS = [
        "دراسة", "بحث", "نتائج", "إحصاء", "%", "مليار", "مليون",
        "خوارزمية", "نموذج", "بيانات", "دقة", "أداء", "معمارية",
        "study", "research", "results", "paper", "accuracy",
        "benchmark", "performance", "parameter", "training",
    ]

    # ── مؤشرات الأخبار الجديدة ───────────────────────────────
    NEWS_SIGNALS = [
        "أعلنت", "كشفت", "طرحت", "أطلقت", "تطلق", "جديد", "أول",
        "announced", "launched", "released", "new", "first",
    ]

    # ── مؤشرات الرأي والتحليل ────────────────────────────────
    OPINION_SIGNALS = [
        "أعتقد", "رأيي", "تقييمي", "من وجهة نظري", "أرى",
        "i think", "in my opinion", "my take",
    ]

    has_deep    = any(s in t for s in DEEP_SIGNALS)
    has_news    = any(s in t for s in NEWS_SIGNALS)
    has_opinion = any(s in t for s in OPINION_SIGNALS)
    has_number  = bool(re.search(r'\d+', tweet_text))

    if has_deep and has_number:
        content_type = "analytical"
    elif has_news:
        content_type = "news"
    elif has_opinion:
        content_type = "opinion"
    else:
        content_type = "general"

    # استخراج أداة/شركة مذكورة
    AI_ENTITIES = [
        "ChatGPT", "GPT-4", "GPT-5", "Gemini", "Claude", "Grok",
        "Copilot", "OpenAI", "Google", "Meta", "Anthropic", "Nvidia",
        "DeepSeek", "Llama", "Mistral", "Sora", "DALL-E",
    ]
    entity = next(
        (e for e in AI_ENTITIES if e.lower() in t), ""
    )

    return {
        "content_type": content_type,
        "entity":       entity,
        "has_number":   has_number,
        "has_deep":     has_deep,
    }


# ══════════════════════════════════════════════════════════════
#  بناء تعليق تحليلي عميق (لا كلام مبهم)
# ══════════════════════════════════════════════════════════════
def build_analytical_comment(tweet_text: str, author_name: str = "") -> str:
    """
    يبني تعليقاً تحليلياً عميقاً يُضيف قيمة حقيقية.
    يختلف عن الردود العادية: يُشير لتفاصيل محددة من المحتوى
    ويُضيف زاوية تحليلية غير مذكورة.
    """
    analysis = _analyze_content_depth(tweet_text)
    ctype    = analysis["content_type"]
    entity   = analysis["entity"]

    # ── استخراج مقتطف من التغريدة ────────────────────────────
    clean = re.sub(r'@\w+', '', tweet_text)
    clean = re.sub(r'https?://\S+', '', clean)
    clean = re.sub(r'#\w+', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    excerpt = clean[:50] if len(clean) > 10 else ""
    if len(excerpt) == 50:
        excerpt = excerpt.rsplit(' ', 1)[0]

    # ══════════════════════════════════════════════════════════
    # قوالب التعليق التحليلي حسب نوع المحتوى
    # ══════════════════════════════════════════════════════════

    if ctype == "analytical":
        options = [
            f"نقطة تحليلية مهمة! بخصوص {excerpt or entity or 'ما ذكرته'} — "
            f"اللافت أن هذا الاتجاه يتوافق مع ما رصدناه في بيانات {entity or 'النموذج'}. "
            f"السؤال: هل التقييم يشمل حالات الاستخدام الحقيقية أم فقط الـ Benchmarks؟",

            f"تحليل دقيق! ما ذكرته عن {excerpt or entity or 'هذا الجانب'} "
            f"يكشف جانباً مهماً غالباً ما يُغفله التقارير. "
            f"وش مصدر البيانات اللي استندت عليها في هذا التحليل؟",

            f"هذا بالضبط اللافت في {entity or 'هذا التطور'}! "
            f"الأرقام اللي ذكرتها تستاهل المقارنة مع ما أعلنته "
            f"{'OpenAI' if 'openai' not in tweet_text.lower() else 'Anthropic'} الأسبوع الماضي. "
            f"هل لاحظت الفرق؟",
        ]

    elif ctype == "news":
        options = [
            f"خبر مهم يستاهل التعمق! بخصوص {excerpt or entity or 'هذا الإعلان'} — "
            f"التساؤل الرئيسي: ما التأثير الفعلي على السوق السعودي خلال الـ 12 شهر القادمة؟",

            f"هذا الخبر يفتح نقاش مهم! "
            f"بخصوص {entity or 'التطور الجديد'} — "
            f"الجانب اللي ما أُشير إليه: تأثيره على الشركات الناشئة في المنطقة. "
            f"وش رأيك في انعكاساته المحلية؟",

            f"تغطية ممتازة! بخصوص {excerpt or entity or 'ما أعلن عنه'} — "
            f"اللافت أن هذا يسبق توقعات المحللين بـ 6 أشهر على الأقل. "
            f"وش توقعاتك للخطوة القادمة؟",
        ]

    elif ctype == "opinion":
        options = [
            f"رأي يستاهل نقاش! بخصوص \"{excerpt}\" — "
            f"أتفق في نقطة، لكن اللي يغيّر المعادلة هو سرعة تبني السوق المحلي. "
            f"هل هذا في حسبتك؟",

            f"زاوية نظر مثيرة! لكن من تجربة عملية مع {entity or 'هذه الأدوات'} — "
            f"النتائج تختلف بحسب حالة الاستخدام. "
            f"على أي نوع من التطبيقات بنيت هذا الرأي؟",

            f"تحليل جيد! البُعد اللي يستاهل يُضاف: "
            f"كيف تتغير هذه المعادلة لما يدخل اللاعبون المحليون (SDAIA / شركات الخليج)؟",
        ]

    else:
        # general
        options = [
            f"نقطة مهمة! بخصوص {excerpt or entity or 'ما ذكرته'} — "
            f"السياق السعودي يضيف زاوية غير مذكورة: "
            f"مدى جاهزية البنية التحتية ومستوى الكوادر المحلية. "
            f"وش تشوف؟",

            f"محتوى يستاهل التعمق! "
            f"بخصوص {entity or 'هذا الموضوع'} — "
            f"اللي يغيّب في كثير من النقاشات: التطبيق العملي في بيئة العمل العربية. "
            f"عندك تجربة في هذا؟",
        ]

    reply = random.choice(options)

    # ضمان عدم تجاوز الحد
    if tweet_length(reply) > 270:
        reply = reply[:265].rsplit(' ', 1)[0] + "..."

    return reply


# ══════════════════════════════════════════════════════════════
#  الوكيل الرئيسي
# ══════════════════════════════════════════════════════════════
class EngageAgent:
    """
    وكيل التفاعل مع أفضل الحسابات التقنية.
    يكتشف الحسابات تلقائياً ويتفاعل معها بلغة تحليلية.
    """

    def __init__(self):
        self.name   = "EngageAgent"
        self.client = tweepy.Client(
            bearer_token=BEARER_TOKEN,
            consumer_key=CONSUMER_KEY,
            consumer_secret=CONSUMER_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET,
            wait_on_rate_limit=True,
        )

    def _load_top_accounts(self) -> list:
        """تحميل قاعدة الحسابات المحفوظة"""
        data = load_json(ACCOUNTS_FILE)
        return data if isinstance(data, list) else []

    def _save_top_accounts(self, accounts: list) -> None:
        save_json(ACCOUNTS_FILE, accounts[:50])  # احتفظ بأفضل 50

    def _load_engaged(self) -> set:
        data = load_json(ENGAGED_FILE)
        return set(data) if isinstance(data, list) else set()

    def _save_engaged(self, engaged: set) -> None:
        save_json(ENGAGED_FILE, list(engaged)[-3000:])

    def discover_top_accounts(self, max_accounts: int = 10) -> list:
        """
        يكتشف أفضل 10 حسابات تقنية عربية بناءً على:
        - التغريدات الأكثر تفاعلاً في الهاشتاقات التقنية
        - عدد المتابعين (مؤشر مصداقية)
        - تكرار ظهور الحساب في نتائج البحث
        """
        logger.info(f"[{self.name}] 🔍 اكتشاف أفضل الحسابات...")
        account_scores: dict = {}

        for query in TECH_ACCOUNT_QUERIES[:3]:  # حد البحث
            try:
                response = self.client.search_recent_tweets(
                    query=query,
                    max_results=50,
                    tweet_fields=["author_id", "public_metrics", "text"],
                    expansions=["author_id"],
                    user_fields=["username", "name", "public_metrics", "description"],
                )
                if not response.data:
                    continue

                users_map = {}
                if response.includes and "users" in response.includes:
                    for user in response.includes["users"]:
                        users_map[user.id] = user

                for tweet in response.data:
                    author_id = tweet.author_id
                    user      = users_map.get(author_id)
                    if not user:
                        continue

                    username   = user.username or ""
                    followers  = (user.public_metrics or {}).get("followers_count", 0)
                    tweet_text = tweet.text or ""
                    metrics    = tweet.public_metrics or {}
                    engagement = (
                        metrics.get("like_count", 0) +
                        metrics.get("retweet_count", 0) * 2 +
                        metrics.get("reply_count", 0) * 3
                    )

                    # ── نقاط الحساب ───────────────────────
                    if username not in account_scores:
                        account_scores[username] = {
                            "username":    username,
                            "name":        user.name or username,
                            "followers":   followers,
                            "appearances": 0,
                            "total_engagement": 0,
                            "description": getattr(user, "description", ""),
                            "recent_tweet": tweet_text[:100],
                        }
                    account_scores[username]["appearances"]      += 1
                    account_scores[username]["total_engagement"] += engagement

                time.sleep(2)

            except tweepy.TweepyException as e:
                logger.warning(f"[{self.name}] فشل البحث: {e}")

        # ── ترتيب الحسابات ──────────────────────────────────
        sorted_accounts = sorted(
            account_scores.values(),
            key=lambda x: (
                x["appearances"] * 3 +
                x["total_engagement"] +
                min(x["followers"] / 1000, 50)  # حد أقصى للمتابعين
            ),
            reverse=True,
        )

        top = sorted_accounts[:max_accounts]
        for i, acc in enumerate(top, 1):
            logger.info(
                f"[{self.name}] #{i} @{acc['username']} | "
                f"متابعون: {acc['followers']:,} | "
                f"ظهور: {acc['appearances']} | "
                f"تفاعل: {acc['total_engagement']}"
            )

        self._save_top_accounts(top)
        return top

    def engage_with_accounts(self, accounts: list, max_engage: int = 5) -> int:
        """
        يتفاعل مع آخر تغريدات الحسابات المحددة.
        يبني تعليقاً تحليلياً مخصصاً لكل تغريدة.
        """
        engaged = self._load_engaged()
        count   = 0

        for acc in accounts:
            if count >= max_engage:
                break

            username = acc.get("username", "")
            if not username:
                continue

            try:
                # جلب آخر تغريدات الحساب
                user_response = self.client.get_user(username=username)
                if not user_response.data:
                    continue

                tweets_response = self.client.get_users_tweets(
                    id=user_response.data.id,
                    max_results=5,
                    tweet_fields=["public_metrics", "text", "created_at"],
                    exclude=["retweets", "replies"],
                )
                if not tweets_response.data:
                    continue

                for tweet in tweets_response.data:
                    if count >= max_engage:
                        break

                    tid        = str(tweet.id)
                    tweet_text = tweet.text or ""

                    if tid in engaged:
                        continue

                    # تحقق: هل التغريدة تستحق التفاعل التحليلي؟
                    depth = _analyze_content_depth(tweet_text)
                    if depth["content_type"] == "general" and not depth["has_number"]:
                        continue  # تجاهل المحتوى العام الضعيف

                    # ── بناء تعليق تحليلي ──────────────────
                    comment = build_analytical_comment(tweet_text, username)

                    time.sleep(random.uniform(30, 90))
                    try:
                        self.client.create_tweet(
                            text=comment,
                            in_reply_to_tweet_id=tid,
                        )
                        logger.info(
                            f"[{self.name}] ✅ تفاعل مع @{username} | "
                            f"نوع: {depth['content_type']} | "
                            f"{comment[:60]}"
                        )
                        engaged.add(tid)
                        count += 1
                    except tweepy.TweepyException as e:
                        logger.warning(f"[{self.name}] فشل التعليق: {e}")

                time.sleep(5)

            except tweepy.TweepyException as e:
                logger.warning(f"[{self.name}] فشل جلب تغريدات @{username}: {e}")

        self._save_engaged(engaged)
        return count

    def run(self, rediscover: bool = False):
        """
        التشغيل الكامل للوكيل:
        1. تحميل/اكتشاف أفضل الحسابات
        2. التفاعل التحليلي مع محتواهم
        """
        logger.info(
            f"[{self.name}] 🌐 بدء جلسة التفاعل — "
            f"{now_riyadh().strftime('%Y-%m-%d %H:%M')}"
        )

        # تحميل الحسابات
        accounts = self._load_top_accounts()
        if not accounts or rediscover:
            logger.info(f"[{self.name}] اكتشاف حسابات جديدة...")
            accounts = self.discover_top_accounts(max_accounts=10)

        if not accounts:
            logger.warning(f"[{self.name}] لم يُعثر على حسابات")
            return

        # التفاعل مع المحتوى
        count = self.engage_with_accounts(accounts, max_engage=5)
        logger.info(f"[{self.name}] 🏁 إجمالي التفاعلات: {count}")

    def get_top_accounts_report(self) -> str:
        """
        يُعيد تقرير موجز بأفضل 10 حسابات تقنية مكتشفة.
        """
        accounts = self._load_top_accounts()
        if not accounts:
            return "لم يتم اكتشاف حسابات بعد. شغّل discover_top_accounts() أولاً."

        lines = ["📊 أفضل الحسابات التقنية المكتشفة:\n"]
        for i, acc in enumerate(accounts[:10], 1):
            lines.append(
                f"{i}. @{acc['username']} ({acc['name']}) | "
                f"متابعون: {acc.get('followers',0):,} | "
                f"ظهور: {acc.get('appearances',0)}"
            )

        return "\n".join(lines)
