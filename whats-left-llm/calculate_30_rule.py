import pandas as pd
import datetime

from datetime import datetime, date, time, timedelta
import matplotlib.pyplot as plt

def apply_ruling(base_salary: float, months_dur: int, year: int, year_seq: int):
  # base_salary -> annual
  # function derives gross salary net of 30% taxes
  # months_dur -> months when 30% ruling will be applied
  # year_seq: which year we deal with: 0 -> first, 1 -> intermeidate year, 2-> last, 3-> no 30% ruling

    if year in (2025, 2026) and year_seq == 0 and months_dur != 12:
      # 30% ruling on months applied
      gross_taxable = (base_salary - (base_salary * 0.3)) / 12 * months_dur
    elif year in (2025, 2026) and year_seq == 1:
      # in case 2025, 2025 not first year -> full year 30% ruling
      gross_taxable = base_salary - (base_salary * 0.3)
    elif year not in (2025, 2026) and year_seq == 1:
      # in case 2026 or later and 27% ruling whole year
      gross_taxable = base_salary - (base_salary * 0.27)
    elif year not in (2025, 2026) and year_seq == 2:
      # in case 2026 or later and 30% ruling part of the year
      gross_taxable = ((base_salary - (base_salary * 0.3)) / 12 * months_dur) + (base_salary / 12 * (12 - months_dur))
    else:
      # no 30% ruling and year later than 2026
      gross_taxable = base_salary

    return gross_taxable

def expat_ruling_calc(age: int, base_salary: float, date_string: str, duration: int = 10,
                      expertise: bool = False, master_dpl: bool = False):

  # INITIATE KEY PARAMETERS
  salary_cap = 233000
  salary_req_young = 35468
  salary_expert = 46660

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

  if age < 30 and expertise == True and master_dpl == True and base_salary >= salary_req_young:
        Ruling_test = True
  elif age >= 30 and expertise == True and base_salary >= salary_expert:
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
    other_years_sequence = list(keys_list[1:4])

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
