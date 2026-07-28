"""Current weather at the dish's location.

Location resolution: prefer the dish's own GPS position (cached on the
``StarlinkPoller`` once it's available), and fall back to the
``[weather] latitude``/``longitude`` config values otherwise. Never
talks to the upstream weather API directly — that's all behind
``CachedWeatherProvider`` — so this route stays fast even if Open-Meteo
is slow or down (a cached/stale reading is served in that case).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from starpulse.api.deps import get_collector, get_settings, get_weather_provider
from starpulse.api.schemas import WeatherResponse
from starpulse.collector.poller import StarlinkPoller
from starpulse.config.settings import Settings
from starpulse.services.weather import CachedWeatherProvider, WeatherUnavailableError

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("", response_model=WeatherResponse)
def get_weather(
    settings: Settings = Depends(get_settings),
    collector: StarlinkPoller = Depends(get_collector),
    provider: CachedWeatherProvider = Depends(get_weather_provider),
) -> WeatherResponse:
    if not settings.weather.enabled:
        return WeatherResponse(available=False, message="Weather integration is disabled in config.toml")

    latitude, longitude, source = _resolve_location(settings, collector)
    if latitude is None or longitude is None:
        return WeatherResponse(
            available=False,
            message=(
                "No location available yet — waiting on the dish's GPS, "
                "or set weather.latitude/longitude in config.toml"
            ),
        )

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
    settings: Settings, collector: StarlinkPoller
) -> tuple[float | None, float | None, str | None]:
    if collector.dish_location is not None:
        latitude, longitude = collector.dish_location
        return latitude, longitude, "dish_gps"
    if settings.weather.latitude is not None and settings.weather.longitude is not None:
        return settings.weather.latitude, settings.weather.longitude, "configured"
    return None, None, None
