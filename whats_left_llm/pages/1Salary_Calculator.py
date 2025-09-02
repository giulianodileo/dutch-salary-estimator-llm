# Dutch Salary-to-Reality Calculator (Enhanced & Accessible)

import streamlit as st
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from whats_left_llm.calculator_core import get_estimates, DB_URI
from whats_left_llm.calculate_30_rule import expat_ruling_calc

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

st.title("Salary Calculator")

# Load options from the database
opts = load_options(DB_URI)
if not any(opts.values()):
    st.error("I cannot find the database, or the tables are empty. Please ensure that you have created it and uploaded the JSONs.")
    st.stop()


# st.markdown(
#     """
#     <style>
#     .big-labels label {
#         font-size: 200px !important;
#         font-weight: 600 !important;
#     }
#     </style>
#     """,
#     unsafe_allow_html=True
# )
# --------------------- INPUTS -------------------
# Aquí aplicamos la clase "input-details" a un contenedor
# st.markdown("<div class='big-labels'>", unsafe_allow_html=True)
with st.container():
    user_name = st.text_input("What's your name?", "")
    if user_name:
        st.success(f"Welcome, {user_name}! 😎")

    age = st.number_input("What is your age?", min_value=18, max_value=70, step=1)

    has_masters_nl = False
    if age < 30:
        choice = st.radio("Do you have a Master’s Degree?", ["Yes", "No"])
        has_masters_nl = (choice == "Yes")

    job = st.selectbox("Job", opts["jobs"])
    seniority = st.selectbox("Seniority", opts["seniorities"])
    city = st.selectbox("City", opts["cities"])
    accommodation_type = st.selectbox("Accommodation", opts["accommodations"])
    has_car = st.radio("Do you have a car?", ["No", "Yes"])

    car_type = st.selectbox("Select your car type:", opts["cars"]) if has_car == "Yes" else None

    submitted = st.button("Calculate")

# st.markdown("</div>", unsafe_allow_html=True)
# --------------------- INPUTS ---------------------------
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
            master_dpl=extra["master_diploma"],
            duration=10
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
        with st.container():
            st.header("Salary informatio")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Gross Salary", f"€{out['salary']['avg']:,.0f}")
            col2.metric("Net Salary", f"€{net_first_year:,.0f}")
            col3.metric("Essential Costs", f"€{out['essential_costs']:,.0f}")
            col4.metric("Disposable", f"€{disposable_first_year:,.0f}")
        with st.container():
            st.header("Cost details")
            col1, col2, col3 = st.columns(3)
            col1.metric("Health Insurance", f"€{out['health_insurance_value']:,.0f}")
            col2.metric("Car", f"€{net_first_year:,.0f}")
            col3.metric("Rent", f"€{out['essential_costs']:,.0f}")
        with st.container():
            col1, col2, col3 = st.columns(3)
            col1.metric("Electricity", f"€{out['utilities_breakdown']['Electricity']:,.0f}")
            col2.metric("Water", f"€{out['utilities_breakdown']['Water']:,.0f}")
            col3.metric("Gas", f"€{out['utilities_breakdown']['Gas']:,.0f}")


            # ---- Details con tabs: Inputs / Extra / Outputs ----
        st.markdown("### Details")

            # (opcional) también mostrar el JSON crudo
        with st.expander("Raw payload (JSON)"):
            import json
            st.code(json.dumps(payload, indent=2), language="json")


    except ValueError as ve:
        st.warning(str(ve))
    except Exception as e:
        st.error(f"Unexpected error: {e}")
else:
    st.info("Fill in the fields and press **Calculate**.")
