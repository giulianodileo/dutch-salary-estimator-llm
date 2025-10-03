# ---------- IMPORTS ---------- #

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

import streamlit as st
import sqlite3
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
DB_URI = "sqlite:///db/app.db"


# ---------- PAGE CONFIGURATION ---------- #

st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- FUNCTIONS CALCULATOR ---------- #

# ----- Salaries and Costs Estimations

def get_estimates(
    job: str,
    seniority: str,
    city: str,
    accommodation_type: str,
    car_type: Optional[str] = None,
    *,
    db_uri: str = DB_URI,
) -> Dict[str, Any]:
    """
    Provides figures regarding:
      - salary: {min, avg, max}
      - rent:   {min, avg, max}
      - car:    total_per_month (o 0 si no se pide)
    If any data is missing, the result is ValueError with a clear message
    """
    with _open(db_uri) as con:

        # 1) Retrieve Gross Salary
        row = con.execute(
            """
            SELECT jpd.min_amount, jpd.average_amount, jpd.max_amount
            FROM job_position_descriptions AS jpd
            JOIN job_positions_seniorities AS jps ON jpd.position_seniority_id = jps.id
            JOIN period  AS p ON jpd.period_id   = p.id
            JOIN currency AS c ON jpd.currency_id = c.id
            WHERE jps.position_name = ? COLLATE NOCASE
              AND jps.seniority     = ? COLLATE NOCASE
              AND p.type = 'monthly'
              AND c.currency_code = 'EUR'
            ORDER BY jpd.average_amount DESC
            LIMIT 1
            """,
            (job, seniority),
        ).fetchone()
        if not row:
            raise ValueError(f"No salary found for ({job}, {seniority}) in EUR/month.")
        sal_min, sal_avg, sal_max = map(lambda x: float(x or 0), row)

        # 2) Rent costs
        row = con.execute(
            """
            SELECT rp.min_amount, rp.average_amount, rp.max_amount
            FROM rental_prices AS rp
            JOIN period  AS p ON rp.period_id   = p.id
            JOIN currency AS c ON rp.currency_id = c.id
            WHERE rp.city               = ? COLLATE NOCASE
              AND rp.accommodation_type = ? COLLATE NOCASE
              AND p.type = 'monthly'
              AND c.currency_code = 'EUR'
            ORDER BY rp.average_amount DESC
            LIMIT 1
            """,
            (city, accommodation_type),
        ).fetchone()
        if not row:
            raise ValueError(f"No rent found for ({city}, {accommodation_type}) in EUR/month.")
        rent_min, rent_avg, rent_max = map(lambda x: float(x or 0), row)

        # 3) Car costs (optional)
        car_month = 0.0
        if car_type:
            row = con.execute(
                """
                SELECT total_per_month
                FROM transportation_car_costs
                WHERE type = ? COLLATE NOCASE
                LIMIT 1
                """,
                (car_type,),
            ).fetchone()
            if not row:
                raise ValueError(f"No car cost found for type '{car_type}'.")
            car_month = float(row[0] or 0)

    essential_costs = get_essential_costs(con, city, accommodation_type, car_type)
    utilities_breakdown = get_utilities_breakdown(con)
    health_insurance_value = get_health_insurance_value(con)

    return {
        "inputs": {
            "job": job,
            "seniority": seniority,
            "city": city,
            "accommodation_type": accommodation_type,
            "car_type": car_type,
        },
        "outputs": {
            "salary": {"min": sal_min, "avg": sal_avg, "max": sal_max},
            "rent":   {"min": rent_min, "avg": rent_avg, "max": rent_max},
            "car_total_per_month": car_month,
            "essential_costs": essential_costs,
            "health_insurance_value": health_insurance_value,
            "utilities_breakdown": utilities_breakdown,
        },
    }

# Open SQL data

def _open(db_uri: str) -> sqlite3.Connection:
    assert db_uri.startswith("sqlite:///")
    path = db_uri.replace("sqlite:///", "", 1)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

# Getting costs

def get_essential_costs(con: sqlite3.Connection, city: str, accommodation_type: str, car_type: Optional[str]) -> float:
    total = 0.0

    # --- 1) Rent ---
    rent = con.execute("""
        SELECT AVG(average_amount)
        FROM rental_prices
        WHERE city = ? AND accommodation_type = ?;
    """, (city, accommodation_type)).fetchone()[0]
    total += rent or 0

    # --- 2) Utilities (sumar todas las categorías) ---
    utilities = con.execute("""
        SELECT SUM(amount)
        FROM utilities;
    """).fetchone()[0]
    total += utilities or 0

    # --- 3) Car costs (si aplica) ---
    if car_type:
        car = con.execute("""
            SELECT AVG(total_per_month)
            FROM transportation_car_costs
            WHERE type = ?;
        """, (car_type,)).fetchone()[0]
        total += car or 0

    # --- 4) Health insurance ---
    hi = con.execute("""
        SELECT AVG(amount)
        FROM health_insurance;
    """).fetchone()[0]
    total += hi or 0

    return total

# Get utilities cost

def get_utilities_breakdown(con: sqlite3.Connection) -> Dict[str, float]:
    """
    Provides a dictionary with utility values separated by category:
    { "Water": 25.9, "Gas": 50.0, "Electricity": 80.0 }
    """
    rows = con.execute("""
        SELECT utility_type, SUM(amount)
        FROM utilities
        GROUP BY utility_type;
    """).fetchall()

    breakdown = {row[0]: row[1] for row in rows}
    return breakdown


# Get health insutance amount
def get_health_insurance_value(con: sqlite3.Connection):
    """
    Provides the cost of a basic, mandatory health insurance package.
    """
    row = con.execute("""
        SELECT amount
        FROM health_insurance
        LIMIT 1;
    """).fetchone()

    return row[0]


