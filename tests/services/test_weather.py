from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from starpulse.services import weather as weather_module
from starpulse.services.weather import (
    CachedWeatherProvider,
    OpenMeteoWeatherClient,
    WeatherSnapshot,
    WeatherUnavailableError,
    describe_weather_code,
)


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class FakeWeatherClient:
    def __init__(self, clock: FakeClock | None = None) -> None:
        self.calls = 0
        self.next_result: WeatherSnapshot | Exception | None = None
        self._clock = clock

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        self.calls += 1
        if isinstance(self.next_result, Exception):
            raise self.next_result
        if self.next_result is not None:
            return self.next_result
        return WeatherSnapshot(
            temperature_c=20.0,
            feels_like_c=19.0,
            humidity_percent=55.0,
            wind_speed_kph=12.0,
            conditions="Clear sky",
            precipitation_mm=0.0,
            precipitation_probability=5.0,
            latitude=latitude,
            longitude=longitude,
            fetched_at=self._clock() if self._clock is not None else datetime.now(timezone.utc),
        )


def test_describe_weather_code_maps_known_codes() -> None:
    assert describe_weather_code(0) == "Clear sky"
    assert describe_weather_code(95) == "Thunderstorm"


def test_describe_weather_code_handles_unknown_and_none() -> None:
    assert describe_weather_code(None) == "Unknown"
    assert describe_weather_code(12345) == "Unknown"


def test_get_weather_fetches_on_first_call() -> None:
    client = FakeWeatherClient()
    provider = CachedWeatherProvider(client, cache_seconds=600.0)

    snapshot = provider.get_weather(51.5, -0.1)

    assert client.calls == 1
    assert snapshot.temperature_c == pytest.approx(20.0)


def test_get_weather_uses_cache_within_ttl() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    client = FakeWeatherClient(clock)
    provider = CachedWeatherProvider(client, cache_seconds=600.0, clock=clock)

    provider.get_weather(51.5, -0.1)
    clock.advance(100)
    provider.get_weather(51.5, -0.1)

    assert client.calls == 1


def test_get_weather_refreshes_after_ttl_expires() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    client = FakeWeatherClient(clock)
    provider = CachedWeatherProvider(client, cache_seconds=600.0, clock=clock)

    provider.get_weather(51.5, -0.1)
    clock.advance(700)
    provider.get_weather(51.5, -0.1)

    assert client.calls == 2


def test_get_weather_serves_stale_cache_on_refresh_failure() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    client = FakeWeatherClient(clock)
    provider = CachedWeatherProvider(client, cache_seconds=600.0, clock=clock)

    first = provider.get_weather(51.5, -0.1)

    clock.advance(700)
    client.next_result = WeatherUnavailableError("upstream down")
    second = provider.get_weather(51.5, -0.1)

    assert second == first
    assert client.calls == 2


def test_get_weather_raises_when_no_cache_and_fetch_fails() -> None:
    client = FakeWeatherClient()
    client.next_result = WeatherUnavailableError("upstream down")
    provider = CachedWeatherProvider(client)

    with pytest.raises(WeatherUnavailableError):
        provider.get_weather(51.5, -0.1)


def test_get_weather_caches_separately_per_rounded_coordinate() -> None:
    client = FakeWeatherClient()
    provider = CachedWeatherProvider(client, cache_seconds=600.0)

    provider.get_weather(51.5, -0.1)
    provider.get_weather(40.0, 10.0)

    assert client.calls == 2


def test_open_meteo_client_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2026, 7, 28, 12, 5, tzinfo=timezone.utc)

    class FakeDateTime:
        @classmethod
        def now(cls, tz=None):
            return fixed_now

        @classmethod
        def fromisoformat(cls, value: str) -> datetime:
            return datetime.fromisoformat(value)

    def fake_get(url, params=None, timeout=None):
        return httpx.Response(
            200,
            json={
                "current": {
                    "temperature_2m": 18.5,
                    "apparent_temperature": 17.0,
                    "relative_humidity_2m": 60,
                    "wind_speed_10m": 14.2,
                    "weather_code": 3,
                    "precipitation": 0.4,
                    "time": "2026-07-28T12:00",
                },
                "hourly": {
                    "time": ["2026-07-28T11:00", "2026-07-28T12:00", "2026-07-28T13:00"],
                    "precipitation_probability": [10, 35, 20],
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(weather_module, "datetime", FakeDateTime)
    monkeypatch.setattr(weather_module.httpx, "get", fake_get)

    client = OpenMeteoWeatherClient()
    snapshot = client.fetch(51.5, -0.1)

    assert snapshot.temperature_c == pytest.approx(18.5)
    assert snapshot.feels_like_c == pytest.approx(17.0)
    assert snapshot.humidity_percent == pytest.approx(60)
    assert snapshot.wind_speed_kph == pytest.approx(14.2)
    assert snapshot.conditions == "Overcast"
    assert snapshot.precipitation_mm == pytest.approx(0.4)
    assert snapshot.precipitation_probability == pytest.approx(35.0)


def test_open_meteo_client_raises_weather_unavailable_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url, params=None, timeout=None):
        raise httpx.ConnectError("connection refused", request=httpx.Request("GET", url))

    monkeypatch.setattr(weather_module.httpx, "get", fake_get)

    client = OpenMeteoWeatherClient()
    with pytest.raises(WeatherUnavailableError):
        client.fetch(51.5, -0.1)
