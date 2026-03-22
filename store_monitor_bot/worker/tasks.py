import asyncio
import json
import logging
from datetime import datetime

from .celery_app import celery_app
from config.settings import DATABASE_URL, REDIS_URL, ADMIN_GROUP_ID, MIN_DISCOUNT_PERCENT
from db.models import get_engine, get_session_factory, UserProduct, MonitoringStatus
from sqlalchemy import select, update
from core.connectors.generic import ConnectorManager
from core.monitor import OpportunityScorer
from db.crud import update_product_data, create_opportunity, create_admin_notification
from redis import Redis as SyncRedis

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.tasks.scrape_product", bind=True)
def scrape_product(self, product_id: int, url: str, old_price: float = None, old_stock: bool = None):
    """Celery task wrapper. Runs the async worker coroutine.

    Args passed from MonitoringEngine: product_id, url, old_price, old_stock
    """
    try:
        return asyncio.run(_scrape_and_update(product_id, url, old_price, old_stock))
    except Exception as exc:
        logger.exception("scrape_product task failed: %s", exc)
        raise


async def _scrape_and_update(product_id: int, url: str, old_price: float = None, old_stock: bool = None):
    engine = get_engine(DATABASE_URL)
    session_factory = get_session_factory(engine)
    connector = ConnectorManager()
    scorer = OpportunityScorer()

    # Perform scraping via connectors (async)
    try:
        data = await connector.scrape(url)
    except Exception as exc:
        logger.exception("Connector scrape failed for %s: %s", url, exc)
        data = None

    async with session_factory() as session:
        if not data:
            # Persist a lightweight admin notification and return
            await create_admin_notification(
                session,
                type="scrape_failed",
                title="Scrape failed",
                message=f"Failed to scrape URL: {url}",
            )
            await engine.dispose()
            return {"status": "failed"}

        new_price = data.get("price")
        new_stock = data.get("in_stock")
        name = data.get("name")

        # Update product record and history
        try:
            updated_product = await update_product_data(
                session,
                product_id=product_id,
                price=new_price,
                in_stock=new_stock,
                name=name,
            )
        except Exception as exc:
            logger.exception("Failed to update product %s: %s", product_id, exc)
            await engine.dispose()
            return {"status": "db_error"}

        # Opportunity detection
        if old_price and new_price and new_price < old_price:
            discount_pct = ((old_price - new_price) / old_price) * 100
            if discount_pct >= MIN_DISCOUNT_PERCENT:
                score = scorer.calculate_score({**data, "lowest_price": updated_product.lowest_price}, old_price, new_price)
                await create_opportunity(session, product_id, old_price, new_price, score, in_stock=new_stock)
                await create_admin_notification(
                    session,
                    type="new_opportunity",
                    title="فرصة جديدة 💡",
                    message=f"{name or 'منتج'} انخفض {discount_pct:.1f}%",
                    icon="💡",
                    color="blue",
                    action_url=f"/opportunities",
                )

        # Notify users who watch this product by publishing to Redis
        try:
            result = await session.execute(
                select(UserProduct).where(
                    UserProduct.product_id == product_id,
                    UserProduct.status == MonitoringStatus.ACTIVE,
                )
            )
            watchers = result.scalars().all()
        except Exception as exc:
            logger.exception("Failed to fetch user watchers for %s: %s", product_id, exc)
            watchers = []

    # Use sync Redis client to publish alerts for the bot process
    try:
        r = SyncRedis.from_url(REDIS_URL)
        for up in watchers:
            # compute alert message similar to original logic
            alert_types = up.alert_types or []
            should_notify = False
            message_text = None

            if (old_price and new_price and new_price < old_price and
                    ("price_drop" in alert_types or "any_price_change" in alert_types)):
                discount = ((old_price - new_price) / old_price) * 100
                if "big_discount" in alert_types and discount < 20:
                    pass
                else:
                    should_notify = True
                    message_text = (
                        f"📉 *انخفاض في السعر!*\n\n"
                        f"السعر السابق: {old_price:.2f}\n"
                        f"السعر الجديد: *{new_price:.2f}*\n"
                        f"الخصم: *{discount:.1f}%*"
                    )

            elif (new_price and up.target_price and new_price <= up.target_price and "target_price" in alert_types):
                should_notify = True
                message_text = (
                    f"🎯 *وصل المنتج للسعر المستهدف!*\n\n"
                    f"السعر الحالي: *{new_price:.2f}*\n"
                    f"السعر المستهدف: {up.target_price:.2f}"
                )

            elif (old_stock == False and new_stock == True and "back_in_stock" in alert_types):
                should_notify = True
                message_text = "🟢 *المنتج عاد للمخزون!*"

            elif (old_stock == True and new_stock == False and "out_of_stock" in alert_types):
                should_notify = True
                message_text = "🔴 *نفد المخزون!*"

            if should_notify and message_text:
                # Publish to a channel the bot listens to. Payload includes telegram_id.
                try:
                    payload = json.dumps({
                        "telegram_id": up.user.telegram_id if hasattr(up, 'user') else None,
                        "user_product_id": up.id,
                        "product_id": product_id,
                        "message": (
                            f"{message_text}\n\n📦 *{name or 'المنتج'}*\n🔗 {url}"
                        ),
                    }, ensure_ascii=False)
                    r.publish("user:alerts", payload)
                except Exception:
                    logger.exception("Failed to publish user alert for product %s", product_id)

        r.close()
    except Exception:
        logger.exception("Redis publish failed for user alerts")

    await engine.dispose()
    return {"status": "ok"}
