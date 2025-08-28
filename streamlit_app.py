from whats_left_llm.data_base_code.calculator_core import get_estimates, DB_URI
from whats_left_llm.calculate_30_rule import expat_ruling_calc
from whats_left_llm.chart import return_net_income
# res = get_estimates(
#     job="Backend Engineer",
#     seniority="Junior",
#     city="Amsterdam",
#     accommodation_type="studio",
#     car_type="mini",  # o None si no aplica
# )
# print(get_estimates("Backend Engineer", "Junior", "Amsterdam", "studio", "mini"))

# streamlit_app.py

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime as dt

import streamlit as st


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
        # Jobs & seniorities
        rows = con.execute("SELECT DISTINCT position_name FROM job_positions_seniorities ORDER BY position_name;").fetchall()
        opts["jobs"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT seniority FROM job_positions_seniorities ORDER BY seniority;").fetchall()
        opts["seniorities"] = [r[0] for r in rows]

        # Cities & accommodation types
        rows = con.execute("SELECT DISTINCT city FROM rental_prices ORDER BY city;").fetchall()
        opts["cities"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT accommodation_type FROM rental_prices WHERE accommodation_type IS NOT NULL ORDER BY accommodation_type;").fetchall()
        opts["accommodations"] = [r[0] for r in rows]

        # Car classes
        rows = con.execute("SELECT DISTINCT type FROM transportation_car_costs ORDER BY type;").fetchall()
        opts["cars"] = [r[0] for r in rows]

    return opts

# ---------- UI ----------
st.set_page_config(page_title="Dutch Salary-to-Reality (Minimal)", layout="wide")
st.title("🇳🇱 Dutch Salary-to-Reality — Minimal App")

st.caption("Selecciona tus inputs y calcula salario y costos esenciales (consulta directa a SQLite, sin LLM).")

opts = load_options(DB_URI)
if not any(opts.values()):
    st.error("No encuentro la base de datos o las tablas están vacías. Asegúrate de haberla creado y cargado JSONs.")
    st.stop()

with st.form("inputs"):
    col1, col2, col3 = st.columns(3)
    with col1:
        job = st.selectbox("Job", opts["jobs"] or ["Backend Engineer"])
        seniority = st.selectbox("Seniority", opts["seniorities"] or ["Junior"])
    with col2:
        city = st.selectbox("City", opts["cities"] or ["Amsterdam"])
        accommodation = st.selectbox("Accommodation type", opts["accommodations"] or ["studio"])
    with col3:
        car_type = st.selectbox("Car type (optional)", ["(none)"] + opts["cars"])
        car_type = None if car_type == "(none)" else car_type



        # ------- Fila 2: extra inputs -------
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        age = st.number_input("Age", min_value=16, max_value=80, value=28, step=1)
    with e2:
        start_date = st.date_input("Start date (MM/DD/YYYY)", value=dt.date.today())
    with e3:
        duration_years = st.number_input("Duration (years)", min_value=0.0, value=1.0, step=0.5)
    with e4:
        expertise = st.checkbox("Expertise", value=False)
        master_diploma = st.checkbox("Master's diploma", value=False)

    submitted = st.form_submit_button("Calculate")

if submitted:
    try:
        res: Dict[str, Any] = get_estimates(
            job=job,
            seniority=seniority,
            city=city,
            accommodation_type=accommodation,
            car_type=car_type,
            db_uri=DB_URI,
        )

        out = res["outputs"]


        # ---- armar "extra" y "payload" para pasar a otras funciones / guardar ----
        extra = {
            "age": int(age),
            "start_date_us": start_date.strftime("%m/%d/%Y"),
            "start_date_iso": start_date.isoformat(),
            "duration_years": int(duration_years),
            "expertise": bool(expertise),
            "master_diploma": bool(master_diploma),
        }

        res_tax = expat_ruling_calc(
            age=extra["age"],
            salary=out['salary']['avg']*12,
            date_string=extra["start_date_iso"],
            duration=extra["duration_years"],
            expertise=extra["expertise"],
            master_dpl=extra["master_diploma"])

        return_net_incomee = return_net_income(res_tax, out['essential_costs'])

        payload = {
            "inputs": res["inputs"],   # job, seniority, city, accommodation_type, car_type
            "extra": extra,            # 👈 tus nuevos inputs
            "outputs": out,            # salary, rent, car_total_per_month
            "tax dic": res_tax,
            "net tax": return_net_incomee,
        }
        st.session_state["last_payload"] = payload  # opcional, por si quieres usarlo luego

        # ---- métricas arriba ----
        st.subheader(f"Result for {job} — {seniority} in {city} ({accommodation} and {out['essential_costs']})")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Salary (avg)", f"€{out['salary']['avg']:,.0f}")
        m2.metric("Rent (avg)",   f"€{out['rent']['avg']:,.0f}")
        m3.metric("Car / month",  f"€{out['car_total_per_month']:,.0f}")
        m4.metric("Essential Living Costs", f"€{out['essential_costs']:,.0f}")
        m5.metric("Your Net Salary after Tax", f"€{return_net_incomee/12:,.0f}" )
        # m4.metric("Salary (max)", f"€{out['salary']['max']:,.0f}")

        # ---- Details con tabs: Inputs / Extra / Outputs ----
        st.markdown("### Details")
        tab1, tab2, tab3 = st.tabs(["Inputs", "Extra", "Outputs"])

        with tab1:
            st.write({
                "job": res["inputs"]["job"],
                "seniority": res["inputs"]["seniority"],
                "city": res["inputs"]["city"],
                "accommodation_type": res["inputs"]["accommodation_type"],
                "car_type": res["inputs"]["car_type"],
            })

        with tab2:
            st.write({
                "age": extra["age"],
                "start_date (US)": extra["start_date_us"],
                "start_date (ISO)": extra["start_date_iso"],
                "duration_years": extra["duration_years"],
                "expertise": extra["expertise"],
                "master_diploma": extra["master_diploma"],
            })

        with tab3:
            st.write({
                "salary": out["salary"],                  # {min, avg, max}
                "rent": out["rent"],                      # {min, avg, max}
                "car_total_per_month": out["car_total_per_month"],
            })

        # (opcional) también mostrar el JSON crudo
        with st.expander("Raw payload (JSON)"):
            import json
            st.code(json.dumps(payload, indent=2), language="json")



    except ValueError as ve:
        st.warning(str(ve))
    except Exception as e:
        st.error(f"Unexpected error: {e}")
else:
    st.info("Completa los campos y presiona **Calculate**.")
