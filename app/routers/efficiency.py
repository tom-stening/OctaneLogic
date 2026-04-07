"""OctaneLogic – efficiency router.

Exposes:
* Energy ledger CRUD
* Detour Delta evaluation
* Physics engine predictions
* Fuel price search (FuelCheck)
* Grid price / charging windows (AEMO)
* EV charge stop search (Open Charge Map)
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.aemo import AEMOClient
from app.api.fuelcheck import FuelCheckClient
from app.api.open_charge_map import OpenChargeMapClient
from app.config import settings
from app.database import get_db
from app.models.energy_ledger import DetourEvaluation, EnergyLedger
from app.physics.terrain_engine import ElevationSegment, TerrainEngine, VehicleProfile
from app.schemas.energy_ledger import (
    DetourEvaluationCreate,
    DetourEvaluationRead,
    EnergyLedgerCreate,
    EnergyLedgerRead,
)

router = APIRouter(prefix="/efficiency", tags=["efficiency"])


# ---------------------------------------------------------------------------
# Energy Ledger
# ---------------------------------------------------------------------------

@router.post("/ledger", response_model=EnergyLedgerRead, status_code=status.HTTP_201_CREATED)
async def create_ledger_entry(
    payload: EnergyLedgerCreate,
    db: AsyncSession = Depends(get_db),
) -> EnergyLedgerRead:
    entry = EnergyLedger(**payload.model_dump())
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return EnergyLedgerRead.model_validate(entry)


@router.get("/ledger", response_model=list[EnergyLedgerRead])
async def list_ledger_entries(
    trip_id: uuid.UUID | None = None,
    vehicle_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[EnergyLedgerRead]:
    stmt = select(EnergyLedger).order_by(EnergyLedger.recorded_at.desc())
    if trip_id:
        stmt = stmt.where(EnergyLedger.trip_id == trip_id)
    if vehicle_id:
        stmt = stmt.where(EnergyLedger.vehicle_id == vehicle_id)
    result = await db.execute(stmt)
    return [EnergyLedgerRead.model_validate(e) for e in result.scalars().all()]


# ---------------------------------------------------------------------------
# Physics Engine prediction
# ---------------------------------------------------------------------------

@router.post("/predict")
async def predict_consumption(
    vehicle_id: str,
    drivetrain: str = Query("ICE", pattern="^(ICE|EV|HYBRID)$"),
    kerb_weight_kg: float = Query(1500.0, gt=0),
    drag_coefficient: float = Query(0.30, gt=0),
    frontal_area_m2: float = Query(2.30, gt=0),
    rolling_resistance: float = Query(0.0130, gt=0),
    regen_efficiency: float = Query(0.65, ge=0, le=1),
    segments: list[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Run the terrain physics engine for a list of route segments.

    Each segment in *segments* should be a JSON object with:
    ``distance_m``, ``elevation_gain_m``, ``speed_kmh``, ``air_temp_c``.
    """
    if not segments:
        raise HTTPException(status_code=400, detail="At least one segment is required")

    profile = VehicleProfile(
        vehicle_id=vehicle_id,
        drivetrain=drivetrain,
        kerb_weight_kg=kerb_weight_kg,
        drag_coefficient=drag_coefficient,
        frontal_area_m2=frontal_area_m2,
        rolling_resistance=rolling_resistance,
        regen_efficiency=regen_efficiency,
    )
    engine = TerrainEngine(profile)

    seg_objects = [
        ElevationSegment(
            distance_m=float(s.get("distance_m", 1000)),
            elevation_gain_m=float(s.get("elevation_gain_m", 0)),
            speed_kmh=float(s.get("speed_kmh", 80)),
            air_temp_c=float(s.get("air_temp_c", settings.default_air_temp_c)),
        )
        for s in segments
    ]

    summary = engine.compute_route(seg_objects)
    return summary.to_dict()


# ---------------------------------------------------------------------------
# Detour Delta
# ---------------------------------------------------------------------------

@router.post(
    "/detour-delta",
    response_model=DetourEvaluationRead,
    status_code=status.HTTP_201_CREATED,
)
async def evaluate_detour(
    payload: DetourEvaluationCreate,
    db: AsyncSession = Depends(get_db),
) -> DetourEvaluationRead:
    """Evaluate whether a fuel-price detour is worth the extra distance and time."""
    evaluation = DetourEvaluation(**payload.model_dump())
    db.add(evaluation)
    await db.flush()
    await db.refresh(evaluation)
    # Compute derived fields for response (mirrors generated columns in SQL)
    net_saving = (
        payload.fuel_saving_aud
        - payload.detour_fuel_cost_aud
        - payload.time_value_aud
    )
    result = DetourEvaluationRead.model_validate(evaluation)
    result.net_saving_aud = round(net_saving, 4)
    result.recommended = net_saving > 0
    return result


# ---------------------------------------------------------------------------
# FuelCheck NSW
# ---------------------------------------------------------------------------

@router.get("/fuel/prices")
async def get_fuel_prices(
    postcode: str = Query(..., min_length=4, max_length=4, pattern="^[0-9]{4}$"),
    fuel_type: str = Query("P95"),
    radius_km: float = Query(5.0, gt=0, le=50),
) -> list[dict[str, Any]]:
    """Return fuel prices near a postcode from FuelCheck NSW.

    Only a postcode (not precise GPS coordinates) is sent to the FuelCheck API.
    """
    client = FuelCheckClient(api_key=settings.fuelcheck_api_key)
    return await client.get_prices_by_postcode(postcode, fuel_type, radius_km)


@router.get("/fuel/cheapest-along-route")
async def cheapest_fuel_along_route(
    postcodes: list[str] = Query(...),
    fuel_type: str = Query("P95"),
) -> dict[str, Any] | None:
    """Find the cheapest fuel station along a list of postcodes."""
    client = FuelCheckClient(api_key=settings.fuelcheck_api_key)
    result = await client.cheapest_along_route(postcodes, fuel_type)
    if result is None:
        raise HTTPException(status_code=404, detail="No fuel stations found along route")
    return result


# ---------------------------------------------------------------------------
# AEMO Grid Pricing
# ---------------------------------------------------------------------------

@router.get("/grid/current-price")
async def get_current_grid_price(
    region: str = Query("NSW1"),
) -> dict[str, Any]:
    """Fetch the current NEM dispatch price for home EV charging decisions."""
    client = AEMOClient(region=region)
    return await client.get_current_price()


@router.get("/grid/cheapest-windows")
async def get_cheapest_charge_windows(
    region: str = Query("NSW1"),
    hours_ahead: int = Query(12, ge=1, le=48),
    required_hours: int = Query(4, ge=1, le=12),
) -> list[dict[str, Any]]:
    """Return cheapest dispatch windows for EV home charging."""
    client = AEMOClient(region=region)
    return await client.get_cheapest_windows(hours_ahead, required_hours)


# ---------------------------------------------------------------------------
# Open Charge Map
# ---------------------------------------------------------------------------

@router.get("/charge-stops")
async def get_charge_stops(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10.0, gt=0, le=100),
    min_kw: float | None = Query(None, ge=1),
) -> list[dict[str, Any]]:
    """Find EV charging stops near a route waypoint."""
    client = OpenChargeMapClient(api_key=settings.ocm_api_key)
    return await client.get_stops_near(lat, lon, radius_km=radius_km, min_kw=min_kw)
