from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from apps.api.middleware.auth import get_current_user

router = APIRouter()


class JournalEntryRequest(BaseModel):
    ticker: str
    direction: str  # long | short
    entry_price: float
    exit_price: Optional[float] = None
    position_size: float
    entry_date: datetime
    exit_date: Optional[datetime] = None
    stop_loss: float
    target: float
    emotion_entry: Optional[str] = None   # calm | anxious | fomo | revenge | confident
    emotion_exit: Optional[str] = None
    rule_followed: Optional[bool] = None
    notes: Optional[str] = None


@router.post("/entries", status_code=201)
async def create_journal_entry(payload: JournalEntryRequest, user=Depends(get_current_user)):
    from apps.api.database import AsyncSessionLocal
    from database.models.users import TradeJournal
    async with AsyncSessionLocal() as db:
        entry = TradeJournal(
            user_id=user.user_id,
            ticker=payload.ticker.upper(),
            direction=payload.direction,
            entry_price=payload.entry_price,
            exit_price=payload.exit_price,
            position_size=payload.position_size,
            entry_date=payload.entry_date,
            exit_date=payload.exit_date,
            stop_loss=payload.stop_loss,
            target=payload.target,
            emotion_entry=payload.emotion_entry,
            emotion_exit=payload.emotion_exit,
            rule_followed=payload.rule_followed,
            notes=payload.notes,
        )
        if payload.exit_price:
            if payload.direction == "long":
                entry.actual_pnl = (payload.exit_price - payload.entry_price) * payload.position_size
                entry.pnl_percent = (payload.exit_price - payload.entry_price) / payload.entry_price * 100
            else:
                entry.actual_pnl = (payload.entry_price - payload.exit_price) * payload.position_size
                entry.pnl_percent = (payload.entry_price - payload.exit_price) / payload.entry_price * 100
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

    # Fire async AI review if trade is closed
    if payload.exit_price:
        from apps.api.celery_app import celery_app
        celery_app.send_task(
            "apps.api.tasks.intelligence_tasks.generate_trade_review",
            args=[str(entry.journal_id)],
        )

    return {"journal_id": str(entry.journal_id)}


@router.get("/entries")
async def list_journal_entries(user=Depends(get_current_user)):
    from apps.api.database import AsyncSessionLocal
    from database.models.users import TradeJournal
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TradeJournal)
            .where(TradeJournal.user_id == user.user_id)
            .order_by(TradeJournal.entry_date.desc())
        )
        entries = result.scalars().all()
    return [
        {
            "id": str(e.journal_id),
            "ticker": e.ticker,
            "direction": e.direction,
            "pnl_percent": e.pnl_percent,
            "entry_date": str(e.entry_date),
            "rule_followed": e.rule_followed,
            "ai_review": e.ai_review,
        }
        for e in entries
    ]


@router.get("/behavioral-report")
async def get_behavioral_report(user=Depends(get_current_user)):
    """AI behavioral analysis of trading patterns."""
    from behavioral.discipline_scorer import generate_monthly_report
    return await generate_monthly_report(str(user.user_id))
