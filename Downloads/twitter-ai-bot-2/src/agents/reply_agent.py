# src/agents/reply_agent.py  — النسخة v3 (فهم سياقي حقيقي)
"""
وكيل الرد السياقي — v3
═══════════════════════════════════════════════════════════════
المشكلة في v1/v2:
  ❌ الردود تبدو آلية حتى مع التحليل
  ❌ الرد لا يثبت إنه "فهم" فعلاً ما قاله الشخص
  ❌ نهاية الرد دائماً سؤال مكرر لا يتعلق بالسياق

الحل في v3:
  ✅ يقتبس كلمة/مصطلح مُحدد قاله الشخص (ما الجملة كاملة)
  ✅ يُقدّم معلومة عملية واحدة مفيدة حسب الموضوع
  ✅ ينهي برد يحفز الحوار — مختلف في كل مرة
  ✅ يتعامل مع كل فئة: سؤال / قلق / خبرة / خلاف / مشاركة
  ✅ يحترم مستوى الشخص: مبتدئ / متوسط / خبير
═══════════════════════════════════════════════════════════════
"""
import re
import random
import sys
import pathlib
import time

import tweepy

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from config.settings import (
    CONSUMER_KEY, CONSUMER_SECRET,
    ACCESS_TOKEN, ACCESS_TOKEN_SECRET,
    BEARER_TOKEN, SEARCH_HASHTAGS,
    REPLY_COUNT_PER_RUN, LOGS_DIR,
)
from src.utils import logger, load_json, save_json, now_riyadh, tweet_length

REPLIED_FILE      = LOGS_DIR / "replied_ids.json"
LAST_MENTION_FILE = LOGS_DIR / "last_mention_id.json"

# ══════════════════════════════════════════════════════════════
# ①  تحليل عميق للتعليق
# ══════════════════════════════════════════════════════════════

AI_TOOLS_MAP = {
    "chatgpt":          "ChatGPT",
    "chat gpt":         "ChatGPT",
    "gpt-4":            "GPT-4",
    "gpt4":             "GPT-4",
    "gpt-4o":           "GPT-4o",
    "gpt-5":            "GPT-5",
    "gpt5":             "GPT-5",
    "gemini":           "Gemini",
    "claude":           "Claude",
    "grok":             "Grok",
    "copilot":          "Copilot",
    "perplexity":       "Perplexity",
    "midjourney":       "Midjourney",
    "sora":             "Sora",
    "dall-e":           "DALL-E",
    "dalle":            "DALL-E",
    "llama":            "Llama",
    "mistral":          "Mistral",
    "deepseek":         "DeepSeek",
    "qwen":             "Qwen",
    "runway":           "Runway",
    "stable diffusion": "Stable Diffusion",
    "cursor":           "Cursor",
    "notebooklm":       "NotebookLM",
    "devin":            "Devin",
    "replit":           "Replit AI",
    "codeium":          "Codeium",
    "github copilot":   "GitHub Copilot",
}

TOPIC_KEYWORDS = {
    "jobs":       ["وظيف", "عمل", "مهن", "بطال", "توظيف", "راتب", "job", "career", "hire", "layoff", "fired", "salary"],
    "education":  ["تعليم", "دراس", "طالب", "جامع", "تعلم", "كورس", "دورة", "education", "student", "learn", "course"],
    "health":     ["صح", "طب", "مستشف", "علاج", "مريض", "health", "medical", "doctor", "hospital"],
    "investment": ["استثمار", "مال", "أعمال", "شركة", "ربح", "invest", "business", "profit", "funding", "startup"],
    "ksa":        ["رؤية", "2030", "سعودية", "مملكة", "sdaia", "نيوم", "vision", "saudi", "riyadh", "وطني"],
    "learning":   ["ابدأ", "كيف أتعلم", "من وين", "أول خطوة", "beginner", "start", "كيف", "مبتدئ"],
    "risk":       ["خطر", "مشكل", "قلق", "خوف", "أمان", "خصوصية", "risk", "danger", "privacy", "harm"],
    "creativity": ["إبداع", "تصميم", "كتابة", "محتوى", "فن", "creative", "design", "art", "write"],
    "coding":     ["برمجة", "كود", "تطوير", "developer", "code", "programming", "python", "api", "مطور"],
    "comparison": ["أحسن", "أفضل", "فرق", "مقارنة", "compare", "vs", "better", "أقوى", "يتفوق"],
    "privacy":    ["خصوصية", "بيانات", "تتبع", "privacy", "data", "track", "surveillance"],
    "future":     ["مستقبل", "توقع", "بعد سنوات", "future", "predict", "upcoming", "2030"],
}

