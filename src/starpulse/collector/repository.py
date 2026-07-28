"""Persistence helpers for Starlink telemetry samples.

Kept separate from the client/poller so storage concerns (how a sample
is written and queried) don't leak into the polling loop or the gRPC
client. The API layer (``starpulse.api.routes.starlink``) reads through
these same helpers rather than querying ``TelemetrySample`` directly, so
storage/query logic isn't duplicated between the collector and the API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from starpulse.collector.client import StarlinkSample
from starpulse.db.models import ConnectionEvent, TelemetrySample

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
        hardware_version=sample.hardware_version,
        software_version=sample.software_version,
        gps_valid=sample.gps_valid,
        gps_enabled=sample.gps_enabled,
        gps_satellites=sample.gps_satellites,
        latitude=sample.latitude,
        longitude=sample.longitude,
        azimuth_deg=sample.azimuth_deg,
        elevation_deg=sample.elevation_deg,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_latest_sample(session: Session) -> TelemetrySample | None:
    """Return the most recently recorded sample, if any."""
    stmt = select(TelemetrySample).order_by(TelemetrySample.timestamp.desc()).limit(1)
    return session.execute(stmt).scalar_one_or_none()


def get_latest_dish_location(session: Session) -> tuple[float, float] | None:
    """Return the most recent dish GPS coordinates stored in telemetry, if any.

    Used as a weather fallback after restart, before the poller has had a
    chance to refresh ``dish_location`` in memory.
    """
    stmt = (
        select(TelemetrySample.latitude, TelemetrySample.longitude)
        .where(TelemetrySample.latitude.is_not(None), TelemetrySample.longitude.is_not(None))
        .order_by(TelemetrySample.timestamp.desc())
        .limit(1)
    )
    row = session.execute(stmt).one_or_none()
    if row is None:
        return None
    return float(row.latitude), float(row.longitude)


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
    peak_download_bps: float | None
    peak_upload_bps: float | None
    best_latency_ms: float | None
    worst_latency_ms: float | None
    average_power_watts: float | None
    min_power_watts: float | None
    max_power_watts: float | None


def get_summary(
    session: Session,
    start: datetime | None = None,
    end: datetime | None = None,
) -> SummaryStats:
    """Compute averages, peaks, and uptime percentage over samples in ``[start, end]``."""
    connected_flag = case((TelemetrySample.connection_state == CONNECTED_STATE, 1), else_=0)

    stmt = select(
        func.count(TelemetrySample.id),
        func.avg(TelemetrySample.download_bps),
        func.avg(TelemetrySample.upload_bps),
        func.avg(TelemetrySample.latency_ms),
        func.avg(TelemetrySample.obstruction_percent),
        func.sum(connected_flag),
        func.max(TelemetrySample.download_bps),
        func.max(TelemetrySample.upload_bps),
        func.min(TelemetrySample.latency_ms),
        func.max(TelemetrySample.latency_ms),
        func.avg(TelemetrySample.power_watts),
        func.min(TelemetrySample.power_watts),
        func.max(TelemetrySample.power_watts),
    )
    stmt = _apply_range(stmt, start, end)

    (
        sample_count,
        avg_download,
        avg_upload,
        avg_latency,
        avg_obstruction,
        connected_count,
        peak_download,
        peak_upload,
        best_latency,
        worst_latency,
        avg_power,
        min_power,
        max_power,
    ) = session.execute(stmt).one()

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
        peak_download_bps=peak_download,
        peak_upload_bps=peak_upload,
        best_latency_ms=best_latency,
        worst_latency_ms=worst_latency,
        average_power_watts=avg_power,
        min_power_watts=min_power,
        max_power_watts=max_power,
    )


# Health score weighting. Uptime dominates (a flaky connection is worse than
# a slightly slow one); latency and obstruction are capped so a single bad
# metric can't single-handedly zero out an otherwise-healthy connection.
_LATENCY_FREE_MS = 20.0
_LATENCY_PENALTY_PER_MS = 0.25
_LATENCY_PENALTY_CAP = 25.0
_OBSTRUCTION_PENALTY_PER_PERCENT = 2.0
_OBSTRUCTION_PENALTY_CAP = 30.0

_DEFAULT_HEALTH_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class HealthScore:
    """A single 0-100 "how good is my Starlink right now" score, plus its inputs."""

    score: float | None
    quality_label: str
    uptime_percent: float | None
    latency_ms: float | None
    obstruction_percent: float | None
    obstruction_impact: str
    sample_count: int
    range_start: datetime | None
    range_end: datetime | None


def get_health_score(
    session: Session,
    start: datetime | None = None,
    end: datetime | None = None,
) -> HealthScore:
    """Compute a 0-100 health score from recent uptime, latency, and obstruction.

    Defaults to the last hour when neither ``start`` nor ``end`` is given,
    so the score reflects current conditions rather than all-time history.
    """
    if start is None and end is None:
        start = datetime.now(timezone.utc) - _DEFAULT_HEALTH_WINDOW

    stats = get_summary(session, start=start, end=end)

    if stats.sample_count == 0:
        return HealthScore(
            score=None,
            quality_label="Unknown",
            uptime_percent=None,
            latency_ms=None,
            obstruction_percent=None,
            obstruction_impact="Unknown",
            sample_count=0,
            range_start=start,
            range_end=end,
        )

    uptime_percent = stats.uptime_percent or 0.0
    latency_ms = stats.average_latency_ms
    obstruction_percent = stats.average_obstruction_percent or 0.0

    uptime_penalty = 100.0 - uptime_percent
    latency_penalty = 0.0
    if latency_ms is not None:
        latency_penalty = min(max(latency_ms - _LATENCY_FREE_MS, 0.0) * _LATENCY_PENALTY_PER_MS, _LATENCY_PENALTY_CAP)
    obstruction_penalty = min(obstruction_percent * _OBSTRUCTION_PENALTY_PER_PERCENT, _OBSTRUCTION_PENALTY_CAP)

    score = max(0.0, min(100.0, 100.0 - uptime_penalty - latency_penalty - obstruction_penalty))

    return HealthScore(
        score=round(score, 1),
        quality_label=_quality_label(score),
        uptime_percent=stats.uptime_percent,
        latency_ms=latency_ms,
        obstruction_percent=stats.average_obstruction_percent,
        obstruction_impact=_obstruction_impact(obstruction_percent),
        sample_count=stats.sample_count,
        range_start=start,
        range_end=end,
    )


def _quality_label(score: float) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Fair"
    if score >= 25:
        return "Poor"
    return "Critical"


def _obstruction_impact(obstruction_percent: float) -> str:
    if obstruction_percent <= 0.1:
        return "None"
    if obstruction_percent <= 2:
        return "Minor"
    if obstruction_percent <= 10:
        return "Moderate"
    return "Severe"


def get_open_connection_event(session: Session) -> ConnectionEvent | None:
    """Return the currently in-progress degraded-connection event, if any."""
    stmt = (
        select(ConnectionEvent)
        .where(ConnectionEvent.end_time.is_(None))
        .order_by(ConnectionEvent.start_time.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def upsert_open_connection_event(session: Session, at: datetime, reason: str) -> ConnectionEvent:
    """Open a new degraded-connection event, or update the reason of the one already open."""
    open_event = get_open_connection_event(session)
    if open_event is not None:
        if open_event.reason != reason:
            open_event.reason = reason
            session.commit()
            session.refresh(open_event)
        return open_event

    event = ConnectionEvent(start_time=at, end_time=None, reason=reason)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def close_open_connection_event(session: Session, end_time: datetime) -> ConnectionEvent | None:
    """Close the currently open event (if any), recording its final duration."""
    open_event = get_open_connection_event(session)
    if open_event is None:
        return None
    open_event.end_time = end_time
    start_time = _ensure_utc(open_event.start_time)
    open_event.duration_seconds = max((_ensure_utc(end_time) - start_time).total_seconds(), 0.0)
    session.commit()
    session.refresh(open_event)
    return open_event


def get_connection_events(
    session: Session,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
) -> list[ConnectionEvent]:
    """Return events overlapping ``[start, end]``, oldest first.

    An event with no ``end_time`` yet (still open/ongoing) is treated as
    overlapping every range that hasn't ended before it started.
    """
    stmt = select(ConnectionEvent)
    if start is not None:
        start = _ensure_utc(start)
        stmt = stmt.where(or_(ConnectionEvent.end_time.is_(None), ConnectionEvent.end_time >= start))
    if end is not None:
        stmt = stmt.where(ConnectionEvent.start_time <= _ensure_utc(end))
    stmt = stmt.order_by(ConnectionEvent.start_time.desc()).limit(limit)
    rows = list(session.execute(stmt).scalars().all())
    return list(reversed(rows))


@dataclass(frozen=True)
class OutageSummary:
    """Outage counts and total downtime, plus the underlying events for a timeline view."""

    outages_today: int
    outages_last_7d: int
    total_downtime_minutes_last_7d: float
    events: list[ConnectionEvent]


_OUTAGE_WINDOW = timedelta(days=7)


def get_outage_summary(session: Session, now: datetime | None = None) -> OutageSummary:
    """Summarize connection events from the last 7 days, plus how many started today."""
    now = now or datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = now - _OUTAGE_WINDOW

    events = get_connection_events(session, start=window_start, end=now, limit=1000)

    outages_today = sum(1 for event in events if _ensure_utc(event.start_time) >= today_start)

    total_seconds = 0.0
    for event in events:
        if event.duration_seconds is not None:
            total_seconds += event.duration_seconds
        elif event.end_time is None:
            total_seconds += max((now - _ensure_utc(event.start_time)).total_seconds(), 0.0)

    return OutageSummary(
        outages_today=outages_today,
        outages_last_7d=len(events),
        total_downtime_minutes_last_7d=round(total_seconds / 60.0, 1),
        events=events,
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
