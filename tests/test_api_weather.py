from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from starpulse.app import create_app
from starpulse.config.settings import load_settings
from starpulse.services.weather import WeatherSnapshot, WeatherUnavailableError


class FakeWeatherClient:
    def __init__(self, result: WeatherSnapshot | Exception) -> None:
        self._result = result
        self.calls = 0

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        self.calls += 1
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _make_app(tmp_path: Path, weather_client, env: dict[str, str] | None = None) -> FastAPI:
    settings = load_settings(data_dir=tmp_path / "data", env=env or {})
    return create_app(settings, start_collector=False, weather_client=weather_client)


def test_weather_unavailable_when_no_location_configured(tmp_path: Path) -> None:
    app = _make_app(tmp_path, FakeWeatherClient(Exception("should not be called")))
    with TestClient(app) as client:
        response = client.get("/api/weather")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["temperature_c"] is None
    assert "location" in body["message"].lower()


def test_weather_unavailable_when_disabled(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        FakeWeatherClient(Exception("should not be called")),
        env={"STARPULSE_WEATHER_ENABLED": "false", "STARPULSE_WEATHER_LATITUDE": "51.5", "STARPULSE_WEATHER_LONGITUDE": "-0.1"},
    )
    with TestClient(app) as client:
        response = client.get("/api/weather")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert "disabled" in body["message"].lower()


def test_weather_returns_snapshot_using_configured_location(tmp_path: Path) -> None:
    snapshot = WeatherSnapshot(
        temperature_c=18.0,
        feels_like_c=17.0,
        humidity_percent=65.0,
        wind_speed_kph=10.0,
        conditions="Partly cloudy",
        latitude=51.5,
        longitude=-0.1,
        fetched_at=datetime.now(timezone.utc),
    )
    app = _make_app(
        tmp_path,
        FakeWeatherClient(snapshot),
        env={"STARPULSE_WEATHER_LATITUDE": "51.5", "STARPULSE_WEATHER_LONGITUDE": "-0.1"},
    )
    with TestClient(app) as client:
        response = client.get("/api/weather")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["temperature_c"] == pytest.approx(18.0)
    assert body["conditions"] == "Partly cloudy"
    assert body["location_source"] == "configured"


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


def test_weather_prefers_dish_gps_over_configured_location(tmp_path: Path) -> None:
    snapshot = WeatherSnapshot(
        temperature_c=10.0,
        feels_like_c=9.0,
        humidity_percent=80.0,
        wind_speed_kph=5.0,
        conditions="Clear sky",
        latitude=40.0,
        longitude=10.0,
        fetched_at=datetime.now(timezone.utc),
    )
    app = _make_app(
        tmp_path,
        FakeWeatherClient(snapshot),
        env={"STARPULSE_WEATHER_LATITUDE": "51.5", "STARPULSE_WEATHER_LONGITUDE": "-0.1"},
    )
    app.state.collector._dish_location = (40.0, 10.0)

    with TestClient(app) as client:
        response = client.get("/api/weather")

    assert response.status_code == 200
    body = response.json()
    assert body["location_source"] == "dish_gps"
    assert body["latitude"] == pytest.approx(40.0)
