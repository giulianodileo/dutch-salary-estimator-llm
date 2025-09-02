import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import List
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
