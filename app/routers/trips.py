"""OctaneLogic – trips router."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.energy_ledger import Trip
from app.schemas.energy_ledger import TripCreate, TripRead

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post("/", response_model=TripRead, status_code=status.HTTP_201_CREATED)
async def create_trip(
    payload: TripCreate,
    db: AsyncSession = Depends(get_db),
) -> TripRead:
    trip = Trip(**payload.model_dump())
    db.add(trip)
    await db.flush()
    await db.refresh(trip)
    return TripRead.model_validate(trip)


@router.get("/", response_model=list[TripRead])
async def list_trips(
    vehicle_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[TripRead]:
    stmt = select(Trip).order_by(Trip.created_at.desc())
    if vehicle_id:
        stmt = stmt.where(Trip.vehicle_id == vehicle_id)
    result = await db.execute(stmt)
    return [TripRead.model_validate(t) for t in result.scalars().all()]


@router.get("/{trip_id}", response_model=TripRead)
async def get_trip(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TripRead:
    trip = await db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripRead.model_validate(trip)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    trip = await db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    await db.delete(trip)
