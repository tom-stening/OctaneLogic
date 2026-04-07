"""OctaneLogic – SQLAlchemy ORM models for the Energy Ledger."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_ref = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    make = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    year = Column(SmallInteger, nullable=False)
    drivetrain = Column(
        Text,
        nullable=False,
        info={"check": "drivetrain IN ('ICE', 'EV', 'HYBRID')"},
    )

    # ICE / Hybrid
    engine_displacement_cc = Column(Numeric(6, 1))
    fuel_type = Column(Text)
    tank_capacity_l = Column(Numeric(5, 1))
    obd_supported = Column(Boolean, nullable=False, default=False)

    # EV / Hybrid battery
    battery_capacity_kwh = Column(Numeric(6, 2))
    usable_capacity_kwh = Column(Numeric(6, 2))
    dc_fast_charge_kw = Column(Numeric(6, 1))
    ac_charge_kw = Column(Numeric(5, 1))

    # Aero / rolling
    drag_coefficient = Column(Numeric(5, 3))
    frontal_area_m2 = Column(Numeric(4, 2))
    rolling_resistance = Column(Numeric(6, 4), default=0.0130)
    kerb_weight_kg = Column(Numeric(6, 1))
    regen_efficiency = Column(Numeric(4, 3))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    trips = relationship("Trip", back_populates="vehicle", cascade="all, delete-orphan")
    ledger_entries = relationship(
        "EnergyLedger", back_populates="vehicle", cascade="all, delete-orphan"
    )


class Trip(Base):
    __tablename__ = "trips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehicle_id = Column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(Text)
    origin_enc = Column(BYTEA)
    destination_enc = Column(BYTEA)
    distance_km = Column(Numeric(8, 2), nullable=False)
    elevation_gain_m = Column(Numeric(8, 1))
    elevation_loss_m = Column(Numeric(8, 1))
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    avg_speed_kmh = Column(Numeric(5, 1))
    avg_temp_c = Column(Numeric(4, 1))
    payload_kg = Column(Numeric(6, 1), default=0)
    source = Column(Text, nullable=False, default="manual")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    vehicle = relationship("Vehicle", back_populates="trips")
    ledger_entries = relationship(
        "EnergyLedger", back_populates="trip", cascade="all, delete-orphan"
    )
    obd_readings = relationship(
        "OBDReading", back_populates="trip", cascade="all, delete-orphan"
    )
    detour_evaluations = relationship(
        "DetourEvaluation", back_populates="trip", cascade="all, delete-orphan"
    )


class EnergyLedger(Base):
    __tablename__ = "energy_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id = Column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )
    segment_index = Column(SmallInteger, nullable=False, default=0)
    segment_km = Column(Numeric(8, 3), nullable=False)

    # ICE
    fuel_consumed_l = Column(Numeric(8, 3))
    fuel_cost_aud = Column(Numeric(8, 4))
    fuel_price_per_l = Column(Numeric(6, 4))
    fuel_station_id = Column(Text)

    # EV
    energy_consumed_wh = Column(Numeric(10, 2))
    charge_cost_aud = Column(Numeric(8, 4))
    charge_rate_kw = Column(Numeric(6, 2))
    soc_start_pct = Column(Numeric(5, 2))
    soc_end_pct = Column(Numeric(5, 2))
    grid_price_per_kwh = Column(Numeric(7, 5))

    # Hybrid
    regen_energy_wh = Column(Numeric(10, 2))
    ev_distance_km = Column(Numeric(8, 2))
    ice_distance_km = Column(Numeric(8, 2))

    # Segment geometry
    avg_grade_pct = Column(Numeric(5, 2))
    max_grade_pct = Column(Numeric(5, 2))

    # Physics engine
    f_drag_n = Column(Numeric(8, 2))
    f_rolling_n = Column(Numeric(8, 2))
    f_slope_n = Column(Numeric(8, 2))
    f_accel_n = Column(Numeric(8, 2))
    predicted_wh_per_km = Column(Numeric(8, 2))
    predicted_l_per_100km = Column(Numeric(6, 3))

    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    trip = relationship("Trip", back_populates="ledger_entries")
    vehicle = relationship("Vehicle", back_populates="ledger_entries")


class FuelPriceSnapshot(Base):
    __tablename__ = "fuel_price_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    station_id = Column(Text, nullable=False)
    station_name = Column(Text)
    suburb = Column(Text)
    postcode = Column(String(4))
    fuel_type = Column(Text, nullable=False)
    price_per_l = Column(Numeric(6, 3), nullable=False)
    brand = Column(Text)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GridPriceSnapshot(Base):
    __tablename__ = "grid_price_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region = Column(Text, nullable=False)
    dispatch_interval = Column(DateTime(timezone=True), nullable=False)
    rrp_per_mwh = Column(Numeric(10, 4), nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("region", "dispatch_interval"),)


class ChargeStop(Base):
    __tablename__ = "charge_stops"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ocm_id = Column(Integer, nullable=False, unique=True)
    name = Column(Text)
    suburb = Column(Text)
    state = Column(Text)
    postcode = Column(String(4))
    lat_approx = Column(Numeric(6, 3))
    lon_approx = Column(Numeric(7, 3))
    max_kw = Column(Numeric(6, 1))
    connector_types = Column(ARRAY(Text))
    cost_description = Column(Text)
    is_operational = Column(Boolean, default=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OBDReading(Base):
    __tablename__ = "obd_readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    vehicle_id = Column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    pid = Column(String(5), nullable=False)
    raw_value = Column(Numeric(10, 4))
    unit = Column(Text)
    fuel_rate_lph = Column(Numeric(6, 3))
    speed_kmh = Column(Numeric(5, 1))
    coolant_temp_c = Column(Numeric(5, 1))

    trip = relationship("Trip", back_populates="obd_readings")


class DetourEvaluation(Base):
    __tablename__ = "detour_evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    detour_km = Column(Numeric(7, 2), nullable=False)
    detour_time_s = Column(Integer, nullable=False)
    fuel_saving_aud = Column(Numeric(8, 4), nullable=False)
    detour_fuel_cost_aud = Column(Numeric(8, 4), nullable=False)
    time_value_aud = Column(Numeric(8, 4), nullable=False)
    station_id = Column(Text)

    trip = relationship("Trip", back_populates="detour_evaluations")
