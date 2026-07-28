"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from starpulse.collector.poller import StarlinkPoller
from starpulse.config.settings import Settings
from starpulse.services.weather import CachedWeatherProvider


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Generator[Session, None, None]:
    yield from request.app.state.db.get_session()


def get_collector(request: Request) -> StarlinkPoller:
    return request.app.state.collector


def get_weather_provider(request: Request) -> CachedWeatherProvider:
    return request.app.state.weather_provider
