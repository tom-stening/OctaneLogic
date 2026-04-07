"""OctaneLogic – Physics Engine

Terrain-aware consumption model implementing the road-load equation:

    F_total = F_drag + F_rolling + F_slope + F_accel

Outputs are in Wh/km (EV) and L/100km (ICE), adjusted for elevation, speed
profile, vehicle mass, aerodynamics, and regenerative-braking recovery.

Reference benchmark route: Sydney → Young, NSW
Key terrain features: Blue Mountains ascent/descent, Great Dividing Range.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
AIR_DENSITY_KG_M3 = 1.225        # kg/m³ at ISA sea level, 15 °C
GRAVITY_M_S2 = 9.81               # m/s²
JOULES_PER_WH = 3_600             # J/Wh
JOULES_PER_MJ = 1_000_000         # J/MJ
PETROL_ENERGY_DENSITY_MJ_L = 34.2 # MJ/L (lower heating value, regular unleaded)
DIESEL_ENERGY_DENSITY_MJ_L = 36.9 # MJ/L
E85_ENERGY_DENSITY_MJ_L = 24.0    # MJ/L


@dataclass
class VehicleProfile:
    """Physical parameters of a single vehicle used by the physics engine."""

    # Identity
    vehicle_id: str
    drivetrain: str  # 'ICE' | 'EV' | 'HYBRID'
    fuel_type: str = "petrol"  # 'petrol' | 'diesel' | 'e85' | 'lpg'

    # Mass
    kerb_weight_kg: float = 1_500.0
    payload_kg: float = 0.0

    # Aerodynamics
    drag_coefficient: float = 0.30   # Cd  (typical mid-size sedan)
    frontal_area_m2: float = 2.30    # A   (m²)

    # Rolling resistance
    rolling_resistance: float = 0.0130  # Crr  (typical asphalt/radial tyre)

    # Powertrain efficiency
    ice_efficiency: float = 0.38     # brake thermal efficiency
    motor_efficiency: float = 0.92   # electric motor efficiency
    inverter_efficiency: float = 0.97
    battery_efficiency: float = 0.95  # round-trip charge/discharge
    regen_efficiency: float = 0.65   # fraction of kinetic energy recovered

    # Derived
    @property
    def total_mass_kg(self) -> float:
        return self.kerb_weight_kg + self.payload_kg

    @property
    def fuel_energy_density_mj_l(self) -> float:
        return {
            "diesel": DIESEL_ENERGY_DENSITY_MJ_L,
            "e85": E85_ENERGY_DENSITY_MJ_L,
        }.get(self.fuel_type, PETROL_ENERGY_DENSITY_MJ_L)

    @property
    def drivetrain_efficiency(self) -> float:
        """Combined well-to-wheel drivetrain efficiency."""
        if self.drivetrain == "EV":
            return self.motor_efficiency * self.inverter_efficiency * self.battery_efficiency
        if self.drivetrain == "HYBRID":
            return max(self.ice_efficiency, self.motor_efficiency * self.inverter_efficiency)
        return self.ice_efficiency


@dataclass
class ElevationSegment:
    """A road segment with distance and elevation data."""

    distance_m: float          # horizontal distance (metres)
    elevation_gain_m: float    # +ve = uphill
    speed_kmh: float = 80.0
    air_temp_c: float = 20.0

    @property
    def grade_fraction(self) -> float:
        """Rise-over-run grade (dimensionless)."""
        if self.distance_m == 0:
            return 0.0
        return self.elevation_gain_m / self.distance_m

    @property
    def grade_degrees(self) -> float:
        return math.degrees(math.atan(self.grade_fraction))

    @property
    def speed_m_s(self) -> float:
        return self.speed_kmh / 3.6


@dataclass
class SegmentResult:
    """Force and energy outputs for a single road segment."""

    segment: ElevationSegment
    vehicle: VehicleProfile

    # Force components (Newtons)
    f_drag_n: float = field(init=False)
    f_rolling_n: float = field(init=False)
    f_slope_n: float = field(init=False)
    f_accel_n: float = field(init=False)
    f_total_n: float = field(init=False)

    # Energy (Wh)
    traction_wh: float = field(init=False)
    regen_wh: float = field(init=False)      # energy recovered (EV/Hybrid only)
    net_wh: float = field(init=False)

    # Consumption metrics
    wh_per_km: float = field(init=False)
    l_per_100km: float | None = field(init=False)

    def __post_init__(self) -> None:
        seg = self.segment
        veh = self.vehicle

        # Correct air density for temperature
        air_density = AIR_DENSITY_KG_M3 * (288.15 / (273.15 + seg.air_temp_c))

        # --- Force components ---
        self.f_drag_n = (
            0.5
            * air_density
            * veh.drag_coefficient
            * veh.frontal_area_m2
            * seg.speed_m_s ** 2
        )
        self.f_rolling_n = (
            veh.rolling_resistance
            * veh.total_mass_kg
            * GRAVITY_M_S2
            * math.cos(math.atan(seg.grade_fraction))
        )
        self.f_slope_n = (
            veh.total_mass_kg
            * GRAVITY_M_S2
            * math.sin(math.atan(seg.grade_fraction))
        )
        # Acceleration force: treated as zero for steady-state cruise
        self.f_accel_n = 0.0

        self.f_total_n = self.f_drag_n + self.f_rolling_n + self.f_slope_n + self.f_accel_n

        # --- Energy calculation ---
        # When f_total_n > 0 the powertrain must do positive traction work.
        # When f_total_n < 0 gravity overcomes aero + rolling; the brakes (or
        # regen motor) absorb the surplus force.  We do NOT draw from the
        # battery in this case.
        if self.f_total_n > 0:
            traction_j = self.f_total_n * seg.distance_m
            self.traction_wh = traction_j / JOULES_PER_WH
            self.regen_wh = 0.0
        elif self.f_total_n < 0 and veh.drivetrain in ("EV", "HYBRID"):
            # Net braking force; regen motor recovers a fraction of it
            braking_j = abs(self.f_total_n) * seg.distance_m
            self.traction_wh = 0.0
            self.regen_wh = braking_j / JOULES_PER_WH * veh.regen_efficiency
        else:
            self.traction_wh = 0.0
            self.regen_wh = 0.0

        # net_wh is battery energy change: positive = discharge, negative = charge
        if self.traction_wh > 0:
            self.net_wh = self.traction_wh / veh.drivetrain_efficiency - self.regen_wh
        else:
            self.net_wh = -self.regen_wh  # regen charges the battery (negative)

        # Consumption metrics (use max(0,...) so wh_per_km is never negative)
        distance_km = seg.distance_m / 1_000.0
        if distance_km > 0:
            self.wh_per_km = max(0.0, self.net_wh) / distance_km
            self.l_per_100km = _wh_per_km_to_l_per_100km(
                self.wh_per_km, veh.fuel_energy_density_mj_l
            )
        else:
            self.wh_per_km = 0.0
            self.l_per_100km = None


def _wh_per_km_to_l_per_100km(wh_per_km: float, energy_density_mj_l: float) -> float:
    """Convert Wh/km to L/100km using the fuel's lower heating value.

    This is useful for ICE/Hybrid comparisons and for displaying equivalent
    fuel consumption on EV dashboards.
    """
    if wh_per_km <= 0 or energy_density_mj_l <= 0:
        return 0.0
    wh_per_100km = wh_per_km * 100.0
    mj_per_100km = wh_per_100km / 1_000.0 * 3.6  # 1 Wh = 3600 J = 0.0036 MJ
    return mj_per_100km / energy_density_mj_l


class TerrainEngine:
    """Compute terrain-aware energy consumption over a route.

    Usage::

        profile = VehicleProfile(vehicle_id="my-ev", drivetrain="EV", ...)
        engine = TerrainEngine(profile)

        segments = [
            ElevationSegment(distance_m=5000, elevation_gain_m=300, speed_kmh=60),
            ElevationSegment(distance_m=5000, elevation_gain_m=-300, speed_kmh=80),
        ]
        summary = engine.compute_route(segments)
        print(summary.total_wh_per_km)
    """

    def __init__(self, vehicle: VehicleProfile) -> None:
        self.vehicle = vehicle

    def compute_segment(self, segment: ElevationSegment) -> SegmentResult:
        """Compute forces and consumption for a single road segment."""
        return SegmentResult(segment=segment, vehicle=self.vehicle)

    def compute_route(self, segments: Sequence[ElevationSegment]) -> "RouteSummary":
        """Aggregate consumption across all segments of a route."""
        results = [self.compute_segment(s) for s in segments]
        return RouteSummary(results=results, vehicle=self.vehicle)

    def efficiency_crossover(
        self,
        segment: ElevationSegment,
        ice_profile: VehicleProfile,
        ev_profile: VehicleProfile,
    ) -> str:
        """Determine whether EV or ICE mode is more efficient for a segment.

        Used by the Hybrid logic to decide mode switching.

        Returns:
            'EV' if electric mode is more efficient, 'ICE' otherwise.
        """
        ev_result = SegmentResult(segment=segment, vehicle=ev_profile)
        ice_result = SegmentResult(segment=segment, vehicle=ice_profile)
        return "EV" if ev_result.wh_per_km <= ice_result.wh_per_km else "ICE"


@dataclass
class RouteSummary:
    """Aggregated result across all segments of a route."""

    results: list[SegmentResult]
    vehicle: VehicleProfile

    @property
    def total_distance_km(self) -> float:
        return sum(r.segment.distance_m for r in self.results) / 1_000.0

    @property
    def total_elevation_gain_m(self) -> float:
        return sum(max(0.0, r.segment.elevation_gain_m) for r in self.results)

    @property
    def total_elevation_loss_m(self) -> float:
        return sum(max(0.0, -r.segment.elevation_gain_m) for r in self.results)

    @property
    def total_net_wh(self) -> float:
        """Total net battery energy change across route.

        Positive = battery discharged; negative = battery charged (net regen).
        """
        return sum(r.net_wh for r in self.results)

    @property
    def total_regen_wh(self) -> float:
        return sum(r.regen_wh for r in self.results)

    @property
    def segment_count(self) -> int:
        return len(self.results)

    @property
    def total_wh_per_km(self) -> float:
        """Average Wh/km across the route (non-negative)."""
        if self.total_distance_km <= 0:
            return 0.0
        # Efficiency losses already applied per-segment; just average over distance
        return max(0.0, self.total_net_wh) / self.total_distance_km

    @property
    def total_l_per_100km(self) -> float | None:
        wh = self.total_wh_per_km
        if wh <= 0:
            return None
        return _wh_per_km_to_l_per_100km(wh, self.vehicle.fuel_energy_density_mj_l)

    @property
    def avg_f_total_n(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.f_total_n for r in self.results) / len(self.results)

    def to_dict(self) -> dict:
        return {
            "vehicle_id": self.vehicle.vehicle_id,
            "drivetrain": self.vehicle.drivetrain,
            "total_distance_km": round(self.total_distance_km, 2),
            "total_elevation_gain_m": round(self.total_elevation_gain_m, 1),
            "total_elevation_loss_m": round(self.total_elevation_loss_m, 1),
            "total_net_wh": round(self.total_net_wh, 2),
            "total_regen_wh": round(self.total_regen_wh, 2),
            "total_wh_per_km": round(self.total_wh_per_km, 2),
            "total_l_per_100km": (
                round(self.total_l_per_100km, 2) if self.total_l_per_100km else None
            ),
            "avg_force_total_n": round(self.avg_f_total_n, 2),
            "segment_count": self.segment_count,
        }
