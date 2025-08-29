# Dutch Salary-to-Reality Calculator Prototype (Enhanced)

import streamlit as st
import pandas as pd
import plotly.express as px
import re

# Import tools (StructuredTool versions)
from tools_2 import (
    get_gross_salary_tool,
    calculate_income_tax_tool,
    deduct_expenses_tool
)

# Import the init_chat_model function (Gemini)
try:
    from langchain.chat_models import init_chat_model
    HAS_LLM = True
except ImportError:
    st.sidebar.error("⚠️ Could not import init_chat_model. Ensure LangChain and Google GenAI integration are installed.")
    HAS_LLM = False

# -------------------- CONFIG & THEME --------------------
st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- LLM SETUP --------------------
@st.cache_resource(show_spinner=True)
def load_llm():
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
        "Category": ["Net Salary", "Essential Costs", "Disposable Income"],
        "Amount": [net, expenses, leftover]
    })

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(px.bar(df, x="Category", y="Amount", color="Category", title="Breakdown"))
    with col2:
        st.plotly_chart(px.pie(df, values="Amount", names="Category", title="Salary Distribution"))

# -------------------- SIMPLE LLM WRAPPER --------------------
def llm_answer(question: str):
    if not HAS_LLM or not llm:
        return "⚠️ LLM not available. Please install LangChain + Google GenAI."
    try:
        return llm.invoke(question).content
    except Exception as e:
        return f"⚠️ An error occurred while getting the answer: {e}"

# -------------------- NAVIGATION --------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["💶 Salary Calculator", "🤖 LLM Chat", "❓ Help"])

# -------------------- PAGE 1: SALARY CALCULATOR --------------------
if page == "💶 Salary Calculator":
    st.title("💶 Dutch Salary-to-Reality Calculator")

    # User Profile Input
    user_name = st.sidebar.text_input("Enter your name:", "")
    if user_name:
        st.sidebar.success(f"Welcome, {user_name}!")

    job = st.sidebar.selectbox("Select Job Role", [
        "Data Scientist", "Data Engineer", "Software Engineer", "Nurse", "Police Officer"
    ])
    seniority = st.sidebar.selectbox("Select Seniority", ["Junior", "Mid-Level", "Senior"])
    city = st.sidebar.selectbox("Select Location", ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven", "Groningen"])

    if st.sidebar.button("Calculate"):
        # 1. Gross salary (via tool)
        gross = get_gross_salary_tool.invoke({"job_title": job, "seniority": seniority})

        if gross == 0:
            st.error("No salary data available for that combination.")
        else:
            # 2. Apply tax tool
            tax_result = calculate_income_tax_tool.invoke({"gross_salary": gross})
            net = tax_result["net_after_tax"]

            # 3. Deduct expenses tool
            expense_result = deduct_expenses_tool.invoke({"net_salary": net, "city": city})
            leftover = expense_result["remaining"]
            expenses = expense_result["expenses"]

            # 4. Display results
            st.subheader(f"Results for {job} ({seniority}) in {city}")
            st.metric("Gross Salary", f"€{gross:,.0f}")
            st.metric("Net Salary (after tax)", f"€{net:,.0f}")
            st.metric("Essential Living Costs", f"€{expenses:,.0f}")
            st.metric("💸 What's Left", f"€{leftover:,.0f}")

            render_salary_charts(net, city, leftover, expenses)

# -------------------- PAGE 2: LLM CHAT --------------------
elif page == "🤖 LLM Chat":
    st.title("🤖 Ask about your Salary Situation")
    st.info("Type a salary-related question, e.g. 'How much disposable income in Amsterdam with €5000 gross?'")

    user_input = st.text_area("Your Question:", "")
    if st.button("Ask") and user_input:
        with st.spinner("Thinking..."):
            answer = llm_answer(user_input)
            st.success(answer)

        # Optional: Extract numbers & city for visualization
        city_match = next((city for city in ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven", "Groningen"]
                           if city.lower() in user_input.lower()), None)
        salary_match = re.findall(r"\d+", user_input)
        if city_match and salary_match:
            gross = int(salary_match[0])
            tax_result = calculate_income_tax_tool.invoke({"gross_salary": gross})
            net = tax_result["net_after_tax"]
            expense_result = deduct_expenses_tool.invoke({"net_salary": net, "city": city_match})
            leftover = expense_result["remaining"]
            render_salary_charts(net, city_match, leftover, expense_result["expenses"])

# -------------------- PAGE 3: HELP --------------------
elif page == "❓ Help":
    st.title("Help & FAQ")
    st.write("""
    **Frequently Asked Questions:**
    - **How do I use the Salary Calculator?**
      Select your job role, location, and seniority to see your net salary and what's left after essential costs.

    - **What is the LLM Chat?**
      You can ask salary-related questions, and the assistant will provide answers using the same tools.

    - **How can I provide feedback?**
      Please use the feedback form below to share your thoughts or report issues.
    """)

    feedback = st.text_area("Your Feedback:", "")
    if st.button("Submit Feedback"):
        if feedback:
            st.success("Thank you for your feedback!")
        else:
            st.warning("Please enter your feedback before submitting.")
