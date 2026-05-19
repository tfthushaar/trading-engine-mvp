"""Celery tasks for market data collection."""
from apps.api.celery_app import celery_app


@celery_app.task(name="apps.api.tasks.market_tasks.collect_prices")
def collect_prices(tickers: list[str] | None = None) -> dict:
    """Collect EOD prices for tracked tickers."""
    try:
        from core.data_ingestion.stock_collector import StockCollector
        collector = StockCollector()
        collector.collect_all()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@celery_app.task(name="apps.api.tasks.market_tasks.collect_news")
def collect_news() -> dict:
    """Collect latest news articles."""
    try:
        from core.data_ingestion.news_collector import NewsCollector
        collector = NewsCollector()
        collector.collect_all()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
