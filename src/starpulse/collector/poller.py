"""Background service that periodically polls the dish and stores samples.

This is intentionally independent of FastAPI: it runs on its own daemon
thread using a plain ``StarlinkClient`` and the ``Database`` session
factory, so it can be started/stopped from an ASGI lifespan handler, a
CLI command, or a standalone script without any web framework involved.
"""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable, Optional

from starpulse.collector.client import DishCoordinates, StarlinkClient, StarlinkUnavailableError
from starpulse.collector.outages import OutageTracker
from starpulse.collector.repository import save_sample
from starpulse.db.models import TelemetrySample
from starpulse.db.session import Database
from starpulse.logging_config import get_logger

logger = get_logger(__name__)


class StarlinkPoller:
    """Polls a ``StarlinkClient`` on a fixed interval and stores results.

    ``start()``/``stop()`` are cheap, synchronous, and idempotent, making
    them safe to call from a synchronous FastAPI lifespan handler.
    """

    def __init__(
        self,
        client: StarlinkClient,
        database: Database,
        interval_seconds: float,
        on_error: Optional[Callable[[Exception], None]] = None,
        outage_tracker: Optional[OutageTracker] = None,
    ) -> None:
        self._client = client
        self._database = database
        self._interval_seconds = interval_seconds
        self._on_error = on_error
        self._outage_tracker = outage_tracker
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_poll_ok: Optional[bool] = None
        self._dish_location: Optional[DishCoordinates] = None
        self._logged_gps_locked_without_coords = False

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def last_poll_ok(self) -> Optional[bool]:
        """Whether the most recent poll attempt succeeded.

        ``None`` until the first poll attempt has happened at all (e.g.
        right after startup, or when the poller was never started).
        """
        return self._last_poll_ok

    @property
    def dish_location(self) -> Optional[DishCoordinates]:
        """The latest dish GPS coordinates known to this poller.

        Updated on every successful poll when the dish authorizes location
        sharing. Keeps the last good reading across transient failures so
        weather/location consumers don't flap. ``None`` until the first
        successful location fetch (or after a reconfigure clears it).
        """
        return self._dish_location

    def reconfigure(self, client: StarlinkClient, interval_seconds: float) -> None:
        """Swap in a new client/interval, e.g. after the setup wizard changes them.

        Restarts the polling thread if it was already running, so the
        change takes effect on the next tick rather than after a full
        app/container restart.
        """
        was_running = self.is_running
        if was_running:
            self.stop()
        else:
            self._client.close()

        self._client = client
        self._interval_seconds = interval_seconds
        self._last_poll_ok = None
        self._dish_location = None
        self._logged_gps_locked_without_coords = False

        if was_running:
            self.start()
        logger.info("Starlink poller reconfigured (interval=%ss)", interval_seconds)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="starlink-poller", daemon=True)
        self._thread.start()
        logger.info("Starlink poller started (interval=%ss)", self._interval_seconds)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        self._client.close()
        logger.info("Starlink poller stopped")

    def poll_once(self) -> TelemetrySample | None:
        """Fetch and store a single sample.

        Returns the stored row, or ``None`` if the dish was unreachable
        (in which case ``on_error``, if provided, is called with the
        exception instead of it propagating).
        """
        try:
            sample = self._client.fetch_sample()
        except StarlinkUnavailableError as exc:
            logger.warning("Skipping telemetry sample: %s", exc)
            self._last_poll_ok = False
            if self._outage_tracker is not None:
                self._outage_tracker.record_failure(datetime.now(timezone.utc))
            if self._on_error is not None:
                self._on_error(exc)
            return None

        sample = self._attach_dish_location(sample)

        session = next(self._database.get_session())
        try:
            row = save_sample(session, sample)
            logger.debug("Stored telemetry sample from %s", sample.timestamp)
            self._last_poll_ok = True
        finally:
            session.close()

        if self._outage_tracker is not None:
            self._outage_tracker.record_success(sample)
        return row

    def _attach_dish_location(self, sample):
        """Refresh/cache dish GPS and copy the latest known coords onto the sample.

        Coordinates come from the separate ``get_location`` RPC (location
        sharing), not from status ``gps_ready``. GPS can be locked while
        coordinates remain unavailable.
        """
        fetched = self._safe_fetch_location()
        if fetched is not None:
            self._dish_location = fetched
            self._logged_gps_locked_without_coords = False
        elif sample.gps_valid and self._dish_location is None:
            self._note_gps_locked_without_coordinates()

        if self._dish_location is None:
            return sample
        coords = self._dish_location
        return replace(
            sample,
            latitude=coords.latitude,
            longitude=coords.longitude,
            altitude_m=coords.altitude_m,
        )

    def _note_gps_locked_without_coordinates(self) -> None:
        """Log once until coordinates appear, so a 5s poll interval doesn't spam."""
        if self._logged_gps_locked_without_coords:
            return
        logger.warning("Starlink GPS locked but coordinates unavailable")
        self._logged_gps_locked_without_coords = True

    def _safe_fetch_location(self) -> Optional[DishCoordinates]:
        """Best-effort fetch of the dish's GPS position.

        Not every ``StarlinkClient`` implements ``fetch_location`` (it's
        optional, duck-typed rather than part of the core protocol), and
        even when it does, the dish may not have location sharing
        authorized — either case just means "no location", not an error.
        ``status_data`` never includes lat/lon; only ``location_data`` does.
        """
        fetch_location = getattr(self._client, "fetch_location", None)
        if fetch_location is None:
            return None
        try:
            return fetch_location()
        except Exception:
            logger.debug("Could not fetch dish location", exc_info=True)
            return None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.poll_once()
            self._stop_event.wait(self._interval_seconds)
