from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from starpulse.collector.repository import close_open_connection_event, save_sample, upsert_open_connection_event
from starpulse.db.session import Database

from tests.collector.factories import make_sample


def _insert_sample(app: FastAPI, **overrides):
    database: Database = app.state.db
    session = next(database.get_session())
    try:
        return save_sample(session, make_sample(**overrides))
    finally:
        session.close()


def _insert_closed_event(app: FastAPI, start: datetime, end: datetime, reason: str = "disconnected"):
    database: Database = app.state.db
    session = next(database.get_session())
    try:
        upsert_open_connection_event(session, at=start, reason=reason)
        return close_open_connection_event(session, end_time=end)
    finally:
        session.close()


def test_status_returns_404_when_no_samples(client: TestClient) -> None:
    response = client.get("/api/starlink/status")

    assert response.status_code == 404


def test_status_returns_latest_sample(app: FastAPI, client: TestClient) -> None:
    _insert_sample(app, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), connection_state="SEARCHING")
    _insert_sample(
        app,
        timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        connection_state="CONNECTED",
        download_bps=999.0,
    )

    response = client.get("/api/starlink/status")

    assert response.status_code == 200
    body = response.json()
    assert body["connection_state"] == "CONNECTED"
    assert body["download_bps"] == 999.0


def test_history_returns_empty_list_when_no_samples(client: TestClient) -> None:
    response = client.get("/api/starlink/history")

    assert response.status_code == 200
    assert response.json() == {"samples": [], "count": 0}


def test_history_returns_samples_oldest_first(app: FastAPI, client: TestClient) -> None:
    _insert_sample(app, timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc), connection_state="B")
    _insert_sample(app, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), connection_state="A")
    _insert_sample(app, timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc), connection_state="C")

    response = client.get("/api/starlink/history")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert [sample["connection_state"] for sample in body["samples"]] == ["A", "B", "C"]


