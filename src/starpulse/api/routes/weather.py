"""Current weather at the dish's location.

Location resolution priority (first match wins):

1. User-configured ``[weather] latitude`` / ``longitude``
2. Latest Starlink dish GPS coordinates (in-memory from the poller, or
   the most recent telemetry sample that stored them)
3. Unavailable — ``available: false`` with an explanatory message

Never talks to the upstream weather API directly — that's all behind
``CachedWeatherProvider`` — so this route stays fast even if Open-Meteo
is slow or down (a cached/stale reading is served in that case).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from starpulse.api.deps import get_collector, get_db, get_settings, get_weather_provider
from starpulse.api.schemas import WeatherResponse
from starpulse.collector import repository
from starpulse.collector.poller import StarlinkPoller
from starpulse.config.settings import Settings
from starpulse.services.weather import CachedWeatherProvider, WeatherUnavailableError

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("", response_model=WeatherResponse)
def get_weather(
    settings: Settings = Depends(get_settings),
    collector: StarlinkPoller = Depends(get_collector),
    provider: CachedWeatherProvider = Depends(get_weather_provider),
    db: Session = Depends(get_db),
) -> WeatherResponse:
    if not settings.weather.enabled:
        return WeatherResponse(available=False, message="Weather integration is disabled in config.toml")

    latitude, longitude, source = _resolve_location(settings, collector, db)
    if latitude is None or longitude is None:
        return WeatherResponse(available=False, message="location unavailable")

    try:
        snapshot = provider.get_weather(latitude, longitude)
    except WeatherUnavailableError:
        return WeatherResponse(available=False, message="Weather service is temporarily unreachable")

    return WeatherResponse(
        available=True,
        temperature_c=snapshot.temperature_c,
        feels_like_c=snapshot.feels_like_c,
        humidity_percent=snapshot.humidity_percent,
        wind_speed_kph=snapshot.wind_speed_kph,
        conditions=snapshot.conditions,
        latitude=snapshot.latitude,
        longitude=snapshot.longitude,
        location_source=source,
        fetched_at=snapshot.fetched_at,
    )


def _resolve_location(
    settings: Settings,
    collector: StarlinkPoller,
    db: Session,
) -> tuple[float | None, float | None, str | None]:
    # 1. Explicit user config always wins over dish GPS.
    if settings.weather.latitude is not None and settings.weather.longitude is not None:
        return settings.weather.latitude, settings.weather.longitude, "configured"

    # 2. Live in-memory dish GPS from the poller, else last stored telemetry.
    if collector.dish_location is not None:
        latitude, longitude = collector.dish_location
        return latitude, longitude, "dish_gps"

    stored = repository.get_latest_dish_location(db)
    if stored is not None:
        latitude, longitude = stored
        return latitude, longitude, "dish_gps"

    # 3. Nothing available yet.
    return None, None, None
