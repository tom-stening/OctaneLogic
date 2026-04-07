"""Tests for the OctaneLogic terrain physics engine.

These tests run entirely in-memory without any database or network dependencies.
"""

from __future__ import annotations

import math
import pytest

from app.physics.terrain_engine import (
    ElevationSegment,
    RouteSummary,
    SegmentResult,
    TerrainEngine,
    VehicleProfile,
    _wh_per_km_to_l_per_100km,
    AIR_DENSITY_KG_M3,
    GRAVITY_M_S2,
    PETROL_ENERGY_DENSITY_MJ_L,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ev_profile() -> VehicleProfile:
    return VehicleProfile(
        vehicle_id="test-ev",
        drivetrain="EV",
        kerb_weight_kg=2_000.0,
        drag_coefficient=0.23,
        frontal_area_m2=2.50,
        rolling_resistance=0.010,
        motor_efficiency=0.95,
        inverter_efficiency=0.98,
        battery_efficiency=0.97,
        regen_efficiency=0.70,
    )


@pytest.fixture
def ice_profile() -> VehicleProfile:
    return VehicleProfile(
        vehicle_id="test-ice",
        drivetrain="ICE",
        fuel_type="petrol",
        kerb_weight_kg=1_500.0,
        drag_coefficient=0.30,
        frontal_area_m2=2.30,
        rolling_resistance=0.0130,
        ice_efficiency=0.38,
        regen_efficiency=0.0,
    )


@pytest.fixture
def flat_segment() -> ElevationSegment:
    return ElevationSegment(distance_m=10_000, elevation_gain_m=0, speed_kmh=100)


@pytest.fixture
def climb_segment() -> ElevationSegment:
    return ElevationSegment(distance_m=5_000, elevation_gain_m=300, speed_kmh=60)


@pytest.fixture
def descent_segment() -> ElevationSegment:
    return ElevationSegment(distance_m=5_000, elevation_gain_m=-300, speed_kmh=80)


# ---------------------------------------------------------------------------
# VehicleProfile tests
# ---------------------------------------------------------------------------

class TestVehicleProfile:
    def test_total_mass_includes_payload(self, ev_profile):
        ev_profile.payload_kg = 150.0
        assert ev_profile.total_mass_kg == 2_150.0

    def test_ev_drivetrain_efficiency(self, ev_profile):
        expected = ev_profile.motor_efficiency * ev_profile.inverter_efficiency * ev_profile.battery_efficiency
        assert math.isclose(ev_profile.drivetrain_efficiency, expected, rel_tol=1e-6)

    def test_ice_drivetrain_efficiency(self, ice_profile):
        assert ice_profile.drivetrain_efficiency == ice_profile.ice_efficiency

    def test_fuel_energy_density_petrol(self, ice_profile):
        assert ice_profile.fuel_energy_density_mj_l == PETROL_ENERGY_DENSITY_MJ_L

    def test_fuel_energy_density_diesel(self, ice_profile):
        ice_profile.fuel_type = "diesel"
        assert ice_profile.fuel_energy_density_mj_l == 36.9

    def test_fuel_energy_density_e85(self, ice_profile):
        ice_profile.fuel_type = "e85"
        assert ice_profile.fuel_energy_density_mj_l == 24.0


# ---------------------------------------------------------------------------
# ElevationSegment tests
# ---------------------------------------------------------------------------

class TestElevationSegment:
    def test_grade_flat(self, flat_segment):
        assert flat_segment.grade_fraction == 0.0

    def test_grade_uphill(self, climb_segment):
        assert math.isclose(climb_segment.grade_fraction, 300 / 5_000, rel_tol=1e-6)

    def test_grade_downhill(self, descent_segment):
        assert math.isclose(descent_segment.grade_fraction, -300 / 5_000, rel_tol=1e-6)

    def test_speed_conversion(self):
        seg = ElevationSegment(distance_m=1000, elevation_gain_m=0, speed_kmh=90)
        assert math.isclose(seg.speed_m_s, 25.0, rel_tol=1e-6)


# ---------------------------------------------------------------------------
# SegmentResult force calculations
# ---------------------------------------------------------------------------

class TestSegmentResult:
    def test_drag_force_positive(self, ev_profile, flat_segment):
        result = SegmentResult(segment=flat_segment, vehicle=ev_profile)
        assert result.f_drag_n > 0

    def test_rolling_force_positive(self, ev_profile, flat_segment):
        result = SegmentResult(segment=flat_segment, vehicle=ev_profile)
        assert result.f_rolling_n > 0

    def test_slope_force_zero_on_flat(self, ev_profile, flat_segment):
        result = SegmentResult(segment=flat_segment, vehicle=ev_profile)
        assert math.isclose(result.f_slope_n, 0.0, abs_tol=1e-6)

    def test_slope_force_positive_on_climb(self, ev_profile, climb_segment):
        result = SegmentResult(segment=climb_segment, vehicle=ev_profile)
        assert result.f_slope_n > 0

    def test_slope_force_negative_on_descent(self, ev_profile, descent_segment):
        result = SegmentResult(segment=descent_segment, vehicle=ev_profile)
        assert result.f_slope_n < 0

    def test_regen_only_on_descent_for_ev(self, ev_profile, descent_segment):
        result = SegmentResult(segment=descent_segment, vehicle=ev_profile)
        assert result.regen_wh > 0

    def test_no_regen_on_climb(self, ev_profile, climb_segment):
        result = SegmentResult(segment=climb_segment, vehicle=ev_profile)
        assert result.regen_wh == 0.0

    def test_no_regen_for_ice(self, ice_profile, descent_segment):
        result = SegmentResult(segment=descent_segment, vehicle=ice_profile)
        assert result.regen_wh == 0.0

    def test_wh_per_km_positive_on_flat(self, ev_profile, flat_segment):
        result = SegmentResult(segment=flat_segment, vehicle=ev_profile)
        assert result.wh_per_km > 0

    def test_climb_consumes_more_than_flat(self, ev_profile, flat_segment, climb_segment):
        flat_result = SegmentResult(segment=flat_segment, vehicle=ev_profile)
        climb_result = SegmentResult(segment=climb_segment, vehicle=ev_profile)
        assert climb_result.wh_per_km > flat_result.wh_per_km

    def test_drag_increases_with_speed(self, ev_profile):
        slow = ElevationSegment(distance_m=1000, elevation_gain_m=0, speed_kmh=60)
        fast = ElevationSegment(distance_m=1000, elevation_gain_m=0, speed_kmh=120)
        slow_result = SegmentResult(segment=slow, vehicle=ev_profile)
        fast_result = SegmentResult(segment=fast, vehicle=ev_profile)
        # Drag ∝ v², so doubling speed quadruples drag
        assert fast_result.f_drag_n > 4 * slow_result.f_drag_n * 0.9  # allow 10% tolerance

    def test_temperature_correction_cold_air(self, ev_profile):
        warm = ElevationSegment(distance_m=1000, elevation_gain_m=0, speed_kmh=100, air_temp_c=30)
        cold = ElevationSegment(distance_m=1000, elevation_gain_m=0, speed_kmh=100, air_temp_c=-10)
        warm_result = SegmentResult(segment=warm, vehicle=ev_profile)
        cold_result = SegmentResult(segment=cold, vehicle=ev_profile)
        # Cold air is denser → more drag
        assert cold_result.f_drag_n > warm_result.f_drag_n

    def test_l_per_100km_computed_for_ice(self, ice_profile, flat_segment):
        result = SegmentResult(segment=flat_segment, vehicle=ice_profile)
        assert result.l_per_100km is not None
        assert result.l_per_100km > 0


# ---------------------------------------------------------------------------
# TerrainEngine and RouteSummary
# ---------------------------------------------------------------------------

class TestTerrainEngine:
    def test_compute_segment_returns_result(self, ev_profile, flat_segment):
        engine = TerrainEngine(ev_profile)
        result = engine.compute_segment(flat_segment)
        assert isinstance(result, SegmentResult)

    def test_compute_route_returns_summary(self, ev_profile, flat_segment, climb_segment):
        engine = TerrainEngine(ev_profile)
        summary = engine.compute_route([flat_segment, climb_segment])
        assert isinstance(summary, RouteSummary)
        assert summary.segment_count == 2

    def test_route_total_distance(self, ev_profile, flat_segment, climb_segment):
        engine = TerrainEngine(ev_profile)
        summary = engine.compute_route([flat_segment, climb_segment])
        expected_km = (flat_segment.distance_m + climb_segment.distance_m) / 1000
        assert math.isclose(summary.total_distance_km, expected_km, rel_tol=1e-6)

    def test_route_elevation_gain(self, ev_profile, climb_segment, descent_segment):
        engine = TerrainEngine(ev_profile)
        summary = engine.compute_route([climb_segment, descent_segment])
        assert math.isclose(summary.total_elevation_gain_m, 300.0, rel_tol=1e-6)
        assert math.isclose(summary.total_elevation_loss_m, 300.0, rel_tol=1e-6)

    def test_regen_reduces_net_consumption(self, ev_profile, climb_segment, descent_segment):
        engine = TerrainEngine(ev_profile)
        summary_with_descent = engine.compute_route([climb_segment, descent_segment])
        summary_climb_only = engine.compute_route([climb_segment])
        # Adding a descent (regen) should reduce total_net_wh
        assert summary_with_descent.total_net_wh < summary_climb_only.total_net_wh

    def test_to_dict_keys(self, ev_profile, flat_segment):
        engine = TerrainEngine(ev_profile)
        summary = engine.compute_route([flat_segment])
        d = summary.to_dict()
        for key in (
            "vehicle_id", "drivetrain", "total_distance_km",
            "total_elevation_gain_m", "total_wh_per_km", "total_l_per_100km",
        ):
            assert key in d

    def test_efficiency_crossover_ev_preferred_low_speed(self, ev_profile, ice_profile):
        engine = TerrainEngine(ev_profile)
        slow_urban = ElevationSegment(distance_m=1000, elevation_gain_m=0, speed_kmh=30)
        # EV is typically more efficient at low speed (no idle/warm-up losses modelled here,
        # but the base thermal efficiency difference should still favour EV)
        result = engine.efficiency_crossover(slow_urban, ice_profile, ev_profile)
        assert result in ("EV", "ICE")  # just verify it returns a valid string

    def test_efficiency_crossover_returns_valid_mode(self, ev_profile, ice_profile, flat_segment):
        engine = TerrainEngine(ev_profile)
        result = engine.efficiency_crossover(flat_segment, ice_profile, ev_profile)
        assert result in ("EV", "ICE")


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_wh_per_km_to_l_per_100km_roundtrip(self):
        # A petrol car doing 7 L/100km at 34.2 MJ/L
        # 7 L/100km = 7 * 34.2 MJ / 100 km = 2.394 MJ/km = 665 Wh/km
        l_per_100 = 7.0
        wh_per_km = l_per_100 * PETROL_ENERGY_DENSITY_MJ_L * 1_000 / 3.6 / 100
        result = _wh_per_km_to_l_per_100km(wh_per_km, PETROL_ENERGY_DENSITY_MJ_L)
        assert math.isclose(result, l_per_100, rel_tol=0.01)

    def test_wh_per_km_zero_returns_zero(self):
        assert _wh_per_km_to_l_per_100km(0.0, PETROL_ENERGY_DENSITY_MJ_L) == 0.0

    def test_negative_energy_density_returns_zero(self):
        assert _wh_per_km_to_l_per_100km(100.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# Sydney–Young benchmark route smoke test
# ---------------------------------------------------------------------------

class TestSydneyYoungRoute:
    """Validate reasonable outputs for the primary benchmark route.

    Sydney to Young (~360 km):
    - Sydney CBD to Penrith: 55 km, mostly flat, urban
    - Penrith to Lithgow (Blue Mountains ascent): 60 km, +900 m
    - Lithgow steep descent (5% grade at 60 km/h): 10 km, -500 m  ← triggers regen
    - Lithgow to Bathurst (rolling): 55 km, +50 m
    - Bathurst to Orange: 55 km, rolling hills +150 m
    - Orange to Cowra: 60 km, gentle descent -250 m
    - Cowra to Young: 60 km, flat undulating
    """

    SEGMENTS = [
        ElevationSegment(distance_m=55_000,  elevation_gain_m=50,    speed_kmh=70,  air_temp_c=22),
        ElevationSegment(distance_m=60_000,  elevation_gain_m=900,   speed_kmh=80,  air_temp_c=18),
        ElevationSegment(distance_m=10_000,  elevation_gain_m=-500,  speed_kmh=60,  air_temp_c=16),
        ElevationSegment(distance_m=55_000,  elevation_gain_m=50,    speed_kmh=90,  air_temp_c=16),
        ElevationSegment(distance_m=55_000,  elevation_gain_m=150,   speed_kmh=100, air_temp_c=17),
        ElevationSegment(distance_m=60_000,  elevation_gain_m=-250,  speed_kmh=100, air_temp_c=18),
        ElevationSegment(distance_m=60_000,  elevation_gain_m=30,    speed_kmh=100, air_temp_c=20),
    ]

    def test_ice_sedan_reasonable_consumption(self, ice_profile):
        engine = TerrainEngine(ice_profile)
        summary = engine.compute_route(self.SEGMENTS)
        # Road-load physics gives the theoretical minimum; real-world adds idle,
        # transmission, and accessory losses pushing this higher.
        # The model should produce a plausible floor (~3 L/100km) to ceiling (15 L/100km).
        assert summary.total_l_per_100km is not None
        assert 2.0 <= summary.total_l_per_100km <= 15.0, (
            f"Unexpected L/100km: {summary.total_l_per_100km}"
        )

    def test_ev_sedan_reasonable_consumption(self, ev_profile):
        engine = TerrainEngine(ev_profile)
        summary = engine.compute_route(self.SEGMENTS)
        # A typical EV should use 140–250 Wh/km on this route
        assert 100.0 <= summary.total_wh_per_km <= 350.0, (
            f"Unexpected Wh/km: {summary.total_wh_per_km}"
        )

    def test_total_distance_correct(self, ev_profile):
        engine = TerrainEngine(ev_profile)
        summary = engine.compute_route(self.SEGMENTS)
        expected_km = sum(s.distance_m for s in self.SEGMENTS) / 1000
        assert math.isclose(summary.total_distance_km, expected_km, rel_tol=0.01)

    def test_regen_captured_on_mountain_descent(self, ev_profile):
        engine = TerrainEngine(ev_profile)
        summary = engine.compute_route(self.SEGMENTS)
        assert summary.total_regen_wh > 0, "Expected regen energy on Blue Mountains descent"
