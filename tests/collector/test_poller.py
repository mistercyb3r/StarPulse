from __future__ import annotations

import time
from pathlib import Path

from starpulse.collector.poller import StarlinkPoller
from starpulse.db.session import Database

from tests.collector.factories import FakeStarlinkClient, make_sample


def test_poll_once_stores_sample_and_returns_row(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    client = FakeStarlinkClient(samples=[make_sample()])
    poller = StarlinkPoller(client, db, interval_seconds=999)

    row = poller.poll_once()

    assert row is not None
    assert row.id is not None
    assert client.fetch_calls == 1


def test_poll_once_returns_none_and_calls_on_error_when_unavailable(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    client = FakeStarlinkClient(samples=[])
    errors: list[Exception] = []
    poller = StarlinkPoller(client, db, interval_seconds=999, on_error=errors.append)

    row = poller.poll_once()

    assert row is None
    assert len(errors) == 1


def test_start_and_stop_polls_in_background(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    samples = [make_sample() for _ in range(5)]
    client = FakeStarlinkClient(samples=samples)
    poller = StarlinkPoller(client, db, interval_seconds=0.01)

    poller.start()
    assert poller.is_running

    deadline = time.monotonic() + 2
    while client.fetch_calls == 0 and time.monotonic() < deadline:
        time.sleep(0.01)

    poller.stop(timeout=2)

    assert not poller.is_running
    assert client.closed is True
    assert client.fetch_calls >= 1


def test_start_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    client = FakeStarlinkClient(samples=[make_sample()])
    poller = StarlinkPoller(client, db, interval_seconds=999)

    poller.start()
    first_thread = poller._thread
    poller.start()

    assert poller._thread is first_thread

    poller.stop(timeout=2)


def test_last_poll_ok_tracks_success_and_failure(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    client = FakeStarlinkClient(samples=[make_sample()])
    poller = StarlinkPoller(client, db, interval_seconds=999)

    assert poller.last_poll_ok is None

    poller.poll_once()
    assert poller.last_poll_ok is True

    poller.poll_once()  # no more queued samples -> unavailable
    assert poller.last_poll_ok is False


def test_reconfigure_while_stopped_swaps_client_and_closes_old_one(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    old_client = FakeStarlinkClient(samples=[make_sample()])
    poller = StarlinkPoller(old_client, db, interval_seconds=999)

    new_client = FakeStarlinkClient(samples=[make_sample()])
    poller.reconfigure(new_client, interval_seconds=1.5)

    assert old_client.closed is True
    assert poller._client is new_client
    assert poller._interval_seconds == 1.5
    assert not poller.is_running


def test_reconfigure_while_running_restarts_with_new_client(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    old_client = FakeStarlinkClient(samples=[make_sample() for _ in range(5)])
    poller = StarlinkPoller(old_client, db, interval_seconds=0.01)
    poller.start()

    deadline = time.monotonic() + 2
    while old_client.fetch_calls == 0 and time.monotonic() < deadline:
        time.sleep(0.01)

    new_client = FakeStarlinkClient(samples=[make_sample() for _ in range(5)])
    poller.reconfigure(new_client, interval_seconds=0.01)

    assert poller.is_running
    assert old_client.closed is True

    deadline = time.monotonic() + 2
    while new_client.fetch_calls == 0 and time.monotonic() < deadline:
        time.sleep(0.01)

    poller.stop(timeout=2)
    assert new_client.fetch_calls >= 1
