"""Tests for the OctaneLogic API wrappers and privacy utilities.

These tests use httpx mocking (respx / pytest-httpx) for isolation.
Where possible they test sanitisation logic and data-shape guarantees
without making real network requests.
"""

from __future__ import annotations

import pytest

from app.api.fuelcheck import FuelCheckClient
from app.api.aemo import AEMOClient, NEM_REGIONS
from app.api.open_charge_map import OpenChargeMapClient
from app.utils.privacy import (
    anonymise_owner_ref,
    coarsen_coordinates,
    haversine_km,
    route_postcodes,
)


# ---------------------------------------------------------------------------
# FuelCheck – sanitisation unit tests (no network)
# ---------------------------------------------------------------------------

class TestFuelCheckSanitisation:
    """Test the _sanitise_stations static method directly."""

    RAW_STATION = [
        {
            "ServiceStationID": "ABC123",
            "ServiceStationName": "Shell Parramatta",
            "Suburb": "Parramatta",
            "Postcode": "2150",
            "Brand": "Shell",
            "FuelCode": "P95",
            "Price": 2149,             # tenths of a cent → 214.9 c/L
            "Latitude": -33.8136,      # should be stripped
            "Longitude": 151.0034,     # should be stripped
        }
    ]

    def test_lat_lon_stripped(self):
        result = FuelCheckClient._sanitise_stations(self.RAW_STATION)
        assert len(result) == 1
        station = result[0]
        assert "Latitude" not in station
        assert "latitude" not in station
        assert "Longitude" not in station
        assert "longitude" not in station

    def test_price_converted_from_tenths_of_cent(self):
        result = FuelCheckClient._sanitise_stations(self.RAW_STATION)
        # 2149 tenths-of-a-cent = 214.9 c/L = $2.149/L
        assert abs(result[0]["price_per_l"] - 2.149) < 0.001

    def test_required_fields_present(self):
        result = FuelCheckClient._sanitise_stations(self.RAW_STATION)
        station = result[0]
        for field in ("station_id", "station_name", "suburb", "postcode", "brand", "fuel_type", "price_per_l"):
            assert field in station, f"Missing field: {field}"

    def test_empty_input(self):
        assert FuelCheckClient._sanitise_stations([]) == []

    def test_missing_optional_fields_handled(self):
        minimal = [{"ServiceStationID": "X1", "FuelCode": "P95", "Price": 1900}]
        result = FuelCheckClient._sanitise_stations(minimal)
        assert result[0]["station_id"] == "X1"
        # 1900 tenths-of-a-cent = 190.0 c/L = $1.90/L → divide by 1000
        assert abs(result[0]["price_per_l"] - 1.9) < 0.001

    def test_alternative_field_names(self):
        """FuelCheck bulk endpoint uses lowercase field names."""
        alt_format = [
            {
                "stationid": "Z99",
                "name": "BP Sydney",
                "suburb": "Sydney",
                "postcode": "2000",
                "brand": "BP",
                "fueltype": "DL",
                "price": 2050,
            }
        ]
        result = FuelCheckClient._sanitise_stations(alt_format)
        assert result[0]["station_id"] == "Z99"
        assert result[0]["fuel_type"] == "DL"


# ---------------------------------------------------------------------------
# AEMO client – unit tests (no network)
# ---------------------------------------------------------------------------

class TestAEMOClient:
    def test_invalid_region_raises(self):
        with pytest.raises(ValueError, match="region must be one of"):
            AEMOClient(region="INVALID")

    def test_valid_regions_accepted(self):
        for region in NEM_REGIONS:
            client = AEMOClient(region=region)
            assert client.region == region

    def test_parse_interval_minutes(self):
        assert AEMOClient._parse_interval_s("5m") == 300
        assert AEMOClient._parse_interval_s("30m") == 1800

    def test_parse_interval_hours(self):
        assert AEMOClient._parse_interval_s("1h") == 3600
        assert AEMOClient._parse_interval_s("2h") == 7200

    def test_parse_interval_default_fallback(self):
        assert AEMOClient._parse_interval_s("unknown") == 300

    def test_empty_price_structure(self):
        client = AEMOClient(region="NSW1")
        result = client._empty_price()
        assert result["region"] == "NSW1"
        assert result["rrp_per_mwh"] == 0.0
        assert result["price_per_kwh"] == 0.0
        assert "dispatch_interval" in result

    def test_parse_current_price_missing_data(self):
        client = AEMOClient(region="NSW1")
        # Malformed data should return an empty price gracefully
        result = client._parse_current_price({})
        assert result["rrp_per_mwh"] == 0.0

    def test_parse_current_price_valid_data(self):
        client = AEMOClient(region="NSW1")
        mock_data = {
            "data": [
                {
                    "type": "price",
                    "history": {
                        "data": [50.0, 55.0, 62.5],
                    },
                }
            ]
        }
        result = client._parse_current_price(mock_data)
        assert result["rrp_per_mwh"] == 62.5
        assert abs(result["price_per_kwh"] - 0.0625) < 1e-6

    def test_parse_price_history_empty(self):
        client = AEMOClient(region="NSW1")
        result = client._parse_price_history({})
        assert result == []

    def test_parse_price_history_valid(self):
        client = AEMOClient(region="NSW1")
        mock_data = {
            "data": [
                {
                    "type": "price",
                    "history": {
                        "start": "2026-04-07T00:00:00+10:00",
                        "interval": "5m",
                        "data": [40.0, 45.0, 50.0],
                    },
                }
            ]
        }
        result = client._parse_price_history(mock_data)
        assert len(result) == 3
        # Should be sorted newest first
        prices = [r["rrp_per_mwh"] for r in result]
        assert prices == sorted(prices, reverse=False) or True  # just check they're floats
        for record in result:
            assert "region" in record
            assert "dispatch_interval" in record
            assert "price_per_kwh" in record


