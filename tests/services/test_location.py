from __future__ import annotations

from pathlib import Path

from starpulse.collector.client import DishCoordinates
from starpulse.collector.repository import save_sample
from starpulse.config.settings import load_settings
from starpulse.db.session import Database
from starpulse.services.location import build_location_status, resolve_weather_location

from tests.collector.factories import FakeStarlinkClient, make_sample


class FakeCollector:
    def __init__(self, dish_location: DishCoordinates | None = None) -> None:
        self.dish_location = dish_location


def test_resolve_prefers_dish_gps_over_configured(tmp_path: Path) -> None:
    settings = load_settings(
        data_dir=tmp_path / "data",
        env={"STARPULSE_WEATHER_LATITUDE": "51.5", "STARPULSE_WEATHER_LONGITUDE": "-0.1"},
    )
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        collector = FakeCollector(DishCoordinates(latitude=52.4, longitude=0.7, altitude_m=12.0))
        resolved = resolve_weather_location(settings, collector, session, persist=False)
        assert resolved is not None
        assert resolved.source == "dish_gps"
        assert resolved.latitude == 52.4
        assert resolved.altitude_m == 12.0
    finally:
        session.close()


def test_resolve_configured_when_no_dish_gps(tmp_path: Path) -> None:
    settings = load_settings(
        data_dir=tmp_path / "data",
        env={"STARPULSE_WEATHER_LATITUDE": "51.5", "STARPULSE_WEATHER_LONGITUDE": "-0.1"},
    )
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        resolved = resolve_weather_location(settings, FakeCollector(None), session, persist=False)
        assert resolved is not None
        assert resolved.source == "configured"
        assert resolved.latitude == 51.5
    finally:
        session.close()


def test_build_location_status_locked_without_coordinates(tmp_path: Path) -> None:
    settings = load_settings(data_dir=tmp_path / "data", env={})
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        save_sample(session, make_sample(gps_valid=True, gps_enabled=True, latitude=None, longitude=None))
        status = build_location_status(settings, FakeCollector(None), session, persist=False)
        assert status.available is False
        assert status.coordinates_collected is False
        assert status.gps_valid is True
        assert status.message == "Coordinates: Not collected yet"
    finally:
        session.close()


def test_poller_persists_altitude_with_coordinates(tmp_path: Path) -> None:
    from starpulse.collector.poller import StarlinkPoller

    db = Database(tmp_path / "test.db")
    db.init_db()
    client = FakeStarlinkClient(
        samples=[make_sample()],
        location=DishCoordinates(latitude=52.4, longitude=0.7, altitude_m=22.5),
    )
    poller = StarlinkPoller(client, db, interval_seconds=999)
    row = poller.poll_once()

    assert row is not None
    assert row.latitude == 52.4
    assert row.longitude == 0.7
    assert row.altitude_m == 22.5
    assert poller.dish_location is not None
    assert poller.dish_location.altitude_m == 22.5
