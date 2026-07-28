from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["uptime_seconds"] >= 0
    assert body["setup_complete"] is False
    # No poll has been attempted yet (start_collector=False in tests).
    assert body["starlink_connected"] is None
