# app.py
import streamlit as st
from pages.salary_calculator import render as render_salary_calculator
from pages.salary_budget_chat import render as render_salary_budget_chat

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    page_icon=":euro:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- NAVIGATION --------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", [":euro: Salary Calculator", ":robot_face: Salary & Budget Chat"])



if page == ":euro: Salary Calculator":
    render_salary_calculator()
else:
    render_salary_budget_chat()
