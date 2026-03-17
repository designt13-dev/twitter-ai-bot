# src/agents/content_agent.py — النسخة v6 (صياغة سعودية طبيعية، منشور كامل)
"""
وكيل الصياغة — v6
══════════════════════════════════════════════════════════════════
المشاكل التي حلّها v6:
  ❌ v5: القوالب تبدو آلية ومترجمة
  ❌ v5: حد 270 حرف يقطع الجمل
  ❌ v5: لا يدعم الفنون والاكتشافات بشكل كافٍ
  ❌ v5: الوكيل يُدقق أجزاء وليس المنشور كاملاً

التحسينات في v6:
  ✅ قوالب مكتوبة كأنها كلام إنسان سعودي حقيقي
  ✅ الحد الأقصى 280 حرف (حد تويتر الفعلي) — الأولوية لاكتمال المعنى
  ✅ التدقيق يشمل المنشور كاملاً (هوك + معلومة + سؤال)
  ✅ دعم كامل: AI + فنون + اكتشافات علمية
  ✅ صورة مع كل منشور

هيكل المنشور الإلزامي:
  ┌─────────────────────────────────────┐
  │ [إيموجي] هوك جذاب — سطر واحد       │
  │                                     │
  │ سطر معلومة أول — كامل المعنى       │
  │ سطر معلومة ثانٍ — يُضيف عمقاً     │
  │                                     │
  │ سؤال يدفع للتفاعل 💬               │
  └─────────────────────────────────────┘

الحد الأقصى الإجمالي: 280 حرف (لا اقتطاع للجمل)
══════════════════════════════════════════════════════════════════
"""
import re
import random
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from src.utils import logger, tweet_length

# ══════════════════════════════════════════════════════════════════
# خرائط الكيانات
# ══════════════════════════════════════════════════════════════════

COMPANY_MAP = {
    "openai": "OpenAI", "google": "Google", "deepmind": "DeepMind",
    "meta": "Meta", "apple": "Apple", "microsoft": "Microsoft",
    "amazon": "Amazon", "anthropic": "Anthropic", "nvidia": "Nvidia",
    "tesla": "Tesla", "samsung": "Samsung", "xai": "xAI",
    "mistral": "Mistral", "deepseek": "DeepSeek", "perplexity": "Perplexity",
    "stability": "Stability AI", "runway": "Runway", "adobe": "Adobe",
    "ibm": "IBM", "baidu": "Baidu", "alibaba": "Alibaba",
    "hugging face": "Hugging Face", "cohere": "Cohere", "sdaia": "SDAIA",
}

TOOL_MAP = {
    "chatgpt": "ChatGPT", "gpt-4": "GPT-4", "gpt-5": "GPT-5",
    "gpt-4o": "GPT-4o", "o3": "o3", "o4": "o4",
    "gemini": "Gemini", "claude": "Claude", "grok": "Grok",
    "copilot": "Copilot", "sora": "Sora", "dall-e": "DALL-E",
    "stable diffusion": "Stable Diffusion", "llama": "Llama",
    "deepseek": "DeepSeek", "midjourney": "Midjourney",
    "notebooklm": "NotebookLM", "cursor": "Cursor", "gemma": "Gemma",
}

ACTION_MAP = {
    "launches": "أطلق", "launched": "أطلق", "launch": "أطلق",
    "releases": "أصدر", "released": "أصدر",
    "announces": "أعلن", "announced": "أعلن",
    "unveils": "كشف عن", "unveiled": "كشف عن",
    "introduces": "قدّم", "introduced": "قدّم",
    "raises": "جمع", "raised": "جمع",
    "acquires": "استحوذ على", "acquired": "استحوذ على",
    "open-sources": "نشر مفتوح المصدر",
    "beats": "تفوّق على", "surpasses": "تجاوز",
    "layoffs": "سرّح موظفين", "lays off": "سرّح",
}

NUMBER_RE = re.compile(
    r'(\$?\d[\d,\.]*)[\s\-]*(billion|million|thousand|%|x\b|times)',
    re.IGNORECASE
)


