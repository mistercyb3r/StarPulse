"""Background service that periodically polls the dish and stores samples.

This is intentionally independent of FastAPI: it runs on its own daemon
thread using a plain ``StarlinkClient`` and the ``Database`` session
factory, so it can be started/stopped from an ASGI lifespan handler, a
CLI command, or a standalone script without any web framework involved.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from starpulse.collector.client import StarlinkClient, StarlinkUnavailableError
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
    ) -> None:
        self._client = client
        self._database = database
        self._interval_seconds = interval_seconds
        self._on_error = on_error
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_poll_ok: Optional[bool] = None

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
            if self._on_error is not None:
                self._on_error(exc)
            return None

        session = next(self._database.get_session())
        try:
            row = save_sample(session, sample)
            logger.debug("Stored telemetry sample from %s", sample.timestamp)
            self._last_poll_ok = True
            return row
        finally:
            session.close()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.poll_once()
            self._stop_event.wait(self._interval_seconds)
