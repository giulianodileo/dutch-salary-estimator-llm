from langchain_core.tools import tool

# -------------------- Gross Salary Lookup --------------------
@tool
def get_gross_salary(job_title: str, seniority: str) -> float:
    """Look up gross monthly salary for a job+seniority from DB/JSON."""
    # TODO: replace this with real JSON/DB lookup
    data = {
        ("Backend Engineer", "Junior"): 3420,
        ("Backend Engineer", "Mid-level"): 5420,
        ("Backend Engineer", "Senior"): 6330,
        ("Data Analyst", "Junior"): 3830,
        ("Data Analyst", "Mid-level"): 4830,
        ("Data Analyst", "Senior"): 5170,
        ("Data Scientist", "Junior"): 4000,
        ("Data Scientist", "Mid-level"): 5080,
        ("Data Scientist", "Senior"): 6920,
        ("Data Engineer", "Junior"): 4080,
        ("Data Engineer", "Mid-level"): 5080,
        ("Data Engineer", "Senior"): 5500,
        ("DevOps Engineer", "Junior"): 4250,
        ("DevOps Engineer", "Mid-level"): 5330,
        ("DevOps Engineer", "Senior"): 5920,
        ("Frontend Engineer", "Junior"): 3500,
        ("Frontend Engineer", "Mid-level"): 5000,
        ("Frontend Engineer", "Senior"): 4830,
        ("Security Engineer", "Junior"): 4830,
        ("Security Engineer", "Mid-level"): 5080,
        ("Security Engineer", "Senior"): 6670,
        ("Software Engineer", "Junior"): 4000,
        ("Software Engineer", "Mid-level"): 5080,
        ("Software Engineer", "Senior"): 5580,
    }

    return data.get((job_title, seniority), 0)

# -------------------- Income Tax Calculator --------------------
@tool
def calculate_income_tax(gross_salary: float) -> dict:
    """Calculate net salary after flat 37% tax."""
    TAX_RATE = 0.37
    net = gross_salary * (1 - TAX_RATE)
    return {"net_after_tax": net, "tax_amount": gross_salary - net}

# -------------------- Expense Deduction --------------------
@tool
def deduct_expenses(net_salary: float, city: str) -> dict:
    """Deduct essential living costs for a given city."""
    ESSENTIALS = {
        "Amsterdam": 1800,
        "Rotterdam": 1500,
        "Utrecht": 1600,
        "Eindhoven": 1400,
        "Groningen": 1200,
    }
    expenses = ESSENTIALS.get(city, 1400)
    return {"remaining": net_salary - expenses, "expenses": expenses}
