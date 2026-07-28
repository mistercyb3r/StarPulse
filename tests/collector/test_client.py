from __future__ import annotations

import grpc
import pytest
import starlink_grpc

from starpulse.collector.client import GrpcStarlinkClient, StarlinkUnavailableError

RAW_STATUS = {
    "state": "CONNECTED",
    "uptime": 98765,
    "snr": None,
    "pop_ping_drop_rate": 0.02,
    "downlink_throughput_bps": 123_456_789.0,
    "uplink_throughput_bps": 9_876_543.0,
    "pop_ping_latency_ms": 27.3,
    "fraction_obstructed": 0.015,
    "currently_obstructed": True,
    "hardware_version": "rev3_prod2400",
    "software_version": "2026.01.01.mr1",
    "gps_ready": True,
    "gps_enabled": True,
    "gps_sats": 14,
    "direction_azimuth": 172.4,
    "direction_elevation": 58.9,
}


def _status_data_ok(context=None):
    return RAW_STATUS, {}, {}


def _history_bulk_data_ok(parse_samples, context=None):
    return {"samples": 1, "end_counter": 1}, {"power_w": [42.5]}


def test_fetch_sample_maps_status_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(starlink_grpc, "status_data", _status_data_ok)
    monkeypatch.setattr(starlink_grpc, "history_bulk_data", _history_bulk_data_ok)

    client = GrpcStarlinkClient(host="dish.example", port=9200)
    sample = client.fetch_sample()

    assert sample.connection_state == "CONNECTED"
    assert sample.uptime_seconds == 98765
    assert sample.download_bps == 123_456_789.0
    assert sample.upload_bps == 9_876_543.0
    assert sample.latency_ms == 27.3
    assert sample.ping_drop_rate == 0.02
    assert sample.obstruction_percent == pytest.approx(1.5)
    assert sample.currently_obstructed is True
    assert sample.snr is None
    assert sample.power_watts == 42.5
    assert sample.hardware_version == "rev3_prod2400"
    assert sample.software_version == "2026.01.01.mr1"
    assert sample.gps_valid is True
    assert sample.gps_enabled is True
    assert sample.gps_satellites == 14
    assert sample.azimuth_deg == pytest.approx(172.4)
    assert sample.elevation_deg == pytest.approx(58.9)


def test_fetch_sample_wraps_grpc_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_rpc_error(context=None):
        raise grpc.RpcError("dish unreachable")

    monkeypatch.setattr(starlink_grpc, "status_data", raise_rpc_error)

    client = GrpcStarlinkClient(host="dish.example", port=9200)
    with pytest.raises(StarlinkUnavailableError):
        client.fetch_sample()


def test_fetch_sample_wraps_starlink_grpc_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_grpc_error(context=None):
        raise starlink_grpc.GrpcError("protocol mismatch")

    monkeypatch.setattr(starlink_grpc, "status_data", raise_grpc_error)

    client = GrpcStarlinkClient(host="dish.example", port=9200)
    with pytest.raises(StarlinkUnavailableError):
        client.fetch_sample()


def test_fetch_sample_tolerates_power_fetch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(starlink_grpc, "status_data", _status_data_ok)

    def raise_history_error(parse_samples, context=None):
        raise starlink_grpc.GrpcError("history unavailable")

    monkeypatch.setattr(starlink_grpc, "history_bulk_data", raise_history_error)

    client = GrpcStarlinkClient(host="dish.example", port=9200)
    sample = client.fetch_sample()

    assert sample.connection_state == "CONNECTED"
    assert sample.power_watts is None


def test_fetch_location_returns_coordinates(monkeypatch: pytest.MonkeyPatch) -> None:
    def location_data_ok(context=None):
        return {"latitude": 51.5074, "longitude": -0.1278, "altitude": 35.0}

    monkeypatch.setattr(starlink_grpc, "location_data", location_data_ok)

    client = GrpcStarlinkClient(host="dish.example", port=9200)
    location = client.fetch_location()

    assert location is not None
    assert location.latitude == pytest.approx(51.5074)
    assert location.longitude == pytest.approx(-0.1278)
    assert location.altitude_m == pytest.approx(35.0)


def test_fetch_location_returns_none_when_not_authorized(monkeypatch: pytest.MonkeyPatch) -> None:
    def location_data_denied(context=None):
        return {"latitude": None, "longitude": None, "altitude": None}

    monkeypatch.setattr(starlink_grpc, "location_data", location_data_denied)

    client = GrpcStarlinkClient(host="dish.example", port=9200)

    assert client.fetch_location() is None


def test_fetch_location_returns_none_on_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_grpc_error(context=None):
        raise starlink_grpc.GrpcError("unreachable")

    monkeypatch.setattr(starlink_grpc, "location_data", raise_grpc_error)

    client = GrpcStarlinkClient(host="dish.example", port=9200)

    assert client.fetch_location() is None


def test_close_closes_underlying_channel_context() -> None:
    closed = {"value": False}

    class FakeContext:
        def close(self) -> None:
            closed["value"] = True

    client = GrpcStarlinkClient()
    client._context = FakeContext()  # type: ignore[assignment]
    client.close()

    assert closed["value"] is True
