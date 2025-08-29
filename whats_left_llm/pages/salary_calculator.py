# pages/salary_calculator.py
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import datetime as dt
import sqlite3
from pathlib import Path
from typing import Dict, Any, List
from calculator_core import get_estimates, DB_URI
from calculate_30_rule import expat_ruling_calc
from chart import return_net_income

COLOR_PALETTE = ["#2E91E5", "#E15F99", "#1CA71C", "#FB0D0D"]

# ---------- Helpers de DB para poblar selects ----------

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

def render_salary_charts(expenses, leftover):
    df = pd.DataFrame({
        "Category": ["Essential + Housing Costs", "Disposable Income"],
        "Amount": [expenses, leftover]
    })
    fig = px.pie(
        df,
        values="Amount",
        names="Category",
        title=":moneybag: Expenses vs Disposable Income",
        hole=0.4,
        color="Category",
        color_discrete_map={
            "Essential + Housing Costs": "#2E91E5",
            "Disposable Income": "#1CA71C",
        },
    )
    fig.update_traces(textinfo="label+percent+value", textfont_color=["black", "white"])
    st.plotly_chart(fig, use_container_width=True)

# -------------------- PAGE 1: SALARY CALCULATOR --------------------

def render():
    st.title(":euro: Dutch Salary-to-Reality Calculator b")

    # Cargar opciones desde la BD
    opts = load_options(DB_URI)
    if not any(opts.values()):
        st.error("No encuentro la base de datos o las tablas están vacías. Asegúrate de haberla creado y cargado JSONs.")
        st.stop()

    # Sidebar Inputs
    user_name = st.sidebar.text_input("What's your name?", "")
    if user_name:
        st.sidebar.success(f"Welcome, {user_name}! :sunglasses:")

    age = st.sidebar.number_input("What is your age?", min_value=18, max_value=70, step=1)

    choice = "No"
    if age < 30:
        choice = st.sidebar.radio(
            "Do you have a Master’s Degree (or higher) obtained in the Netherlands?",
            ["Yes", "No"],
        )
    has_masters_nl = (choice == "Yes")

    job = st.sidebar.selectbox("Job Role", opts["jobs"])
    seniority = st.sidebar.selectbox("Seniority", opts["seniorities"])
    city = st.sidebar.selectbox("City", opts["cities"])
    accommodation_type = st.sidebar.selectbox("Accommodation Type", opts["accommodations"])
    has_car = st.sidebar.radio("Do you have a car?", ["No", "Yes"])
    car_type = st.sidebar.selectbox("Select your car type:", opts["cars"]) if has_car == "Yes" else 0
    expertise = True

    submitted = st.sidebar.button("Calculate")

    if submitted:
        try:
            res: Dict[str, Any] = get_estimates(
                job=job,
                seniority=seniority,
                city=city,
                accommodation_type=accommodation_type,
                car_type=car_type,
                db_uri=DB_URI,
            )
            out = res["outputs"]

            extra = {
                "age": int(age),
                "start_date_us": "2025-01-01",
                "start_date_iso": "2025-01-01",
                "duration_years": 10,
                "expertise": bool(expertise),
                "master_diploma": bool(has_masters_nl),
            }

            res_tax = expat_ruling_calc(
                age=extra["age"],
                salary=out['salary']['avg'] * 12,
                date_string=extra["start_date_iso"],
                duration=extra["duration_years"],
                expertise=extra["expertise"],
                master_dpl=extra["master_diploma"]
            )

            net_year = return_net_income(res_tax, out['essential_costs'])
            return_net_incomee = return_net_income(res_tax, out['essential_costs'])
            net_month = res_tax[2025] / 12
            payload = {
                "inputs": res["inputs"],
                "extra": extra,
                "outputs": out,
                "tax dic": res_tax,
                "net tax": net_year / 12,
                    "kpis": {
                        "gross_month": out['salary']['avg'],
                        "net_month": net_month,
                        "essential_month": out['essential_costs'],
                        "disposable_month": return_net_incomee/12,
                    },
            }
            st.session_state["last_payload"] = payload

            # KPIs
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Gross Salary", f"€{out['salary']['avg']:,.0f}")
            col2.metric("Net Salary", f"€{(res_tax[2025]/12):,.0f}")
            col3.metric("Essential Living Costs", f"€{out['essential_costs']:,.0f}")
            col4.metric("Disposable Income", f"€{net_year/12:,.0f}")

            # Chart
            render_salary_charts(out['essential_costs'], net_year)

            # Details
            st.markdown("### Details")
            with st.expander("Raw payload (JSON)"):
                st.code(json.dumps(payload, indent=2), language="json")

        except ValueError as ve:
            st.warning(str(ve))
        except Exception as e:
            st.error(f"Unexpected error: {e}")
    else:
        st.info("Completa los campos y presiona **Calculate**.")
