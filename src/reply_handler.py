# src/reply_handler.py
"""
نظام الرد التفاعلي — يرد على التعليقات الواردة على المنشورات
═══════════════════════════════════════════════════════════════
التدفق:
1. جلب Mentions الأخيرة (ردود على تغريداتنا)
2. الرد عليها بأسلوب إنساني تفاعلي
3. البحث في hashtags للرد على تغريدات الآخرين
═══════════════════════════════════════════════════════════════
هدف: 15 رد/يوم (5 ردود × 3 مرات/يوم)
بدون هاشتاقات — أسلوب سعودي طبيعي
"""
import tweepy
import time
import random
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from config.settings import (
    CONSUMER_KEY, CONSUMER_SECRET,
    ACCESS_TOKEN, ACCESS_TOKEN_SECRET,
    BEARER_TOKEN, SEARCH_HASHTAGS,
    REPLY_COUNT_PER_RUN, LOGS_DIR,
)
from src.utils import logger, load_json, save_json, now_riyadh, today_str


# ── ملفات السجل ──────────────────────────────────────────────
REPLIED_FILE      = LOGS_DIR / "replied_ids.json"
LAST_MENTION_FILE = LOGS_DIR / "last_mention_id.json"


def load_replied() -> set:
    data = load_json(REPLIED_FILE)
    return set(data) if isinstance(data, list) else set()


def save_replied(replied: set) -> None:
    save_json(REPLIED_FILE, list(replied)[-2000:])


def load_last_mention_id() -> str | None:
    data = load_json(LAST_MENTION_FILE)
    return data.get("id") if isinstance(data, dict) else None


def save_last_mention_id(mention_id: str) -> None:
    save_json(LAST_MENTION_FILE, {"id": mention_id})


# ══════════════════════════════════════════════════════════════
#  قوالب الردود — إنسانية + بدون هاشتاقات
# ══════════════════════════════════════════════════════════════
# ردود على Mentions (شخص رد علينا)
MENTION_REPLIES = [
    "شكرًا على تفاعلك! رأيك يُضيف للنقاش. ما الجانب الأكثر إثارةً بالنسبة لك؟",
    "سعيد أن الموضوع لفت انتباهك. هل لديك تجربة مشابهة في هذا المجال؟",
    "ملاحظة مهمة! هذا بالضبط ما يجعل النقاش التقني ممتعًا. ما رأيك في المستقبل القريب؟",
    "رائع أنك تابعت. هل تعتقد أن هذا سيُؤثر على مجال عملك مباشرة؟",
    "شكرًا! نقطة تستحق التوسع فيها. هل جربت {tool} في سياق مشابه؟",
    "وجهة نظر مثيرة للاهتمام. في رأيي السوق السعودي من أكثر الأسواق استعدادًا لهذا التحول.",
    "تعليق قيّم! ما الذي تتمنى أن تراه قريبًا في هذا المجال؟",
    "ممتنن لمشاركتك الرأي. هل تعتقد أن {field} سيكون القطاع الأكثر تأثرًا؟",
    "فكرة تستحق نقاشًا أعمق. يسعدني أسمع المزيد من وجهة نظرك.",
    "شكرًا على التفاعل! هذا النوع من النقاشات يُثري المحتوى التقني العربي.",
]

# ردود على تغريدات الآخرين (بحث)
SEARCH_REPLIES = [
    "رأي رائع! الذكاء الاصطناعي فعلًا يغيّر المعادلة. هل جربت {tool} في هذا السياق؟",
    "نقطة مهمة جدًا. في رأيي هذا المجال سيتطور كثيرًا. ما توقعاتك؟",
    "موضوع حيوي. هل تعتقد أن السوق السعودي يسير بالسرعة الكافية في هذا التوجه؟",
    "شكرًا على هذا الطرح. الذكاء الاصطناعي يفتح آفاقًا كثيرة لم تكن متاحة من قبل.",
    "متفق معك. هذه التقنية ستُعيد رسم ملامح كثير من القطاعات خلال سنوات قليلة.",
    "تحليل ممتاز! من تجربتي مع {tool}، النتائج مختلفة تمامًا عن الطرق التقليدية.",
    "استمر في نشر هذا الوعي — نحتاج المزيد من النقاشات التقنية الهادفة باللغة العربية.",
    "فكرة ملهمة. دمج الذكاء الاصطناعي مع {field} سيحدث نقلة نوعية في السنوات القادمة.",
    "مثير للاهتمام! هل لديك تجربة عملية مع هذا الحل؟ يسعدني أعرف أكثر.",
    "طرح مميز. الذكاء الاصطناعي أصبح ضرورة تنافسية لا ترفًا في كل القطاعات.",
    "رؤية واضحة. الفرق بين من يتبنى AI ومن لا يتبناه سيتضح جليًا خلال سنوات قليلة.",
    "محتوى قيّم. شاركنا المزيد من هذه الأفكار — نحتاجها في المحتوى العربي.",
    "موضوع يستحق النقاش. كيف ترى دور التعليم في تهيئة الكوادر لهذا التحول؟",
    "الاستثمار في تعلم AI الآن يعني ميزة تنافسية حقيقية لاحقًا — أتفق معك تمامًا.",
    "هذا بالضبط ما نحتاج نقاشه أكثر. شكرًا لطرح الموضوع بهذا الوضوح.",
    "ملاحظة ذكية! من تجربتي أن {tool} غيّر طريقة التعامل مع {field} بشكل كامل.",
    "أحسنت الطرح. هذا ما يحتاجه محتوى التقنية العربي — عمق ووضوح ومصداقية.",
]

