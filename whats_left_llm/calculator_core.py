# calculator_core.py
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any

DB_URI = "sqlite:///db/app.db"

def _open(db_uri: str) -> sqlite3.Connection:
    assert db_uri.startswith("sqlite:///")
    path = db_uri.replace("sqlite:///", "", 1)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def get_essential_costs(con: sqlite3.Connection, city: str, accommodation_type: str, car_type: Optional[str]) -> float:
    total = 0.0

    # --- 1) Rent ---
    rent = con.execute("""
        SELECT AVG(average_amount)
        FROM rental_prices
        WHERE city = ? AND accommodation_type = ?;
    """, (city, accommodation_type)).fetchone()[0]
    total += rent or 0

    # --- 2) Utilities (sumar todas las categorías) ---
    utilities = con.execute("""
        SELECT SUM(amount)
        FROM utilities;
    """).fetchone()[0]
    total += utilities or 0

    # --- 3) Car costs (si aplica) ---
    if car_type:
        car = con.execute("""
            SELECT AVG(total_per_month)
            FROM transportation_car_costs
            WHERE type = ?;
        """, (car_type,)).fetchone()[0]
        total += car or 0

    # --- 4) Health insurance ---
    hi = con.execute("""
        SELECT AVG(amount)
        FROM health_insurance;
    """).fetchone()[0]
    total += hi or 0

    return total

def get_utilities_breakdown(con: sqlite3.Connection) -> Dict[str, float]:
    """
    Devuelve un dict con los valores de utilities separados por categoría:
    { "Water": 25.9, "Gas": 50.0, "Electricity": 80.0 }
    """
    rows = con.execute("""
        SELECT utility_type, SUM(amount)
        FROM utilities
        GROUP BY utility_type;
    """).fetchall()

    breakdown = {row[0]: row[1] for row in rows}
    return breakdown


def get_health_insurance_value(con: sqlite3.Connection):
    """
    Devuelve el valor de health insurance (si solo hay un registro en la tabla).
    """
    row = con.execute("""
        SELECT amount
        FROM health_insurance
        LIMIT 1;
    """).fetchone()

    return row[0]
