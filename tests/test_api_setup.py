from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from starpulse.app import create_app
from starpulse.config.settings import load_settings

from tests.collector.factories import FakeStarlinkClient


def _make_client(tmp_path: Path) -> TestClient:
    settings = load_settings(data_dir=tmp_path, env={})
    app = create_app(settings, starlink_client=FakeStarlinkClient(samples=[]), start_collector=False)
    return TestClient(app)


def test_setup_status_defaults_to_incomplete(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        response = client.get("/api/setup/status")

    assert response.status_code == 200
    body = response.json()
    assert body["setup_complete"] is False
    assert body["dish_host"] == "192.168.100.1"
    assert body["poll_interval_seconds"] == 5.0
    assert body["port"] == 8000


def test_submitting_setup_persists_and_marks_complete(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        response = client.post(
            "/api/setup",
            json={"dish_host": "10.1.2.3", "poll_interval_seconds": 10.0, "port": 8000},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["setup_complete"] is True
        assert body["restart_required"] is False

        status = client.get("/api/setup/status").json()
        assert status["setup_complete"] is True
        assert status["dish_host"] == "10.1.2.3"
        assert status["poll_interval_seconds"] == 10.0

    # Persisted to config.toml, so a fresh load sees it too.
    reloaded = load_settings(data_dir=tmp_path, env={})
    assert reloaded.starlink.dish_host == "10.1.2.3"
    assert reloaded.starlink.poll_interval_seconds == 10.0


def test_submitting_setup_with_new_port_flags_restart_required(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        response = client.post(
            "/api/setup",
            json={"dish_host": "192.168.100.1", "poll_interval_seconds": 5.0, "port": 9090},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["restart_required"] is True
    assert "restart" in body["message"].lower()


def test_submitting_setup_reconfigures_the_collector(tmp_path: Path) -> None:
    settings = load_settings(data_dir=tmp_path, env={})
    fake_client = FakeStarlinkClient(samples=[])
    app = create_app(settings, starlink_client=fake_client, start_collector=False)

    with TestClient(app) as client:
        collector = app.state.collector
        original_client = collector._client

        client.post(
            "/api/setup",
            json={"dish_host": "10.9.9.9", "poll_interval_seconds": 3.0, "port": 8000},
        )

        assert original_client.closed is True
        assert collector._interval_seconds == 3.0


def test_setup_rejects_invalid_payload(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        response = client.post(
            "/api/setup",
            json={"dish_host": "", "poll_interval_seconds": -1, "port": 70000},
        )

    assert response.status_code == 422
