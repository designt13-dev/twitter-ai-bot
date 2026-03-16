# src/agents/content_agent.py  — النسخة v4 (بدون ترجمة آلية)
"""
وكيل الصياغة التفاعلية — v4
══════════════════════════════════════════════════════════════
الإصلاح الجذري:
  ❌ قبل: ترجمة Google Translate ركيكة → تشويه المعنى
  ✅ الآن: استخراج حقائق من الإنجليزية → حقن في قوالب سعودية مكتوبة يدوياً

المنهج:
  1. استخراج: شركة + أداة + فعل + رقم + فئة (regex + keyword maps)
  2. اختيار قالب سعودي مناسب لكل فئة (novelty / jobs / ksa / risk / funding)
  3. حقن الحقائق في القالب → تغريدة مكتملة 230-270 حرف
  4. تدقيق جودة: هوك واضح، ختام تفاعلي، لهجة سعودية، اكتمال الجملة

نمط التغريدة:
  ┌─────────────────────────────────────────────────────────┐
  │ [إيموجي] [هوك يثير الفضول — سطر واحد]                │
  │                                                         │
  │ [شركة/أداة] [فعل سعودي] [موضوع]                       │
  │                                                         │
  │ ← [حقيقة 1 مكتملة]                                     │
  │ ← [حقيقة 2 مكتملة]                                     │
  │                                                         │
  │ [سؤال سعودي تفاعلي] 💬                                 │
  └─────────────────────────────────────────────────────────┘
══════════════════════════════════════════════════════════════
"""
import re
import random
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from src.utils import logger, tweet_length

# ══════════════════════════════════════════════════════════════
# ①  خرائط استخراج الحقائق من العنوان الإنجليزي
# ══════════════════════════════════════════════════════════════

COMPANY_MAP = {
    "openai":      "OpenAI",
    "google":      "Google",
    "deepmind":    "DeepMind",
    "meta":        "Meta",
    "apple":       "Apple",
    "microsoft":   "Microsoft",
    "amazon":      "Amazon",
    "anthropic":   "Anthropic",
    "nvidia":      "Nvidia",
    "tesla":       "Tesla",
    "samsung":     "Samsung",
    "huawei":      "Huawei",
    "xai":         "xAI",
    "mistral":     "Mistral",
    "cohere":      "Cohere",
    "deepseek":    "DeepSeek",
    "perplexity":  "Perplexity",
    "stability":   "Stability AI",
    "runway":      "Runway",
    "adobe":       "Adobe",
    "salesforce":  "Salesforce",
    "ibm":         "IBM",
    "baidu":       "Baidu",
    "alibaba":     "Alibaba",
    "tencent":     "Tencent",
}

TOOL_MAP = {
    "chatgpt":           "ChatGPT",
    "gpt-4":             "GPT-4",
    "gpt-5":             "GPT-5",
    "gpt-4o":            "GPT-4o",
    "o3":                "o3",
    "o4":                "o4",
    "gemini":            "Gemini",
    "gemini 2":          "Gemini 2",
    "claude":            "Claude",
    "claude 4":          "Claude 4",
    "grok":              "Grok",
    "copilot":           "Copilot",
    "perplexity":        "Perplexity",
    "midjourney":        "Midjourney",
    "sora":              "Sora",
    "dall-e":            "DALL-E",
    "stable diffusion":  "Stable Diffusion",
    "llama":             "Llama",
    "mistral":           "Mistral",
    "deepseek":          "DeepSeek",
    "qwen":              "Qwen",
    "notebooklm":        "NotebookLM",
    "cursor":            "Cursor",
    "gemma":             "Gemma",
    "phi":               "Phi",
    "codeium":           "Codeium",
    "github copilot":    "GitHub Copilot",
    "devin":             "Devin",
    "replit":            "Replit AI",
}

