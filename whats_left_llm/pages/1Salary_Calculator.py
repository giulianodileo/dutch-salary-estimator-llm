# Dutch Salary-to-Reality Calculator (Enhanced & Accessible)

import streamlit as st
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from whats_left_llm.calculator_core import get_estimates, DB_URI
from whats_left_llm.calculate_30_rule import expat_ruling_calc

st.markdown(
        """
        <style>
        /* Sidebar en azul oscuro + texto claro */
        section[data-testid="stSidebar"] {
            background: #EAF6FD; /* si quieres sidebar claro usa este,
                                    para sidebar oscuro usa: background:#023E8A; */
        }
        section[data-testid="stSidebar"] * {
            color: #03045E;
        }

        /* Form y contenedores tipo “card” coherentes con el tema */
        [data-testid="stForm"],
        .st-card,
        div[data-testid="stVerticalBlock"] > div:has(> div > div > div[role="group"]) {
            background: #ADE8F4;                /* secondaryBackgroundColor */
            border: 1px solid #90E0EF;
            border-radius: 12px;
            padding: 16px 18px;
        }

        /* Expander: header y borde */
        details[data-testid="stExpander"] {
            background: #ADE8F4;
            border: 1px solid #90E0EF;
            border-radius: 12px;
        }
        details[data-testid="stExpander"] summary {
            color: #03045E;
            font-weight: 600;
        }

        /* Botón primario acorde a la paleta */
        button[kind="primary"] {
            background: #0077B6 !important;
            color: #FFFFFF !important;
            border: 1px solid #0096C7 !important;
        }
        button[kind="primary"]:hover {
            background: #0096C7 !important;
        }

        /* Métricas: color de texto acorde */
        [data-testid="stMetricLabel"] { color: #023E8A; font-weight: 600; }
        [data-testid="stMetricValue"] { color: #03045E; }

        /* Enlaces y focos */
        a { color: #0077B6; }
        .st-emotion-cache-1xarl3l:focus, *:focus-visible { outline-color: #00B4D8; }
        </style>
        """,
        unsafe_allow_html=True
    )


def add_ui_css():
    st.markdown(
        """
        <style>
        /* Igualamos el look del form */
        [data-testid="stForm"] {
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.04);
            border-radius: 12px;
            padding: 16px 18px;
        }

        /* Caja reutilizable para cualquier sección */
        .st-card {
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.04);
            border-radius: 12px;
            padding: 16px 18px;
            margin-bottom: 16px;
        }

        .st-card-title {
            margin: 0 0 8px 0;
            font-weight: 600;
            font-size: 1.1rem;
        }
        </style>
        """,
        unsafe_allow_html=True
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
        car_value = payload["outputs"]["car_total_per_month"]

        # ---- Metrics ----
        add_ui_css()
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
            col1.metric("Gross salary", f"€{out['salary']['avg']:,.0f}")
            col1.metric("Net salary", f"€{net_first_year:,.0f}")
            col2.metric("Costs", f"€{out['essential_costs']:,.0f}")
            col2.metric("Money in your pocket", f"€{disposable_first_year:,.0f}")

        with st.container():
            with st.expander("Watch your costs"):
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
                    st.markdown(
                        """
                        <div style="
                            background-color: #ff4d4d;
                            padding: 10px;
                            border-radius: 10px;
                            height: 100%;
                        ">
                            <h3 style="color:white;">⚠️ Alerta</h3>
                            <p style="color:white;">Este es un contenedor pintado de rojo</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

        # ---- NEW BAR CHART: Net salary evolution (2026–2031) ----
        import plotly.express as px

        years = [2026, 2027, 2028, 2029, 2030, 2031]
        net_salaries = []

        for y in years:
            if y in res_tax:
                net_salaries.append(res_tax[y] / 12)  # monthly net salary
            elif y >= 2031:
                normal_net = res_tax[max(res_tax.keys())] / 12
                net_salaries.append(normal_net)

        labels = [
            "30% ruling (2026)",
            "27% ruling (2027)",
            "27% ruling (2028)",
            "27% ruling (2029)",
            "27% ruling (2030)",
            "Normal taxes (2031+)"
        ]

        fig = px.bar(
            x=labels,
            y=net_salaries,
            text=[f"€{val:,.0f}" for val in net_salaries],
            labels={"x": "Year & Ruling", "y": "Net Salary (per month)"},
            color=labels,
            color_discrete_sequence=COLOR_PALETTE
        )

        fig.update_traces(textposition="outside")
        fig.update_layout(
            title="Impact of 30% Ruling on Net Salary (2026–2031)",
            showlegend=False,
            yaxis=dict(
                tickformat="€,.0f",
                range=[3500, max(net_salaries) * 1.1] # X starts from 3500
                )
        )

        st.plotly_chart(fig, use_container_width=True)

    except ValueError as ve:
        st.warning(str(ve))
    except Exception as e:
        st.error(f"Unexpected error: {e}")
else:
    st.info("Fill in the fields and press **What's left**.")

            # ---- Details con tabs: Inputs / Extra / Outputs ----
        # st.markdown("### Details")

        #     # (opcional) también mostrar el JSON crudo
        # with st.expander("Raw payload (JSON)"):
        #     import json
        #     st.code(json.dumps(payload, indent=2), language="json")

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
