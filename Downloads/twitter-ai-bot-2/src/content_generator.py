# src/content_generator.py
"""
محرك المحتوى — النسخة الثالثة (v3)
═══════════════════════════════════════════════════════════════
المشكلة الجذرية في v1/v2:
  ❌ الترجمة الآلية (Google Translate) → عربية ركيكة وغير طبيعية
  ❌ استبدال كلمات فقط لا يصنع لهجة سعودية حقيقية
  ❌ المحتوى يبدو مقطوعاً لأن الترجمة تُفقد السياق

الحل في v3:
  ✅ استخراج الحقائق الجوهرية من الخبر: الفاعل + الفعل + الرقم + الأثر
  ✅ إعادة بناء التغريدة بلهجة سعودية طبيعية من الصفر
  ✅ قوالب ذكية تحافظ على المعنى الكامل
  ✅ سؤال تفاعلي مرتبط بمحتوى الخبر (لا عشوائي)
═══════════════════════════════════════════════════════════════
"""
import random
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.utils import logger, tweet_length, clean_text
from src.news_fetcher import translate_to_arabic, get_random_article, get_articles_batch


# ══════════════════════════════════════════════════════════════
# ① استخراج الحقائق الجوهرية من الخبر الإنجليزي
# ══════════════════════════════════════════════════════════════
def extract_facts(article: dict) -> dict:
    """
    يستخرج الحقائق الجوهرية من مقالة إنجليزية:
      - company: اسم الشركة / الأداة (OpenAI, Google, Meta...)
      - action:  ما حدث (launched, released, raised, acquired...)
      - number:  أي رقم مذكور ($1B, 90%, GPT-5...)
      - impact:  كلمة الأثر (faster, cheaper, smarter, replace...)
      - topic:   الموضوع (ai_model, funding, layoff, product, research)
    """
    title   = article.get("title",   "").lower()
    summary = article.get("summary", "").lower()
    combined = title + " " + summary

    # ── الشركات والأدوات ──
    COMPANIES = {
        "openai":      "OpenAI",  "chatgpt": "ChatGPT",
        "gpt-4":       "GPT-4",   "gpt-5": "GPT-5",   "gpt4": "GPT-4",
        "gemini":      "Gemini",  "google": "Google",
        "anthropic":   "Anthropic","claude": "Claude",
        "meta":        "Meta",    "llama": "Llama",
        "microsoft":   "Microsoft","copilot": "Copilot",
        "nvidia":      "NVIDIA",  "apple": "Apple",
        "mistral":     "Mistral", "deepseek": "DeepSeek",
        "grok":        "Grok",    "xai": "xAI",
        "amazon":      "Amazon",  "aws": "AWS",
        "hugging face":"Hugging Face",
        "stability":   "Stability AI",
        "midjourney":  "Midjourney",
        "sora":        "Sora",    "runway": "Runway",
        "perplexity":  "Perplexity",
        "cursor":      "Cursor",  "github": "GitHub",
        "tesla":       "Tesla",   "spacex": "SpaceX",
        "samsung":     "Samsung", "qualcomm": "Qualcomm",
        "sdaia":       "SDAIA",   "aramco": "أرامكو",
        "neom":        "نيوم",
    }
    company = ""
    for kw, name in COMPANIES.items():
        if kw in combined:
            company = name
            break

    # ── الأفعال ──
    ACTION_MAP = {
        "launched":  "أطلق",   "launch":   "أطلق",
        "released":  "أصدر",   "release":  "أصدر",
        "unveiled":  "كشف عن", "unveil":   "كشف عن",
        "announced": "أعلن عن","announce": "أعلن عن",
        "raised":    "جمع",    "funding":  "جمع تمويل",
        "acquired":  "استحوذ على","acquisition":"استحوذ على",
        "partnered": "تشارك مع","partnership":"تشارك مع",
        "beats":     "تفوق على","outperforms":"تفوق على",
        "surpassed": "تجاوز",
        "cuts":      "خفّض",   "cut":      "خفّض",
        "layoffs":   "أعلن تسريح","fired": "أعلن تسريح",
        "trained":   "درّب",   "training": "درّب",
        "updated":   "حدّث",   "update":   "حدّث",
        "open-source":"فتح المصدر","open source":"فتح المصدر",
        "ban":       "حظر",    "banned":   "حظر",
        "replaced":  "استبدل", "replace":  "يستبدل",
    }
    action = ""
    for kw, ar in ACTION_MAP.items():
        if kw in combined:
            action = ar
            break

    # ── الأرقام والإحصاءات ──
    numbers = re.findall(
        r'\$[\d,.]+[BMK]?|\d+[\.,]?\d*\s*(?:billion|million|trillion|%|percent|x|times|faster|cheaper|tokens|parameters)',
        combined, re.IGNORECASE
    )
    number = numbers[0] if numbers else ""

    # ── الأثر ──
    IMPACT_MAP = {
        "faster":    "أسرع",  "speed":   "سرعة أعلى",
        "cheaper":   "أرخص",  "cost":    "تكلفة أقل",
        "smarter":   "أذكى",  "better":  "أفضل أداء",
        "replace":   "يحل محل البشر","job": "مستقبل الوظائف",
        "dangerous": "مخاطر",  "risk":   "مخاطر",
        "privacy":   "خصوصية","security":"أمان",
        "free":      "مجاناً","open":    "مفتوح للجميع",
        "record":    "رقم قياسي","breakthrough":"إنجاز",
        "first":     "الأول من نوعه",
        "billion":   "مليار",  "million": "مليون",
        "regulation":"تنظيم","law":     "قانون",
        "ban":       "حظر","block":   "حجب",
        "saudi":     "السعودية","ksa":  "المملكة",
        "arabic":    "العربية","arab":  "العرب",
    }
    impact = ""
    for kw, ar in IMPACT_MAP.items():
        if kw in combined:
            impact = ar
            break

    # ── تصنيف الموضوع ──
    if any(w in combined for w in ["layoff","fired","job","employ","worker","hire"]):
        topic = "jobs"
    elif any(w in combined for w in ["funding","raised","billion","million","valuation","ipo"]):
        topic = "funding"
    elif any(w in combined for w in ["model","gpt","llm","claude","gemini","mistral","llama","deepseek"]):
        topic = "ai_model"
    elif any(w in combined for w in ["law","regulation","ban","policy","congress","senate","eu","government"]):
        topic = "regulation"
    elif any(w in combined for w in ["research","paper","study","published","university","breakthrough"]):
        topic = "research"
    elif any(w in combined for w in ["product","app","feature","tool","update","version"]):
        topic = "product"
    elif any(w in combined for w in ["robot","hardware","chip","device","sensor"]):
        topic = "hardware"
    else:
        topic = "general"

    return {
        "company": company,
        "action":  action,
        "number":  number,
        "impact":  impact,
        "topic":   topic,
        "title_en":   article.get("title", ""),
        "summary_en": article.get("summary", "")[:500],
        "source":     article.get("source", ""),
        "image_url":  article.get("image_url"),
    }