# ----- Apply Taxation, Tax Benefits, Net Salary, and Disposable Income

# Tax Ruling with Variations per Year

def apply_ruling(base_salary: float, months_dur: int, year: int, year_seq: int):
    """
    Applies the tax ruling in accordance with the latest updates:
    First Year (2026) -> 30% of the gross salary is going to be tax free
    Second to Fifth Year (2027-2030 -> 27% of the gross salary is going to be
    tax free
    Sixth Year and Beyond (2031-) -> Normal taxation applies. No Benefits
    -----
    base_salary -> annual gross salary
    months_dur -> number of months for which the 30% ruling applies
    year_seq -> which year we deal with:
        0 -> first,
        1 -> intermeidate year,
        2-> last,
        3-> no 30% ruling
    """

    if year in (2025, 2026) and year_seq == 0:
      # 30% ruling on months applied
      gross_taxable = (base_salary - ((base_salary * 0.3) / 12 * months_dur))
      print(gross_taxable)

    elif year in (2025, 2026) and year_seq == 1:
      # in case 2025, 2025 not first year -> full year 30% ruling
      gross_taxable = base_salary - (base_salary * 0.3)
      print(gross_taxable)

    elif year not in (2025, 2026) and year_seq == 1:
      # in case 2026 or later and 27% ruling whole year
      gross_taxable = base_salary - (base_salary * 0.27)
      print(gross_taxable)

    elif year not in (2025, 2026) and year_seq == 2:
      # in case 2026 or later and 30% ruling part of the year
      gross_taxable = ((base_salary - (base_salary * 0.3)) / 12 * months_dur) + (base_salary / 12 * (12 - months_dur))
      print(gross_taxable)

    else:
      # no 30% ruling and year later than 2026
      print(gross_taxable)
      gross_taxable = base_salary

    return gross_taxable

# Conditions for expacts to be eligible for tax ruling

def expat_ruling_calc(age: int,
                      base_salary: float,
                      date_string: str,
                      duration: int = 10,
                      master_dpl: bool = False):
    """
    This will determine if an expat is eligible for the tax ruling or not,
    based on the following criteria:
        - If the expact is younger than 30, then has to hold a master's
        degree and receive a salary of at least 35,468€
        - If the expact is 30 years old or older, then has to receive a salary
        of at least 46,660€
    -----
    age -> different criterias apply for those being younger than 30 years old
    base_salary -> There is a minimum required salary for which the tax benefit
    can be applied
    date_string -> Starting date from which the tax ruling would apply.
    By default, this is always 2026-01-01
    duration -> amount of years for which the tax ruling applies (or not)
    master_dpl -> special requirement for under 30s: they need to own a
    master's degree (or higher level).
    """

    # 1) Initiate key paramenters to be eligible for the tax ruling:
    # - Maximum gross salary: 233,000€
    salary_cap = 246000
    # - Minimum required salary for under 30s: 35,468€
    salary_req_young = 35468
    # - Minimum required salary for over 30s: 46,660€
    salary_expert = 46660
    eligible = False

    if age >= 30 and base_salary >= salary_req_young:
        eligible = True

    elif age < 30 and master_dpl and base_salary >= salary_expert and base_salary < salary_cap:
        eligible = True

    # 2) Define the starting date from which the tax rule starts to apply

    start_date = datetime.strptime(date_string, "%Y-%m-%d")

    # DETERMINE CURRENT YEAR
    current_year = start_date.year

    months_remaining_init = 12 - start_date.month + 1
    months_remaining_final = 12 - months_remaining_init

  # YEARS SEQUENCE
  # CREATE A SEQUENCE OF YEARS EXPECTED TO BE EMPLOYED IN NL
  # CREATE DICTIONARY TO KEEP VALUES IN

    years_sequence = list(range(current_year, current_year + duration))
    my_dict = {}
    my_key = years_sequence

    for key in my_key:
        my_dict[key] = ""

  # CHECK IF 30% RULING WILL APPLY

    if age < 30 and eligible == True and master_dpl == True and base_salary >= salary_req_young:
            Ruling_test = True
    elif age >= 30 and eligible == True and base_salary >= salary_expert:
            Ruling_test = True
    else:
            Ruling_test = False

  # CALCULATION BASE

    if base_salary > salary_cap:
        base_salary = salary_cap
    else:
        base_salary = base_salary

    keys_list = list(my_dict.keys())  # Get the tuple
    keys = list(keys_list)  # Convert tuple to list: ['A', 'B', 'C']

  # CHECKING IF THERE IS A BROKEN YEAR AND CALCULATING THESE PARTS #
  ##################################################################

    if Ruling_test == True:
        # months_remaining_init != 12 and Ruling_test == True:
        # if start date not January

        year1 = apply_ruling(base_salary, months_remaining_init, int(keys_list[0]), 0)
        year5 = apply_ruling(base_salary, months_remaining_final, int(keys_list[4]), 2)
        my_dict[keys[0]] = year1
        my_dict[keys[4]] = year5

        # other years -not first and last years
        other_years_sequence = list(keys_list[1:5])

        for key in other_years_sequence:
            if key >= 2027:
            # new 27% ruling
                my_dict[key] = apply_ruling(base_salary, 12, int(key), 1)

        else:
            # apply 30% ruling
            my_dict[key] = apply_ruling(base_salary, 12, int(key), 1)

        # populating remainder of the dictionary - no ruling
        for key in keys_list[5:]:

            my_dict[key] = float(base_salary)

        return my_dict

    else:
        # not applicable - not fulfilling conditions
        # populating remainder of the dictionary - no ruling
        for key in keys_list:

            my_dict[key] = float(base_salary)

        return my_dict

