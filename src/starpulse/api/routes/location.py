"""Resolved location for weather and the Location Settings page."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from starpulse.api.deps import get_collector, get_db, get_settings, get_weather_provider
from starpulse.api.schemas import (
    LocationActionResponse,
    LocationResponse,
    LocationSettingsResponse,
    LocationTestRequest,
    ManualLocationRequest,
    WeatherResponse,
)
from starpulse.collector.poller import StarlinkPoller
from starpulse.config.settings import Settings
from starpulse.config.writer import update_config_file
from starpulse.logging_config import get_logger
from starpulse.services.geocoding import NullPlaceNameResolver, PlaceNameResolver
from starpulse.services.geoip import GeoIpProvider, NullGeoIpProvider
from starpulse.services.location import (
    PRIVACY_NOTE,
    build_location_status,
    clear_manual_and_stored_location,
    dish_gps_diagnostics,
)
from starpulse.services.weather import CachedWeatherProvider, WeatherUnavailableError

router = APIRouter(prefix="/location", tags=["location"])
logger = get_logger(__name__)


def get_place_resolver(request: Request) -> PlaceNameResolver:
    return getattr(request.app.state, "place_resolver", None) or NullPlaceNameResolver()


def get_geoip_provider(request: Request) -> GeoIpProvider:
    return getattr(request.app.state, "geoip_provider", None) or NullGeoIpProvider()


@router.get("", response_model=LocationResponse)
def get_location(
    settings: Settings = Depends(get_settings),
    collector: StarlinkPoller = Depends(get_collector),
    db: Session = Depends(get_db),
    place_resolver: PlaceNameResolver = Depends(get_place_resolver),
    geoip_provider: GeoIpProvider = Depends(get_geoip_provider),
) -> LocationResponse:
    status = build_location_status(
        settings,
        collector,
        db,
        place_resolver,
        persist=True,
        geoip_provider=geoip_provider,
    )
    return _to_location_response(status)


@router.get("/settings", response_model=LocationSettingsResponse)
def get_location_settings(
    settings: Settings = Depends(get_settings),
    collector: StarlinkPoller = Depends(get_collector),
    db: Session = Depends(get_db),
    place_resolver: PlaceNameResolver = Depends(get_place_resolver),
    geoip_provider: GeoIpProvider = Depends(get_geoip_provider),
    provider: CachedWeatherProvider = Depends(get_weather_provider),
) -> LocationSettingsResponse:
    return _build_settings_response(settings, collector, db, place_resolver, geoip_provider, provider)


@router.post("/manual", response_model=LocationActionResponse)
def save_manual_location(
    payload: ManualLocationRequest,
    settings: Settings = Depends(get_settings),
    collector: StarlinkPoller = Depends(get_collector),
    db: Session = Depends(get_db),
    place_resolver: PlaceNameResolver = Depends(get_place_resolver),
    geoip_provider: GeoIpProvider = Depends(get_geoip_provider),
    provider: CachedWeatherProvider = Depends(get_weather_provider),
) -> LocationActionResponse:
    update_config_file(
        settings.config_file,
        {"weather": {"latitude": payload.latitude, "longitude": payload.longitude}},
    )
    settings.weather.latitude = payload.latitude
    settings.weather.longitude = payload.longitude
    logger.info("Manual weather location saved (lat=%s lon=%s)", payload.latitude, payload.longitude)

    return LocationActionResponse(
        ok=True,
        message="Manual location saved. Weather will use these coordinates.",
        settings=_build_settings_response(settings, collector, db, place_resolver, geoip_provider, provider),
    )


@router.post("/clear", response_model=LocationActionResponse)
def clear_saved_location(
    settings: Settings = Depends(get_settings),
    collector: StarlinkPoller = Depends(get_collector),
    db: Session = Depends(get_db),
    place_resolver: PlaceNameResolver = Depends(get_place_resolver),
    geoip_provider: GeoIpProvider = Depends(get_geoip_provider),
    provider: CachedWeatherProvider = Depends(get_weather_provider),
) -> LocationActionResponse:
    update_config_file(settings.config_file, {"weather": {"latitude": "", "longitude": ""}})
    settings.weather.latitude = None
    settings.weather.longitude = None
    clear_manual_and_stored_location(db)
    logger.info("Cleared manual weather location and stored resolve cache")

    return LocationActionResponse(
        ok=True,
        message="Saved location cleared. Approximate IP or Starlink GPS may be used if available.",
        settings=_build_settings_response(settings, collector, db, place_resolver, geoip_provider, provider),
    )


@router.post("/test", response_model=WeatherResponse)
def test_location_weather(
    payload: LocationTestRequest,
    settings: Settings = Depends(get_settings),
    provider: CachedWeatherProvider = Depends(get_weather_provider),
) -> WeatherResponse:
    if not settings.weather.enabled:
        return WeatherResponse(available=False, message="Weather integration is disabled in config.toml")

    try:
        snapshot = provider.get_weather(payload.latitude, payload.longitude)
    except WeatherUnavailableError:
        return WeatherResponse(
            available=False,
            latitude=payload.latitude,
            longitude=payload.longitude,
            message="Weather service is temporarily unreachable",
        )

    return WeatherResponse(
        available=True,
        temperature_c=snapshot.temperature_c,
        feels_like_c=snapshot.feels_like_c,
        humidity_percent=snapshot.humidity_percent,
        wind_speed_kph=snapshot.wind_speed_kph,
        conditions=snapshot.conditions,
        precipitation_mm=snapshot.precipitation_mm,
        precipitation_probability=snapshot.precipitation_probability,
        latitude=snapshot.latitude,
        longitude=snapshot.longitude,
        location_source="configured",
        fetched_at=snapshot.fetched_at,
    )


def _to_location_response(status) -> LocationResponse:
    return LocationResponse(
        available=status.available,
        latitude=status.latitude,
        longitude=status.longitude,
        altitude_m=status.altitude_m,
        source=status.source,
        source_label=status.source_label,
        place_name=status.place_name,
        accuracy=status.accuracy,
        approximate=status.approximate,
        gps_valid=status.gps_valid,
        gps_enabled=status.gps_enabled,
        gps_satellites=status.gps_satellites,
        coordinates_collected=status.coordinates_collected,
        message=status.message,
    )


def _build_settings_response(
    settings: Settings,
    collector: StarlinkPoller,
    db: Session,
    place_resolver: PlaceNameResolver,
    geoip_provider: GeoIpProvider,
    provider: CachedWeatherProvider,
) -> LocationSettingsResponse:
    status = build_location_status(
        settings,
        collector,
        db,
        place_resolver,
        persist=False,
        geoip_provider=geoip_provider,
    )
    diagnostics = dish_gps_diagnostics(collector, db)

    weather_ok = False
    weather_summary = None
    if status.available and status.latitude is not None and status.longitude is not None and settings.weather.enabled:
        try:
            snapshot = provider.get_weather(status.latitude, status.longitude)
            weather_ok = True
            weather_summary = snapshot.conditions or "Connected"
        except WeatherUnavailableError:
            weather_ok = False
            weather_summary = "Weather unreachable"

    return LocationSettingsResponse(
        active_source=status.source,
        active_source_label=status.source_label,
        active_latitude=status.latitude,
        active_longitude=status.longitude,
        place_name=status.place_name,
        accuracy=status.accuracy,
        approximate=status.approximate,
        weather_ok=weather_ok,
        weather_summary=weather_summary,
        dish_gps_available=bool(diagnostics["dish_coordinates_available"]),
        dish_latitude=diagnostics["dish_latitude"],  # type: ignore[arg-type]
        dish_longitude=diagnostics["dish_longitude"],  # type: ignore[arg-type]
        manual_latitude=settings.weather.latitude,
        manual_longitude=settings.weather.longitude,
        gps_valid=diagnostics["gps_valid"],  # type: ignore[arg-type]
        gps_enabled=diagnostics["gps_enabled"],  # type: ignore[arg-type]
        gps_satellites=diagnostics["gps_satellites"],  # type: ignore[arg-type]
        advanced_note=diagnostics["note"],  # type: ignore[arg-type]
        message=status.message,
        privacy_note=PRIVACY_NOTE,
    )
