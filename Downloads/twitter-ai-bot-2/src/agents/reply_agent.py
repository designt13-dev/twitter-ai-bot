# src/agents/reply_agent.py
"""
وكيل الرد السياقي v2 — يقرأ التعليق ويبني رداً حقيقياً
"""
import re, random, sys, pathlib, time
import tweepy
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
from config.settings import (
    CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN,
    ACCESS_TOKEN_SECRET, BEARER_TOKEN,
    SEARCH_HASHTAGS, REPLY_COUNT_PER_RUN, LOGS_DIR,
)
from src.utils import logger, load_json, save_json, now_riyadh, tweet_length

REPLIED_FILE      = LOGS_DIR / "replied_ids.json"
LAST_MENTION_FILE = LOGS_DIR / "last_mention_id.json"

TOOL_FACTS = {
    "ChatGPT": [
        "ChatGPT-4o يفهم الصور والصوت والنص في نفس الوقت الحين.",
        "جرّب Projects في ChatGPT — تنظّم محادثاتك بشكل أفضل.",
        "ChatGPT Plus يعطيك أولوية وأدوات متقدمة مقارنة بالمجاني.",
    ],
    "Claude": [
        "Claude 3.5 Sonnet من أفضل النماذج لتحليل المستندات والأكواد.",
        "Claude يقدر يقرأ ملف PDF كامل بسياق طويل جداً.",
        "Anthropic تركّز على الأمان — هذا يميّز Claude عن المنافسين.",
    ],
    "DeepSeek": [
        "DeepSeek R1 يضاهي GPT-4 بتكلفة أقل بكثير.",
        "DeepSeek مفتوح المصدر — تقدر تشغله محلياً على جهازك.",
    ],
    "Gemini": [
        "Gemini 2.0 Flash من أسرع النماذج وأرخصها الحين.",
        "Gemini يتكامل مع Google Workspace مباشرة — مفيد للشغل.",
    ],
    "Grok": [
        "Grok عنده وصول مباشر لبيانات X في الوقت الفعلي.",
        "Grok 3 الحين يُعتبر من أقوى النماذج المتاحة.",
    ],
}

TOPIC_FACTS = {
    "jobs": [
        "الوظائف اللي تتطلب إبداعاً وتفاعلاً بشرياً الأكثر مقاومةً لـ AI.",
        "McKinsey تقول 30% من المهام القابلة للأتمتة ستتأثر بحلول 2030.",
        "الوظائف الجديدة اللي خلقها AI أكثر من اللي أزالها — لحد الآن.",
    ],
    "coding": [
        "GitHub Copilot رفع إنتاجية المطورين 55% حسب دراسة GitHub.",
        "AI لن يستبدل المطورين — لكن المطور اللي يستخدم AI سيستبدل من لا يستخدمه.",
    ],
    "ksa": [
        "المملكة استثمرت أكثر من 40 مليار دولار في التقنية والذكاء الاصطناعي.",
        "SDAIA تطور نماذج AI تفهم اللهجة السعودية — خطوة مهمة.",
    ],
    "risk": [
        "أكبر مخاطر AI الحين: التزييف العميق + انتهاك الخصوصية + التحيز.",
        "الدول اللي ما تنظّم AI مبكراً ستعاني لاحقاً.",
    ],
    "general": [
        "الشركات اللي دمجت AI في عملها رأت إنتاجية أعلى بـ 40% في المتوسط.",
        "AI الحين يعالج أكثر من مليار طلب يومياً — الرقم يضاعف كل سنة.",
    ],
}

LEARNING_PATHS = {
    "coding":   ["ابدأ بـ Python + مكتبة Hugging Face — أسرع طريق لـ AI عملياً."],
    "general":  ["افضل طريقة: استخدم AI يومياً في مهمة حقيقية عندك."],
    "education":["NotebookLM من Google يحوّل أي PDF لدرس تفاعلي — جرّبه."],
}

FOLLOWUP = {
    "jobs":       ["وش مجالك؟ عشان أعطيك رأي أدق.", "تشوف نفسك تكيّفت مع هالتغيير؟"],
    "coding":     ["وش لغة البرمجة اللي تشتغل عليها؟", "Copilot أو Cursor — أيهما جربت؟"],
    "ksa":        ["وش رأيك في جاهزية السوق السعودي لهذا؟"],
    "risk":       ["وش الجانب اللي يقلقك أكثر؟"],
    "general":    ["وش رأيك؟ 💬", "كيف تشوف تأثيره على مجالك؟"],
}