# -------------------- CHARTS --------------------

# Pie chart function

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
        textfont_color="black",
        insidetextorientation='radial',
        hovertemplate="<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>"
    )
    fig.update_traces(textinfo="percent", textfont_color="white")

    fig.update_layout(template="plotly_white")

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

#

def calc_tax(gross_salary: float) -> float:

    # --- 1) Guardrail: input should be non-negative
    if gross_salary < 0:
        raise ValueError("gross_salary must be non-negative")

    # --- 2) Define the 2025 Box 1 brackets as (upper_limit, rate)
    # Bracket 1: 0        .. 38,441  -> 35.82%
    # Bracket 2: 38,441   .. 76,817  -> 37.48%
    # Bracket 3: 76,817   .. +inf    -> 49.50%
    # We implement these as cumulative upper bounds. The last one is infinity.
    brackets: List[Tuple[float, float]] = [
        (38_441.00, 0.3582),
        (76_817.00, 0.3748),
        (float("inf"), 0.4950),
    ]

    # assume taxable income is gross salary
    taxable_income = gross_salary

    # Walk the brackets and accumulate tax per slice
    tax = 0.0
    lower_limit = 0.0

    for upper_limit, rate in brackets:
        # Income that falls inside THIS bracket:
        #   from the current lower_limit up to the bracket's upper_limit,
        #   but never exceeding taxable_income.
        slice_amount = max(0.0, min(taxable_income, upper_limit) - lower_limit)
        if slice_amount <= 0:
            # No taxable income left for this or further brackets.
            break
        # Tax for this slice = slice_amount * rate
        tax += slice_amount * rate
        # Move the lower bound up to this bracket's upper limit
        lower_limit = upper_limit
        # If we've already taxed the entire taxable_income, stop early
        if taxable_income <= upper_limit:
            break

    # Net income = full gross - tax
    net_income = gross_salary - tax

    # Return with cents precision
    print(round(tax, 2))
    return round(tax, 2)
calc_tax(74400)
##########################################################################
# CALCULATOR for ARBEIDSKORTING                                          #
# RETURNS tax discount (arbeitskorting)                                  #
##########################################################################

def bereken_arbeidskorting(salaris):
    """
    Berekent de arbeidskorting voor Nederland 2025 op basis van het brutosalaris.
    De arbeidskorting heeft 4 fases:
    - Fase 1 (€0 - €11.491): 0% korting
    - Fase 2 (€11.491 - €24.821): Opbouw van 31,15%
    - Fase 3 (€24.821 - €39.958): Plateau van €4.152
    - Fase 4 (€39.958 - €124.934): Afbouw van 6%
    - Boven €124.934: Geen arbeidskorting
    Args:
        salaris (float): Het bruto jaarsalaris in euro's
    Returns:
        float: De arbeidskorting in euro's
    """

    # Grenzen en tarieven arbeidskorting 2025
    GRENS_1 = 11491    # Ondergrens voor arbeidskorting
    GRENS_2 = 24821    # Einde opbouwfase
    GRENS_3 = 39958    # Einde plateau
    GRENS_4 = 124934   # Bovengrens arbeidskorting

    OPBOUW_TARIEF = 0.3115    # 31,15% opbouw in fase 2
    MAX_KORTING = 4152        # Maximum arbeidskorting (plateau)
    AFBOUW_TARIEF = 0.06      # 6% afbouw in fase 4

    # Input validatie
    if salaris < 0:
        raise ValueError("Salaris kan niet negatief zijn")

    # Fase 1: €0 - €11.491 (geen korting)
    if salaris <= GRENS_1:
        return 0.0

    # Fase 2: €11.491 - €24.821 (opbouw 31,15%)
    elif salaris <= GRENS_2:
        opbouw_bedrag = salaris - GRENS_1
        korting = opbouw_bedrag * OPBOUW_TARIEF
        return round(korting, 2)

    # Fase 3: €24.821 - €39.958 (plateau €4.152)
    elif salaris <= GRENS_3:
        return MAX_KORTING

    # Fase 4: €39.958 - €124.934 (afbouw 6%)
    elif salaris <= GRENS_4:
        afbouw_bedrag = salaris - GRENS_3
        afbouw = afbouw_bedrag * AFBOUW_TARIEF
        korting = MAX_KORTING - afbouw
        return round(max(korting, 0), 2)  # Minimum 0

    # Boven €124.934: geen arbeidskorting meer
    else:
        return 0.0


##########################################################################
# CALCULATOR for ALGEMENE HEFFINGSKORTING                                #
# RETURNS tax discount (algemene heffingskorting                         #
##########################################################################

def bereken_algemene_heffingskorting(salaris):
    """
    Berekent de algemene heffingskorting voor Nederland 2025 op basis van het brutosalaris.
    De algemene heffingskorting heeft 3 fases:
    - Fase 1 (€0 - €24.812): Volledige korting van €3.362
    - Fase 2 (€24.812 - €76.421): Afbouw van 6,007% per euro boven €24.812
    - Fase 3 (boven €76.421): Geen algemene heffingskorting meer

    Args:
        salaris (float): Het bruto jaarsalaris in euro's
    Returns:
        float: De algemene heffingskorting in euro's
    """

    # Grenzen en tarieven algemene heffingskorting 2025
    MAXIMUM_KORTING = 3362      # Maximum algemene heffingskorting
    AFBOUW_ONDERGRENS = 24812   # Vanaf dit bedrag begint afbouw
    AFBOUW_BOVENGRENS = 76421   # Boven dit bedrag is er geen korting meer
    AFBOUW_TARIEF = 0.06007     # 6,007% afbouw per euro boven de ondergrens

    # Input validatie
    if salaris < 0:
        raise ValueError("Salaris kan niet negatief zijn")

    # Fase 1: €0 - €24.812 (volledige korting)
    if salaris <= AFBOUW_ONDERGRENS:
        return MAXIMUM_KORTING

    # Fase 2: €24.812 - €76.421 (afbouw 6,007%)
    elif salaris <= AFBOUW_BOVENGRENS:
        afbouw_bedrag = salaris - AFBOUW_ONDERGRENS
        afbouw = afbouw_bedrag * AFBOUW_TARIEF
        korting = MAXIMUM_KORTING - afbouw
        return round(max(korting, 0), 2)  # Minimum 0

    # Fase 3: Boven €76.421 (geen korting meer)
    else:
        return 0.0