AI_TOOLS = [
    "ChatGPT", "Gemini", "Claude", "Copilot", "Perplexity",
    "NotebookLM", "Grok", "Mistral",
]
FIELDS = [
    "التعليم", "الصحة", "المال والأعمال", "التسويق",
    "الموارد البشرية", "خدمة العملاء", "المحتوى الرقمي",
]


def _format_reply(template: str) -> str:
    return template.format(
        tool=random.choice(AI_TOOLS),
        field=random.choice(FIELDS),
    )


# ══════════════════════════════════════════════════════════════
#  إعداد العملاء
# ══════════════════════════════════════════════════════════════
def get_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )


# ══════════════════════════════════════════════════════════════
#  الرد على Mentions (ردود على تغريداتنا)
# ══════════════════════════════════════════════════════════════
def reply_to_mentions(client: tweepy.Client, replied: set, max_count: int) -> int:
    count = 0
    try:
        # جلب الـ mentions الأخيرة
        kwargs = {
            "max_results": 20,
            "tweet_fields": ["author_id", "conversation_id"],
        }
        last_id = load_last_mention_id()
        if last_id:
            kwargs["since_id"] = last_id

        response = client.get_users_mentions(
            id=client.get_me().data.id,
            **kwargs
        )

        if not response.data:
            logger.info("[Mentions] لا توجد mentions جديدة")
            return 0

        # احفظ آخر ID
        newest_id = str(response.data[0].id)
        save_last_mention_id(newest_id)

        for mention in response.data:
            if count >= max_count:
                break

            mid = str(mention.id)
            if mid in replied:
                continue

            delay = random.uniform(15, 45)
            logger.info(f"[Mentions] انتظار {delay:.0f}s...")
            time.sleep(delay)

            reply_text = _format_reply(random.choice(MENTION_REPLIES))
            try:
                client.create_tweet(
                    text=reply_text,
                    in_reply_to_tweet_id=mid,
                )
                logger.info(f"[Mentions] ✅ رد على {mid}: {reply_text[:60]}...")
                replied.add(mid)
                count += 1
            except tweepy.TweepyException as e:
                logger.warning(f"[Mentions] فشل الرد: {e}")

    except tweepy.TweepyException as e:
        logger.warning(f"[Mentions] فشل جلب mentions: {e}")

    return count


# ══════════════════════════════════════════════════════════════
#  البحث عن تغريدات للرد عليها
# ══════════════════════════════════════════════════════════════
def search_and_reply(client: tweepy.Client, replied: set, target: int) -> int:
    count = 0
    random.shuffle(SEARCH_HASHTAGS)

    for hashtag in SEARCH_HASHTAGS:
        if count >= target:
            break
        try:
            query    = f"{hashtag} -is:retweet lang:ar"
            response = client.search_recent_tweets(
                query=query,
                max_results=20,
                tweet_fields=["author_id", "created_at"],
            )
            if not response.data:
                continue

            logger.info(f"[Search] {hashtag}: {len(response.data)} تغريدة")

            for tweet in response.data:
                if count >= target:
                    break
                tid = str(tweet.id)
                if tid in replied:
                    continue

                delay = random.uniform(30, 90)
                logger.info(f"[Search] انتظار {delay:.0f}s...")
                time.sleep(delay)

                reply_text = _format_reply(random.choice(SEARCH_REPLIES))
                try:
                    client.create_tweet(
                        text=reply_text,
                        in_reply_to_tweet_id=tid,
                    )
                    logger.info(f"[Search] ✅ رد على {tid}")
                    replied.add(tid)
                    count += 1
                except tweepy.TweepyException as e:
                    logger.warning(f"[Search] فشل الرد: {e}")

        except tweepy.TweepyException as e:
            logger.warning(f"[Search] فشل البحث عن {hashtag}: {e}")

    return count


# ══════════════════════════════════════════════════════════════
#  الدالة الرئيسية
# ══════════════════════════════════════════════════════════════
def run_reply_bot():
    logger.info(
        f"[ReplyBot] 🤖 بدء جلسة الردود — "
        f"{now_riyadh().strftime('%Y-%m-%d %H:%M')}"
    )

    client  = get_client()
    replied = load_replied()
    target  = REPLY_COUNT_PER_RUN
    count   = 0

    # أولوية: الرد على من تفاعل معنا أولًا
    mention_count = reply_to_mentions(client, replied, max_count=min(3, target))
    count += mention_count
    logger.info(f"[ReplyBot] Mentions: {mention_count} رد")

    # ثم البحث عن تغريدات الآخرين
    remaining = target - count
    if remaining > 0:
        search_count = search_and_reply(client, replied, target=remaining)
        count += search_count
        logger.info(f"[ReplyBot] Search: {search_count} رد")

    save_replied(replied)
    logger.info(f"[ReplyBot] 🏁 انتهت الجلسة — إجمالي: {count} رد")


if __name__ == "__main__":
    run_reply_bot()