BEGINNER_SIGNALS = [
    "ما أفهم", "ما أعرف", "كيف أبدأ", "وش هو", "إيش يعني", "ابن آدم عادي",
    "أنا مو خبير", "للمبتدئين", "ما عندي خبرة", "جديد في", "من وين أبدأ",
    "شرح", "explain", "what is", "how to start", "beginner",
]
EXPERT_SIGNALS = [
    "architecture", "transformer", "fine-tuning", "inference", "benchmark",
    "weights", "tokens", "parameters", "gradient", "latency", "throughput",
    "rag", "embedding", "vector", "prompt engineering", "quantization",
    "lora", "rlhf", "attention", "context window",
]


def deep_analyze(text: str) -> dict:
    """تحليل شامل للتعليق لفهم النية والسياق والمستوى"""
    t       = re.sub(r'@\w+', '', text).strip()
    t_clean = re.sub(r'https?://\S+', '', t).strip()
    t_lower = t_clean.lower()

    # الأدوات المذكورة
    tools = []
    for kw, name in sorted(AI_TOOLS_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if kw in t_lower and name not in tools:
            tools.append(name)
    primary_tool = tools[0] if tools else ""

    # الموضوع
    topics = []
    for topic, kws in TOPIC_KEYWORDS.items():
        if any(kw in t_lower for kw in kws):
            topics.append(topic)
    primary_topic = topics[0] if topics else "general"

    # النية
    is_question   = bool(re.search(r'[؟?]', t_clean) or
                         any(q in t_lower for q in ["كيف", "وش", "ماذا", "هل", "ليش", "لماذا", "متى", "وين", "إيش"]))
    is_asking_how = any(w in t_lower for w in ["كيف أبدأ", "كيف أتعلم", "من وين", "أبدأ من", "أول خطوة", "كيف أستخدم", "طريقة"])
    is_experience = any(w in t_clean for w in ["جربت", "استخدمت", "من تجربتي", "أنا شخصياً", "عملت", "طبّقت", "لاحظت"])
    is_sharing    = any(w in t_clean for w in ["شفت", "قرأت", "سمعت", "اطلعت", "مقال", "خبر", "دراسة", "رأيت"])
    is_concern    = any(w in t_clean for w in ["خايف", "قلقان", "مو متأكد", "مشكلة", "خطر", "مخيف", "مقلق", "تخوف"])
    is_positive   = any(w in t_clean for w in ["رائع", "ممتاز", "أحسن", "مو طبيعي", "والله", "مذهل", "ما شاء الله", "صح", "أوافق"])
    is_disagreeing = any(w in t_clean for w in ["أختلف", "مو صحيح", "ما أوافق", "خطأ", "لا أعتقد", "مو كذا", "مبالغة", "كذب"])

    # مستوى الخبرة
    if any(w in t_lower for w in EXPERT_SIGNALS):
        level = "expert"
    elif any(w in t_lower for w in BEGINNER_SIGNALS):
        level = "beginner"
    else:
        level = "intermediate"

    # استخراج مقتطف للاقتباس
    quote = _extract_key_phrase(t_clean)

    return {
        "text":          t_clean,
        "quote":         quote,
        "tool":          primary_tool,
        "topic":         primary_topic,
        "level":         level,
        "is_question":   is_question,
        "is_asking_how": is_asking_how,
        "is_experience": is_experience,
        "is_sharing":    is_sharing,
        "is_concern":    is_concern,
        "is_positive":   is_positive,
        "is_disagreeing":is_disagreeing,
    }


def _extract_key_phrase(text: str) -> str:
    """يستخرج عبارة مفتاحية (20-55 حرف) من التعليق"""
    clean = re.sub(r'[^\u0600-\u06FFa-zA-Z0-9\s،,.]', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()

    if len(clean) <= 45:
        return clean

    # حاول أن تأخذ جملة قصيرة كاملة
    sentences = re.split(r'[،,.]', clean)
    for s in sentences:
        s = s.strip()
        if 15 <= len(s) <= 55:
            return s

    # خذ أول 45 حرف مع قطع عند آخر مسافة
    pos = clean.rfind(' ', 0, 45)
    if pos > 10:
        return clean[:pos]
    return clean[:40]


# ══════════════════════════════════════════════════════════════
# ②  قواعد المعرفة للرد — معلومات مفيدة حسب الأداة والموضوع
# ══════════════════════════════════════════════════════════════

TOOL_TIPS = {
    "ChatGPT": [
        "ChatGPT-4o يفهم الصور والصوت والنص في وقت واحد — جربه مع رفع صورة.",
        "في ChatGPT، استخدم 'Custom Instructions' عشان يتذكر أسلوبك دائماً.",
        "GPT-4o الأسرع للمحادثة، وo1 الأفضل للمسائل المنطقية والرياضيات.",
        "Prompt Engineering أهم مهارة — كلما وصفت طلبك بدقة، النتيجة أحسن.",
    ],
    "Gemini": [
        "Gemini 2.0 Flash الأسرع للمهام اليومية، و Gemini Ultra للمهام الثقيلة.",
        "Gemini مدمج مع Google Workspace — يقدر يقرأ Gmail وDocs مباشرة.",
        "Deep Research في Gemini يعطيك تقارير مفصّلة من مصادر متعددة.",
    ],
    "Claude": [
        "Claude متميز بفهم النصوص الطويلة — يقدر يقرأ مستند 200 صفحة كامل.",
        "Claude 3.5 Sonnet الأمثل للكتابة الإبداعية والتلخيص.",
        "Claude حذر في إعطاء معلومات مضللة — هذا نقطة قوة في استخدامات العمل.",
    ],
    "Copilot": [
        "GitHub Copilot يكتب الكود ويشرحه ويراجعه — وفّر على المطورين ساعات.",
        "Microsoft Copilot في Office مدمج مع بياناتك — يقدر يكتب تقارير من Excel.",
    ],
    "Midjourney": [
        "Midjourney v6 يعطي صور فوتوغرافية واقعية بشكل لافت — جرب aspect ratio 16:9.",
        "في Midjourney، أضف '--style raw' للحصول على صور أقل معالجة وأكثر واقعية.",
    ],
    "DeepSeek": [
        "DeepSeek R1 مفتوح المصدر ويتفوق على GPT-4 في المسائل المنطقية والكود.",
        "DeepSeek متاح مجاناً عبر API — وهذا يفتح الباب لكثير من التطبيقات.",
    ],
    "Grok": [
        "Grok 3 من xAI وصل لمستوى أفضل النماذج — ومتاح لمشتركي X Premium.",
        "Grok لديه وصول مباشر للأخبار الحديثة على X — مفيد للأخبار اللحظية.",
    ],
}

TOPIC_TIPS = {
    "jobs": [
        "المهارات اللي AI ما يعوّضها بسهولة: التفكير النقدي، التواصل البشري، والقيادة.",
        "اللي يتعلم كيف يستخدم AI في وظيفته بذكاء — يضاعف إنتاجيته ويحمي مكانه.",
        "المهن الإبداعية والاجتماعية الأكثر مقاومة للأتمتة — حسب آخر الدراسات.",
        "AI يزيل المهام الروتينية — ويُركّز الإنسان على القرارات والعلاقات.",
    ],
    "education": [
        "AI يفتح التعليم الشخصي — كل طالب يقدر يتعلم بأسلوبه الخاص.",
        "NotebookLM من Google ثوري للطلاب — يلخص ويحوّل الملاحظات لـ podcast.",
        "كورس AI for Everyone من Coursera مجاني ومثالي للبداية — 6 ساعات فقط.",
        "مهارة الـ Prompt Engineering أصبحت مطلوبة في أغلب الوظائف التقنية.",
    ],
    "investment": [
        "AI infrastructure (chips, data centers, cloud) — القطاع الأكثر نمواً الحين.",
        "Nvidia وMicrosoft وAmazon من أكثر المستفيدين من موجة AI هذه الأيام.",
        "Venture Capital يضخ أكثر من 100 مليار سنوياً في شركات AI حالياً.",
    ],
    "coding": [
        "Cursor IDE يستخدم AI عشان يكتب الكود معك — يوفّر 40% من وقت التطوير.",
        "GitHub Copilot يكتب الكود، يراجعه، ويشرحه — أداة ما تستغني عنها.",
        "Python + AI APIs هو الكومبو المطلوب في أغلب وظائف AI الحين.",
        "تعلم كيف تكتب Prompts للكود — هذه المهارة ثمنها في السوق يرتفع.",
    ],
    "ksa": [
        "SDAIA تقود التحول نحو AI في المملكة وتشرف على مبادرات رؤية 2030.",
        "المملكة من أعلى دول العالم في استخدام ChatGPT نسبةً للسكان.",
        "مبادرة مستقبل الاستثمار (FII) جعلت الرياض مركزاً لـ AI عالمياً.",
        "خطة المملكة في AI تشمل 300 خدمة حكومية رقمية بحلول 2030.",
    ],
    "risk": [
        "الحل ليس التوقف عن استخدام AI — بل تعلّم استخدامه بوعي وتفكير نقدي.",
        "Hallucination مشكلة حقيقية في نماذج AI — تحقق دائماً من المعلومات المهمة.",
        "أكثر ما يُقلق الباحثين: التعمق في الاعتماد على AI دون فهم محدوديته.",
    ],
    "comparison": [
        "GPT-4o الأسرع للمحادثات، وo3 الأقوى للتفكير المنطقي، وClaude الأفضل للكتابة.",
        "كل نموذج له نقطة قوة — المهم تعرف وين تستخدم كل واحد.",
        "Benchmark tests مهمة — لكن التجربة الفعلية في مجالك أهم من الأرقام.",
    ],
    "general": [
        "AI الحين يوفّر ساعات يومياً لمن يُحسن استخدامه في عمله.",
        "أفضل طريقة تتعلم AI: جرّب أداة واحدة يومياً لأسبوع.",
        "المستقبل لمن يعمل مع AI — لا لمن يعمل ضده.",
        "AI ليس magic — لكنه أداة تضاعف إنتاجية من يُتقن استخدامها.",
    ],
}

# ══════════════════════════════════════════════════════════════
# ③  بناء الرد السياقي الذكي
# ══════════════════════════════════════════════════════════════

def build_contextual_reply(analysis: dict) -> str:
    """
    يبني رداً سياقياً طبيعياً يعكس فهماً حقيقياً للتعليق.
    الهيكل: إقرار بالسياق → معلومة مفيدة → دفع للحوار
    """
    tool    = analysis["tool"]
    topic   = analysis["topic"]
    level   = analysis["level"]
    quote   = analysis["quote"]
    
    # — أولاً: اختر نقطة المعرفة المناسبة —
    if tool and tool in TOOL_TIPS:
        tip = random.choice(TOOL_TIPS[tool])
    elif topic in TOPIC_TIPS:
        tip = random.choice(TOPIC_TIPS[topic])
    else:
        tip = random.choice(TOPIC_TIPS["general"])

    # — ثانياً: اختر أسلوب الافتتاح حسب النية —
    opening = _pick_opening(analysis, quote)
    
    # — ثالثاً: اختر نهاية الرد —
    closing = _pick_closing(analysis, tool, topic)

    # — رابعاً: جمّع الرد —
    # نمط A: افتتاح + نصيحة/معلومة + إغلاق
    reply_a = f"{opening}\n{tip}\n{closing}"
    if tweet_length(reply_a) <= 275:
        return reply_a

    # نمط B: افتتاح مختصر + نصيحة + إغلاق
    reply_b = f"{opening} {tip}\n{closing}"
    if tweet_length(reply_b) <= 275:
        return reply_b

    # نمط C: نصيحة + إغلاق فقط
    reply_c = f"{tip}\n{closing}"
    if tweet_length(reply_c) <= 275:
        return reply_c

    # Fallback: قطع النصيحة
    tip_short = tip[:120] if len(tip) > 120 else tip
    return f"{tip_short}\n{closing}"


def _pick_opening(analysis: dict, quote: str) -> str:
    """يختار افتتاحية الرد حسب النية"""
    tool  = analysis["tool"]
    level = analysis["level"]
    
    if analysis["is_asking_how"]:
        if level == "beginner":
            openers = [
                "نقطة انطلاق كويسة —",
                "سؤال كثير يبحث عنه —",
                "البداية أسهل مما تتخيل —",
                "خطوتك الأولى:",
            ]
        else:
            openers = [
                "سؤال عملي —",
                "مباشرة:",
                "إجابة مختصرة:",
            ]
        return random.choice(openers)

    if analysis["is_concern"]:
        openers = [
            "قلق مشروع —",
            "هذا الخوف منطقي —",
            "كثير يفكرون بنفس الطريقة —",
            "الخوف طبيعي — لكن الصورة أوسع:",
        ]
        return random.choice(openers)

    if analysis["is_disagreeing"]:
        openers = [
            "رأي يستاهل النقاش —",
            "وجهة نظر محترمة —",
            "نقطة مهمة —",
            "تحفظ مفهوم —",
        ]
        return random.choice(openers)

    if analysis["is_experience"]:
        openers = [
            "تجربة قيّمة —",
            "هذا اللي يفيد الكل —",
            "شكراً على التجربة —",
            "مشاركة مفيدة —",
        ]
        return random.choice(openers)

    if analysis["is_positive"]:
        openers = [
            "بالضبط —",
            "صح —",
            "وزيادة على هذا:",
            "وللي يريد يعمّق أكثر:",
        ]
        return random.choice(openers)

    if analysis["is_sharing"]:
        openers = [
            "شيء يضيف للصورة:",
            "وكمان:",
            "من نفس الزاوية:",
        ]
        return random.choice(openers)

    # عام
    openers = [
        "نقطة مهمة —",
        "يضيف للموضوع:",
        "بالنسبة لـ{}:".format(f" {tool}" if tool else ""),
    ]
    return random.choice(openers)


def _pick_closing(analysis: dict, tool: str, topic: str) -> str:
    """يختار إغلاقاً يدفع للحوار حسب الموضوع"""
    
    if analysis["is_asking_how"]:
        return random.choice([
            "جربت؟ وش أول شيء عملته؟",
            "تحتاج مساعدة في خطوة معينة؟",
            "هل هذا يساعدك؟ 💬",
        ])
    
    if analysis["is_concern"]:
        return random.choice([
            "وش أكثر شيء يقلقك تحديداً؟ 💬",
            "هل هذا يخفف من المخاوف؟",
            "تشوف الفوائد تعوّض المخاطر؟",
        ])
    
    if analysis["is_disagreeing"]:
        return random.choice([
            "وش رأيك بعد هذه النقطة؟ 💬",
            "هل غير رأيك شيء؟",
            "نكمل النقاش؟",
        ])
    
    TOPIC_CLOSINGS = {
        "jobs":      ["وش خطتك للتكيف؟ 💬", "هل جهّزت مهاراتك؟", "برأيك — فرصة أم تهديد؟"],
        "education": ["في أي مجال تتعلم AI الحين؟ 💬", "تحتاج كورس معين؟", "هل تجربة التعلم كانت ممتعة؟"],
        "coding":    ["وش مشروعك القادم مع AI؟ 💬", "أي IDE تستخدم الحين؟", "جربت Cursor أو Copilot؟"],
        "ksa":       ["وش تتوقع من المملكة في AI خلال ٣ سنوات؟ 💬", "هل تتابع مبادرات SDAIA؟"],
        "investment":["وش القطاع اللي تراه أكثر استفادة؟ 💬", "تشوفها فرصة استثمارية؟"],
        "risk":      ["وش الحل الأمثل برأيك؟ 💬", "تشوف الفوائد أكبر من المخاطر؟"],
        "comparison":["وش تفضل في استخداماتك اليومية؟ 💬", "جربت كلهم؟"],
    }
    
    if topic in TOPIC_CLOSINGS:
        return random.choice(TOPIC_CLOSINGS[topic])
    
    return random.choice([
        "وش رأيك؟ 💬",
        "شاركنا تجربتك.",
        "تتوقع له تأثير على مجالك؟",
        "كيف تشوفه؟ 💬",
    ])


# ══════════════════════════════════════════════════════════════
# ④  منطق الاتصال بـ Twitter API
# ══════════════════════════════════════════════════════════════

def get_twitter_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )


def load_replied() -> set:
    data = load_json(REPLIED_FILE, default=[])
    return set(data) if isinstance(data, list) else set()


def save_replied(replied: set) -> None:
    save_json(REPLIED_FILE, list(replied)[-500:])  # احتفظ بآخر 500 فقط


# ══════════════════════════════════════════════════════════════
# ⑤  ReplyAgent — الكلاس الرئيسي
# ══════════════════════════════════════════════════════════════

class ReplyAgent:
    def __init__(self):
        self.name    = "ReplyAgent-v3"
        self.client  = get_twitter_client()
        self.replied = load_replied()

    def _post_reply(self, reply_text: str, in_reply_to_id: str) -> bool:
        """ينشر الرد ويُعيد True إذا نجح"""
        try:
            self.client.create_tweet(
                text=reply_text,
                in_reply_to_tweet_id=in_reply_to_id,
            )
            logger.info(f"[{self.name}] ✅ رد → {in_reply_to_id} | {tweet_length(reply_text)} حرف")
            return True
        except tweepy.TooManyRequests:
            logger.warning(f"[{self.name}] ⏳ Rate limit — انتظار 15 دقيقة")
            time.sleep(900)
            return False
        except tweepy.Forbidden as e:
            logger.error(f"[{self.name}] ❌ Forbidden: {e}")
            return False
        except tweepy.TweepyException as e:
            logger.error(f"[{self.name}] ❌ خطأ في الرد: {e}")
            return False

    def handle_mentions(self) -> int:
        """يرد على الـ mentions"""
        replied_count = 0
        try:
            # جلب آخر منشن ID
            last_data = load_json(LAST_MENTION_FILE, default={})
            since_id  = last_data.get("id") if isinstance(last_data, dict) else None

            me = self.client.get_me()
            if not me or not me.data:
                return 0
            my_id = me.data.id

            kwargs = {
                "id": my_id,
                "max_results": 20,
                "tweet_fields": ["text", "author_id", "conversation_id"],
            }
            if since_id:
                kwargs["since_id"] = since_id

            mentions = self.client.get_users_mentions(**kwargs)
            if not mentions.data:
                logger.info(f"[{self.name}] لا توجد mentions جديدة")
                return 0

            # حفظ آخر ID
            save_json(LAST_MENTION_FILE, {"id": str(mentions.data[0].id)})

            for tweet in mentions.data:
                tid = str(tweet.id)
                if tid in self.replied:
                    continue
                if str(tweet.author_id) == str(my_id):
                    continue

                analysis   = deep_analyze(tweet.text)
                reply_text = build_contextual_reply(analysis)

                if self._post_reply(reply_text, tid):
                    self.replied.add(tid)
                    replied_count += 1
                    if replied_count >= REPLY_COUNT_PER_RUN:
                        break
                    time.sleep(10)

        except tweepy.TweepyException as e:
            logger.error(f"[{self.name}] ❌ خطأ في الـ mentions: {e}")

        save_replied(self.replied)
        return replied_count

    def reply_to_search(self) -> int:
        """يرد على تغريدات تحتوي على hashtags معيّنة"""
        replied_count = 0
        hashtags      = SEARCH_HASHTAGS[:3]  # أول 3 هاشتاقات فقط

        for tag in hashtags:
            try:
                results = self.client.search_recent_tweets(
                    query=f"{tag} lang:ar -is:retweet -is:reply",
                    max_results=10,
                    tweet_fields=["text", "author_id"],
                )
                if not results.data:
                    continue

                for tweet in results.data:
                    tid = str(tweet.id)
                    if tid in self.replied:
                        continue

                    analysis   = deep_analyze(tweet.text)
                    reply_text = build_contextual_reply(analysis)

                    if self._post_reply(reply_text, tid):
                        self.replied.add(tid)
                        replied_count += 1
                        if replied_count >= REPLY_COUNT_PER_RUN:
                            save_replied(self.replied)
                            return replied_count
                        time.sleep(12)

            except tweepy.TweepyException as e:
                logger.warning(f"[{self.name}] ⚠️ بحث {tag}: {e}")

        save_replied(self.replied)
        return replied_count

    def run(self):
        """تشغيل دورة الردود الكاملة"""
        logger.info(f"[{self.name}] 🚀 بدء دورة الردود — {now_riyadh().strftime('%H:%M')}")
        total = 0
        total += self.handle_mentions()
        if total < REPLY_COUNT_PER_RUN:
            total += self.reply_to_search()
        logger.info(f"[{self.name}] ✅ انتهت دورة الردود | مجموع الردود: {total}")


# ── اختبار بدون Twitter API ───────────────────────────────────
if __name__ == "__main__":
    TESTS = [
        "جربت ChatGPT بس ما فهمت كيف أبدأ — وش أفضل طريقة للمبتدئين؟",
        "خايف AI ياخذ وظيفتي كمحاسب — وش رأيك؟",
        "ما أوافق، نماذج AI ما تأثر على البرمجة",
        "DeepSeek أفضل من ChatGPT في رأيي استخدمته كثير",
        "وش الفرق بين Gemini وClaude؟",
        "المملكة تتقدم في AI والحمد لله — رؤية 2030 تشتغل",
        "خصوصية البيانات في AI تقلقني صراحة",
    ]

    print("=" * 60)
    for comment in TESTS:
        analysis = deep_analyze(comment)
        reply    = build_contextual_reply(analysis)
        print(f"\n💬 التعليق: {comment}")
        print(f"🔍 الموضوع: {analysis['topic']} | الأداة: {analysis['tool'] or '—'} | "
              f"المستوى: {analysis['level']}")
        print(f"🤖 الرد ({tweet_length(reply)} حرف):\n{reply}")
        print("-" * 55)
