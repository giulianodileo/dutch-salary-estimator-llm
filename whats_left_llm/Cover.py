import streamlit as st
# from whats_left_llm.pages.Salary_Calculator import render as render_salary_calculator
# from whats_left_llm.pages.Salary_Chat import render as render_salary_budget_chat
# from whats_left_llm.pages.Team import render as render_team
# from whats_left_llm.pages.Next_Step import render as render_next_step


# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

st.markdown(
    """
    <h1 style='text-align: center; font-size: 64px; font-weight: 800; color: #0B3A6F;'>
        How much do you have
    </h1>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <h1 style='text-align: center; font-size: 64px; font-weight: 800; color: #0B3A6F;'>
        in your pocket?
    </h1>
    """,
    unsafe_allow_html=True
)
