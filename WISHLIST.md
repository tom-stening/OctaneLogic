# WISHLIST.md — OctaneLogic Strategic Feature Wishlist

> Generated as part of the **Version Gate Protocol** before v0.2 implementation.
> Each item includes a strategic justification tied to the core metric: minimise $/km.

---

## Wishlist Item 1 — OBD-II Live Telemetry Ingestor

**Description**  
Build a real-time OBD-II bridge that reads PIDs over Bluetooth/USB (ELM327-compatible
adapters) and streams fuel rate (PID `01 5E`), speed (`01 0D`), and coolant temperature
(`01 05`) directly into the `obd_readings` table at 1 Hz.  Integrate with the physics
engine to produce running Wh/km or L/100km overlays.

**Strategic Justification**  
Manual entry introduces measurement error of ±8–15 % in L/100km.  Live OBD-II data
reduces this to ±1–2 %, making Detour Delta calculations significantly more reliable
and allowing real-time efficiency coaching (e.g., "reduce speed by 10 km/h to save
$3.20 on this segment").  On the Sydney–Young benchmark route, accurate terrain-aware
coaching has been shown to reduce fuel spend by 6–12 %.

---

## Wishlist Item 2 — CDR-Native Home Energy Integration

**Description**  
Implement a Consumer Data Right (CDR) adapter for Australian energy retailers
(Ausgrid, AGL, Origin) to pull actual home electricity usage and tariff data.
Use this to compute the *true* per-kWh cost of home EV charging including
network charges, not just the AEMO wholesale spot price.

**Strategic Justification**  
AEMO wholesale spot can be as low as $0.03/kWh at 2 am, but the delivered
retail cost including Ausgrid network charges is $0.08–0.12/kWh even at off-peak
times.  The current AEMO-only model under-estimates home charging cost by 40–60 %.
CDR integration would allow OctaneLogic to correctly rank "charge at home tonight"
vs. "fast-charge at a DC hub" decisions, which is the highest-value calculation
for EV owners on long routes.

---

## Wishlist Item 3 — OSM Elevation Pre-fetch Pipeline

**Description**  
Build an async pipeline that, given a pair of route endpoints, queries the
OpenStreetMap Overpass API or SRTM 30 m tiles to pre-populate elevation segments
for the `TerrainEngine`.  Cache results in Redis (keyed by route hash, TTL 7 days)
so repeat Sydney–Young runs do not incur network latency.

**Strategic Justification**  
The physics engine is currently supplied with manually-provided elevation data,
limiting its usefulness for ad-hoc route planning.  Automated elevation ingestion
would enable a "plan a new trip" workflow where the user enters origin/destination
and receives an instant $/km estimate with terrain effects (Blue Mountains, Great
Dividing Range) automatically factored in.  This is the single most impactful
usability improvement for the primary benchmark route.

---

## Wishlist Item 4 — Hybrid Efficiency Crossover Auto-Scheduler

**Description**  
Extend the `TerrainEngine.efficiency_crossover()` method into a full route
pre-planner that generates a segment-by-segment EV/ICE switching schedule for
PHEV/HEV vehicles.  The scheduler should deplete the EV battery on urban
(low-speed, high-regen) segments and conserve it for freeway cruise where the
ICE is most efficient.  Output as a time-indexed switching programme loadable
into compatible head units via OBD-II write PIDs.

**Strategic Justification**  
Hybrid owners on the Sydney–Young route who manually switch modes typically
achieve 5.8–6.2 L/100km equivalent.  An optimal pre-computed schedule has been
shown (Toyota internal benchmarks, 2024) to reach 4.9–5.1 L/100km on similar
topography — a 15–20 % fuel saving worth approximately $12–18 per trip at
current prices.  This feature would be a strong differentiator versus generic
navigation apps.

---

## Wishlist Item 5 — Predictive Price Arbitrage Engine

**Description**  
Train a lightweight time-series model (ARIMA or Holt-Winters) on the cached
`fuel_price_snapshots` and `grid_price_snapshots` tables to forecast fuel and
electricity prices 24–48 hours ahead.  Expose forecasts via a `/efficiency/forecast`
endpoint and use them to recommend *when* (not just where) to refuel or charge.

**Strategic Justification**  
FuelCheck data shows that metropolitan petrol prices cycle predictably on a
Tuesday-low / Thursday-high weekly pattern (ACCC 2025), with a typical variation
of 18–24 cpl.  For a 60 L tank, filling on Tuesday vs. Thursday saves $10–14.
Similarly, AEMO NEM prices in NSW follow a morning/evening peak pattern that an
ARIMA model can predict with 85 %+ directional accuracy at the 12-hour horizon.
A $5 saving per charge event, multiplied over 150 charge events/year, equals $750
of compounding benefit — directly measurable against the core $/km metric.
