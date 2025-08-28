# schema.py
from pathlib import Path
from typing import Optional, Union
import sqlite3

# === Embedded fallback schema (used if schema_sql_path not found) ===
SCHEMA_SQL = r"""
PRAGMA foreign_keys = ON;

-- Reference tables
CREATE TABLE IF NOT EXISTS sources (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  site   TEXT NOT NULL,
  url    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS years (
  id    INTEGER PRIMARY KEY AUTOINCREMENT,
  year  INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS currency (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  currency_code TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS period (
  id   INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS job_positions_seniorities (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  position_name TEXT NOT NULL,
  seniority     TEXT NOT NULL,
  UNIQUE (position_name, seniority)
);

-- Facts
CREATE TABLE IF NOT EXISTS job_position_descriptions (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  position_seniority_id INTEGER NOT NULL,
  source_id             INTEGER NOT NULL,
  min_amount            REAL,
  max_amount            REAL,
  average_amount        REAL,
  period_id             INTEGER NOT NULL,
  currency_id           INTEGER NOT NULL,
  FOREIGN KEY (position_seniority_id) REFERENCES job_positions_seniorities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (source_id)             REFERENCES sources(id)                   ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (period_id)             REFERENCES period(id)                    ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (currency_id)           REFERENCES currency(id)                  ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS health_insurance (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  package_type TEXT NOT NULL,
  year_id      INTEGER NOT NULL,
  period_id    INTEGER NOT NULL,
  amount       REAL NOT NULL,
  currency_id  INTEGER NOT NULL,
  source_id    INTEGER NOT NULL,
  FOREIGN KEY (year_id)     REFERENCES years(id)    ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (period_id)   REFERENCES period(id)   ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (currency_id) REFERENCES currency(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (source_id)   REFERENCES sources(id)  ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS utilities (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  utility_type TEXT NOT NULL,
  year_id      INTEGER NOT NULL,
  period_id    INTEGER NOT NULL,
  amount       REAL NOT NULL,
  source_id    INTEGER NOT NULL,
  FOREIGN KEY (year_id)   REFERENCES years(id)   ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (period_id) REFERENCES period(id)  ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS rental_prices (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  city                TEXT NOT NULL,
  accommodation_type  TEXT,
  period_id           INTEGER NOT NULL,
  currency_id         INTEGER NOT NULL,
  min_amount          REAL,
  max_amount          REAL,
  average_amount      REAL,
  source_id           INTEGER NOT NULL,
  FOREIGN KEY (period_id)   REFERENCES period(id)   ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (currency_id) REFERENCES currency(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (source_id)   REFERENCES sources(id)  ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS fixed_costs (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  total             REAL NOT NULL,
  depreciation_time REAL,
  insurance         REAL,
  motor_vehicle_tax REAL,
  maintenance       REAL
);

CREATE TABLE IF NOT EXISTS variable_costs (
  id                     INTEGER PRIMARY KEY AUTOINCREMENT,
  total                  REAL NOT NULL,
  depreciation_kms       REAL,
  maintenance_and_repair REAL,
  fuel                   REAL
);

CREATE TABLE IF NOT EXISTS transportation_car_costs (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  type                TEXT NOT NULL,
  fixed_costs_id      INTEGER NOT NULL,
  variable_costs_id   INTEGER NOT NULL,
  total_per_month     REAL,
  average_km_per_year REAL,
  FOREIGN KEY (fixed_costs_id)    REFERENCES fixed_costs(id)    ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (variable_costs_id) REFERENCES variable_costs(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  UNIQUE (fixed_costs_id, variable_costs_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_jpd_possen   ON job_position_descriptions(position_seniority_id);
CREATE INDEX IF NOT EXISTS idx_jpd_source   ON job_position_descriptions(source_id);
CREATE INDEX IF NOT EXISTS idx_jpd_period   ON job_position_descriptions(period_id);
CREATE INDEX IF NOT EXISTS idx_jpd_currency ON job_position_descriptions(currency_id);

CREATE INDEX IF NOT EXISTS idx_hi_year     ON health_insurance(year_id);
CREATE INDEX IF NOT EXISTS idx_hi_period   ON health_insurance(period_id);
CREATE INDEX IF NOT EXISTS idx_hi_currency ON health_insurance(currency_id);
CREATE INDEX IF NOT EXISTS idx_hi_source   ON health_insurance(source_id);

CREATE INDEX IF NOT EXISTS idx_utl_year   ON utilities(year_id);
CREATE INDEX IF NOT EXISTS idx_utl_period ON utilities(period_id);
CREATE INDEX IF NOT EXISTS idx_utl_source ON utilities(source_id);

CREATE INDEX IF NOT EXISTS idx_rent_city           ON rental_prices(city);
CREATE INDEX IF NOT EXISTS idx_rent_accommodation  ON rental_prices(accommodation_type);
CREATE INDEX IF NOT EXISTS idx_rent_period         ON rental_prices(period_id);
CREATE INDEX IF NOT EXISTS idx_rent_currency       ON rental_prices(currency_id);
CREATE INDEX IF NOT EXISTS idx_rent_source         ON rental_prices(source_id);
"""

def exec_schema(con: sqlite3.Connection):
    """Siempre usa SCHEMA_SQL embebido para crear las tablas."""
    con.executescript(SCHEMA_SQL)
