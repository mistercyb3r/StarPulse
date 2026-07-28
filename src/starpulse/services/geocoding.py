"""Optional reverse geocoding for human-readable place names.

Coordinates themselves always come from the dish or user config — this
module only labels them. Failures are soft: callers show coordinates
instead of inventing a place name.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Protocol

import httpx

from starpulse.logging_config import get_logger

logger = get_logger(__name__)

# BigDataCloud's free client reverse-geocode endpoint (no API key).
_REVERSE_URL = "https://api.bigdatacloud.net/data/reverse-geocode-client"
_DEFAULT_CACHE_SECONDS = 86_400.0  # 24h — place names rarely change
_REQUEST_TIMEOUT_SECONDS = 5.0


class PlaceNameResolver(Protocol):
    def resolve(self, latitude: float, longitude: float) -> str | None: ...


class NullPlaceNameResolver:
    """Test/disabled resolver that never invents a place name."""

    def resolve(self, latitude: float, longitude: float) -> str | None:
        return None


class BigDataCloudPlaceNameResolver:
    """Reverse-geocode lat/lon via BigDataCloud; TTL-cached per rounded coords."""

    def __init__(
        self,
        cache_seconds: float = _DEFAULT_CACHE_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        self._cache_seconds = cache_seconds
        self._client = client
        self._lock = threading.Lock()
        self._cache: dict[tuple[float, float], tuple[str | None, datetime]] = {}

    def resolve(self, latitude: float, longitude: float) -> str | None:
        key = (round(latitude, 3), round(longitude, 3))
        now = datetime.now(timezone.utc)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                place, fetched_at = cached
                if (now - fetched_at) < timedelta(seconds=self._cache_seconds):
                    return place

        place = self._fetch(latitude, longitude)
        with self._lock:
            self._cache[key] = (place, now)
        return place

    def _fetch(self, latitude: float, longitude: float) -> str | None:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "localityLanguage": "en",
        }
        try:
            if self._client is not None:
                response = self._client.get(_REVERSE_URL, params=params)
            else:
                response = httpx.get(_REVERSE_URL, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("Reverse geocode failed: %s", exc)
            return None

        return _format_place_name(data)


def _format_place_name(data: dict) -> str | None:
    locality = data.get("city") or data.get("locality") or data.get("principalSubdivision")
    if not locality:
        info = data.get("localityInfo")
        if isinstance(info, dict):
            entries = info.get("administrative") or []
            if entries and isinstance(entries[0], dict):
                locality = entries[0].get("name")

    country = data.get("countryCode") or data.get("countryName")
    if locality and country:
        return f"{locality}, {country}"
    if locality:
        return str(locality)
    if country:
        return str(country)
    return None
