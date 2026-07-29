from __future__ import annotations

from pathlib import Path

from starpulse.collector.client import DishCoordinates
from starpulse.collector.repository import save_sample
from starpulse.config.settings import load_settings
from starpulse.db.session import Database
from starpulse.services.geoip import FixedGeoIpProvider, GeoIpResult, NullGeoIpProvider
from starpulse.services.location import LOCATION_REQUIRED_MESSAGE, build_location_status, resolve_weather_location

from tests.collector.factories import FakeStarlinkClient, make_sample


class FakeCollector:
    def __init__(self, dish_location: DishCoordinates | None = None) -> None:
        self.dish_location = dish_location


def test_resolve_prefers_manual_over_dish_gps(tmp_path: Path) -> None:
    settings = load_settings(
        data_dir=tmp_path / "data",
        env={"STARPULSE_WEATHER_LATITUDE": "51.5", "STARPULSE_WEATHER_LONGITUDE": "-0.1"},
    )
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        collector = FakeCollector(DishCoordinates(latitude=52.4, longitude=0.7, altitude_m=12.0))
        resolved = resolve_weather_location(
            settings, collector, session, persist=False, geoip_provider=NullGeoIpProvider()
        )
        assert resolved is not None
        assert resolved.source == "configured"
        assert resolved.latitude == 51.5
    finally:
        session.close()


def test_resolve_geoip_when_no_manual(tmp_path: Path) -> None:
    settings = load_settings(data_dir=tmp_path / "data", env={})
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        geoip = FixedGeoIpProvider(
            GeoIpResult(latitude=40.7, longitude=-74.0, place_name="New York, US", accuracy="City level only")
        )
        resolved = resolve_weather_location(
            settings, FakeCollector(None), session, persist=False, geoip_provider=geoip
        )
        assert resolved is not None
        assert resolved.source == "geoip"
        assert resolved.latitude == 40.7
        assert resolved.place_name == "New York, US"
    finally:
        session.close()


def test_resolve_dish_gps_as_advanced_fallback(tmp_path: Path) -> None:
    settings = load_settings(data_dir=tmp_path / "data", env={})
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        collector = FakeCollector(DishCoordinates(latitude=52.4, longitude=0.7))
        resolved = resolve_weather_location(
            settings, collector, session, persist=False, geoip_provider=NullGeoIpProvider()
        )
        assert resolved is not None
        assert resolved.source == "dish_gps"
    finally:
        session.close()


def test_build_location_status_no_location_is_location_required(tmp_path: Path) -> None:
    settings = load_settings(data_dir=tmp_path / "data", env={})
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        save_sample(session, make_sample(gps_valid=True, gps_enabled=True, latitude=None, longitude=None))
        status = build_location_status(
            settings,
            FakeCollector(None),
            session,
            persist=False,
            geoip_provider=NullGeoIpProvider(),
        )
        assert status.available is False
        assert status.message == LOCATION_REQUIRED_MESSAGE
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
