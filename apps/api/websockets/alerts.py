"""
WebSocket alert feed.

Client subscribes to /ws/alerts/{user_id}
Server pushes AI-narrated watchlist alerts as they fire.
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis

from apps.api.config import get_settings

router = APIRouter()
settings = get_settings()


@router.websocket("/alerts/{user_id}")
async def alerts_websocket(websocket: WebSocket, user_id: str):
    await websocket.accept()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    channel = f"alerts:{user_id}"
    await pubsub.subscribe(channel)

    async def listen():
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])

    listen_task = asyncio.create_task(listen())
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        listen_task.cancel()
        await pubsub.unsubscribe(channel)
        await r.aclose()
