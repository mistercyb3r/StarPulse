from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from starpulse.collector.repository import save_sample
from starpulse.db.session import Database

from tests.collector.factories import make_sample


def _insert_sample(app: FastAPI, **overrides):
    database: Database = app.state.db
    session = next(database.get_session())
    try:
        return save_sample(session, make_sample(**overrides))
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
