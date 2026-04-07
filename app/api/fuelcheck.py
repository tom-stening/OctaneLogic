"""OctaneLogic – FuelCheck NSW API wrapper.

Privacy model:
* The wrapper accepts a *postcode* or *suburb* (not precise GPS coordinates)
  before forwarding the search to FuelCheck.  This prevents the FuelCheck
  servers from learning the user's exact location.
* Raw station coordinates returned by the API are *not* stored in the
  application database; only suburb/postcode and the station ID are retained.
* API key is read from the environment and never logged.

Reference: https://api.nsw.gov.au/Product/Index/22 (FuelCheck NSW)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FUELCHECK_BASE_URL = "https://api.onegov.nsw.gov.au/FuelPriceCheck/v2"
_DEFAULT_TIMEOUT_S = 10.0


class FuelCheckClient:
    """Async wrapper around the NSW FuelCheck API.

    All location data is coarsened to postcode/suburb before the request
    leaves the device, preserving user location privacy.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = FUELCHECK_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        self._api_key = api_key or os.environ.get("FUELCHECK_API_KEY", "")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_prices_by_postcode(
        self,
        postcode: str,
        fuel_type: str = "P95",
        radius_km: float = 5.0,
    ) -> list[dict[str, Any]]:
        """Return fuel prices for all stations within *radius_km* of a postcode.

        Args:
            postcode: 4-digit NSW postcode (e.g. "2000").
            fuel_type: FuelCheck product code such as "P95", "DL", "E10".
            radius_km: Search radius in kilometres around the postcode centroid.

        Returns:
            List of station price dicts with keys:
            ``station_id``, ``station_name``, ``suburb``, ``postcode``,
            ``fuel_type``, ``price_per_l``, ``brand``.
            Raw lat/lon from the API response are *dropped*.
        """
        params = {
            "fueltype": fuel_type,
            "latitude": "",          # intentionally omitted – we rely on postcode
            "longitude": "",
            "radius": str(radius_km),
            "postcode": postcode,
        }
        raw = await self._get("/fuel/prices/nearby", params=params)
        return self._sanitise_stations(raw.get("stations", []))

    async def get_prices_bulk(
        self,
        fuel_type: str = "P95",
    ) -> list[dict[str, Any]]:
        """Return the current price for all NSW stations (bulk endpoint).

        No location data is sent in this request.
        """
        params = {"fueltype": fuel_type}
        raw = await self._get("/fuel/prices", params=params)
        return self._sanitise_stations(raw.get("prices", []))

    async def get_reference_data(self) -> dict[str, Any]:
        """Return fuel types and brand list from the FuelCheck reference endpoint."""
        return await self._get("/fuel/lovs")

    # ------------------------------------------------------------------
    # Detour-Delta helper
    # ------------------------------------------------------------------

    async def cheapest_along_route(
        self,
        postcodes: list[str],
        fuel_type: str = "P95",
    ) -> dict[str, Any] | None:
        """Find the cheapest station across a list of postcodes along a route.

        Args:
            postcodes: Ordered list of postcodes that approximate the route
                corridor.  The caller is responsible for ensuring these are
                derived from route geometry, *not* from live device GPS.
            fuel_type: FuelCheck product code.

        Returns:
            The cheapest station dict, or ``None`` if no results.
        """
        all_stations: list[dict[str, Any]] = []
        for postcode in postcodes:
            stations = await self.get_prices_by_postcode(postcode, fuel_type)
            all_stations.extend(stations)

        if not all_stations:
            return None
        return min(all_stations, key=lambda s: s["price_per_l"])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        headers = {
            "apikey": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "FuelCheck API error %s for %s",
                    exc.response.status_code,
                    url,
                )
                raise
            except httpx.RequestError as exc:
                logger.error("FuelCheck network error: %s", exc)
                raise

    @staticmethod
    def _sanitise_stations(stations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Strip precise coordinates and PII from raw API station records."""
        sanitised = []
        for raw in stations:
            sanitised.append(
                {
                    "station_id": raw.get("ServiceStationID") or raw.get("stationid", ""),
                    "station_name": raw.get("ServiceStationName") or raw.get("name", ""),
                    "suburb": raw.get("Suburb") or raw.get("suburb", ""),
                    "postcode": raw.get("Postcode") or raw.get("postcode", ""),
                    "brand": raw.get("Brand") or raw.get("brand", ""),
                    "fuel_type": raw.get("FuelCode") or raw.get("fueltype", ""),
                    "price_per_l": float(
                        raw.get("Price") or raw.get("price", 0) or 0
                    ) / 1000.0,  # FuelCheck returns tenths of a cent; /1000 → AUD/L
                }
            )
        return sanitised
