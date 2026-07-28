"""Current weather, weather impact, and weather vs performance history.

Location resolution (dish GPS → configured → last stored) lives in
``starpulse.services.location``. Weather Impact correlates Open-Meteo
readings with Starlink telemetry and outage events.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from starpulse.api.deps import get_collector, get_db, get_settings, get_weather_provider
from starpulse.api.schemas import (
    ConnectionEventResponse,
    PerformanceBucket,
    WeatherHistoryPoint,
    WeatherHistoryResponse,
    WeatherImpactResponse,
    WeatherResponse,
)
from starpulse.collector import repository as telemetry_repository
from starpulse.collector.poller import StarlinkPoller
from starpulse.config.settings import Settings
from starpulse.services.location import location_unavailable_message, resolve_weather_location
from starpulse.services.weather import CachedWeatherProvider, WeatherUnavailableError
from starpulse.services.weather_impact import compute_weather_impact
from starpulse.services.weather_repository import get_weather_history

router = APIRouter(prefix="/weather", tags=["weather"])


class WeatherHistoryPeriod(str, Enum):
    LAST_24H = "24h"
    LAST_7D = "7d"
    LAST_30D = "30d"


_PERIOD_TO_TIMEDELTA = {
    WeatherHistoryPeriod.LAST_24H: timedelta(hours=24),
    WeatherHistoryPeriod.LAST_7D: timedelta(days=7),
    WeatherHistoryPeriod.LAST_30D: timedelta(days=30),
}

_BUCKET_SIZES = {
    WeatherHistoryPeriod.LAST_24H: timedelta(minutes=30),
    WeatherHistoryPeriod.LAST_7D: timedelta(hours=3),
    WeatherHistoryPeriod.LAST_30D: timedelta(hours=12),
}


@router.get("", response_model=WeatherResponse)
def get_weather(
    settings: Settings = Depends(get_settings),
    collector: StarlinkPoller = Depends(get_collector),
    provider: CachedWeatherProvider = Depends(get_weather_provider),
    db: Session = Depends(get_db),
) -> WeatherResponse:
    if not settings.weather.enabled:
        return WeatherResponse(available=False, message="Weather integration is disabled in config.toml")

    resolved = resolve_weather_location(settings, collector, db, persist=True)
    if resolved is None:
        return WeatherResponse(
            available=False,
            message=location_unavailable_message(settings, collector, db),
        )

    try:
        snapshot = provider.get_weather(resolved.latitude, resolved.longitude)
    except WeatherUnavailableError:
        return WeatherResponse(available=False, message="Weather service is temporarily unreachable")

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
        location_source=resolved.source,
        fetched_at=snapshot.fetched_at,
    )


@router.get("/impact", response_model=WeatherImpactResponse)
def get_weather_impact(
    settings: Settings = Depends(get_settings),
    collector: StarlinkPoller = Depends(get_collector),
    provider: CachedWeatherProvider = Depends(get_weather_provider),
    db: Session = Depends(get_db),
) -> WeatherImpactResponse:
    if not settings.weather.enabled:
        return WeatherImpactResponse(
            available=False,
            severity="Unknown",
            message="Weather integration is disabled in config.toml",
        )

    snapshot = None
    resolved = resolve_weather_location(settings, collector, db, persist=True)
    if resolved is not None:
        try:
            snapshot = provider.get_weather(resolved.latitude, resolved.longitude)
        except WeatherUnavailableError:
            snapshot = None

    impact = compute_weather_impact(db, snapshot)
    if impact.severity == "Unknown" and snapshot is None and resolved is None:
        return WeatherImpactResponse(
            available=False,
            severity="Unknown",
            reasons=impact.reasons,
            message=location_unavailable_message(settings, collector, db),
        )

    return WeatherImpactResponse(
        available=True,
        severity=impact.severity,
        reasons=impact.reasons,
        conditions=impact.conditions,
        temperature_c=impact.temperature_c,
        wind_speed_kph=impact.wind_speed_kph,
        precipitation_probability=impact.precipitation_probability,
        precipitation_mm=impact.precipitation_mm,
        latency_ms=impact.latency_ms,
        download_bps=impact.download_bps,
        upload_bps=impact.upload_bps,
        latency_delta_percent=impact.latency_delta_percent,
        download_delta_percent=impact.download_delta_percent,
        active_outage=impact.active_outage,
        sample_count=impact.sample_count,
    )


@router.get("/history", response_model=WeatherHistoryResponse)
def get_weather_history_endpoint(
    period: WeatherHistoryPeriod = Query(WeatherHistoryPeriod.LAST_24H),
    db: Session = Depends(get_db),
) -> WeatherHistoryResponse:
    now = datetime.now(timezone.utc)
    start = now - _PERIOD_TO_TIMEDELTA[period]
    bucket_size = _BUCKET_SIZES[period]

    weather_rows = get_weather_history(db, start=start, end=now, limit=5000)
    weather_points = [
        WeatherHistoryPoint(
            timestamp=row.timestamp,
            temperature_c=row.temperature_c,
            wind_speed_kph=row.wind_speed_kph,
            precipitation_mm=row.precipitation_mm,
            precipitation_probability=row.precipitation_probability,
            conditions=row.conditions,
        )
        for row in weather_rows
    ]

    samples = telemetry_repository.get_recent_samples(db, start=start, end=now, limit=50_000)
    performance = _bucket_performance(samples, start=start, end=now, bucket_size=bucket_size)

    outage_events = telemetry_repository.get_connection_events(db, start=start, end=now, limit=1000)
    outages = [ConnectionEventResponse.model_validate(event) for event in outage_events]

    return WeatherHistoryResponse(
        period=period.value,
        range_start=start,
        range_end=now,
        weather=weather_points,
        performance=performance,
        outages=outages,
    )


def _bucket_performance(samples, *, start: datetime, end: datetime, bucket_size: timedelta) -> list[PerformanceBucket]:
    if end <= start:
        return []

    buckets: list[PerformanceBucket] = []
    cursor = start
    while cursor < end:
        bucket_end = min(cursor + bucket_size, end)
        in_bucket = [
            sample
            for sample in samples
            if _ensure_utc(sample.timestamp) >= cursor and _ensure_utc(sample.timestamp) < bucket_end
        ]
        downloads = [s.download_bps for s in in_bucket if s.download_bps is not None]
        uploads = [s.upload_bps for s in in_bucket if s.upload_bps is not None]
        latencies = [s.latency_ms for s in in_bucket if s.latency_ms is not None]
        buckets.append(
            PerformanceBucket(
                timestamp=cursor,
                average_download_bps=(sum(downloads) / len(downloads)) if downloads else None,
                average_upload_bps=(sum(uploads) / len(uploads)) if uploads else None,
                average_latency_ms=(sum(latencies) / len(latencies)) if latencies else None,
                sample_count=len(in_bucket),
            )
        )
        cursor = bucket_end
    return buckets


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
