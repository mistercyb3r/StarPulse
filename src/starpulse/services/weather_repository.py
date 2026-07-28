"""Persistence helpers for weather samples used by Weather Impact Analysis."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from starpulse.db.models import WeatherSample
from starpulse.services.weather import WeatherSnapshot


def save_weather_sample(
    session: Session,
    snapshot: WeatherSnapshot,
    location_source: str,
) -> WeatherSample:
    """Persist a weather snapshot as a new ``WeatherSample`` row."""
    row = WeatherSample(
        timestamp=snapshot.fetched_at,
        temperature_c=snapshot.temperature_c,
        feels_like_c=snapshot.feels_like_c,
        humidity_percent=snapshot.humidity_percent,
        wind_speed_kph=snapshot.wind_speed_kph,
        precipitation_mm=snapshot.precipitation_mm,
        precipitation_probability=snapshot.precipitation_probability,
        conditions=snapshot.conditions,
        latitude=snapshot.latitude,
        longitude=snapshot.longitude,
        location_source=location_source,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def get_latest_weather_sample(session: Session) -> WeatherSample | None:
    stmt = select(WeatherSample).order_by(WeatherSample.timestamp.desc()).limit(1)
    return session.execute(stmt).scalar_one_or_none()


def get_weather_history(
    session: Session,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 2000,
) -> list[WeatherSample]:
    """Return weather samples in ``[start, end]``, oldest first."""
    stmt = select(WeatherSample)
    if start is not None:
        stmt = stmt.where(WeatherSample.timestamp >= _ensure_utc(start))
    if end is not None:
        stmt = stmt.where(WeatherSample.timestamp <= _ensure_utc(end))
    stmt = stmt.order_by(WeatherSample.timestamp.desc()).limit(limit)
    rows = list(session.execute(stmt).scalars().all())
    return list(reversed(rows))


def has_recent_weather_sample(session: Session, within_seconds: float) -> bool:
    """True if a weather sample was stored within the last ``within_seconds``."""
    latest = get_latest_weather_sample(session)
    if latest is None:
        return False
    age = (datetime.now(timezone.utc) - _ensure_utc(latest.timestamp)).total_seconds()
    return age < within_seconds


def get_good_weather_windows(
    session: Session,
    start: datetime,
    end: datetime | None = None,
) -> list[WeatherSample]:
    """Weather samples that look like a fair-weather baseline for impact math."""
    end = end or datetime.now(timezone.utc)
    samples = get_weather_history(session, start=start, end=end, limit=5000)
    return [s for s in samples if _is_good_weather(s)]


def _is_good_weather(sample: WeatherSample) -> bool:
    conditions = (sample.conditions or "").lower()
    if any(token in conditions for token in ("rain", "snow", "thunder", "drizzle", "hail", "shower")):
        return False
    if sample.precipitation_probability is not None and sample.precipitation_probability >= 20:
        return False
    if sample.precipitation_mm is not None and sample.precipitation_mm >= 0.2:
        return False
    if sample.wind_speed_kph is not None and sample.wind_speed_kph >= 40:
        return False
    return True


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