# فعل إنجليزي → فعل سعودي
ACTION_MAP = {
    "launch":       "أطلق",
    "launches":     "أطلق",
    "launched":     "أطلق",
    "release":      "أصدر",
    "releases":     "أصدر",
    "released":     "أصدر",
    "announce":     "أعلن عن",
    "announces":    "أعلن عن",
    "announced":    "أعلن عن",
    "unveil":       "كشف عن",
    "unveils":      "كشف عن",
    "unveiled":     "كشف عن",
    "introduce":    "قدّم",
    "introduces":   "قدّم",
    "introduced":   "قدّم",
    "update":       "حدّث",
    "updates":      "حدّث",
    "updated":      "حدّث",
    "upgrade":      "طوّر",
    "upgrades":     "طوّر",
    "build":        "بنى",
    "builds":       "بنى",
    "deploy":       "نشر",
    "deploys":      "نشر",
    "raise":        "جمع",
    "raises":       "جمع",
    "raised":       "جمع",
    "fund":         "مُوِّل",
    "funded":       "مُوِّل",
    "invest":       "استثمر",
    "invests":      "استثمر",
    "layoff":       "تسريح",
    "layoffs":      "سرّح موظفين",
    "fire":         "سرّح",
    "fires":        "سرّح",
    "fired":        "سرّح",
    "cut":          "خفّض",
    "cuts":         "خفّض",
    "partner":      "تعاون مع",
    "partners":     "تعاون مع",
    "acquire":      "استحوذ على",
    "acquires":     "استحوذ على",
    "beat":         "تفوّق على",
    "beats":        "تفوّق على",
    "surpass":      "تجاوز",
    "surpasses":    "تجاوز",
    "open":         "فتح",
    "opens":        "فتح",
    "open-source":  "نشر بشكل مفتوح المصدر",
}

# أرقام ووحدات
NUMBER_RE = re.compile(
    r'(\$?\d[\d,\.]*)\s*(billion|million|thousand|%|x|times|'
    r'مليار|مليون|ألف|بالمئة|أضعاف)?',
    re.IGNORECASE
)

# ══════════════════════════════════════════════════════════════
# ②  قوالب التغريدات المكتوبة يدوياً — لكل فئة مجموعة قوالب
# ══════════════════════════════════════════════════════════════

# هوكس حسب الفئة
HOOKS = {
    "novelty": [
        "⚡️ خبر AI ما تبيه يفوتك",
        "🚀 شيء جديد في عالم الذكاء الاصطناعي",
        "🔥 تطور ما كنا نتوقعه بهالسرعة",
        "💥 إعلان يوم الحين — والكل يتحدث عنه",
        "🧠 خبر AI يستاهل توقف دقيقة",
        "⚡️ تحديث يغير المعادلة في عالم AI",
        "🚨 إطلاق جديد يستاهل الانتباه",
    ],
    "jobs": [
        "🚨 سؤال يشغل بال كثير منا الحين",
        "⚠️ خبر يخلي الواحد يفكر في مستقبله",
        "🔴 تحول يمس سوق العمل مباشرة",
        "💡 AI والوظائف — خبر جديد يستاهل",
        "🤔 تغيير في سوق الشغل — الصورة تتضح",
    ],
    "funding": [
        "💰 تمويل ضخم دخل عالم AI",
        "📈 أموال طائلة تتجه لـ AI",
        "💵 رقم ضخم يعكس حجم الثقة في AI",
        "🏦 استثمار كبير — والأرقام تعكس الاتجاه",
    ],
    "ksa": [
        "🇸🇦 المملكة في الخبر — تفاصيل تستاهل",
        "🚀 رؤية 2030 والذكاء الاصطناعي",
        "💡 المملكة مو متلقية — تبني وتطور",
        "🔥 SDAIA تتحرك — خبر جديد",
    ],
    "risk": [
        "⚠️ تحذير جدي من عالم AI — اقرأ قبل تمر",
        "🔴 جانب ما يتحدث عنه كثير في عالم AI",
        "🚨 مخاطر AI — الصورة الكاملة",
    ],
    "open_source": [
        "🧠 نموذج مفتوح المصدر جديد — والنتائج مفاجئة",
        "⚡️ نموذج AI مجاني يتفوق على المدفوع",
        "🔓 مفتوح المصدر يغير قواعد اللعبة",
    ],
    "general": [
        "🧠 خبر تقني يستاهل دقيقة من وقتك",
        "📌 من أخبار AI يوم الحين",
        "💻 تطور في عالم الذكاء الاصطناعي",
        "🌐 خبر AI ما يطلع كل يوم",
        "🎯 خبر يستاهل الانتباه في عالم التقنية",
        "⚙️ جديد في عالم AI — الفكرة ببساطة",
    ],
}

