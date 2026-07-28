"""ORM models.

``AppMeta`` is a small generic key/value table used to prove the database
layer works end-to-end (schema creation, sessions, migrations story) and
to later hold things like the applied schema version.

``TelemetrySample`` stores one polled snapshot of Starlink dish telemetry.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from starpulse.db.base import Base


class AppMeta(Base):
    """Generic key/value store for application-level metadata."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TelemetrySample(Base):
    """One polled snapshot of Starlink dish telemetry.

    Populated by the Starlink collector (see ``starpulse.collector``),
    never written to directly from API routes.
    """

    __tablename__ = "telemetry_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # When the sample was collected.
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, default=_utcnow)

    # Dish-reported connection state, e.g. "CONNECTED", "SEARCHING", "OFFLINE".
    connection_state: Mapped[str] = mapped_column(String(32), nullable=False)

    # Seconds since the dish last rebooted.
    uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Download / upload throughput, in bits per second.
    download_bps: Mapped[float | None] = mapped_column(Float, nullable=True)
    upload_bps: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Round-trip ping latency to the Starlink point of presence, in ms.
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Fraction (0.0-1.0) of ping replies lost during the sample period.
    ping_drop_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Percentage (0-100) of the sky view currently obstructed.
    obstruction_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    currently_obstructed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Signal-to-noise ratio reported by the dish. Frequently null, since
    # SNR reporting was deprecated in newer dish firmware/protocol versions.
    snr: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Power draw, in watts. Only available via the dish's bulk history
    # data (not the general status), so may be null if that call fails.
    power_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
