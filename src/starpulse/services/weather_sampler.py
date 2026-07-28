"""Background sampler that persists weather readings for impact analysis.

Runs on the weather cache interval so Open-Meteo is not hammered, and
only writes a new ``WeatherSample`` when none was stored within that
interval (the in-memory ``CachedWeatherProvider`` still handles
request-path caching independently).
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from starpulse.collector.poller import StarlinkPoller
from starpulse.config.settings import Settings
from starpulse.db.session import Database
from starpulse.logging_config import get_logger
from starpulse.services.location import resolve_weather_location
from starpulse.services.weather import CachedWeatherProvider, WeatherUnavailableError
from starpulse.services.weather_repository import has_recent_weather_sample, save_weather_sample

logger = get_logger(__name__)


class WeatherSampler:
    """Periodically resolve location, fetch (cached) weather, and persist samples."""

    def __init__(
        self,
        database: Database,
        settings: Settings,
        collector: StarlinkPoller,
        provider: CachedWeatherProvider,
        *,
        interval_seconds: float | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._database = database
        self._settings = settings
        self._collector = collector
        self._provider = provider
        self._interval_seconds = interval_seconds if interval_seconds is not None else settings.weather.cache_seconds
        self._enabled = settings.weather.enabled if enabled is None else enabled
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if not self._enabled or self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="weather-sampler", daemon=True)
        self._thread.start()
        logger.info("Weather sampler started (interval=%ss)", self._interval_seconds)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        logger.info("Weather sampler stopped")

    def sample_once(self) -> bool:
        """Fetch and optionally persist one weather sample. Returns True if a row was written."""
        if not self._enabled:
            return False

        session = next(self._database.get_session())
        try:
            if has_recent_weather_sample(session, within_seconds=self._interval_seconds):
                return False

            resolved = resolve_weather_location(self._settings, self._collector, session, persist=True)
            if resolved is None:
                logger.debug("Weather sampler skipped: location unavailable")
                return False

            try:
                snapshot = self._provider.get_weather(resolved.latitude, resolved.longitude)
            except WeatherUnavailableError as exc:
                logger.warning("Weather sampler could not fetch weather: %s", exc)
                return False

            save_weather_sample(session, snapshot, location_source=resolved.source)
            logger.debug("Stored weather sample at %s", snapshot.fetched_at)
            return True
        finally:
            session.close()

    def _run(self) -> None:
        # Sample immediately on start so dashboards have data without waiting a full TTL.
        self.sample_once()
        while not self._stop_event.is_set():
            self._stop_event.wait(self._interval_seconds)
            if self._stop_event.is_set():
                break
            self.sample_once()
