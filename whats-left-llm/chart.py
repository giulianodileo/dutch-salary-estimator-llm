# CHART TO DISPLAY NET DISPOSABLE INCOME AND OTHER #
# CONSUMES DATA DICTIONARY WITH COMPONENTS         #
####################################################

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

##########################################################################
# TAX CALCULATOR                                                         #
# RETURNS tax                                                            #
##########################################################################

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
    return round(tax, 2)

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

##########################################################################
#                               CHART                                    #
#                                                                        #
##########################################################################

def chart_netincome(my_dict: dict, fixed_costs):
# example: my_dict = expat_ruling_calc(35, 35000, "2025-10-01", 7, True, True)
# see python -> calculate_30_rule for more detais or Jypeter notebook
# function receives data_dict and fixed_costs amount
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns

###############################################################################
############################ PREPARING DATA ###################################
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

# CALCULATING NETTO INCOME AFTER TAX & FIXED EXPENSES
    df["Netto Disposable"] = df["Taxable Income"] + (df["Tax"] + df["Arbeidskorting"] + df["Algemene Heffingskorting"]) - df["Fixed Costs"]
    df.loc[df["Netto Disposable"] < 0, "Netto Disposable"] = 0

# CALCULATING NET TAX
    df["Net Tax"] = df["Tax"] - (df["Arbeidskorting"] + df["Algemene Heffingskorting"])

    print(df)

#######################################################################################
############################## PREPARING CHART ########################################
#######################################################################################

# Prepare data
    plot_df = df[['Year', 'Netto Disposable', 'Fixed Costs', 'Net Tax']].copy()
    plot_df['Net Tax'] = plot_df['Net Tax'].abs()
    plot_df['Year'] = plot_df['Year'].astype(str)

# Set style and color palette
    sns.set_theme(style="whitegrid")

# Use Blues sequential palette
    colors = sns.color_palette("Blues", n_colors=3)  # 3 shades for 3 categories

# Plot stacked bars
    fig, ax = plt.subplots(figsize=(10,6))

    bottom = None
    categories = ['Netto Disposable', 'Fixed Costs','Net Tax']

    for i, cat in enumerate(categories):
                ax.bar(
                    plot_df['Year'],
                    plot_df[cat],
                    label=cat,
                    bottom=bottom,
                    color=colors[i]
                )

        # Annotate inside each segment
    for x, y, b in zip(plot_df['Year'], plot_df[cat], bottom if bottom is not None else [0]*len(plot_df)):
                if y > 0:
                    ax.text(
                        x, b + y/2, f"{y:,.0f}",
                        ha='center', va='center',
                        fontsize=9, color="black",
                    )

    bottom = plot_df[categories[:i+1]].sum(axis=1)

    # Titles & labels
    ax.set_title("Income Composition by Year", fontsize=16)
    ax.set_ylabel("Amount (€)", fontsize=12, weight='bold')
    ax.set_xlabel("Year", fontsize=12,weight='bold')

    # Legend outside
    ax.legend(
            title="Category",
            bbox_to_anchor=(1.02, 1),
            loc='upper left',
            borderaxespad=0,
            frameon=False
        )

    sns.despine()
    plt.tight_layout()
    plt.show()

    # TESTING TERMINAL

if __name__ == "__main__":
    # Example usage
    my_dict = {2025: 80000.0,
               2026: 80000.0,
               2027: 70000.0,
               2028: 70000.0,
               2029: 100000.0,
                }
    chart_netincome(my_dict, 12000)
