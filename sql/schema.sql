-- =============================================================================
-- OctaneLogic Energy Ledger Schema
-- Unified schema for ICE, Hybrid, and EV drivetrains
-- PostgreSQL with pgcrypto for field-level encryption of sensitive data
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS postgis;  -- for geospatial queries

-- -----------------------------------------------------------------------------
-- VEHICLES
-- Distinct performance profiles per vehicle ID
-- -----------------------------------------------------------------------------
CREATE TABLE vehicles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_ref           TEXT NOT NULL,                      -- anonymised owner token (no PII)
    name                TEXT NOT NULL,
    make                TEXT NOT NULL,
    model               TEXT NOT NULL,
    year                SMALLINT NOT NULL,
    drivetrain          TEXT NOT NULL CHECK (drivetrain IN ('ICE', 'EV', 'HYBRID')),

    -- ICE / Hybrid parameters
    engine_displacement_cc  NUMERIC(6,1),                  -- cm³
    fuel_type           TEXT CHECK (fuel_type IN ('petrol', 'diesel', 'e85', 'lpg', NULL)),
    tank_capacity_l     NUMERIC(5,1),
    obd_supported       BOOLEAN NOT NULL DEFAULT FALSE,

    -- EV / Hybrid battery parameters
    battery_capacity_kwh    NUMERIC(6,2),
    usable_capacity_kwh     NUMERIC(6,2),
    dc_fast_charge_kw       NUMERIC(6,1),
    ac_charge_kw            NUMERIC(5,1),

    -- Aerodynamic & rolling parameters (used by physics engine)
    drag_coefficient    NUMERIC(5,3),                      -- Cd
    frontal_area_m2     NUMERIC(4,2),                      -- m²
    rolling_resistance  NUMERIC(6,4) DEFAULT 0.0130,       -- Crr
    kerb_weight_kg      NUMERIC(6,1),

    -- Regenerative braking efficiency (Hybrid/EV only)
    regen_efficiency    NUMERIC(4,3) CHECK (regen_efficiency BETWEEN 0 AND 1),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_vehicles_owner ON vehicles (owner_ref);
CREATE INDEX idx_vehicles_drivetrain ON vehicles (drivetrain);

