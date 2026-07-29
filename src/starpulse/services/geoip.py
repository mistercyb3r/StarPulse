"""Approximate client location via public IP (city-level only).

Used as a weather fallback when the user has not set manual coordinates.
Never invents a precise address — results are labeled Approximate IP location.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

import httpx

from starpulse.logging_config import get_logger

logger = get_logger(__name__)

# Free client-IP geolocation (no API key). City-level accuracy only.
_GEOIP_URL = "https://api.bigdatacloud.net/data/ip-geolocation-client"
_DEFAULT_CACHE_SECONDS = 86_400.0
_REQUEST_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class GeoIpResult:
    latitude: float
    longitude: float
    place_name: str | None = None
    accuracy: str = "City level only"


class GeoIpProvider(Protocol):
    def resolve(self) -> GeoIpResult | None: ...


class NullGeoIpProvider:
    """Disabled/test provider — never returns a location."""

    def resolve(self) -> GeoIpResult | None:
        return None


class FixedGeoIpProvider:
    """Test double that always returns the same approximate location."""

    def __init__(self, result: GeoIpResult | None) -> None:
        self._result = result

    def resolve(self) -> GeoIpResult | None:
        return self._result


class BigDataCloudGeoIpProvider:
    """Resolve approximate lat/lon from the server's outbound IP."""

    def __init__(
        self,
        cache_seconds: float = _DEFAULT_CACHE_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        self._cache_seconds = cache_seconds
        self._client = client
        self._lock = threading.Lock()
        self._cached: tuple[GeoIpResult | None, datetime] | None = None

    def resolve(self) -> GeoIpResult | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            if self._cached is not None:
                result, fetched_at = self._cached
                if (now - fetched_at) < timedelta(seconds=self._cache_seconds):
                    return result

        result = self._fetch()
        with self._lock:
            self._cached = (result, now)
        return result

    def _fetch(self) -> GeoIpResult | None:
        params = {"localityLanguage": "en"}
        try:
            if self._client is not None:
                response = self._client.get(_GEOIP_URL, params=params)
            else:
                response = httpx.get(_GEOIP_URL, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("GeoIP lookup failed: %s", exc)
            return None

        try:
            latitude = float(data["latitude"])
            longitude = float(data["longitude"])
        except (KeyError, TypeError, ValueError):
            logger.debug("GeoIP response missing coordinates: %s", data)
            return None

        city = data.get("city") or data.get("locality")
        country = data.get("countryCode") or data.get("countryName")
        place_name = None
        if city and country:
            place_name = f"{city}, {country}"
        elif city:
            place_name = str(city)
        elif country:
            place_name = str(country)

        return GeoIpResult(latitude=latitude, longitude=longitude, place_name=place_name)
