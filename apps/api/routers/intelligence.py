from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from apps.api.middleware.auth import get_current_user

router = APIRouter()

DISCLAIMER = (
    "This analysis is AI-generated for educational and informational purposes only. "
    "It does not constitute financial advice or investment recommendations. "
    "All trading involves risk. Consult a registered financial advisor."
)


class TradeEvalRequest(BaseModel):
    ticker: str
    entry_price: float
    stop_loss: float
    target: float
    timeframe: str = "swing"
    notes: Optional[str] = None


class DailyBriefingResponse(BaseModel):
    date: str
    briefing: str
    top_catalysts: list[str]
    sectors_to_watch: list[str]
    risk_events: list[str]
    disclaimer: str


@router.get("/briefing/daily", response_model=DailyBriefingResponse)
async def get_daily_briefing():
    """AI-generated pre-market briefing."""
    from intelligence.market_narrative.briefing_generator import generate_daily_briefing
    return await generate_daily_briefing()


@router.post("/trade/evaluate")
async def evaluate_trade(payload: TradeEvalRequest, user=Depends(get_current_user)):
    """Score a trade setup across 7 quality dimensions."""
    from intelligence.trade_quality.scorer import score_trade
    result = await score_trade(
        ticker=payload.ticker,
        entry=payload.entry_price,
        stop_loss=payload.stop_loss,
        target=payload.target,
        timeframe=payload.timeframe,
    )
    return result


@router.get("/news/{ticker}")
async def get_ticker_news_intelligence(ticker: str):
    """AI-narrated news analysis for a ticker."""
    from intelligence.news_intelligence.summarizer import get_ticker_news_intelligence
    return await get_ticker_news_intelligence(ticker.upper())


@router.get("/watchlist-alerts")
async def get_watchlist_alerts(user=Depends(get_current_user)):
    """AI-narrated watchlist alerts for the current user."""
    from intelligence.watchlist_intelligence.anomaly_detector import get_user_alerts
    return await get_user_alerts(str(user.user_id))


@router.get("/sector/{sector}")
async def get_sector_intelligence(sector: str):
    """AI sector summary."""
    from intelligence.market_narrative.sector_summarizer import summarize_sector
    return await summarize_sector(sector)


@router.get("/ticker/{ticker}/summary")
async def get_ticker_summary(ticker: str):
    """Full AI intelligence summary for a ticker."""
    from intelligence.market_narrative.briefing_generator import generate_ticker_summary
    return await generate_ticker_summary(ticker.upper())
