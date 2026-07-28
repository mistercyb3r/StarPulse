"""First-run setup: check/report whether it's done, and accept the wizard's form.

Kept deliberately small: it only touches the handful of settings the
setup wizard actually asks for (dish host, poll interval, web port), and
applies what it safely can without a restart (dish host/poll interval,
by reconfiguring the running ``StarlinkPoller``) while flagging what
can't (the web server's own port, since it's already bound).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from starpulse.api.deps import get_collector, get_db, get_settings
from starpulse.api.schemas import SetupRequest, SetupResponse, SetupStatusResponse
from starpulse.collector.poller import StarlinkPoller
from starpulse.config.settings import Settings
from starpulse.config.writer import update_config_file
from starpulse.core.setup_state import is_setup_complete, mark_setup_complete
from starpulse.logging_config import get_logger

router = APIRouter(prefix="/setup", tags=["setup"])
logger = get_logger(__name__)


@router.get("/status", response_model=SetupStatusResponse)
def get_setup_status(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> SetupStatusResponse:
    return SetupStatusResponse(
        setup_complete=is_setup_complete(db),
        dish_host=settings.starlink.dish_host,
        dish_port=settings.starlink.dish_port,
        poll_interval_seconds=settings.starlink.poll_interval_seconds,
        port=settings.server.port,
        weather_latitude=settings.weather.latitude,
        weather_longitude=settings.weather.longitude,
    )


@router.post("", response_model=SetupResponse)
def submit_setup(
    payload: SetupRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    collector: StarlinkPoller = Depends(get_collector),
    db: Session = Depends(get_db),
) -> SetupResponse:
    weather_updates: dict[str, object] = {}
    # Optional: only touch [weather] when the wizard provides a full lat/lon pair.
    # Omitting both leaves any previously configured location alone.
    if payload.weather_latitude is not None and payload.weather_longitude is not None:
        weather_updates = {
            "latitude": payload.weather_latitude,
            "longitude": payload.weather_longitude,
        }

    updates: dict[str, dict[str, object]] = {
        "starlink": {
            "dish_host": payload.dish_host,
            "poll_interval_seconds": payload.poll_interval_seconds,
        },
        "server": {"port": payload.port},
    }
    if weather_updates:
        updates["weather"] = weather_updates

    update_config_file(settings.config_file, updates)

    # Apply what can take effect immediately.
    settings.starlink.dish_host = payload.dish_host
    settings.starlink.poll_interval_seconds = payload.poll_interval_seconds
    settings.server.port = payload.port
    if payload.weather_latitude is not None and payload.weather_longitude is not None:
        settings.weather.latitude = payload.weather_latitude
        settings.weather.longitude = payload.weather_longitude

    client_factory = request.app.state.starlink_client_factory
    new_client = client_factory(payload.dish_host, settings.starlink.dish_port)
    collector.reconfigure(new_client, payload.poll_interval_seconds)

    mark_setup_complete(db)

    restart_required = payload.port != request.app.state.bound_server_port
    message = (
        "Settings saved. Restart StarPulse for the new port to take effect."
        if restart_required
        else "Settings saved."
    )
    logger.info("Setup wizard submitted (restart_required=%s)", restart_required)

    return SetupResponse(setup_complete=True, restart_required=restart_required, message=message)
