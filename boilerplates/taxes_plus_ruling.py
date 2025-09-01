#####################################################################
# DUTCH TAX BRACKETS 2025                                           #
#####################################################################

def apply_nl_taxes_2025(taxable_income: float) -> float:
    """Apply Dutch 2025 Box 1 tax rates to taxable income. Returns net annual."""
    brackets = [
        (38441, 0.3582),
        (76817, 0.3748),
        (float("inf"), 0.495),
    ]

    tax = 0
    last_cap = 0
    remaining = taxable_income

    for cap, rate in brackets:
        income_in_bracket = min(remaining, cap - last_cap)
        if income_in_bracket > 0:
            tax += income_in_bracket * rate
            remaining -= income_in_bracket
        last_cap = cap
        if remaining <= 0:
            break

    return taxable_income - tax  # net annual

#####################################################################
# MAIN FUNCTION                                                     #
#####################################################################

def expat_ruling_calc(age: int, gross_salary: float, master_dpl: bool = False,
                      duration: int = 10) -> dict:
    """
    Calculate net income projection under Dutch 30% ruling rules.

    Rules:
      - Start fixed at Jan 1st 2026
      - Projection covers `duration` years (default 10)
      - Ruling duration = 5 years (2026–2030)
        * 2026 → 30% ruling
        * 2027–2030 → 27% ruling
        * 2031+ → no ruling
      - Eligibility:
          * Age >= 30 and gross >= 66,657 → eligible
          * Age < 30 and master_dpl and gross >= 50,668 → eligible
          * Else → not eligible
    Returns:
      {year: net_annual_income}
    """

    # --- Eligibility check ---
    eligible = False
    if age >= 30 and gross_salary >= 66657:
        eligible = True
    elif age < 30 and master_dpl and gross_salary >= 50668:
        eligible = True

    # --- Projection years ---
    start_year = 2026
    years_sequence = list(range(start_year, start_year + duration))
    my_dict = {}

    # --- Apply ruling + taxes ---
    for i, year in enumerate(years_sequence):
        if eligible:
            if i == 0:  # 2026
                taxable = gross_salary * 0.70
            elif 1 <= i <= 4:  # 2027–2030
                taxable = gross_salary * 0.73
            else:  # after 2030
                taxable = gross_salary
        else:
            taxable = gross_salary

        net = apply_nl_taxes_2025(taxable)
        my_dict[year] = net

    return my_dict

#####################################################################
# TESTING                                                           #
#####################################################################

if __name__ == "__main__":
    result = expat_ruling_calc(age=32, gross_salary=70000, master_dpl=False)
    for year, net in result.items():
        print(year, f"€{net:,.0f}")
