import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional
import sqlite3
from pathlib import Path

DB_URI = "sqlite:///db/app.db"


# ---------- Cost calculations ---------- #

def get_estimates(
    job: str,
    seniority: str,
    city: str,
    accommodation_type: str,
    car_type: Optional[str] = None,
    *,
    db_uri: str = DB_URI,
) -> Dict[str, Any]:
    """
    Devuelve:
      - salary: {min, avg, max}
      - rent:   {min, avg, max}
      - car:    total_per_month (o 0 si no se pide)
    Lanza ValueError con mensaje claro si falta algún dato.
    """
    with _open(db_uri) as con:
        # 1) Salary
        row = con.execute(
            """
            SELECT jpd.min_amount, jpd.average_amount, jpd.max_amount
            FROM job_position_descriptions AS jpd
            JOIN job_positions_seniorities AS jps ON jpd.position_seniority_id = jps.id
            JOIN period  AS p ON jpd.period_id   = p.id
            JOIN currency AS c ON jpd.currency_id = c.id
            WHERE jps.position_name = ? COLLATE NOCASE
              AND jps.seniority     = ? COLLATE NOCASE
              AND p.type = 'monthly'
              AND c.currency_code = 'EUR'
            ORDER BY jpd.average_amount DESC
            LIMIT 1
            """,
            (job, seniority),
        ).fetchone()
        if not row:
            raise ValueError(f"No salary found for ({job}, {seniority}) in EUR/month.")
        sal_min, sal_avg, sal_max = map(lambda x: float(x or 0), row)

        # 2) Rent
        row = con.execute(
            """
            SELECT rp.min_amount, rp.average_amount, rp.max_amount
            FROM rental_prices AS rp
            JOIN period  AS p ON rp.period_id   = p.id
            JOIN currency AS c ON rp.currency_id = c.id
            WHERE rp.city               = ? COLLATE NOCASE
              AND rp.accommodation_type = ? COLLATE NOCASE
              AND p.type = 'monthly'
              AND c.currency_code = 'EUR'
            ORDER BY rp.average_amount DESC
            LIMIT 1
            """,
            (city, accommodation_type),
        ).fetchone()
        if not row:
            raise ValueError(f"No rent found for ({city}, {accommodation_type}) in EUR/month.")
        rent_min, rent_avg, rent_max = map(lambda x: float(x or 0), row)

        # 3) Car (optional)
        car_month = 0.0
        if car_type:
            row = con.execute(
                """
                SELECT total_per_month
                FROM transportation_car_costs
                WHERE type = ? COLLATE NOCASE
                LIMIT 1
                """,
                (car_type,),
            ).fetchone()
            if not row:
                raise ValueError(f"No car cost found for type '{car_type}'.")
            car_month = float(row[0] or 0)

    essential_costs = get_essential_costs(con, city, accommodation_type, car_type)
    utilities_breakdown = get_utilities_breakdown(con)
    health_insurance_value = get_health_insurance_value(con)

    return {
        "inputs": {
            "job": job,
            "seniority": seniority,
            "city": city,
            "accommodation_type": accommodation_type,
            "car_type": car_type,
        },
        "outputs": {
            "salary": {"min": sal_min, "avg": sal_avg, "max": sal_max},
            "rent":   {"min": rent_min, "avg": rent_avg, "max": rent_max},
            "car_total_per_month": car_month,
            "essential_costs": essential_costs,
            "health_insurance_value": health_insurance_value,
            "utilities_breakdown": utilities_breakdown,
        },
    }

# Open SQL data

def _open(db_uri: str) -> sqlite3.Connection:
    assert db_uri.startswith("sqlite:///")
    path = db_uri.replace("sqlite:///", "", 1)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

# Getting costs

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

# Get utilities cost

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


# Get health insutance amount
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
