import os
from redis import Redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)


def publish_channel(channel: str, message: str):
    try:
        redis_client.publish(channel, message)
    except Exception:
        # swallow — callers should log
        pass
