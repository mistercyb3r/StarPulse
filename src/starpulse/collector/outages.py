"""Degraded-connection detection.

Runs alongside the ``StarlinkPoller``: after every poll attempt (success
or failure), ``OutageTracker`` decides whether the connection is
currently degraded and keeps a single open ``ConnectionEvent`` row (see
``starpulse.collector.repository``) in sync with that decision, closing
it once things recover.

Kept separate from ``repository`` (pure persistence) and ``poller``
(scheduling) so the classification policy — what counts as "degraded"
— is its own small, independently testable unit.
"""

from __future__ import annotations

from datetime import datetime

from starpulse.collector import repository
from starpulse.collector.client import StarlinkSample
from starpulse.db.session import Database
from starpulse.logging_config import get_logger

logger = get_logger(__name__)

CONNECTED_STATE = "CONNECTED"

# A sample is "high packet loss" once at least half of pings in the
# dish's own reporting window were dropped, even though it still
# otherwise reports itself as connected.
HIGH_PACKET_LOSS_THRESHOLD = 0.5

REASON_DISCONNECTED = "disconnected"
REASON_HIGH_PACKET_LOSS = "high_packet_loss"
REASON_DISH_UNAVAILABLE = "dish_unavailable"


def classify_sample(sample: StarlinkSample) -> str | None:
    """Return a degraded-connection reason for ``sample``, or ``None`` if it looks healthy."""
    if sample.connection_state != CONNECTED_STATE:
        return REASON_DISCONNECTED
    if sample.ping_drop_rate is not None and sample.ping_drop_rate >= HIGH_PACKET_LOSS_THRESHOLD:
        return REASON_HIGH_PACKET_LOSS
    return None


class OutageTracker:
    """Classifies each poll result and keeps one open ``ConnectionEvent`` in sync.

    Uses its own short-lived session per call (like the poller does for
    ``save_sample``) rather than being handed one, so it stays usable
    from any thread without session-lifetime coupling to the caller.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def record_success(self, sample: StarlinkSample) -> None:
        """Update outage tracking after a successful poll (a stored sample)."""
        reason = classify_sample(sample)
        session = next(self._database.get_session())
        try:
            if reason is None:
                repository.close_open_connection_event(session, end_time=sample.timestamp)
            else:
                repository.upsert_open_connection_event(session, at=sample.timestamp, reason=reason)
        finally:
            session.close()

    def record_failure(self, at: datetime) -> None:
        """Update outage tracking after a failed poll (the dish itself was unreachable)."""
        session = next(self._database.get_session())
        try:
            repository.upsert_open_connection_event(session, at=at, reason=REASON_DISH_UNAVAILABLE)
        finally:
            session.close()
