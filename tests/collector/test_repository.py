from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from starpulse.collector.repository import (
    close_open_connection_event,
    count_samples,
    get_connection_events,
    get_health_score,
    get_latest_sample,
    get_open_connection_event,
    get_outage_summary,
    get_recent_samples,
    get_summary,
    save_sample,
    upsert_open_connection_event,
)
from starpulse.db.session import Database

from tests.collector.factories import make_sample


def test_save_sample_persists_all_fields(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        sample = make_sample(
            connection_state="CONNECTED",
            download_bps=100.0,
            power_watts=33.3,
            hardware_version="rev3_prod2400",
            gps_satellites=12,
            azimuth_deg=180.5,
        )
        row = save_sample(session, sample)

        assert row.id is not None
        assert row.connection_state == "CONNECTED"
        assert row.download_bps == 100.0
        assert row.power_watts == 33.3
        assert row.hardware_version == "rev3_prod2400"
        assert row.gps_satellites == 12
        assert row.azimuth_deg == pytest.approx(180.5)
        assert count_samples(session) == 1
    finally:
        session.close()


def test_get_latest_sample_returns_most_recent(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        older = make_sample(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), connection_state="CONNECTED")
        newer = make_sample(timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc), connection_state="SEARCHING")

        save_sample(session, older)
        save_sample(session, newer)

        latest = get_latest_sample(session)
        assert latest is not None
        assert latest.connection_state == "SEARCHING"

        recent = get_recent_samples(session, limit=10)
        assert [row.connection_state for row in recent] == ["CONNECTED", "SEARCHING"]
    finally:
        session.close()


