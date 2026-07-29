"""Unit tests for email notification helpers and cooldown/history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from starpulse.config.settings import load_settings
from starpulse.db.models import NotificationEvent
from starpulse.db.session import Database
from starpulse.services.notifications import (
    EVENT_HIGH_LATENCY,
    EVENT_STARLINK_OFFLINE,
    EVENT_TEST,
    STATUS_SENT,
    STATUS_SUPPRESSED,
    NotificationService,
    build_alert_body,
    format_duration,
    is_in_cooldown,
    list_notification_history,
)
from tests.collector.factories import make_sample


def test_build_alert_body_matches_example_shape() -> None:
    started = datetime(2026, 7, 29, 13, 32, tzinfo=timezone.utc)
    body = build_alert_body(
        summary="Starlink connection lost.",
        started=started,
        duration_seconds=12 * 60,
        last_latency_ms=35,
    )
    assert "Starlink connection lost." in body
    assert "Started:" in body
    assert "Duration:" in body
    assert "12 minutes" in body
    assert "Last known latency:" in body
    assert "35 ms" in body


def test_format_duration() -> None:
    assert format_duration(60) == "1 minute"
    assert format_duration(12 * 60) == "12 minutes"


def test_cooldown_blocks_repeat_sends(tmp_path: Path) -> None:
    db = Database(tmp_path / "n.db")
    db.init_db()
    session = next(db.get_session())
    try:
        session.add(
            NotificationEvent(
                timestamp=datetime.now(timezone.utc) - timedelta(seconds=30),
                event_type=EVENT_STARLINK_OFFLINE,
                channel="email",
                subject="x",
                body="y",
                status=STATUS_SENT,
            )
        )
        session.commit()
        assert is_in_cooldown(session, EVENT_STARLINK_OFFLINE, 900) is True
        assert is_in_cooldown(session, EVENT_HIGH_LATENCY, 900) is False
    finally:
        session.close()


def test_notify_suppressed_when_disabled(tmp_path: Path) -> None:
    settings = load_settings(data_dir=tmp_path / "data", env={})
    settings.notifications.enabled = False
    settings.notifications.smtp_host = "smtp.example.com"
    settings.notifications.smtp_to = "a@b.c"
    settings.notifications.smtp_from = "a@b.c"
    db = Database(tmp_path / "data" / "db.sqlite")
    db.init_db()
    service = NotificationService(db, settings)

    with patch("starpulse.services.notifications.send_smtp_email") as send:
        result = service.notify(EVENT_TEST, subject="s", body="b")
        send.assert_not_called()

    assert result.status == STATUS_SUPPRESSED
    session = next(db.get_session())
    try:
        history = list_notification_history(session)
        assert len(history) == 1
        assert history[0].status == STATUS_SUPPRESSED
    finally:
        session.close()


def test_notify_sends_when_enabled(tmp_path: Path) -> None:
    settings = load_settings(data_dir=tmp_path / "data", env={})
    settings.notifications.enabled = True
    settings.notifications.smtp_host = "smtp.example.com"
    settings.notifications.smtp_to = "a@b.c"
    settings.notifications.smtp_from = "a@b.c"
    settings.notifications.cooldown_seconds = 0
    db = Database(tmp_path / "data" / "db.sqlite")
    db.init_db()
    service = NotificationService(db, settings)

    with patch("starpulse.services.notifications.send_smtp_email") as send:
        result = service.notify(EVENT_STARLINK_OFFLINE, subject="🚨 StarPulse Alert - Starlink Offline", body="x")
        send.assert_called_once()

    assert result.ok is True
    assert result.status == STATUS_SENT


def test_evaluate_sample_warnings_high_latency(tmp_path: Path) -> None:
    settings = load_settings(data_dir=tmp_path / "data", env={})
    settings.notifications.enabled = True
    settings.notifications.smtp_host = "smtp.example.com"
    settings.notifications.smtp_to = "a@b.c"
    settings.notifications.smtp_from = "a@b.c"
    settings.notifications.cooldown_seconds = 0
    settings.notifications.latency_warn_ms = 50
    db = Database(tmp_path / "data" / "db.sqlite")
    db.init_db()
    service = NotificationService(db, settings)

    with patch("starpulse.services.notifications.send_smtp_email"):
        results = service.evaluate_sample_warnings(make_sample(latency_ms=120.0))

    assert any(r.status == STATUS_SENT for r in results)


def test_outage_tracker_notifies_on_open_close(tmp_path: Path) -> None:
    from starpulse.collector.outages import OutageTracker

    settings = load_settings(data_dir=tmp_path / "data", env={})
    settings.notifications.enabled = True
    settings.notifications.smtp_host = "smtp.example.com"
    settings.notifications.smtp_to = "a@b.c"
    settings.notifications.smtp_from = "a@b.c"
    settings.notifications.cooldown_seconds = 0
    db = Database(tmp_path / "data" / "db.sqlite")
    db.init_db()
    service = NotificationService(db, settings)
    tracker = OutageTracker(db, notifications=service)

    with patch("starpulse.services.notifications.send_smtp_email") as send:
        tracker.record_success(make_sample(connection_state="SEARCHING"))
        tracker.record_success(make_sample(connection_state="CONNECTED", ping_drop_rate=0.0))
        assert send.call_count == 2
