import streamlit as st
from tools import get_gross_salary, calculate_income_tax, deduct_expenses

# Sidebar inputs
job = st.sidebar.selectbox("Select Job Role", [
    "Data Scientist", "Data Engineer", "Software Engineer", "Nurse", "Police Officer"
])
seniority = st.sidebar.selectbox("Select Seniority", ["Junior", "Mid-Level", "Senior"])
city = st.sidebar.selectbox("Select Location", ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven", "Groningen"])

if st.sidebar.button("Calculate"):
    # 1. Get gross salary
    gross = get_gross_salary.invoke({"job_title": job, "seniority": seniority})

    if gross == 0:
        st.error("No salary data available for that combination.")
    else:
        # 2. Tax
        tax_result = calculate_income_tax.invoke({"gross_salary": gross})
        net = tax_result["net_after_tax"]

        # 3. Expenses
        expense_result = deduct_expenses.invoke({"net_salary": net, "city": city})
        leftover = expense_result["remaining"]

        # 4. Display
        st.subheader(f"Results for {job} ({seniority}) in {city}")
        st.metric("Gross Salary", f"€{gross:,.0f}")
        st.metric("Net Salary (after tax)", f"€{net:,.0f}")
        st.metric("Essential Living Costs", f"€{expense_result['expenses']:,.0f}")
        st.metric("💸 What's Left", f"€{leftover:,.0f}")