# قوالب الجسم — {C}=شركة، {T}=أداة، {A}=فعل، {N}=رقم
BODY_TEMPLATES = {
    "novelty": [
        "{C} {A} {T} — نموذج يعيد تشكيل توقعاتنا من AI",
        "{C} {A} {T} بقدرات جديدة تفوق ما كان متاحاً",
        "{C} {A} {T} — تحديث يستاهل تجربته",
        "{C} تكشف عن {T} بمزايا لم نشوفها من قبل",
        "الإعلان الرسمي: {C} {A} {T} بمستوى جديد",
    ],
    "jobs": [
        "{C} تسرّح {N} موظف — وهذا يثير تساؤلات جدية عن مستقبل الوظائف",
        "{C} تُقلّص فريقها البشري — {N} الأرقام تتحدث",
        "التحول الرقمي يتسارع — {C} تُعيد هيكلة العمل",
        "{C} و{N} موظف: الأتمتة تغير سوق الشغل بشكل غير مسبوق",
    ],
    "funding": [
        "{C} تجمع {N} — ثقة الأسواق في AI تكبر",
        "تمويل {N} لـ {C} — الرهان على AI يتسع",
        "{C} تستقطب {N} في جولة تمويل جديدة",
        "الأموال تتجه لـ {C}: {N} في أحدث جولة تمويل",
    ],
    "ksa": [
        "المملكة تتقدم — {C} {A} وثيق الصلة برؤية 2030",
        "{C} تدخل السوق السعودي بـ {T} — خطوة تستاهل المتابعة",
        "خطوة جديدة نحو رؤية 2030 في عالم AI — التفاصيل تستاهل",
        "SDAIA تُطلق مبادرة جديدة — AI في خدمة رؤية 2030",
    ],
    "risk": [
        "دراسة جديدة تكشف: {C} و{T} تطرح تساؤلات عن الأمان",
        "تحذيرات جدية من الاستخدام غير المقيد لـ {T}",
        "{C} تواجه انتقادات — والتفاصيل مقلقة",
    ],
    "open_source": [
        "{C} {A} {T} — متاح للجميع ويتفوق على المدفوع",
        "{T} مفتوح المصدر من {C} — النتائج تتحدث بنفسها",
        "{C} تنشر {T} مجاناً — ويبدو أنه يغير المعادلة",
    ],
    "general": [
        "{C} {A} {T} — خطوة جديدة في مسيرة AI",
        "{C} تكشف عن تطورات مهمة في عالم الذكاء الاصطناعي",
        "{T} من {C} — وهذا ما يعنيه لنا",
        "تطور جديد من {C} يستاهل المتابعة",
    ],
}