def return_net_income(my_dict: dict, fixed_costs):

###############################################################################
############################ RETURN NET INCOME YEAR 1##########################
###############################################################################

# CONVERTING TO PANDA DATAFRAME AND ADDING OTHER PARAMETERS
    df = pd.DataFrame(list(my_dict.items()), columns=["Year", "Taxable Income"])

# ADDING FIXED COSTS FROM DICTIONARY
    df["Fixed Costs"] = fixed_costs

# CALCULATING TAX
    df["Tax"] = round(-df["Taxable Income"].apply(calc_tax), 0)

# CALCULATING DEDUCTABLES
    df["Arbeidskorting"] = round(df["Taxable Income"].apply(bereken_arbeidskorting),0)
    df["Algemene Heffingskorting"] = round(df["Taxable Income"].apply(bereken_algemene_heffingskorting),0)

# CALCULATING NET TAX
    df["Net Tax"] = - (abs(df["Tax"]) - (df["Arbeidskorting"] + df["Algemene Heffingskorting"]))

# CALCULATING NETTO INCOME AFTER TAX & FIXED EXPENSES
    df["Netto Disposable"] = df["Taxable Income"] + df["Net Tax"] - df["Fixed Costs"]
    df.loc[df["Netto Disposable"] < 0, "Netto Disposable"] = 0

    return df["Netto Disposable"].iloc[0]


# Netto charts

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

    # -----------------------------------------------------------
    # DATA PREPARATION (UNCHANGED)
    # -----------------------------------------------------------

    # Convert the dictionary to a Pandas DataFrame
    df = pd.DataFrame(list(my_dict.items()), columns=["Year", "Taxable Income"])

    # Add fixed costs to the DataFrame
    df["Fixed Costs"] = fixed_costs

    # Calculate taxes and deductions
    df["Tax"] = round(-df["Taxable Income"].apply(calc_tax), 0)
    df["Arbeidskorting"] = round(df["Taxable Income"].apply(bereken_arbeidskorting), 0)
    df["Algemene Heffingskorting"] = round(df["Taxable Income"].apply(bereken_algemene_heffingskorting), 0)
    df["Gross Salary"] = gross_salary
    # Calculate net tax
    df["Net Tax"] = - (abs(df["Tax"]) - (df["Arbeidskorting"] + df["Algemene Heffingskorting"]))

    # Calculate net disposable income after tax and expenses
    # df["Netto Disposable"] = df["Taxable Income"] + df["Net Tax"] - df["Fixed Costs"]

    df["Netto Disposable"] = df["Gross Salary"] + df["Net Tax"] - df["Fixed Costs"]



    df.loc[df["Netto Disposable"] < 0, "Netto Disposable"] = 0

    # -----------------------------------------------------------
    # CHART PREPARATION AND VISUALIZATION WITH PLOTLY
    # -----------------------------------------------------------

    # Check eligibility to display the chart
    eligible = False
    if age >= 30 and gross_salary >= 66657:
        eligible = True
    elif age < 30 and master_dpl and gross_salary >= 50668:
        eligible = True

    if not eligible:
        print("You are not eligible to view the chart based on the criteria.")
        return # Exit the function if not eligible

    # If eligible, prepare the data and create the chart
    plot_df = df[['Year', 'Netto Disposable', 'Fixed Costs', 'Net Tax']].copy()

    # --- CAMBIO CLAVE: MANTENER SOLO 6 AÑOS Y AÑADIR LAS ETIQUETAS ---
    plot_df = plot_df.head(6)

    # Define custom labels
    custom_labels = [
        "30% 2026",
        "27% 2027",
        "27% 2028",
        "27% 2029",
        "27% 2030",
        "37% 2031+",
        # "Normal taxes 2032+",
        # "Normal taxes 2033+",
        # "Normal taxes 2034+",
        # "Normal taxes 2035+"
    ]

    # Añadir la nueva columna al DataFrame
    plot_df['Custom Label'] = custom_labels
    # -----------------------------------------------------------------

    plot_df['Net Tax'] = plot_df['Net Tax'].abs()

    # Convert to monthly values and ensure a numeric type
    numeric_cols = ['Netto Disposable', 'Fixed Costs', 'Net Tax']
    for col in numeric_cols:
        plot_df[col] = pd.to_numeric(plot_df[col], errors='coerce') / 12
    plot_df = plot_df.fillna(0)

    # Calculate the total monthly income for annotations
    plot_df['Total'] = plot_df['Netto Disposable'] + plot_df['Fixed Costs'] + plot_df['Net Tax']

    # Create the stacked bar chart with Plotly
    fig = go.Figure()

    # Define a clean color palette
    COLOR_PALETTE = ["#1C6EB6", "#61AFF3","#61AFF3", "#61AFF3", "#61AFF3", "#ADE8F4"]


    # Add the bars for each category
    fig.add_trace(go.Bar(
        x=plot_df['Custom Label'],
        y=plot_df['Netto Disposable'],
        name='Net Disposable Income',
        marker_color=COLOR_PALETTE,
        hovertemplate='Net Disposable Income: €%{y:,.0f}<extra></extra>'
    ))

    # Add annotations for the total value on top of each bar stack
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

    # Update the layout for a stacked bar style and add annotations
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

    # Display the chart in Streamlit
    st.plotly_chart(fig, use_container_width=True)