# ══════════════════════════════════════════════════════════════
# ② ترجمة ذكية — العنوان فقط + تنظيف
# ══════════════════════════════════════════════════════════════
def smart_translate_title(title_en: str) -> str:
    """
    يترجم العنوان الإنجليزي ويُنظّفه.
    يُبقي أسماء الشركات والأدوات بالإنجليزية.
    """
    if not title_en:
        return ""
    try:
        ar = translate_to_arabic(title_en, max_len=200)
        if not ar:
            return ""
        # إزالة التشكيل المبالغ فيه
        ar = re.sub(r'[\u064B-\u0652]', '', ar)
        # إزالة الفراغات الزائدة
        ar = re.sub(r'\s+', ' ', ar).strip()
        # اقتطع عند آخر جملة مكتملة
        ar = _cut_at_sentence(ar, 140)
        return ar
    except Exception:
        return ""


def _cut_at_sentence(text: str, limit: int) -> str:
    """اقتطع عند آخر علامة ترقيم قبل الحد"""
    if len(text) <= limit:
        return text
    for p in ['。', '؟', '!', '.']:
        pos = text.rfind(p, 0, limit)
        if pos > limit * 0.5:
            return text[:pos+1].strip()
    pos = text.rfind(' ', 0, limit)
    return text[:pos].strip() if pos > 0 else text[:limit]


# ══════════════════════════════════════════════════════════════
# ③ بناء التغريدة بلهجة سعودية طبيعية
# ══════════════════════════════════════════════════════════════