# نقاط الحقائق — {N}=رقم، {T}=أداة، {C}=شركة
FACT_POINTS = {
    "speed": [
        "السرعة تفوق النماذج السابقة بأشواط",
        "وقت الاستجابة أسرع {N} مرة من الجيل السابق",
        "الأداء {N} أسرع — وهذا يغير تجربة الاستخدام فعلياً",
        "معالجة أسرع = نتائج أفضل في وقت أقل",
    ],
    "cost": [
        "التكلفة انخفضت {N} — وهذا يفتح الباب لتطبيقات أوسع",
        "أرخص {N} من المنافسين — وهذا يغير قرار الاعتماد عليه",
        "سعر أقل = وصول أوسع لكل المطورين والشركات",
    ],
    "size": [
        "النموذج يضم {N} معامل — حجم لم نشوفه من قبل",
        "بـ {N} مليار معامل — يتجاوز ما كان يُعتقد ممكناً",
    ],
    "jobs": [
        "وظائف تتغير — اللي يتكيف اليوم يتقدم غداً",
        "{N} وظيفة تأثرت — والأرقام في ارتفاع",
        "التحول في سوق الشغل يسرّع — المهارات الجديدة هي الأمان",
        "من يتعلم AI اليوم يضمن مكانه في سوق الشغل غداً",
    ],
    "funding": [
        "هذا التمويل يعكس ثقة كبيرة في مستقبل AI",
        "الاستثمار الكبير = منافسة أشد في السوق",
        "أموال ضخمة تعني تطورات أسرع في المنتجات",
        "{N} دولار — الأكبر في قطاع AI هذا العام",
    ],
    "open_source": [
        "مفتوح المصدر يعني أي مطور يقدر يبني عليه",
        "يتفوق على نماذج مدفوعة — وهذا يغير قرار الشراء",
        "المجتمع التقني يقدر يطوره — وهذا يسرّع الابتكار",
    ],
    "ksa": [
        "يناسب أهداف رؤية 2030 في تطوير التقنية",
        "خطوة تعزز مكانة المملكة في خارطة AI العالمية",
        "SDAIA تقود هذا التحول — والنتائج ستظهر قريباً",
    ],
    "capability": [
        "يفهم النص والصوت والصورة في نفس الوقت",
        "قادر على استيعاب سياق أطول بكثير من السابق",
        "أداء أفضل في المهام المعقدة والتحليل العميق",
        "يحل مسائل كانت تستغرق ساعات في دقائق",
    ],
    "general": [
        "هذا يعني تطبيقات عملية أكثر في حياتنا اليومية",
        "التأثير سيصل لكثير من القطاعات — التقنية والتعليم والصحة",
        "AI يتقدم بشكل أسرع من كل التوقعات",
        "اللي يتابع التطورات الحين يفهم إلى وين يسير السوق",
    ],
}

# أسئلة الختام حسب الفئة
CLOSINGS = {
    "novelty": [
        "جربته؟ وش انطباعك؟ 💬",
        "وش رأيك — يستاهل التجربة؟",
        "من وجهة نظرك — مين يقود سباق AI الحين؟",
        "تشوف نفسك تستخدمه؟ وش أكثر ميزة تهمك؟",
        "وش أكثر شيء لفت نظرك فيه؟ 💬",
    ],
    "jobs": [
        "وش المهارة اللي تعتقد AI ما يقدر يعوّضها؟ 💬",
        "تشوف نفسك جاهز لهالتحول؟",
        "وش خطتك عشان تتكيف مع هذا التغيير؟",
        "برأيك — فرصة ولا تهديد؟ 💬",
    ],
    "funding": [
        "استثمار ذكي ولا فقاعة برأيك؟ 🤔",
        "وش القطاع اللي تراه الأكثر استفادة من هذا؟",
        "تشوف AI فرصة استثمارية حقيقية؟ 💬",
        "برأيك أين تذهب هذه الأموال بالضبط؟",
    ],
    "ksa": [
        "وش تتوقع من المملكة في AI خلال ٣ سنوات؟ 💬",
        "تشوف رؤية 2030 تحقق أهدافها في التقنية؟",
        "وش أكثر مبادرة تقنية سعودية تتابعها؟ 💬",
    ],
    "risk": [
        "وش الحل الأمثل برأيك — قيود أم توعية؟ 💬",
        "تشوف الفوائد أكبر من المخاطر؟",
        "وش أكثر مخاوفك من AI في حياتك اليومية؟ 💬",
    ],
    "open_source": [
        "تفضل مفتوح المصدر ولا المدفوع؟ وليش؟ 💬",
        "برأيك النماذج المفتوحة تهدد المدفوعة؟",
        "وش أبرز مشروع تشوف إنه يستفيد من هذا؟ 💬",
    ],
    "general": [
        "وش رأيكم؟ 💬",
        "يهمك هذا الخبر؟ وش تفكر؟",
        "كيف تشوف تأثيره على مجالك؟ 💬",
        "وش أكثر شيء يلفت انتباهك فيه؟",
        "تتوقع له تأثير على حياتك؟ شارك رأيك 💬",
    ],
}


# ══════════════════════════════════════════════════════════════
# ③  منطق استخراج الحقائق
# ══════════════════════════════════════════════════════════════

