"""Resolve and remember the location used for weather lookups.

Priority (first match wins):

1. User-configured ``[weather] latitude`` / ``longitude`` (config/env/setup)
2. Starlink dish GPS (live poller cache, then latest telemetry sample)
3. Last resolved location stored in ``app_meta`` (continuity after restart)
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from starpulse.collector import repository as telemetry_repository
from starpulse.collector.poller import StarlinkPoller
from starpulse.config.settings import Settings
from starpulse.db.models import AppMeta

RESOLVED_LAT_KEY = "weather_resolved_latitude"
RESOLVED_LON_KEY = "weather_resolved_longitude"
RESOLVED_SOURCE_KEY = "weather_resolved_source"


@dataclass(frozen=True)
class ResolvedLocation:
    latitude: float
    longitude: float
    source: str  # "configured" | "dish_gps" | "stored"


def resolve_weather_location(
    settings: Settings,
    collector: StarlinkPoller,
    session: Session,
    *,
    persist: bool = True,
) -> ResolvedLocation | None:
    """Resolve weather coordinates and optionally persist them to ``app_meta``."""
    resolved: ResolvedLocation | None = None

    if settings.weather.latitude is not None and settings.weather.longitude is not None:
        resolved = ResolvedLocation(
            latitude=settings.weather.latitude,
            longitude=settings.weather.longitude,
            source="configured",
        )
    elif collector.dish_location is not None:
        latitude, longitude = collector.dish_location
        resolved = ResolvedLocation(latitude=latitude, longitude=longitude, source="dish_gps")
    else:
        stored_dish = telemetry_repository.get_latest_dish_location(session)
        if stored_dish is not None:
            latitude, longitude = stored_dish
            resolved = ResolvedLocation(latitude=latitude, longitude=longitude, source="dish_gps")
        else:
            stored = _load_stored_location(session)
            if stored is not None:
                resolved = stored

    if resolved is not None and persist:
        _store_resolved_location(session, resolved)
    return resolved


def _load_stored_location(session: Session) -> ResolvedLocation | None:
    lat_row = session.get(AppMeta, RESOLVED_LAT_KEY)
    lon_row = session.get(AppMeta, RESOLVED_LON_KEY)
    if lat_row is None or lon_row is None:
        return None
    try:
        latitude = float(lat_row.value)
        longitude = float(lon_row.value)
    except ValueError:
        return None
    return ResolvedLocation(latitude=latitude, longitude=longitude, source="stored")


def _store_resolved_location(session: Session, resolved: ResolvedLocation) -> None:
    _upsert_meta(session, RESOLVED_LAT_KEY, str(resolved.latitude))
    _upsert_meta(session, RESOLVED_LON_KEY, str(resolved.longitude))
    _upsert_meta(session, RESOLVED_SOURCE_KEY, resolved.source)
    session.commit()


def _upsert_meta(session: Session, key: str, value: str) -> None:
    row = session.get(AppMeta, key)
    if row is None:
        session.add(AppMeta(key=key, value=value))
    else:
        row.value = value
