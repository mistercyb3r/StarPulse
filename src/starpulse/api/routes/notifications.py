"""Email notification settings, test send, and history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from starpulse.api.deps import get_db, get_settings
from starpulse.api.schemas import (
    NotificationHistoryItem,
    NotificationHistoryResponse,
    NotificationSettingsActionResponse,
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
    NotificationTestResponse,
)
from starpulse.config.settings import Settings
from starpulse.config.writer import update_config_file
from starpulse.logging_config import get_logger
from starpulse.services.notifications import (
    NotificationService,
    list_notification_history,
    settings_public_dict,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = get_logger(__name__)


def get_notifications(request: Request) -> NotificationService:
    return request.app.state.notifications


@router.get("/settings", response_model=NotificationSettingsResponse)
def get_notification_settings(settings: Settings = Depends(get_settings)) -> NotificationSettingsResponse:
    return NotificationSettingsResponse(**settings_public_dict(settings.notifications))


@router.post("/settings", response_model=NotificationSettingsActionResponse)
def update_notification_settings(
    payload: NotificationSettingsUpdate,
    settings: Settings = Depends(get_settings),
    notifications: NotificationService = Depends(get_notifications),
) -> NotificationSettingsActionResponse:
    updates: dict = {}
    data = payload.model_dump(exclude_unset=True)

    if "smtp_password" in data:
        password = data.pop("smtp_password")
        # Empty string means "leave unchanged" so the UI can omit secrets.
        if password is not None and password != "":
            updates["smtp_password"] = password

    for key, value in data.items():
        if value is not None:
            updates[key] = value

    if updates:
        update_config_file(settings.config_file, {"notifications": updates})
        for key, value in updates.items():
            setattr(settings.notifications, key, value)
        notifications.reload_settings(settings)
        logger.info("Notification settings updated (%s)", ", ".join(sorted(updates)))

    return NotificationSettingsActionResponse(
        ok=True,
        message="Notification settings saved.",
        settings=NotificationSettingsResponse(**settings_public_dict(settings.notifications)),
    )


@router.post("/test", response_model=NotificationTestResponse)
def test_notification_email(
    notifications: NotificationService = Depends(get_notifications),
) -> NotificationTestResponse:
    result = notifications.send_test_email()
    return NotificationTestResponse(
        ok=result.ok,
        status=result.status,
        message=result.message,
        event_id=result.event_id,
    )


@router.get("/history", response_model=NotificationHistoryResponse)
def get_notification_history(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> NotificationHistoryResponse:
    limit = max(1, min(limit, 200))
    rows = list_notification_history(db, limit=limit)
    return NotificationHistoryResponse(
        events=[
            NotificationHistoryItem(
                id=row.id,
                timestamp=row.timestamp,
                event_type=row.event_type,
                channel=row.channel,
                subject=row.subject,
                body=row.body,
                status=row.status,
                error_message=row.error_message,
            )
            for row in rows
        ],
        count=len(rows),
    )
