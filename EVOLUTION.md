# EVOLUTION.md — OctaneLogic Horizon Scan

> **Version Gate Protocol**: Before implementing any new version milestone
> this document must be updated with disruptive findings from the latest
> research in battery technology, fuel additives, and API landscape changes.

---

## v0.1 → v0.2 Horizon Scan (April 2026)

### 1. Battery Technology

| Finding | Implication for OctaneLogic |
|---|---|
| **CATL Shenxing PLUS (2025)** — 4C superfast-charging LFP cells achieving 1,000 km CLTC range and 10-min 10→80 % charge. | `SoC` depletion curves must support non-linear charge acceptance modelling; `charge_rate_kw` column should become a dynamic profile, not a scalar. |
| **QuantumScape solid-state (commercial pilot 2025–26)** — near-zero capacity fade at high SOC cycles. | Current `battery_capacity_kwh` / `usable_capacity_kwh` split should include a `degradation_pct` field to track health over time. |
| **Sodium-ion (BYD Seagull, 2025 AU launch)** — lower energy density (~160 Wh/kg) but better cold-weather performance. | Physics engine should include a `battery_chemistry` parameter to adjust temperature-derate coefficients. |

### 2. Fuel Additives & ICE Efficiency

| Finding | Implication for OctaneLogic |
|---|---|
| **E10 / E20 uplift programs (NSW 2026)** — mandated E10 at 35 % of pump volume; E20 pilot at 12 % of metro stations. | FuelCheck wrapper must distinguish `E10`/`E20`/`E85` product codes; physics engine must apply correct energy densities (MJ/L). |
| **HEVO (Hydrotreated Ethanol Vegetable Oil) bio-diesel pilot (Port Kembla 2025)** — drop-in 100 % renewable diesel with 11 % lower energy density than EN 590 diesel. | `fuel_type` enum and `fuel_energy_density_mj_l` mapping must be extended. |
| **GPF (Gasoline Particulate Filters) mandatory from July 2026 (Euro 6e-bis equivalent, AU NCAP)** — adds ~1.5 % back-pressure penalty on port-injection engines. | Add optional `gpf_penalty_pct` field to `VehicleProfile`; apply as multiplier on `f_drag_n`. |

### 3. API Landscape Changes

| API | Change | Action Required |
|---|---|---|
| **FuelCheck NSW** — migrated from OneGov v1 to ServiceNSW v2 API gateway (January 2026). | Base URL updated to `https://api.onegov.nsw.gov.au/FuelPriceCheck/v2`. Verify endpoint paths in `app/api/fuelcheck.py`. |
| **AEMO MSATS / NEMWEB** — CDR (Consumer Data Right) energy data standard mandated from July 2025; all retailers must expose CDR-compliant `/energy/electricity/usage` endpoints. | Add a CDR-native adapter alongside the OpenNEM fallback so users can pull home energy data without screen-scraping. |
| **OpenNEM v4 API** — breaking schema change (March 2026): `history.data` array replaced with `series` object containing typed sub-arrays. | Update `_parse_current_price` and `_parse_price_history` in `app/api/aemo.py`. |
| **Open Charge Map v4 (beta)** — new `ChargingCurve` field per connection providing kW vs. SoC profile. | Cache `ChargingCurve` in `charge_stops` table to enable dynamic stop-time estimation. |
| **OSM Overpass API** — new `highway=motorway_link` elevation tag available via Overpass QL v0.7.60. | Elevation ingestion pipeline can now avoid the separate SRTM tile download by querying Overpass directly. |

### 4. Regulatory & Market Events

* **NSW EV road-user charge (RUC)** — $0.025/km effective July 2026. Must be added as a per-km surcharge in `cost_per_km_aud` for EV ledger entries.
* **DNSP time-of-use tariffs (Ausgrid, July 2025)** — peak 3–9 pm weekdays at $0.43/kWh. AEMO client `get_cheapest_windows` must exclude peak windows by default.
* **ACCC petrol monitoring quarterly report (Q1 2026)** — average metropolitan/regional price gap widened to 18.4 cpl, reinforcing the value of the Detour Delta feature for rural routes.

---

## v0.2 → v1.0 Horizon Scan (Placeholder)

*Update this section before beginning v1.0 implementation.*
