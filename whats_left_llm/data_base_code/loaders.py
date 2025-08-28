# loaders.py
import json
from pathlib import Path
from typing import Optional, Union, Dict
from urllib.parse import urlparse
import sqlite3


from schema import exec_schema
from db_utils import connect_sqlite_uri

# ---------- Helpers comunes ----------
def _get_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""

def _norm_period(p: str) -> str:
    if not p:
        return "monthly"
    p = p.strip().lower()
    if p in {"month", "mensual", "per month", "monthly"}:
        return "monthly"
    if p in {"year", "annual", "anual", "per year", "yearly"}:
        return "yearly"
    if p in {"week", "weekly", "semana", "per week"}:
        return "weekly"
    return p

def _get_or_create(con: sqlite3.Connection, table: str, unique_col: str, value) -> int:
    row = con.execute(f"SELECT id FROM {table} WHERE {unique_col} = ?", (value,)).fetchone()
    if row:
        return int(row[0])
    cur = con.execute(f"INSERT INTO {table}({unique_col}) VALUES (?)", (value,))
    return int(cur.lastrowid)

def _get_or_create_source(con: sqlite3.Connection, site: Optional[str], url: str) -> int:
    site = (site or _get_domain(url) or "unknown").strip()
    row = con.execute("SELECT id FROM sources WHERE url = ?", (url,)).fetchone()
    if row:
        return int(row[0])
    con.execute("INSERT OR IGNORE INTO sources(site, url) VALUES(?, ?)", (site, url))
    return int(con.execute("SELECT id FROM sources WHERE url = ?", (url,)).fetchone()[0])

def _get_or_create_position_seniority(con: sqlite3.Connection, position: str, seniority: str) -> int:
    con.execute("""
        INSERT OR IGNORE INTO job_positions_seniorities(position_name, seniority)
        VALUES (?, ?)
    """, (position, seniority))
    return int(con.execute("""
        SELECT id FROM job_positions_seniorities
        WHERE position_name = ? AND seniority = ?
    """, (position, seniority)).fetchone()[0])

