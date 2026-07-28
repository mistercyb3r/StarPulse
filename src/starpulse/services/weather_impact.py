"""Correlate current/historical weather with Starlink telemetry for impact scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from starpulse.collector import repository as telemetry_repository
from starpulse.db.models import WeatherSample
from starpulse.services.weather import WeatherSnapshot
from starpulse.services.weather_repository import get_good_weather_windows, get_latest_weather_sample

CONNECTED_STATE = "CONNECTED"
_RECENT_WINDOW = timedelta(hours=1)
_BASELINE_WINDOW = timedelta(days=7)

_HIGH_WIND_KPH = 60.0
_MODERATE_WIND_KPH = 40.0
_HIGH_PRECIP_PROB = 70.0
_MODERATE_PRECIP_PROB = 40.0
_HIGH_PRECIP_MM = 2.0
_MODERATE_PRECIP_MM = 0.5

_SEVERE_CONDITIONS = ("thunder", "heavy rain", "violent", "heavy snow", "hail")
_WET_CONDITIONS = ("rain", "drizzle", "snow", "shower")


@dataclass(frozen=True)
class WeatherImpactResult:
    severity: str  # Low | Moderate | High | Unknown
    reasons: list[str]
    conditions: str | None
    temperature_c: float | None
    wind_speed_kph: float | None
    precipitation_probability: float | None
    precipitation_mm: float | None
    latency_ms: float | None
    download_bps: float | None
    upload_bps: float | None
    latency_delta_percent: float | None
    download_delta_percent: float | None
    active_outage: bool
    sample_count: int


def compute_weather_impact(
    session: Session,
    snapshot: WeatherSnapshot | WeatherSample | None = None,
    *,
    now: datetime | None = None,
) -> WeatherImpactResult:
    """Compute Weather Impact severity and human-readable reasons."""
    now = now or datetime.now(timezone.utc)
    weather = snapshot or get_latest_weather_sample(session)

    if weather is None:
        return WeatherImpactResult(
            severity="Unknown",
            reasons=["No weather data available yet"],
            conditions=None,
            temperature_c=None,
            wind_speed_kph=None,
            precipitation_probability=None,
            precipitation_mm=None,
            latency_ms=None,
            download_bps=None,
            upload_bps=None,
            latency_delta_percent=None,
            download_delta_percent=None,
            active_outage=False,
            sample_count=0,
        )

    conditions = getattr(weather, "conditions", None)
    temperature_c = getattr(weather, "temperature_c", None)
    wind_speed_kph = getattr(weather, "wind_speed_kph", None)
    precip_prob = getattr(weather, "precipitation_probability", None)
    precip_mm = getattr(weather, "precipitation_mm", None)

    weather_level, weather_reasons = _weather_severity(
        conditions=conditions,
        wind_speed_kph=wind_speed_kph,
        precip_prob=precip_prob,
        precip_mm=precip_mm,
    )

    recent = telemetry_repository.get_summary(session, start=now - _RECENT_WINDOW, end=now)
    baseline_stats = _baseline_performance(session, now)
    open_event = telemetry_repository.get_open_connection_event(session)
    active_outage = open_event is not None

    latency_delta = _percent_delta(recent.average_latency_ms, baseline_stats.average_latency_ms if baseline_stats else None)
    download_delta = _percent_delta(recent.average_download_bps, baseline_stats.average_download_bps if baseline_stats else None)

    perf_level, perf_reasons = _performance_severity(
        latency_delta_percent=latency_delta,
        download_delta_percent=download_delta,
        ping_drop_rate=_recent_packet_loss(session, now),
        active_outage=active_outage,
    )

    severity = _max_severity(weather_level, perf_level)
    reasons = weather_reasons + perf_reasons
    if not reasons and severity == "Low":
        reasons = _benign_reasons(conditions, wind_speed_kph, precip_prob, precip_mm)

    return WeatherImpactResult(
        severity=severity,
        reasons=reasons,
        conditions=conditions,
        temperature_c=temperature_c,
        wind_speed_kph=wind_speed_kph,
        precipitation_probability=precip_prob,
        precipitation_mm=precip_mm,
        latency_ms=recent.average_latency_ms,
        download_bps=recent.average_download_bps,
        upload_bps=recent.average_upload_bps,
        latency_delta_percent=latency_delta,
        download_delta_percent=download_delta,
        active_outage=active_outage,
        sample_count=recent.sample_count,
    )


def _weather_severity(
    *,
    conditions: str | None,
    wind_speed_kph: float | None,
    precip_prob: float | None,
    precip_mm: float | None,
) -> tuple[str, list[str]]:
    level = "Low"
    reasons: list[str] = []
    text = (conditions or "").lower()

    if any(token in text for token in _SEVERE_CONDITIONS):
        level = "High"
        reasons.append(conditions or "Severe weather detected")
    elif any(token in text for token in _WET_CONDITIONS):
        level = _max_severity(level, "Moderate")
        if "heavy" in text:
            level = "High"
            reasons.append(conditions or "Heavy precipitation detected")
        else:
            reasons.append(conditions or "Precipitation detected")

    if wind_speed_kph is not None:
        if wind_speed_kph >= _HIGH_WIND_KPH:
            level = "High"
            reasons.append(f"High wind ({wind_speed_kph:.0f} km/h)")
        elif wind_speed_kph >= _MODERATE_WIND_KPH:
            level = _max_severity(level, "Moderate")
            reasons.append(f"Elevated wind ({wind_speed_kph:.0f} km/h)")

    if precip_prob is not None:
        if precip_prob >= _HIGH_PRECIP_PROB:
            level = "High"
            reasons.append(f"High rain probability ({precip_prob:.0f}%)")
        elif precip_prob >= _MODERATE_PRECIP_PROB:
            level = _max_severity(level, "Moderate")
            reasons.append(f"Rain likely ({precip_prob:.0f}%)")

    if precip_mm is not None:
        if precip_mm >= _HIGH_PRECIP_MM:
            level = "High"
            reasons.append(f"Heavy rain detected ({precip_mm:.1f} mm)")
        elif precip_mm >= _MODERATE_PRECIP_MM:
            level = _max_severity(level, "Moderate")
            reasons.append(f"Rain detected ({precip_mm:.1f} mm)")

    return level, reasons


def _performance_severity(
    *,
    latency_delta_percent: float | None,
    download_delta_percent: float | None,
    ping_drop_rate: float | None,
    active_outage: bool,
) -> tuple[str, list[str]]:
    level = "Low"
    reasons: list[str] = []

    if active_outage:
        level = "High"
        reasons.append("Active connection outage")

    if latency_delta_percent is not None and latency_delta_percent > 0:
        if latency_delta_percent >= 50:
            level = "High"
            reasons.append(f"Latency increased by {latency_delta_percent:.0f}%")
        elif latency_delta_percent >= 25:
            level = _max_severity(level, "Moderate")
            reasons.append(f"Latency increased by {latency_delta_percent:.0f}%")

    if download_delta_percent is not None and download_delta_percent < 0:
        drop = abs(download_delta_percent)
        if drop >= 40:
            level = "High"
            reasons.append(f"Download speed reduced by {drop:.0f}%")
        elif drop >= 25:
            level = _max_severity(level, "Moderate")
            reasons.append(f"Download speed reduced by {drop:.0f}%")

    if ping_drop_rate is not None and ping_drop_rate >= 0.2:
        level = _max_severity(level, "High" if ping_drop_rate >= 0.5 else "Moderate")
        reasons.append(f"Elevated packet loss ({ping_drop_rate * 100:.0f}%)")

    return level, reasons


def _benign_reasons(
    conditions: str | None,
    wind_speed_kph: float | None,
    precip_prob: float | None,
    precip_mm: float | None,
) -> list[str]:
    reasons: list[str] = []
    if conditions:
        reasons.append(conditions)
    if wind_speed_kph is None or wind_speed_kph < _MODERATE_WIND_KPH:
        reasons.append("Low wind")
    if (precip_prob is None or precip_prob < 20) and (precip_mm is None or precip_mm < 0.2):
        reasons.append("No rain")
    return reasons or ["Conditions look stable"]


def _baseline_performance(session: Session, now: datetime):
    good = get_good_weather_windows(session, start=now - _BASELINE_WINDOW, end=now)
    if not good:
        return None
    # Average telemetry across windows spanned by good-weather samples (±30 min each).
    # Using the full good-weather period as one range keeps the query cheap.
    start = min(_ensure_utc(s.timestamp) for s in good) - timedelta(minutes=30)
    end = max(_ensure_utc(s.timestamp) for s in good) + timedelta(minutes=30)
    stats = telemetry_repository.get_summary(session, start=start, end=end)
    return stats if stats.sample_count else None


def _recent_packet_loss(session: Session, now: datetime) -> float | None:
    samples = telemetry_repository.get_recent_samples(session, start=now - _RECENT_WINDOW, end=now, limit=500)
    values = [s.ping_drop_rate for s in samples if s.ping_drop_rate is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _percent_delta(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline is None or baseline == 0:
        return None
    return ((current - baseline) / baseline) * 100.0


def _max_severity(a: str, b: str) -> str:
    order = {"Low": 0, "Moderate": 1, "High": 2, "Unknown": -1}
    return a if order.get(a, -1) >= order.get(b, -1) else b


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
