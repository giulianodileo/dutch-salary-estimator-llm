# nlsql_multi_json_multi_db_core.py
# ------------------------------------------------------------
# NL -> SQL across MULTIPLE JSON-backed SQLite DBs + a normalized main DB
# - Works with LangChain (SQLDatabase utility) and Gemini via init_chat_model
# - Includes JSON->SQLite loaders and normalized schema ingestion for your schema.sql
# ------------------------------------------------------------

import os, re, json, sqlite3, ast, tempfile
from typing import Optional, Union, List, Dict, Any, Tuple
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from pandas import DataFrame
from typing_extensions import TypedDict, Annotated

# ========= LangChain / LLM =========
try:
    from langchain_community.utilities import SQLDatabase     # uses SQLAlchemy under the hood
    from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
    from langchain.chat_models import init_chat_model
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
except Exception as e:
    raise ImportError(
        "LangChain packages missing. Install deps with:\n"
        "  pip install -U langchain langchain-community langchain-core sqlalchemy\n"
        "Also install LLM provider:\n"
        "  pip install -U google-generativeai\n"
    ) from e

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

CREATE TABLE IF NOT EXISTS patrols (
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

# =========================
# JSON ingestion utilities (RAW MODE)
# =========================

def json_to_dataframe(path: str, array_key: Optional[str] = None) -> DataFrame:
    with open(path, "r", encoding="utf-8") as f:
        payload: Union[List[Any], Dict[str, Any]] = json.load(f)

    if isinstance(payload, list):
        return pd.json_normalize(payload)

    if isinstance(payload, dict):
        if array_key and array_key in payload and isinstance(payload[array_key], list):
            return pd.json_normalize(payload[array_key])
        # auto-pick first list of dicts
        for _, v in payload.items():
            if isinstance(v, list) and (not v or all(isinstance(x, dict) for x in v)):
                return pd.json_normalize(v)
        return pd.json_normalize(payload)

    raise ValueError("Unsupported JSON structure. Expected list or dict at root.")

def ensure_columns_snake(df: DataFrame) -> DataFrame:
    df = df.copy()
    df.columns = [re.sub(r"\W+", "_", str(c)).strip("_").lower() for c in df.columns]
    for c in df.columns:
        if pd.api.types.is_object_dtype(df[c]):
            try:
                df[c] = pd.to_numeric(df[c])
            except Exception:
                pass
    return df

def write_df_to_sqlite(df: DataFrame, db_uri: str, table: str):
    assert db_uri.startswith("sqlite:///"), "Use a sqlite:/// URI"
    sqlite_path = db_uri.replace("sqlite:///", "", 1)
    os.makedirs(os.path.dirname(sqlite_path) or ".", exist_ok=True)
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        df.to_sql(table, conn, if_exists="replace", index=False)

# =========================
# Multi-DB helpers
# =========================

def attach_sqlite_dbs(db: SQLDatabase, attachments: List[Tuple[str, str]]):
    """ATTACH extra SQLite files to the active connection: [(path, alias), ...]."""
    for path, alias in attachments:
        safe_alias = re.sub(r"\W+", "_", alias.strip())
        path_sql = path.replace("'", "''")
        db.run(f"ATTACH DATABASE '{path_sql}' AS {safe_alias};")

def _safe_eval_rows(s: str):
    try:
        return ast.literal_eval(s)
    except Exception:
        return []

def sqlite_schema_with_attachments(db: SQLDatabase) -> str:
    """Return a schema string for 'main' and all ATTACHed DBs. Robust to envs."""
    aliases = ["main"]
    try:
        dblist = db.run("PRAGMA database_list;")
        rows = _safe_eval_rows(dblist)
        parsed = [r[1] for r in rows if isinstance(r, (list, tuple)) and len(r) >= 2]
        if parsed:
            aliases = parsed
    except Exception:
        pass
    if aliases == ["main"]:
        try:
            dblist2 = db.run("SELECT seq, name, file FROM pragma_database_list;")
            rows2 = _safe_eval_rows(dblist2)
            parsed2 = [r[1] for r in rows2 if isinstance(r, (list, tuple)) and len(r) >= 2]
            if parsed2:
                aliases = parsed2
        except Exception:
            pass

    lines = []
    for alias in aliases:
        try:
            tbls_repr = db.run(
                f"SELECT name FROM {alias}.sqlite_master WHERE type='table' ORDER BY name;"
            )
            tbl_rows = _safe_eval_rows(tbls_repr)
            tables = [t for (t, *_) in tbl_rows if isinstance(t, str)]
        except Exception:
            tables = []

        if not tables:
            if alias == "main":
                try:
                    main_info = db.get_table_info()
                    if main_info.strip():
                        lines.append("-- Database: main")
                        lines.append(main_info.strip())
                        lines.append("")
                        continue
                except Exception:
                    pass
            continue

        lines.append(f"-- Database: {alias}")
        for t in tables:
            try:
                cols_repr = db.run(f"PRAGMA {alias}.table_info('{t}');")
                cols = _safe_eval_rows(cols_repr)  # (cid,name,type,notnull,dflt,pk)
                col_str = ", ".join(
                    f"{c[1]} {c[2] or ''}".strip()
                    for c in cols
                    if isinstance(c, (list, tuple)) and len(c) >= 3
                )
                if not col_str:
                    col_str = "(unknown_columns)"
                lines.append(f"TABLE {alias}.{t}({col_str})")
            except Exception:
                lines.append(f"TABLE {alias}.{t}(?)")
        lines.append("")

    if not lines:
        try:
            main_info = db.get_table_info()
            if main_info.strip():
                lines.append("-- Database: main")
                lines.append(main_info.strip())
        except Exception:
            lines.append("-- Database: main")
    return "\n".join(lines).strip()

# =========================
# LLM & chains
# =========================

def init_llm():
    # Requires GOOGLE_API_KEY in env for google_genai provider
    if not os.getenv("GOOGLE_API_KEY"):
        raise EnvironmentError(
            "Missing GOOGLE_API_KEY. Set it in your environment, e.g.:\n"
            "  export GOOGLE_API_KEY='your-key-here'"
        )
    return init_chat_model("gemini-2.5-flash", model_provider="google_genai")

class QueryOutput(TypedDict):
    query: Annotated[str, ..., "Return ONLY a valid SQL query. No markdown, no prose."]

def strip_fences(q: str) -> str:
    if not q: return ""
    q = q.strip()
    q = re.sub(r"^```(?:\w+)?\s*", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\s*```$", "", q)
    return q.strip()

DB_HINT_RE = re.compile(
    r"\b(salary|salaries|position|seniority|avg|average|min|max|median|count|sum|"
    r"top|by|group|filter|where|roles?|engineer|scientist|mlops|data|pay|compensation|"
    r"premium|insurance|health|rent|housing|accommodation|utilities?|gas|electricity|water|"
    r"car|vehicle|fuel|maintenance|depreciation)\b",
    re.IGNORECASE,
)

def is_db_question(q: str) -> bool:
    return bool(DB_HINT_RE.search(q or ""))

SQL_SYSTEM = """
You are a SQL generator for a jobs & living-costs advisor assistant.
Output ONLY a syntactically correct {dialect} SQL query based on the latest user question.
NEVER invent tables or columns.

Multiple databases may be present. Always reference tables with dbalias.table
(e.g., main.jobs, ins.plans, rent.costs). If tables lack join keys, avoid joins:
prefer per-table aggregation and combine using UNION ALL; or alias columns to a
common name and aggregate across the UNION ALL result.

Schema (databases, tables & columns):
{table_info}
"""
SQL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SQL_SYSTEM),
    MessagesPlaceholder("history"),
    ("user", "Question: {question}\nReturn ONLY a SQL query."),
])

ANSWER_PROMPT = ChatPromptTemplate.from_template(
    "You are a professional jobs & salaries advisor.\n\n"
    "User question: {question}\n\n"
    "SQL executed:\n```sql\n{sql}\n```\n"
    "Raw result: {raw}\n\n"
    "Provide a concise, professional answer."
)

CASUAL_SYSTEM = """
You are a professional, friendly jobs & salaries advisor.
- Keep replies brief and conversational.
- Do NOT fabricate data or query results.
- Do NOT include SQL in your response.
"""
CASUAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", CASUAL_SYSTEM),
    MessagesPlaceholder("history"),
    ("user", "{input}"),
])

def build_sql_writer(db: SQLDatabase, llm):
    schema_text = sqlite_schema_with_attachments(db)
    return (
        SQL_PROMPT.partial(dialect=db.dialect, table_info=schema_text)
        | llm.with_structured_output(QueryOutput)
    )

def build_casual_chain(llm):
    return CASUAL_PROMPT | llm

def execute_sql(db: SQLDatabase, sql: str):
    tool = QuerySQLDatabaseTool(db=db)
    try:
        return tool.invoke(sql)
    except Exception as e:
        return f"ERROR: {e}"

def answer_from_result(llm, question: str, sql: str, raw_result: str) -> str:
    if isinstance(raw_result, str) and raw_result.startswith("ERROR:"):
        return f"Query failed.\n\n```sql\n{sql}\n```\n{raw_result}"
    return llm.invoke(
        ANSWER_PROMPT.invoke({"question": question, "sql": sql, "raw": raw_result})
    ).content

# =========================
# NORMALIZED SCHEMA INGESTION (YOUR NEW SCHEMA)
# =========================

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

def _connect_sqlite_uri(db_uri: str) -> sqlite3.Connection:
    assert db_uri.startswith("sqlite:///"), "Use a sqlite:/// URI"
    sqlite_path = db_uri.replace("sqlite:///", "", 1)
    os.makedirs(os.path.dirname(sqlite_path) or ".", exist_ok=True)
    con = sqlite3.connect(sqlite_path)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def _exec_schema(con: sqlite3.Connection, schema_sql_path: Union[str, Path, None]):
    """
    Si schema_sql_path no existe, usa SCHEMA_SQL embebido.
    """
    schema_text = None
    if schema_sql_path:
        p = Path(schema_sql_path)
        if not p.is_absolute():
            # prueba cwd y junto al propio archivo
            p_candidates = [p, Path.cwd() / p, Path(__file__).resolve().parent / p]
        else:
            p_candidates = [p]
        for c in p_candidates:
            if c.exists():
                schema_text = c.read_text(encoding="utf-8")
                break

    if schema_text is None:
        # fallback embebido
        schema_text = SCHEMA_SQL

    con.executescript(schema_text)

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

def build_normalized_main_db(
    db_uri: str,
    schema_sql_path: Union[str, Path],
    data_dir: Union[str, Path] = "data/raw",
    filenames: Dict[str, str] = None,
):
    """
    Crea/reescribe la DB normalizada (según schema.sql) y carga todos los JSON.
    db_uri: e.g. 'sqlite:///db/app.db'
    schema_sql_path: ruta a tu schema.sql
    data_dir: carpeta base de JSONs
    filenames: mapping opcional si usas otros nombres
    """
    defaults = {
        "gd": "/Users/andresgentile/code/giulianodileo/dutch-salary-estimator-llm/data/clean_data/gd_tech_salaries.json",
        "ps": "/Users/andresgentile/code/giulianodileo/dutch-salary-estimator-llm/data/clean_data/ps_tech_salaries.json",
        "hi": "/Users/andresgentile/code/giulianodileo/dutch-salary-estimator-llm/data/clean_data/health_insurance.json",
        "housing": "/Users/andresgentile/code/giulianodileo/dutch-salary-estimator-llm/data/clean_data/housing_prices.json",
        "util": "/Users/andresgentile/code/giulianodileo/dutch-salary-estimator-llm/data/clean_data/nibud_utilities.json",
        "car": "/Users/andresgentile/code/giulianodileo/dutch-salary-estimator-llm/data/clean_data/nibud_car_cost.json",
    }
    base = Path(data_dir) if data_dir else None
    with _connect_sqlite_uri(db_uri) as con:
        _exec_schema(con, schema_sql_path)

        def _pick(path_str: str) -> Path:
            p = Path(path_str)
            if p.is_absolute():
                return p
            return (base / p) if base else p

        # Glassdoor
        p = _pick(defaults["gd"])
        if p.exists(): load_tech_salaries_normalized(con, p)

        # PayScale
        p = _pick(defaults["ps"])
        if p.exists(): load_tech_salaries_normalized(con, p)

        # Health insurance
        p = _pick(defaults["hi"])
        if p.exists(): load_health_insurance_normalized(con, p)

        # Utilities
        p = _pick(defaults["util"])
        if p.exists(): load_utilities_normalized(con, p)

        # Housing
        p = _pick(defaults["housing"])
        if p.exists(): load_housing_normalized(con, p)

        # Car costs
        p = _pick(defaults["car"])
        if p.exists(): load_nibud_car_cost_normalized(con, p)


# =========================
# RAW JSON MODE (optional quick demos)
# =========================

def make_main_db_from_json(json_path: str, db_uri: str, table: str, array_key: Optional[str] = None) -> DataFrame:
    df = ensure_columns_snake(json_to_dataframe(json_path, array_key=array_key))
    if df.empty:
        raise ValueError("Main JSON produced an empty DataFrame.")
    write_df_to_sqlite(df, db_uri, table)
    return df

def make_extra_db_from_json(json_path: str, out_dbfile: str, table: str, array_key: Optional[str] = None) -> DataFrame:
    df = ensure_columns_snake(json_to_dataframe(json_path, array_key=array_key))
    if df.empty:
        raise ValueError(f"Extra JSON produced an empty DataFrame: {json_path}")
    write_df_to_sqlite(df, f"sqlite:///{out_dbfile}", table)
    return df

# =========================
# Minimal demo entrypoint
# =========================

def demo_query_normalized():
    """Tiny demo: build normalized DB and run one NL->SQL question."""
    # 1) Build DB from your JSONs + schema
    build_normalized_main_db(
        db_uri="sqlite:///db/app.db",
        schema_sql_path=None,
        data_dir=None,
    )

    # 2) Connect and ask a question
    db = SQLDatabase.from_uri("sqlite:///db/app.db")
    llm = init_llm()
    writer = build_sql_writer(db, llm)

    question = "tell me the highest salary and the hights cost of renting in amsterdam"
    res = writer.invoke({"history": [], "question": question})
    sql = strip_fences(res["query"])
    raw = execute_sql(db, sql)
    answer = answer_from_result(llm, question, sql, raw)
    print("SQL:\n", sql)
    print("\nANSWER:\n", answer)

if __name__ == "__main__":
    # Run a quick demo if executed as a script
    demo_query_normalized()
