from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from starpulse.app import create_app
from starpulse.collector.client import DishCoordinates
from starpulse.collector.repository import save_sample
from starpulse.config.settings import load_settings
from starpulse.services.geocoding import NullPlaceNameResolver
from starpulse.services.weather import WeatherSnapshot, WeatherUnavailableError

from tests.collector.factories import make_sample


class FakeWeatherClient:
    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        self.calls += 1
        raise WeatherUnavailableError("not needed")


class FakePlaceResolver:
    def __init__(self, place_name: str | None = "Thetford, GB") -> None:
        self.place_name = place_name
        self.calls: list[tuple[float, float]] = []

    def resolve(self, latitude: float, longitude: float) -> str | None:
        self.calls.append((latitude, longitude))
        return self.place_name


def _make_app(tmp_path: Path, *, env: dict[str, str] | None = None, place_resolver=None):
    settings = load_settings(data_dir=tmp_path / "data", env=env or {})
    return create_app(
        settings,
        start_collector=False,
        start_weather_sampler=False,
        weather_client=FakeWeatherClient(),
        place_resolver=place_resolver if place_resolver is not None else NullPlaceNameResolver(),
    )


def test_location_returns_dish_gps_coordinates(tmp_path: Path) -> None:
    place = FakePlaceResolver("Thetford, GB")
    app = _make_app(tmp_path, place_resolver=place)
    app.state.collector._dish_location = DishCoordinates(
        latitude=52.413, longitude=0.748, altitude_m=18.0
    )

    session = next(app.state.db.get_session())
    try:
        save_sample(session, make_sample(gps_valid=True, gps_enabled=True, gps_satellites=14))
    finally:
        session.close()

    with TestClient(app) as client:
        response = client.get("/api/location")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["coordinates_collected"] is True
    assert body["source"] == "dish_gps"
    assert body["source_label"] == "Starlink GPS"
    assert body["place_name"] == "Thetford, GB"
    assert body["latitude"] == pytest.approx(52.413)
    assert body["longitude"] == pytest.approx(0.748)
    assert body["altitude_m"] == pytest.approx(18.0)
    assert body["gps_valid"] is True
    assert place.calls == [(52.413, 0.748)]


def test_location_gps_locked_but_coordinates_not_collected(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    session = next(app.state.db.get_session())
    try:
        save_sample(
            session,
            make_sample(
                gps_valid=True,
                gps_enabled=True,
                latitude=None,
                longitude=None,
                altitude_m=None,
            ),
        )
    finally:
        session.close()

    with TestClient(app) as client:
        response = client.get("/api/location")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["coordinates_collected"] is False
    assert body["gps_valid"] is True
    assert "Coordinates: Not collected yet" in body["message"]
    assert body["latitude"] is None
    assert body["longitude"] is None


def test_location_manual_configuration_fallback(tmp_path: Path) -> None:
    place = FakePlaceResolver("Vilnius, LT")
    app = _make_app(
        tmp_path,
        env={"STARPULSE_WEATHER_LATITUDE": "54.6872", "STARPULSE_WEATHER_LONGITUDE": "25.2797"},
        place_resolver=place,
    )

    with TestClient(app) as client:
        response = client.get("/api/location")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["source"] == "configured"
    assert body["source_label"] == "Configured"
    assert body["place_name"] == "Vilnius, LT"
    assert body["latitude"] == pytest.approx(54.6872)
    assert body["longitude"] == pytest.approx(25.2797)


def test_weather_message_when_gps_locked_without_coords(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    session = next(app.state.db.get_session())
    try:
        save_sample(session, make_sample(gps_valid=True, latitude=None, longitude=None))
    finally:
        session.close()

    with TestClient(app) as client:
        response = client.get("/api/weather")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert "Coordinates: Not collected yet" in body["message"]
    assert "location sharing" in body["message"].lower() or "latitude" in body["message"].lower()
