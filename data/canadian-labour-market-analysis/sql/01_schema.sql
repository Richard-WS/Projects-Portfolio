-- ============================================================================
-- Canadian Labour Market Analysis — schema
--
-- A small star-shaped warehouse built from two Statistics Canada tables:
--
--   14-10-0327-01  Labour force characteristics by province, annual
--                  (1976-2025; 10 provinces + Canada; 12 characteristics;
--                  3 genders; 22 age groups; levels in thousands, rates in %)
--   17-10-0005-01  Population estimates on July 1, by age and gender, annual
--                  (1971-2025; all 13 regions; 3 genders; age groups shared
--                  with the labour table plus "All ages")
--
-- Regions is the only dimension table; labour_force and population are the
-- two fact tables. They join on (ref_year, region_code, gender, age_group)
-- using the shared age-group vocabulary, so per-capita and rate calculations
-- stay consistent across the warehouse.
--
-- SQLite dialect. Foreign keys are enforced per-connection (PRAGMA).
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Dimension: regions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS regions (
    region_code TEXT PRIMARY KEY,                -- CA, NL, PE, NS, NB, QC, ON, MB, SK, AB, BC, YT, NT, NU, NTI
    region_name TEXT NOT NULL UNIQUE,            -- full English name from StatsCan
    region_type TEXT NOT NULL
        CHECK (region_type IN ('country', 'province', 'territory'))
);

-- ---------------------------------------------------------------------------
-- Fact: labour_force
-- One row per (year, region, gender, age group, characteristic).
-- Values are either thousands of persons (uom = 'Persons in thousands') or
-- percentages (uom = 'Percent') — the same characteristic name is reused
-- across levels and rates, so uom disambiguates.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS labour_force (
    ref_year      INTEGER NOT NULL CHECK (ref_year BETWEEN 1900 AND 2100),
    region_code   TEXT    NOT NULL REFERENCES regions(region_code),
    gender        TEXT    NOT NULL CHECK (gender IN ('Total', 'Men+', 'Women+')),
    age_group     TEXT    NOT NULL,
    characteristic TEXT   NOT NULL,              -- e.g. Employment, Unemployment rate
    value         REAL    NOT NULL,
    uom           TEXT    NOT NULL CHECK (uom IN ('Persons in thousands', 'Percent')),
    PRIMARY KEY (ref_year, region_code, gender, age_group, characteristic)
);

-- Common access patterns: one region across time, one characteristic across regions.
CREATE INDEX IF NOT EXISTS idx_labour_region_year ON labour_force (region_code, ref_year);
CREATE INDEX IF NOT EXISTS idx_labour_char        ON labour_force (characteristic, age_group);

-- ---------------------------------------------------------------------------
-- Fact: population
-- One row per (year, region, gender, age group). Population counts are
-- persons (not thousands), matching the raw table.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS population (
    ref_year    INTEGER NOT NULL CHECK (ref_year BETWEEN 1900 AND 2100),
    region_code TEXT    NOT NULL REFERENCES regions(region_code),
    gender      TEXT    NOT NULL CHECK (gender IN ('Total', 'Men+', 'Women+')),
    age_group   TEXT    NOT NULL,
    value       REAL    NOT NULL,
    PRIMARY KEY (ref_year, region_code, gender, age_group)
);

CREATE INDEX IF NOT EXISTS idx_pop_region_year ON population (region_code, ref_year);
