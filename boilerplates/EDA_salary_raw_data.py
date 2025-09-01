import json
import pandas as pd
import os
import re

#############################################################################
# Function to extract numbers from seniority
def extract_numbers(s):
    # Find all numbers in the string
    numbers = re.findall(r'\d+', s)
    # Convert to integers
    return [int(n) for n in numbers]

##############################################################################
# CLEAING EXTRACTING SENIORITY & UPDATING

string = data_dict[1]['seniority']
res = extract_numbers(string)
val1 = int(res[0])
val2 = int(res[1])
val = (val1 + val2) / 2
seniority = []

for i in data_dict.keys():
    string = data_dict[i]['seniority']
    res = extract_numbers(string)
    val1 = int(res[0])
    val2 = int(res[1])
    val = (val1 + val2) / 2

    if val <= 2:
        res = "junior"
    elif val > 2 and val <= 5:
        res = "mid-level"
    else:
        res = "senior"

    data_dict[i]['seniority'] = res


###########################################################################
# FUNCTION TO EXTRACT SALARIES
###########################################################################

def extract_salary(s):
    # Find all numbers in the string (including K)
    matches = re.findall(r'(\d+)[Kk]?', s)
    # Convert to floats and multiply by 1000 if 'K' is present
    numbers = [float(n) * 1000 for n in matches]
    if numbers:
        return {'min_amount': min(numbers), 'max_amount': max(numbers)}
    else:
        return {'min_amount': None, 'max_amount': None}

# Apply extraction to dictionary
for key, value in data_dict.items():
    salary_range = extract_salary(value['salary'])
    value.update(salary_range)

#############################################################################
# EXTRACTING SALARIS IN DICTIONARY - MEDIAN LEVEL
salary = {}

for i in data_dict.keys():
    string = data_dict[i]['salary']
    res = extract_salary(string)
    salary[i] = res

for i in data_dict.keys():
    data_dict[i]['avg_amount'] = (data_dict[i]['min_amount'] + data_dict[i]['max_amount']) / 2

##############################################################################
# NORMALIZE ROLES ############################################################
def normalize_role(role: str) -> str:
    """
    Normalize job titles to match JSON golden standard values.
    If exact match exists, return unchanged.
    If alias exists, map to JSON value.
    If no match, return None.
    """

    # Golden standard roles from JSON
    golden_roles = {
        "Data Scientist": "Data Scientist",
        "Data Analyst": "Data Analyst",
        "Data Engineer": "Data Engineer",
        "Software Engineer": "Software Engineer",
        "DevOps Engineer": "DevOps Engineer",
        "Security Engineer": "Security Engineer",
        "Front End Developer / Engineer": "Front End Developer / Engineer",
        "Back End Developer/ Engineer": "Back End Developer/ Engineer"
    }

    # Alias mapping → maps your input roles to golden JSON values
    alias_map = {
        "Frontend Engineer": "Front End Developer / Engineer",
        "Backend Engineer": "Back End Developer/ Engineer",
        "Devops Engineer": "DevOps Engineer",
        "Ai Engineer": "Ai Engineer",       # not in JSON
        "Cloud Engineer": "Cloud Engineer"   # not in JSON
    }

    # Exact match first
    if role in golden_roles:
        return role

    # Check alias map
    if role in alias_map:
        return alias_map[role]

    # If not found, return or role if you prefer)
    return role
