"""Pydantic schemas for the OctaneLogic Energy Ledger API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Vehicle
# ---------------------------------------------------------------------------

class VehicleBase(BaseModel):
    name: str
    make: str
    model: str
    year: int = Field(..., ge=1900, le=2100)
    drivetrain: str = Field(..., pattern="^(ICE|EV|HYBRID)$")
    fuel_type: Optional[str] = Field(None, pattern="^(petrol|diesel|e85|lpg)$")
    engine_displacement_cc: Optional[float] = None
    tank_capacity_l: Optional[float] = None
    obd_supported: bool = False
    battery_capacity_kwh: Optional[float] = None
    usable_capacity_kwh: Optional[float] = None
    dc_fast_charge_kw: Optional[float] = None
    ac_charge_kw: Optional[float] = None
    drag_coefficient: Optional[float] = Field(None, ge=0.1, le=1.5)
    frontal_area_m2: Optional[float] = None
    rolling_resistance: Optional[float] = Field(None, ge=0.005, le=0.05)
    kerb_weight_kg: Optional[float] = None
    regen_efficiency: Optional[float] = Field(None, ge=0.0, le=1.0)


class VehicleCreate(VehicleBase):
    owner_ref: str = Field(..., min_length=8, description="Anonymised owner token (no PII)")


class VehicleRead(VehicleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_ref: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Trip
# ---------------------------------------------------------------------------

class TripBase(BaseModel):
    name: Optional[str] = None
    distance_km: float = Field(..., gt=0)
    elevation_gain_m: Optional[float] = None
    elevation_loss_m: Optional[float] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    avg_speed_kmh: Optional[float] = None
    avg_temp_c: Optional[float] = None
    payload_kg: Optional[float] = Field(None, ge=0)
    source: str = Field("manual", pattern="^(manual|obd2|gps|api)$")


class TripCreate(TripBase):
    vehicle_id: uuid.UUID


class TripRead(TripBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vehicle_id: uuid.UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# Energy Ledger
# ---------------------------------------------------------------------------

class EnergyLedgerBase(BaseModel):
    segment_index: int = Field(0, ge=0)
    segment_km: float = Field(..., gt=0)

    # ICE
    fuel_consumed_l: Optional[float] = None
    fuel_cost_aud: Optional[float] = None
    fuel_price_per_l: Optional[float] = None
    fuel_station_id: Optional[str] = None

    # EV
    energy_consumed_wh: Optional[float] = None
    charge_cost_aud: Optional[float] = None
    charge_rate_kw: Optional[float] = None
    soc_start_pct: Optional[float] = Field(None, ge=0, le=100)
    soc_end_pct: Optional[float] = Field(None, ge=0, le=100)
    grid_price_per_kwh: Optional[float] = None

    # Hybrid
    regen_energy_wh: Optional[float] = None
    ev_distance_km: Optional[float] = None
    ice_distance_km: Optional[float] = None

    # Geometry
    avg_grade_pct: Optional[float] = None
    max_grade_pct: Optional[float] = None

    # Physics
    f_drag_n: Optional[float] = None
    f_rolling_n: Optional[float] = None
    f_slope_n: Optional[float] = None
    f_accel_n: Optional[float] = None
    predicted_wh_per_km: Optional[float] = None
    predicted_l_per_100km: Optional[float] = None


class EnergyLedgerCreate(EnergyLedgerBase):
    trip_id: uuid.UUID
    vehicle_id: uuid.UUID


class EnergyLedgerRead(EnergyLedgerBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trip_id: uuid.UUID
    vehicle_id: uuid.UUID
    recorded_at: datetime


# ---------------------------------------------------------------------------
# Fuel Price Snapshot
# ---------------------------------------------------------------------------

class FuelPriceSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    station_id: str
    station_name: Optional[str]
    suburb: Optional[str]
    postcode: Optional[str]
    fuel_type: str
    price_per_l: float
    brand: Optional[str]
    fetched_at: datetime


# ---------------------------------------------------------------------------
# Grid Price Snapshot
# ---------------------------------------------------------------------------

class GridPriceSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    region: str
    dispatch_interval: datetime
    rrp_per_mwh: float
    fetched_at: datetime


# ---------------------------------------------------------------------------
# Charge Stop
# ---------------------------------------------------------------------------

class ChargeStopRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ocm_id: int
    name: Optional[str]
    suburb: Optional[str]
    state: Optional[str]
    postcode: Optional[str]
    lat_approx: Optional[float]
    lon_approx: Optional[float]
    max_kw: Optional[float]
    connector_types: Optional[list[str]]
    cost_description: Optional[str]
    is_operational: bool
    fetched_at: datetime


# ---------------------------------------------------------------------------
# Detour Evaluation
# ---------------------------------------------------------------------------

class DetourEvaluationCreate(BaseModel):
    trip_id: uuid.UUID
    detour_km: float = Field(..., ge=0)
    detour_time_s: int = Field(..., ge=0)
    fuel_saving_aud: float
    detour_fuel_cost_aud: float
    time_value_aud: float
    station_id: Optional[str] = None


class DetourEvaluationRead(DetourEvaluationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evaluated_at: datetime
    net_saving_aud: Optional[float] = None
    recommended: Optional[bool] = None
