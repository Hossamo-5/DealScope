import json
import time
import logging
from celery import Task
from redis import Redis as SyncRedis

from .celery_app import celery_app
from .utils import redis_client
from .rate_limit import reserve_notification_slot

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL = 60 * 60


@celery_app.task(bind=True, name="worker.notify.send_notification", max_retries=5, queue="notifications")
def send_notification(self: Task, payload: dict):
    try:
        nid = payload.get("id") or f"auto:{int(time.time()*1000)}"
        payload["id"] = nid

        key = f"notify:sent:{nid}"
        # Set idempotency key
        if redis_client.set(key, "1", nx=True, ex=IDEMPOTENCY_TTL):
            # Reserve slot
            ok = reserve_notification_slot(redis_client, payload)
            if not ok:
                countdown = min(60, (self.request.retries + 1) * 5)
                raise self.retry(countdown=countdown)

            channel = "user:alerts" if payload.get("type") == "user" else "admin:notifications"
            try:
                redis_client.publish(channel, json.dumps(payload, ensure_ascii=False))
            except Exception:
                logger.exception("publish failed for %s", channel)
        return {"status": "published", "id": nid}
    except self.MaxRetriesExceededError:
        logger.exception("Max retries reached for notification %s", payload.get("id"))
        raise
    except Exception as exc:
        logger.exception("notification task error: %s", exc)
        raise self.retry(exc=exc, countdown=min(120, (self.request.retries + 1) * 10))
