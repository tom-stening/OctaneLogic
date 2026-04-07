# OctaneLogic

A local-first energy efficiency engine for ICE, Hybrid, and EV drivetrains.
Minimises **$/km** by integrating real-time fuel and grid pricing with a
terrain-aware physics model.

**Core metric:** Minimise `$/km` — optimise `Wh/km` (EV) or `L/100km` (ICE/Hybrid).  
**Primary benchmark route:** Sydney → Young, NSW (high elevation variance — Blue Mountains, Great Dividing Range).

---

## Architecture

```
OctaneLogic/
├── app/
│   ├── main.py               # FastAPI application
│   ├── config.py             # Pydantic Settings (env-driven)
│   ├── database.py           # Async SQLAlchemy session factory
│   ├── physics/
│   │   └── terrain_engine.py # Road-load physics: F_total = F_drag + F_rolling + F_slope + F_accel
│   ├── api/
│   │   ├── fuelcheck.py      # FuelCheck NSW — real-time fuel price arbitrage
│   │   ├── aemo.py           # AEMO / OpenNEM — grid-optimised home charging
│   │   └── open_charge_map.py # Open Charge Map — EV charge stop discovery
│   ├── models/
│   │   └── energy_ledger.py  # SQLAlchemy ORM models
│   ├── schemas/
│   │   └── energy_ledger.py  # Pydantic request/response schemas
│   ├── routers/
│   │   ├── vehicles.py       # Vehicle profile CRUD
│   │   ├── trips.py          # Trip management
│   │   └── efficiency.py     # Physics predictions, fuel/grid pricing, detour evaluation
│   └── utils/
│       └── privacy.py        # Coordinate coarsening, anonymisation helpers
├── sql/
│   └── schema.sql            # PostgreSQL schema (ICE/EV/Hybrid unified ledger)
├── tests/
│   ├── test_physics.py       # Physics engine unit + integration tests
│   └── test_api_wrappers.py  # API wrapper sanitisation + privacy tests
├── EVOLUTION.md              # Version Gate horizon scan
├── WISHLIST.md               # Strategic feature wishlist
├── docker-compose.yml        # PostgreSQL + Redis + API service
└── .env.example              # Environment variable template
```

---

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Fill in FUELCHECK_API_KEY, OCM_API_KEY, DB_ENCRYPTION_KEY

# 2. Start services
docker compose up -d

# 3. Open API docs
open http://localhost:8000/docs
```

---

## Domain Logic

### ICE
* **FuelCheck NSW** API for real-time price arbitrage along route postcodes.
* **Detour Delta**: `POST /efficiency/detour-delta` — is `fuel_saving > detour_cost + time_value`?
* Manual entry or OBD-II (PID `01 5E`) ingestion via `obd_readings` table.

### EV
* **AEMO** real-time dispatch pricing for grid-optimised home charging windows.
* SoC vs terrain-based depletion via the physics engine.
* Charge stop mapping with **Open Charge Map** (kW vs. cost).

### Hybrid
* **Efficiency Crossover**: `TerrainEngine.efficiency_crossover()` switches between EV and ICE based on load/speed.
* Regenerative braking efficiency tracked on descents (Blue Mountains / Great Dividing Range).

---

## Physics Engine

The `TerrainEngine` implements the road-load equation:

```
F_total = F_drag + F_rolling + F_slope + F_accel
```

Where:

| Force | Formula |
|---|---|
| `F_drag` | `½ ρ Cd A v²` |
| `F_rolling` | `Crr m g cos(θ)` |
| `F_slope` | `m g sin(θ)` |
| `F_accel` | `m a` (0 for steady-state) |

Air density is corrected for ambient temperature.  Regen recovery is modelled as
`|F_total| × d × η_regen` when the vehicle is in a braking phase (`F_total < 0`).

---

## Privacy Model

| Data | Treatment |
|---|---|
| User GPS coordinates | Never sent to external APIs — coarsened to postcode/suburb first |
| Station/stop coordinates | Truncated to 3 decimal places (~111 m) in local DB |
| Owner identity | SHA-256 hashed to 16-char token; original never stored |
| Trip origin/destination | Encrypted with pgcrypto field-level encryption at rest |

---

## Tech Stack

| Component | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Database | PostgreSQL 16 + PostGIS (on Unraid) |
| Cache | Redis 7 |
| ORM | SQLAlchemy 2 (async) |
| HTTP client | httpx (async) |
| Physics | Pure Python + NumPy |
| Deployment | Docker Compose |

---

## Running Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

---

## Version Gate Protocol

Before implementing any new version milestone:
1. Run a **Horizon Scan** — update [`EVOLUTION.md`](EVOLUTION.md)
2. Add 5 wishlist items to [`WISHLIST.md`](WISHLIST.md) with strategic justifications
