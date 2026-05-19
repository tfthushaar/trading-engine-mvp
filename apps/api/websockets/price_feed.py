"""
WebSocket price feed.

Pattern:
  Client subscribes to /ws/prices/{ticker}
  Server pulls from Redis pub/sub channel "price:{ticker}"
  Polygon.io ingestion worker publishes to that channel.
  Multiple clients share one Redis subscription per ticker.
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis

from apps.api.config import get_settings

router = APIRouter()
settings = get_settings()


class ConnectionManager:
    def __init__(self):
        # ticker -> set of websockets
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, ticker: str, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(ticker, set()).add(ws)

    def disconnect(self, ticker: str, ws: WebSocket):
        if ticker in self._connections:
            self._connections[ticker].discard(ws)

    async def broadcast(self, ticker: str, message: str):
        dead = set()
        for ws in self._connections.get(ticker, set()):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[ticker].discard(ws)


manager = ConnectionManager()


@router.websocket("/prices/{ticker}")
async def price_websocket(websocket: WebSocket, ticker: str):
    ticker = ticker.upper()
    await manager.connect(ticker, websocket)
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"price:{ticker}")

    async def listen():
        async for message in pubsub.listen():
            if message["type"] == "message":
                await manager.broadcast(ticker, message["data"])

    listen_task = asyncio.create_task(listen())
    try:
        while True:
            # Keep connection alive; client sends pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(ticker, websocket)
        listen_task.cancel()
        await pubsub.unsubscribe(f"price:{ticker}")
        await r.aclose()
