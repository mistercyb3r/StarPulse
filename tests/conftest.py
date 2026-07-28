from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from starpulse.app import create_app
from starpulse.config.settings import Settings, load_settings


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "starpulse-data"


@pytest.fixture
def settings(data_dir: Path) -> Settings:
    # env={} isolates tests from whatever STARPULSE_* variables happen to
    # be set in the host environment running the test suite.
    return load_settings(data_dir=data_dir, env={})


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    # start_collector=False: these fixtures back general API tests, which
    # shouldn't try to reach a real Starlink dish. Collector-specific
    # tests live under tests/collector/ and construct their own app.
    return create_app(settings, start_collector=False)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
