"""Starlink dish client.

Talks to the dish using the ``starlink_grpc`` module from the
``starlink-grpc-core`` package (the packaged core of the
sparky8512/starlink-grpc-tools project). That module resolves the dish's
gRPC protocol via reflection at runtime, so no protobuf files need to be
generated or vendored here.

Everything above this module (the poller, the database layer, the API)
depends only on the ``StarlinkClient`` protocol and ``StarlinkSample``
dataclass defined here, not on gRPC or ``starlink_grpc`` directly. That
keeps the rest of the app testable with a fake client and insulated from
changes to the underlying transport.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import grpc
import starlink_grpc

from starpulse.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_DISH_HOST = "192.168.100.1"
DEFAULT_DISH_PORT = 9200

# Errors raised by starlink_grpc/grpc that indicate the dish is temporarily
# unreachable or returned something we don't know how to parse.
_TRANSPORT_ERRORS = (starlink_grpc.GrpcError, grpc.RpcError, AttributeError, ValueError, IndexError)


class StarlinkUnavailableError(Exception):
    """Raised when the dish cannot be reached or its response can't be parsed."""


@dataclass(frozen=True)
class StarlinkSample:
    """A normalized snapshot of dish telemetry, independent of the gRPC wire format."""

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

    # Static/semi-static dish info, reported alongside every status poll.
    hardware_version: str | None
    software_version: str | None
    gps_valid: bool | None
    gps_enabled: bool | None
    gps_satellites: int | None
    azimuth_deg: float | None
    elevation_deg: float | None


class StarlinkClient(Protocol):
    """Anything that can fetch one telemetry sample from a dish."""

    def fetch_sample(self) -> StarlinkSample: ...

    def close(self) -> None: ...

    def fetch_location(self) -> tuple[float, float] | None:
        """Return the dish's (latitude, longitude), or ``None`` if unavailable.

        Optional: not every implementation needs to provide this — callers
        should use ``getattr(client, "fetch_location", None)`` rather than
        assuming it exists, since this is a duck-typed extension to the
        core protocol rather than a hard requirement.
        """
        ...


class GrpcStarlinkClient:
    """Real ``StarlinkClient`` backed by a gRPC connection to the dish."""

    def __init__(self, host: str = DEFAULT_DISH_HOST, port: int = DEFAULT_DISH_PORT) -> None:
        self._context = starlink_grpc.ChannelContext(target=f"{host}:{port}")

    def fetch_sample(self) -> StarlinkSample:
        try:
            status, _obstruction, _alerts = starlink_grpc.status_data(context=self._context)
        except _TRANSPORT_ERRORS as exc:
            raise StarlinkUnavailableError(f"Failed to fetch dish status: {exc}") from exc

        return _sample_from_status(status, power_watts=self._fetch_latest_power())

    def _fetch_latest_power(self) -> float | None:
        """Best-effort fetch of the most recent power draw sample.

        Power usage is only exposed via the dish's bulk history data, not
        the general status, and older firmware may not report it at all.
        A failure here is logged and ignored rather than failing the
        whole sample, since throughput/latency/obstruction are more
        important than power.
        """
        try:
            _general, bulk = starlink_grpc.history_bulk_data(1, context=self._context)
        except _TRANSPORT_ERRORS as exc:
            logger.debug("Could not fetch power usage sample: %s", exc)
            return None

        power_samples = bulk.get("power_w") or []
        return power_samples[-1] if power_samples else None

    def fetch_location(self) -> tuple[float, float] | None:
        """Best-effort fetch of the dish's GPS position.

        Requires location sharing to be authorized on the dish; returns
        ``None`` (rather than raising) whenever it isn't, since that's a
        normal, expected outcome, not a failure.
        """
        try:
            location = starlink_grpc.location_data(context=self._context)
        except _TRANSPORT_ERRORS as exc:
            logger.debug("Could not fetch dish location: %s", exc)
            return None

        latitude = location.get("latitude")
        longitude = location.get("longitude")
        if latitude is None or longitude is None:
            return None
        return latitude, longitude

    def close(self) -> None:
        self._context.close()


def _sample_from_status(status: dict[str, Any], power_watts: float | None) -> StarlinkSample:
    fraction_obstructed = status.get("fraction_obstructed")
    return StarlinkSample(
        timestamp=datetime.now(timezone.utc),
        connection_state=status.get("state") or "UNKNOWN",
        uptime_seconds=status.get("uptime"),
        download_bps=status.get("downlink_throughput_bps"),
        upload_bps=status.get("uplink_throughput_bps"),
        latency_ms=status.get("pop_ping_latency_ms"),
        ping_drop_rate=status.get("pop_ping_drop_rate"),
        obstruction_percent=(fraction_obstructed * 100 if fraction_obstructed is not None else None),
        currently_obstructed=status.get("currently_obstructed"),
        snr=status.get("snr"),
        power_watts=power_watts,
        hardware_version=status.get("hardware_version"),
        software_version=status.get("software_version"),
        gps_valid=status.get("gps_ready"),
        gps_enabled=status.get("gps_enabled"),
        gps_satellites=status.get("gps_sats"),
        azimuth_deg=status.get("direction_azimuth"),
        elevation_deg=status.get("direction_elevation"),
    )
