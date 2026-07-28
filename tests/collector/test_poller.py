from __future__ import annotations

import time
from pathlib import Path

import pytest

from starpulse.collector.outages import OutageTracker
from starpulse.collector.poller import StarlinkPoller
from starpulse.collector.repository import get_open_connection_event
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


def test_poll_once_opens_outage_event_on_disconnect(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    client = FakeStarlinkClient(samples=[make_sample(connection_state="SEARCHING")])
    tracker = OutageTracker(db)
    poller = StarlinkPoller(client, db, interval_seconds=999, outage_tracker=tracker)

    poller.poll_once()

    session = next(db.get_session())
    try:
        open_event = get_open_connection_event(session)
        assert open_event is not None
        assert open_event.reason == "disconnected"
    finally:
        session.close()


def test_poll_once_closes_outage_event_on_recovery(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    client = FakeStarlinkClient(
        samples=[make_sample(connection_state="SEARCHING"), make_sample(connection_state="CONNECTED")]
    )
    tracker = OutageTracker(db)
    poller = StarlinkPoller(client, db, interval_seconds=999, outage_tracker=tracker)

    poller.poll_once()
    poller.poll_once()

    session = next(db.get_session())
    try:
        assert get_open_connection_event(session) is None
    finally:
        session.close()


def test_poll_once_opens_outage_event_when_dish_unavailable(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    client = FakeStarlinkClient(samples=[])
    tracker = OutageTracker(db)
    poller = StarlinkPoller(client, db, interval_seconds=999, outage_tracker=tracker)

    poller.poll_once()

    session = next(db.get_session())
    try:
        open_event = get_open_connection_event(session)
        assert open_event is not None
        assert open_event.reason == "dish_unavailable"
    finally:
        session.close()


def test_poll_once_without_outage_tracker_still_works(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    client = FakeStarlinkClient(samples=[make_sample()])
    poller = StarlinkPoller(client, db, interval_seconds=999)

    row = poller.poll_once()

    assert row is not None


def test_poll_once_stores_and_refreshes_dish_location(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    client = FakeStarlinkClient(samples=[make_sample(), make_sample()], location=(51.5, -0.1))
    poller = StarlinkPoller(client, db, interval_seconds=999)

    assert poller.dish_location is None

    row = poller.poll_once()
    assert poller.dish_location == (51.5, -0.1)
    assert client.location_calls == 1
    assert row is not None
    assert row.latitude == pytest.approx(51.5)
    assert row.longitude == pytest.approx(-0.1)

    poller.poll_once()
    # Location is refreshed on every successful poll so telemetry stays current.
    assert client.location_calls == 2
    assert poller.dish_location == (51.5, -0.1)


def test_poll_once_keeps_last_known_location_when_refresh_fails(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    client = FakeStarlinkClient(samples=[make_sample(), make_sample()], location=(51.5, -0.1))
    poller = StarlinkPoller(client, db, interval_seconds=999)

    poller.poll_once()
    client._location = None
    row = poller.poll_once()

    assert poller.dish_location == (51.5, -0.1)
    assert row is not None
    assert row.latitude == pytest.approx(51.5)
    assert row.longitude == pytest.approx(-0.1)


def test_poll_once_tolerates_client_without_fetch_location(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()

    class MinimalClient:
        def fetch_sample(self):
            return make_sample()

        def close(self) -> None:
            pass

    poller = StarlinkPoller(MinimalClient(), db, interval_seconds=999)

    row = poller.poll_once()

    assert row is not None
    assert poller.dish_location is None