def netincome(my_dict: dict, fixed_costs, gross_salary):

    # Convert the dictionary to a Pandas DataFrame
    df = pd.DataFrame(list(my_dict.items()), columns=["Year", "Taxable Income"])

    # Add fixed costs to the DataFrame
    df["Fixed Costs"] = fixed_costs

    # Calculate taxes and deductions
    df["Tax"] = round(-df["Taxable Income"].apply(calc_tax), 0)
    df["Arbeidskorting"] = round(df["Taxable Income"].apply(bereken_arbeidskorting), 0)
    df["Algemene Heffingskorting"] = round(df["Taxable Income"].apply(bereken_algemene_heffingskorting), 0)
    df["Gross Salary"] = gross_salary
    # Calculate net tax
    df["Net Tax"] = - (abs(df["Tax"]) - (df["Arbeidskorting"] + df["Algemene Heffingskorting"]))

    # Calculate net disposable income after tax and expenses
    # df["Netto Disposable"] = df["Taxable Income"] + df["Net Tax"] - df["Fixed Costs"]


    df["Netto Disposable"] = df["Gross Salary"] + df["Net Tax"]

    print(df)

    return df["Netto Disposable"].iloc[0]


def netto_disposable(my_dict: dict, fixed_costs, gross_salary):

    # Convert the dictionary to a Pandas DataFrame
    df = pd.DataFrame(list(my_dict.items()), columns=["Year", "Taxable Income"])

    # Add fixed costs to the DataFrame
    df["Fixed Costs"] = fixed_costs

    # Calculate taxes and deductions
    df["Tax"] = round(-df["Taxable Income"].apply(calc_tax), 0)
    df["Arbeidskorting"] = round(df["Taxable Income"].apply(bereken_arbeidskorting), 0)
    df["Algemene Heffingskorting"] = round(df["Taxable Income"].apply(bereken_algemene_heffingskorting), 0)
    df["Gross Salary"] = gross_salary
    # Calculate net tax
    df["Net Tax"] = - (abs(df["Tax"]) - (df["Arbeidskorting"] + df["Algemene Heffingskorting"]))

    # Calculate net disposable income after tax and expenses
    # df["Netto Disposable"] = df["Taxable Income"] + df["Net Tax"] - df["Fixed Costs"]


    df["Netto Disposable"] = df["Gross Salary"] + df["Net Tax"]


    df["Netto Disposable"] = df["Netto Disposable"]/12
    print(df)
    return df.set_index("Year")["Netto Disposable"].to_dict()

def net_tax(my_dict: dict, fixed_costs, gross_salary):

    # Convert the dictionary to a Pandas DataFrame
    df = pd.DataFrame(list(my_dict.items()), columns=["Year", "Taxable Income"])

    # Add fixed costs to the DataFrame
    df["Fixed Costs"] = fixed_costs

    # Calculate taxes and deductions
    df["Tax"] = round(-df["Taxable Income"].apply(calc_tax), 0)
    df["Arbeidskorting"] = round(df["Taxable Income"].apply(bereken_arbeidskorting), 0)
    df["Algemene Heffingskorting"] = round(df["Taxable Income"].apply(bereken_algemene_heffingskorting), 0)
    df["Gross Salary"] = gross_salary
    # Calculate net tax
    df["Net Tax"] = - (abs(df["Tax"]) - (df["Arbeidskorting"] + df["Algemene Heffingskorting"]))

    # Calculate net disposable income after tax and expenses
    # df["Netto Disposable"] = df["Taxable Income"] + df["Net Tax"] - df["Fixed Costs"]


    df["Netto Disposable"] = (df["Gross Salary"] + df["Net Tax"])
    df["Net Tax"] = df["Net Tax"]/12

    print(df)

    return df.set_index("Year")["Net Tax"].to_dict()

# ---------------------------------------- UI Frontend --------------------


# ----- Page Config (Optional - customize per page) -----
st.set_page_config(page_title="Your Page Title", layout="wide")

