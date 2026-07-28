from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from starpulse.app import create_app
from starpulse.collector.repository import save_sample
from starpulse.config.settings import load_settings
from starpulse.services.weather import WeatherSnapshot, WeatherUnavailableError

from tests.collector.factories import make_sample


class FakeWeatherClient:
    def __init__(self, result: WeatherSnapshot | Exception) -> None:
        self._result = result
        self.calls = 0
        self.last_coords: tuple[float, float] | None = None

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        self.calls += 1
        self.last_coords = (latitude, longitude)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _snapshot(**overrides) -> WeatherSnapshot:
    base = WeatherSnapshot(
        temperature_c=18.0,
        feels_like_c=17.0,
        humidity_percent=65.0,
        wind_speed_kph=10.0,
        conditions="Partly cloudy",
        latitude=51.5,
        longitude=-0.1,
        fetched_at=datetime.now(timezone.utc),
    )
    return WeatherSnapshot(**{**base.__dict__, **overrides})


def _make_app(tmp_path: Path, weather_client, env: dict[str, str] | None = None) -> FastAPI:
    settings = load_settings(data_dir=tmp_path / "data", env=env or {})
    return create_app(settings, start_collector=False, weather_client=weather_client)


def test_weather_unavailable_when_no_location(tmp_path: Path) -> None:
    """Case 3: no configured coords and no dish GPS → location unavailable."""
    app = _make_app(tmp_path, FakeWeatherClient(Exception("should not be called")))
    with TestClient(app) as client:
        response = client.get("/api/weather")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["temperature_c"] is None
    assert body["message"] == "location unavailable"


def test_weather_unavailable_when_disabled(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        FakeWeatherClient(Exception("should not be called")),
        env={
            "STARPULSE_WEATHER_ENABLED": "false",
            "STARPULSE_WEATHER_LATITUDE": "51.5",
            "STARPULSE_WEATHER_LONGITUDE": "-0.1",
        },
    )
    with TestClient(app) as client:
        response = client.get("/api/weather")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert "disabled" in body["message"].lower()


def test_weather_uses_configured_location(tmp_path: Path) -> None:
    """Case 1: user-configured weather.latitude/longitude."""
    weather = FakeWeatherClient(_snapshot(latitude=51.5, longitude=-0.1))
    app = _make_app(
        tmp_path,
        weather,
        env={"STARPULSE_WEATHER_LATITUDE": "51.5", "STARPULSE_WEATHER_LONGITUDE": "-0.1"},
    )
    with TestClient(app) as client:
        response = client.get("/api/weather")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["location_source"] == "configured"
    assert body["temperature_c"] == pytest.approx(18.0)
    assert weather.last_coords == (51.5, -0.1)


def test_weather_uses_dish_gps_when_no_config(tmp_path: Path) -> None:
    """Case 2: no config → fall back to Starlink dish GPS."""
    weather = FakeWeatherClient(_snapshot(latitude=40.0, longitude=10.0))
    app = _make_app(tmp_path, weather)
    app.state.collector._dish_location = (40.0, 10.0)

    with TestClient(app) as client:
        response = client.get("/api/weather")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["location_source"] == "dish_gps"
    assert body["latitude"] == pytest.approx(40.0)
    assert weather.last_coords == (40.0, 10.0)


def test_weather_configured_location_overrides_dish_gps(tmp_path: Path) -> None:
    """Case 1 beats case 2: explicit config always wins over dish GPS."""
    weather = FakeWeatherClient(_snapshot(latitude=51.5, longitude=-0.1))
    app = _make_app(
        tmp_path,
        weather,
        env={"STARPULSE_WEATHER_LATITUDE": "51.5", "STARPULSE_WEATHER_LONGITUDE": "-0.1"},
    )
    app.state.collector._dish_location = (40.0, 10.0)

    with TestClient(app) as client:
        response = client.get("/api/weather")

    assert response.status_code == 200
    body = response.json()
    assert body["location_source"] == "configured"
    assert weather.last_coords == (51.5, -0.1)


def test_weather_falls_back_to_stored_telemetry_gps(tmp_path: Path) -> None:
    """Case 2 via DB: after restart, use latest GPS stored on a telemetry sample."""
    weather = FakeWeatherClient(_snapshot(latitude=55.0, longitude=12.0))
    app = _make_app(tmp_path, weather)

    session = next(app.state.db.get_session())
    try:
        save_sample(session, make_sample(latitude=55.0, longitude=12.0))
    finally:
        session.close()

    with TestClient(app) as client:
        response = client.get("/api/weather")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["location_source"] == "dish_gps"
    assert weather.last_coords == (55.0, 12.0)


def test_weather_returns_unavailable_when_upstream_fails(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        FakeWeatherClient(WeatherUnavailableError("upstream down")),
        env={"STARPULSE_WEATHER_LATITUDE": "51.5", "STARPULSE_WEATHER_LONGITUDE": "-0.1"},
    )
    with TestClient(app) as client:
        response = client.get("/api/weather")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert "unreachable" in body["message"].lower()