-- -----------------------------------------------------------------------------
-- TRIPS
-- Each trip ties together route, vehicle, and energy consumption
-- -----------------------------------------------------------------------------
CREATE TABLE trips (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id          UUID NOT NULL REFERENCES vehicles (id) ON DELETE CASCADE,
    name                TEXT,

    -- Route metadata (coordinates stored as encrypted BYTEA to protect privacy)
    origin_enc          BYTEA,                              -- pgp_sym_encrypt(lat::text||','||lon::text, key)
    destination_enc     BYTEA,
    distance_km         NUMERIC(8,2) NOT NULL,
    elevation_gain_m    NUMERIC(8,1),
    elevation_loss_m    NUMERIC(8,1),

    -- Timing
    started_at          TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,
    duration_s          INTEGER GENERATED ALWAYS AS
                            (EXTRACT(EPOCH FROM (ended_at - started_at))::INTEGER) STORED,

    -- Aggregate conditions
    avg_speed_kmh       NUMERIC(5,1),
    avg_temp_c          NUMERIC(4,1),
    payload_kg          NUMERIC(6,1) DEFAULT 0,

    -- Data source
    source              TEXT NOT NULL DEFAULT 'manual'
                            CHECK (source IN ('manual', 'obd2', 'gps', 'api')),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_trips_vehicle ON trips (vehicle_id);
CREATE INDEX idx_trips_started  ON trips (started_at DESC);

-- -----------------------------------------------------------------------------
-- ENERGY_LEDGER
-- Core efficiency records — one row per segment or full trip
-- Covers ICE (L/100km), EV (Wh/km), and Hybrid (both)
-- -----------------------------------------------------------------------------
CREATE TABLE energy_ledger (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_id             UUID NOT NULL REFERENCES trips (id) ON DELETE CASCADE,
    vehicle_id          UUID NOT NULL REFERENCES vehicles (id) ON DELETE CASCADE,
    segment_index       SMALLINT NOT NULL DEFAULT 0,        -- 0 = whole trip, >0 = segment

    -- --- ICE metrics ---
    fuel_consumed_l     NUMERIC(8,3),
    l_per_100km         NUMERIC(6,3)
                            GENERATED ALWAYS AS (
                                CASE WHEN fuel_consumed_l IS NOT NULL
                                     THEN fuel_consumed_l / NULLIF(segment_km, 0) * 100
                                END
                            ) STORED,
    fuel_cost_aud       NUMERIC(8,4),
    fuel_price_per_l    NUMERIC(6,4),
    fuel_station_id     TEXT,                               -- FuelCheck station ID (no coords)

    -- --- EV metrics ---
    energy_consumed_wh  NUMERIC(10,2),
    wh_per_km           NUMERIC(8,2)
                            GENERATED ALWAYS AS (
                                CASE WHEN energy_consumed_wh IS NOT NULL
                                     THEN energy_consumed_wh / NULLIF(segment_km, 0)
                                END
                            ) STORED,
    charge_cost_aud     NUMERIC(8,4),
    charge_rate_kw      NUMERIC(6,2),
    soc_start_pct       NUMERIC(5,2),
    soc_end_pct         NUMERIC(5,2),
    grid_price_per_kwh  NUMERIC(7,5),                      -- AEMO spot price snapshot

    -- --- Hybrid metrics ---
    regen_energy_wh     NUMERIC(10,2),                     -- recovered on descents
    ev_distance_km      NUMERIC(8,2),                      -- km driven in EV mode
    ice_distance_km     NUMERIC(8,2),                      -- km driven in ICE mode

    -- --- Segment geometry ---
    segment_km          NUMERIC(8,3) NOT NULL,
    avg_grade_pct       NUMERIC(5,2),
    max_grade_pct       NUMERIC(5,2),

    -- --- Unified cost metric ---
    cost_per_km_aud     NUMERIC(8,6)
                            GENERATED ALWAYS AS (
                                COALESCE(fuel_cost_aud, 0) + COALESCE(charge_cost_aud, 0)
                                    / NULLIF(segment_km, 0)
                            ) STORED,

    -- --- Physics engine outputs ---
    f_drag_n            NUMERIC(8,2),
    f_rolling_n         NUMERIC(8,2),
    f_slope_n           NUMERIC(8,2),
    f_accel_n           NUMERIC(8,2),
    predicted_wh_per_km NUMERIC(8,2),                      -- model output
    predicted_l_per_100km NUMERIC(6,3),                    -- model output

    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ledger_trip    ON energy_ledger (trip_id);
CREATE INDEX idx_ledger_vehicle ON energy_ledger (vehicle_id);
CREATE INDEX idx_ledger_date    ON energy_ledger (recorded_at DESC);

-- -----------------------------------------------------------------------------
-- FUEL_PRICE_SNAPSHOTS
-- Cached FuelCheck API responses (no raw user location stored)
-- -----------------------------------------------------------------------------
CREATE TABLE fuel_price_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    station_id          TEXT NOT NULL,                      -- FuelCheck station code
    station_name        TEXT,
    suburb              TEXT,
    postcode            CHAR(4),
    fuel_type           TEXT NOT NULL,
    price_per_l         NUMERIC(6,3) NOT NULL,
    brand               TEXT,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fuel_station   ON fuel_price_snapshots (station_id);
CREATE INDEX idx_fuel_postcode  ON fuel_price_snapshots (postcode);
CREATE INDEX idx_fuel_fetched   ON fuel_price_snapshots (fetched_at DESC);

-- Keep only 24 h of snapshots to limit storage
CREATE OR REPLACE FUNCTION purge_old_fuel_snapshots() RETURNS void LANGUAGE sql AS $$
    DELETE FROM fuel_price_snapshots WHERE fetched_at < now() - INTERVAL '24 hours';
$$;

-- -----------------------------------------------------------------------------
-- GRID_PRICE_SNAPSHOTS
-- Cached AEMO dispatch prices — used for home-charging optimisation
-- -----------------------------------------------------------------------------
CREATE TABLE grid_price_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region              TEXT NOT NULL,                      -- e.g. 'NSW1'
    dispatch_interval   TIMESTAMPTZ NOT NULL,               -- 5-minute interval
    rrp_per_mwh         NUMERIC(10,4) NOT NULL,             -- Regional Reference Price
    price_per_kwh       NUMERIC(8,6)
                            GENERATED ALWAYS AS (rrp_per_mwh / 1000.0) STORED,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (region, dispatch_interval)
);

CREATE INDEX idx_grid_region    ON grid_price_snapshots (region);
CREATE INDEX idx_grid_interval  ON grid_price_snapshots (dispatch_interval DESC);

-- Keep 7 days of grid price history
CREATE OR REPLACE FUNCTION purge_old_grid_snapshots() RETURNS void LANGUAGE sql AS $$
    DELETE FROM grid_price_snapshots WHERE fetched_at < now() - INTERVAL '7 days';
$$;

-- -----------------------------------------------------------------------------
-- CHARGE_STOPS
-- Open Charge Map results cached per route query (no raw user coords)
-- -----------------------------------------------------------------------------
CREATE TABLE charge_stops (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ocm_id              INTEGER NOT NULL UNIQUE,            -- Open Charge Map POI ID
    name                TEXT,
    suburb              TEXT,
    state               TEXT,
    postcode            CHAR(4),
    -- Lat/lon stored at ~1 km precision (3 decimal places) to preserve privacy
    lat_approx          NUMERIC(6,3),
    lon_approx          NUMERIC(7,3),
    max_kw              NUMERIC(6,1),
    connector_types     TEXT[],
    cost_description    TEXT,
    is_operational      BOOLEAN DEFAULT TRUE,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_charge_ocm     ON charge_stops (ocm_id);
CREATE INDEX idx_charge_postcode ON charge_stops (postcode);

-- -----------------------------------------------------------------------------
-- OBD_READINGS
-- Raw OBD-II ingestion (PID 01 5E = fuel rate, L/h)
-- Stored encrypted; linked to trip but no raw GPS
-- -----------------------------------------------------------------------------
CREATE TABLE obd_readings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_id             UUID NOT NULL REFERENCES trips (id) ON DELETE CASCADE,
    vehicle_id          UUID NOT NULL REFERENCES vehicles (id) ON DELETE CASCADE,
    recorded_at         TIMESTAMPTZ NOT NULL,
    pid                 CHAR(5) NOT NULL,                   -- e.g. '01 5E'
    raw_value           NUMERIC(10,4),
    unit                TEXT,
    -- derived values
    fuel_rate_lph       NUMERIC(6,3),                       -- from PID 01 5E
    speed_kmh           NUMERIC(5,1),                       -- from PID 01 0D
    coolant_temp_c      NUMERIC(5,1)                        -- from PID 01 05
);

CREATE INDEX idx_obd_trip   ON obd_readings (trip_id);
CREATE INDEX idx_obd_date   ON obd_readings (recorded_at DESC);

-- -----------------------------------------------------------------------------
-- DETOUR_EVALUATIONS
-- Stores the result of the "Detour Delta" calculation
-- -----------------------------------------------------------------------------
CREATE TABLE detour_evaluations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_id             UUID NOT NULL REFERENCES trips (id) ON DELETE CASCADE,
    evaluated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    detour_km           NUMERIC(7,2) NOT NULL,
    detour_time_s       INTEGER NOT NULL,
    fuel_saving_aud     NUMERIC(8,4) NOT NULL,
    detour_fuel_cost_aud NUMERIC(8,4) NOT NULL,
    time_value_aud      NUMERIC(8,4) NOT NULL,              -- user-configured $/hour
    net_saving_aud      NUMERIC(8,4)
                            GENERATED ALWAYS AS (
                                fuel_saving_aud - detour_fuel_cost_aud - time_value_aud
                            ) STORED,
    recommended         BOOLEAN
                            GENERATED ALWAYS AS (
                                fuel_saving_aud > detour_fuel_cost_aud + time_value_aud
                            ) STORED,
    station_id          TEXT                                -- recommended station
);

