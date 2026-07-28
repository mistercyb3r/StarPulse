"""Pydantic response models for the API layer.

Kept separate from the ORM models in ``starpulse.db.models`` so the
public API shape can evolve independently of the database schema.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TelemetrySampleResponse(BaseModel):
    """One telemetry sample, as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    connection_state: str
    uptime_seconds: int | None
    download_bps: float | None
    upload_bps: float | None
    latency_ms: float | None
    ping_drop_rate: float | None
    obstruction_percent: float | None
    currently_obstructed: bool | None
    snr: float | None
    power_watts: float | None
    hardware_version: str | None
    software_version: str | None
    gps_valid: bool | None
    gps_enabled: bool | None
    gps_satellites: int | None
    latitude: float | None
    longitude: float | None
    altitude_m: float | None = None
    azimuth_deg: float | None
    elevation_deg: float | None


class StarlinkHistoryResponse(BaseModel):
    """A time-ordered (oldest first) window of telemetry samples."""

    samples: list[TelemetrySampleResponse]
    count: int


class SummaryPeriod(str, Enum):
    """Convenience shorthand for the ``period`` query param on ``/summary``."""

    LAST_24H = "24h"
    LAST_7D = "7d"
    LAST_30D = "30d"


class StarlinkSummaryResponse(BaseModel):
    """Aggregate telemetry stats over a (possibly unbounded) time range.

    Fields are ``None`` when there are no samples in range to average.
    """

    sample_count: int
    average_download_bps: float | None
    average_upload_bps: float | None
    average_latency_ms: float | None
    uptime_percent: float | None
    average_obstruction_percent: float | None
    peak_download_bps: float | None
    peak_upload_bps: float | None
    best_latency_ms: float | None
    worst_latency_ms: float | None
    average_power_watts: float | None
    min_power_watts: float | None
    max_power_watts: float | None
    range_start: datetime | None
    range_end: datetime | None


class StarlinkHealthResponse(BaseModel):
    """A single 0-100 "how good is my Starlink right now" score, plus its inputs.

    Defaults to summarizing the last hour when no explicit range is given.
    ``score``/``obstruction_impact``/``quality_label`` are ``"Unknown"``-ish
    placeholders when there are no samples in range yet.
    """

    health_score: float | None
    quality_label: str
    uptime_percent: float | None
    latency_ms: float | None
    obstruction_percent: float | None
    obstruction_impact: str
    sample_count: int
    range_start: datetime | None
    range_end: datetime | None


class DishInfoResponse(BaseModel):
    """Dish identification and pointing/GPS info, from the most recent sample."""

    model_config = ConfigDict(from_attributes=True)

    connection_state: str
    uptime_seconds: int | None
    hardware_version: str | None
    software_version: str | None
    gps_valid: bool | None
    gps_enabled: bool | None
    gps_satellites: int | None
    azimuth_deg: float | None
    elevation_deg: float | None
    last_updated: datetime = Field(validation_alias="timestamp")


