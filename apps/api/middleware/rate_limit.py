import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import redis.asyncio as aioredis

from apps.api.config import get_settings

settings = get_settings()

RATE_LIMITS = {
    "free":    100,
    "pro":     1000,
    "premium": 10000,
    "default": 100,
}

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks, docs, metrics
        if request.url.path in ("/health", "/api/docs", "/api/redoc", "/api/metrics", "/openapi.json"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        window = 3600  # 1 hour
        key = f"rate_limit:{client_ip}:{int(time.time() // window)}"

        try:
            r = await get_redis()
            current = await r.incr(key)
            if current == 1:
                await r.expire(key, window)

            limit = RATE_LIMITS["default"]
            if current > limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Try again in an hour.",
                        "limit": limit,
                        "current": current,
                    },
                )
        except Exception:
            pass  # Redis unavailable — fail open, don't block legitimate traffic

        return await call_next(request)
