"""HTTP helpers: NaN-safe JSON responses, request context middleware, error mapping."""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
import math
from decimal import Decimal
from typing import Any

import numpy as np
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from backend import ratelimit
from backend.ai import llm

log = logging.getLogger("trading_engine")


def sanitize(obj: Any) -> Any:
    """Make any result JSON-safe: numpy scalars/arrays, NaN/inf -> None, dataclasses, dates, Decimal."""
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (int,)) and not isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return v if math.isfinite(v) else None
    if isinstance(obj, np.ndarray):
        return sanitize(obj.tolist())
    if isinstance(obj, dict):
        return {str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [sanitize(v) for v in obj]
    if dataclasses.is_dataclass(obj):
        return sanitize(dataclasses.asdict(obj))
    if isinstance(obj, (dt.datetime, dt.date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "model_dump"):
        return sanitize(obj.model_dump())
    return str(obj)


class SafeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(sanitize(content), allow_nan=False, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def ok(data: Any, cache_s: int = 0, status_code: int = 200) -> SafeJSONResponse:
    headers = {"Cache-Control": f"public, max-age={cache_s}, s-maxage={cache_s}, stale-while-revalidate={cache_s * 2}"} if cache_s else {"Cache-Control": "no-store"}
    return SafeJSONResponse(data, status_code=status_code, headers=headers)


def client_ip_from(scope: Scope) -> str:
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    for h in ("x-real-ip", "x-forwarded-for", "cf-connecting-ip"):
        if headers.get(h):
            return headers[h].split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


class RequestContextMiddleware:
    """Pure ASGI middleware: sets client IP and the visitor's optional LLM key for the duration of the request."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        t1 = ratelimit.client_ip.set(client_ip_from(scope))
        visitor = None
        if headers.get("x-llm-key"):
            visitor = {
                "provider": (headers.get("x-llm-provider") or "groq").lower(),
                "key": headers["x-llm-key"].strip(),
                "model": (headers.get("x-llm-model") or "").strip()[:100],
            }
        t2 = llm.visitor_llm.set(visitor)
        try:
            await self.app(scope, receive, send)
        finally:
            ratelimit.client_ip.reset(t1)
            llm.visitor_llm.reset(t2)


def limit(bucket: str, per_10min: int) -> None:
    """Per-IP compute limit for an endpoint group (raises RateLimited)."""
    ratelimit.hit(f"{bucket}:{ratelimit.client_ip.get()}", per_10min, 600)


def error_response(request: Request, exc: Exception) -> SafeJSONResponse:
    from backend.market.data import MarketDataError

    if isinstance(exc, ratelimit.RateLimited):
        r = ok({"detail": f"Too many requests. Try again in {exc.retry_after} seconds."}, status_code=429)
        r.headers["Retry-After"] = str(exc.retry_after)
        return r
    if isinstance(exc, MarketDataError):
        msg = str(exc)
        return ok({"detail": msg}, status_code=404 if "no price data" in msg or "invalid symbol" in msg or "not enough" in msg else 502)
    if isinstance(exc, ValueError):
        return ok({"detail": str(exc)}, status_code=400)
    log.exception("unhandled error on %s", request.url.path)
    return ok({"detail": "Something went wrong while processing this request."}, status_code=500)
