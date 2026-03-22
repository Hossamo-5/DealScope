from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import json

from auth.security import verify_admin

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationRequest(BaseModel):
    recipient: int = Field(..., description="Telegram user id or group id")
    message: str = Field(..., min_length=1, max_length=4096)
    type: Optional[str] = Field(default="user", pattern=r"^(user|admin)$")


@router.post("/send")
async def send_notification_endpoint(body: NotificationRequest, admin: dict = Depends(verify_admin)):
    """Enqueue a notification to be delivered by the notifications worker."""
    try:
        # Lazy import to avoid startup import cycles
        from worker.notify import send_notification

        payload = {
            "id": None,
            "type": body.type,
            "recipient": int(body.recipient),
            "message": body.message,
            "meta": {"issued_by": int(admin.get("sub", 0))},
        }

        task = send_notification.delay(payload)
        return {"status": "queued", "task_id": task.id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
