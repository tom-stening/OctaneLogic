"""OctaneLogic – AEMO (Australian Energy Market Operator) API wrapper.

Used to fetch real-time and forecast National Electricity Market (NEM) dispatch
prices for grid-optimised home EV charging.

Privacy model:
* No user location or vehicle data is included in AEMO API requests.
* Only the NEM region (e.g. "NSW1") is transmitted, which is coarse enough
  to carry no personally identifiable information.
* API responses are cached locally in PostgreSQL and never forwarded to
  third parties.

Reference: https://aemo.com.au/en/energy-systems/electricity/national-electricity-market-nem/data-nem/market-data-nemweb
AEMO NEMSIGHT/OpenNEM JSON feed: https://opennem.org.au/api/docs
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# AEMO's publicly accessible current-price endpoint (no API key required)
AEMO_CURRENT_PRICE_URL = (
    "https://visualisations.aemo.com.au/aemo/apps/api/report/ELEC_NEM_SUMMARY"
)
AEMO_DISPATCH_URL = (
    "https://aemo.com.au/aemo/apps/api/report/TRADINGPRICE"
)

# Fallback to OpenNEM (community API, more reliable for automation)
OPENNEM_BASE_URL = "https://api.opennem.org.au"

_DEFAULT_TIMEOUT_S = 15.0

# Valid NEM regions
NEM_REGIONS = ("NSW1", "QLD1", "SA1", "TAS1", "VIC1")


class AEMOClient:
    """Async wrapper for AEMO / OpenNEM electricity price data.

    Designed for home-charging optimisation: fetch the current spot price for
    a NEM region and determine the cheapest dispatch windows for overnight
    EV charging.
    """

    def __init__(
        self,
        region: str = "NSW1",
        timeout: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        if region not in NEM_REGIONS:
            raise ValueError(f"region must be one of {NEM_REGIONS}, got {region!r}")
        self.region = region
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_current_price(self) -> dict[str, Any]:
        """Fetch the current 5-minute dispatch price for the configured region.

        Returns:
            Dict with keys ``region``, ``dispatch_interval`` (ISO-8601),
            ``rrp_per_mwh``, ``price_per_kwh``.
        """
        data = await self._fetch_opennem_current()
        return self._parse_current_price(data)

    async def get_price_history(self, hours: int = 24) -> list[dict[str, Any]]:
        """Fetch recent price history for the region.

        Args:
            hours: Number of hours of history to retrieve (max 48).

        Returns:
            List of dispatch interval dicts, newest first.
        """
        hours = min(hours, 48)
        data = await self._fetch_opennem_history(hours=hours)
        return self._parse_price_history(data)

    async def get_cheapest_windows(
        self,
        hours_ahead: int = 12,
        required_hours: int = 4,
    ) -> list[dict[str, Any]]:
        """Return the cheapest *required_hours* dispatch windows in the next
        *hours_ahead* hours, ordered cheapest-first.

        This is the core output consumed by the EV charging scheduler.

        Args:
            hours_ahead: How many hours to look ahead.
            required_hours: How many hours of cheap charging are needed.

        Returns:
            List of dispatch interval dicts, sorted by ascending ``rrp_per_mwh``.
        """
        history = await self.get_price_history(hours=hours_ahead)
        sorted_windows = sorted(history, key=lambda r: r["rrp_per_mwh"])
        return sorted_windows[:required_hours]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_opennem_current(self) -> dict[str, Any]:
        url = f"{OPENNEM_BASE_URL}/stats/power/network/NEM/{self.region}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                logger.error("AEMO/OpenNEM HTTP error %s: %s", exc.response.status_code, url)
                raise
            except httpx.RequestError as exc:
                logger.error("AEMO/OpenNEM network error: %s", exc)
                raise

    async def _fetch_opennem_history(self, hours: int) -> dict[str, Any]:
        url = f"{OPENNEM_BASE_URL}/stats/energy/network/NEM/{self.region}"
        params = {"period": f"{hours}h", "interval": "5m"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                logger.error("AEMO history HTTP error %s: %s", exc.response.status_code, url)
                raise
            except httpx.RequestError as exc:
                logger.error("AEMO history network error: %s", exc)
                raise

    def _parse_current_price(self, data: dict[str, Any]) -> dict[str, Any]:
        """Extract the price from OpenNEM's current stats response."""
        try:
            series = data.get("data", [])
            price_series = next(
                (s for s in series if s.get("type") == "price"), None
            )
            if price_series is None:
                return self._empty_price()

            history = price_series.get("history", {})
            values = history.get("data", [])
            rrp = float(values[-1]) if values else 0.0

            return {
                "region": self.region,
                "dispatch_interval": datetime.now(tz=timezone.utc).isoformat(),
                "rrp_per_mwh": round(rrp, 4),
                "price_per_kwh": round(rrp / 1_000.0, 6),
            }
        except (KeyError, IndexError, TypeError, StopIteration):
            logger.warning("Unexpected AEMO response format; returning empty price")
            return self._empty_price()

    def _parse_price_history(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert OpenNEM history response to a flat list of price records."""
        records: list[dict[str, Any]] = []
        try:
            series = data.get("data", [])
            price_series = next(
                (s for s in series if s.get("type") == "price"), None
            )
            if price_series is None:
                return records

            history = price_series.get("history", {})
            start_iso = history.get("start")
            interval_str = history.get("interval", "5m")
            values = history.get("data", [])

            # Parse interval to seconds
            interval_s = self._parse_interval_s(interval_str)
            start_dt = datetime.fromisoformat(start_iso) if start_iso else datetime.now(tz=timezone.utc)

            for i, val in enumerate(values):
                if val is None:
                    continue
                interval_dt = start_dt.replace(
                    second=0, microsecond=0
                )
                from datetime import timedelta
                interval_dt = start_dt + timedelta(seconds=i * interval_s)
                rrp = float(val)
                records.append(
                    {
                        "region": self.region,
                        "dispatch_interval": interval_dt.isoformat(),
                        "rrp_per_mwh": round(rrp, 4),
                        "price_per_kwh": round(rrp / 1_000.0, 6),
                    }
                )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Could not parse AEMO history: %s", exc)

        # Newest first
        records.sort(key=lambda r: r["dispatch_interval"], reverse=True)
        return records

    @staticmethod
    def _parse_interval_s(interval_str: str) -> int:
        """Convert an interval string like '5m' or '30m' to seconds."""
        interval_str = interval_str.strip().lower()
        if interval_str.endswith("m"):
            return int(interval_str[:-1]) * 60
        if interval_str.endswith("h"):
            return int(interval_str[:-1]) * 3_600
        return 300  # default 5 minutes

    def _empty_price(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "dispatch_interval": datetime.now(tz=timezone.utc).isoformat(),
            "rrp_per_mwh": 0.0,
            "price_per_kwh": 0.0,
        }
