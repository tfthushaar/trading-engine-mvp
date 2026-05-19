"""
Celery tasks for intelligence and backtest operations.
These run asynchronously in the worker container.
"""
import asyncio
from apps.api.celery_app import celery_app


@celery_app.task(name="apps.api.tasks.intelligence_tasks.run_backtest", bind=True, max_retries=2)
def run_backtest(self, payload: dict, user_id: str) -> dict:
    """Run backtesting on a user strategy. Executes synchronously in worker."""
    try:
        tickers = payload.get("tickers", [])
        start_date = payload.get("start_date", "2023-01-01")
        end_date = payload.get("end_date", "2024-12-31")
        initial_capital = payload.get("initial_capital", 100000.0)
        commission_pct = payload.get("commission_pct", 0.1)
        slippage_pct = payload.get("slippage_pct", 0.05)
        strategy_id = payload.get("strategy_id", "")

        import yfinance as yf
        import pandas as pd
        import numpy as np

        all_trades = []
        for ticker in tickers:
            try:
                hist = yf.Ticker(ticker).history(start=start_date, end=end_date, interval="1d")
                if hist.empty or len(hist) < 20:
                    continue

                close = hist["Close"]
                # Simple momentum strategy: buy when close > 20d SMA, sell when below
                sma20 = close.rolling(20).mean()
                capital = initial_capital / max(len(tickers), 1)
                position = False
                entry_price = 0.0
                trades = []

                for i in range(20, len(close)):
                    price = close.iloc[i]
                    ma = sma20.iloc[i]
                    commission = price * commission_pct / 100
                    slip = price * slippage_pct / 100

                    if not position and price > ma:
                        entry_price = price + commission + slip
                        position = True
                    elif position and price < ma:
                        exit_price = price - commission - slip
                        pnl_pct = (exit_price - entry_price) / entry_price * 100
                        trades.append(pnl_pct)
                        capital *= (1 + pnl_pct / 100)
                        position = False

                all_trades.extend(trades)
            except Exception:
                continue

        if not all_trades:
            return {"error": "No trades generated — check ticker symbols and date range"}

        returns = np.array(all_trades)
        win_rate = float((returns > 0).mean())
        avg_return = float(returns.mean())
        total_return = float(np.prod(1 + returns / 100) - 1) * 100
        sharpe = float(returns.mean() / returns.std() * (252 ** 0.5)) if returns.std() > 0 else 0.0
        max_dd = float(min(np.minimum.accumulate(np.cumsum(returns) / 100 + 1) - 1, 0)) * 100

        return {
            "strategy_id": strategy_id,
            "tickers": tickers,
            "start_date": start_date,
            "end_date": end_date,
            "total_trades": len(all_trades),
            "win_rate": round(win_rate, 3),
            "avg_return_pct": round(avg_return, 3),
            "total_return_pct": round(total_return, 2),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown_pct": round(max_dd, 2),
            "disclaimer": "Backtesting results are hypothetical and do not guarantee future performance.",
        }
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="apps.api.tasks.intelligence_tasks.generate_trade_review", bind=True)
def generate_trade_review(self, journal_id: str) -> dict:
    """Generate AI post-trade review for a journaled trade."""
    try:
        result = asyncio.run(_async_trade_review(journal_id))
        return result
    except Exception as exc:
        return {"error": str(exc), "journal_id": journal_id}


async def _async_trade_review(journal_id: str) -> dict:
    from apps.api.database import AsyncSessionLocal
    from database.models.users import TradeJournal
    from sqlalchemy import select
    from apps.api.config import get_settings
    import anthropic

    settings = get_settings()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TradeJournal).where(TradeJournal.journal_id == journal_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return {"error": "Journal entry not found"}

    # Build review prompt
    direction = entry.direction or "unknown"
    pnl = float(entry.pnl_percent or 0)
    rule_followed = entry.rule_followed
    emotion = entry.emotion_entry or "unknown"

    outcome = "winner" if pnl > 0 else "loser"
    prompt = f"""You are a trading coach reviewing a completed trade.

Trade Details:
- Ticker: {entry.ticker}
- Direction: {direction}
- Entry: ${entry.entry_price}, Exit: ${entry.exit_price}
- Stop Loss: ${entry.stop_loss}, Target: ${entry.target}
- P&L: {pnl:+.2f}%
- Outcome: {outcome}
- Rules followed: {rule_followed}
- Emotional state at entry: {emotion}
- Notes: {entry.notes or 'None'}

Write a 3-sentence post-trade review covering:
1. Was this a good trade process (regardless of outcome)?
2. What was the key lesson?
3. What to do differently or repeat next time?

Be direct and honest."""

    review_text = f"Trade review for {entry.ticker}: P&L {pnl:+.2f}%."
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        review_text = response.content[0].text.strip()
    except Exception:
        pass

    # Detect behavioral flags
    flags = []
    if rule_followed is False:
        flags.append("rule_violation")
    if emotion in ("fomo", "revenge"):
        flags.append(f"emotional_entry_{emotion}")
    if pnl < 0 and entry.stop_loss and entry.exit_price:
        exit_p = float(entry.exit_price or 0)
        sl = float(entry.stop_loss or 0)
        entry_p = float(entry.entry_price or 1)
        if direction == "long" and exit_p < sl:
            flags.append("stop_loss_not_honored")

    # Update the journal entry
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TradeJournal).where(TradeJournal.journal_id == journal_id)
        )
        entry = result.scalar_one_or_none()
        if entry:
            entry.ai_review = {"review": review_text, "generated_at": __import__("datetime").datetime.utcnow().isoformat()}
            entry.behavioral_flags = flags
            await db.commit()

    return {"journal_id": journal_id, "review": review_text, "behavioral_flags": flags}
