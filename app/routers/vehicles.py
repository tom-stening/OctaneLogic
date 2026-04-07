"""OctaneLogic – vehicles router."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.energy_ledger import Vehicle
from app.schemas.energy_ledger import VehicleCreate, VehicleRead

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.post("/", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    payload: VehicleCreate,
    db: AsyncSession = Depends(get_db),
) -> VehicleRead:
    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    await db.flush()
    await db.refresh(vehicle)
    return VehicleRead.model_validate(vehicle)


@router.get("/", response_model=list[VehicleRead])
async def list_vehicles(
    owner_ref: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[VehicleRead]:
    stmt = select(Vehicle)
    if owner_ref:
        stmt = stmt.where(Vehicle.owner_ref == owner_ref)
    result = await db.execute(stmt)
    vehicles = result.scalars().all()
    return [VehicleRead.model_validate(v) for v in vehicles]


@router.get("/{vehicle_id}", response_model=VehicleRead)
async def get_vehicle(
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> VehicleRead:
    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return VehicleRead.model_validate(vehicle)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    await db.delete(vehicle)
