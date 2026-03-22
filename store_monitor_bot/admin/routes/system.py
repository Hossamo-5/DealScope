from fastapi import APIRouter, Depends
from auth.security import verify_admin
from pydantic import BaseModel
import os
import socket
import json
from typing import Dict

from config.settings import REDIS_URL, DATABASE_URL

router = APIRouter(prefix="/api/system", tags=["system"])


class HealthResp(BaseModel):
    redis: str
    db: str
    celery: str
    bot: str


@router.get("/health", response_model=HealthResp)
async def system_health(admin: dict = Depends(verify_admin)):
    """Return simple health checks for Redis, DB, Celery and Bot subscription."""
    results: Dict[str, str] = {"redis": "unknown", "db": "unknown", "celery": "unknown", "bot": "unknown"}

    # Redis ping
    try:
        import redis

        r = redis.from_url(REDIS_URL)
        if r.ping():
            results["redis"] = "ok"
        else:
            results["redis"] = "fail"
    except Exception:
        results["redis"] = "error"

    # DB connectivity (async engine)
    try:
        from db.models import get_engine
        from sqlalchemy import text

        eng = get_engine(DATABASE_URL)
        # async engine — use async context
        try:
            async with eng.connect() as conn:
                await conn.execute(text("SELECT 1"))
            results["db"] = "ok"
        except Exception:
            results["db"] = "error"
    except Exception:
        results["db"] = "error"

    # Celery ping
    try:
        from worker.celery_app import celery_app

        pong = celery_app.control.ping(timeout=2.0)
        results["celery"] = "ok" if pong else "no_workers"
    except Exception:
        results["celery"] = "error"

    # Bot (check pubsub channel presence) — quick sanity check: attempt Redis pubsub ping
    try:
        import redis
        r = redis.from_url(REDIS_URL)
        # publish a ping to admin:health — check how many subscribers received it
        count = r.publish("admin:health", json.dumps({"ts": 1}))
        results["bot"] = "ok" if (count and int(count) > 0) else "no_subscribers"
    except Exception:
        results["bot"] = "error"

    return results
