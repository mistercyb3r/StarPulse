from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from starpulse.app import create_app
from starpulse.collector.repository import count_samples
from starpulse.config.settings import load_settings

from tests.collector.factories import FakeStarlinkClient, make_sample


def test_app_wires_up_and_runs_injected_collector(tmp_path: Path) -> None:
    """End-to-end check that create_app() starts/stops the poller via the
    ASGI lifespan and that polled samples land in the database, without
    ever touching a real network or dish."""
    settings = load_settings(data_dir=tmp_path, env={})
    settings.starlink.poll_interval_seconds = 0.01

    client = FakeStarlinkClient(samples=[make_sample() for _ in range(10)])
    app = create_app(settings, starlink_client=client, start_collector=True)

    with TestClient(app) as test_client:
        assert app.state.collector.is_running

        deadline = time.monotonic() + 2
        while client.fetch_calls == 0 and time.monotonic() < deadline:
            time.sleep(0.01)

        response = test_client.get("/api/health")
        assert response.status_code == 200

    assert not app.state.collector.is_running
    assert client.closed is True

    session = next(app.state.db.get_session())
    try:
        assert count_samples(session) >= 1
    finally:
        session.close()


def test_app_does_not_start_collector_when_disabled(tmp_path: Path) -> None:
    settings = load_settings(data_dir=tmp_path, env={})
    client = FakeStarlinkClient(samples=[make_sample()])
    app = create_app(settings, starlink_client=client, start_collector=False)

    with TestClient(app):
        assert not app.state.collector.is_running

    assert client.fetch_calls == 0
