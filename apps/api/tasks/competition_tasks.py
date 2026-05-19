"""Celery task for async strategy competition runs."""
import asyncio
from apps.api.celery_app import celery_app


@celery_app.task(name="apps.api.tasks.competition_tasks.run_competition_task", bind=True, max_retries=1)
def run_competition_task(self, tickers: list[str], period: str, user_id: str) -> dict:
    """Run strategy competition for a list of tickers asynchronously."""
    try:
        from agents.strategy_competition.competition_runner import run_competition
        import asyncio

        async def run_all():
            results = []
            for ticker in tickers:
                result = await run_competition(ticker, period)
                results.append({
                    "ticker": result.ticker,
                    "winner": result.winner_name,
                    "ranking": result.ranking,
                    "ai_interpretation": result.ai_interpretation,
                })
            return results

        results = asyncio.run(run_all())
        return {"status": "ok", "results": results, "tickers": tickers}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
