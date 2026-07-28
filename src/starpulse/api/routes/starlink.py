"""Read-only endpoints exposing collected Starlink telemetry.

These routes only ever read from the database via
``starpulse.collector.repository`` — they never talk to the dish
directly. That keeps the collector fully decoupled from the API layer;
the collector would work identically with this router removed entirely.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from starpulse.api.deps import get_db
from starpulse.api.schemas import (
    DishInfoResponse,
    StarlinkHealthResponse,
    StarlinkHistoryResponse,
    StarlinkSummaryResponse,
    SummaryPeriod,
    TelemetrySampleResponse,
)
from starpulse.collector import repository

router = APIRouter(prefix="/starlink", tags=["starlink"])

DEFAULT_HISTORY_LIMIT = 100
MAX_HISTORY_LIMIT = 1000

_PERIOD_TO_TIMEDELTA = {
    SummaryPeriod.LAST_24H: timedelta(hours=24),
    SummaryPeriod.LAST_7D: timedelta(days=7),
    SummaryPeriod.LAST_30D: timedelta(days=30),
}


@router.get("/status", response_model=TelemetrySampleResponse)
def get_status(db: Session = Depends(get_db)) -> TelemetrySampleResponse:
    """Return the most recently collected telemetry sample."""
    sample = repository.get_latest_sample(db)
    if sample is None:
        raise HTTPException(status_code=404, detail="No telemetry samples recorded yet")
    return TelemetrySampleResponse.model_validate(sample)


@router.get("/history", response_model=StarlinkHistoryResponse)
def get_history(
    start: datetime | None = Query(None, description="Only include samples at/after this time (ISO 8601)"),
    end: datetime | None = Query(None, description="Only include samples at/before this time (ISO 8601)"),
    limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT, description="Maximum samples to return"),
    db: Session = Depends(get_db),
) -> StarlinkHistoryResponse:
    """Return historical telemetry samples, oldest first."""
    samples = repository.get_recent_samples(db, start=start, end=end, limit=limit)
    return StarlinkHistoryResponse(
        samples=[TelemetrySampleResponse.model_validate(sample) for sample in samples],
        count=len(samples),
    )


@router.get("/summary", response_model=StarlinkSummaryResponse)
def get_summary(
    start: datetime | None = Query(None, description="Only include samples at/after this time (ISO 8601)"),
    end: datetime | None = Query(None, description="Only include samples at/before this time (ISO 8601)"),
    period: SummaryPeriod | None = Query(
        None, description="Shorthand for start: one of 24h, 7d, 30d. Overrides start/end when given."
    ),
    db: Session = Depends(get_db),
) -> StarlinkSummaryResponse:
    """Return average/peak download/upload, latency, uptime %, and average obstruction %."""
    if period is not None:
        end = None
        start = datetime.now(timezone.utc) - _PERIOD_TO_TIMEDELTA[period]

    stats = repository.get_summary(db, start=start, end=end)
    return StarlinkSummaryResponse(
        sample_count=stats.sample_count,
        average_download_bps=stats.average_download_bps,
        average_upload_bps=stats.average_upload_bps,
        average_latency_ms=stats.average_latency_ms,
        uptime_percent=stats.uptime_percent,
        average_obstruction_percent=stats.average_obstruction_percent,
        peak_download_bps=stats.peak_download_bps,
        peak_upload_bps=stats.peak_upload_bps,
        range_start=start,
        range_end=end,
    )


@router.get("/health", response_model=StarlinkHealthResponse)
def get_health_score(
    start: datetime | None = Query(None, description="Only include samples at/after this time (ISO 8601)"),
    end: datetime | None = Query(None, description="Only include samples at/before this time (ISO 8601)"),
    db: Session = Depends(get_db),
) -> StarlinkHealthResponse:
    """Return a 0-100 health score derived from recent uptime, latency, and obstruction.

    Defaults to the last hour when no range is given, so it reflects
    current conditions rather than being diluted by all-time history.
    """
    health = repository.get_health_score(db, start=start, end=end)
    return StarlinkHealthResponse(
        health_score=health.score,
        quality_label=health.quality_label,
        uptime_percent=health.uptime_percent,
        latency_ms=health.latency_ms,
        obstruction_percent=health.obstruction_percent,
        obstruction_impact=health.obstruction_impact,
        sample_count=health.sample_count,
        range_start=health.range_start,
        range_end=health.range_end,
    )


@router.get("/dish-info", response_model=DishInfoResponse)
def get_dish_info(db: Session = Depends(get_db)) -> DishInfoResponse:
    """Return dish identification, pointing, and GPS info from the latest sample."""
    sample = repository.get_latest_sample(db)
    if sample is None:
        raise HTTPException(status_code=404, detail="No telemetry samples recorded yet")
    return DishInfoResponse.model_validate(sample)