def test_history_respects_limit(app: FastAPI, client: TestClient) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        _insert_sample(app, timestamp=base + timedelta(hours=i), connection_state=f"S{i}")

    response = client.get("/api/starlink/history", params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert [sample["connection_state"] for sample in body["samples"]] == ["S3", "S4"]


def test_history_respects_time_range(app: FastAPI, client: TestClient) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        _insert_sample(app, timestamp=base + timedelta(hours=i), connection_state=f"S{i}")

    response = client.get(
        "/api/starlink/history",
        params={
            "start": (base + timedelta(hours=1)).isoformat(),
            "end": (base + timedelta(hours=3)).isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [sample["connection_state"] for sample in body["samples"]] == ["S1", "S2", "S3"]


def test_history_limit_validation(client: TestClient) -> None:
    assert client.get("/api/starlink/history", params={"limit": 0}).status_code == 422
    assert client.get("/api/starlink/history", params={"limit": 10_000}).status_code == 422


def test_summary_with_no_samples(client: TestClient) -> None:
    response = client.get("/api/starlink/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["sample_count"] == 0
    assert body["average_download_bps"] is None
    assert body["average_upload_bps"] is None
    assert body["average_latency_ms"] is None
    assert body["average_obstruction_percent"] is None
    assert body["uptime_percent"] is None
    assert body["peak_download_bps"] is None
    assert body["peak_upload_bps"] is None
    assert body["best_latency_ms"] is None
    assert body["worst_latency_ms"] is None
    assert body["average_power_watts"] is None
    assert body["min_power_watts"] is None
    assert body["max_power_watts"] is None


def test_summary_computes_averages_and_uptime(app: FastAPI, client: TestClient) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _insert_sample(
        app,
        timestamp=base,
        connection_state="CONNECTED",
        download_bps=100.0,
        upload_bps=10.0,
        latency_ms=20.0,
        obstruction_percent=0.0,
    )
    _insert_sample(
        app,
        timestamp=base + timedelta(hours=1),
        connection_state="SEARCHING",
        download_bps=200.0,
        upload_bps=20.0,
        latency_ms=40.0,
        obstruction_percent=2.0,
    )
    _insert_sample(
        app,
        timestamp=base + timedelta(hours=2),
        connection_state="CONNECTED",
        download_bps=300.0,
        upload_bps=30.0,
        latency_ms=60.0,
        obstruction_percent=4.0,
    )

    response = client.get("/api/starlink/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["sample_count"] == 3
    assert body["average_download_bps"] == pytest.approx(200.0)
    assert body["average_upload_bps"] == pytest.approx(20.0)
    assert body["average_latency_ms"] == pytest.approx(40.0)
    assert body["average_obstruction_percent"] == pytest.approx(2.0)
    # 2 of 3 samples were CONNECTED.
    assert body["uptime_percent"] == pytest.approx(66.6667, rel=1e-3)


def test_summary_respects_time_range(app: FastAPI, client: TestClient) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _insert_sample(app, timestamp=base, connection_state="SEARCHING", download_bps=100.0)
    _insert_sample(
        app, timestamp=base + timedelta(hours=1), connection_state="CONNECTED", download_bps=300.0
    )

    response = client.get(
        "/api/starlink/summary",
        params={"start": (base + timedelta(minutes=30)).isoformat()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sample_count"] == 1
    assert body["average_download_bps"] == pytest.approx(300.0)
    assert body["uptime_percent"] == pytest.approx(100.0)


def test_summary_includes_peak_values(app: FastAPI, client: TestClient) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _insert_sample(app, timestamp=base, download_bps=100.0, upload_bps=10.0)
    _insert_sample(app, timestamp=base + timedelta(hours=1), download_bps=500.0, upload_bps=50.0)
    _insert_sample(app, timestamp=base + timedelta(hours=2), download_bps=200.0, upload_bps=20.0)

    response = client.get("/api/starlink/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["peak_download_bps"] == pytest.approx(500.0)
    assert body["peak_upload_bps"] == pytest.approx(50.0)


def test_summary_includes_latency_and_power_stats(app: FastAPI, client: TestClient) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _insert_sample(app, timestamp=base, latency_ms=20.0, power_watts=30.0)
    _insert_sample(app, timestamp=base + timedelta(hours=1), latency_ms=80.0, power_watts=50.0)

    response = client.get("/api/starlink/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["best_latency_ms"] == pytest.approx(20.0)
    assert body["worst_latency_ms"] == pytest.approx(80.0)
    assert body["average_power_watts"] == pytest.approx(40.0)
    assert body["min_power_watts"] == pytest.approx(30.0)
    assert body["max_power_watts"] == pytest.approx(50.0)


def test_summary_period_shorthand_overrides_start(app: FastAPI, client: TestClient) -> None:
    old = datetime.now(timezone.utc) - timedelta(days=10)
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    _insert_sample(app, timestamp=old, download_bps=999.0)
    _insert_sample(app, timestamp=recent, download_bps=111.0)

    response = client.get("/api/starlink/summary", params={"period": "24h"})

    assert response.status_code == 200
    body = response.json()
    assert body["sample_count"] == 1
    assert body["average_download_bps"] == pytest.approx(111.0)


def test_summary_rejects_unknown_period(client: TestClient) -> None:
    response = client.get("/api/starlink/summary", params={"period": "1y"})

    assert response.status_code == 422


def test_health_with_no_samples(client: TestClient) -> None:
    response = client.get("/api/starlink/health")

    assert response.status_code == 200
    body = response.json()
    assert body["health_score"] is None
    assert body["quality_label"] == "Unknown"
    assert body["sample_count"] == 0


def test_health_reflects_recent_samples(app: FastAPI, client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    _insert_sample(
        app,
        timestamp=now - timedelta(minutes=5),
        connection_state="CONNECTED",
        latency_ms=15.0,
        obstruction_percent=0.0,
    )

    response = client.get("/api/starlink/health")

    assert response.status_code == 200
    body = response.json()
    assert body["health_score"] == pytest.approx(100.0)
    assert body["quality_label"] == "Excellent"
    assert body["obstruction_impact"] == "None"


def test_dish_info_returns_404_when_no_samples(client: TestClient) -> None:
    response = client.get("/api/starlink/dish-info")

    assert response.status_code == 404


def test_dish_info_returns_latest_sample_fields(app: FastAPI, client: TestClient) -> None:
    _insert_sample(
        app,
        connection_state="CONNECTED",
        hardware_version="rev3_prod2400",
        software_version="2026.01.01.mr1",
        gps_valid=True,
        gps_enabled=True,
        gps_satellites=16,
        azimuth_deg=180.0,
        elevation_deg=65.0,
    )

    response = client.get("/api/starlink/dish-info")

    assert response.status_code == 200
    body = response.json()
    assert body["hardware_version"] == "rev3_prod2400"
    assert body["software_version"] == "2026.01.01.mr1"
    assert body["gps_valid"] is True
    assert body["gps_satellites"] == 16
    assert body["azimuth_deg"] == pytest.approx(180.0)
    assert body["elevation_deg"] == pytest.approx(65.0)
    assert "last_updated" in body


def test_outages_with_no_events(client: TestClient) -> None:
    response = client.get("/api/starlink/outages")

    assert response.status_code == 200
    body = response.json()
    assert body["outages_today"] == 0
    assert body["outages_last_7d"] == 0
    assert body["total_downtime_minutes_last_7d"] == 0.0
    assert body["events"] == []


def test_outages_returns_summary_and_events(app: FastAPI, client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    _insert_closed_event(app, start=now - timedelta(minutes=30), end=now - timedelta(minutes=25), reason="disconnected")

    response = client.get("/api/starlink/outages")

    assert response.status_code == 200
    body = response.json()
    assert body["outages_today"] == 1
    assert body["outages_last_7d"] == 1
    assert body["total_downtime_minutes_last_7d"] == pytest.approx(5.0)
    assert len(body["events"]) == 1
    assert body["events"][0]["reason"] == "disconnected"
    assert body["events"][0]["duration_seconds"] == pytest.approx(300.0)


def test_outages_excludes_events_older_than_7_days(app: FastAPI, client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    _insert_closed_event(
        app, start=now - timedelta(days=10), end=now - timedelta(days=10) + timedelta(minutes=5), reason="disconnected"
    )

    response = client.get("/api/starlink/outages")

    assert response.status_code == 200
    body = response.json()
    assert body["outages_last_7d"] == 0
    assert body["events"] == []
