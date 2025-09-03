import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import List
import plotly.express as px
# This is to make sure


# def render_pie_chart_percent_only(labels: List[str], values: List[float]):
#     """
#     Render a donut pie chart showing percentage breakdown of essential living costs.

#     Parameters:
#     - labels: list of category names (e.g., ["Housing Costs", "Transportation", ...])
#     - values: list of numeric values corresponding to labels
#     - title: chart title string
#     """

#     # Define the new color palette from your request
#     COLOR_PALETTE = [
#         "#48CAE4",
#         "#00B4D8",
#         "#0096C7",
#         "#0077B6",
#         "#023E8A",
#         "#03045E",
#     ]

#     fig = px.pie(
#         names=labels,
#         values=values,
#         hole=0.4,
#         color_discrete_sequence=COLOR_PALETTE
#     )

#     # Update traces to show percentages and set text color
#     fig.update_traces(
#         textinfo="percent",
#         textfont_color="white",
#         # --- CAMBIO CLAVE: PERSONALIZAR EL HOVER ---
#         hovertemplate="<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>"
#         # Esto resultará en un hoverbox como:
#         # **Health Insurance**
#         # Amount: €157
#         # Percentage: 8.36%
#         # ---------------------------------------------
#     )

#     # Update layout to use a clean template
#     fig.update_layout(
#         template="plotly_white",
#         showlegend=False)
#     st.plotly_chart(fig, use_container_width=False)


def render_pie_chart_percent_only(labels: List[str], values: List[float]):
    """
    Render a donut pie chart showing percentage breakdown of essential living costs.

    Parameters:
    - labels: list of category names (e.g., ["Housing Costs", "Transportation", ...])
    - values: list of numeric values corresponding to labels
    - title: chart title string
    """

    # Define the new color palette from your request
    COLOR_PALETTE = [
        "#48CAE4",
        "#00B4D8",
        "#0096C7",
        "#0077B6",
        "#023E8A",
        "#03045E",
    ]

    fig = px.pie(
        names=labels,
        values=values,
        hole=0.4,
        color_discrete_sequence=COLOR_PALETTE
    )

    # Update traces to show percentages and set text color
    fig.update_traces(
        textinfo="percent",
        textfont_color="white",
        hovertemplate="<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>"
    )

    # Update layout to use a clean template
    fig.update_layout(
        template="plotly_white",
        showlegend=True,
        height=280,
    )
    # --- CAMBIO CLAVE: USAR COLUMNAS PARA REDUCIR EL TAMAÑO ---
    # Crea tres columnas para centrar el gráfico.
    # La del medio tendrá el gráfico y las otras dos serán espacios en blanco.
    # col1, col2, col3 = st.columns([0.1, 2, 0.1])

    # with col2:
    #     st.plotly_chart(fig, use_container_width=True) # Se mantiene en True para que llene su columna
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
