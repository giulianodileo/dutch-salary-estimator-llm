import streamlit as st
from ui_charts import render_income_projection, render_salary_projection_chart, render_bar_chart_30_rule, render_pie_chart_percent_only
import pandas as pd

def main():
    st.title("Test App for Salary Calculator UI")
    st.write("✅ Starting main()")

    # Simulated data for testing
    res_tax = {
        2026: 48000,
        2027: 50000,
        2028: 52000,
        2029: 54000,
        2030: 56000,
        2031: 58000,
        2032: 60000,
        2033: 62000,
        2034: 64000,
        2035: 66000,
    }
    essential_costs = 1500  # example monthly essential costs

    salary_data = {
        "Year": list(res_tax.keys()),
        "Salary": [val / 12 for val in res_tax.values()],
        "Salary_30_rule": [val * 0.7 / 12 for val in res_tax.values()]
    }

    labels = ["Housing Costs", "Transportation", "Utilities", "Other"]
    values = [700, 300, 200, 300]

    st.write("🔹 Rendering income projection")
    render_income_projection(res_tax, essential_costs)
    st.write("✅ Rendered income projection")

    st.write("🔹 Rendering bar chart 30% ruling")
    render_bar_chart_30_rule(salary_data)
    st.write("✅ Rendered bar chart")

    st.write("🔹 Rendering pie chart for essential costs")
    render_pie_chart_percent_only(labels, values, "Essential Living Costs Breakdown")
    st.write("✅ Rendered pie chart")

    # Prepare df_proj for salary projection chart
    projection_data = []
    for year in sorted(res_tax.keys()):
        net_annual = res_tax[year]
        net_monthly = net_annual / 12
        disposable = net_monthly - essential_costs
        projection_data.append({
            "Year": year,
            "Net Monthly (€)": round(net_monthly, 0),
            "Disposable Monthly (€)": round(disposable, 0)
        })
    df_proj = pd.DataFrame(projection_data)

    st.write("🔹 Rendering salary projection chart")
    render_salary_projection_chart(df_proj)
    st.write("✅ Rendered salary projection chart")

if __name__ == "__main__":
    main()
