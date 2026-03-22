from celery import Celery
from config.settings import REDIS_URL

# Celery application configuration
celery_app = Celery(
    "store_monitor",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["worker.tasks", "worker.notify"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
