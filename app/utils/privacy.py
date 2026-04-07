"""OctaneLogic – location privacy utilities.

Provides helpers for coarsening GPS coordinates before they leave the device,
ensuring user location data is never transmitted at full precision to external
APIs or stored at full precision in third-party caches.
"""

from __future__ import annotations

import hashlib
import math


def coarsen_coordinates(lat: float, lon: float, precision: int = 2) -> tuple[float, float]:
    """Round GPS coordinates to reduce spatial precision.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        precision: Number of decimal places to retain.
                   2 dp  ≈  1.1 km precision (safe for API queries)
                   3 dp  ≈  111 m  (used for local DB storage)

    Returns:
        Tuple of (rounded_lat, rounded_lon).
    """
    return round(lat, precision), round(lon, precision)


def coords_to_postcode_approximation(lat: float, lon: float) -> str:
    """Return a coarsened coordinate string suitable for postcode-level queries.

    This is intentionally imprecise – it snaps to a 0.1-degree grid (~11 km)
    so that postcode lookups cannot be used to pinpoint the user's location.

    Returns:
        A string like "-33.8,151.2" (2 dp).
    """
    coarse_lat, coarse_lon = coarsen_coordinates(lat, lon, precision=1)
    return f"{coarse_lat},{coarse_lon}"


def anonymise_owner_ref(raw_identifier: str) -> str:
    """Derive a stable, anonymous owner token from a raw identifier.

    Uses SHA-256 so the original identifier cannot be recovered.

    Args:
        raw_identifier: Any user identifier (email, username, device ID, …).

    Returns:
        A 16-character hex string suitable for use as ``owner_ref``.
    """
    digest = hashlib.sha256(raw_identifier.encode()).hexdigest()
    return digest[:16]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in kilometres between two points.

    Args:
        lat1, lon1: First point in decimal degrees.
        lat2, lon2: Second point in decimal degrees.
    """
    r = 6_371.0  # Earth mean radius, km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def route_postcodes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    step_km: float = 50.0,
) -> list[tuple[float, float]]:
    """Generate evenly-spaced intermediate waypoints along a great-circle route.

    These waypoints are at coarse (2 dp) precision and are used to build the
    list of postcodes for fuel-price corridor searches rather than tracking
    precise device location.

    Args:
        origin_lat, origin_lon: Start point.
        dest_lat, dest_lon: End point.
        step_km: Approximate spacing between intermediate waypoints (km).

    Returns:
        List of (lat, lon) tuples at 2 dp precision, including start and end.
    """
    total_km = haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)
    n_steps = max(2, int(total_km / step_km) + 1)
    waypoints = []
    for i in range(n_steps + 1):
        t = i / n_steps
        lat = origin_lat + t * (dest_lat - origin_lat)
        lon = origin_lon + t * (dest_lon - origin_lon)
        coarse = coarsen_coordinates(lat, lon, precision=2)
        if not waypoints or coarse != waypoints[-1]:
            waypoints.append(coarse)
    return waypoints