# ---------- Loaders normalizados ----------
def load_tech_salaries_normalized(con: sqlite3.Connection, json_path: Union[str, Path]):
    rows = json.loads(Path(json_path).read_text(encoding="utf-8"))
    for r in rows:
        pos = r.get("position")
        sen = r.get("seniority")
        comp = r.get("compensation", {}) or {}
        currency_code = comp.get("currency", "EUR")
        period_type = _norm_period(comp.get("period", "monthly"))
        min_amount = comp.get("min_amount")
        avg_amount = comp.get("avg_amount")
        max_amount = comp.get("max_amount")
        url = r.get("source_url", "").strip()
        site = (r.get("source_site") or _get_domain(url) or "unknown").strip()

        currency_id = _get_or_create(con, "currency", "currency_code", currency_code)
        period_id = _get_or_create(con, "period", "type", period_type)
        source_id = _get_or_create_source(con, site, url)
        possen_id = _get_or_create_position_seniority(con, pos, sen)

        con.execute("""
            INSERT INTO job_position_descriptions(
              position_seniority_id, source_id,
              min_amount, max_amount, average_amount,
              period_id, currency_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (possen_id, source_id, min_amount, max_amount, avg_amount, period_id, currency_id))
    con.commit()

def load_health_insurance_normalized(con: sqlite3.Connection, json_path: Union[str, Path]):
    r = json.loads(Path(json_path).read_text(encoding="utf-8"))
    year_val = int(str(r.get("ref_year")).strip())
    period_type = _norm_period(r.get("period", "monthly"))
    currency_code = r.get("currency", "EUR")
    amount = float(r.get("avg_amount"))
    url = r.get("source_url", "").strip()
    site = (r.get("source_site") or _get_domain(url) or "unknown").strip()
    package_type = r.get("package_type", "basic")

    year_id = _get_or_create(con, "years", "year", year_val)
    period_id = _get_or_create(con, "period", "type", period_type)
    currency_id = _get_or_create(con, "currency", "currency_code", currency_code)
    source_id = _get_or_create_source(con, site, url)

    con.execute("""
        INSERT INTO health_insurance(package_type, year_id, period_id, amount, currency_id, source_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (package_type, year_id, period_id, amount, currency_id, source_id))
    con.commit()

def load_utilities_normalized(con: sqlite3.Connection, json_path: Union[str, Path]):
    rows = json.loads(Path(json_path).read_text(encoding="utf-8"))
    for r in rows:
        util_type = r.get("category")
        amount = float(r.get("value"))
        period_type = _norm_period(r.get("period", "monthly"))
        year_val = int(r.get("year"))
        url = r.get("source_url", "").strip()
        site = (r.get("source_site") or _get_domain(url) or "unknown").strip()

        year_id = _get_or_create(con, "years", "year", year_val)
        period_id = _get_or_create(con, "period", "type", period_type)
        source_id = _get_or_create_source(con, site, url)

        con.execute("""
            INSERT INTO utilities(utility_type, year_id, period_id, amount, source_id)
            VALUES (?, ?, ?, ?, ?)
        """, (util_type, year_id, period_id, amount, source_id))
    con.commit()

def load_housing_normalized(con: sqlite3.Connection, json_path: Union[str, Path]):
    rows = json.loads(Path(json_path).read_text(encoding="utf-8"))
    for r in rows:
        city = r.get("city")
        acc = r.get("accomodation", r.get("accommodation"))  # handle typo
        currency_code = r.get("currency", "EUR")
        period_type = _norm_period(r.get("period", "monthly"))
        url = r.get("source_url", "").strip()
        site = (r.get("source_site") or _get_domain(url) or "unknown").strip()

        if {"min_amount", "avg_amount", "max_amount"}.issubset(r.keys()):
            min_amount, avg_amount, max_amount = r["min_amount"], r["avg_amount"], r["max_amount"]
        else:
            min_amount, avg_amount, max_amount = r.get("min_price"), r.get("avg_price"), r.get("max_price")

        currency_id = _get_or_create(con, "currency", "currency_code", currency_code)
        period_id = _get_or_create(con, "period", "type", period_type)
        source_id = _get_or_create_source(con, site, url)

        con.execute("""
            INSERT INTO rental_prices(
                city, accommodation_type, period_id, currency_id,
                min_amount, max_amount, average_amount, source_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (city, acc, period_id, currency_id, min_amount, max_amount, avg_amount, source_id))
    con.commit()

def load_nibud_car_cost_normalized(con: sqlite3.Connection, json_path: Union[str, Path]):
    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    outer = payload[0] if isinstance(payload, list) else payload
    for row in outer.get("data", []):
        car_type = row.get("class_name")
        fx = row.get("fixed_costs", {}) or {}
        vx = row.get("variable_costs", {}) or {}

        cur_fx = con.execute("""
            INSERT INTO fixed_costs(total, depreciation_time, insurance, motor_vehicle_tax, maintenance)
            VALUES (?, ?, ?, ?, ?)
        """, (fx.get("total"), fx.get("depreciation_time"), fx.get("insurance"),
              fx.get("motor_vehicle_tax"), fx.get("maintenance")))
        fixed_id = int(cur_fx.lastrowid)

        cur_vx = con.execute("""
            INSERT INTO variable_costs(total, depreciation_kms, maintenance_and_repair, fuel)
            VALUES (?, ?, ?, ?)
        """, (vx.get("total"), vx.get("depreciation_kms"), vx.get("maintenance_and_repair"), vx.get("fuel")))
        var_id = int(cur_vx.lastrowid)

        con.execute("""
            INSERT INTO transportation_car_costs(
                type, fixed_costs_id, variable_costs_id, total_per_month, average_km_per_year
            ) VALUES (?, ?, ?, ?, ?)
        """, (car_type, fixed_id, var_id, row.get("total_per_month"), row.get("average_km_per_year")))
    con.commit()

def ingest_new_jsons(
    db_uri: str = "sqlite:///db/app.db",
    files: Dict[str, Union[str, Path]] = None,
):
    """
    Carga nuevos JSONs en una DB ya existente.
    Espera keys: {'gd','ps','hi','util','housing','car'}.
    NO recrea la base, NO toca datos existentes.
    """
    sqlite_path = db_uri.replace("sqlite:///", "", 1)
    if not Path(sqlite_path).exists():
        raise FileNotFoundError(f"No existe la DB en {sqlite_path}. Corre build_normalized_main_db primero.")

    if not files:
        print("⚠️ No se pasaron archivos para ingerir.")
        return

    # Mapa clave -> loader correspondiente
    _LOADER = {
        "gd": load_tech_salaries_normalized,     # Glassdoor salaries
        # "ps": load_tech_salaries_normalized,     # PayScale salaries
        # "hi": load_health_insurance_normalized,  # Health insurance
        # "util": load_utilities_normalized,       # Utilities
        # "housing": load_housing_normalized,      # Housing prices
        # "car": load_nibud_car_cost_normalized,   # Car costs
    }

    with connect_sqlite_uri(db_uri) as con:
        for key, path in files.items():
            loader = _LOADER.get(key)
            if not loader:
                print(f"⚠️ Clave desconocida '{key}'. Usa una de: {list(_LOADER)}. Omitido.")
                continue

            p = Path(path)
            if not p.exists():
                print(f"⚠️ No existe JSON: {p}. Omitido.")
                continue

            loader(con, p)
            print(f"✅ Ingerido: {key} <- {p}")


def build_normalized_main_db(
    db_uri: str = "sqlite:///db/app.db",
    data_dir: Optional[Union[str, Path]] = None,
    filenames: Dict[str, str] = None,
):
    """
    Crea la DB normalizada y carga todos los JSONs
    SOLO si la DB no existe todavía.
    """
    defaults = {
        "gd": "data/clean_data/gd_tech_salaries.json",
        "ps": "data/clean_data/ps_tech_salaries.json",
        "hi": "data/clean_data/health_insurance.json",
        "housing": "data/clean_data/housing_prices.json",
        "util": "data/clean_data/nibud_utilities.json",
        "car": "data/clean_data/nibud_car_cost.json",
    }
    if filenames:
        defaults.update(filenames)

    sqlite_path = db_uri.replace("sqlite:///", "", 1)

    # ✅ No hacer nada si ya existe la DB
    if Path(sqlite_path).exists():
        print(f"ℹ️ DB ya existe en {sqlite_path}, no se reconstruye ni se recargan JSONs.")
        return

    base = Path(data_dir) if data_dir else None

    with connect_sqlite_uri(db_uri) as con:
        # 1. Aplica el esquema embebido
        exec_schema(con)

        # 2. Helper para rutas relativas
        def _pick(path_str: str) -> Path:
            p = Path(path_str)
            if p.is_absolute():
                return p
            return (base / p) if base else p

        # 3. Carga cada JSON en su tabla si existe
        p = _pick(defaults["gd"])
        if p.exists(): load_tech_salaries_normalized(con, p)

        p = _pick(defaults["ps"])
        if p.exists(): load_tech_salaries_normalized(con, p)

        p = _pick(defaults["hi"])
        if p.exists(): load_health_insurance_normalized(con, p)

        p = _pick(defaults["util"])
        if p.exists(): load_utilities_normalized(con, p)

        p = _pick(defaults["housing"])
        if p.exists(): load_housing_normalized(con, p)

        p = _pick(defaults["car"])
        if p.exists(): load_nibud_car_cost_normalized(con, p)

    print(f"✅ DB creada y cargada: {sqlite_path}")
