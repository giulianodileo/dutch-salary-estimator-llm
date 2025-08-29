# Dutch Salary-to-Reality Calculator Prototype (Enhanced)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from datetime import datetime
# -------------------- IMPORT TOOLS --------------------
from tools import get_gross_salary, calculate_income_tax, deduct_expenses

# Import the init_chat_model function (Gemini)


# -------------------- CONFIG & THEME --------------------
st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- LLM SETUP --------------------
try:
    from langchain.chat_models import init_chat_model
    HAS_LLM = True
except ImportError:
    st.sidebar.error(
        ":warning: Could not import init_chat_model. Install LangChain + Google GenAI."
    )
    HAS_LLM = False
# -------------------- GLOBAL CONSTANTS --------------------
ACCOMMODATION = {
    "Room": 0,
    "Studio": 0,
    "Apartment (1 bedroom)": 0,
    "Apartment (2 bedroom)": 0
}
CITIES = ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven", "Groningen"]
JOBS = [
    "Backend Engineer", "Data Analyst", "Data Scientist", "Data Engineer",
    "DevOps Engineer", "Frontend Engineer", "Security Engineer", "Software Engineer"
]
SENIORITY_LEVELS = ["Junior", "Mid-Level", "Senior"]
# Colorblind-friendly palette
COLOR_PALETTE = ["#2E91E5", "#E15F99", "#1CA71C", "#FB0D0D"]
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
    """Load Gemini via LangChain"""
    if not HAS_LLM:
        return None
    try:
        return init_chat_model("gemini-2.5-flash", model_provider="google_genai")
    except Exception as e:
        st.sidebar.error(f"⚠️ Could not load LLM: {e}")
        return None
llm = load_llm()

# -------------------- VISUALIZATION --------------------

def render_salary_charts(net, city, leftover, expenses):
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
        response = llm.invoke(question)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        return f":warning: LLM error: {e}"


# -------------------- NAVIGATION --------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["💶 Salary Calculator", "🤖 LLM Chat", "❓ Help"])

# -------------------- PAGE 1: SALARY CALCULATOR --------------------
if page == ":euro: Salary Calculator":
    st.title(":euro: Dutch Salary-to-Reality Calculator")
    # Sidebar Inputs
    user_name = st.sidebar.text_input("What's your name?", "")
    if user_name:
        st.sidebar.success(f"Welcome, {user_name}! 😎")

    job = st.sidebar.selectbox("What is your job?", [
        "Backend Engineer",
        "Data Analyst",
        "Data Scientist",
        "Data Engineer",
        "DevOps Engineer",
        "Frontend Engineer",
        "Security Engineer",
        "Software Engineer",
    ])

    seniority = st.sidebar.selectbox("What is your seniority?", ["Junior", "Mid-Level", "Senior"])
    city = st.sidebar.selectbox("Where are you planning to live?", ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven", "Groningen"])

    if st.sidebar.button("Calculate"):
        # 1. Gross salary (from tool)
        gross = get_gross_salary.invoke({"job_title": job, "seniority": seniority})

        if gross == 0:
            st.error("No salary data available for that combination.")
        else:
            st.subheader(f"Expected salary for a {seniority} {job} in {city}")
            # -------------------- METRICS --------------------
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Gross Salary", f"€{gross:,.0f}")
            col2.metric("Net Salary", f"€{net:,.0f}")
            col3.metric("Essentials + Housing Costs", f"€{expenses:,.0f}", help="Monthly essential expenses including housing.")
            col4.metric("Disposable Income", f"€{leftover:,.0f}", help="Money left after paying essentials + housing.")
            # -------------------- PIE CHART --------------------
            render_salary_charts(expenses, leftover)
            # REMOVED: COMPARISON CHART
            # city_avg_expenses = 1200
            # render_comparison_chart(net, city_avg_expenses)
            # -------------------- DISPOSABLE INCOME GAUGE --------------------
            disposable_pct = max(0, leftover / net * 100)
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
            # -------------------- SAVINGS RECOMMENDATION --------------------
            st.markdown("### :moneybag: Suggested Savings")
            if leftover <= 0:
                st.warning("You are spending all of your net income. Consider reducing housing or essentials costs.")
            elif leftover / net < 0.2:
                st.info("Your disposable income is low. Aim to save at least 5-10% of your net salary.")
            elif leftover / net < 0.4:
                st.success("Good! You can save 15-25% of your net salary each month.")
            else:
                st.success("Excellent! You have a high disposable income. Consider saving 25-40% or investing for growth.")
            st.info(f":bulb: Tip: Track your spending monthly. In {city}, typical accommodation costs range around {ACCOMMODATION[accommodation_type]} €.")
# -------------------- PAGE 2: LLM CHAT --------------------
elif page == "🤖 LLM Chat":
    st.title("🤖 Ask about your Salary Situation")
    st.info("Type a salary-related question, e.g. 'How much disposable income in Amsterdam with €5000 gross?'")

    user_input = st.text_area("Your Question:", "")
    if st.button("Ask") and user_input:
        with st.spinner("Thinking..."):
            answer = llm_answer(user_input)
            st.success(answer)
# -------------------- PAGE 3: HELP --------------------
elif page == "❓ Help":
    st.title("Help & FAQ")
    st.write("""
    *Frequently Asked Questions:*
    - *How do I use the Salary Calculator?* Select your job, city, seniority, age, and accommodation type.
    - *Why age & degree?* If under 30, degree info affects benefits/policies.
    - *What is the LLM Chat?* Ask salary-related questions; the assistant will respond.
    - *Provide feedback below:* Share your thoughts or report issues.
    """)

    feedback = st.text_area("Your Feedback:", "")
    if st.button("Submit Feedback") and feedback:
        save_feedback(feedback)
########################################################################################################################
# Some example questions to ask the LLM chat box regarding salary situations.
# These questions cover various aspects of salary, cost of living, and financial planning:
# General Salary Questions:
# What is the average salary for a Data Scientist in Amsterdam?
# How does the salary of a Software Engineer in Rotterdam compare to that in Utrecht?
# What factors influence salary levels in the Netherlands?
# Cost of Living:
# What are the essential living costs in Amsterdam for a single person?
# How much should I budget for rent in Rotterdam?
# What are the average monthly expenses for a family of four living in Utrecht?
# Disposable Income:
# If I earn €5000 gross per month in Eindhoven, what will my net salary be after taxes?
# How much disposable income can I expect after paying essential living costs in Groningen?
# What percentage of my salary should I save each month?
# Salary Negotiation:
# What is the best way to negotiate a higher salary during a job offer?
# How can I justify asking for a salary increase during my performance review?
# Job Role Specific:
# What is the salary range for a Nurse in the Netherlands?
# How does the salary of a Police Officer in Amsterdam compare to that in smaller cities?
# Tax Implications:
# What is the tax rate for salaries in the Netherlands?
# How do tax deductions affect my net salary?
# Financial Planning:
# What financial advice do you have for someone starting their career in the tech industry?
# How can I effectively manage my finances with a salary of €4000 per month?
# Future Salary Expectations:
# What salary growth can I expect in the tech industry over the next five years?
# How does the salary of entry-level positions compare to mid-level positions in the Netherlands?
# Miscellaneous:
# What are the benefits of working in a startup versus a large corporation in terms of salary?
# How do bonuses and benefits factor into overall salary compensation?