def test_get_latest_sample_returns_none_when_empty(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        assert get_latest_sample(session) is None
        assert count_samples(session) == 0
    finally:
        session.close()


def test_get_recent_samples_filters_by_range(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(5):
            save_sample(session, make_sample(timestamp=base + timedelta(hours=i), connection_state=f"S{i}"))

        rows = get_recent_samples(session, start=base + timedelta(hours=1), end=base + timedelta(hours=3))

        assert [row.connection_state for row in rows] == ["S1", "S2", "S3"]
    finally:
        session.close()


def test_get_recent_samples_treats_naive_datetimes_as_utc(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        save_sample(session, make_sample(timestamp=datetime(2026, 1, 1, 12, tzinfo=timezone.utc)))

        # Naive datetime (no tzinfo) should be treated as UTC, not rejected or silently wrong.
        rows = get_recent_samples(session, start=datetime(2026, 1, 1, 0, 0, 0))

        assert len(rows) == 1
    finally:
        session.close()


def test_get_summary_with_no_samples(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        stats = get_summary(session)

        assert stats.sample_count == 0
        assert stats.average_download_bps is None
        assert stats.average_upload_bps is None
        assert stats.average_latency_ms is None
        assert stats.average_obstruction_percent is None
        assert stats.uptime_percent is None
    finally:
        session.close()


def test_get_summary_computes_averages_and_uptime(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        save_sample(
            session,
            make_sample(
                timestamp=base,
                connection_state="CONNECTED",
                download_bps=100.0,
                upload_bps=10.0,
                latency_ms=20.0,
                obstruction_percent=0.0,
                power_watts=30.0,
            ),
        )
        save_sample(
            session,
            make_sample(
                timestamp=base + timedelta(hours=1),
                connection_state="SEARCHING",
                download_bps=300.0,
                upload_bps=30.0,
                latency_ms=60.0,
                obstruction_percent=4.0,
                power_watts=40.0,
            ),
        )

        stats = get_summary(session)

        assert stats.sample_count == 2
        assert stats.average_download_bps == pytest.approx(200.0)
        assert stats.average_upload_bps == pytest.approx(20.0)
        assert stats.average_latency_ms == pytest.approx(40.0)
        assert stats.average_obstruction_percent == pytest.approx(2.0)
        assert stats.uptime_percent == pytest.approx(50.0)
        assert stats.peak_download_bps == pytest.approx(300.0)
        assert stats.peak_upload_bps == pytest.approx(30.0)
        assert stats.best_latency_ms == pytest.approx(20.0)
        assert stats.worst_latency_ms == pytest.approx(60.0)
        assert stats.average_power_watts == pytest.approx(35.0)
        assert stats.min_power_watts == pytest.approx(30.0)
        assert stats.max_power_watts == pytest.approx(40.0)
    finally:
        session.close()


def test_get_summary_respects_time_range(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        save_sample(session, make_sample(timestamp=base, connection_state="SEARCHING"))
        save_sample(session, make_sample(timestamp=base + timedelta(hours=1), connection_state="CONNECTED"))

        stats = get_summary(session, start=base + timedelta(minutes=30))

        assert stats.sample_count == 1
        assert stats.uptime_percent == pytest.approx(100.0)
    finally:
        session.close()


def test_get_health_score_with_no_samples(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        health = get_health_score(session)

        assert health.score is None
        assert health.quality_label == "Unknown"
        assert health.obstruction_impact == "Unknown"
        assert health.sample_count == 0
    finally:
        session.close()


def test_get_health_score_perfect_connection(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i in range(3):
            save_sample(
                session,
                make_sample(
                    timestamp=base + timedelta(minutes=i),
                    connection_state="CONNECTED",
                    latency_ms=15.0,
                    obstruction_percent=0.0,
                ),
            )

        health = get_health_score(session, start=base, end=base + timedelta(hours=1))

        assert health.score == pytest.approx(100.0)
        assert health.quality_label == "Excellent"
        assert health.uptime_percent == pytest.approx(100.0)
        assert health.obstruction_impact == "None"
    finally:
        session.close()


def test_get_health_score_penalizes_downtime_latency_and_obstruction(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        save_sample(
            session,
            make_sample(
                timestamp=base,
                connection_state="SEARCHING",
                latency_ms=120.0,
                obstruction_percent=8.0,
            ),
        )

        health = get_health_score(session, start=base, end=base + timedelta(hours=1))

        # 0% uptime alone drives the score to the floor, regardless of other penalties.
        assert health.score == pytest.approx(0.0)
        assert health.quality_label == "Critical"
        assert health.uptime_percent == pytest.approx(0.0)
        assert health.obstruction_impact == "Moderate"
    finally:
        session.close()


def test_get_health_score_defaults_to_last_hour(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        old = datetime.now(timezone.utc) - timedelta(hours=5)
        save_sample(session, make_sample(timestamp=old, connection_state="SEARCHING", latency_ms=500.0))

        health = get_health_score(session)

        assert health.sample_count == 0
        assert health.score is None
    finally:
        session.close()


def test_upsert_open_connection_event_creates_then_updates_reason(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)

        event = upsert_open_connection_event(session, at=base, reason="disconnected")
        assert event.id is not None
        assert event.end_time is None
        assert event.reason == "disconnected"

        # A second call while still open updates the reason in place rather
        # than creating a second open event.
        updated = upsert_open_connection_event(session, at=base + timedelta(seconds=5), reason="high_packet_loss")
        assert updated.id == event.id
        assert updated.reason == "high_packet_loss"
        assert updated.start_time.replace(tzinfo=timezone.utc) == base

        open_event = get_open_connection_event(session)
        assert open_event is not None
        assert open_event.id == event.id
    finally:
        session.close()


def test_close_open_connection_event_sets_end_time_and_duration(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        upsert_open_connection_event(session, at=base, reason="disconnected")

        closed = close_open_connection_event(session, end_time=base + timedelta(minutes=2))

        assert closed is not None
        assert closed.end_time.replace(tzinfo=timezone.utc) == base + timedelta(minutes=2)
        assert closed.duration_seconds == pytest.approx(120.0)
        assert get_open_connection_event(session) is None
    finally:
        session.close()


def test_close_open_connection_event_returns_none_when_nothing_open(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        assert close_open_connection_event(session, end_time=datetime.now(timezone.utc)) is None
    finally:
        session.close()


def test_get_connection_events_filters_by_range(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        upsert_open_connection_event(session, at=base, reason="disconnected")
        close_open_connection_event(session, end_time=base + timedelta(minutes=1))

        upsert_open_connection_event(session, at=base + timedelta(days=2), reason="high_packet_loss")
        close_open_connection_event(session, end_time=base + timedelta(days=2, minutes=1))

        events = get_connection_events(session, start=base + timedelta(days=1), end=base + timedelta(days=3))

        assert len(events) == 1
        assert events[0].reason == "high_packet_loss"
    finally:
        session.close()


def test_get_outage_summary_with_no_events(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        summary = get_outage_summary(session)

        assert summary.outages_today == 0
        assert summary.outages_last_7d == 0
        assert summary.total_downtime_minutes_last_7d == 0.0
        assert summary.events == []
    finally:
        session.close()


def test_get_outage_summary_counts_and_downtime(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        now = datetime.now(timezone.utc)

        # Closed event, started+ended today.
        upsert_open_connection_event(session, at=now - timedelta(hours=2), reason="disconnected")
        close_open_connection_event(session, end_time=now - timedelta(hours=2) + timedelta(minutes=5))

        # Closed event from 3 days ago (counts toward the week, not "today").
        old_start = now - timedelta(days=3)
        upsert_open_connection_event(session, at=old_start, reason="high_packet_loss")
        close_open_connection_event(session, end_time=old_start + timedelta(minutes=10))

        summary = get_outage_summary(session, now=now)

        assert summary.outages_today == 1
        assert summary.outages_last_7d == 2
        assert summary.total_downtime_minutes_last_7d == pytest.approx(15.0)
        assert len(summary.events) == 2
    finally:
        session.close()


def test_get_outage_summary_counts_ongoing_event_downtime(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        now = datetime.now(timezone.utc)
        upsert_open_connection_event(session, at=now - timedelta(minutes=10), reason="dish_unavailable")

        summary = get_outage_summary(session, now=now)

        assert summary.outages_today == 1
        assert summary.total_downtime_minutes_last_7d == pytest.approx(10.0, rel=1e-2)
        assert summary.events[0].end_time is None
    finally:
        session.close()
