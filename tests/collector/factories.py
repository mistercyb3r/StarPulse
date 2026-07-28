"""Test helpers for building fake Starlink samples and clients.

Not a test module itself (no ``test_`` prefix), just shared fixtures data
imported by the actual test modules in this package.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from starpulse.collector.client import StarlinkSample, StarlinkUnavailableError


def make_sample(**overrides: Any) -> StarlinkSample:
    defaults: dict[str, Any] = dict(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        connection_state="CONNECTED",
        uptime_seconds=12345,
        download_bps=150_000_000.0,
        upload_bps=12_000_000.0,
        latency_ms=25.5,
        ping_drop_rate=0.01,
        obstruction_percent=0.5,
        currently_obstructed=False,
        snr=None,
        power_watts=42.0,
        hardware_version="rev3_prod2400",
        software_version="2026.01.01.mr1",
        gps_valid=True,
        gps_enabled=True,
        gps_satellites=12,
        azimuth_deg=180.5,
        elevation_deg=64.2,
    )
    defaults.update(overrides)
    return StarlinkSample(**defaults)


class FakeStarlinkClient:
    """Test double implementing the ``StarlinkClient`` protocol.

    Returns queued samples in order; once exhausted it raises either the
    provided ``error`` or a generic ``StarlinkUnavailableError``, mimicking
    a dish that has gone offline.
    """

    def __init__(
        self,
        samples: list[StarlinkSample] | None = None,
        error: Exception | None = None,
        location: tuple[float, float] | None = None,
    ) -> None:
        self._samples = list(samples) if samples is not None else []
        self._error = error
        self._location = location
        self.closed = False
        self.fetch_calls = 0
        self.location_calls = 0

    def fetch_sample(self) -> StarlinkSample:
        self.fetch_calls += 1
        if self._samples:
            return self._samples.pop(0)
        if self._error is not None:
            raise self._error
        raise StarlinkUnavailableError("FakeStarlinkClient has no more samples queued")

    def fetch_location(self) -> tuple[float, float] | None:
        self.location_calls += 1
        return self._location

    def close(self) -> None:
        self.closed = True