def deep_analyze(text):
    t = re.sub(r'@\w+|https?://\S+', '', text).strip()
    tl = t.lower()
    AI_TOOLS = {
        "chatgpt":"ChatGPT","gpt-4":"GPT-4","gpt4":"GPT-4","gpt-5":"GPT-5",
        "gemini":"Gemini","claude":"Claude","grok":"Grok","deepseek":"DeepSeek",
        "copilot":"Copilot","midjourney":"Midjourney","sora":"Sora",
        "llama":"Llama","mistral":"Mistral","cursor":"Cursor",
    }
    tools = [n for k,n in AI_TOOLS.items() if k in tl]
    TOPICS = {
        "jobs":   ["وظيف","عمل","بطال","توظيف","job","career","layoff","fired"],
        "coding": ["برمجة","كود","تطوير","code","programming","python","developer"],
        "ksa":    ["سعودية","مملكة","رؤية","2030","sdaia","saudi"],
        "risk":   ["خطر","قلق","خوف","أمان","خصوصية","risk","danger","privacy"],
        "general":[]
    }
    topic = "general"
    for tp, kws in TOPICS.items():
        if any(k in tl for k in kws):
            topic = tp; break
    BEGINNER = ["ما أفهم","ما أعرف","كيف أبدأ","وش هو","إيش يعني","ما عندي خبرة"]
    EXPERT   = ["architecture","transformer","fine-tuning","inference","benchmark","tokens","parameters","rag","embedding"]
    level = "expert" if any(w in tl for w in EXPERT) else "beginner" if any(w in t for w in BEGINNER) else "intermediate"
    clean = re.sub(r'[\U00010000-\U0010ffff]','',t).strip()
    quote = (clean[:67]+"...") if len(clean)>70 else clean
    return {
        "text": t, "quote": quote,
        "tool": tools[0] if tools else "",
        "topic": topic, "level": level,
        "is_question":    bool(re.search(r'[؟?]',t) or any(q in t for q in ["كيف","وش","هل","ليش","وين","إيش"])),
        "is_asking_how":  any(w in tl for w in ["كيف أبدأ","كيف أتعلم","من وين","أول خطوة","أبدأ من"]),
        "is_experience":  any(w in t for w in ["جربت","استخدمت","من تجربتي","شخصياً","عملت"]),
        "is_concern":     any(w in t for w in ["خايف","قلقان","مخيف","مقلق","مشكلة"]),
        "is_positive":    any(w in t for w in ["رائع","ممتاز","مو طبيعي","والله","مذهل"]),
        "is_disagreeing": any(w in t for w in ["ما أوافق","مو صحيح","أختلف","خطأ","لا "]),
    }

def build_contextual_reply(comment_text, original_tweet=""):
    ctx   = deep_analyze(comment_text)
    quote = ctx["quote"]
    tool  = ctx["tool"]
    topic = ctx["topic"]

    if tool and tool in TOOL_FACTS:
        fact = random.choice(TOOL_FACTS[tool])
    else:
        fact = random.choice(TOPIC_FACTS.get(topic, TOPIC_FACTS["general"]))

    path    = random.choice(LEARNING_PATHS.get(topic, LEARNING_PATHS["general"]))
    followup= random.choice(FOLLOWUP.get(topic, FOLLOWUP["general"]))

    if ctx["is_asking_how"]:
        reply = f'سؤال يسأله كثيرون — "{quote}"\n\n{path}\n\n{followup}'
    elif ctx["is_disagreeing"]:
        reply = f'وجهة نظرك تستاهل نقاش — "{quote}"\n\nبس اللي يُذكر: {fact}\n\n{followup}'
    elif ctx["is_concern"]:
        reply = f'قلقك منطقي — "{quote}"\n\n{fact}\n\n{followup}'
    elif ctx["is_experience"]:
        reply = f'تجربة واقعية — "{quote}"\n\nأضيف: {fact}\n\n{followup}'
    elif ctx["is_positive"]:
        reply = f'فعلاً يستاهل — "{quote}"\n\n{fact}\n\n{followup}'
    elif ctx["is_question"]:
        reply = f'سؤال وجيه — "{quote}"\n\n{fact}\n\n{followup}'
    else:
        reply = f'نقطة مهمة — "{quote}"\n\n{fact}\n\n{followup}'

    if ctx["level"] == "beginner":
        reply = "لا تقلق — " + reply

    if tweet_length(reply) > 275:
        lines = reply.split('\n')
        out, total = [], 0
        for l in lines:
            if total + len(l) + 1 <= 270:
                out.append(l); total += len(l)+1
        reply = '\n'.join(out).strip()

    return reply

