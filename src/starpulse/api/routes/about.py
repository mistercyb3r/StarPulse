"""About / system information for the dashboard About page."""

from __future__ import annotations

import platform
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from starpulse import __version__
from starpulse.api.deps import get_collector, get_db, get_settings
from starpulse.api.schemas import AboutResponse
from starpulse.collector.poller import StarlinkPoller
from starpulse.config.settings import Settings
from starpulse.core.paths import resolve_db_path
from starpulse.core.setup_state import is_setup_complete

router = APIRouter(tags=["about"])

_start_time = time.monotonic()

GITHUB_URL = "https://github.com/mistercyb3r/StarPulse"

CREDITS = [
    "Built for self-hosted Starlink monitoring.",
    "Uses starlink-grpc-core for dish telemetry.",
    "Weather data via Open-Meteo (no API key).",
    "Inspired by local-first tools like Home Assistant.",
]


@router.get("/about", response_model=AboutResponse)
def get_about(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    collector: StarlinkPoller = Depends(get_collector),
) -> AboutResponse:
    db.execute(select(1))
    db_path = resolve_db_path(settings.data_dir, settings.database.path)
    return AboutResponse(
        name="StarPulse",
        version=__version__,
        description="Self-hosted local Starlink telemetry dashboard.",
        github_url=GITHUB_URL,
        uptime_seconds=round(time.monotonic() - _start_time, 2),
        setup_complete=is_setup_complete(db),
        starlink_connected=collector.last_poll_ok,
        database_path=str(Path(db_path)),
        data_dir=str(settings.data_dir),
        python_version=sys.version.split()[0],
        platform=f"{platform.system()} {platform.release()}",
        credits=CREDITS,
    )
