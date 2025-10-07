# ---------- Import packages and libraries ---------- #

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from core.tax import calc_tax, bereken_algemene_heffingskorting, bereken_arbeidskorting
from typing import List

# ---------- Chart functions ---------- #

def chart_netincome(my_dict: dict, fixed_costs, age, gross_salary, master_dpl):
    """
    Generates and displays a stacked bar chart of net income
    and fixed costs for the first 6 years, based on monthly values, using Plotly.

    Args:
        my_dict (dict): Dictionary with taxable income by year.
        fixed_costs (float): The amount of annual fixed costs.
        age (int): The person's age.
        gross_salary (float): The gross salary.
        master_dpl (bool): True if they have a Master's degree, False otherwise.
    """

    # --- Data Preparation

    # 1. Convert the dictionary to a Pandas DataFrame
    df = pd.DataFrame(list(my_dict.items()), columns=["Year", "Taxable Income"])

    # 2. Add fixed costs to the DataFrame
    df["Fixed Costs"] = fixed_costs

    # 3. Calculate taxes and deductions
    df["Tax"] = round(-df["Taxable Income"].apply(calc_tax), 0)
    df["Arbeidskorting"] = round(df["Taxable Income"].apply(bereken_arbeidskorting), 0)
    df["Algemene Heffingskorting"] = round(df["Taxable Income"].apply(bereken_algemene_heffingskorting), 0)
    df["Gross Salary"] = gross_salary

    # 4. Calculate net tax
    df["Net Tax"] = - (abs(df["Tax"]) - (df["Arbeidskorting"] + df["Algemene Heffingskorting"]))

    # 5. Calculate net disposable income after tax and expenses
    df["Netto Disposable"] = df["Gross Salary"] + df["Net Tax"] - df["Fixed Costs"]

    df.loc[df["Netto Disposable"] < 0, "Netto Disposable"] = 0


    # --- Chart preparation and visualization

    # 1. Check eligibility (does the 30% rule apply?)
    eligible = False
    if age >= 30 and gross_salary >= 46660:
        eligible = True
    elif age < 30 and master_dpl and gross_salary >= 35468:
        eligible = True

    if not eligible:
        print("You are not eligible to view the chart based on the criteria.")
        return # Exit the function if not eligible

    # 2. Prepare the data and create the chart
    plot_df = df[['Year', 'Netto Disposable', 'Fixed Costs', 'Net Tax']].copy()

    # 3. Display the values from years 2026 - 2031+
    plot_df = plot_df.head(6)

    # 4. Define custom labels and add to column
    custom_labels = [
        "30% (2026)",
        "27% (2027)",
        "27% (2028)",
        "27% (2029)",
        "27% (2030)",
        "Normal Tax (2031)",
    ]

    plot_df['Custom Label'] = custom_labels
    plot_df['Net Tax'] = plot_df['Net Tax'].abs()

    # 5. Convert to monthly values and ensure a numeric type
    numeric_cols = ['Netto Disposable', 'Fixed Costs', 'Net Tax']
    for col in numeric_cols:
        plot_df[col] = pd.to_numeric(plot_df[col], errors='coerce') / 12
    plot_df = plot_df.fillna(0)

    # 6. Calculate the total monthly income for annotations
    plot_df['Total'] = plot_df['Netto Disposable'] + plot_df['Fixed Costs'] + plot_df['Net Tax']

    # 7. Create the stacked bar chart with Plotly
    fig = go.Figure()

    # 8. Define a clean color palette
    COLOR_PALETTE_BARS = [
        "#1C6EB6",
        "#61AFF3",
        "#61AFF3",
        "#61AFF3",
        "#61AFF3",
        "#ADE8F4"
    ]

    # 9. Add bars for each category
    fig.add_trace(go.Bar(
        x=plot_df['Custom Label'],
        y=plot_df['Netto Disposable'],
        name='Net Disposable Income',
        marker_color=COLOR_PALETTE_BARS,
        hovertemplate='Net Disposable Income: €%{y:,.0f}<extra></extra>'
    ))

    # 10. Add annotations for the total value on top of each bar stack
    annotations = []
    for year, total in zip(plot_df['Custom Label'], plot_df['Netto Disposable']):
        annotations.append(
            dict(
                x=year,
                y=total,
                text=f'€{total:,.0f}',
                xanchor='center',
                yanchor='bottom',
                showarrow=False,
                font=dict(size=12, color='white'),
                yshift=10
            )
        )

    # 11. Update the layout for a stacked bar style and add annotations
    fig.update_layout(
        barmode='stack',
        title="Evolution of your disposable income",
        xaxis_title="Taxation per Year",
        yaxis=dict(
            showticklabels=False,
            showgrid=False,
            showline=False,
        ),
        annotations=annotations,
        hovermode=False
    )

    # 12. Display the chart in Streamlit
    st.plotly_chart(fig, use_container_width=True)


def render_pie_chart_percent_only(labels: List[str], values: List[float]):
    """
    Render a donut pie chart showing percentage breakdown of essential living costs.

    Parameters:
    - labels: list of category names (e.g., ["Housing Costs", "Transportation", ...])
    - values: list of numeric values corresponding to labels
    - title: chart title string
    """

    # 1. Define color palette and apply
    COLOR_PALETTE_PIE = [
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
        color_discrete_sequence=COLOR_PALETTE_PIE
    )

    # 2. Additional settings to the pie chart
    fig.update_traces(
        textinfo="percent",
        textfont_color="white",
        insidetextorientation='radial',
        showlegend=True,
        hovertemplate="<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>"
    )

    fig.update_layout(
        template="plotly_white",
        height=280
    )

    st.plotly_chart(fig, use_container_width=True)
