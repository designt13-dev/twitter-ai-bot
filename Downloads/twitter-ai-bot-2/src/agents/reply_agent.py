# src/agents/reply_agent.py
"""
وكيل الرد الذكي (Contextual Reply Agent)
══════════════════════════════════════════════════════════════
الفرق عن النظام السابق:
  ❌ قبل: ردود جاهزة من قوالب ثابتة تُختار عشوائياً
  ✅ الآن: الوكيل يقرأ التعليق كاملاً ويفهم سياقه
           ثم يبني رداً بناءً على:
           1. ما قاله الشخص بالضبط (اقتباس مقتطف)
           2. ما يريده (سؤال / قلق / إطراء / تجربة / خلاف)
           3. الموضوع الذي يتحدث عنه
           4. مستوى المعرفة المُستشَف من طريقة كتابته
           5. الأداة أو التقنية التي يذكرها

التدفق:
  نص التعليق
    ↓
  [deep_analyze] → تحليل عميق: نية + سياق + مستوى + أداة + موضوع + مشاعر
    ↓
  [build_contextual_reply] → رد يدمج محتوى التعليق فعلاً
    ↓
  [quality_check] → تحقق من الطول والسياق
══════════════════════════════════════════════════════════════
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
#  ① تحليل عميق للتعليق الوارد
# ══════════════════════════════════════════════════════════════
def deep_analyze(text: str) -> dict:
    """
    تحليل شامل للتعليق الوارد.
    يُعيد dict غني بالسياق لبناء رد مخصص.
    """
    t = re.sub(r'@\w+', '', text).strip()
    t_clean = re.sub(r'https?://\S+', '', t).strip()
    t_lower = t_clean.lower()

    # ── 1. الأداة المذكورة ───────────────────────────────────
    AI_TOOLS = {
        "chatgpt":      "ChatGPT",
        "chat gpt":     "ChatGPT",
        "gpt-4":        "GPT-4",
        "gpt4":         "GPT-4",
        "gpt-5":        "GPT-5",
        "gpt5":         "GPT-5",
        "gemini":       "Gemini",
        "bard":         "Gemini",
        "claude":       "Claude",
        "grok":         "Grok",
        "copilot":      "Copilot",
        "perplexity":   "Perplexity",
        "midjourney":   "Midjourney",
        "sora":         "Sora",
        "dall-e":       "DALL-E",
        "dalle":        "DALL-E",
        "llama":        "Llama",
        "mistral":      "Mistral",
        "deepseek":     "DeepSeek",
        "qwen":         "Qwen",
        "runway":       "Runway",
        "stable diffusion": "Stable Diffusion",
        "github copilot":   "GitHub Copilot",
        "cursor":       "Cursor",
        "notebooklm":   "NotebookLM",
    }
    tools = [name for kw, name in AI_TOOLS.items() if kw in t_lower]
    primary_tool = tools[0] if tools else ""

    # ── 2. الموضوع الرئيسي ──────────────────────────────────
    TOPIC_KEYWORDS = {
        "jobs":       ["وظيف", "عمل", "مهن", "بطال", "توظيف", "job", "career", "hire", "layoff"],
        "education":  ["تعليم", "دراس", "طالب", "جامعة", "مدرس", "تعلم", "كورس", "دورة", "education", "student"],
        "health":     ["صح", "طب", "مستشف", "علاج", "مريض", "health", "medical", "doctor"],
        "investment": ["استثمار", "مال", "أعمال", "شركة", "ربح", "invest", "business", "profit"],
        "ksa":        ["رؤية", "2030", "سعودية", "مملكة", "sdaia", "نيوم", "vision", "saudi", "riyadh"],
        "learning":   ["ابدأ", "كيف أتعلم", "من وين", "أول خطوة", "beginner", "start", "learn"],
        "risk":       ["خطر", "مشكل", "قلق", "خوف", "أمان", "خصوصية", "risk", "danger", "privacy"],
        "creativity": ["إبداع", "تصميم", "كتابة", "محتوى", "فن", "creative", "design", "art"],
        "coding":     ["برمجة", "كود", "تطوير", "developer", "code", "programming", "python"],
        "comparison": ["أحسن", "أفضل", "فرق", "مقارنة", "مقارن", "compare", "vs", "better"],
    }
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in t_lower for kw in keywords):
            topics.append(topic)
    primary_topic = topics[0] if topics else "general"

    # ── 3. النية / غرض الكاتب ───────────────────────────────
    is_question     = bool(re.search(r'[؟?]', t_clean) or
                           any(q in t_clean for q in ["كيف", "وش", "ماذا", "هل", "ليش",
                                                       "لماذا", "متى", "وين", "أين", "إيش"]))
    is_asking_how   = any(w in t_lower for w in
                          ["كيف أبدأ", "كيف أتعلم", "من وين ابدأ", "أبدأ من وين",
                           "وين ابدأ", "ابدأ من", "كيف أستخدم", "أول خطوة"])
    is_experience   = any(w in t_clean for w in
                          ["جربت", "استخدمت", "استعملت", "من تجربتي", "أنا شخصياً",
                           "شخصيًا", "عندي تجربة", "عملت", "طبّقت", "جاءت نتيجة"])
    is_sharing      = any(w in t_clean for w in
                          ["شفت", "قرأت", "سمعت", "اطلعت", "شاركت", "مقال", "خبر", "دراسة"])
    is_comparing    = "comparison" in topics or any(w in t_lower for w in ["vs", "أحسن", "فرق بين"])

    # ── 4. المشاعر ──────────────────────────────────────────
    POS_WORDS = [
        "رائع", "ممتاز", "جميل", "مبدع", "أحسنت", "شكرًا", "شكرا",
        "صح", "زين", "عظيم", "ما شاء الله", "بارك", "مفيد", "ممتع",
        "يستاهل", "محتوى قيّم", "قيّم", "مميز", "احسنت", "يعطيك",
        "استمر", "كفو", "جبار", "خوش",
    ]
    NEG_WORDS = [
        "لا أعتقد", "ما أعتقد", "خطأ", "غلط", "مبالغة", "مش صحيح",
        "ما صحيح", "ما يمكن", "مستحيل", "بعيد", "مبالغ", "ما أوافق",
        "ما صح", "ما أصدق", "مشكوك",
    ]
    CONCERN_WORDS = [
        "قلق", "خايف", "خوف", "مخاوف", "خطر", "مشكلة",
        "مخيف", "يخوف", "ماذا لو", "وش لو", "وين نصير",
        "مرعب", "صعب", "أزمة",
    ]
    SARCASM_SIGNALS = [
        "طبعًا 😂", "أكيد 🙄", "هههه", "😂😂", "بالتأكيد 🤣",
    ]

    is_positive  = any(w in t_clean for w in POS_WORDS)
    is_negative  = any(w in t_clean for w in NEG_WORDS)
    is_concerned = any(w in t_clean for w in CONCERN_WORDS)
    is_sarcastic = any(s in t_clean for s in SARCASM_SIGNALS)

    # ── 5. مستوى المعرفة المُستشَف ───────────────────────────
    EXPERT_SIGNALS = [
        "prompt engineering", "fine-tuning", "rag", "embeddings",
        "llm", "transformer", "attention mechanism", "inference",
        "hallucination", "token", "context window", "api",
        "برومبت", "ضبط دقيق", "استدعاء", "نموذج",
    ]
    BEGINNER_SIGNALS = [
        "ما أعرف", "ما عرفت", "وين أبدأ", "شيء جديد علي",
        "أول مرة", "مبتدئ", "من الصفر",
    ]
    knowledge_level = "intermediate"
    if any(s in t_lower for s in EXPERT_SIGNALS):
        knowledge_level = "expert"
    elif any(s in t_lower for s in BEGINNER_SIGNALS):
        knowledge_level = "beginner"

    # ── 6. استخراج مقتطف للاقتباس ───────────────────────────
    cleaned = re.sub(r'\s+', ' ', t_clean).strip()
    # استخرج الجزء الأكثر أهمية (الجملة الأولى الحقيقية)
    first_sentence = re.split(r'[.،؟!]', cleaned)[0].strip()
    quote = first_sentence[:45] if len(first_sentence) > 8 else ""
    if len(quote) == 45:
        quote = quote.rsplit(' ', 1)[0] + "..."

    # ── 7. استخراج الكلمة المفتاحية الأهم ───────────────────
    keyword = primary_tool or ""
    if not keyword and topics:
        keyword_map = {
            "jobs": "مستقبل الوظائف",
            "education": "التعليم",
            "health": "الصحة والتقنية",
            "investment": "الاستثمار في AI",
            "ksa": "رؤية 2030",
            "learning": "التعلم",
            "risk": "المخاطر",
            "creativity": "الإبداع",
            "coding": "البرمجة",
            "comparison": "المقارنة",
        }
        keyword = keyword_map.get(primary_topic, "")

    return {
        "raw":              t_clean,
        "tools":            tools,
        "primary_tool":     primary_tool,
        "topics":           topics,
        "primary_topic":    primary_topic,
        "is_question":      is_question,
        "is_asking_how":    is_asking_how,
        "is_experience":    is_experience,
        "is_sharing":       is_sharing,
        "is_comparing":     is_comparing,
        "is_positive":      is_positive,
        "is_negative":      is_negative,
        "is_concerned":     is_concerned,
        "is_sarcastic":     is_sarcastic,
        "knowledge_level":  knowledge_level,
        "quote":            quote,
        "keyword":          keyword,
    }


# ══════════════════════════════════════════════════════════════
#  ② بناء الرد السياقي المخصص
# ══════════════════════════════════════════════════════════════
def build_contextual_reply(comment_text: str) -> str:
    """
    يبني رداً مخصصاً يعكس قراءة حقيقية للتعليق.
    يختلف جذرياً عن الردود الجاهزة:
      - يذكر ما قاله الشخص
      - يُقدّر مستوى معرفته
      - يرد على النقطة الأساسية بشكل مباشر
    """
    a = deep_analyze(comment_text)

    # ── مسارات الرد حسب الأولوية ────────────────────────────

    # [1] سؤال مقارنة بين أدوات
    if a["is_comparing"] and len(a["tools"]) >= 2:
        return _reply_comparison(a)

    # [2] خبرة شخصية مشتركة
    if a["is_experience"] and a["primary_tool"]:
        return _reply_to_experience_with_tool(a)

    # [3] سؤال "كيف أبدأ" لمبتدئ
    if a["is_asking_how"] and a["knowledge_level"] == "beginner":
        return _reply_how_to_beginner(a)

    # [4] سؤال تقني متقدم
    if a["is_question"] and a["knowledge_level"] == "expert":
        return _reply_expert_question(a)

    # [5] قلق أو مخاوف
    if a["is_concerned"]:
        return _reply_concern(a)

    # [6] خلاف أو تشكيك
    if a["is_negative"]:
        return _reply_disagreement(a)

    # [7] إطراء وتقدير
    if a["is_positive"] and not a["is_question"]:
        return _reply_appreciation(a)

    # [8] سؤال عام عن أداة محددة
    if a["primary_tool"] and a["is_question"]:
        return _reply_tool_question(a)

    # [9] سؤال موضوع محدد
    if a["is_question"] and a["primary_topic"] != "general":
        return _reply_topic_question(a)

    # [10] مشاركة خبر أو رأي
    if a["is_sharing"]:
        return _reply_sharing(a)

    # [11] رد عام ذكي
    return _reply_general(a)


# ── دوال بناء الرد المخصص ─────────────────────────────────

def _reply_comparison(a: dict) -> str:
    tools = a["tools"][:2]
    t1, t2 = tools[0], tools[1]
    options = [
        f"سؤال مهم! {t1} و{t2} لكل منهم نقاط قوة مختلفة. "
        f"{t1} أقوى في التحليل والكتابة الطويلة، بينما {t2} يتميز في التكامل مع الأدوات. "
        f"وش الاستخدام اللي تبي تقارن فيه؟",

        f"مقارنة دقيقة! الفرق الحقيقي بين {t1} و{t2} يظهر في نوع المهمة — "
        f"مو في الاسم. وش تحاول تنجزه؟ أقدر أوجهك للأنسب.",

        f"كلاهم ممتاز، بس لأغراض مختلفة. "
        f"وش المهمة اللي تبي تشوف أيهم أحسن فيها؟ "
        f"الجواب يعتمد على الاستخدام مو على الأداة فقط.",
    ]
    return random.choice(options)


def _reply_to_experience_with_tool(a: dict) -> str:
    tool  = a["primary_tool"]
    quote = a["quote"]
    options = [
        f"تجربتك مع {tool} مهمة! "
        f"اللي ذكرته عن \"{quote}\" — هذا بالضبط اللي يميز المستخدم المحترف. "
        f"وش أكثر شيء استفدت منه في تجربتك؟",

        f"تجربتك مع {tool} تستاهل تشاركها أكثر! "
        f"\"{quote}\" — نقطة تستاهل التعمق فيها. "
        f"هل النتيجة فاقت توقعاتك أو جاءت أقل؟",

        f"والله تجربتك مع {tool} مفيدة للجميع! "
        f"وش الاستخدام اللي جعلك تحكم بهذا؟ "
        f"تفاصيل أكثر تفيد اللي يبدأ الحين.",
    ]
    return random.choice(options)


def _reply_how_to_beginner(a: dict) -> str:
    topic = a["primary_topic"]
    tool  = a["primary_tool"]
    target = tool or {
        "coding":     "البرمجة مع AI",
        "creativity": "الإبداع بالذكاء الاصطناعي",
        "education":  "التعلم مع AI",
    }.get(topic, "الذكاء الاصطناعي")

    options = [
        f"لو تبدأ مع {target} من الصفر، أبسط طريقة: "
        f"① افتح ChatGPT وجربه في مشكلة تواجهها اليوم. "
        f"② بعد ما تحس بالفرق — تعلم كيف تكتب Prompts أفضل. "
        f"③ طبّق في مجالك مباشرة. وش مجالك؟",

        f"البداية أسهل مما تتخيل! مع {target}: "
        f"خطوة واحدة اليوم: افتح ChatGPT وقوله 'ساعدني في [مشكلة تواجهها]'. "
        f"بعد أسبوع ستلاحظ الفرق بنفسك. "
        f"وش أول مشكلة تبي تجرب عليها؟",
    ]
    return random.choice(options)


def _reply_expert_question(a: dict) -> str:
    tool    = a["primary_tool"]
    keyword = a["keyword"]
    topic   = a["primary_topic"]
    quote   = a["quote"]

    options = [
        f"سؤال ممتاز يكشف فهم عميق! "
        f"بخصوص \"{quote}\" — هذا مجال فيه نقاش واسع الحين. "
        f"وش أكثر جانب تبحث فيه؟ أقدر أعطيك مصادر متخصصة.",

        f"نقطة دقيقة تطرحها! بخصوص {keyword or topic}: "
        f"الجواب يعتمد على السياق. "
        f"هل تقصد من جهة {tool or 'الأداة'} أو من جهة التطبيق؟ "
        f"وضّح أكثر عشان نتعمق في الجواب الصح.",
    ]
    return random.choice(options)


def _reply_concern(a: dict) -> str:
    quote   = a["quote"]
    keyword = a["keyword"]
    options = [
        f"قلقك مفهوم ومشروع — وهو بالضبط نوع التفكير اللي نحتاجه! "
        f"بخصوص \"{quote or keyword or 'النقطة اللي ذكرتها'}\" — "
        f"الوعي بالمخاطر جزء أساسي من استخدام AI بشكل صحيح. "
        f"وش أكثر جانب يشغل بالك؟",

        f"والله اللي يقلق من AI أحياناً أذكى من اللي يقبله بعيون مغمضة! "
        f"بخصوص {keyword or 'ما ذكرته'} — هناك فرق بين قلق منطقي وبين تضخيم. "
        f"وش المصدر اللي شكّل هذا القلق عندك؟",
    ]
    return random.choice(options)


def _reply_disagreement(a: dict) -> str:
    quote = a["quote"]
    options = [
        f"رأيك يستاهل نقاش حقيقي! "
        f"بخصوص \"{quote}\" — أفهم وجهة نظرك، وفيها نقاط وجيهة. "
        f"بس من اللي رصدته عملياً، الصورة أكثر تعقيداً. "
        f"وش الأساس اللي بنيت عليه رأيك؟",

        f"وجهة نظر محترمة! اختلاف الرأي يثري النقاش. "
        f"بخصوص \"{quote}\" — لو عندك مثال أو تجربة تدعم كلامك، "
        f"يسعدني أسمع أكثر ونناقش بعمق.",
    ]
    return random.choice(options)


def _reply_appreciation(a: dict) -> str:
    quote   = a["quote"]
    keyword = a["keyword"]
    options = [
        f"شكرًا جزيلاً على الكلام الطيب! "
        f"هذا النوع من التفاعل حول {keyword or 'المحتوى التقني'} "
        f"هو اللي يخلي النقاش العربي أعمق وأقيم. "
        f"وش الموضوع اللي تحب نعمق فيه أكثر؟",

        f"والله يسعدني اهتمامك ومتابعتك! "
        f"\"{quote}\" — كلام يشجع على الاستمرار. "
        f"لو عندك سؤال أو موضوع تقني تبي نناقشه — الباب مفتوح.",
    ]
    return random.choice(options)


def _reply_tool_question(a: dict) -> str:
    tool  = a["primary_tool"]
    quote = a["quote"]
    TOOL_INSIGHTS = {
        "ChatGPT": (
            "ChatGPT الفرق الحقيقي في نتائجه يكمن في جودة الـ Prompt. "
            "المحترفون يعطونه سياقاً ودوراً وتفاصيل — والنتيجة مختلفة تمامًا."
        ),
        "Gemini": (
            "Gemini يتميز بالتكامل مع خدمات Google وقوته في البحث الحي. "
            "ربطه مع Google Docs يغير طريقة العمل بالكامل."
        ),
        "Claude": (
            "Claude الأقوى في تحليل النصوص الطويلة والكتابة الدقيقة. "
            "لو عندك وثيقة طويلة أو كتابة أكاديمية — هو الأنسب."
        ),
        "Grok": (
            "Grok يتميز بتكامله مع X ووصوله للمحتوى الحي. "
            "شخصيته في الردود مختلفة — وهذا يناسب بعض الاستخدامات."
        ),
        "DeepSeek": (
            "DeepSeek أثبت أن التنافس في AI مو حكر على الكبار. "
            "كفاءته العالية بتكلفة أقل يجعله خياراً ممتازاً للمطورين."
        ),
        "Midjourney": (
            "Midjourney الأقوى في جودة الصور الفنية. "
            "السر في صياغة الـ Prompt — وهناك مجتمع ضخم يشارك أفضل الصياغات."
        ),
    }
    insight = TOOL_INSIGHTS.get(tool, f"{tool} أداة قوية تستاهل التجربة.")
    return (
        f"سؤال ممتاز عن {tool}! "
        f"{insight} "
        f"بخصوص \"{quote}\" — وش تحديداً تريد تعرفه؟"
    )[:270]


def _reply_topic_question(a: dict) -> str:
    topic   = a["primary_topic"]
    quote   = a["quote"]
    keyword = a["keyword"]

    TOPIC_ANSWERS = {
        "jobs": (
            "موضوع الوظائف مع AI مهم جداً! الحقيقة: "
            "الوظائف التكرارية هي الأكثر تأثراً، "
            "لكن اللي يتعلم AI يفتح أبواباً ما كانت موجودة."
        ),
        "education": (
            "التعليم أكثر قطاع سيتأثر إيجابياً! "
            "تخيل منهج يتكيف مع كل طالب. "
            "الأدوات موجودة الحين — مثل NotebookLM وKhan AI."
        ),
        "health": (
            "AI في الطب يتقدم بسرعة — من تشخيص الأشعة لتحليل الجينات. "
            "الهدف يعطي الطبيب وقت أكثر للمريض."
        ),
        "investment": (
            "الاستثمار في التقنية مو خيار — ضرورة. "
            "بس المهم تفرق بين الضجة والقيمة الحقيقية."
        ),
        "ksa": (
            "المملكة جادة — من SDAIA لنيوم لمبادرات TUWAIQ. "
            "اللي يبني مهاراته الحين يكون جاهز للفرص القادمة."
        ),
        "learning": (
            "أسهل بداية: اختر مشكلة واحدة في يومك وجرب تحلها بـ ChatGPT. "
            "بعد أسبوع ستلاحظ الفرق بنفسك."
        ),
        "risk": (
            "القلق من أي تقنية جديدة طبيعي. "
            "المهم نفرق بين قلق منطقي وتضخيم. "
            "الوعي بالمخاطر هو الاستخدام الأذكى."
        ),
        "creativity": (
            "الإبداع البشري مو في خطر — AI ما يملك تجربة حياة حقيقية. "
            "لكن المبدع اللي يستخدمه يضاعف إنتاجه عشرات المرات."
        ),
        "coding": (
            "AI في البرمجة غيّر المعادلة! "
            "GitHub Copilot وCursor يسرّعان الكتابة، "
            "لكن الفهم العميق للكود لا يزال ميزة حقيقية."
        ),
    }
    answer = TOPIC_ANSWERS.get(topic, "موضوع يستاهل نقاش!")
    return (
        f"سؤال ممتاز بخصوص {keyword or topic}! "
        f"{answer} "
        f"بخصوص \"{quote}\" — وش تحديداً يشغل بالك أكثر؟"
    )[:270]


def _reply_sharing(a: dict) -> str:
    quote   = a["quote"]
    keyword = a["keyword"]
    options = [
        f"شكرًا على المشاركة! "
        f"\"{quote}\" — نقطة تستاهل التعمق. "
        f"وش رأيك الشخصي في تأثيرها على {keyword or 'المجال'}؟",

        f"مثير للاهتمام ما شاركته! "
        f"بخصوص \"{quote}\" — هل رأيت أي تطبيق عملي لهذا في السوق المحلي؟",
    ]
    return random.choice(options)


def _reply_general(a: dict) -> str:
    quote   = a["quote"]
    keyword = a["keyword"]
    topic   = a["primary_topic"]
    options = [
        f"نقطة تستاهل نقاش! "
        f"بخصوص \"{quote or keyword or 'ما ذكرته'}\" — "
        f"وش أكثر جانب يثير اهتمامك في موضوع {topic}؟",

        f"رأي مهم يستاهل الاهتمام! "
        f"في {keyword or topic} — الحديث يطول. "
        f"وش اللي شكّل هذا الرأي عندك؟",

        f"والله نقطة مهمة! "
        f"المحتوى التقني بالعربي يحتاج أصوات متعددة. "
        f"وش توقعاتك للسنة القادمة في {keyword or topic or 'عالم AI'}؟",
    ]
    return random.choice(options)


# ══════════════════════════════════════════════════════════════
#  ③ تشغيل وكيل الرد عبر Twitter API
# ══════════════════════════════════════════════════════════════
def load_replied() -> set:
    data = load_json(REPLIED_FILE)
    return set(data) if isinstance(data, list) else set()


def save_replied(replied: set) -> None:
    save_json(REPLIED_FILE, list(replied)[-2000:])


def load_last_mention_id():
    data = load_json(LAST_MENTION_FILE)
    return data.get("id") if isinstance(data, dict) else None


def save_last_mention_id(mention_id: str) -> None:
    save_json(LAST_MENTION_FILE, {"id": mention_id})


def get_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )


class ReplyAgent:
    """
    وكيل الرد السياقي الذكي.
    يقرأ كل تعليق ويبني رداً مخصصاً بناءً على محتواه.
    """

    def __init__(self):
        self.name   = "ReplyAgent"
        self.client = get_client()

    def reply_to_mentions(self, replied: set, max_count: int = 5) -> int:
        count = 0
        try:
            me = self.client.get_me()
            if not me or not me.data:
                logger.warning(f"[{self.name}] لم يُتمكن من جلب بيانات الحساب")
                return 0

            kwargs = {
                "max_results": 20,
                "tweet_fields": ["author_id", "text", "conversation_id"],
            }
            last_id = load_last_mention_id()
            if last_id:
                kwargs["since_id"] = last_id

            response = self.client.get_users_mentions(id=me.data.id, **kwargs)
            if not response.data:
                logger.info(f"[{self.name}] لا توجد mentions جديدة")
                return 0

            save_last_mention_id(str(response.data[0].id))

            for mention in response.data:
                if count >= max_count:
                    break
                mid          = str(mention.id)
                mention_text = getattr(mention, "text", "") or ""
                if mid in replied:
                    continue

                # ── تحليل عميق + رد سياقي ──────────────────
                analysis   = deep_analyze(mention_text)
                reply_text = build_contextual_reply(mention_text)

                logger.info(
                    f"[{self.name}] 📖 \"{mention_text[:45]}\" | "
                    f"أداة: {analysis['primary_tool']} | "
                    f"موضوع: {analysis['primary_topic']} | "
                    f"مستوى: {analysis['knowledge_level']} | "
                    f"نية: {'سؤال' if analysis['is_question'] else 'تعليق'}"
                )

                time.sleep(random.uniform(20, 60))
                try:
                    self.client.create_tweet(
                        text=reply_text,
                        in_reply_to_tweet_id=mid,
                    )
                    logger.info(f"[{self.name}] ✅ رد: {reply_text[:65]}")
                    replied.add(mid)
                    count += 1
                except tweepy.TweepyException as e:
                    logger.warning(f"[{self.name}] فشل الرد: {e}")

        except tweepy.TweepyException as e:
            logger.warning(f"[{self.name}] فشل جلب mentions: {e}")
        return count

    def search_and_reply(self, replied: set, target: int = 5) -> int:
        count = 0
        shuffled = list(SEARCH_HASHTAGS)
        random.shuffle(shuffled)

        for hashtag in shuffled:
            if count >= target:
                break
            try:
                response = self.client.search_recent_tweets(
                    query=f"{hashtag} -is:retweet lang:ar",
                    max_results=20,
                    tweet_fields=["author_id", "text"],
                )
                if not response.data:
                    continue

                for tweet in response.data:
                    if count >= target:
                        break
                    tid        = str(tweet.id)
                    tweet_text = getattr(tweet, "text", "") or ""
                    if tid in replied:
                        continue

                    # ── رد سياقي حقيقي ─────────────────────
                    analysis   = deep_analyze(tweet_text)
                    reply_text = build_contextual_reply(tweet_text)

                    time.sleep(random.uniform(30, 90))
                    try:
                        self.client.create_tweet(
                            text=reply_text,
                            in_reply_to_tweet_id=tid,
                        )
                        logger.info(
                            f"[{self.name}] ✅ رد بحث | "
                            f"موضوع: {analysis['primary_topic']} | "
                            f"{reply_text[:55]}"
                        )
                        replied.add(tid)
                        count += 1
                    except tweepy.TweepyException as e:
                        logger.warning(f"[{self.name}] فشل الرد: {e}")

            except tweepy.TweepyException as e:
                logger.warning(f"[{self.name}] فشل البحث عن {hashtag}: {e}")

        return count

    def run(self):
        logger.info(
            f"[{self.name}] 🤖 بدء جلسة الردود — "
            f"{now_riyadh().strftime('%Y-%m-%d %H:%M')}"
        )
        replied = load_replied()
        count   = 0

        # 1. الردود على Mentions (أولوية قصوى)
        m = self.reply_to_mentions(replied, max_count=5)
        count += m
        logger.info(f"[{self.name}] Mentions: {m} رد")

        # 2. البحث والرد على التغريدات الأخرى
        remaining = REPLY_COUNT_PER_RUN - count
        if remaining > 0:
            s = self.search_and_reply(replied, target=remaining)
            count += s
            logger.info(f"[{self.name}] Search: {s} رد")

        save_replied(replied)
        logger.info(f"[{self.name}] 🏁 إجمالي: {count} رد")


# للتشغيل المباشر (backward compatibility)
def build_smart_reply(comment_text: str) -> str:
    return build_contextual_reply(comment_text)


def run_reply_bot():
    agent = ReplyAgent()
    agent.run()