def _detect_company(text: str) -> str:
    t = text.lower()
    for k, v in COMPANY_MAP.items():
        if k in t:
            return v
    return ""


def _detect_tool(text: str) -> str:
    t = text.lower()
    for k in sorted(TOOL_MAP, key=len, reverse=True):
        if k in t:
            return TOOL_MAP[k]
    return ""


def _detect_action(text: str) -> str:
    t = text.lower()
    for k in sorted(ACTION_MAP, key=len, reverse=True):
        if k in t:
            return ACTION_MAP[k]
    return "أطلق"


def _detect_number(text: str) -> str:
    m = NUMBER_RE.findall(text)
    if not m:
        return ""
    unit_ar = {
        "billion": "مليار دولار", "million": "مليون دولار",
        "thousand": "ألف", "%": "%", "x": "ضعف", "times": "ضعف"
    }
    best = m[0]
    num = best[0].replace(",", "")
    unit = unit_ar.get(best[1].lower(), best[1])
    return f"{num} {unit}".strip()


def _detect_category(title: str, summary: str) -> str:
    t = (title + " " + summary).lower()
    if any(w in t for w in ["art", "museum", "creative", "design", "fashion",
                              "architecture", "painting", "sculpture", "فن",
                              "متحف", "تصميم", "إبداع", "لوحة"]):
        return "arts"
    if any(w in t for w in ["open-source", "open source", "open weights", "opensource"]):
        return "open_source"
    if any(w in t for w in ["billion", "million", "funding", "raise", "invest",
                              "valuation", "تمويل", "استثمار"]):
        return "funding"
    if any(w in t for w in ["layoff", "fired", "cut jobs", "job loss", "workforce",
                              "تسريح", "وظيف", "automation replac"]):
        return "jobs"
    if any(w in t for w in ["saudi", "ksa", "riyadh", "vision 2030", "sdaia",
                              "سعودي", "المملكة", "رؤية", "2030"]):
        return "ksa"
    if any(w in t for w in ["discover", "research", "study", "found", "science",
                              "space", "اكتشاف", "علم", "فضاء", "دراسة"]):
        return "discovery"
    if any(w in t for w in ["risk", "danger", "warning", "ban", "regulate",
                              "safety", "خطر", "تحذير", "تنظيم"]):
        return "risk"
    return "novelty"


# ══════════════════════════════════════════════════════════════════
# قوالب المنشور الكاملة — مكتوبة بلهجة سعودية طبيعية جداً
# هيكل كل قالب: hook + body1 + body2 + q
# الحد الأقصى الإجمالي: 280 حرف
# ══════════════════════════════════════════════════════════════════

