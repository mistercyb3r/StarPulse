"""Email notification dispatch for StarPulse alerts.

Sends SMTP email for Starlink offline/recovered and performance warnings,
enforces per-event-type cooldowns, and persists every attempt in SQLite.
"""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from starpulse.collector.client import StarlinkSample
from starpulse.config.settings import NotificationsSettings, Settings
from starpulse.db.models import ConnectionEvent, NotificationEvent
from starpulse.db.session import Database
from starpulse.logging_config import get_logger

logger = get_logger(__name__)

EVENT_STARLINK_OFFLINE = "starlink_offline"
EVENT_STARLINK_RECOVERED = "starlink_recovered"
EVENT_HIGH_LATENCY = "high_latency"
EVENT_PACKET_LOSS = "packet_loss"
EVENT_HIGH_OBSTRUCTION = "high_obstruction"
EVENT_SERVER_HEALTH = "server_health"
EVENT_TEST = "test"

STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_SUPPRESSED = "suppressed"

CHANNEL_EMAIL = "email"

REASON_LABELS = {
    "disconnected": "Starlink connection lost.",
    "high_packet_loss": "Starlink degraded due to high packet loss.",
    "dish_unavailable": "Starlink dish unreachable.",
}


@dataclass(frozen=True)
class NotificationResult:
    ok: bool
    status: str
    message: str
    event_id: int | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_local_timestamp(value: datetime) -> str:
    """Format a UTC datetime as ``YYYY-MM-DD HH:MM`` in local time."""
    local = _ensure_utc(value).astimezone()
    return local.strftime("%Y-%m-%d %H:%M")


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes} minutes" if minutes != 1 else "1 minute"
    return f"{secs} seconds"


def _smtp_ready(cfg: NotificationsSettings) -> bool:
    return bool(cfg.smtp_host.strip() and cfg.smtp_to.strip() and (cfg.smtp_from.strip() or cfg.smtp_user.strip()))


