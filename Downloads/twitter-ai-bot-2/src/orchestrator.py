# src/orchestrator.py
"""
المُنسِّق الرئيسي (Master Orchestrator)
══════════════════════════════════════════════════════════════
يُنسِّق عمل جميع الوكلاء بالتسلسل الصحيح:

تدفق النشر اليومي:
  SearchAgent → أفضل 8 أخبار (مُرتَّبة خوارزمياً)
      ↓
  ContentAgent → 8 تغريدات بهوك سعودي + تدقيق جودة
      ↓
  PublisherAgent → نشر التغريدات مع الصور

تدفق الردود (3 مرات يوميًا):
  ReplyAgent → قراءة mentions + بناء ردود سياقية

تدفق التفاعل (مرة يوميًا):
  EngageAgent → اكتشاف أفضل 10 حسابات + تفاعل تحليلي
══════════════════════════════════════════════════════════════
"""
import sys
import pathlib
import argparse

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.utils import logger, now_riyadh
from src.agents.search_agent   import SearchAgent
from src.agents.content_agent  import ContentAgent
from src.agents.publisher_agent import PublisherAgent
from src.agents.reply_agent    import ReplyAgent
from src.agents.engage_agent   import EngageAgent


def run_post_pipeline(n: int = 1) -> dict:
    """
    تدفق النشر الكامل:
    Search → Content → Publish

    n: عدد التغريدات المطلوب نشرها (1 لكل وقت مجدول)
    """
    logger.info(
        f"[Orchestrator] 🚀 بدء دورة النشر — "
        f"{now_riyadh().strftime('%Y-%m-%d %H:%M')} — "
        f"{n} تغريدة"
    )

    # ① البحث والترتيب
    search  = SearchAgent()
    articles = search.get_top_articles(n=max(n * 2, 8))  # نجلب ضعف العدد للاختيار

    if not articles:
        logger.error("[Orchestrator] ❌ لا توجد مقالات — إيقاف")
        return {"success": False, "error": "no_articles"}

    # ② الصياغة والتدقيق
    content = ContentAgent()
    tweets  = content.build_batch(articles[:n])

    # فلترة: أبقِ فقط التغريدات التي اجتازت التدقيق (score >= 4)
    good_tweets = [t for t in tweets if t["audit"]["score"] >= 4]
    if not good_tweets:
        good_tweets = tweets  # إذا لم يُجتز أي — أبقِ الكل

    # ③ النشر
    publisher = PublisherAgent()
    results   = publisher.publish_batch(good_tweets[:n], delay_seconds=60)

    success = sum(1 for r in results if r.get("success"))
    logger.info(
        f"[Orchestrator] ✅ دورة النشر انتهت | "
        f"نُشر: {success}/{n}"
    )

    return {
        "success": True,
        "published": success,
        "total": n,
        "results": results,
    }


def run_reply_pipeline():
    """تدفق الردود السياقية"""
    logger.info(
        f"[Orchestrator] 💬 بدء دورة الردود — "
        f"{now_riyadh().strftime('%H:%M')}"
    )
    agent = ReplyAgent()
    agent.run()


def run_engage_pipeline(rediscover: bool = False):
    """تدفق التفاعل مع أفضل الحسابات"""
    logger.info(
        f"[Orchestrator] 🌐 بدء دورة التفاعل — "
        f"{now_riyadh().strftime('%H:%M')}"
    )
    agent = EngageAgent()
    agent.run(rediscover=rediscover)


def run_full_daily():
    """
    الدورة اليومية الكاملة:
    نشر + ردود + تفاعل
    (للاختبار اليدوي الشامل)
    """
    logger.info("[Orchestrator] 🌅 بدء الدورة اليومية الكاملة")

    # 1. دورة نشر كاملة (8 تغريدات)
    run_post_pipeline(n=8)

    # 2. دورة ردود
    run_reply_pipeline()

    # 3. تفاعل مع الحسابات
    run_engage_pipeline()

    logger.info("[Orchestrator] 🌙 الدورة اليومية الكاملة انتهت")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Twitter AI Bot Orchestrator")
    parser.add_argument(
        "--mode",
        choices=["post", "reply", "engage", "full"],
        default="post",
        help="نوع التشغيل",
    )
    parser.add_argument("--n", type=int, default=1, help="عدد التغريدات")
    parser.add_argument("--rediscover", action="store_true",
                        help="إعادة اكتشاف الحسابات")
    args = parser.parse_args()

    if args.mode == "post":
        run_post_pipeline(n=args.n)
    elif args.mode == "reply":
        run_reply_pipeline()
    elif args.mode == "engage":
        run_engage_pipeline(rediscover=args.rediscover)
    elif args.mode == "full":
        run_full_daily()