# هوكات مصنوعة بلهجة سعودية حقيقية — موزعة حسب نوع الخبر
HOOKS = {
    "ai_model": [
        "🤖 نموذج AI جديد طلع الحين —",
        "⚡ عالم AI ما يهدأ —",
        "🧠 أقوى نموذج ذكاء اصطناعي لحد الآن؟",
        "🔥 خبر AI ما تبيه يفوتك —",
        "💡 في جديد كبير في عالم النماذج —",
    ],
    "funding": [
        "💰 تمويل ضخم دخل عالم التقنية —",
        "📈 المستثمرين يراهنون على AI —",
        "🚀 شركة تقنية جمعت مبالغ مو طبيعية —",
        "💵 رأس المال يتحرك نحو الذكاء الاصطناعي —",
    ],
    "jobs": [
        "😰 سؤال يشغل بال الكثير —",
        "🤔 الذكاء الاصطناعي والوظائف — الحقيقة:",
        "⚠️ خبر يخلي الواحد يفكر في مستقبله —",
        "💼 سوق العمل يتغير — اعرف كيف:",
    ],
    "regulation": [
        "⚖️ الحكومات بدأت تتحرك على AI —",
        "🏛️ قرار جديد يغير قواعد اللعبة في AI —",
        "📋 تنظيم الذكاء الاصطناعي — خبر مهم:",
        "🚨 قانون جديد يطال شركات AI —",
    ],
    "research": [
        "🔬 دراسة علمية تكشف شيء مثير في AI —",
        "📊 بحث جديد يغير نظرتنا لـ AI —",
        "🎓 باحثون توصلوا لشيء ما توقعناه —",
    ],
    "product": [
        "🛠️ أداة تقنية جديدة تستاهل تجربتها —",
        "📱 تحديث كبير وصل —",
        "✨ ميزة جديدة مو طبيعية —",
    ],
    "hardware": [
        "💻 معالج/جهاز جديد يغير المعادلة —",
        "🔧 تقنية hardware جديدة الحين —",
        "⚙️ في جديد على صعيد الأجهزة —",
    ],
    "general": [
        "🔴 خبر تقني يستاهل وقفة —",
        "📌 شيء لفت نظري في عالم التقنية —",
        "⚡ من آخر أخبار AI والتقنية —",
        "🌐 خبر اليوم في عالم التقنية —",
    ],
}

# أسئلة تفاعلية حسب نوع الخبر
QUESTIONS = {
    "ai_model": [
        "جربته؟ وش انطباعك مقارنة بالسابق؟",
        "وش تتوقع يغيّر في طريقة شغلك؟",
        "تشوفه أفضل من {company}؟",
        "متى تتوقع وصوله للسوق العربي؟",
    ],
    "funding": [
        "وش رأيك — استثمار ذكي أو فقاعة؟",
        "تتوقع الشركة تنجح؟",
        "المستثمرين شايفين شيء ما نشوفه؟",
        "هل يستاهل هذا التمويل؟",
    ],
    "jobs": [
        "تشوف AI يهدد مجالك؟",
        "كيف تجهّز نفسك لهالتغيير؟",
        "وش المهارة اللي تعتقد ما يقدر AI يعوّضها؟",
        "خايف من هالتغيير ولا متحمس؟",
    ],
    "regulation": [
        "تأييد أو معارضة لهالقرار؟",
        "وش تأثيره على السوق السعودي برأيك؟",
        "يكفي هذا التنظيم أو يحتاج أكثر؟",
    ],
    "research": [
        "وش أكثر شيء فاجأك في هالنتائج؟",
        "كيف تشوف تأثيره عملياً؟",
        "تتوقع تطبيقه قريب؟",
    ],
    "product": [
        "جربته؟ وش رأيك؟",
        "تستخدمه في شغلك؟",
        "يستاهل التحويل إليه؟",
    ],
    "hardware": [
        "تنتظر تجربته؟",
        "يفرق معك هالتحسين؟",
        "متى تتوقع وصوله للسعودية؟",
    ],
    "general": [
        "وش رأيك؟ 💬",
        "كيف تشوف تأثيره علينا؟",
        "يهمك هذا الخبر؟",
        "وش توقعاتك؟",
    ],
}

# ملاحظات سعودية محلية — تُضاف أحياناً
LOCAL_NOTES = [
    "يتماشى مع رؤية 2030 اللي تراهن على التقنية.",
    "السوق السعودي من أوائل المتأثرين بهالتطورات.",
    "SDAIA والمملكة تراقب هالتطورات باهتمام.",
    "شركات محلية كثيرة تسير بنفس الاتجاه.",
    "فرصة للمطورين السعوديين ما تتكرر كثيراً.",
]


