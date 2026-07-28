"""Aggregates all versioned/feature routers under a single /api prefix."""

from __future__ import annotations

from fastapi import APIRouter

from starpulse.api.routes import health, setup, starlink

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(starlink.router)
api_router.include_router(setup.router)
