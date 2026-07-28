from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from starpulse.collector.repository import save_sample, upsert_open_connection_event
from starpulse.db.session import Database
from starpulse.services.weather import WeatherSnapshot
from starpulse.services.weather_impact import compute_weather_impact
from starpulse.services.weather_repository import save_weather_sample

from tests.collector.factories import make_sample


def _snapshot(**overrides) -> WeatherSnapshot:
    base = dict(
        temperature_c=18.0,
        feels_like_c=17.0,
        humidity_percent=50.0,
        wind_speed_kph=10.0,
        conditions="Clear sky",
        precipitation_mm=0.0,
        precipitation_probability=5.0,
        latitude=51.5,
        longitude=-0.1,
        fetched_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return WeatherSnapshot(**base)


def test_compute_weather_impact_low_for_benign_weather(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        impact = compute_weather_impact(session, _snapshot())
        assert impact.severity == "Low"
        assert "Clear sky" in impact.reasons or "Low wind" in impact.reasons
    finally:
        session.close()


def test_compute_weather_impact_high_for_thunderstorm(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        impact = compute_weather_impact(
            session,
            _snapshot(conditions="Thunderstorm", precipitation_probability=90.0, precipitation_mm=5.0),
        )
        assert impact.severity == "High"
    finally:
        session.close()


def test_compute_weather_impact_bumps_for_active_outage(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        upsert_open_connection_event(session, at=datetime.now(timezone.utc), reason="disconnected")
        impact = compute_weather_impact(session, _snapshot(conditions="Clear sky"))
        assert impact.severity == "High"
        assert impact.active_outage is True
        assert any("outage" in reason.lower() for reason in impact.reasons)
    finally:
        session.close()


def test_compute_weather_impact_detects_latency_regression(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        now = datetime.now(timezone.utc)
        # Good-weather baseline samples with low latency.
        for hours_ago in (30, 28, 26):
            save_weather_sample(
                session,
                _snapshot(
                    conditions="Clear sky",
                    precipitation_probability=5.0,
                    fetched_at=now - timedelta(hours=hours_ago),
                ),
                location_source="configured",
            )
            save_sample(
                session,
                make_sample(
                    timestamp=now - timedelta(hours=hours_ago),
                    latency_ms=20.0,
                    download_bps=200_000_000.0,
                    connection_state="CONNECTED",
                ),
            )

        # Recent degraded performance.
        for minutes_ago in (50, 40, 30, 20, 10):
            save_sample(
                session,
                make_sample(
                    timestamp=now - timedelta(minutes=minutes_ago),
                    latency_ms=40.0,
                    download_bps=100_000_000.0,
                    connection_state="CONNECTED",
                ),
            )

        impact = compute_weather_impact(session, _snapshot(conditions="Partly cloudy"), now=now)
        assert impact.latency_delta_percent is not None
        assert impact.latency_delta_percent >= 25
        assert impact.severity in {"Moderate", "High"}
        assert any("Latency increased" in reason for reason in impact.reasons)
    finally:
        session.close()


def test_save_and_list_weather_history(tmp_path: Path) -> None:
    from starpulse.services.weather_repository import get_weather_history

    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        now = datetime.now(timezone.utc)
        save_weather_sample(session, _snapshot(fetched_at=now - timedelta(hours=2)), "configured")
        save_weather_sample(session, _snapshot(fetched_at=now - timedelta(hours=1)), "dish_gps")

        rows = get_weather_history(session, start=now - timedelta(hours=3), end=now)
        assert len(rows) == 2
        assert rows[0].location_source == "configured"
        assert rows[1].location_source == "dish_gps"
    finally:
        session.close()