-- =============================================================================
-- VIEWS
-- =============================================================================

CREATE OR REPLACE VIEW v_vehicle_efficiency_summary AS
SELECT
    v.id                AS vehicle_id,
    v.name              AS vehicle_name,
    v.drivetrain,
    COUNT(el.id)        AS ledger_entries,
    ROUND(AVG(el.l_per_100km)::NUMERIC, 2)      AS avg_l_per_100km,
    ROUND(AVG(el.wh_per_km)::NUMERIC, 1)        AS avg_wh_per_km,
    ROUND(SUM(el.fuel_cost_aud + COALESCE(el.charge_cost_aud, 0))::NUMERIC, 2) AS total_energy_cost_aud,
    ROUND(SUM(el.segment_km)::NUMERIC, 1)       AS total_km,
    ROUND(AVG(el.cost_per_km_aud)::NUMERIC, 6)  AS avg_cost_per_km_aud
FROM vehicles v
LEFT JOIN energy_ledger el ON el.vehicle_id = v.id
GROUP BY v.id, v.name, v.drivetrain;

CREATE OR REPLACE VIEW v_cheapest_fuel_by_postcode AS
SELECT DISTINCT ON (postcode, fuel_type)
    postcode,
    fuel_type,
    station_id,
    station_name,
    price_per_l,
    fetched_at
FROM fuel_price_snapshots
WHERE fetched_at > now() - INTERVAL '1 hour'
ORDER BY postcode, fuel_type, price_per_l ASC;

CREATE OR REPLACE VIEW v_optimal_charge_window AS
SELECT
    region,
    dispatch_interval,
    price_per_kwh,
    RANK() OVER (PARTITION BY region ORDER BY price_per_kwh ASC) AS cheapest_rank
FROM grid_price_snapshots
WHERE dispatch_interval >= now() - INTERVAL '24 hours';
