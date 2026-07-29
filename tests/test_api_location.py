from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from starpulse.app import create_app
from starpulse.collector.client import DishCoordinates
from starpulse.collector.repository import save_sample
from starpulse.config.settings import load_settings
from starpulse.services.geocoding import NullPlaceNameResolver
from starpulse.services.geoip import FixedGeoIpProvider, GeoIpResult, NullGeoIpProvider
from starpulse.services.location import LOCATION_REQUIRED_MESSAGE
from starpulse.services.weather import WeatherSnapshot, WeatherUnavailableError

from tests.collector.factories import make_sample


class FakeWeatherClient:
    def __init__(self, result: WeatherSnapshot | Exception | None = None) -> None:
        self.calls = 0
        self.last_coords = None
        self._result = result

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        self.calls += 1
        self.last_coords = (latitude, longitude)
        if isinstance(self._result, Exception):
            raise self._result
        if self._result is not None:
            return self._result
        raise WeatherUnavailableError("not needed")


def _snapshot(**overrides) -> WeatherSnapshot:
    base = dict(
        temperature_c=12.0,
        feels_like_c=11.0,
        humidity_percent=70.0,
        wind_speed_kph=8.0,
        conditions="Clear sky",
        precipitation_mm=0.0,
        precipitation_probability=5.0,
        latitude=52.4,
        longitude=0.7,
        fetched_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return WeatherSnapshot(**base)


def _make_app(
    tmp_path: Path,
    *,
    env: dict[str, str] | None = None,
    place_resolver=None,
    geoip_provider=None,
    weather_client=None,
):
    settings = load_settings(data_dir=tmp_path / "data", env=env or {})
    return create_app(
        settings,
        start_collector=False,
        start_weather_sampler=False,
        weather_client=weather_client or FakeWeatherClient(),
        place_resolver=place_resolver if place_resolver is not None else NullPlaceNameResolver(),
        geoip_provider=geoip_provider if geoip_provider is not None else NullGeoIpProvider(),
    )


def test_location_manual_coordinates(tmp_path: Path) -> None:
    class Place:
        def resolve(self, latitude: float, longitude: float) -> str | None:
            return "Thetford, GB"

    app = _make_app(
        tmp_path,
        env={"STARPULSE_WEATHER_LATITUDE": "52.4128", "STARPULSE_WEATHER_LONGITUDE": "0.7471"},
        place_resolver=Place(),
        weather_client=FakeWeatherClient(_snapshot()),
    )

    with TestClient(app) as client:
        response = client.get("/api/location")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["source"] == "configured"
    assert body["source_label"] == "Manual configuration"
    assert body["place_name"] == "Thetford, GB"


def test_location_no_location_configured(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    session = next(app.state.db.get_session())
    try:
        save_sample(session, make_sample(gps_valid=True, latitude=None, longitude=None))
    finally:
        session.close()

    with TestClient(app) as client:
        response = client.get("/api/location")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["message"] == LOCATION_REQUIRED_MESSAGE
    assert body["latitude"] is None


def test_location_starlink_gps_fallback(tmp_path: Path) -> None:
    app = _make_app(tmp_path, weather_client=FakeWeatherClient(_snapshot(latitude=52.4, longitude=0.7)))
    app.state.collector._dish_location = DishCoordinates(latitude=52.4, longitude=0.7, altitude_m=18.0)

    with TestClient(app) as client:
        response = client.get("/api/location")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["source"] == "dish_gps"
    assert body["source_label"] == "Starlink GPS"


def test_location_geoip_fallback(tmp_path: Path) -> None:
    geoip = FixedGeoIpProvider(
        GeoIpResult(latitude=51.5, longitude=-0.1, place_name="London, GB", accuracy="City level only")
    )
    app = _make_app(
        tmp_path,
        geoip_provider=geoip,
        weather_client=FakeWeatherClient(_snapshot(latitude=51.5, longitude=-0.1)),
    )

    with TestClient(app) as client:
        response = client.get("/api/location")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["source"] == "geoip"
    assert body["approximate"] is True
    assert body["accuracy"] == "City level only"
    assert body["source_label"] == "Approximate IP location"


def test_manual_preferred_over_geoip_and_dish(tmp_path: Path) -> None:
    geoip = FixedGeoIpProvider(GeoIpResult(latitude=40.0, longitude=-74.0))
    app = _make_app(
        tmp_path,
        env={"STARPULSE_WEATHER_LATITUDE": "52.4", "STARPULSE_WEATHER_LONGITUDE": "0.7"},
        geoip_provider=geoip,
        weather_client=FakeWeatherClient(_snapshot()),
    )
    app.state.collector._dish_location = DishCoordinates(latitude=10.0, longitude=20.0)

    with TestClient(app) as client:
        body = client.get("/api/location").json()

    assert body["source"] == "configured"
    assert body["latitude"] == pytest.approx(52.4)


def test_location_settings_and_save_clear(tmp_path: Path) -> None:
    app = _make_app(tmp_path, weather_client=FakeWeatherClient(_snapshot()))

    with TestClient(app) as client:
        settings = client.get("/api/location/settings").json()
        assert settings["privacy_note"].startswith("StarPulse does not require location sharing")
        assert "Location required" in (settings["message"] or "Location required")

        saved = client.post("/api/location/manual", json={"latitude": 52.413, "longitude": 0.748}).json()
        assert saved["ok"] is True
        assert saved["settings"]["active_source"] == "configured"
        assert saved["settings"]["weather_ok"] is True

        cleared = client.post("/api/location/clear", json={}).json()
        assert cleared["ok"] is True
        assert cleared["settings"]["manual_latitude"] is None


def test_location_weather_test(tmp_path: Path) -> None:
    weather = FakeWeatherClient(_snapshot(conditions="Overcast"))
    app = _make_app(tmp_path, weather_client=weather)

    with TestClient(app) as client:
        response = client.post("/api/location/test", json={"latitude": 52.4, "longitude": 0.7})

    assert response.status_code == 200
    assert response.json()["conditions"] == "Overcast"
    assert weather.last_coords == (52.4, 0.7)


def test_weather_returns_location_required_when_missing(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        body = client.get("/api/weather").json()
    assert body["available"] is False
    assert body["message"] == LOCATION_REQUIRED_MESSAGE


def test_advanced_note_for_locked_gps_without_coords(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    session = next(app.state.db.get_session())
    try:
        save_sample(session, make_sample(gps_valid=True, latitude=None, longitude=None))
    finally:
        session.close()

    with TestClient(app) as client:
        settings = client.get("/api/location/settings").json()

    assert settings["advanced_note"] == "Starlink GPS locked but coordinates unavailable"
    # Dashboard location payload must not push that jargon as the main message.
    with TestClient(app) as client:
        location = client.get("/api/location").json()
    assert location["message"] == LOCATION_REQUIRED_MESSAGE