# ----- MAIN STYLING SECTION (Copy this to all pages) -----
st.markdown("""
<style>
/* Remove the white bar / header background */
header[data-testid="stHeader"] {
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%);
    border-bottom: none;
}

/* Also color the toolbar (Deploy / menu) area */
header[data-testid="stHeader"] .st-emotion-cache-1dp5vir {
    background: transparent;
}

/* Main app background with enhanced gradient */
.stApp {
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%);
    min-height: 100vh;
}

/* All text colors */
h1, h2, h3, h4, h5, h6, p, span, div, .stMarkdown {
    color: white !important;
}

/* Title styling */
h1 {
    font-size: 2.5rem !important;
    font-weight: 600 !important;
    text-align: center;
    margin-bottom: 2rem !important;
    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

/* Section headers */
h3 {
    font-size: 1.5rem !important;
    font-weight: 500 !important;
    margin-bottom: 1.5rem !important;
    text-align: center;
    text-shadow: 0 1px 2px rgba(0,0,0,0.2);
}

/* Hide Streamlit elements */
.stDeployButton {
    display: none;
}

footer {
    display: none;
}

#MainMenu {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)

# ===== OPTIONAL ADDITIONAL COMPONENTS =====
# Include these only on pages where you need them

# ----- Glassmorphism Container Styling (for cards/containers) -----
glassmorphism_css = """
<style>
/* Column containers */
.column-container {
    padding: 1rem;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 15px;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
}

/* Item styling for lists/rows */
.item-row {
    display: flex;
    align-items: center;
    padding: 0.8rem 1rem;
    margin-bottom: 1rem;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    backdrop-filter: blur(5px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    transition: all 0.3s ease;
}

.item-row:hover {
    background: rgba(255, 255, 255, 0.15);
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

/* Image container */
.item-image {
    margin-right: 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 50px;
    height: 50px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 50%;
    padding: 8px;
}

/* Item text */
.item-text {
    font-weight: 500 !important;
    font-size: 1.1rem !important;
    color: white !important;
}
</style>
"""

# ----- Divider Styling (for column separators) -----
divider_css = """
<style>
/* Enhanced divider styling */
.divider {
    border-left: 2px solid rgba(255, 255, 255, 0.3);
    min-height: 400px;
    margin: auto;
    box-shadow: 0 0 10px rgba(255, 255, 255, 0.1);
}
</style>
"""

# ===== USAGE EXAMPLES =====

# To use glassmorphism containers:
# st.markdown(glassmorphism_css, unsafe_allow_html=True)
# st.markdown("<div class='column-container'>Your content here</div>", unsafe_allow_html=True)

# To use dividers:
# st.markdown(divider_css, unsafe_allow_html=True)
# st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# ===== SIMPLIFIED VERSION FOR BASIC PAGES =====
# If you just need the background and text colors, use only this:

# ---------- BASIC PAGE STYLING ---------- #

def apply_full_styling():
    """Apply complete blue theme styling including sidebar"""
    st.markdown("""
    <style>
    /* Remove the white bar / header background */
    header[data-testid="stHeader"] {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%);
        border-bottom: none;
    }

    /* Also color the toolbar (Deploy / menu) area */
    header[data-testid="stHeader"] .st-emotion-cache-1dp5vir {
        background: transparent;
    }

    /* Main app background with enhanced gradient */
    .stApp {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%);
        min-height: 100vh;
    }

    /* All text colors */
    h1, h2, h3, h4, h5, h6, p, span, div, .stMarkdown {
        color: white !important;
    }

    /* Title styling */
    h1 {
        font-size: 2.5rem !important;
        font-weight: 600 !important;
        text-align: center;
        margin-bottom: 2rem !important;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }

    /* Section headers */
    h3 {
        font-size: 1.5rem !important;
        font-weight: 500 !important;
        margin-bottom: 1.5rem !important;
        text-align: center;
        text-shadow: 0 1px 2px rgba(0,0,0,0.2);
    }

    /* SIDEBAR STYLING */
    /* Sidebar background */
    .css-1d391kg {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%);
    }

    /* Sidebar content area */
    .stSidebar > div:first-child {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%);
    }

    /* Fix for newer Streamlit versions */
    section[data-testid="stSidebar"] {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%) !important;
    }

    section[data-testid="stSidebar"] > div {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%) !important;
    }

    /* Sidebar text colors */
    .stSidebar .stMarkdown,
    .stSidebar .stSelectbox label,
    .stSidebar .stTextInput label,
    .stSidebar .stNumberInput label,
    .stSidebar .stTextArea label,
    .stSidebar .stDateInput label,
    .stSidebar .stTimeInput label,
    .stSidebar .stFileUploader label,
    .stSidebar .stColorPicker label,
    .stSidebar .stSlider label,
    .stSidebar .stRadio label,
    .stSidebar .stCheckbox label,
    .stSidebar .stMultiSelect label,
    .stSidebar h1, .stSidebar h2, .stSidebar h3,
    .stSidebar h4, .stSidebar h5, .stSidebar h6,
    .stSidebar p, .stSidebar span, .stSidebar div {
        color: white !important;
    }

    /* Sidebar input fields */
    .stSidebar .stSelectbox select,
    .stSidebar .stTextInput input,
    .stSidebar .stNumberInput input,
    .stSidebar .stTextArea textarea {
        background: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 5px;
    }

    /* Sidebar buttons */
    .stSidebar .stButton button {
        background: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 8px;
        backdrop-filter: blur(5px);
        transition: all 0.3s ease;
    }

    .stSidebar .stButton button:hover {
        background: rgba(255, 255, 255, 0.2) !important;
        border-color: rgba(255, 255, 255, 0.5) !important;
        transform: translateY(-1px);
    }

    /* Hide Streamlit elements */
    .stDeployButton {
        display: none;
    }

    footer {
        display: none;
    }

    #MainMenu {
        visibility: hidden;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------- LLM CHAT STYLING ---------- #

