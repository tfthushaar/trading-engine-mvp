"""Trading Engine API (FastAPI). Served by Vercel as a Python function (api/index.py) or by uvicorn locally."""
from __future__ import annotations

import logging
import platform
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from backend import ratelimit
from backend.ai import llm
from backend.config import get_settings
from backend.http import RequestContextMiddleware, error_response, ok
from backend.market.data import MarketDataError
from backend.routers import ai, market, models, strategies, tools

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
settings = get_settings()
STARTED = time.time()

app = FastAPI(
    title="Trading Engine API",
    version="1.0.0",
    description="Neural-network market intelligence: pretrained ensemble signals, live model training, rule-strategy baselines and AI narration.",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=["GET", "POST"], allow_headers=["*"], max_age=86400)
app.add_middleware(RequestContextMiddleware)

for r in (tools.router, market.router, models.router, strategies.router, ai.router):
    app.include_router(r)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    return error_response(request, exc)


@app.exception_handler(MarketDataError)
async def _market_data(request: Request, exc: MarketDataError):
    return error_response(request, exc)


@app.exception_handler(ratelimit.RateLimited)
async def _rate_limited(request: Request, exc: ratelimit.RateLimited):
    return error_response(request, exc)


@app.exception_handler(ValueError)
async def _value_error(request: Request, exc: ValueError):
    return error_response(request, exc)


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(x) for x in first.get("loc", [])[1:])
    return ok({"detail": f"Invalid request{(' at ' + where) if where else ''}: {first.get('msg', 'validation error')}"}, status_code=422)


@app.get("/api/health", tags=["meta"])
async def health():
    return ok({"status": "ok", "uptime_s": round(time.time() - STARTED, 1)})


@app.get("/api/status", tags=["meta"])
async def status():
    from backend.dl import global_model

    try:
        card = global_model.card()
        model = {"available": True, "version": card["version"], "trained_at": card["trained_at"], "horizon_days": card["horizon"],
                 "members": [m["name"] for m in card["members"]], "test_auc": card["ensemble"]["test"]["auc"]}
    except Exception as exc:
        model = {"available": False, "error": str(exc)}
    return ok({
        "app": settings.app_name,
        "environment": settings.environment,
        "python": platform.python_version(),
        "llm": llm.status(),
        "llm_providers": {k: v["label"] for k, v in llm.PROVIDERS.items()},
        "neural_model": model,
        "limits": {"lab_trainings_per_10min": settings.train_per_ip_10min, "shared_ai_calls_per_10min": settings.llm_shared_per_ip_10min},
    })
