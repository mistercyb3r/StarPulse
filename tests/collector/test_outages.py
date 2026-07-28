from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from starpulse.collector.outages import OutageTracker, classify_sample
from starpulse.collector.repository import get_open_connection_event
from starpulse.db.session import Database

from tests.collector.factories import make_sample


def test_classify_sample_returns_none_when_healthy() -> None:
    sample = make_sample(connection_state="CONNECTED", ping_drop_rate=0.01)

    assert classify_sample(sample) is None


def test_classify_sample_detects_disconnected_state() -> None:
    sample = make_sample(connection_state="SEARCHING", ping_drop_rate=0.0)

    assert classify_sample(sample) == "disconnected"


def test_classify_sample_detects_high_packet_loss_even_when_connected() -> None:
    sample = make_sample(connection_state="CONNECTED", ping_drop_rate=0.75)

    assert classify_sample(sample) == "high_packet_loss"


def test_classify_sample_tolerates_missing_ping_drop_rate() -> None:
    sample = make_sample(connection_state="CONNECTED", ping_drop_rate=None)

    assert classify_sample(sample) is None


def test_outage_tracker_record_success_opens_event_when_degraded(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    tracker = OutageTracker(db)

    tracker.record_success(make_sample(connection_state="SEARCHING"))

    session = next(db.get_session())
    try:
        event = get_open_connection_event(session)
        assert event is not None
        assert event.reason == "disconnected"
    finally:
        session.close()


def test_outage_tracker_record_success_closes_event_when_healthy(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    tracker = OutageTracker(db)

    tracker.record_success(make_sample(connection_state="SEARCHING"))
    tracker.record_success(make_sample(connection_state="CONNECTED", ping_drop_rate=0.0))

    session = next(db.get_session())
    try:
        assert get_open_connection_event(session) is None
    finally:
        session.close()


def test_outage_tracker_record_failure_opens_dish_unavailable_event(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    tracker = OutageTracker(db)

    tracker.record_failure(datetime.now(timezone.utc))

    session = next(db.get_session())
    try:
        event = get_open_connection_event(session)
        assert event is not None
        assert event.reason == "dish_unavailable"
    finally:
        session.close()