def apply_chat_styling():
    """Apply blue theme styling for Salary Chat page (with left-aligned big title)"""
    st.markdown("""
    <style>
    /* Background + header */
    header[data-testid="stHeader"] {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%) !important;
        border-bottom: none !important;
    }
    header[data-testid="stHeader"] .st-emotion-cache-1dp5vir {
        background: transparent !important;
    }
    .stApp {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%) !important;
        min-height: 100vh !important;
    }

    /* Text */
    h1, h2, h3, h4, h5, h6, p, span, div, .stMarkdown {
        color: white !important;
    }

    /* Title */
    h1 {
        font-size: 3rem !important;     /* bigger than default */
        font-weight: 700 !important;    /* bolder */
        text-align: left !important;    /* lock to left */
        margin-bottom: 2rem !important;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
    }

    /* Info boxes */
    .stAlert {
        background: rgba(255, 255, 255, 0.15) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 8px !important;
    }

    /* Buttons (Ask + Suggested Questions unified style) */
    .stButton button {
        background: rgba(255, 255, 255, 0.25) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 500 !important;
        backdrop-filter: blur(8px) !important;
        transition: all 0.3s ease !important;
        font-size: 1rem !important;
    }
    .stButton button:hover {
        background: rgba(255, 255, 255, 0.35) !important;
        border-color: rgba(255, 255, 255, 0.6) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3) !important;
    }

    /* Typing bar (textarea) */
    div[data-testid="stTextArea"] textarea {
        background-color: rgba(255, 255, 255, 0.25) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        border-radius: 8px !important;
        padding: 0.6rem !important;
        backdrop-filter: blur(8px) !important;
        font-size: 1rem !important;
    }
    div[data-testid="stTextArea"] textarea::placeholder {
        color: rgba(255, 255, 255, 0.8) !important;
    }

    /* Text input (if used) */
    div[data-testid="stTextInput"] input {
        background-color: rgba(255, 255, 255, 0.25) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        border-radius: 8px !important;
        padding: 0.5rem !important;
        backdrop-filter: blur(8px) !important;
        font-size: 1rem !important;
    }
    div[data-testid="stTextInput"] input::placeholder {
        color: rgba(255, 255, 255, 0.8) !important;
    }

    /* Hide Streamlit branding */
    .stDeployButton { display: none !important; }
    footer { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    </style>
    """, unsafe_allow_html=True)

# ---------- CALCULATOR STYLING --------- #

def apply_calculator_styling():
    """Apply blue theme styling for Salary Calculator page (with transparent charts)"""
    st.markdown("""
    <style>
    /* Background + header */
    header[data-testid="stHeader"] {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%) !important;
        border-bottom: none !important;
    }
    header[data-testid="stHeader"] .st-emotion-cache-1dp5vir {
        background: transparent !important;
    }
    .stApp {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #004e92 100%) !important;
        min-height: 100vh !important;
    }

    /* Text */
    h1, h2, h3, h4, h5, h6, p, span, div, .stMarkdown {
        color: white !important;
    }

    /* Title */
    h1 {
        font-size: 3rem !important;
        font-weight: 700 !important;
        text-align: left !important;
        margin-bottom: 2rem !important;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
    }

    /* Info boxes */
    .stAlert {
        background: rgba(255, 255, 255, 0.15) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 8px !important;
    }

    /* Buttons */
    .stButton button {
        background: rgba(255, 255, 255, 0.25) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 500 !important;
        backdrop-filter: blur(8px) !important;
        transition: all 0.3s ease !important;
        font-size: 1rem !important;
    }
    .stButton button:hover {
        background: rgba(255, 255, 255, 0.35) !important;
        border-color: rgba(255, 255, 255, 0.6) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3) !important;
    }

    /* Plotly chart containers (force transparent) */
    div[data-testid="stPlotlyChart"] {
        background: rgba(0,0,0,0) !important;
    }
    div[data-testid="stPlotlyChart"] iframe {
        background: rgba(0,0,0,0) !important;
    }

    /* Hide Streamlit branding */
    .stDeployButton { display: none !important; }
    footer { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    </style>
    """, unsafe_allow_html=True)



# -------------------- DB HELPERS --------------------
def _sqlite_path(db_uri: str) -> str:
    assert db_uri.startswith("sqlite:///")
    return db_uri.replace("sqlite:///", "", 1)