def build_smart_tweet(article: dict) -> str:
    """
    يبني تغريدة ذكية بلهجة سعودية طبيعية.
    الفرق عن v2: يستخرج الحقائق أولاً ثم يعيد صياغتها.
    """
    facts = extract_facts(article)
    topic    = facts["topic"]
    company  = facts["company"]
    action   = facts["action"]
    number   = facts["number"]
    impact   = facts["impact"]

    # ── 1. الهوك ──
    hook = random.choice(HOOKS.get(topic, HOOKS["general"]))

    # ── 2. العنوان المترجم ──
    title_ar = smart_translate_title(facts["title_en"])
    if not title_ar:
        title_ar = f"{company} {action}".strip() if company and action else "خبر تقني مهم"

    # ── 3. بناء جملة الخبر الرئيسية ──
    # نبني جملة واحدة قوية تضم: الفاعل + الفعل + الرقم + الأثر
    body_parts = []

    if company and action:
        base = f"{company} {action}"
        if number:
            base += f" ({_clean_number(number)})"
        body_parts.append(base)

    if impact and impact not in (body_parts[0] if body_parts else ""):
        body_parts.append(f"النتيجة: {impact}")

    body = "\n".join(f"← {p}" for p in body_parts) if body_parts else ""

    # ── 4. السؤال التفاعلي المرتبط بالخبر ──
    q_list = QUESTIONS.get(topic, QUESTIONS["general"])
    question = random.choice(q_list)
    # استبدل {company} إن وُجد
    question = question.replace("{company}", company) if company else question.replace(" {company}", "")

    # ── 5. ملاحظة محلية (35% من الأحيان) ──
    add_local = random.random() < 0.35
    local_note = random.choice(LOCAL_NOTES) if add_local else ""

    # ══════════════════════════════════════════════════════════
    # بناء تدريجي — من الأكثر تفصيلاً للأبسط
    # ══════════════════════════════════════════════════════════

    # النمط A — كامل: هوك + عنوان + تفاصيل + محلي + سؤال
    if body and local_note:
        tweet = f"{hook}\n\n{title_ar}\n\n{body}\n\n{local_note}\n\n{question}"
        if tweet_length(tweet) <= 275:
            return tweet

    # النمط B — هوك + عنوان + تفاصيل + سؤال
    if body:
        tweet = f"{hook}\n\n{title_ar}\n\n{body}\n\n{question}"
        if tweet_length(tweet) <= 275:
            return tweet

    # النمط C — هوك + عنوان + سؤال
    tweet = f"{hook}\n\n{title_ar}\n\n{question}"
    if tweet_length(tweet) <= 275:
        return tweet

    # النمط D — عنوان مختصر + سؤال
    short_title = _cut_at_sentence(title_ar, 160)
    q_short = random.choice(["وش رأيك؟ 💬", "كيف تشوفه؟", "يهمك هذا؟"])
    return f"🔴 {short_title}\n\n{q_short}"


def _clean_number(num_str: str) -> str:
    """تحويل الأرقام الإنجليزية إلى عربية مقروءة"""
    n = num_str.strip()
    n = n.replace("billion", "مليار").replace("Billion", "مليار")
    n = n.replace("million", "مليون").replace("Million", "مليون")
    n = n.replace("trillion", "تريليون").replace("Trillion", "تريليون")
    n = n.replace("percent", "%").replace("faster", "أسرع").replace("cheaper", "أرخص")
    n = n.replace("times", "أضعاف").replace("x", "×")
    n = n.replace("tokens", "توكن").replace("parameters", "معامل")
    return n


# ══════════════════════════════════════════════════════════════
# الدوال الرئيسية
# ══════════════════════════════════════════════════════════════
def generate_tweet() -> dict:
    """يُعيد تغريدة واحدة من خبر حقيقي"""
    article = get_random_article()

    if not article:
        logger.error("[Content v3] ❌ لا توجد مقالة — fallback")
        return {
            "type":  "fallback",
            "text":  (
                "🔴 خبر اليوم في عالم AI:\n\n"
                "عالم الذكاء الاصطناعي يتطور بسرعة ما نتوقعها — "
                "كل أسبوع في نموذج جديد أو تطوير يغير المعادلة.\n\n"
                "وش آخر أداة AI جربتها؟ 💬"
            ),
            "is_thread": False, "thread_tweets": [], "image_url": None,
        }

    text   = build_smart_tweet(article)
    length = tweet_length(text)
    facts  = extract_facts(article)

    logger.info(
        f"[Content v3] ✅ {length} حرف | "
        f"موضوع: {facts['topic']} | "
        f"شركة: {facts['company'] or 'لا'} | "
        f"صورة: {'✅' if article.get('image_url') else '❌'}"
    )

    return {
        "type":          "news",
        "text":          text,
        "is_thread":     False,
        "thread_tweets": [],
        "image_url":     article.get("image_url"),
    }


def generate_tweets_batch(n: int = 8) -> list:
    """توليد دفعة من التغريدات اليومية"""
    articles = get_articles_batch(n)
    results  = []

    for i, article in enumerate(articles):
        text   = build_smart_tweet(article)
        facts  = extract_facts(article)
        length = tweet_length(text)
        logger.info(
            f"[Batch v3] {i+1}/{n} | "
            f"{length} حرف | {facts['topic']} | {article.get('source','?')}"
        )
        results.append({
            "type":          "news",
            "text":          text,
            "is_thread":     False,
            "thread_tweets": [],
            "image_url":     article.get("image_url"),
        })

    return results


# ══════════════════════════════════════════════════════════════
# اختبار سريع — python -m src.content_generator
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n🧪 اختبار محرك المحتوى v3\n" + "═"*50)
    result = generate_tweet()
    print(f"\n📝 النص ({tweet_length(result['text'])} حرف):\n")
    print(result["text"])
    print(f"\n🖼️  صورة: {result.get('image_url','لا')}")
    print("═"*50)
