# Dutch Salary-to-Reality Calculator Prototype (Enhanced)

import streamlit as st
import pandas as pd
import plotly.express as px
import re

# Attempt to import the LLM package
try:
    from llama_cpp import Llama
    HAS_LLM = True
except ImportError:
    HAS_LLM = False

# Import the init_chat_model function for the Gemini model
try:
    from some_module import init_chat_model  # Replace 'some_module' with the actual module name
except ImportError:
    st.sidebar.error("⚠️ Could not import init_chat_model. Ensure the correct module is installed.")
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
def load_llm(local=False):
    if not HAS_LLM:
        return None
    try:
        if local:
            # Load the local Llama model
            return Llama(model_path="./models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf", n_ctx=512)
        else:
            # Load the remote Gemini model
            return init_chat_model("gemini-2.5-flash", model_provider="google_genai")
    except Exception as e:
        st.sidebar.error(f"⚠️ Could not load LLM: {e}")
        return None

# Set local to True or False based on your preference
llm = load_llm(local=False)  # Change to True if you want to load the local model

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
    if not HAS_LLM or not llm:
        return "⚠️ LLM not available. Install `llama-cpp-python` and a GGUF model to enable chat."

    prompt = f"You are a helpful assistant. Answer the following salary-related question clearly and concisely.\nQuestion: {question}\n"

    try:
        output = llm(prompt, max_tokens=400, stop=["\n"])  # Adjust max_tokens as needed
        return output["choices"][0]["text"].strip() if "choices" in output and output["choices"] else "⚠️ No answer available."
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

        # Optional: Extracting numbers & city for visualization
        city_match = next((city for city in ESSENTIALS if city.lower() in user_input.lower()), None)
        salary_match = re.findall(r"\d+", user_input)
        if city_match and salary_match:
            gross = int(salary_match[0])
            net, leftover = calculate_salary(gross, city_match)
            render_salary_charts(net, city_match, leftover)

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

########################################################################################################################
# Some example questions to ask the LLM chat box regarding salary situations.
# These questions cover various aspects of salary, cost of living, and financial planning:

# General Salary Questions:
# What is the average salary for a Data Scientist in Amsterdam?
# How does the salary of a Software Engineer in Rotterdam compare to that in Utrecht?
####################### What factors influence salary levels in the Netherlands?

# Cost of Living:
########## What are the essential living costs in Amsterdam for a single person?
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
############################## What financial advice do you have for someone starting their career in the tech industry?
# How can I effectively manage my finances with a salary of €4000 per month?

# Future Salary Expectations:
# What salary growth can I expect in the tech industry over the next five years?
# How does the salary of entry-level positions compare to mid-level positions in the Netherlands?

# Miscellaneous:
# What are the benefits of working in a startup versus a large corporation in terms of salary?
# How do bonuses and benefits factor into overall salary compensation?
