"""Portfolio Brain — full AI portfolio risk analysis."""
import numpy as np
import pandas as pd
import yfinance as yf
import anthropic
from datetime import datetime, timezone

from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

settings = get_settings()


async def _get_positions(user_id: str) -> list[dict]:
    try:
        from apps.api.database import AsyncSessionLocal
        from database.models.users import PortfolioPosition
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PortfolioPosition).where(PortfolioPosition.user_id == user_id)
            )
            positions = result.scalars().all()
        return [
            {"ticker": p.ticker, "quantity": float(p.quantity or 0), "avg_cost": float(p.avg_cost or 0)}
            for p in positions
        ]
    except Exception:
        return []


async def analyze_portfolio(user_id: str) -> dict:
    positions = await _get_positions(user_id)
    if not positions:
        return {"message": "No positions found. Add positions to get portfolio analysis.", "disclaimer": MANDATORY_DISCLAIMER}

    tickers = [p["ticker"] for p in positions]
    total_cost = sum(p["quantity"] * p["avg_cost"] for p in positions)

    # Get current prices
    current_values = {}
    for p in positions:
        try:
            t = yf.Ticker(p["ticker"])
            current_price = t.fast_info.last_price
            current_values[p["ticker"]] = {
                "current_price": round(current_price, 2),
                "current_value": round(current_price * p["quantity"], 2),
                "cost_basis": round(p["avg_cost"] * p["quantity"], 2),
                "unrealized_pnl_pct": round((current_price - p["avg_cost"]) / p["avg_cost"] * 100, 2),
            }
        except Exception:
            current_values[p["ticker"]] = {}

    total_value = sum(v.get("current_value", 0) for v in current_values.values())

    # Sector weights
    sector_weights: dict[str, float] = {}
    for p in positions:
        try:
            t = yf.Ticker(p["ticker"])
            sector = t.info.get("sector", "Unknown")
            val = current_values.get(p["ticker"], {}).get("current_value", 0)
            weight = val / total_value if total_value > 0 else 0
            sector_weights[sector] = sector_weights.get(sector, 0) + weight
        except Exception:
            pass

    top_sector = max(sector_weights, key=sector_weights.get) if sector_weights else "Unknown"
    top_sector_pct = round(sector_weights.get(top_sector, 0) * 100, 1)

    # AI narrative
    positions_text = "\n".join(
        f"  {p['ticker']}: {p['quantity']} shares @ ${p['avg_cost']:.2f} avg cost"
        for p in positions
    )
    sector_text = "\n".join(f"  {s}: {round(w*100,1)}%" for s, w in sorted(sector_weights.items(), key=lambda x: x[1], reverse=True))

    prompt = f"""You are a portfolio risk analyst. Analyze this portfolio and provide a 3-4 sentence assessment.

Positions:
{positions_text}

Sector Exposure:
{sector_text}

Comment on: concentration risk, diversification quality, any obvious imbalances, and one specific suggestion.
Be specific and actionable. No buy/sell recommendations — focus on portfolio construction quality."""

    narrative = ""
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        )
        narrative = response.content[0].text.strip()
    except Exception:
        narrative = f"Portfolio has {len(positions)} positions with {top_sector_pct}% concentration in {top_sector}."

    # Health score (simple heuristic)
    health_score = 70.0
    if top_sector_pct > 60:
        health_score -= 15
    if len(positions) < 3:
        health_score -= 10
    if len(positions) > 15:
        health_score += 5
    health_score = round(max(0, min(100, health_score)), 1)

    return {
        "user_id": user_id,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "position_count": len(positions),
        "sector_weights": {k: round(v * 100, 1) for k, v in sector_weights.items()},
        "top_concentration": {"sector": top_sector, "pct": top_sector_pct},
        "health_score": health_score,
        "positions": current_values,
        "ai_narrative": narrative,
        "disclaimer": MANDATORY_DISCLAIMER,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }
