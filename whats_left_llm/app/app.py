# Dutch Salary-to-Reality Calculator (Enhanced & Accessible)
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json

from whats_left_llm.data_base_code.calculator_core import get_estimates, DB_URI
from whats_left_llm.calculate_30_rule import expat_ruling_calc
from whats_left_llm.chart import return_net_income

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime as dt

# -------------------- LLM SETUP --------------------
try:
    from langchain.chat_models import init_chat_model
    HAS_LLM = True
except ImportError:
    st.sidebar.error(
        ":warning: Could not import init_chat_model. Install LangChain + Google GenAI."
    )
    HAS_LLM = False

# Colorblind-friendly palette
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

opts = load_options(DB_URI)
if not any(opts.values()):
    st.error("No encuentro la base de datos o las tablas están vacías. Asegúrate de haberla creado y cargado JSONs.")
    st.stop()

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    page_icon=":euro:",
    layout="wide",
    initial_sidebar_state="expanded"
)
# -------------------- CACHED LLM LOADER --------------------
@st.cache_resource(show_spinner=True)
def load_llm():
    if not HAS_LLM:
        return None
    try:
        return init_chat_model("gemini-2.5-flash", model_provider="google_genai")
    except Exception as e:
        st.sidebar.error(f":warning: Could not load LLM: {e}")
        return None
llm = load_llm()
# -------------------- HELPER FUNCTIONS --------------------

def render_salary_charts(expenses, leftover):
    """Accessible Pie Chart: Expenses vs Disposable Income with white text for disposable income"""
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
            "Disposable Income": "#1CA71C"
        })
    fig.update_traces(textinfo="label+percent+value",
                     textfont_color=["black", "white"])
    st.plotly_chart(fig)
# REMOVED: render_comparison_chart function
# def render_comparison_chart(net_salary, city_avg_expenses):
#    """Compare user's net vs average city expenses"""
#    df = pd.DataFrame({
#        "Category": ["Your Net Salary", "Avg City Expenses"],
#        "Amount": [net_salary, city_avg_expenses]
#    })
#    st.plotly_chart(
#        px.bar(
#            df, x="Category", y="Amount",
#            title=":bar_chart: Net Salary vs Average City Expenses",
#            color="Category", color_discrete_sequence=COLOR_PALETTE
#        )
#    )
def llm_answer(question: str):
    """Query the LLM"""
    if not HAS_LLM or not llm:
        return ":warning: LLM not available."
    try:
        return llm.invoke(question).content
    except Exception as e:
        return f":warning: LLM error: {e}"
def save_feedback(feedback_text):
    """Save feedback locally"""
    try:
        with open("feedback.jsonl", "a") as f:
            json.dump({"timestamp": str(datetime.now()), "feedback": feedback_text}, f)
            f.write("\n")
        st.success("Thank you for your feedback!")
    except Exception as e:
        st.error(f"Could not save feedback: {e}")
# -------------------- NAVIGATION --------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", [":euro: Salary Calculator", ":robot_face: Salary & Budget Chat", ":question: Help"])
# -------------------- PAGE 1: SALARY CALCULATOR --------------------
if page == ":euro: Salary Calculator":
    st.title(":euro: Dutch Salary-to-Reality Calculator")
    # Sidebar Inputs
    user_name = st.sidebar.text_input("What's your name?", "")
    if user_name:
        st.sidebar.success(f"Welcome, {user_name}! :sunglasses:")
    age = st.sidebar.number_input("What is your age?", min_value=18, max_value=70, step=1)
    # Degree question immediately after age
    if age < 30:
        choice = st.sidebar.radio(
        "Do you have a Master’s Degree (or higher) obtained in the Netherlands?",
        ["Yes", "No"],
    )
    has_masters_nl = (choice == "Yes")   # <- bool True/False
    # Remaining sidebar inputs
    job = st.sidebar.selectbox("Job Role", opts["jobs"])
    seniority = st.sidebar.selectbox("Seniority", opts["seniorities"])
    city = st.sidebar.selectbox("City", opts["cities"])
    accommodation_type = st.sidebar.selectbox("Accommodation Type", opts["accommodations"])
    start_date = st.sidebar.date_input("Start date (MM/DD/YYYY)", value=dt.date.today())
    duration_years = 10
    has_car = st.sidebar.radio("Do you have a car?", ["No", "Yes"])

    if has_car == "Yes":
        car_type = st.sidebar.selectbox(
            "Select your car type:", opts["cars"]
        )
    else:
        car_type = 0

    expertise = True

    submitted = st.sidebar.button("Calculate")

#22222222222222282828282828828828282828828288282828282828282882828282882882828288282828282882
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


        # ---- armar "extra" y "payload" para pasar a otras funciones / guardar ----
        extra = {
            "age": int(age),
            "start_date_us": start_date.strftime("%m/%d/%Y"),
            "start_date_iso": start_date.isoformat(),
            "duration_years": int(duration_years),
            "expertise": bool(expertise),
            "master_diploma": bool(has_masters_nl),
        }

        res_tax = expat_ruling_calc(
            age=extra["age"],
            salary=out['salary']['avg']*12,
            date_string=extra["start_date_iso"],
            duration=extra["duration_years"],
            expertise=extra["expertise"],
            master_dpl=extra["master_diploma"])

        return_net_incomee = return_net_income(res_tax, out['essential_costs'])
        # st.session_state["return_net_incomee"] = return_net_incomee

        payload = {
            "inputs": res["inputs"],   # job, seniority, city, accommodation_type, car_type
            "extra": extra,            # 👈 tus nuevos inputs
            "outputs": out,            # salary, rent, car_total_per_month
            "tax dic": res_tax,
            "net tax": return_net_incomee/12,
        }
        st.session_state["last_payload"] = payload  # opcional, por si quieres usarlo luego

    # -------------------- METRICS --------------------
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Gross Salary", f"€{out['salary']['avg']:,.0f}")
        col2.metric("Net Salary", f"€{(res_tax[2025]/12):,.0f}")
        col3.metric("Essential Living Costs", f"€{out['essential_costs']:,.0f}")
        col4.metric("Disposable Income", f"€{return_net_incomee/12:,.0f}")

     #         # -------------------- PIE CHART --------------------
        render_salary_charts(out['essential_costs'], return_net_incomee)

            # -------------------- DISPOSABLE INCOME GAUGE --------------------
        disposable_pct = max(0, return_net_incomee / (((return_net_incomee/12)+out['essential_costs']) * 100))
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
    st.info("Completa los campos y presiona **Calculate**.")
# return_net_incomee = return_net_income(res_tax, out['essential_costs'])
# thabiso = st.session_state["return_net_incomee"]

# st.session_state["last_payload"]["net tax"]

# thabisoo = st.session_state["last_payload"]["net tax"]
#             # -------------------- SAVINGS RECOMMENDATION --------------------
st.markdown("### :moneybag: Suggested Savings")
# if (thabiso) <= 0:
#     st.warning("You are spending all of your net income. Consider reducing housing or essentials costs.")
# elif thabiso / thabisoo < 0.2:
#     st.info("Your disposable income is low. Aim to save at least 5-10% of your net salary.")
# elif thabiso / thabisoo < 0.4:
#     st.success("Good! You can save 15-25% of your net salary each month.")
# else:
#     st.success("Excellent! You have a high disposable income. Consider saving 25-40% or investing for growth.")
#     st.info(f":bulb: Tip: Track your spending monthly. In {city}, typical accommodation costs range around {accommodation_type} €.")
##...........................................................................................................................................................................................................





#...............................................................................................................................................................................................................

# -------------------- PAGE 2: LLM CHAT --------------------
# elif page == ":robot_face: Salary & Budget Chat":
#     st.title(":robot_face: Ask about Your Salary & Budget")
#     st.info("Ask questions like: 'Disposable income in Amsterdam with €5000 gross?'")
#     # Suggested questions for users
#     suggested_questions = [
#         "Average salary for Data Scientist in Amsterdam?",
#         "How much to budget for rent in Utrecht?",
#         "How much disposable income with €4500 net in Rotterdam?"
#     ]
#     st.write(":bulb: Suggested questions:")
#     for q in suggested_questions:
#         if st.button(q):
#             user_input = q
#             with st.spinner("Thinking..."):
#                 answer = llm_answer(user_input)
#             st.success(answer)
#     user_input = st.text_area("Or type your own question:", "")
#     if st.button("Ask") and user_input:
#         with st.spinner("Thinking..."):
#             answer = llm_answer(user_input)
#             st.success(answer)
# # -------------------- PAGE 3: HELP --------------------
# elif page == ":question: Help":
#     st.title("Help & FAQ")
#     st.write("""
#     *Frequently Asked Questions:*
#     - *How do I use the Salary Calculator?* Select your job, city, seniority, age, and accommodation type.
#     - *Why age & degree?* If under 30, degree info affects benefits/policies.
#     - *What is the LLM Chat?* Ask salary-related questions; the assistant will respond.
#     - *Provide feedback below:* Share your thoughts or report issues.
#     """)
#     feedback = st.text_area("Your Feedback:", "")
#     if st.button("Submit Feedback") and feedback:
#         save_feedback(feedback)
