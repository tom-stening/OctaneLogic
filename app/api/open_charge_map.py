"""OctaneLogic – Open Charge Map API wrapper.

Used to locate EV charging stops along a route, including available power
(kW) and cost information.

Privacy model:
* Coordinates submitted to the OCM API are route waypoints, not the user's
  current GPS position.  Callers are expected to pass intermediate route
  coordinates rather than live device location.
* Results are cached in the local database at ~1 km coordinate precision
  (3 decimal places) to avoid storing exact charging-stop positions.

Reference: https://openchargemap.org/site/develop/api
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OCM_BASE_URL = "https://api.openchargemap.io/v3"
_DEFAULT_TIMEOUT_S = 12.0


class OpenChargeMapClient:
    """Async wrapper around the Open Charge Map REST API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = OCM_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        self._api_key = api_key or os.environ.get("OCM_API_KEY", "")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_stops_near(
        self,
        lat: float,
        lon: float,
        radius_km: float = 10.0,
        max_results: int = 20,
        min_kw: float | None = None,
        connector_types: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Return EV charge stops near a route waypoint.

        Args:
            lat: Latitude of the route waypoint (NOT live device position).
            lon: Longitude of the route waypoint.
            radius_km: Search radius in kilometres.
            max_results: Maximum number of results to return.
            min_kw: Filter to stops with at least this power output.
            connector_types: List of OCM connection type IDs to filter by.

        Returns:
            List of sanitised charge-stop dicts suitable for database storage.
        """
        params: dict[str, Any] = {
            "key": self._api_key,
            "latitude": lat,
            "longitude": lon,
            "distance": radius_km,
            "distanceunit": "km",
            "maxresults": max_results,
            "compact": True,
            "verbose": False,
            "output": "json",
        }
        if connector_types:
            params["connectiontypeid"] = ",".join(str(c) for c in connector_types)

        raw_stops = await self._get("/poi", params=params)
        sanitised = [self._sanitise_stop(s) for s in raw_stops]

        if min_kw is not None:
            sanitised = [s for s in sanitised if (s["max_kw"] or 0) >= min_kw]

        return sanitised

    async def get_stops_along_route(
        self,
        waypoints: list[tuple[float, float]],
        radius_km: float = 5.0,
        min_kw: float | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate charging stops within *radius_km* of each route waypoint.

        Deduplicates by OCM POI ID so each station appears only once.

        Args:
            waypoints: List of (lat, lon) route waypoints.
            radius_km: Search corridor radius around each waypoint.
            min_kw: Optional minimum charger power filter.

        Returns:
            Deduplicated list of charge-stop dicts ordered by position along
            the route.
        """
        seen_ids: set[int] = set()
        results: list[dict[str, Any]] = []

        for lat, lon in waypoints:
            stops = await self.get_stops_near(lat, lon, radius_km=radius_km, min_kw=min_kw)
            for stop in stops:
                ocm_id = stop["ocm_id"]
                if ocm_id not in seen_ids:
                    seen_ids.add(ocm_id)
                    results.append(stop)

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                logger.error("OCM API HTTP error %s: %s", exc.response.status_code, url)
                raise
            except httpx.RequestError as exc:
                logger.error("OCM API network error: %s", exc)
                raise

    @staticmethod
    def _sanitise_stop(raw: dict[str, Any]) -> dict[str, Any]:
        """Extract only the fields we store; truncate coords to 3 dp."""
        address = raw.get("AddressInfo", {})
        connections = raw.get("Connections", []) or []

        # Max power across all connections
        max_kw: float | None = None
        connector_types: list[str] = []
        for conn in connections:
            kw = conn.get("PowerKW")
            if kw is not None:
                max_kw = max(max_kw or 0.0, float(kw))
            ct = (conn.get("ConnectionType") or {}).get("Title")
            if ct and ct not in connector_types:
                connector_types.append(ct)

        # Truncate to 3 decimal places (~111 m precision) for privacy
        raw_lat = address.get("Latitude")
        raw_lon = address.get("Longitude")
        lat_approx = round(float(raw_lat), 3) if raw_lat is not None else None
        lon_approx = round(float(raw_lon), 3) if raw_lon is not None else None

        return {
            "ocm_id": raw.get("ID"),
            "name": address.get("Title"),
            "suburb": address.get("Town"),
            "state": address.get("StateOrProvince"),
            "postcode": address.get("Postcode"),
            "lat_approx": lat_approx,
            "lon_approx": lon_approx,
            "max_kw": max_kw,
            "connector_types": connector_types,
            "cost_description": (raw.get("UsageCost") or "").strip() or None,
            "is_operational": raw.get("StatusType", {}).get("IsOperational", True)
            if raw.get("StatusType")
            else True,
        }
