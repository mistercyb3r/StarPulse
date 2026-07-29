from __future__ import annotations

from starpulse.services.geoip import FixedGeoIpProvider, GeoIpResult, NullGeoIpProvider


def test_null_geoip_returns_none() -> None:
    assert NullGeoIpProvider().resolve() is None


def test_fixed_geoip_returns_result() -> None:
    result = GeoIpResult(latitude=1.0, longitude=2.0, place_name="Test", accuracy="City level only")
    assert FixedGeoIpProvider(result).resolve() == result
