"""Persistence helpers for Starlink telemetry samples.

Kept separate from the client/poller so storage concerns (how a sample
is written and queried) don't leak into the polling loop or the gRPC
client. The API layer (``starpulse.api.routes.starlink``) reads through
these same helpers rather than querying ``TelemetrySample`` directly, so
storage/query logic isn't duplicated between the collector and the API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from starpulse.collector.client import StarlinkSample
from starpulse.db.models import TelemetrySample

CONNECTED_STATE = "CONNECTED"


def save_sample(session: Session, sample: StarlinkSample) -> TelemetrySample:
    """Persist a ``StarlinkSample`` as a new ``TelemetrySample`` row."""
    row = TelemetrySample(
        timestamp=sample.timestamp,
        connection_state=sample.connection_state,
        uptime_seconds=sample.uptime_seconds,
        download_bps=sample.download_bps,
        upload_bps=sample.upload_bps,
        latency_ms=sample.latency_ms,
        ping_drop_rate=sample.ping_drop_rate,
        obstruction_percent=sample.obstruction_percent,
        currently_obstructed=sample.currently_obstructed,
        snr=sample.snr,
        power_watts=sample.power_watts,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_latest_sample(session: Session) -> TelemetrySample | None:
    """Return the most recently recorded sample, if any."""
    stmt = select(TelemetrySample).order_by(TelemetrySample.timestamp.desc()).limit(1)
    return session.execute(stmt).scalar_one_or_none()


def get_recent_samples(
    session: Session,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 100,
) -> list[TelemetrySample]:
    """Return up to ``limit`` samples in ``[start, end]``, oldest first.

    ``start``/``end`` are inclusive and optional; omitting both returns
    the most recent ``limit`` samples overall.
    """
    stmt = select(TelemetrySample)
    stmt = _apply_range(stmt, start, end)
    stmt = stmt.order_by(TelemetrySample.timestamp.desc()).limit(limit)
    rows = list(session.execute(stmt).scalars().all())
    return list(reversed(rows))


def count_samples(session: Session) -> int:
    return session.execute(select(func.count()).select_from(TelemetrySample)).scalar_one()


@dataclass(frozen=True)
class SummaryStats:
    """Aggregate telemetry stats over a (possibly unbounded) time range."""

    sample_count: int
    average_download_bps: float | None
    average_upload_bps: float | None
    average_latency_ms: float | None
    average_obstruction_percent: float | None
    uptime_percent: float | None


def get_summary(
    session: Session,
    start: datetime | None = None,
    end: datetime | None = None,
) -> SummaryStats:
    """Compute averages and uptime percentage over samples in ``[start, end]``."""
    connected_flag = case((TelemetrySample.connection_state == CONNECTED_STATE, 1), else_=0)

    stmt = select(
        func.count(TelemetrySample.id),
        func.avg(TelemetrySample.download_bps),
        func.avg(TelemetrySample.upload_bps),
        func.avg(TelemetrySample.latency_ms),
        func.avg(TelemetrySample.obstruction_percent),
        func.sum(connected_flag),
    )
    stmt = _apply_range(stmt, start, end)

    sample_count, avg_download, avg_upload, avg_latency, avg_obstruction, connected_count = session.execute(
        stmt
    ).one()

    uptime_percent = None
    if sample_count:
        uptime_percent = (connected_count or 0) / sample_count * 100

    return SummaryStats(
        sample_count=sample_count,
        average_download_bps=avg_download,
        average_upload_bps=avg_upload,
        average_latency_ms=avg_latency,
        average_obstruction_percent=avg_obstruction,
        uptime_percent=uptime_percent,
    )


def _apply_range(stmt, start: datetime | None, end: datetime | None):
    if start is not None:
        stmt = stmt.where(TelemetrySample.timestamp >= _ensure_utc(start))
    if end is not None:
        stmt = stmt.where(TelemetrySample.timestamp <= _ensure_utc(end))
    return stmt


def _ensure_utc(value: datetime) -> datetime:
    """Treat naive datetimes (e.g. from query params without a UTC offset) as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
