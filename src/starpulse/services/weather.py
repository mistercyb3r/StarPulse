"""Current weather, from the free Open-Meteo API (no API key required).

Kept independent of the Starlink collector: the dashboard's weather card
is a "nice to have" that shouldn't affect telemetry polling or storage
in any way. ``CachedWeatherProvider`` wraps a ``WeatherClient`` with an
in-memory TTL cache so repeated dashboard polls don't hammer the
upstream API.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

import httpx

from starpulse.logging_config import get_logger

logger = get_logger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 5.0
DEFAULT_CACHE_SECONDS = 600.0

# WMO weather interpretation codes, as used by Open-Meteo.
_WEATHER_CODE_LABELS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def describe_weather_code(code: int | None) -> str:
    if code is None:
        return "Unknown"
    return _WEATHER_CODE_LABELS.get(code, "Unknown")


class WeatherUnavailableError(Exception):
    """Raised when the upstream weather API can't be reached or parsed."""


@dataclass(frozen=True)
class WeatherSnapshot:
    """A single point-in-time weather reading."""

    temperature_c: float | None
    feels_like_c: float | None
    humidity_percent: float | None
    wind_speed_kph: float | None
    conditions: str
    precipitation_mm: float | None
    precipitation_probability: float | None
    latitude: float
    longitude: float
    fetched_at: datetime


class WeatherClient(Protocol):
    """Anything that can fetch current weather for a coordinate."""

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot: ...


def _nearest_hourly_precipitation_probability(data: dict[str, Any], now: datetime) -> float | None:
    """Pick the precip probability from the hourly series closest to ``now``."""
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    probs = hourly.get("precipitation_probability") or []
    if not times or not probs or len(times) != len(probs):
        return None

    best_idx = 0
    best_delta = None
    for idx, raw in enumerate(times):
        try:
            # Open-Meteo returns local ISO timestamps without Z when timezone=auto.
            ts = datetime.fromisoformat(raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=now.tzinfo or timezone.utc)
            delta = abs((ts - now).total_seconds())
        except ValueError:
            continue
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_idx = idx

    value = probs[best_idx]
    return float(value) if value is not None else None


class OpenMeteoWeatherClient:
    """Real ``WeatherClient`` backed by the free Open-Meteo forecast API."""

    def fetch(self, latitude: float, longitude: float) -> WeatherSnapshot:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "wind_speed_10m,weather_code,precipitation"
            ),
            "hourly": "precipitation_probability",
            "forecast_days": 1,
            "timezone": "auto",
        }
        try:
            response = httpx.get(OPEN_METEO_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WeatherUnavailableError(f"Open-Meteo request failed: {exc}") from exc

        now = datetime.now(timezone.utc)
        current = data.get("current") or {}
        return WeatherSnapshot(
            temperature_c=current.get("temperature_2m"),
            feels_like_c=current.get("apparent_temperature"),
            humidity_percent=current.get("relative_humidity_2m"),
            wind_speed_kph=current.get("wind_speed_10m"),
            conditions=describe_weather_code(current.get("weather_code")),
            precipitation_mm=current.get("precipitation"),
            precipitation_probability=_nearest_hourly_precipitation_probability(data, now),
            latitude=latitude,
            longitude=longitude,
            fetched_at=now,
        )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CachedWeatherProvider:
    """Caches ``WeatherClient`` responses per (rounded) coordinate for ``cache_seconds``.

    On a refresh failure, serves the last known (stale) reading for that
    location instead of failing outright, if one exists — a transient
    upstream hiccup shouldn't blank out the dashboard's weather card.
    """

    def __init__(
        self,
        client: WeatherClient,
        cache_seconds: float = DEFAULT_CACHE_SECONDS,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._client = client
        self._cache_seconds = cache_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[tuple[float, float], WeatherSnapshot] = {}

    @property
    def cache_seconds(self) -> float:
        return self._cache_seconds

    def get_weather(self, latitude: float, longitude: float) -> WeatherSnapshot:
        key = (round(latitude, 2), round(longitude, 2))

        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and (self._clock() - cached.fetched_at).total_seconds() < self._cache_seconds:
                return cached

        try:
            snapshot = self._client.fetch(latitude, longitude)
        except WeatherUnavailableError:
            if cached is not None:
                logger.warning("Weather refresh failed, serving last known reading")
                return cached
            raise

        with self._lock:
            self._cache[key] = snapshot
        return snapshot