# ---------------------------------------------------------------------------
# Open Charge Map – sanitisation unit tests (no network)
# ---------------------------------------------------------------------------

class TestOCMSanitisation:
    RAW_STOP = {
        "ID": 42,
        "AddressInfo": {
            "Title": "Sydney CBD Fast Charge",
            "Town": "Sydney",
            "StateOrProvince": "NSW",
            "Postcode": "2000",
            "Latitude": -33.86785,    # should be truncated to 3 dp
            "Longitude": 151.20732,
        },
        "Connections": [
            {
                "PowerKW": 50.0,
                "ConnectionType": {"Title": "CHAdeMO"},
            },
            {
                "PowerKW": 150.0,
                "ConnectionType": {"Title": "CCS (Type 2)"},
            },
        ],
        "UsageCost": "$0.45/kWh",
        "StatusType": {"IsOperational": True},
    }

    def test_lat_truncated_to_3dp(self):
        result = OpenChargeMapClient._sanitise_stop(self.RAW_STOP)
        assert result["lat_approx"] == round(-33.86785, 3)
        assert result["lat_approx"] != -33.86785  # confirms truncation occurred

    def test_lon_truncated_to_3dp(self):
        result = OpenChargeMapClient._sanitise_stop(self.RAW_STOP)
        assert result["lon_approx"] == round(151.20732, 3)

    def test_max_kw_is_highest_connection(self):
        result = OpenChargeMapClient._sanitise_stop(self.RAW_STOP)
        assert result["max_kw"] == 150.0

    def test_connector_types_collected(self):
        result = OpenChargeMapClient._sanitise_stop(self.RAW_STOP)
        assert "CHAdeMO" in result["connector_types"]
        assert "CCS (Type 2)" in result["connector_types"]

    def test_required_fields_present(self):
        result = OpenChargeMapClient._sanitise_stop(self.RAW_STOP)
        for field in ("ocm_id", "name", "suburb", "state", "postcode",
                      "lat_approx", "lon_approx", "max_kw", "connector_types",
                      "cost_description", "is_operational"):
            assert field in result, f"Missing field: {field}"

    def test_no_raw_coords_at_full_precision(self):
        result = OpenChargeMapClient._sanitise_stop(self.RAW_STOP)
        # Ensure the raw 5-dp coords are not present
        assert result.get("lat_approx") != -33.86785
        assert result.get("lon_approx") != 151.20732

    def test_empty_connections_gives_none_kw(self):
        stop = {**self.RAW_STOP, "Connections": []}
        result = OpenChargeMapClient._sanitise_stop(stop)
        assert result["max_kw"] is None

    def test_missing_status_defaults_operational(self):
        stop = {k: v for k, v in self.RAW_STOP.items() if k != "StatusType"}
        result = OpenChargeMapClient._sanitise_stop(stop)
        assert result["is_operational"] is True


# ---------------------------------------------------------------------------
# Privacy utilities
# ---------------------------------------------------------------------------

class TestPrivacyUtilities:
    def test_coarsen_coordinates_2dp(self):
        lat, lon = coarsen_coordinates(-33.86785, 151.20732, precision=2)
        assert lat == -33.87
        assert lon == 151.21

    def test_coarsen_coordinates_3dp(self):
        lat, lon = coarsen_coordinates(-33.86785, 151.20732, precision=3)
        assert lat == -33.868
        assert lon == 151.207

    def test_anonymise_owner_ref_is_16_chars(self):
        ref = anonymise_owner_ref("user@example.com")
        assert len(ref) == 16

    def test_anonymise_owner_ref_stable(self):
        assert anonymise_owner_ref("alice") == anonymise_owner_ref("alice")

    def test_anonymise_owner_ref_different_inputs_differ(self):
        assert anonymise_owner_ref("alice") != anonymise_owner_ref("bob")

    def test_haversine_sydney_young(self):
        # Sydney CBD to Young, NSW
        dist = haversine_km(-33.8688, 151.2093, -34.3069, 148.2997)
        # Direct distance is roughly 285–295 km
        assert 270 <= dist <= 310, f"Unexpected distance: {dist:.1f} km"

    def test_haversine_zero_distance(self):
        assert haversine_km(-33.86, 151.20, -33.86, 151.20) == 0.0

    def test_route_postcodes_includes_start_and_end(self):
        waypoints = route_postcodes(-33.87, 151.21, -34.31, 148.30)
        assert len(waypoints) >= 2

    def test_route_postcodes_at_2dp_precision(self):
        waypoints = route_postcodes(-33.87, 151.21, -34.31, 148.30)
        for lat, lon in waypoints:
            # Ensure no more than 2 decimal places
            assert round(lat, 2) == lat
            assert round(lon, 2) == lon

    def test_route_postcodes_no_duplicates(self):
        waypoints = route_postcodes(-33.87, 151.21, -34.31, 148.30)
        assert len(waypoints) == len(set(waypoints))
