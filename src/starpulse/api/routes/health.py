"""Health/liveness endpoint.

Useful for confirming the server is up and the database is reachable,
and as the first real endpoint a new frontend or Docker healthcheck can
point at.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from starpulse import __version__
from starpulse.api.deps import get_collector, get_db
from starpulse.collector.poller import StarlinkPoller
from starpulse.core.setup_state import is_setup_complete

router = APIRouter(tags=["health"])

_start_time = time.monotonic()


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    setup_complete: bool
    starlink_connected: bool | None = Field(
        description="Whether the most recent dish poll succeeded. Null until the first poll attempt."
    )


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Session = Depends(get_db),
    collector: StarlinkPoller = Depends(get_collector),
) -> HealthResponse:
    db.execute(select(1))  # confirms the database connection is alive
    return HealthResponse(
        status="ok",
        version=__version__,
        uptime_seconds=round(time.monotonic() - _start_time, 2),
        setup_complete=is_setup_complete(db),
        starlink_connected=collector.last_poll_ok,
    )
