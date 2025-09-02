# from typing import list
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from typing import List

def render_salary_projection_chart(df_proj: pd.DataFrame):
    """
    Render a line chart showing Net Monthly and Disposable Monthly income projections.

    Parameters:
    - df_proj: pd.DataFrame with columns:
        - 'Year' (int or str)
        - 'Net Monthly (€)' (float)
        - 'Disposable Monthly (€)' (float)
    """
    fig = px.line(
        df_proj,
        x="Year",
        y=["Net Monthly (€)", "Disposable Monthly (€)"],
        markers=True,
        title="Net & Disposable Income Projection",
        labels={"value": "Amount (€)", "variable": "Income Type"}
    )
    fig.update_layout(
        legend_title_text="Income Type",
        xaxis=dict(dtick=1),
        xaxis_title="Year",
        yaxis_title="Amount (€)",
        yaxis_tickprefix="€",
        template="plotly_white"
    )
    st.plotly_chart(fig, use_container_width=True)


def render_bar_chart_30_rule(salary_data: dict):
    """
    Render a grouped bar chart comparing salary with and without 30% ruling.

    Parameters:
    - salary_data: dict with keys:
        - "Year": list of years
        - "Salary": list of salary values
        - "Salary_30_rule": list of salary values with 30% ruling applied
    """
    df = pd.DataFrame(salary_data)
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Salary', x=df["Year"], y=df["Salary"]))
    fig.add_trace(go.Bar(name='Salary with 30% ruling', x=df["Year"], y=df["Salary_30_rule"]))
    fig.update_layout(
        barmode='group',
        title="Salary Comparison with 30% Ruling",
        yaxis_title="Monthly Salary (€)",
        xaxis_title="Year",
        template="plotly_white"
    )
    st.plotly_chart(fig, use_container_width=True)

from typing import List
def render_pie_chart_percent_only(labels: List[str], values: List[float], title: str):
    """
    Render a donut pie chart showing percentage breakdown of essential living costs.

    Parameters:
    - labels: list of category names (e.g., ["Housing Costs", "Transportation", ...])
    - values: list of numeric values corresponding to labels
    - title: chart title string
    """
    fig = px.pie(
        names=labels,
        values=values,
        title=title,
        hole=0.4,
        color=labels,
        color_discrete_map={
            "Housing Costs": "#E15F99",
            "Transportation": "#1CA71C",
            "Utilities": "#2E91E5",
            "Other": "#FB0D0D"
        }
    )
    fig.update_traces(textinfo="percent", textfont_color="white")
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig)

def render_income_projection(res_tax: dict, essential_costs: float):
    """
    Render a table and line chart showing net and disposable monthly income projections.

    Parameters:
    - res_tax: dict of {year: net_annual_salary}
    - essential_costs: monthly essential costs to subtract from net salary
    """
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

    st.markdown("### 📈 Net Income Projection (2026–2035)")
    st.dataframe(df_proj, use_container_width=True)

    fig = px.line(
        df_proj,
        x="Year",
        y=["Net Monthly (€)", "Disposable Monthly (€)"],
        markers=True,
        title="Net & Disposable Income Projection"
    )
    fig.update_layout(
        xaxis_title="Year",
        yaxis_title="Amount (€)",
        template="plotly_white"
    )
    st.plotly_chart(fig, use_container_width=True)
