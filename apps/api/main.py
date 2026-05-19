import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from apps.api.config import get_settings
from apps.api.database import engine, Base
from apps.api.middleware.rate_limit import RateLimitMiddleware
from apps.api.middleware.audit import AuditMiddleware
from apps.api.routers import (
    auth, market_data, intelligence, trade_lab,
    portfolio, journal, learning, agents, watchlist,
)
from apps.api.websockets.price_feed import router as ws_price_router
from apps.api.websockets.alerts import router as ws_alerts_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: dispose engine
    await engine.dispose()


if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.2)

app = FastAPI(
    title="AI Market Intelligence OS",
    description="AI-powered market analysis and trader decision-support platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditMiddleware)

# ── Metrics ───────────────────────────────────────────────────────────────────
Instrumentator().instrument(app).expose(app, endpoint="/api/metrics")

# ── REST Routers ──────────────────────────────────────────────────────────────
app.include_router(auth.router,         prefix="/api/auth",          tags=["auth"])
app.include_router(market_data.router,  prefix="/api/market",        tags=["market-data"])
app.include_router(intelligence.router, prefix="/api/intelligence",   tags=["intelligence"])
app.include_router(trade_lab.router,    prefix="/api/trade-lab",      tags=["trade-lab"])
app.include_router(portfolio.router,    prefix="/api/portfolio",      tags=["portfolio"])
app.include_router(journal.router,      prefix="/api/journal",        tags=["journal"])
app.include_router(learning.router,     prefix="/api/learn",          tags=["learning"])
app.include_router(agents.router,       prefix="/api/agents",         tags=["agents"])
app.include_router(watchlist.router,    prefix="/api/watchlist",      tags=["watchlist"])

# ── WebSocket Routers ─────────────────────────────────────────────────────────
app.include_router(ws_price_router,  prefix="/ws")
app.include_router(ws_alerts_router, prefix="/ws")


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": "1.0.0"}