class ConnectionEventResponse(BaseModel):
    """A single period of degraded connectivity."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    start_time: datetime
    end_time: datetime | None
    duration_seconds: float | None
    # One of: "disconnected", "high_packet_loss", "dish_unavailable".
    reason: str


class OutageSummaryResponse(BaseModel):
    """Outage counts and downtime for the "Connection History" dashboard section."""

    outages_today: int
    outages_last_7d: int
    total_downtime_minutes_last_7d: float
    events: list[ConnectionEventResponse]


class LocationResponse(BaseModel):
    """Resolved dish/weather location for the dashboard Location card.

    Never invents coordinates. ``place_name`` is optional reverse-geocode
    labeling only; when reverse geocoding fails, coordinates still return.
    """

    available: bool
    latitude: float | None = None
    longitude: float | None = None
    altitude_m: float | None = None
    # One of: "dish_gps", "configured", "stored", or None when unavailable.
    source: str | None = None
    source_label: str | None = None
    place_name: str | None = None
    gps_valid: bool | None = None
    gps_enabled: bool | None = None
    gps_satellites: int | None = None
    coordinates_collected: bool = False
    message: str | None = None


class LocationSettingsResponse(BaseModel):
    """Payload for the Location Settings page."""

    active_source: str | None = None
    active_source_label: str | None = None
    active_latitude: float | None = None
    active_longitude: float | None = None
    place_name: str | None = None
    dish_gps_available: bool = False
    dish_latitude: float | None = None
    dish_longitude: float | None = None
    manual_latitude: float | None = None
    manual_longitude: float | None = None
    gps_valid: bool | None = None
    gps_enabled: bool | None = None
    message: str | None = None
    privacy_note: str


class ManualLocationRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LocationTestRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LocationActionResponse(BaseModel):
    ok: bool
    message: str
    settings: LocationSettingsResponse


class WeatherResponse(BaseModel):
    """Current weather at the dish's location (dish GPS, or a configured fallback).

    ``available`` is ``False`` (with all data fields ``None``) when weather
    is disabled, no location is known yet, or the upstream API is
    unreachable — ``message`` explains why in that case.
    """

    available: bool
    temperature_c: float | None = None
    feels_like_c: float | None = None
    humidity_percent: float | None = None
    wind_speed_kph: float | None = None
    conditions: str | None = None
    precipitation_mm: float | None = None
    precipitation_probability: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    # One of: "dish_gps", "configured", "stored", or None when unavailable.
    location_source: str | None = None
    fetched_at: datetime | None = None
    message: str | None = None


class WeatherImpactResponse(BaseModel):
    """Weather Impact score correlated with recent Starlink performance."""

    available: bool
    severity: str
    reasons: list[str] = Field(default_factory=list)
    conditions: str | None = None
    temperature_c: float | None = None
    wind_speed_kph: float | None = None
    precipitation_probability: float | None = None
    precipitation_mm: float | None = None
    latency_ms: float | None = None
    download_bps: float | None = None
    upload_bps: float | None = None
    latency_delta_percent: float | None = None
    download_delta_percent: float | None = None
    active_outage: bool = False
    sample_count: int = 0
    message: str | None = None


class WeatherHistoryPoint(BaseModel):
    timestamp: datetime
    temperature_c: float | None = None
    wind_speed_kph: float | None = None
    precipitation_mm: float | None = None
    precipitation_probability: float | None = None
    conditions: str | None = None


class PerformanceBucket(BaseModel):
    timestamp: datetime
    average_download_bps: float | None = None
    average_upload_bps: float | None = None
    average_latency_ms: float | None = None
    sample_count: int = 0


class WeatherHistoryResponse(BaseModel):
    period: str
    range_start: datetime
    range_end: datetime
    weather: list[WeatherHistoryPoint]
    performance: list[PerformanceBucket]
    outages: list[ConnectionEventResponse]


class SetupStatusResponse(BaseModel):
    """Whether first-run setup has been completed, plus the current values.

    The frontend uses ``setup_complete`` to decide whether to show the
    setup wizard or the dashboard, and pre-fills the wizard's form (or
    shows a "current settings" summary) from the other fields.
    """

    setup_complete: bool
    dish_host: str
    dish_port: int
    poll_interval_seconds: float
    port: int
    weather_latitude: float | None = None
    weather_longitude: float | None = None


class SetupRequest(BaseModel):
    """Submitted by the setup wizard (or re-submitted later to change settings)."""

    dish_host: str = Field(min_length=1, max_length=255)
    poll_interval_seconds: float = Field(gt=0, le=3600)
    port: int = Field(ge=1, le=65535)
    # Optional fixed weather location. Blank/None leaves dish GPS as the source.
    weather_latitude: float | None = Field(default=None, ge=-90, le=90)
    weather_longitude: float | None = Field(default=None, ge=-180, le=180)


class SetupResponse(BaseModel):
    setup_complete: bool
    restart_required: bool
    message: str