def _detect_company(text: str) -> str:
    t = text.lower()
    for key, name in COMPANY_MAP.items():
        if key in t:
            return name
    return ""


def _detect_tool(text: str) -> str:
    t = text.lower()
    # الأدوات المركّبة أولاً (gpt-4o, stable diffusion, etc.)
    for key in sorted(TOOL_MAP.keys(), key=len, reverse=True):
        if key in t:
            return TOOL_MAP[key]
    return ""


def _detect_action(text: str) -> str:
    t = text.lower()
    for key, val in sorted(ACTION_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(r'\b' + re.escape(key) + r'\b', t):
            return val
    return "أطلق"


def _detect_numbers(text: str) -> str:
    """يستخرج أبرز رقم من النص"""
    matches = NUMBER_RE.findall(text)
    if not matches:
        return ""
    # إعطاء الأولوية للأرقام الكبيرة (مليارات > ملايين > ...)
    priority = {"billion": 4, "million": 3, "مليار": 4, "مليون": 3,
                "%": 2, "x": 2, "times": 2, "thousand": 1, "ألف": 1}
    best = max(matches, key=lambda m: priority.get(m[1].lower(), 0) if m[1] else 0)
    num = best[0].replace(",", "")
    unit = best[1]
    unit_ar = {
        "billion": "مليار دولار",
        "million": "مليون",
        "thousand": "ألف",
        "%": "%",
        "x": "x",
        "times": "x",
        "مليار": "مليار",
        "مليون": "مليون",
    }.get(unit.lower() if unit else "", unit)
    return f"{num} {unit_ar}".strip()


def _detect_category(text: str, entities: dict) -> str:
    """يحدد فئة الخبر بدقة"""
    t = text.lower()
    company = entities.get("company", "").lower()
    
    # فئة مفتوح المصدر
    if any(w in t for w in ["open-source", "open source", "opensource", "open weights"]):
        return "open_source"
    
    # فئة التمويل
    if any(w in t for w in ["raise", "raises", "raised", "funding", "billion", "million",
                             "invest", "valuation", "venture", "series a", "series b"]):
        if any(w in t for w in ["billion", "million", "$"]):
            return "funding"
    
    # فئة الوظائف
    if any(w in t for w in ["layoff", "layoffs", "fired", "cut jobs", "job", "workforce",
                             "employees", "workers", "automation replac"]):
        return "jobs"
    
    # فئة السعودية
    if any(w in t for w in ["saudi", "ksa", "riyadh", "vision 2030", "sdaia", "neom",
                             "aramco", "sabic", "stc"]):
        return "ksa"
    
    # فئة المخاطر
    if any(w in t for w in ["risk", "danger", "warning", "concern", "ban", "regulate",
                             "safety", "harm", "bias", "misinformation"]):
        return "risk"
    
    # فئة الإطلاق (الافتراضي للجديد)
    if any(w in t for w in ["launch", "release", "unveil", "announce", "new", "introduce",
                             "debut", "first", "update", "upgrade"]):
        return "novelty"
    
    return "general"


def _select_fact_type(category: str, number: str, text: str) -> str:
    """يختار نوع نقطة الحقيقة المناسبة"""
    t = text.lower()
    if category == "jobs":
        return "jobs"
    if category == "funding":
        return "funding"
    if category == "ksa":
        return "ksa"
    if category == "open_source":
        return "open_source"
    if "faster" in t or "speed" in t or "quicker" in t:
        return "speed"
    if "cheaper" in t or "cost" in t or "price" in t or "afford" in t:
        return "cost"
    if "billion parameter" in t or "parameter" in t:
        return "size"
    if "multimodal" in t or "image" in t or "audio" in t or "vision" in t:
        return "capability"
    return "general"


def _fill_template(template: str, company: str, tool: str, action: str, number: str) -> str:
    """يحقن الحقائق في القالب"""
    entity = tool or company or "AI"
    c = company or tool or "AI"
    t = tool or company or "نموذج AI"
    a = action or "أطلق"
    n = number or ""
    
    result = template
    result = result.replace("{C}", c)
    result = result.replace("{T}", t)
    result = result.replace("{A}", a)
    result = result.replace("{N}", n if n else "نتائج لافتة")
    result = result.replace("{E}", entity)
    return result.strip()


# ══════════════════════════════════════════════════════════════
# ④  ContentAgent الرئيسي
# ══════════════════════════════════════════════════════════════

class ContentAgent:
    """
    وكيل الصياغة التفاعلية v4 — بدون ترجمة آلية
    يأخذ مقالة مُحلَّلة من SearchAgent ويُنتج تغريدة احترافية.
    """

    def __init__(self):
        self.name = "ContentAgent-v4"

    def build_tweet(self, article: dict) -> str:
        """
        بناء تغريدة سعودية مكتملة من مقالة إنجليزية.
        يعتمد على استخراج الحقائق وقوالب مكتوبة يدوياً — لا ترجمة.
        """
        title_en   = article.get("title",   "") or ""
        summary_en = (article.get("summary", "") or "")[:400]
        full_text  = f"{title_en} {summary_en}"

        # ── ① استخراج الحقائق ─────────────────────────────
        entities   = article.get("entities", {})
        company    = entities.get("company", "") or _detect_company(full_text)
        tool       = entities.get("tool",    "") or _detect_tool(full_text)
        action     = _detect_action(full_text)
        number     = entities.get("number",  "") or _detect_numbers(full_text)
        category   = _detect_category(full_text, {"company": company, "tool": tool})

        # ── ② اختيار عناصر القالب ────────────────────────
        hook_pool    = HOOKS.get(category, HOOKS["general"])
        body_pool    = BODY_TEMPLATES.get(category, BODY_TEMPLATES["general"])
        closing_pool = CLOSINGS.get(category, CLOSINGS["general"])

        hook    = random.choice(hook_pool)
        body_t  = random.choice(body_pool)
        closing = random.choice(closing_pool)

        body = _fill_template(body_t, company, tool, action, number)

        # ── ③ اختيار نقطتين مناسبتين ─────────────────────
        fact_type = _select_fact_type(category, number, full_text)
        fact_pool = FACT_POINTS.get(fact_type, FACT_POINTS["general"])
        # نقطة عامة دائماً من "general" كاحتياطي
        general_pool = FACT_POINTS["general"]

        p1_raw = random.choice(fact_pool)
        p2_raw = random.choice([f for f in general_pool if f != p1_raw] or general_pool)

        p1 = _fill_template(p1_raw, company, tool, action, number)
        p2 = _fill_template(p2_raw, company, tool, action, number)

        # ── ④ تجميع التغريدة ─────────────────────────────
        # نمط A — كامل (هوك + جسم + نقطتين + ختام)
        tweet_a = f"{hook}\n\n{body}\n\n← {p1}\n← {p2}\n\n{closing}"
        if tweet_length(tweet_a) <= 270:
            return tweet_a

        # نمط B — بدون نقطة ثانية
        tweet_b = f"{hook}\n\n{body}\n\n← {p1}\n\n{closing}"
        if tweet_length(tweet_b) <= 270:
            return tweet_b

        # نمط C — هوك + جسم + ختام
        tweet_c = f"{hook}\n\n{body}\n\n{closing}"
        if tweet_length(tweet_c) <= 270:
            return tweet_c

        # نمط D — هوك مختصر + ختام مختصر
        short_close = random.choice(["وش رأيكم؟ 💬", "كيف تشوفونه؟", "رأيكم؟ 💬"])
        tweet_d = f"{hook}\n\n{body}\n\n{short_close}"
        if tweet_length(tweet_d) <= 270:
            return tweet_d

        # نمط E — طوارئ: قطع الجسم
        body_short = body[:140] if len(body) > 140 else body
        return f"{hook}\n\n{body_short}\n\n{short_close}"

    def audit_tweet(self, tweet_text: str) -> dict:
        """تدقيق جودة التغريدة"""
        issues = []
        length = tweet_length(tweet_text)

        if length < 180:
            issues.append(f"⚠️ قصيرة ({length} حرف)")
        elif length > 275:
            issues.append(f"❌ طويلة ({length} حرف)")

        lines = tweet_text.split('\n')
        first = lines[0] if lines else ""
        HOOK_EMOJIS = ['🚨','⚡','🔥','🚀','💥','⚠️','🔴','💡','📌','💻','⚙️','🌐','🎯',
                       '🧠','💰','📈','🏦','💵','🇸🇦','🤔','🔓','🔐']
        if not any(e in first for e in HOOK_EMOJIS):
            issues.append("⚠️ لا يوجد إيموجي في الهوك")

        if not any(c in tweet_text for c in ['؟', '💬', 'شاركونا', 'رأيك', 'وش']):
            issues.append("⚠️ لا يوجد ختام تفاعلي")

        if re.search(r'[،،]\s*$', tweet_text.strip()):
            issues.append("❌ تنتهي بجملة ناقصة")

        # تحقق من الجملة التي تبدأ بـ { (قالب لم يُملأ)
        if '{' in tweet_text or '}' in tweet_text:
            issues.append("❌ قالب غير مكتمل")

        score = max(0, 10 - len(issues) * 2)
        return {
            "length": length,
            "score":  score,
            "issues": issues,
            "passed": len(issues) == 0,
        }

    def build_batch(self, articles: list) -> list:
        """ينتج دفعة من التغريدات"""
        results = []
        for i, art in enumerate(articles, 1):
            tweet = self.build_tweet(art)
            audit = self.audit_tweet(tweet)
            logger.info(
                f"[{self.name}] #{i} | "
                f"{audit['length']} حرف | "
                f"جودة: {audit['score']}/10 | "
                f"{'✅' if audit['passed'] else '⚠️ ' + str(audit['issues'][:1])} | "
                f"{art.get('source','?')}"
            )
            results.append({
                "tweet":     tweet,
                "article":   art,
                "audit":     audit,
                "image_url": art.get("image_url"),
            })
        return results


# ── اختبار سريع ──────────────────────────────────────────────
if __name__ == "__main__":
    SAMPLES = [
        {
            "title":   "OpenAI launches GPT-5 with 10x faster inference and 50% lower cost",
            "summary": "OpenAI announced GPT-5 today, its most powerful model yet. "
                       "The new model is 10 times faster than GPT-4 and costs 50% less to use. "
                       "It supports multimodal inputs including text, images, and audio.",
            "source":  "TechCrunch",
            "entities": {"company": "OpenAI", "tool": "GPT-5",
                         "number": "10x", "category": "novelty"},
        },
        {
            "title":   "Meta raises $10 billion to fund AI research and new data centers",
            "summary": "Meta announced a $10 billion investment round to accelerate AI development.",
            "source":  "VentureBeat",
            "entities": {"company": "Meta", "tool": "",
                         "number": "$10 billion", "category": "funding"},
        },
        {
            "title":   "Google lays off 12,000 employees as AI automation grows",
            "summary": "Google announced layoffs of 12,000 employees citing AI-driven automation.",
            "source":  "The Verge",
            "entities": {"company": "Google", "tool": "",
                         "number": "12,000", "category": "jobs"},
        },
        {
            "title":   "DeepSeek releases open-source model that outperforms GPT-4",
            "summary": "DeepSeek released a new open-source model that benchmarks higher than GPT-4.",
            "source":  "Wired",
            "entities": {"company": "DeepSeek", "tool": "DeepSeek",
                         "number": "", "category": "novelty"},
        },
        {
            "title":   "Saudi Arabia launches national AI strategy with SDAIA",
            "summary": "Saudi Arabia unveiled a national AI strategy aligned with Vision 2030.",
            "source":  "Arab News",
            "entities": {"company": "SDAIA", "tool": "",
                         "number": "", "category": "ksa"},
        },
    ]

    agent = ContentAgent()
    print("=" * 60)
    for art in SAMPLES:
        tweet = agent.build_tweet(art)
        audit = agent.audit_tweet(tweet)
        print(f"\n📰 {art['title'][:55]}...")
        print(f"{'─'*55}")
        print(tweet)
        print(f"{'─'*55}")
        print(f"⟹ {audit['length']} حرف | جودة: {audit['score']}/10 | {'✅ نجح' if audit['passed'] else '⚠️ ' + str(audit['issues'])}")
        print()