FULL_TEMPLATES = {

    # ── الذكاء الاصطناعي: إطلاق جديد ──────────────────────────
    "novelty": [
        {
            "hook":  "⚡️ {C} أطلقت {T} — والأرقام تقول كل شيء",
            "body1": "{T} يعمل بسرعة {N} أسرع من السابق، وأُتيح للجميع الآن.",
            "body2": "الجديد إنه يفهم السياق بشكل أعمق ويدعم العربية بشكل أفضل.",
            "q":     "وش أول شيء تجربه فيه؟ 💬",
        },
        {
            "hook":  "🚀 {C} تعلن {T} — ما توقعنا هذا الوقت",
            "body1": "النموذج الجديد يتفوق على كل ما قبله في الأداء والسرعة بفرق واضح.",
            "body2": "أكثر شيء يلفت إن السعر انخفض — وهذا يعني وصول أوسع لعموم الناس.",
            "q":     "هل تشوف أن سباق AI ينفعنا أو يخوّفنا؟ 💬",
        },
        {
            "hook":  "🔥 خبر AI ما تبيه يفوتك",
            "body1": "{C} {A} {T}، وهو يقدر الآن يحل مسائل كانت تستغرق ساعات في دقائق.",
            "body2": "المطورون بدأوا يبنون عليه تطبيقات حقيقية من أول يوم — وهذا مو كلام.",
            "q":     "جربته؟ شاركنا انطباعك 💬",
        },
        {
            "hook":  "💥 إعلان يستاهل تقف عنده",
            "body1": "{C} أعلنت رسمياً عن {T} بعد أشهر اختبار — والآن متاح للجمهور.",
            "body2": "المميز فيه إنه يدعم مهام متعددة في نفس الوقت مع دقة أعلى من المنافسين.",
            "q":     "تشوف نفسك تستخدمه في عملك؟ كيف؟ 💬",
        },
        {
            "hook":  "🧠 تطور AI جديد — والكل يتكلم عنه",
            "body1": "{T} من {C} يكسر التوقعات: أداء يتجاوز {N} مقارنة بالإصدار السابق.",
            "body2": "التحسين مو بس في الأرقام — المستخدمون يقولون التجربة تحسّنت فعلياً.",
            "q":     "مين يقود سباق AI الحين من وجهة نظرك؟ 💬",
        },
    ],

    # ── تمويل ──────────────────────────────────────────────────
    "funding": [
        {
            "hook":  "💰 {C} جمعت {N} — الرهان على AI يكبر",
            "body1": "هذا التمويل يجعل {C} الأكثر تمويلاً في AI هذا العام بفرق كبير.",
            "body2": "المستثمرون يراهنون على النمو طويل الأمد — والأرقام تعكس ثقة حقيقية.",
            "q":     "استثمار ذكي ولا فقاعة برأيك؟ 🤔",
        },
        {
            "hook":  "📈 {N} تتجه لـ {C} — وهذا يقول كثير",
            "body1": "جولة التمويل ترفع تقييم {C} لمستويات لم نشوفها من قبل في القطاع.",
            "body2": "الإنفاق على AI في العالم تجاوز كل التوقعات — ونحن في بداية الموجة.",
            "q":     "وش القطاع اللي يستفيد أكثر من هذا التمويل؟ 💬",
        },
    ],

    # ── وظائف ──────────────────────────────────────────────────
    "jobs": [
        {
            "hook":  "🚨 {C} و{N} موظف — سؤال يشغل بالي",
            "body1": "{C} أعلنت تسريح {N} موظف وذكرت الأتمتة كسبب رئيسي لإعادة الهيكلة.",
            "body2": "اللي يتعلم يعمل مع AI في مجاله — مو ضده — هو اللي يحمي مكانه.",
            "q":     "وش المهارة اللي تعتقد إن AI ما يقدر يعوّضها؟ 💬",
        },
        {
            "hook":  "⚠️ AI والوظائف — الصورة بدأت تتضح",
            "body1": "دراسة حديثة: {N} من الوظائف الحالية ستتغير جوهرياً خلال 5 سنوات.",
            "body2": "لكن نفس الدراسة تؤكد إن AI سيخلق أدواراً جديدة لم تكن موجودة أصلاً.",
            "q":     "تشوف نفسك مستعداً لهذا التحول؟ وش خطتك؟ 💬",
        },
    ],

    # ── مفتوح المصدر ───────────────────────────────────────────
    "open_source": [
        {
            "hook":  "🔓 {C} تفتح {T} للجميع — وهذا يغير المعادلة",
            "body1": "{T} أصبح مفتوح المصدر ويتفوق على نماذج مدفوعة بآلاف الدولارات شهرياً.",
            "body2": "أي مطور أو شركة صغيرة تقدر الحين تبني تطبيقات AI متقدمة بدون تكاليف.",
            "q":     "تفضل مفتوح المصدر ولا المدفوع؟ وليش؟ 💬",
        },
        {
            "hook":  "🧠 نموذج مجاني يتفوق على المدفوع",
            "body1": "{C} أصدرت {T} مفتوح المصدر وتفوّق على نماذج تطلب اشتراكاً شهرياً.",
            "body2": "المجتمع التقني طوّره في ساعات — الذكاء الجماعي أقوى من أي شركة منفردة.",
            "q":     "النماذج المفتوحة ستهزم المدفوعة نهاية المطاف؟ 💬",
        },
    ],

    # ── السعودية ───────────────────────────────────────────────
    "ksa": [
        {
            "hook":  "🇸🇦 المملكة تتحرك في AI — خبر يستاهل",
            "body1": "خطوة جديدة نحو رؤية 2030: مبادرة تقنية تطوّر حلول AI للسوق العربي.",
            "body2": "SDAIA تقود هذا التحول والمملكة أصبحت وجهة جدية للشركات التقنية الكبرى.",
            "q":     "وش تتوقع المملكة تحقق في AI خلال ٣ سنوات؟ 💬",
        },
        {
            "hook":  "💡 السعودية + AI = مستقبل واعد",
            "body1": "{C} شريك استراتيجي جديد للمملكة في مشاريع الذكاء الاصطناعي الوطنية.",
            "body2": "الاستثمار السعودي في التقنية يتسارع — ورؤية 2030 تحوّل المشهد فعلاً.",
            "q":     "وش المجال اللي تتمنى AI يطوّره في المملكة أولاً؟ 💬",
        },
    ],

    # ── فنون وثقافة ────────────────────────────────────────────
    "arts": [
        {
            "hook":  "🎨 AI والفنون — حدود بدأت تتلاشى",
            "body1": "أدوات AI تولّد أعمالاً فنية احترافية من وصف نصي بسيط في ثوانٍ معدودة.",
            "body2": "الجدل لا يزال قائماً: هل يُثري عالم الفن أم يُهدد الفنانين؟ الإجابة: الاثنين معاً.",
            "q":     "تشوف AI شريك للفنان ولا منافس له؟ 💬",
        },
        {
            "hook":  "🖼️ اكتشاف فني يستاهل الانتباه",
            "body1": "باحثون استخدموا AI لكشف لوحة مخفية تحت طبقات الطلاء في عمل عمره أكثر من 400 سنة.",
            "body2": "التقنية تقرأ الطبقات بدون لمس اللوحة — وهذا يفتح بابًا جديداً لدراسة تاريخ الفن.",
            "q":     "وش أكثر اكتشاف فني يسحرك؟ 💬",
        },
        {
            "hook":  "✨ إبداع + تقنية = مستقبل الفنون",
            "body1": "معرض فني في {C} يجمع الفن التقليدي مع AI في تجربة تفاعلية غير مسبوقة.",
            "body2": "الزوار يتفاعلون بأجسادهم والـ AI يُعيد رسم اللوحة في الوقت الحقيقي.",
            "q":     "لو كنت هناك — كيف تحب تتفاعل مع العمل الفني؟ 💬",
        },
        {
            "hook":  "🌍 عالم الفن يتغيّر — وأنت؟",
            "body1": "متاحف عالمية كبرى بدأت توظّف AI لاستعادة أعمال فنية تالفة بدقة مذهلة.",
            "body2": "ما كان ممكناً قبل عشر سنوات يصير الآن في دقائق — التقنية أعادت كنوزاً ضائعة.",
            "q":     "تحب تزور معرضاً فنياً يعمل بـ AI؟ وش انطباعك؟ 💬",
        },
    ],

    # ── اكتشافات علمية ─────────────────────────────────────────
    "discovery": [
        {
            "hook":  "🔭 اكتشاف علمي يخلّي الواحد يفكر",
            "body1": "باحثون استخدموا AI لاكتشاف {T} جديد — وهذا يُعيد رسم نظريات علمية قديمة.",
            "body2": "ما يبهر إن الـ AI وصل للنتيجة في أسابيع بعد أن عجز العلماء عقوداً بالطرق التقليدية.",
            "q":     "وش أكثر اكتشاف علمي غيّر نظرتك للعالم؟ 💬",
        },
        {
            "hook":  "🌍 العلم لا يتوقف — اكتشاف جديد",
            "body1": "دراسة حديثة تكشف عن {T} لم يكن معروفاً من قبل وتتحدى مفاهيم درسناها.",
            "body2": "الـ AI حلّل بيانات كانت تستغرق عقوداً — أنجزها الآن في أيام معدودة.",
            "q":     "هل يجذبك عالم الاكتشافات؟ وش المجال اللي يثير فضولك أكثر؟ 💬",
        },
    ],

    # ── مخاطر ─────────────────────────────────────────────────
    "risk": [
        {
            "hook":  "⚠️ تحذير جدي من عالم AI — اقرأ قبل تمر",
            "body1": "دراسة جديدة: {T} يُنتج معلومات خاطئة في {N} من الحالات تحت ضغط أسئلة معينة.",
            "body2": "الحل مو إيقاف AI — بل تطوير التفكير النقدي والتحقق دائماً من المعلومات المهمة.",
            "q":     "وش أكثر شيء يقلقك من الاعتماد على AI؟ 💬",
        },
        {
            "hook":  "🔴 AI والمخاطر — محادثة لازم نخوضها",
            "body1": "خبراء يحذرون إن التوسع السريع في AI بدون تنظيم يخلق مخاطر ما ندركها الحين.",
            "body2": "لكن التنظيم المفرط يُبطئ الابتكار — والتوازن هو التحدي الحقيقي أمام الحكومات.",
            "q":     "تشوف التنظيم ضرورة ولا عائق للتقدم؟ 💬",
        },
    ],

    # ── عام ────────────────────────────────────────────────────
    "general": [
        {
            "hook":  "🧠 خبر AI يستاهل دقيقة من وقتك",
            "body1": "{C} {A} {T} — وهذا يُعيد رسم توقعاتنا من الذكاء الاصطناعي هذا العام.",
            "body2": "التأثير مو بس تقني — التعليم والصحة والأعمال ستشعر به قريباً جداً.",
            "q":     "كيف تشوف تأثيره على مجالك تحديداً؟ 💬",
        },
        {
            "hook":  "📌 من أخبار AI اليوم — شيء لفت نظري",
            "body1": "{C} تطوّر {T} ليكون أكفأ وأقل استهلاكاً للطاقة — تحدٍّ كان معلقاً سنوات.",
            "body2": "الاستدامة جزء أساسي من محادثة AI الآن — تشغيل النماذج الكبيرة يكلّف طاقة ضخمة.",
            "q":     "هل تفكر في التأثير البيئي لـ AI؟ 💬",
        },
        {
            "hook":  "💡 تطور هادئ — لكن تأثيره ضخم",
            "body1": "{C} تُحسّن {T} بشكل تدريجي — والنتائج الجديدة تفاجئ حتى المتخصصين.",
            "body2": "التقدم الحقيقي في AI أحياناً مو في الإعلانات الكبيرة — بل في التحسينات اليومية.",
            "q":     "وش التطور في AI أثّر فيك شخصياً أكثر؟ 💬",
        },
    ],
}

