# Dutch Salary-to-Reality Calculator (Enhanced & Accessible)

import streamlit as st
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from calculator_core import get_estimates, DB_URI
from calculate_30_rule import expat_ruling_calc

COLOR_PALETTE = ["#2E91E5", "#E15F99", "#1CA71C", "#FB0D0D"]
# -------------------- DB HELPERS --------------------
def _sqlite_path(db_uri: str) -> str:
    assert db_uri.startswith("sqlite:///")
    return db_uri.replace("sqlite:///", "", 1)

def _open(db_uri: str) -> sqlite3.Connection:
    path = _sqlite_path(db_uri)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def load_options(db_uri: str = DB_URI) -> Dict[str, List[str]]:
    opts = {"jobs": [], "seniorities": [], "cities": [], "accommodations": [], "cars": []}
    path = _sqlite_path(db_uri)
    if not Path(path).exists():
        return opts

    with _open(db_uri) as con:
        rows = con.execute("SELECT DISTINCT position_name FROM job_positions_seniorities ORDER BY position_name;").fetchall()
        opts["jobs"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT seniority FROM job_positions_seniorities ORDER BY seniority;").fetchall()
        opts["seniorities"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT city FROM rental_prices ORDER BY city;").fetchall()
        opts["cities"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT accommodation_type FROM rental_prices WHERE accommodation_type IS NOT NULL ORDER BY accommodation_type;").fetchall()
        opts["accommodations"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT type FROM transportation_car_costs ORDER BY type;").fetchall()
        opts["cars"] = [r[0] for r in rows]

    return opts

opts = load_options(DB_URI)
if not any(opts.values()):
    st.error("Database not found or empty. Load it before using the app.")
    st.stop()


# -------------------- PAGE 1: SALARY CALCULATOR --------------------

def render():
    st.title(":euro: Dutch Salary-to-Reality Calculator")

    # Load options from the database
    opts = load_options(DB_URI)
    if not any(opts.values()):
        st.error("I cannot find the database, or the tables are empty. Please ensure that you have created it and uploaded the JSONs.")
        st.stop()

    # Sidebar inputs
    user_name = st.sidebar.text_input("What's your name?", "")
    if user_name:
        st.sidebar.success(f"Welcome, {user_name}! :sunglasses:")

    age = st.sidebar.number_input("What is your age?", min_value=18, max_value=70, step=1)
    has_masters_nl = False
    if age < 30:
        choice = st.sidebar.radio("Do you have a Master’s Degree (NL or equivalent)?", ["Yes", "No"])
        has_masters_nl = (choice == "Yes")

    job = st.sidebar.selectbox("Job Role", opts["jobs"])
    seniority = st.sidebar.selectbox("Seniority", opts["seniorities"])
    city = st.sidebar.selectbox("City", opts["cities"])
    accommodation_type = st.sidebar.selectbox("Accommodation Type", opts["accommodations"])
    has_car = st.sidebar.radio("Do you have a car?", ["No", "Yes"])
    car_type = st.sidebar.selectbox("Select your car type:", opts["cars"]) if has_car == "Yes" else None

    submitted = st.sidebar.button("Calculate")

    if submitted:
        try:
            res: Dict[str, Any] = get_estimates(
                job=job,
                seniority=seniority,
                city=city,
                accommodation_type=accommodation_type,
                car_type=car_type,
                db_uri=DB_URI
            )
            out = res["outputs"]

            extra = {
                "age": int(age),
                "master_diploma": bool(has_masters_nl)}

            res_tax = expat_ruling_calc(
                age=extra["age"],
                gross_salary=out['salary']['avg']*12,
                master_dpl=extra["master_diploma"], duration=10
            )

            # First year values
            first_year = min(res_tax.keys())
            net_first_year = res_tax[first_year] / 12
            disposable_first_year = net_first_year - out['essential_costs']

            payload = {
                "inputs": res["inputs"],
                "extra": extra,
                "outputs": out,
                "tax dict": res_tax,
                "net tax": net_first_year
            }
            st.session_state["last_payload"] = payload

            # ---- Metrics ----
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Gross Salary", f"€{out['salary']['avg']:,.0f}")
            col2.metric("Net Salary (2026)", f"€{net_first_year:,.0f}")
            col3.metric("Essential Costs", f"€{out['essential_costs']:,.0f}")
            col4.metric("Disposable (2026)", f"€{disposable_first_year:,.0f}")


        except ValueError as ve:
            st.warning(str(ve))
        except Exception as e:
            st.error(f"Unexpected error: {e}")
    else:
        st.info("Fill in the fields and press **Calculate**.")