def build_alert_body(
    *,
    summary: str,
    started: datetime | None = None,
    ended: datetime | None = None,
    duration_seconds: float | None = None,
    last_latency_ms: float | None = None,
    extra_lines: list[tuple[str, str]] | None = None,
) -> str:
    lines = [summary, ""]
    if started is not None:
        lines.append(f"Started:\n{format_local_timestamp(started)}")
        lines.append("")
    if ended is not None:
        lines.append(f"Ended:\n{format_local_timestamp(ended)}")
        lines.append("")
    if duration_seconds is not None:
        lines.append(f"Duration:\n{format_duration(duration_seconds)}")
        lines.append("")
    if last_latency_ms is not None:
        lines.append(f"Last known latency:\n{int(round(last_latency_ms))} ms")
        lines.append("")
    for label, value in extra_lines or []:
        lines.append(f"{label}:\n{value}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def send_smtp_email(cfg: NotificationsSettings, *, subject: str, body: str) -> None:
    """Send one email via SMTP. Raises on failure."""
    if not _smtp_ready(cfg):
        raise ValueError("SMTP is not fully configured (host, from/user, and to are required)")

    from_addr = (cfg.smtp_from or cfg.smtp_user).strip()
    to_addr = cfg.smtp_to.strip()

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_addr
    message["To"] = to_addr
    message.set_content(body)

    if cfg.smtp_use_tls:
        context = ssl.create_default_context()
        with smtplib.SMTP(cfg.smtp_host.strip(), cfg.smtp_port, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            if cfg.smtp_user.strip():
                smtp.login(cfg.smtp_user.strip(), cfg.smtp_password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(cfg.smtp_host.strip(), cfg.smtp_port, timeout=20) as smtp:
            if cfg.smtp_user.strip():
                smtp.login(cfg.smtp_user.strip(), cfg.smtp_password)
            smtp.send_message(message)


def last_sent_at(session: Session, event_type: str) -> datetime | None:
    stmt = (
        select(NotificationEvent.timestamp)
        .where(
            NotificationEvent.event_type == event_type,
            NotificationEvent.status == STATUS_SENT,
        )
        .order_by(NotificationEvent.timestamp.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def is_in_cooldown(session: Session, event_type: str, cooldown_seconds: float, *, now: datetime | None = None) -> bool:
    if cooldown_seconds <= 0:
        return False
    last = last_sent_at(session, event_type)
    if last is None:
        return False
    now = now or _utcnow()
    return _ensure_utc(now) - _ensure_utc(last) < timedelta(seconds=cooldown_seconds)


def list_notification_history(session: Session, *, limit: int = 50) -> list[NotificationEvent]:
    stmt = select(NotificationEvent).order_by(NotificationEvent.timestamp.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


class NotificationService:
    """Evaluates alert conditions and sends email with cooldown + history."""

    def __init__(self, database: Database, settings: Settings) -> None:
        self._database = database
        self._settings = settings

    @property
    def config(self) -> NotificationsSettings:
        return self._settings.notifications

    def reload_settings(self, settings: Settings) -> None:
        self._settings = settings

    def notify(
        self,
        event_type: str,
        *,
        subject: str,
        body: str,
        respect_cooldown: bool = True,
        force: bool = False,
    ) -> NotificationResult:
        cfg = self.config
        session = next(self._database.get_session())
        try:
            if not force and not cfg.enabled:
                return self._record(
                    session,
                    event_type=event_type,
                    subject=subject,
                    body=body,
                    status=STATUS_SUPPRESSED,
                    error_message="Notifications are disabled",
                )

            if not _smtp_ready(cfg):
                return self._record(
                    session,
                    event_type=event_type,
                    subject=subject,
                    body=body,
                    status=STATUS_SUPPRESSED,
                    error_message="SMTP is not fully configured",
                )

            if respect_cooldown and not force and is_in_cooldown(session, event_type, cfg.cooldown_seconds):
                return self._record(
                    session,
                    event_type=event_type,
                    subject=subject,
                    body=body,
                    status=STATUS_SUPPRESSED,
                    error_message=f"Cooldown active ({int(cfg.cooldown_seconds)}s)",
                )

            try:
                send_smtp_email(cfg, subject=subject, body=body)
            except Exception as exc:
                logger.warning("Failed to send notification email (%s): %s", event_type, exc)
                return self._record(
                    session,
                    event_type=event_type,
                    subject=subject,
                    body=body,
                    status=STATUS_FAILED,
                    error_message=str(exc),
                )

            logger.info("Sent notification email: %s", event_type)
            return self._record(
                session,
                event_type=event_type,
                subject=subject,
                body=body,
                status=STATUS_SENT,
                error_message=None,
            )
        finally:
            session.close()

    def send_test_email(self) -> NotificationResult:
        subject = "🚨 StarPulse Alert - Test Email"
        body = build_alert_body(
            summary="This is a test email from StarPulse.",
            started=_utcnow(),
            extra_lines=[("Status", "If you received this, SMTP is configured correctly.")],
        )
        return self.notify(EVENT_TEST, subject=subject, body=body, respect_cooldown=False, force=True)

    def on_outage_opened(self, event: ConnectionEvent, sample: StarlinkSample | None = None) -> NotificationResult:
        reason = event.reason
        summary = REASON_LABELS.get(reason, "Starlink connection lost.")
        subject = "🚨 StarPulse Alert - Starlink Offline"
        body = build_alert_body(
            summary=summary,
            started=event.start_time,
            last_latency_ms=sample.latency_ms if sample is not None else None,
            extra_lines=[("Reason", reason.replace("_", " "))],
        )
        return self.notify(EVENT_STARLINK_OFFLINE, subject=subject, body=body)

    def on_outage_closed(self, event: ConnectionEvent, sample: StarlinkSample | None = None) -> NotificationResult:
        subject = "🚨 StarPulse Alert - Starlink Recovered"
        body = build_alert_body(
            summary="Starlink connection recovered.",
            started=event.start_time,
            ended=event.end_time,
            duration_seconds=event.duration_seconds,
            last_latency_ms=sample.latency_ms if sample is not None else None,
        )
        return self.notify(EVENT_STARLINK_RECOVERED, subject=subject, body=body)

    def evaluate_sample_warnings(self, sample: StarlinkSample, *, health_score: float | None = None) -> list[NotificationResult]:
        """Emit performance/health warnings for a healthy connected sample."""
        cfg = self.config
        results: list[NotificationResult] = []

        if sample.latency_ms is not None and sample.latency_ms >= cfg.latency_warn_ms:
            subject = "🚨 StarPulse Alert - High Latency Warning"
            body = build_alert_body(
                summary="Starlink latency is elevated.",
                started=sample.timestamp,
                last_latency_ms=sample.latency_ms,
                extra_lines=[("Threshold", f"{cfg.latency_warn_ms:g} ms")],
            )
            results.append(self.notify(EVENT_HIGH_LATENCY, subject=subject, body=body))

        if sample.ping_drop_rate is not None and sample.ping_drop_rate >= cfg.packet_loss_warn:
            pct = sample.ping_drop_rate * 100.0
            subject = "🚨 StarPulse Alert - Packet Loss Warning"
            body = build_alert_body(
                summary="Starlink packet loss is elevated.",
                started=sample.timestamp,
                last_latency_ms=sample.latency_ms,
                extra_lines=[
                    ("Packet loss", f"{pct:.1f}%"),
                    ("Threshold", f"{cfg.packet_loss_warn * 100:g}%"),
                ],
            )
            results.append(self.notify(EVENT_PACKET_LOSS, subject=subject, body=body))

        if sample.obstruction_percent is not None and sample.obstruction_percent >= cfg.obstruction_warn_percent:
            subject = "🚨 StarPulse Alert - High Obstruction Percentage"
            body = build_alert_body(
                summary="Starlink obstruction percentage is high.",
                started=sample.timestamp,
                last_latency_ms=sample.latency_ms,
                extra_lines=[
                    ("Obstruction", f"{sample.obstruction_percent:.1f}%"),
                    ("Threshold", f"{cfg.obstruction_warn_percent:g}%"),
                ],
            )
            results.append(self.notify(EVENT_HIGH_OBSTRUCTION, subject=subject, body=body))

        if health_score is not None and health_score < cfg.health_warn_score:
            subject = "🚨 StarPulse Alert - Server Health Warning"
            body = build_alert_body(
                summary="StarPulse health score is below the warning threshold.",
                started=sample.timestamp,
                last_latency_ms=sample.latency_ms,
                extra_lines=[
                    ("Health score", f"{health_score:.0f}"),
                    ("Threshold", f"{cfg.health_warn_score:g}"),
                ],
            )
            results.append(self.notify(EVENT_SERVER_HEALTH, subject=subject, body=body))

        return results

    def on_dish_unavailable(self, at: datetime) -> NotificationResult:
        """Server/dish health warning when polls fail (in addition to offline event)."""
        subject = "🚨 StarPulse Alert - Server Health Warning"
        body = build_alert_body(
            summary="StarPulse could not reach the Starlink dish.",
            started=at,
            extra_lines=[("Status", "Dish poll failed")],
        )
        return self.notify(EVENT_SERVER_HEALTH, subject=subject, body=body)

    def _record(
        self,
        session: Session,
        *,
        event_type: str,
        subject: str,
        body: str,
        status: str,
        error_message: str | None,
    ) -> NotificationResult:
        row = NotificationEvent(
            timestamp=_utcnow(),
            event_type=event_type,
            channel=CHANNEL_EMAIL,
            subject=subject,
            body=body,
            status=status,
            error_message=error_message,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        ok = status == STATUS_SENT
        message = {
            STATUS_SENT: "Email sent",
            STATUS_FAILED: error_message or "Send failed",
            STATUS_SUPPRESSED: error_message or "Suppressed",
        }.get(status, status)
        return NotificationResult(ok=ok, status=status, message=message, event_id=row.id)


def settings_public_dict(cfg: NotificationsSettings) -> dict[str, Any]:
    """Settings payload safe to return over the API (password never included)."""
    return {
        "enabled": cfg.enabled,
        "smtp_host": cfg.smtp_host,
        "smtp_port": cfg.smtp_port,
        "smtp_user": cfg.smtp_user,
        "smtp_password_set": bool(cfg.smtp_password),
        "smtp_from": cfg.smtp_from,
        "smtp_to": cfg.smtp_to,
        "smtp_use_tls": cfg.smtp_use_tls,
        "cooldown_seconds": cfg.cooldown_seconds,
        "latency_warn_ms": cfg.latency_warn_ms,
        "packet_loss_warn": cfg.packet_loss_warn,
        "obstruction_warn_percent": cfg.obstruction_warn_percent,
        "health_warn_score": cfg.health_warn_score,
        "smtp_configured": _smtp_ready(cfg),
    }