# الحد الأقصى للتغريدة بالحروف
MAX_TWEET_CHARS = 280


# ══════════════════════════════════════════════════════════════════
# ContentAgent v6
# ══════════════════════════════════════════════════════════════════

class ContentAgent:
    """
    وكيل الصياغة v6 — منشور كامل المعنى، لهجة سعودية حقيقية.
    الوكيل يُدقق المنشور كاملاً (هوك + معلومتان + سؤال) قبل النشر.
    """

    def __init__(self):
        self.name = "ContentAgent-v6"

    # ── بناء المنشور ──────────────────────────────────────────
    def build_tweet(self, article: dict) -> str:
        title   = article.get("title",   "") or ""
        summary = (article.get("summary", "") or "")[:600]
        full    = f"{title} {summary}"

        entities = article.get("entities", {})
        company  = entities.get("company", "") or _detect_company(full)
        tool     = entities.get("tool",    "") or _detect_tool(full)
        action   = _detect_action(full)
        number   = entities.get("number",  "") or _detect_number(full)
        category = entities.get("category", "") or _detect_category(title, summary)

        pool = FULL_TEMPLATES.get(category, FULL_TEMPLATES["general"])
        tpl  = random.choice(pool)

        c = company or tool or "الشركة"
        t = tool or company or "النموذج"
        n = number or "نتائج لافتة"

        # للفنون والاكتشافات: تجنب قوالب تتطلب شركة/أداة محددة إذا لم تُكتشف
        if category in ("arts", "discovery") and not company and not tool:
            # اختر قالباً لا يحتوي {C} أو {T} في body1
            static_pool = [tpl_ for tpl_ in pool
                           if '{C}' not in tpl_['body1'] and '{T}' not in tpl_['body1']]
            if static_pool:
                tpl = random.choice(static_pool)

        def fill(s: str) -> str:
            return (s.replace("{C}", c)
                     .replace("{T}", t)
                     .replace("{A}", action)
                     .replace("{N}", n))

        hook  = fill(tpl["hook"])
        body1 = fill(tpl["body1"])
        body2 = fill(tpl["body2"])
        q     = fill(tpl["q"])

        # تجميع المنشور كاملاً أولاً
        tweet = f"{hook}\n\n{body1}\n{body2}\n\n{q}"

        # إذا تجاوز الحد الأقصى — اختصر body2 عند آخر علامة ترقيم طبيعية
        if tweet_length(tweet) > MAX_TWEET_CHARS:
            b2 = body2
            for punct in ['—', '،', '.']:
                pos = b2.rfind(punct, 20, 100)
                if pos > 20:
                    b2 = b2[:pos].strip()
                    break
            else:
                b2 = b2[:90].strip()
            tweet = f"{hook}\n\n{body1}\n{b2}\n\n{q}"

        # إذا لا يزال طويلاً — أبقِ body1 فقط (جملة واحدة أفضل من جملة مقطوعة)
        if tweet_length(tweet) > MAX_TWEET_CHARS:
            tweet = f"{hook}\n\n{body1}\n\n{q}"

        return tweet

    # ── تدقيق المنشور كاملاً ─────────────────────────────────
    def audit_tweet(self, tweet_text: str) -> dict:
        """
        يُدقق المنشور الكامل — لا يُقيّم الأجزاء منفصلة.
        يتحقق من: الهوك + معلومتان + سؤال + طول معقول + لا قوالب فارغة.
        """
        issues = []
        length = tweet_length(tweet_text)
        lines  = [l.strip() for l in tweet_text.split('\n') if l.strip()]

        # ── تحقق الطول ──────────────────────────────────────
        if length < 120:
            issues.append(f"⚠️ المنشور قصير جداً ({length} حرف) — يحتاج محتوى أكثر")
        if length > MAX_TWEET_CHARS:
            issues.append(f"❌ المنشور طويل ({length} حرف) — يتجاوز {MAX_TWEET_CHARS}")

        # ── تحقق الهوك (السطر الأول) ────────────────────────
        if lines:
            first_line = lines[0]
            HOOK_EMOJIS = list("⚡🚀🔥💥🧠💰📈🇸🇦⚠️🔴💡📌💻🎨🔭✨🔓🚨🖼️🌍")
            if not any(e in first_line for e in HOOK_EMOJIS):
                issues.append("⚠️ الهوك بدون إيموجي")
            if len(first_line) > 80:
                issues.append("⚠️ الهوك طويل — يجب أن يكون في سطر واحد مختصر")

        # ── تحقق وجود سؤال تفاعلي ───────────────────────────
        if '؟' not in tweet_text and '💬' not in tweet_text:
            issues.append("⚠️ لا يوجد سؤال تفاعلي في نهاية المنشور")

        # ── تحقق اكتمال المعلومة (سطرين على الأقل) ──────────
        HOOK_STARTS = ['⚡','🚀','🔥','💥','🧠','💰','📈','🇸','⚠','🔴','💡','📌','💻','🎨','🔭','✨','🔓','🚨','🖼','🌍','📡']
        def _is_q_line(ln):
            return '💬' in ln or (ln.strip().endswith('؟') and len(ln.strip()) < 70)
        content_lines = [l for l in lines if l and not any(l.startswith(em) for em in HOOK_STARTS) and not _is_q_line(l)]
        if len(content_lines) < 2:
            issues.append("⚠️ المعلومة أقل من سطرين — يحتاج محتوى أعمق")
            issues.append("⚠️ المعلومة أقل من سطرين — يحتاج محتوى أعمق")

        # ── تحقق عدم وجود قوالب فارغة ──────────────────────
        if '{' in tweet_text or '}' in tweet_text:
            issues.append("❌ قالب غير مكتمل — متغيرات لم تُملأ")

        # ── النتيجة النهائية ──────────────────────────────────
        score = max(0, 10 - len(issues) * 2)
        return {
            "length":  length,
            "score":   score,
            "issues":  issues,
            "passed":  len(issues) == 0,
            "summary": f"{length} حرف | {score}/10 | {'✅ ناجح' if not issues else ' | '.join(issues)}"
        }

    # ── معالجة دفعة من الأخبار ───────────────────────────────
    def build_batch(self, articles: list) -> list:
        results = []
        for i, art in enumerate(articles, 1):
            tweet = self.build_tweet(art)
            audit = self.audit_tweet(tweet)

            status = "✅" if audit["passed"] else f"⚠️ {audit['issues'][:1]}"
            logger.info(
                f"[{self.name}] #{i} | {audit['length']} حرف | "
                f"جودة: {audit['score']}/10 | {status} | "
                f"{art.get('source', '?')}"
            )

            results.append({
                "tweet":     tweet,
                "article":   art,
                "audit":     audit,
                "image_url": art.get("image_url") or "",
            })
        return results


