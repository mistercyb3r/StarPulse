"""Read-only endpoints exposing collected Starlink telemetry.

These routes only ever read from the database via
``starpulse.collector.repository`` — they never talk to the dish
directly. That keeps the collector fully decoupled from the API layer;
the collector would work identically with this router removed entirely.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from starpulse.api.deps import get_db
from starpulse.api.schemas import (
    StarlinkHistoryResponse,
    StarlinkSummaryResponse,
    TelemetrySampleResponse,
)
from starpulse.collector import repository

router = APIRouter(prefix="/starlink", tags=["starlink"])

DEFAULT_HISTORY_LIMIT = 100
MAX_HISTORY_LIMIT = 1000


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
    db: Session = Depends(get_db),
) -> StarlinkSummaryResponse:
    """Return average download/upload/latency, uptime %, and average obstruction %."""
    stats = repository.get_summary(db, start=start, end=end)
    return StarlinkSummaryResponse(
        sample_count=stats.sample_count,
        average_download_bps=stats.average_download_bps,
        average_upload_bps=stats.average_upload_bps,
        average_latency_ms=stats.average_latency_ms,
        uptime_percent=stats.uptime_percent,
        average_obstruction_percent=stats.average_obstruction_percent,
        range_start=start,
        range_end=end,
    )
