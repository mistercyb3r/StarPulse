"""Resolve weather/location coordinates for StarPulse.

Priority (first match wins):

1. Manual coordinates from ``[weather] latitude`` / ``longitude`` (settings/setup)
2. Approximate GeoIP location (city-level; clearly labeled)
3. Starlink dish GPS when location sharing returns real coordinates (advanced)
4. Last resolved ``app_meta`` cache (continuity after restart)

Browser geolocation is client-side only: the UI populates the form and saves
via manual coordinates (priority 1).

Dish GPS *lock* is never shown as a normal-user location failure — that
detail belongs in Location Settings → Advanced diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from starpulse.collector import repository as telemetry_repository
from starpulse.collector.poller import StarlinkPoller
from starpulse.config.settings import Settings
from starpulse.db.models import AppMeta
from starpulse.services.geocoding import PlaceNameResolver
from starpulse.services.geoip import GeoIpProvider, NullGeoIpProvider

RESOLVED_LAT_KEY = "weather_resolved_latitude"
RESOLVED_LON_KEY = "weather_resolved_longitude"
RESOLVED_SOURCE_KEY = "weather_resolved_source"
RESOLVED_ALT_KEY = "weather_resolved_altitude_m"

SOURCE_LABELS = {
    "configured": "Manual configuration",
    "geoip": "Approximate IP location",
    "dish_gps": "Starlink GPS",
    "stored": "Last known",
}

PRIVACY_NOTE = (
    "StarPulse does not require location sharing. "
    "Coordinates can be entered manually and remain local."
)

LOCATION_REQUIRED_MESSAGE = "Location required"


@dataclass(frozen=True)
class ResolvedLocation:
    latitude: float
    longitude: float
    source: str  # "configured" | "geoip" | "dish_gps" | "stored"
    altitude_m: float | None = None
    place_name: str | None = None
    accuracy: str | None = None


@dataclass(frozen=True)
class LocationStatus:
    """Dashboard-facing location snapshot (never invents coordinates)."""

    available: bool
    latitude: float | None
    longitude: float | None
    altitude_m: float | None
    source: str | None
    source_label: str | None
    place_name: str | None
    accuracy: str | None
    approximate: bool
    gps_valid: bool | None
    gps_enabled: bool | None
    gps_satellites: int | None
    dish_coordinates_available: bool
    coordinates_collected: bool
    message: str | None


def resolve_weather_location(
    settings: Settings,
    collector: StarlinkPoller,
    session: Session,
    *,
    persist: bool = True,
    geoip_provider: GeoIpProvider | None = None,
) -> ResolvedLocation | None:
    """Resolve weather coordinates and optionally persist them to ``app_meta``."""
    resolved = _resolve_configured(settings)
    if resolved is None:
        resolved = _resolve_geoip(geoip_provider)
    if resolved is None:
        resolved = _resolve_dish_gps(collector, session)
    if resolved is None:
        resolved = _load_stored_location(session)

    if resolved is not None and persist:
        _store_resolved_location(session, resolved)
    return resolved


def build_location_status(
    settings: Settings,
    collector: StarlinkPoller,
    session: Session,
    place_resolver: PlaceNameResolver | None = None,
    *,
    persist: bool = True,
    geoip_provider: GeoIpProvider | None = None,
) -> LocationStatus:
    """Build a full location status for the dashboard Location card / API."""
    latest = telemetry_repository.get_latest_sample(session)
    gps_valid = latest.gps_valid if latest is not None else None
    gps_enabled = latest.gps_enabled if latest is not None else None
    gps_satellites = latest.gps_satellites if latest is not None else None
    dish = _resolve_dish_gps(collector, session)

    resolved = resolve_weather_location(
        settings,
        collector,
        session,
        persist=persist,
        geoip_provider=geoip_provider,
    )
    if resolved is None:
        return LocationStatus(
            available=False,
            latitude=None,
            longitude=None,
            altitude_m=None,
            source=None,
            source_label=None,
            place_name=None,
            accuracy=None,
            approximate=False,
            gps_valid=gps_valid,
            gps_enabled=gps_enabled,
            gps_satellites=gps_satellites,
            dish_coordinates_available=False,
            coordinates_collected=False,
            message=LOCATION_REQUIRED_MESSAGE,
        )

    place_name = resolved.place_name
    if place_name is None and place_resolver is not None:
        place_name = place_resolver.resolve(resolved.latitude, resolved.longitude)

    return LocationStatus(
        available=True,
        latitude=resolved.latitude,
        longitude=resolved.longitude,
        altitude_m=resolved.altitude_m,
        source=resolved.source,
        source_label=SOURCE_LABELS.get(resolved.source, resolved.source),
        place_name=place_name,
        accuracy=resolved.accuracy,
        approximate=resolved.source == "geoip",
        gps_valid=gps_valid,
        gps_enabled=gps_enabled,
        gps_satellites=gps_satellites,
        dish_coordinates_available=dish is not None,
        coordinates_collected=True,
        message=None,
    )


def location_unavailable_message(
    settings: Settings,
    collector: StarlinkPoller,
    session: Session,
) -> str:
    """User-facing reason weather has no location (no dish GPS jargon)."""
    return LOCATION_REQUIRED_MESSAGE


def clear_manual_and_stored_location(session: Session) -> None:
    """Remove last-resolved coordinates from ``app_meta`` (config cleared separately)."""
    for key in (RESOLVED_LAT_KEY, RESOLVED_LON_KEY, RESOLVED_SOURCE_KEY, RESOLVED_ALT_KEY):
        row = session.get(AppMeta, key)
        if row is not None:
            session.delete(row)
    session.commit()


def peek_dish_gps(collector: StarlinkPoller, session: Session) -> ResolvedLocation | None:
    """Return dish GPS coordinates if available, without writing app_meta."""
    return _resolve_dish_gps(collector, session)


def dish_gps_diagnostics(
    collector: StarlinkPoller,
    session: Session,
) -> dict[str, object]:
    """Advanced diagnostics for Location Settings (not shown on the dashboard)."""
    latest = telemetry_repository.get_latest_sample(session)
    gps_valid = latest.gps_valid if latest is not None else None
    gps_enabled = latest.gps_enabled if latest is not None else None
    dish = _resolve_dish_gps(collector, session)
    note = None
    if gps_valid is True and dish is None:
        note = "Starlink GPS locked but coordinates unavailable"
    return {
        "gps_valid": gps_valid,
        "gps_enabled": gps_enabled,
        "gps_satellites": latest.gps_satellites if latest is not None else None,
        "dish_coordinates_available": dish is not None,
        "dish_latitude": dish.latitude if dish is not None else None,
        "dish_longitude": dish.longitude if dish is not None else None,
        "note": note,
    }


def _resolve_configured(settings: Settings) -> ResolvedLocation | None:
    if settings.weather.latitude is None or settings.weather.longitude is None:
        return None
    return ResolvedLocation(
        latitude=settings.weather.latitude,
        longitude=settings.weather.longitude,
        source="configured",
    )


def _resolve_geoip(geoip_provider: GeoIpProvider | None) -> ResolvedLocation | None:
    provider = geoip_provider or NullGeoIpProvider()
    result = provider.resolve()
    if result is None:
        return None
    return ResolvedLocation(
        latitude=result.latitude,
        longitude=result.longitude,
        source="geoip",
        place_name=result.place_name,
        accuracy=result.accuracy,
    )


def _resolve_dish_gps(collector: StarlinkPoller, session: Session) -> ResolvedLocation | None:
    if collector.dish_location is not None:
        coords = collector.dish_location
        return ResolvedLocation(
            latitude=coords.latitude,
            longitude=coords.longitude,
            altitude_m=coords.altitude_m,
            source="dish_gps",
        )
    stored_dish = telemetry_repository.get_latest_dish_location(session)
    if stored_dish is not None:
        return ResolvedLocation(
            latitude=stored_dish.latitude,
            longitude=stored_dish.longitude,
            altitude_m=stored_dish.altitude_m,
            source="dish_gps",
        )
    return None


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
    altitude_m = None
    alt_row = session.get(AppMeta, RESOLVED_ALT_KEY)
    if alt_row is not None and alt_row.value:
        try:
            altitude_m = float(alt_row.value)
        except ValueError:
            altitude_m = None
    source_row = session.get(AppMeta, RESOLVED_SOURCE_KEY)
    source = source_row.value if source_row is not None else "stored"
    # Preserve original source label when possible; fall back to "stored".
    if source not in SOURCE_LABELS:
        source = "stored"
    return ResolvedLocation(
        latitude=latitude,
        longitude=longitude,
        altitude_m=altitude_m,
        source=source if source != "stored" else "stored",
    )


def _store_resolved_location(session: Session, resolved: ResolvedLocation) -> None:
    _upsert_meta(session, RESOLVED_LAT_KEY, str(resolved.latitude))
    _upsert_meta(session, RESOLVED_LON_KEY, str(resolved.longitude))
    _upsert_meta(session, RESOLVED_SOURCE_KEY, resolved.source)
    if resolved.altitude_m is not None:
        _upsert_meta(session, RESOLVED_ALT_KEY, str(resolved.altitude_m))
    session.commit()


def _upsert_meta(session: Session, key: str, value: str) -> None:
    row = session.get(AppMeta, key)
    if row is None:
        session.add(AppMeta(key=key, value=value))
    else:
        row.value = value