# ── اختبار سريع ─────────────────────────────────────────────────
if __name__ == "__main__":
    SAMPLES = [
        {
            "title": "OpenAI launches GPT-5 with 10x faster inference and 50% lower cost",
            "summary": "OpenAI today unveiled GPT-5 claiming 10 times faster than GPT-4 with full multimodal support.",
            "source": "TechCrunch", "image_url": "https://example.com/img1.jpg",
            "entities": {"company": "OpenAI", "tool": "GPT-5", "number": "10 ضعف", "category": "novelty"},
        },
        {
            "title": "Meta raises $10 billion for new AI data centers",
            "summary": "Meta announced a massive $10 billion round to build AI infrastructure globally.",
            "source": "VentureBeat", "image_url": "https://example.com/img2.jpg",
            "entities": {"company": "Meta", "tool": "", "number": "10 مليار دولار", "category": "funding"},
        },
        {
            "title": "Google lays off 12,000 employees citing AI automation",
            "summary": "Google cutting 12000 jobs, saying AI-driven efficiency reduces need for large workforce.",
            "source": "The Verge", "image_url": "",
            "entities": {"company": "Google", "tool": "", "number": "12,000", "category": "jobs"},
        },
        {
            "title": "DeepSeek releases open-source model beating GPT-4 on all benchmarks",
            "summary": "DeepSeek open-sourced a model outperforming GPT-4 on coding, reasoning, and language tasks.",
            "source": "Wired", "image_url": "",
            "entities": {"company": "DeepSeek", "tool": "DeepSeek", "number": "", "category": "open_source"},
        },
        {
            "title": "AI art installation transforms visitor movement into live paintings at Louvre",
            "summary": "A new AI art show in Paris uses body movement to generate real-time paintings at the Louvre.",
            "source": "Artsy", "image_url": "https://example.com/art.jpg",
            "entities": {"company": "باريس", "tool": "", "number": "", "category": "arts"},
        },
        {
            "title": "Scientists use AI to discover new antibiotic compound defeating superbugs",
            "summary": "Researchers used deep learning to discover a new antibiotic that killed drug-resistant bacteria.",
            "source": "MIT Technology Review", "image_url": "https://example.com/science.jpg",
            "entities": {"company": "", "tool": "نموذج AI", "number": "", "category": "discovery"},
        },
    ]

    agent = ContentAgent()
    print("=" * 65)
    print(f"  اختبار {agent.name}")
    print("=" * 65)

    passed = 0
    for art in SAMPLES:
        tw = agent.build_tweet(art)
        au = agent.audit_tweet(tw)

        print(f"\n📰 {art['title'][:60]}")
        print("─" * 65)
        print(tw)
        print("─" * 65)
        print(f"⟹ {au['summary']}")
        if au["passed"]:
            passed += 1

    print("\n" + "=" * 65)
    print(f"النتيجة: {passed}/{len(SAMPLES)} منشور ناجح")
    print("=" * 65)
