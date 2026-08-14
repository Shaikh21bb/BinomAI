import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.db.models.notification import Notification
from app.db.models.user import User

logger = structlog.get_logger(__name__)


async def notify_company(
    db: AsyncSession,
    company_id: uuid.UUID,
    notif_type: str,
    title: str,
    message: Optional[str] = None,
    link_url: Optional[str] = None,
) -> int:
    """Create an in-app notification for every active member of the company."""
    from app.db.models.user import User

    stmt = select(User.id).where(User.company_id == company_id, User.is_active.is_(True))
    user_ids = (await db.execute(stmt)).scalars().all()
    if not user_ids:
        return 0

    rows = [
        Notification(
            user_id=uid,
            company_id=company_id,
            type=notif_type,
            title=title,
            message=message,
            link_url=link_url,
        )
        for uid in user_ids
    ]
    db.add_all(rows)
    logger.info("notification_created", type=notif_type, company_id=str(company_id), users=len(rows))
    return len(rows)
