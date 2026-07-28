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
    assert body["source_label"] == "Manual configuration"
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


def test_location_settings_reports_sources_and_privacy(tmp_path: Path) -> None:
    from starpulse.collector.client import DishCoordinates

    app = _make_app(
        tmp_path,
        env={"STARPULSE_WEATHER_LATITUDE": "54.6", "STARPULSE_WEATHER_LONGITUDE": "25.2"},
    )
    app.state.collector._dish_location = DishCoordinates(latitude=52.4, longitude=0.7)

    with TestClient(app) as client:
        response = client.get("/api/location/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["active_source"] == "dish_gps"
    assert body["active_source_label"] == "Starlink GPS"
    assert body["dish_gps_available"] is True
    assert body["manual_latitude"] == pytest.approx(54.6)
    assert body["manual_longitude"] == pytest.approx(25.2)
    assert body["privacy_note"].startswith("StarPulse does not require location sharing")


def test_save_manual_location_persists_as_fallback(tmp_path: Path) -> None:
    app = _make_app(tmp_path)

    with TestClient(app) as client:
        response = client.post("/api/location/manual", json={"latitude": 52.413, "longitude": 0.748})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["settings"]["manual_latitude"] == pytest.approx(52.413)
        assert body["settings"]["active_source"] == "configured"

        settings = client.get("/api/location/settings").json()
        assert settings["manual_longitude"] == pytest.approx(0.748)

    reloaded = load_settings(data_dir=tmp_path / "data", env={})
    assert reloaded.weather.latitude == pytest.approx(52.413)
    assert reloaded.weather.longitude == pytest.approx(0.748)


def test_clear_saved_location_removes_manual_and_stored(tmp_path: Path) -> None:
    from starpulse.db.models import AppMeta
    from starpulse.services.location import RESOLVED_LAT_KEY, RESOLVED_LON_KEY

    app = _make_app(
        tmp_path,
        env={"STARPULSE_WEATHER_LATITUDE": "51.5", "STARPULSE_WEATHER_LONGITUDE": "-0.1"},
    )
    session = next(app.state.db.get_session())
    try:
        session.add(AppMeta(key=RESOLVED_LAT_KEY, value="48.0"))
        session.add(AppMeta(key=RESOLVED_LON_KEY, value="2.0"))
        session.commit()
    finally:
        session.close()

    with TestClient(app) as client:
        response = client.post("/api/location/clear", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["settings"]["manual_latitude"] is None
        assert body["settings"]["manual_longitude"] is None
        assert body["settings"]["active_source"] is None

    reloaded = load_settings(data_dir=tmp_path / "data", env={})
    assert reloaded.weather.latitude is None
    assert reloaded.weather.longitude is None


def test_location_weather_test_uses_provided_coordinates(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    from starpulse.services.weather import WeatherSnapshot

    class OkWeather:
        def __init__(self) -> None:
            self.last_coords = None

        def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
            self.last_coords = (latitude, longitude)
            return WeatherSnapshot(
                temperature_c=12.0,
                feels_like_c=11.0,
                humidity_percent=70.0,
                wind_speed_kph=8.0,
                conditions="Clear sky",
                precipitation_mm=0.0,
                precipitation_probability=5.0,
                latitude=latitude,
                longitude=longitude,
                fetched_at=datetime.now(timezone.utc),
            )

    weather = OkWeather()
    settings = load_settings(data_dir=tmp_path / "data", env={})
    app = create_app(
        settings,
        start_collector=False,
        start_weather_sampler=False,
        weather_client=weather,
        place_resolver=NullPlaceNameResolver(),
    )

    with TestClient(app) as client:
        response = client.post("/api/location/test", json={"latitude": 52.4, "longitude": 0.7})

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["conditions"] == "Clear sky"
    assert weather.last_coords == (52.4, 0.7)
