import json
from typing import AsyncGenerator

import redis
import redis.asyncio as aioredis

from app.config import get_settings

_redis: aioredis.Redis | None = None
_sync_redis: redis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def get_sync_redis() -> redis.Redis:
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _sync_redis


async def publish(channel: str, event_type: str, payload: dict) -> None:
    r = get_redis()
    message = json.dumps({"event_type": event_type, "payload": payload})
    await r.publish(channel, message)


def publish_sync(channel: str, event_type: str, payload: dict) -> None:
    r = get_sync_redis()
    message = json.dumps({"event_type": event_type, "payload": payload})
    r.publish(channel, message)


async def subscribe(channel: str) -> AsyncGenerator[dict, None]:
    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield json.loads(message["data"])
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


def runcard_channel(runcard_id: str) -> str:
    return f"runcard:{runcard_id}"


def project_channel(project_id: str) -> str:
    return f"project:{project_id}"
