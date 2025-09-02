# Dutch Salary-to-Reality Calculator (Enhanced & Accessible)

import streamlit as st
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from whats_left_llm.calculator_core import get_estimates, DB_URI
from whats_left_llm.calculate_30_rule import expat_ruling_calc
from ui_charts import (
    render_salary_projection_chart,
    render_bar_chart_30_rule,
    render_pie_chart_percent_only,
    render_income_projection
)


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

        # Debug: check essential costs keys and values
        st.write("Debug: Essential costs breakdown", {
            "housing_costs": out.get('housing_costs'),
            "transportation_costs": out.get('transportation_costs'),
            "utilities_costs": out.get('utilities_costs'),
            "other_costs": out.get('other_costs'),
        })

        extra = {
            "age": int(age),
            "master_diploma": bool(has_masters_nl)
        }

        res_tax = expat_ruling_calc(
            age=extra["age"],
            gross_salary=out['salary']['avg'] * 12,
            master_dpl=extra["master_diploma"],
            duration=10
        )

        # 30% ruling eligibility message + LLM link button
        if extra["age"] < 30 and has_masters_nl:
            st.success("You are eligible for the 30% ruling! 🎉")
            if st.button("Learn why you're eligible for the 30% ruling"):
                st.session_state["llm_question"] = "Why am I eligible for the 30% ruling in the Netherlands?"
                st.experimental_set_query_params(page=":robot_face: Salary & Budget Chat")
        else:
            st.info("Based on your input, you are not eligible for the 30% ruling.")

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

        # ---- Bar chart comparing salary with and without 30% ruling ----
        salary_data = {
            "Year": list(res_tax.keys()),
            "Salary": [val / 12 for val in res_tax.values()],
            "Salary_30_rule": [val * 0.7 / 12 for val in res_tax.values()]  # example 30% ruling effect
        }

        render_bar_chart_30_rule(salary_data)

        # ---- Pie chart for essential living costs breakdown ----
        labels = ["Housing Costs", "Transportation", "Utilities", "Other"]
        values = [
            out.get('housing_costs', 0),
            out.get('transportation_costs', 0),
            out.get('utilities_costs', 0),
            out.get('other_costs', 0)
        ]
        if sum(values) > 0:
            render_pie_chart_percent_only(labels, values, "Essential Living Costs Breakdown")
        else:
            st.info("Essential living costs data is not available.")

        # ---- Disposable income gauge ----
        leftover = disposable_first_year
        net = net_first_year
        disposable_pct = max(0, leftover / net * 100) if net > 0 else 0

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=disposable_pct,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Disposable Income %"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "green"},
                'steps': [
                    {'range': [0, 20], 'color': 'red'},
                    {'range': [20, 50], 'color': 'orange'},
                    {'range': [50, 100], 'color': 'lightgreen'}
                ],
                'threshold': {
                    'line': {'color': "blue", 'width': 4},
                    'thickness': 0.75,
                    'value': disposable_pct
                }
            }
        ))
        st.plotly_chart(fig, use_container_width=True)

        # ---- Savings recommendation ----
        st.markdown("### 💰 Suggested Savings")
        if leftover <= 0:
            st.warning("You are spending all of your net income. Consider reducing housing, essentials, or car costs.")
        elif leftover / net < 0.2:
            st.info("Your disposable income is low. Aim to save at least 5-10% of your net salary.")
        elif leftover / net < 0.4:
            st.success("Good! You can save 15-25% of your net salary each month.")
        else:
            st.success("Excellent! You have a high disposable income. Consider saving 25-40% or investing for growth.")

        # ---- Details con tabs: Inputs / Extra / Outputs ----
        st.markdown("### Details")

        # Raw JSON payload expander
        with st.expander("Raw payload (JSON)"):
            import json
            st.code(json.dumps(payload, indent=2), language="json")

    except ValueError as ve:
        st.warning(str(ve))
    except Exception as e:
        st.error(f"Unexpected error: {e}")

else:
    st.info("Fill in the fields and press **Calculate**.")
