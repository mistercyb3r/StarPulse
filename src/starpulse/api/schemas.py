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


class SetupRequest(BaseModel):
    """Submitted by the setup wizard (or re-submitted later to change settings)."""

    dish_host: str = Field(min_length=1, max_length=255)
    poll_interval_seconds: float = Field(gt=0, le=3600)
    port: int = Field(ge=1, le=65535)


class SetupResponse(BaseModel):
    setup_complete: bool
    restart_required: bool
    message: str
