# Dutch Salary-to-Reality Calculator (Enhanced & Accessible)

import streamlit as st
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from whats_left_llm.calculator_core import get_estimates, DB_URI
from whats_left_llm.calculate_30_rule import expat_ruling_calc
from whats_left_llm.ui_charts import render_pie_chart_percent_only, render_bar_chart_giuliano
from whats_left_llm.chart import chart_netincome


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

st.markdown("### Money in your pocket")

# Load options from the database
opts = load_options(DB_URI)
if not any(opts.values()):
    st.error("I cannot find the database, or the tables are empty. Please ensure that you have created it and uploaded the JSONs.")
    st.stop()

with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        user_name = st.text_input("Name", "")
    if user_name:
        st.success(f"Welcome, {user_name}! 😎")
    with col2:
        age = st.number_input("Age", min_value=18, max_value=70, step=1)
    with col1:
        job = st.selectbox("Job", opts["jobs"])
    with col2:
        seniority = st.selectbox("Seniority", opts["seniorities"])
    with col1:
        city = st.selectbox("City", opts["cities"])
    with col2:
        accommodation_type = st.selectbox("Accommodation", opts["accommodations"])
    with col1:
        has_masters_nl = st.selectbox("Master's degree", ["Yes", "No"])
    with col2:
        car_type = st.selectbox("Car type", ["No"] + opts["cars"])
        if car_type == "No":
            car_cost = 0
        else:
            car_cost = car_type
    submitted = st.button("What's left")

def check_degree_requirement(age: int, has_degree: str) -> bool:
    if age < 30 and has_degree == "Yes":
        return True
    return False

degre_value = check_degree_requirement(age, has_masters_nl)

# --------------------- INPUTS ---------------------------
if submitted:
    try:
        res: Dict[str, Any] = get_estimates(
            job=job,
            seniority=seniority,
            city=city,
            accommodation_type=accommodation_type,
            car_type=car_cost,
            db_uri=DB_URI
        )
        out = res["outputs"]

        extra = {
            "age": int(age),
            "master_diploma": bool(degre_value)
        }

        res_tax = expat_ruling_calc(
            age=extra["age"],
            gross_salary=out['salary']['avg'] * 12,
            master_dpl=extra["master_diploma"],
            duration=6
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
        car_value = payload["outputs"]["car_total_per_month"]

        # ---- Metrics ----
        with st.container(border=True):

            st.markdown(
                """
                <style>
                [data-testid="stMetricValue"] {
                    font-size: 24px;
                }
                [data-testid="stMetricLabel"] {
                    font-size: 20px;
                    font-weight: 600;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

            st.markdown("#### Whats left")
            col1, col2 = st.columns(2)
            col2.metric("Net salary", f"€{net_first_year:,.0f}")
            col2.metric("Money in your pocket", f"€{disposable_first_year:,.0f}")
            col1.metric("Gross salary", f"€{out['salary']['avg']:,.0f}")
            col1.metric("Costs", f"€{out['essential_costs']:,.0f}")
            with st.container():
                with st.expander("What are your costs?"):
                    col1, col2 = st.columns(2)
                    with col1:
                        subcol1, subcol2 = st.columns(2)
                        with subcol1:
                            subcol1.metric("Rent", f"€{out['rent']['avg']:,.0f}")
                            subcol1.metric("Car", f"€{car_value:,.0f}")
                            subcol1.metric("Health Insurance", f"€{out['health_insurance_value']:,.0f}")
                        with subcol2:
                            subcol2.metric("Gas", f"€{out['utilities_breakdown']['Gas']:,.0f}")
                            subcol2.metric("Electricity", f"€{out['utilities_breakdown']['Electricity']:,.0f}")
                            subcol2.metric("Water", f"€{out['utilities_breakdown']['Water']:,.0f}")
                    with col2:
                        # ------------------ Thabisso ---------------------------
                        labels = ["Rent", "Car", "Health Insurance", "Gas", "Electricity", "Water"]
                        utilities = out['utilities_breakdown']
                        values = [
                            out['rent']['avg'],
                            out['car_total_per_month'],
                            utilities.get("Gas", 0),
                            utilities.get("Electricity", 0),
                            utilities.get("Water", 0),
                            out['health_insurance_value']
                        ]
                        render_pie_chart_percent_only(labels, values)



        with st.container():
            chart_netincome(res_tax, out['essential_costs']*12, age, out['salary']['avg']*12, degre_value)

        #                         # ---- Details con tabs: Inputs / Extra / Outputs ----
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
    st.info("Fill in the fields and press **What's left**.")


# PALETTE = {
#     "navy":   "#03045E",
#     "blue9":  "#023E8A",
#     "blue7":  "#0077B6",
#     "blue6":  "#0096C7",
#     "blue5":  "#00B4D8",
#     "blue4":  "#48CAE4",
#     "blue3":  "#90E0EF",
#     "blue2":  "#ADE8F4",
#     "blue1":  "#CAF0F8",
# }
