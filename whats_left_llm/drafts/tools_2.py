from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

# -------------------- 1. Gross Salary Lookup --------------------
class JobInput(BaseModel):
    job_title: str = Field(description="Job title, e.g. 'Software Engineer'")
    seniority: str = Field(description="Seniority level, e.g. 'Junior', 'Mid-Level', or 'Senior'")

def get_gross_salary(job_title: str, seniority: str) -> float:
    """Look up gross monthly salary for a job+seniority from DB/JSON."""
    data = {
        ("Software Engineer", "Junior"): 4000,
        ("Software Engineer", "Senior"): 8000,
        ("Data Scientist", "Mid-Level"): 5500,
        ("Nurse", "Mid-Level"): 2800,
        ("Police Officer", "Senior"): 3500,
    }
    return data.get((job_title, seniority), 0)

get_gross_salary_tool = StructuredTool.from_function(
    func=get_gross_salary,
    name="get_gross_salary",
    description="Fetch gross salary for a given job and seniority level",
    args_schema=JobInput
)


# -------------------- 2. Income Tax Calculator --------------------
class TaxInput(BaseModel):
    gross_salary: float = Field(description="Gross monthly salary in euros")

def calculate_income_tax(gross_salary: float) -> dict:
    """Calculate net salary after a flat tax rate (currently 37%)."""
    TAX_RATE = 0.37
    net = gross_salary * (1 - TAX_RATE)
    return {"net_after_tax": net, "tax_amount": gross_salary - net}

calculate_income_tax_tool = StructuredTool.from_function(
    func=calculate_income_tax,
    name="calculate_income_tax",
    description="Calculate net salary after flat 37% tax",
    args_schema=TaxInput
)


# -------------------- 3. Expense Deduction --------------------
class ExpenseInput(BaseModel):
    net_salary: float = Field(description="Net monthly salary in euros")
    city: str = Field(description="City where the person lives (Amsterdam, Rotterdam, Utrecht, Eindhoven, Groningen)")

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
    remaining = net_salary - expenses
    return {"remaining": remaining, "expenses": expenses}

deduct_expenses_tool = StructuredTool.from_function(
    func=deduct_expenses,
    name="deduct_expenses",
    description="Deduct essential living costs for a given city",
    args_schema=ExpenseInput
)
