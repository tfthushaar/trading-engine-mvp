"""
Redis-backed event bus for inter-service communication.
Producers publish MarketEvents; consumers subscribe to channels.
"""
import json
import asyncio
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Callable, Awaitable
import redis.asyncio as aioredis

from apps.api.config import get_settings

settings = get_settings()

CHANNELS = {
    "price_update":      "events:price_update",
    "news":              "events:news",
    "earnings":          "events:earnings",
    "insider":           "events:insider",
    "options_anomaly":   "events:options_anomaly",
    "volume_spike":      "events:volume_spike",
    "breakout":          "events:breakout",
    "sentiment_spike":   "events:sentiment_spike",
    "briefing_ready":    "events:briefing_ready",
}


@dataclass
class MarketEvent:
    event_type: str
    source: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ticker: Optional[str] = None
    payload: dict = field(default_factory=dict)


class EventBus:
    def __init__(self):
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def publish(self, event: MarketEvent) -> None:
        r = await self._get_redis()
        channel = CHANNELS.get(event.event_type, f"events:{event.event_type}")
        await r.publish(channel, json.dumps(asdict(event)))

        # Also push to ticker-specific price channel for WebSocket fans
        if event.event_type == "price_update" and event.ticker:
            await r.publish(f"price:{event.ticker}", json.dumps(event.payload))

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[MarketEvent], Awaitable[None]],
    ) -> None:
        r = await self._get_redis()
        pubsub = r.pubsub()
        channel = CHANNELS.get(event_type, f"events:{event_type}")
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    event = MarketEvent(**data)
                    await handler(event)
                except Exception as exc:
                    print(f"[EventBus] Handler error on {event_type}: {exc}")


event_bus = EventBus()
