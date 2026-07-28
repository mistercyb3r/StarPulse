from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from starpulse.collector.repository import (
    count_samples,
    get_health_score,
    get_latest_sample,
    get_recent_samples,
    get_summary,
    save_sample,
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