def get_twitter_client():
    return tweepy.Client(
        bearer_token=BEARER_TOKEN, consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET, access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET, wait_on_rate_limit=True,
    )

def load_replied():
    data = load_json(REPLIED_FILE)
    return set(data) if isinstance(data, list) else set()

def save_replied(replied):
    save_json(REPLIED_FILE, list(replied))

def handle_mentions(client, replied, max_replies=5):
    count = 0
    try:
        last_data = load_json(LAST_MENTION_FILE) or {}
        since_id  = last_data.get("last_mention_id")
        me        = client.get_me().data.id
        mentions  = client.get_users_mentions(
            id=me, since_id=since_id,
            tweet_fields=["text","author_id","created_at"], max_results=10,
        )
        if not mentions.data:
            logger.info("[ReplyAgent] لا منشنات"); return 0
        save_json(LAST_MENTION_FILE, {"last_mention_id": str(mentions.data[0].id)})
        for mention in mentions.data:
            if count >= max_replies: break
            tid = str(mention.id)
            if tid in replied: continue
            reply = build_contextual_reply(mention.text)
            try:
                client.create_tweet(text=reply, in_reply_to_tweet_id=tid)
                replied.add(tid); count += 1
                logger.info(f"[ReplyAgent] ✅ {tid}: {reply[:50]}...")
                time.sleep(5)
            except tweepy.TweepyException as e:
                logger.error(f"[ReplyAgent] ❌ {e}")
    except Exception as e:
        logger.error(f"[ReplyAgent] ❌ {e}")
    return count

def reply_to_search(client, replied, max_replies=5):
    count = 0
    for hashtag in random.sample(SEARCH_HASHTAGS, min(3, len(SEARCH_HASHTAGS))):
        if count >= max_replies: break
        try:
            results = client.search_recent_tweets(
                query=f"{hashtag} lang:ar -is:retweet -is:reply",
                tweet_fields=["text","public_metrics"], max_results=10,
            )
            if not results.data: continue
            tweets = sorted(results.data,
                key=lambda t: t.public_metrics.get("like_count",0), reverse=True)
            for tweet in tweets[:3]:
                if count >= max_replies: break
                tid = str(tweet.id)
                if tid in replied or len(tweet.text.strip()) < 15: continue
                reply = build_contextual_reply(tweet.text)
                try:
                    client.create_tweet(text=reply, in_reply_to_tweet_id=tid)
                    replied.add(tid); count += 1
                    logger.info(f"[ReplyAgent] ✅ هاشتاق {hashtag}: {reply[:50]}...")
                    time.sleep(8)
                except tweepy.TweepyException as e:
                    logger.error(f"[ReplyAgent] ❌ {e}")
        except Exception as e:
            logger.error(f"[ReplyAgent] ❌ بحث {hashtag}: {e}")
    return count

def run_reply_agent():
    logger.info(f"[ReplyAgent] 🚀 بدأ — {now_riyadh()}")
    client  = get_twitter_client()
    replied = load_replied()
    total   = handle_mentions(client, replied, max_replies=3)
    total  += reply_to_search(client, replied, max_replies=max(0, REPLY_COUNT_PER_RUN-total))
    save_replied(replied)
    logger.info(f"[ReplyAgent] ✅ انتهى — {total} ردود")
    return total

if __name__ == "__main__":
    tests = [
        "جربت ChatGPT بس ما فهمت كيف أبدأ",
        "خايف AI ياخذ وظيفتي كمحاسب",
        "DeepSeek أحسن من GPT-4 ولا مبالغة؟",
    ]
    for t in tests:
        print(f"\n💬 {t}\n🤖 {build_contextual_reply(t)}\n{'─'*40}")
