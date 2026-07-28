"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from starpulse import __version__
from starpulse.api.router import api_router
from starpulse.collector.client import GrpcStarlinkClient, StarlinkClient
from starpulse.collector.poller import StarlinkPoller
from starpulse.config.settings import Settings, load_settings
from starpulse.core.paths import resolve_db_path
from starpulse.db.session import Database
from starpulse.logging_config import configure_logging, get_logger

StarlinkClientFactory = Callable[[str, int], StarlinkClient]

logger = get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    starlink_client: StarlinkClient | None = None,
    start_collector: bool = True,
) -> FastAPI:
    """Build and return a configured FastAPI application.

    Passing ``settings`` explicitly (e.g. pointed at a temp directory) is
    the main seam tests use to avoid touching real config/data files.
    ``starlink_client`` lets callers (mainly tests) inject a fake client
    instead of connecting to a real dish; ``start_collector=False`` skips
    starting the background poller entirely, e.g. for tests that only
    care about the HTTP API.
    """
    settings = settings or load_settings()
    configure_logging(level=settings.logging.level, log_file=settings.logging.file or None)

    logger.info("Starting StarPulse v%s", __version__)
    logger.debug("Using data directory: %s", settings.data_dir)

    db_path = resolve_db_path(settings.data_dir, settings.database.path)
    database = Database(db_path)
    database.init_db()

    # When a fake client is injected (tests), reconfiguring the collector
    # (e.g. via the setup wizard) should keep reusing that same fake
    # rather than trying to open a real gRPC connection.
    client_factory: StarlinkClientFactory = (
        (lambda _host, _port: starlink_client) if starlink_client is not None else GrpcStarlinkClient
    )
    client = client_factory(settings.starlink.dish_host, settings.starlink.dish_port)
    collector = StarlinkPoller(client, database, settings.starlink.poll_interval_seconds)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if start_collector:
            collector.start()
        try:
            yield
        finally:
            if start_collector:
                collector.stop()
            logger.info("Shutting down StarPulse")
            database.dispose()

    app = FastAPI(
        title="StarPulse",
        description="Self-hosted local dashboard for Starlink telemetry.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = database
    app.state.collector = collector
    app.state.starlink_client_factory = client_factory
    # The port actually bound by the running server process, captured
    # before any setup-wizard update mutates settings.server.port — used
    # to tell the caller whether a restart is needed for a port change.
    app.state.bound_server_port = settings.server.port

    # The frontend is a separate app (its own dev server/port, or a static
    # build served from elsewhere), and there are no user accounts to
    # protect a session for. Allowing any local origin keeps that
    # separation possible without requiring a reverse proxy.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    return app
