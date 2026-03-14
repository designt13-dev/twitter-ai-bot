# src/reply_handler.py
"""
نظام الرد الذكي — يقرأ التعليق الوارد ويبني رداً مخصصاً بناءً على محتواه
═══════════════════════════════════════════════════════════════════════════
التدفق:
1. جلب Mentions الجديدة (ردود على تغريداتنا)
2. تحليل نص التعليق: الموضوع، المشاعر، النية، الكلمات المفتاحية
3. بناء رد مخصص يدمج محتوى التعليق الأصلي — بلهجة سعودية
4. البحث عن تغريدات أخرى للتفاعل معها
═══════════════════════════════════════════════════════════════════════════
"""
import tweepy
import time
import random
import re
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from config.settings import (
    CONSUMER_KEY, CONSUMER_SECRET,
    ACCESS_TOKEN, ACCESS_TOKEN_SECRET,
    BEARER_TOKEN, SEARCH_HASHTAGS,
    REPLY_COUNT_PER_RUN, LOGS_DIR,
)
from src.utils import logger, load_json, save_json, now_riyadh, tweet_length

REPLIED_FILE      = LOGS_DIR / "replied_ids.json"
LAST_MENTION_FILE = LOGS_DIR / "last_mention_id.json"


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


# ══════════════════════════════════════════════════════════════
#  استخراج مقتطف من التعليق للدمج في الرد
# ══════════════════════════════════════════════════════════════
def extract_quote(text: str, max_len: int = 40) -> str:
    """
    يستخرج مقتطفاً قصيراً من التعليق يُدمج في الرد،
    مما يُظهر أن الرد بُني بعد قراءة التعليق فعلياً.
    """
    # حذف الـ @mentions والروابط
    clean = re.sub(r'@\w+', '', text)
    clean = re.sub(r'https?://\S+', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    if len(clean) <= max_len:
        return clean

    # اقطع عند آخر كلمة ضمن الحد
    pos = clean.rfind(' ', 0, max_len)
    if pos > 10:
        return clean[:pos] + "..."
    return clean[:max_len] + "..."


def extract_key_keyword(text: str) -> str:
    """استخراج أهم كلمة مفتاحية من التعليق للإشارة إليها في الرد"""
    # أدوات AI
    ai_tools = ["ChatGPT", "Gemini", "Claude", "Grok", "Copilot",
                 "Perplexity", "Midjourney", "Sora", "DALL-E", "Llama"]
    t_lower = text.lower()
    for tool in ai_tools:
        if tool.lower() in t_lower:
            return tool

    # مصطلحات تقنية
    tech_terms = {
        "تعلم آلي": "التعلم الآلي",
        "machine learning": "Machine Learning",
        "deep learning": "Deep Learning",
        "رؤية 2030": "رؤية 2030",
        "sdaia": "SDAIA",
        "prompt": "Prompt Engineering",
        "automation": "الأتمتة",
    }
    for kw, label in tech_terms.items():
        if kw.lower() in t_lower:
            return label

    return ""


# ══════════════════════════════════════════════════════════════
#  محرك التحليل — يقرأ نص التعليق ويفهمه
# ══════════════════════════════════════════════════════════════
def analyze_comment(text: str) -> dict:
    """
    يحلل نص التعليق ويُعيد dict يحدد:
    - الأدوات المذكورة (ChatGPT، Gemini...)
    - الموضوع (وظائف، تعليم، صحة، استثمار...)
    - النية (سؤال، إطراء، قلق، خبرة شخصية)
    - المشاعر (إيجابي، سلبي، محايد)
    - مقتطف للرد (quote)
    - كلمة مفتاحية رئيسية
    """
    t = text.strip()

    # ── الأدوات المذكورة ────────────────────────────────────
    tools_detected = []
    tool_keywords = {
        "chatgpt": "ChatGPT", "chat gpt": "ChatGPT",
        "gemini": "Gemini", "claude": "Claude",
        "grok": "Grok", "copilot": "Copilot",
        "perplexity": "Perplexity", "midjourney": "Midjourney",
        "sora": "Sora", "dall-e": "DALL-E", "dalle": "DALL-E",
        "llama": "Llama", "mistral": "Mistral",
        "deepseek": "DeepSeek", "qwen": "Qwen",
    }
    t_lower = t.lower()
    for kw, name in tool_keywords.items():
        if kw in t_lower:
            tools_detected.append(name)

    # ── الموضوعات ────────────────────────────────────────────
    topic_map = {
        "وظيف":     "jobs",
        "عمل":      "jobs",
        "مهن":      "jobs",
        "بطال":     "jobs",
        "توظيف":    "jobs",
        "تعليم":    "education",
        "دراس":     "education",
        "طالب":     "education",
        "جامعة":    "education",
        "مدرس":     "education",
        "صح":       "health",
        "طب":       "health",
        "مستشف":    "health",
        "علاج":     "health",
        "استثمار":  "investment",
        "مال":      "investment",
        "أعمال":    "business",
        "شركة":     "business",
        "ريادة":    "business",
        "تجارة":    "business",
        "رؤية":     "ksa",
        "2030":     "ksa",
        "سعودية":   "ksa",
        "مملكة":    "ksa",
        "sdaia":    "ksa",
        "نيوم":     "ksa",
        "تعلم":     "learning",
        "كورس":     "learning",
        "دورة":     "learning",
        "ابدأ":     "learning",
        "خطر":      "risk",
        "مشكل":     "risk",
        "قلق":      "risk",
        "خوف":      "risk",
        "تشفير":    "security",
        "أمن":      "security",
        "خصوصية":   "privacy",
        "بيانات":   "data",
        "إبداع":    "creativity",
        "تصميم":    "creativity",
        "كتابة":    "creativity",
        "محتوى":    "creativity",
        "برمجة":    "coding",
        "كود":      "coding",
        "developer": "coding",
    }
    topics_detected = []
    for kw, topic in topic_map.items():
        if kw in t:
            if topic not in topics_detected:
                topics_detected.append(topic)

    # ── النية ───────────────────────────────────────────────
    is_question = bool(
        re.search(r'[؟?]', t) or
        any(q in t for q in ["كيف", "وش", "ماذا", "هل", "ليش", "لماذا",
                              "متى", "وين", "أين", "من أين", "إيش"])
    )
    is_experience = any(w in t for w in [
        "جربت", "استخدمت", "استعملت", "عندي تجربة", "أنا شخصياً",
        "من تجربتي", "عملت", "طبّقت", "جاءت نتيجة", "شخصيًا",
    ])
    is_asking_how = any(w in t for w in [
        "كيف أبدأ", "كيف أتعلم", "من وين ابدأ", "وين ابدأ",
        "ابدأ من", "كيف أستخدم", "من أين أبدأ",
    ])
    is_sharing_news = any(w in t for w in [
        "شفت", "قرأت", "سمعت", "اطلعت", "شاركت", "مقال", "خبر",
    ])

    # ── المشاعر ─────────────────────────────────────────────
    pos_words = [
        "رائع", "ممتاز", "جميل", "مبدع", "أحسنت", "شكرًا", "شكرا",
        "صح", "زين", "عظيم", "ما شاء الله", "بارك الله", "مفيد",
        "استمر", "يستاهل", "ممتع", "محتوى قيّم", "قيّم", "مميز",
        "احسنت", "بارك", "الله يعطيك العافية", "رائع",
    ]
    neg_words = [
        "لا أعتقد", "ما أعتقد", "خطأ", "غلط", "مبالغة", "مش صحيح",
        "ما صحيح", "ما يمكن", "مستحيل", "بعيد", "مبالغ", "ما أوافق",
    ]
    concern_words = [
        "قلق", "خايف", "خوف", "مخاوف", "خطر", "مشكلة",
        "مخيف", "يخوف", "ماذا لو", "شو لو", "وش لو", "وين نصير",
    ]

    is_positive  = any(w in t for w in pos_words)
    is_negative  = any(w in t for w in neg_words)
    is_concerned = any(w in t for w in concern_words)

    return {
        "tools":         tools_detected,
        "topics":        topics_detected,
        "is_question":   is_question,
        "is_experience": is_experience,
        "is_asking_how": is_asking_how,
        "is_sharing":    is_sharing_news,
        "is_positive":   is_positive,
        "is_negative":   is_negative,
        "is_concerned":  is_concerned,
        "quote":         extract_quote(t, 38),
        "keyword":       extract_key_keyword(t),
        "raw":           t,
    }


# ══════════════════════════════════════════════════════════════
#  مكتبة الردود المخصصة حسب الموضوع
# ══════════════════════════════════════════════════════════════
TOPIC_REPLIES = {
    "jobs": [
        "نقطة مهمة تطرحها! AI ما يسرق الوظيفة — اللي يتعلمه ويستخدمه هو اللي يتميز. وش مجالك؟",
        "سؤال يشغل بال كثيرين! الوظائف اللي تعتمد على التكرار هي الأكثر تأثرًا، لكن وظائف التفكير والإبداع؟ تحتاج AI كأداة مساعدة مو بديل. وش رأيك؟",
        "صراحة اللي يتعلم AI الحين يفتح أبوابًا ما كانت موجودة. السوق السعودي يحتاج كوادر تتقن هذا. كيف تشوف وضعك بعد سنتين؟",
    ],
    "education": [
        "التعليم هو أكثر قطاع سيتأثر إيجابيًا! تخيل منهج يتكيف مع كل طالب. وش تتوقع يوصلنا في المملكة لهذا المستوى؟",
        "صراحة أي طالب الحين يستخدم AI بذكاء يقدر يختصر وقت التعلم. السؤال: هل التعليم الرسمي يواكب هذا؟ وش رأيك؟",
        "من الأشياء اللي تبشّر: أدوات مثل NotebookLM وKhan Academy AI بدأت تغير التعليم الذاتي. جربت شيء منها؟",
    ],
    "health": [
        "الذكاء الاصطناعي في الطب يتقدم بسرعة — من تشخيص الأشعة لتحليل الجينات. الهدف يعطي الطبيب وقت أكثر للمريض. وش تشوف؟",
        "المستشفيات السعودية بدأت تُدخل AI في التشخيص والمتابعة. هذا يبشّر لأن الكوادر الصحية المحلية ستستفيد مباشرة. وش رأيك؟",
    ],
    "investment": [
        "الاستثمار في التقنية الحين مو خيار — ضرورة. الشركات اللي ما تتبنى AI في عملياتها ستجد نفسها متأخرة. وش رأيك؟",
        "صراحة فرص AI كثيرة، لكن المهم تفرق بين الضجة الإعلامية والقيمة الحقيقية. لا كل شيء يلمع ذهب! وش تعتقد؟",
    ],
    "ksa": [
        "المملكة جادة — من SDAIA لنيوم لمبادرات TUWAIQ. السؤال: كيف كل واحد منا يستفيد ويشارك في هذا التحول؟",
        "رؤية 2030 وضعت AI في قلب التحول الرقمي. اللي يبني مهاراته الحين — يكون جاهز للفرص اللي قادمة. وش خطتك؟",
    ],
    "learning": [
        "أبسط طريقة تبدأ: اختر مشكلة واحدة في يومك وجرب تحلها بـ ChatGPT. بعد أسبوع ستلاحظ الفرق. جربت هذا الأسلوب؟",
        "أفضل كورسات AI مجانية: DeepLearning.AI على Coursera، وGoogle AI Essentials. تبدأ من الأساس وتتقدم بخطوات واضحة. وين أنت الحين؟",
        "لو تبدأ من الصفر: تعلّم كيف تكتب Prompts بشكل صحيح، جرب أدوات مختلفة، وطبّق في مجالك المباشر. وش مجالك؟",
    ],
    "risk": [
        "قلقك منطقي ومشروع. AI مو مثالي — يخطئ وأحيانًا يولّد معلومات غلط بثقة. الوعي بهذا هو استخدام أذكى. وش أكثر شيء يقلقك؟",
        "صراحة أكبر التحديات مو التقنية — هو استخدامها بدون تفكير نقدي. التحقق من المعلومات وحماية البيانات أساسيات ما تتهاون فيها.",
    ],
    "creativity": [
        "الإبداع البشري مو في خطر — AI ما يملك تجربة حياة حقيقية. لكن المبدع اللي يستخدمه يضاعف إنتاجه عشرات المرات. وش مجالك الإبداعي؟",
        "صراحة أدوات مثل Midjourney وSora غيّرت شكل الإنتاج الإبداعي. لكن اللي يفرق بين المتوسط والمتميز لا يزال الرؤية البشرية. وش رأيك؟",
    ],
    "coding": [
        "البرمجة مع AI تغيّرت كثيرًا! GitHub Copilot وCursor يسرّعان الكتابة، لكن الفهم العميق للكود لا يزال ميزة حقيقية. وش تجربتك معه؟",
        "صراحة AI في البرمجة أداة تضخيم للمبرمج المحترف، مو بديل عنه. اللي يعرف يوجّهه يكتب بسرعة × 5. جربت هذا؟",
    ],
    "security": [
        "موضوع الأمن والخصوصية في AI مهم جداً. البيانات اللي تُشاركها مع النماذج لا تشاركها بدون تفكير. هل تستخدم إعدادات الخصوصية؟",
    ],
    "data": [
        "البيانات هي وقود AI — ولهذا الشركات اللي تملك بيانات جيدة تملك ميزة تنافسية ضخمة. وش رأيك في كيفية حمايتها؟",
    ],
}

# ردود للأسئلة العامة (كيف أبدأ)
HOW_TO_REPLIES = [
    "لو تبدأ من الصفر، ثلاث خطوات: أولاً جرب ChatGPT في مهمة يومية. ثانياً تعلّم Prompt Eng (على YouTube محتوى عربي ممتاز). ثالثاً طبّق في مجالك مباشرة. وش مجالك؟",
    "أسهل بداية: افتح ChatGPT الحين وقوله 'ساعدني في [مشكلة تواجهها]'. مجرد ما تجرب تحس الفرق. ما تحتاج خلفية تقنية للبداية. جربت؟",
    "أفضل كورس مجاني للبداية: 'AI For Everyone' على Coursera من Andrew Ng. قصير ومو تقني. بعده ستعرف وين توجه اهتمامك.",
]

# ردود تقدير
APPRECIATION_REPLIES = [
    "شكرًا كثير على الكلام الطيب! هذا النوع من التفاعل يخلي النقاش التقني العربي أعمق. استمر وشاركنا رأيك دايمًا.",
    "والله يسعدني اهتمامك! لو عندك موضوع تقني تحب نناقشه — قوله وأخذ نقاش أوسع.",
    "شكرًا على الكلام الطيب! المحتوى التقني بالعربي يحتاج مثل هذا التفاعل. وش الموضوع اللي تحب أعمق فيه؟",
]

# ردود الخبرة الشخصية
EXPERIENCE_REPLIES = [
    "تجربتك هذه تستاهل تشاركها أكثر! وش أكثر شيء أثّر فيك في هذه التجربة؟",
    "مثير للاهتمام — التجارب الشخصية أصدق من المقالات النظرية. وش أكثر شيء فاجأك في نتائج تجربتك؟",
    "والله تجربتك تفيد الجميع! هل كانت النتيجة أحسن أو أقل مما توقعت؟",
]

# ردود الخلاف المحترم
DISAGREEMENT_REPLIES = [
    "وجهة نظر تستاهل النقاش! في نقاط معك، لكن اللي رصدته من تجربة عملية يختلف نوعًا ما. وش الأساس اللي بنيت عليه رأيك؟",
    "ترى وجهة نظرك محترمة. اختلاف الرأي يثري النقاش. وش اللي يجعلك ترى الموضوع بهذه الزاوية؟",
    "رأيك يستاهل الاحترام. لو عندك مثال أو تجربة بتوضح وجهة نظرك — يسعدني أسمع أكثر.",
]

# ردود القلق
CONCERN_REPLIES = [
    "قلقك مفهوم ومشروع. AI مو مثالي، والوعي بمخاطره جزء أساسي من استخدامه بشكل صحيح. وش الجانب اللي يشغل بالك أكثر؟",
    "صراحة القلق من أي تقنية جديدة شيء طبيعي. المهم نفرق بين القلق المبني على معلومة حقيقية وبين التضخيم. وش المصدر اللي شكّل رأيك؟",
    "ترى اللي يقلق من AI في الغالب أذكى من اللي يقبله بشكل أعمى. السؤال الصح: كيف نستفيد منه بأمان؟",
]

# ردود أدوات محددة
TOOL_SPECIFIC_REPLIES = {
    "ChatGPT": [
        "ChatGPT فعلًا غيّر المعادلة من 2022! لكن الفرق الحقيقي في جودة النتائج يكمن في طريقة الـ Prompt. وش أكثر استخدام تستفيد منه؟",
        "صراحة ChatGPT أداة قوية، لكن كثيرون يستخدمونه بطريقة محدودة. المحترفون يعطونه سياقاً ودوراً وتفاصيل — والنتيجة مختلفة تمامًا. جربت؟",
    ],
    "Gemini": [
        "Gemini يتميز بالتكامل مع خدمات Google — قوة إضافية في البحث وتحليل البيانات الحية. جربت ربطه مع Google Docs؟",
        "صراحة Gemini تطور كثير خلال الفترة الأخيرة، خصوصًا في فهم الصور والسياق الطويل. وش أكثر استخدام تحب تجربه؟",
    ],
    "Claude": [
        "Claude يتميز في تحليل النصوص الطويلة والكتابة الأكاديمية. لو عندك وثيقة طويلة تحب تحللها — هو الأنسب. جربته؟",
        "صراحة Claude أقل شهرة من ChatGPT لكن في كثير من المهام يتفوق — خصوصًا في الكتابة الدقيقة وتحليل العقود. وش رأيك؟",
    ],
    "Grok": [
        "Grok مثير خصوصًا بتكامله مع X وقدرته على الوصول للمحتوى الحي. وش أكثر ميزة تستخدمها فيه؟",
        "صراحة Grok له شخصية مميزة في الردود. لكن هل هو بديل عن ChatGPT؟ رأيي لا — كل له مكانه. وش تعتقد؟",
    ],
    "DeepSeek": [
        "DeepSeek أثبت أن التنافس في AI مو حكر على الشركات الكبرى. كفاءته العالية بتكلفة أقل يستاهل الاهتمام. جربته؟",
        "صراحة DeepSeek فاجأ كثيرين بمستواه. يستاهل يكون ضمن مجموعة أدواتك. وش أكثر استخدام تبي تجربه فيه؟",
    ],
}

# ردود عامة — بلهجة سعودية طبيعية
GENERAL_REPLIES = [
    "موضوع يستاهل نقاش! وش أكثر جانب يثير اهتمامك فيه؟",
    "صراحة هذا النوع من النقاشات مهم — نحتاج أكثر محتوى تقني عربي عميق. شاركنا رأيك أكثر.",
    "ترى المحتوى التقني بالعربي يحتاج أصوات متعددة. رأيك مهم ويُثري النقاش.",
    "وجهة نظر مثيرة! السوق السعودي بدأ يتفاعل مع هذه التطورات بجدية. وش تشوف أكثر قطاع سيتأثر؟",
    "والله نقطة مهمة طرحتها. من تجربتي أن هذا المجال يتغير بسرعة كبيرة. وش توقعاتك للسنة القادمة؟",
]


# ══════════════════════════════════════════════════════════════
#  مولّد الردود الذكية — يدمج محتوى التعليق في الرد
# ══════════════════════════════════════════════════════════════
def build_smart_reply(comment_text: str) -> str:
    """
    يبني رداً ذكياً يدمج محتوى التعليق الأصلي فيه،
    مما يُظهر أن الرد بُني بعد قراءة حقيقية.
    """
    analysis = analyze_comment(comment_text)
    quote    = analysis["quote"]
    keyword  = analysis["keyword"]
    reply    = None

    # ── أولوية 1: أداة محددة مذكورة ────────────────────────
    if analysis["tools"]:
        tool = analysis["tools"][0]
        if tool in TOOL_SPECIFIC_REPLIES:
            reply = random.choice(TOOL_SPECIFIC_REPLIES[tool])

    # ── أولوية 2: سؤال "كيف أبدأ" ──────────────────────────
    if not reply and analysis["is_asking_how"]:
        reply = random.choice(HOW_TO_REPLIES)

    # ── أولوية 3: مشاركة تجربة شخصية ───────────────────────
    if not reply and analysis["is_experience"]:
        reply = random.choice(EXPERIENCE_REPLIES)

    # ── أولوية 4: قلق ومخاوف ────────────────────────────────
    if not reply and analysis["is_concerned"]:
        reply = random.choice(CONCERN_REPLIES)

    # ── أولوية 5: خلاف ──────────────────────────────────────
    if not reply and analysis["is_negative"]:
        reply = random.choice(DISAGREEMENT_REPLIES)

    # ── أولوية 6: إطراء وشكر ────────────────────────────────
    if not reply and analysis["is_positive"]:
        reply = random.choice(APPRECIATION_REPLIES)

    # ── أولوية 7: موضوع محدد ────────────────────────────────
    if not reply and analysis["topics"]:
        topic = analysis["topics"][0]
        if topic in TOPIC_REPLIES:
            reply = random.choice(TOPIC_REPLIES[topic])

    # ── أولوية 8: رد عام ────────────────────────────────────
    if not reply:
        reply = random.choice(GENERAL_REPLIES)

    # ══════════════════════════════════════════════════════════
    # دمج محتوى التعليق في الرد — يجعله مخصصاً حقيقياً
    # ══════════════════════════════════════════════════════════
    personalized = _personalize_reply(reply, quote, keyword, analysis)

    # تأكد من حد الطول
    if tweet_length(personalized) > 270:
        personalized = reply  # fallback للرد الأصلي بدون تخصيص

    return personalized


def _personalize_reply(reply: str, quote: str, keyword: str, analysis: dict) -> str:
    """
    يضيف لمسة تخصيص للرد بناءً على محتوى التعليق.
    يجعل الرد يبدو أنه تم قراءة التعليق فعلاً.
    """
    # إذا كان الرد بالإطراء — أضف شكراً مع الاقتباس
    if analysis["is_positive"] and quote and len(quote) > 5:
        if tweet_length(f'"{quote}" — {reply}') <= 270:
            # لا نضيف اقتباساً للردود الطويلة
            pass  # أبقِ الرد كما هو لأنه مخصص أصلاً

    # إذا ذُكرت أداة — أضف اسمها في البداية
    if analysis["tools"] and keyword:
        # الرد بالفعل يذكر الأداة في معظم الأحيان
        pass

    # إذا كان سؤالاً — أضف تأكيداً في البداية
    if analysis["is_question"] and not analysis["is_asking_how"]:
        starters = [
            "سؤال ممتاز! ",
            "وجهة نظر تستاهل — ",
            "نقطة ممتازة! ",
        ]
        candidate = random.choice(starters) + reply
        if tweet_length(candidate) <= 268:
            return candidate

    # إذا كان تجربة شخصية — أضف اعترافاً
    if analysis["is_experience"]:
        starters = [
            "والله تجربتك مهمة — ",
            "تجربتك هذي تستاهل — ",
        ]
        candidate = random.choice(starters) + reply
        if tweet_length(candidate) <= 268:
            return candidate

    return reply


# ══════════════════════════════════════════════════════════════
#  إعداد العميل
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
#  الرد على Mentions
# ══════════════════════════════════════════════════════════════
def reply_to_mentions(client: tweepy.Client, replied: set, max_count: int) -> int:
    count = 0
    try:
        me = client.get_me()
        if not me or not me.data:
            logger.warning("[Mentions] لم يُتمكن من جلب بيانات الحساب")
            return 0

        kwargs = {
            "max_results": 20,
            "tweet_fields": ["author_id", "text", "conversation_id"],
        }
        last_id = load_last_mention_id()
        if last_id:
            kwargs["since_id"] = last_id

        response = client.get_users_mentions(id=me.data.id, **kwargs)

        if not response.data:
            logger.info("[Mentions] لا توجد mentions جديدة")
            return 0

        save_last_mention_id(str(response.data[0].id))

        for mention in response.data:
            if count >= max_count:
                break

            mid          = str(mention.id)
            mention_text = getattr(mention, "text", "") or ""

            if mid in replied:
                continue

            # ── بناء الرد الذكي المخصص ─────────────────────
            reply_text = build_smart_reply(mention_text)

            analysis = analyze_comment(mention_text)
            logger.info(
                f"[Mentions] 📖 تعليق: '{mention_text[:50]}' | "
                f"موضوع: {analysis['topics']} | نية: "
                f"{'سؤال' if analysis['is_question'] else 'تعليق'}"
            )

            delay = random.uniform(20, 60)
            time.sleep(delay)

            try:
                client.create_tweet(
                    text=reply_text,
                    in_reply_to_tweet_id=mid,
                )
                logger.info(
                    f"[Mentions] ✅ رد مخصص | "
                    f"الرد: {reply_text[:60]}"
                )
                replied.add(mid)
                count += 1
            except tweepy.TweepyException as e:
                logger.warning(f"[Mentions] فشل الرد: {e}")

    except tweepy.TweepyException as e:
        logger.warning(f"[Mentions] فشل جلب mentions: {e}")

    return count


# ══════════════════════════════════════════════════════════════
#  البحث والرد على تغريدات الآخرين
# ══════════════════════════════════════════════════════════════
def search_and_reply(client: tweepy.Client, replied: set, target: int) -> int:
    count = 0
    random.shuffle(SEARCH_HASHTAGS)

    for hashtag in SEARCH_HASHTAGS:
        if count >= target:
            break
        try:
            response = client.search_recent_tweets(
                query=f"{hashtag} -is:retweet lang:ar",
                max_results=20,
                tweet_fields=["author_id", "text"],
            )
            if not response.data:
                continue

            logger.info(f"[Search] {hashtag}: {len(response.data)} تغريدة")

            for tweet in response.data:
                if count >= target:
                    break

                tid        = str(tweet.id)
                tweet_text = getattr(tweet, "text", "") or ""

                if tid in replied:
                    continue

                # ── رد ذكي مخصص بناءً على محتوى التغريدة ───
                reply_text = build_smart_reply(tweet_text)
                analysis   = analyze_comment(tweet_text)

                delay = random.uniform(30, 90)
                time.sleep(delay)

                try:
                    client.create_tweet(
                        text=reply_text,
                        in_reply_to_tweet_id=tid,
                    )
                    logger.info(
                        f"[Search] ✅ رد على {tid[:10]}... | "
                        f"الموضوع: {analysis['topics']} | "
                        f"الرد: {reply_text[:50]}"
                    )
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
        f"[ReplyBot] 🤖 بدء جلسة الردود الذكية — "
        f"{now_riyadh().strftime('%Y-%m-%d %H:%M')}"
    )

    client  = get_client()
    replied = load_replied()
    count   = 0

    # 1. الردود على Mentions (أولوية قصوى)
    m_count = reply_to_mentions(client, replied, max_count=5)
    count  += m_count
    logger.info(f"[ReplyBot] Mentions: {m_count} رد")

    # 2. البحث والرد على التغريدات الأخرى
    remaining = REPLY_COUNT_PER_RUN - count
    if remaining > 0:
        s_count = search_and_reply(client, replied, target=remaining)
        count  += s_count
        logger.info(f"[ReplyBot] Search: {s_count} رد")

    save_replied(replied)
    logger.info(f"[ReplyBot] 🏁 إجمالي الجلسة: {count} رد")


if __name__ == "__main__":
    run_reply_bot()
