"""
APScheduler-based market data scheduler.

Schedules:
  Pre-market (08:30 IST):   news, macro, earnings calendar, institutional data
  Market open (09:15 IST):  start intraday polling
  Intraday (every 1 min):   price updates, watchlist scanning
  Midday (12:30 IST):       intraday briefing generation
  Market close (15:30 IST): EOD data collection, debrief generation
  EOD (17:00 IST):          sentiment pipeline, strategy scoring
  Overnight (23:00 IST):    ML model refresh, behavioral scoring
"""
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from apps.api.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


async def run_pre_market():
    logger.info("Scheduler: running pre-market data collection")
    try:
        from core.data_ingestion.news_collector import NewsCollector
        from core.data_ingestion.macro_collector import MacroCollector
        from core.data_ingestion.earnings_collector import EarningsCollector
        await asyncio.gather(
            asyncio.to_thread(NewsCollector().collect),
            asyncio.to_thread(MacroCollector().collect),
            asyncio.to_thread(EarningsCollector().collect),
        )
        from intelligence.market_narrative.briefing_generator import generate_daily_briefing
        await generate_daily_briefing()
        logger.info("Scheduler: pre-market complete")
    except Exception as e:
        logger.error(f"Scheduler pre-market error: {e}")


async def run_intraday_scan():
    logger.info("Scheduler: running intraday watchlist scan")
    try:
        from intelligence.watchlist_intelligence.anomaly_detector import scan_all_watchlists
        await scan_all_watchlists()
    except Exception as e:
        logger.error(f"Scheduler intraday scan error: {e}")


async def run_eod_collection():
    logger.info("Scheduler: running EOD data collection")
    try:
        from core.data_ingestion.stock_collector import StockCollector
        from core.data_ingestion.social_collector import SocialCollector
        await asyncio.gather(
            asyncio.to_thread(StockCollector().collect),
            asyncio.to_thread(SocialCollector().collect),
        )
        # Run existing sentiment pipeline
        from core.sentiment_engine import run_sentiment_pipeline
        await asyncio.to_thread(run_sentiment_pipeline)
        logger.info("Scheduler: EOD complete")
    except Exception as e:
        logger.error(f"Scheduler EOD error: {e}")


async def run_overnight_ml():
    logger.info("Scheduler: running overnight ML refresh")
    try:
        from apps.api.celery_app import celery_app
        celery_app.send_task("apps.api.tasks.ml_tasks.refresh_regime_model")
        celery_app.send_task("apps.api.tasks.ml_tasks.compute_behavioral_scores")
        logger.info("Scheduler: overnight ML tasks queued")
    except Exception as e:
        logger.error(f"Scheduler overnight ML error: {e}")


def main():
    tz = settings.scheduler_timezone
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(run_pre_market,     CronTrigger(hour=8, minute=30, timezone=tz))
    scheduler.add_job(run_intraday_scan,  CronTrigger(minute="*/1", hour="9-15", timezone=tz))
    scheduler.add_job(run_eod_collection, CronTrigger(hour=15, minute=35, timezone=tz))
    scheduler.add_job(run_overnight_ml,   CronTrigger(hour=23, minute=0, timezone=tz))

    scheduler.start()
    logger.info(f"Scheduler started (timezone: {tz})")

    loop = asyncio.get_event_loop()
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
