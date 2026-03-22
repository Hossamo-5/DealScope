from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from auth.security import verify_admin

router = APIRouter(prefix="/api/test", tags=["test"])


class TelegramTest(BaseModel):
    telegram_id: int = Field(...)
    message: str = Field(..., min_length=1)


class ScraperTest(BaseModel):
    url: str = Field(..., min_length=5)
    product_id: Optional[int] = None


@router.post("/telegram")
async def test_telegram(body: TelegramTest, admin: dict = Depends(verify_admin)):
    """Enqueue a notification to simulate Telegram delivery (via notifications worker)."""
    try:
        from worker.notify import send_notification

        payload = {"id": None, "type": "user", "recipient": int(body.telegram_id), "message": body.message, "meta": {"test": True}}
        task = send_notification.delay(payload)
        return {"status": "queued", "task_id": task.id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/scraper")
async def test_scraper(body: ScraperTest, admin: dict = Depends(verify_admin)):
    """If product_id provided, enqueue scrape_product task; otherwise run a quick live scrape and return result."""
    try:
        if body.product_id:
            from worker.tasks import scrape_product
            task = scrape_product.delay(int(body.product_id), body.url, None, None)
            return {"status": "queued", "task_id": task.id}

        # quick inline scrape for testing
        from core.connectors.generic import ConnectorManager
        connector = ConnectorManager()
        data = await connector.scrape(body.url)
        return {"status": "ok", "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/worker")
async def test_worker_trigger(admin: dict = Depends(verify_admin)):
    """Trigger a simple no-op job on the workers to check queueing."""
    try:
        from worker.celery_app import celery_app
        # send a ping task to workers using control or run a lightweight task if available
        pong = celery_app.control.ping(timeout=2.0)
        return {"status": "ok", "workers": pong}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
