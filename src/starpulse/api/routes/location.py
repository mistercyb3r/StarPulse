"""Resolved location for weather and the dashboard Location card."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from starpulse.api.deps import get_collector, get_db, get_settings
from starpulse.api.schemas import LocationResponse
from starpulse.collector.poller import StarlinkPoller
from starpulse.config.settings import Settings
from starpulse.services.geocoding import NullPlaceNameResolver, PlaceNameResolver
from starpulse.services.location import build_location_status

router = APIRouter(prefix="/location", tags=["location"])


def get_place_resolver(request: Request) -> PlaceNameResolver:
    return getattr(request.app.state, "place_resolver", None) or NullPlaceNameResolver()


@router.get("", response_model=LocationResponse)
def get_location(
    settings: Settings = Depends(get_settings),
    collector: StarlinkPoller = Depends(get_collector),
    db: Session = Depends(get_db),
    place_resolver: PlaceNameResolver = Depends(get_place_resolver),
) -> LocationResponse:
    status = build_location_status(settings, collector, db, place_resolver, persist=True)
    return LocationResponse(
        available=status.available,
        latitude=status.latitude,
        longitude=status.longitude,
        altitude_m=status.altitude_m,
        source=status.source,
        source_label=status.source_label,
        place_name=status.place_name,
        gps_valid=status.gps_valid,
        gps_enabled=status.gps_enabled,
        gps_satellites=status.gps_satellites,
        coordinates_collected=status.coordinates_collected,
        message=status.message,
    )
