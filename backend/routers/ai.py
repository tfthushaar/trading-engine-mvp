"""AI endpoints: briefings, ticker reads, news, analyst chat, learning."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.ai import agents, education, insights
from backend.http import limit, ok, ok_ai

router = APIRouter(prefix="/api", tags=["ai"])


@router.get("/insights/briefing")
async def briefing():
    return ok_ai(await insights.market_briefing(), 300)


@router.get("/insights/ticker/{symbol}")
async def ticker(symbol: str):
    return ok_ai(await insights.ticker_brief(symbol), 300)


@router.get("/insights/news/{symbol}")
async def news(symbol: str):
    return ok_ai(await insights.news_read(symbol), 300)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)
    portfolio: list[dict] = Field(default_factory=list)


@router.post("/analyst/chat")
async def chat(req: ChatRequest):
    limit("chat", 40)
    return ok(await agents.chat(req.message, req.history, req.portfolio))


@router.get("/learn/concepts")
async def concepts():
    return ok({"concepts": education.catalog(), "levels": education.LEVELS}, cache_s=86400)


class ExplainRequest(BaseModel):
    concept: str
    level: str = "intermediate"
    symbol: str | None = None
    experiment: dict | None = None


@router.post("/learn/explain")
async def explain(req: ExplainRequest):
    limit("learn", 40)
    return ok(await education.explain(req.concept, req.level, req.symbol, req.experiment))