def _open(db_uri: str) -> sqlite3.Connection:
    path = _sqlite_path(db_uri)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def load_options(db_uri: str = DB_URI) -> Dict[str, List[str]]:
    opts = {"jobs": [], "seniorities": [], "cities": [], "accommodations": [], "cars": []}
    path = _sqlite_path(db_uri)
    if not Path(path).exists():
        return opts

    with _open(db_uri) as con:
        rows = con.execute("SELECT DISTINCT position_name FROM job_positions_seniorities ORDER BY position_name;").fetchall()
        opts["jobs"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT seniority FROM job_positions_seniorities ORDER BY seniority;").fetchall()
        opts["seniorities"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT city FROM rental_prices ORDER BY city;").fetchall()
        opts["cities"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT accommodation_type FROM rental_prices WHERE accommodation_type IS NOT NULL ORDER BY accommodation_type;").fetchall()
        opts["accommodations"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT type FROM transportation_car_costs ORDER BY type;").fetchall()
        opts["cars"] = [r[0] for r in rows]

    return opts

opts = load_options(DB_URI)
if not any(opts.values()):
    st.error("Database not found or empty. Load it before using the app.")
    st.stop()

# Clean labels within the user input page
def clean_label(text: str) -> str:
    return text.replace("_", " ").replace("-", " ").title() if text else text


# -------------------- PAGE 1: SALARY CALCULATOR --------------------

st.markdown("### Disposable income Calculator")

# Load options from the database
opts = load_options(DB_URI)
if not any(opts.values()):
    st.error("I cannot find the database, or the tables are empty. Please ensure that you have created it and uploaded the JSONs.")
    st.stop()

# Build cleaned versions
jobs_display = [clean_label(j) for j in opts["jobs"]]
seniorities_display = [clean_label(s) for s in opts["seniorities"]]
cities_display = [clean_label(c) for c in opts["cities"]]
accommodations_display = [clean_label(a) for a in opts["accommodations"]]
cars_display = [clean_label(c) for c in opts["cars"]]


with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        user_name = st.text_input("Name", "")
    if user_name:
        st.success(f"Welcome, {user_name}! 😎")
    with col2:
        age = st.number_input("Age", min_value=18, max_value=70, step=1)

    with col1:
        job_display = st.selectbox("Job", jobs_display)
        job = opts["jobs"][jobs_display.index(job_display)]

    with col2:
        seniority_display = st.selectbox("Seniority", seniorities_display)
        seniority = opts["seniorities"][seniorities_display.index(seniority_display)]

    with col1:
        city_display = st.selectbox("City", cities_display)
        city = opts["cities"][cities_display.index(city_display)]

    with col2:
        accommodation_display = st.selectbox("Accommodation", accommodations_display)
        accommodation_type = opts["accommodations"][accommodations_display.index(accommodation_display)]

    with col1:
        has_masters_nl = st.selectbox("Master's degree (or higher education)", ["Yes", "No"])

    with col2:
        car_display = st.selectbox("Car type", ["No"] + cars_display)
        if car_display == "No":
            car_cost = 0
        else:
            car_cost = opts["cars"][cars_display.index(car_display)]

    submitted = st.button("What's Left")


def check_degree_requirement(age: int, has_degree: str) -> bool:
    if age < 30 and has_degree == "Yes":
        return True
    return False

degre_value = check_degree_requirement(age, has_masters_nl)

# --------------------- INPUTS ---------------------------
if submitted:
    try:
        res: Dict[str, Any] = get_estimates(
            job=job,
            seniority=seniority,
            city=city,
            accommodation_type=accommodation_type,
            car_type=car_cost,
            db_uri=DB_URI
        )
        out = res["outputs"]

        extra = {
            "age": int(age),
            "master_diploma": bool(degre_value)
        }

        res_tax = expat_ruling_calc(
            age=extra["age"],
            base_salary=out['salary']['avg'] * 12,
            date_string="2026-01-01",
            duration=6,
            master_dpl=extra["master_diploma"],

        )

        # First year values
        first_year = min(res_tax.keys())
        net_first_year = res_tax[first_year] / 12
        disposable_first_year = net_first_year - out['essential_costs']

        payload = {
            "inputs": res["inputs"],
            "extra": extra,
            "outputs": out,
            "tax dict": res_tax,
        }

        netnet = (netincome(payload["tax dict"], out['essential_costs']*12, out['salary']['avg']*12)/12)
        pocket = netnet - out['essential_costs']


        net_taxx =  net_tax(payload["tax dict"], out['essential_costs']*12, out['salary']['avg']*12)
        netto_disposablee = netto_disposable(payload["tax dict"], out['essential_costs']*12, out['salary']['avg']*12)

        payload = {
            "inputs": res["inputs"],
            "extra": extra,
            "outputs": out,
            "tax dict": res_tax,
            "net": netnet,
            "pocket": pocket,
            "netto_disposable": netto_disposablee,
            "net_tax": net_taxx
        }

        st.session_state["last_payload"] = payload
        car_value = payload["outputs"]["car_total_per_month"]

        # ---- Metrics ----
        with st.container(border=True):

            st.markdown(
                """
                <style>
                [data-testid="stMetricValue"] {
                    font-size: 24px;
                }
                [data-testid="stMetricLabel"] {
                    font-size: 20px;
                    font-weight: 600;
                }
                </style>
                """,
                unsafe_allow_html=True
            )
            netnet = (netincome(payload["tax dict"], out['essential_costs']*12, out['salary']['avg']*12)/12)
            pocket = netnet - out['essential_costs']

            st.markdown("#### Your overview")
            col1, col2 = st.columns(2)

# --------------------------------------------------------------------------------

            col2.metric("Net salary", f"€{netnet:,.0f}")
            col2.metric("Disposable income", f"€{pocket:,.0f}")
            col1.metric("Gross salary", f"€{out['salary']['avg']:,.0f}")
            col1.metric("Costs", f"€{out['essential_costs']:,.0f}")
            with st.container():
                with st.expander("Discover your costs"):
                    col1, col2 = st.columns(2)
                    with col1:
                        subcol1, subcol2 = st.columns(2)
                        with subcol1:
                            subcol1.metric("Rent", f"€{out['rent']['avg']:,.0f}")
                            subcol1.metric("Car", f"€{car_value:,.0f}")
                            subcol1.metric("Health Insurance", f"€{out['health_insurance_value']:,.0f}")
                        with subcol2:
                            subcol2.metric("Gas", f"€{out['utilities_breakdown']['Gas']:,.0f}")
                            subcol2.metric("Electricity", f"€{out['utilities_breakdown']['Electricity']:,.0f}")
                            subcol2.metric("Water", f"€{out['utilities_breakdown']['Water']:,.0f}")
                    with col2:
                        labels = ["Rent", "Car", "Health Insurance", "Gas", "Electricity", "Water"]
                        utilities = out['utilities_breakdown']
                        values = [
                            out['rent']['avg'],
                            out['car_total_per_month'],
                            utilities.get("Gas", 0),
                            utilities.get("Electricity", 0),
                            utilities.get("Water", 0),
                            out['health_insurance_value']
                        ]
                        render_pie_chart_percent_only(labels, values)



        with st.container():
            chart_netincome(res_tax, out['essential_costs']*12, age, out['salary']['avg']*12, degre_value)

        # Option to visualize JSON
        # with st.expander("Raw payload (JSON)"):
        #     import json
        #     st.code(json.dumps(payload, indent=2), language="json")



    except ValueError as ve:
        st.warning(str(ve))
    except Exception as e:
        st.error(f"Unexpected error: {e}")
else:
    st.info("Fill in the fields and press **What's Left**.")


# PALETTE = {
#     "navy":   "#03045E",
#     "blue9":  "#023E8A",
#     "blue7":  "#0077B6",
#     "blue6":  "#0096C7",
#     "blue5":  "#00B4D8",
#     "blue4":  "#48CAE4",
#     "blue3":  "#90E0EF",
#     "blue2":  "#ADE8F4",
#     "blue1":  "#CAF0F8",
# }
