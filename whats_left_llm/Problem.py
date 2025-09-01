import streamlit as st
# from whats_left_llm.pages.Salary_Calculator import render as render_salary_calculator
# from whats_left_llm.pages.Salary_Chat import render as render_salary_budget_chat
# from whats_left_llm.pages.Team import render as render_team
# from whats_left_llm.pages.Next_Step import render as render_next_step
from whats_left_llm.css import apply_custom_css


# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    layout="wide",
    initial_sidebar_state="expanded"
)


st.title("Problem")
st.info("Problem")
