from typing import List
import pandas as pd
from datetime import datetime


def apply_ruling(base_salary: float, months_dur: int, year: int, year_seq: int):
  # base_salary -> annual
  # function derives gross salary net of 30% taxes
  # months_dur -> months when 30% ruling will be applied
  # year_seq: which year we deal with: 0 -> first, 1 -> intermeidate year, 2-> last, 3-> no 30% ruling

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

# 30% ruling for expacts

def expat_ruling_calc(age: int,
                      base_salary: float,
                      date_string: str,
                      duration: int = 10,
                      master_dpl: bool = False):

  # INITIATE KEY PARAMETERS
  salary_cap = 233000
  salary_req_young = 35468
  salary_expert = 46660

  eligible = False
  if age >= 30 and base_salary >= 66657:
      eligible = True
  elif age < 30 and master_dpl and base_salary >= 50668:
      eligible = True

  # DETERMINE MONTHS REMAINING IN FIRST YEAR & LAST YEAR
  # date_string = "2024-12-25"

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


# ----- Calculate tax discount (arbeitskorting)

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


# ----- Return tax discount (algemene heffingskorting)

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
