# Dutch Salary-to-Reality Calculator Prototype (Enhanced)

import streamlit as st
import pandas as pd
import plotly.express as px
import re
from google.cloud import storage  # For Google Cloud integration
from google.oauth2 import service_account  # For authentication

# -------------------- CONFIG & THEME --------------------
st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- USER AUTHENTICATION --------------------
# Simple user authentication (for demonstration purposes)
if 'username' not in st.session_state:
    st.session_state['username'] = st.text_input("Enter your name:", "")
    if st.session_state['username']:
        st.session_state['authenticated'] = True
        st.sidebar.success(f"Welcome, {st.session_state['username']}!")
    else:
        st.sidebar.warning("Please enter your name to continue.")
        st.stop()

# -------------------- LLM SETUP --------------------
def load_llm():
    # Load LLM from Google Cloud
    try:
        credentials = service_account.Credentials.from_service_account_file(
            'path/to/your/service-account-file.json'
        )
        # Initialize your LLM here using Google Cloud
        # This is a placeholder; replace with actual LLM loading code
        return "LLM Loaded"  # Replace with actual LLM instance
    except Exception as e:
        st.sidebar.error(f"⚠️ Could not load LLM: {e}")
        return None

llm = load_llm()

# -------------------- DATA --------------------
TAX_RATE = 0.37
ESSENTIALS = {
    "Amsterdam": 1800,
    "Rotterdam": 1500,
    "Utrecht": 1600,
    "Eindhoven": 1400,
    "Groningen": 1200
}

# -------------------- FUNCTIONS --------------------
def calculate_salary(gross, city):
    net = gross * (1 - TAX_RATE)
    leftover = net - ESSENTIALS[city]
    return net, leftover

def render_salary_charts(net, city, leftover):
    df = pd.DataFrame({
        "Category": ["Net Salary", "Essential Costs", "Disposable Income"],
        "Amount": [net, ESSENTIALS[city], leftover]
    })

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            px.bar(df, x="Category", y="Amount", color="Category", title="Breakdown")
        )
    with col2:
        st.plotly_chart(
            px.pie(df, values="Amount", names="Category", title="Salary Distribution")
        )

def llm_answer(question: str):
    if not llm:
        return "⚠️ LLM not available. Please check your connection."
    # Placeholder for LLM interaction
    # Replace with actual LLM call
    return f"Answer from LLM for: {question}"

# -------------------- NAVIGATION --------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["💶 Salary Calculator", "🤖 LLM Chat", "❓ Help"])

# -------------------- PAGE 1: SALARY CALCULATOR --------------------
if page == "💶 Salary Calculator":
    st.title("💶 Dutch Salary-to-Reality Calculator")

    job = st.sidebar.selectbox("Select Job Role", [
        "Data Scientist", "Data Engineer", "Software Engineer", "Nurse", "Police Officer"])
    location = st.sidebar.selectbox("Select Location", list(ESSENTIALS.keys()))
    gross_salary = st.sidebar.number_input(
        "Enter Gross Monthly Salary (€)", min_value=1000, max_value=20000, value=4000, step=100
    )

    if st.sidebar.button("Calculate"):
        net, leftover = calculate_salary(gross_salary, location)

        st.subheader(f"Results for {job} in {location}")
        st.metric("Net Salary (after tax)", f"€{net:,.0f}")
        st.metric("Essential Living Costs", f"€{ESSENTIALS[location]:,.0f}")
        st.metric("💸 What's Left", f"€{leftover:,.0f}")

        render_salary_charts(net, location, leftover)

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
    **Frequently Asked Questions:**
    - **How do I use the Salary Calculator?**
      Select your job role, location, and enter your gross monthly salary to see your net salary and what's left after essential costs.

    - **What is the LLM Chat?**
      You can ask salary-related questions, and the assistant will provide answers based on your input.

    - **How can I provide feedback?**
      Please use the feedback form below to share your thoughts or report issues.
    """)

    feedback = st.text_area("Your Feedback:", "")
    if st.button("Submit Feedback"):
        if feedback:
            st.success("Thank you for your feedback!")
        else:
            st.warning("Please enter your feedback before submitting.")
