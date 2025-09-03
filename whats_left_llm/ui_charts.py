import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import List
import plotly.express as px
# This is to make sure

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
    st.plotly_chart(fig, use_container_width=True)

def render_bar_chart_giuliano(res_tax: dict, age, gross_salary, master_dpl):
    # ---- BAR CHART: Net salary evolution (2026–2031) ----

    eligible = False
    if age >= 30 and gross_salary >= 66657:
        eligible = True
    elif age < 30 and master_dpl and gross_salary >= 50668:
        eligible = True
        print("True")
    else:
        eligible = False
        print("False else")

    if eligible:
        years = [2026, 2027, 2028, 2029, 2030, 2031]
        net_salaries = []

        for y in years:
            if y in res_tax:
                net_salaries.append(res_tax[y] / 12)  # monthly net salary
            elif y >= 2031:
                normal_net = res_tax[max(res_tax.keys())] / 12
                net_salaries.append(normal_net)

        labels = [
            "30% ruling (2026)",
            "27% ruling (2027)",
            "27% ruling (2028)",
            "27% ruling (2029)",
            "27% ruling (2030)",
            "Normal taxes (2031+)"
        ]

        COLOR_PALETTE = ["#02315A", "#1C6EB6", "#61AFF3"]

        fig = px.bar(
            x=labels,
            y=net_salaries,
            text=[f"€{val:,.0f}" for val in net_salaries],
            labels={"x": "Year & Ruling", "y": "Net Salary (per month)"},
            color=labels,
            color_discrete_sequence=COLOR_PALETTE
        )

        fig.update_traces(textposition="outside")
        fig.update_layout(
            title="Impact of 30% Ruling on Net Salary (2026–2031)",
            showlegend=False,
            yaxis=dict(
                tickformat="€,.0f",
                range=[3500, max(net_salaries) * 1.1] # X starts from 3500
                )
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        print("You are not selected")
