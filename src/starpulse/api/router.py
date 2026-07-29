"""Aggregates all versioned/feature routers under a single /api prefix."""

from __future__ import annotations

from fastapi import APIRouter

from starpulse.api.routes import about, health, location, notifications, setup, starlink, weather

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(about.router)
api_router.include_router(starlink.router)
api_router.include_router(setup.router)
api_router.include_router(weather.router)
api_router.include_router(location.router)
api_router.include_router(notifications.router)
