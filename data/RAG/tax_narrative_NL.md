---

topic: taxation
subcategory: income_tax
country: Netherlands
year: 2025
data_type: tax_brackets
source: Belastingdienst
-----------------------

# Salary Tax Information in the Netherlands (2025)

## General Information

A salary in the Netherlands is subject to **progressive income tax rates**, divided into brackets as of 2025. The system applies to residents' worldwide income and is usually handled through payroll deductions by employers.

### Key Tax Brackets (2025, below state pension age)

* **Up to €38,441**: the tax rate is 35.82% (includes social security contributions)
* **€38,441 – €76,817**: the tax rate is 37.48%
* **Above €76,817** the tax rate is 49.50%

### Calculation Method

* Payroll tax is deducted by employers based on gross salary.
* Tax is applied progressively, depending on income bracket.
* Salary is taxed under **Box 1** (income from work and home ownership).
* Residents: taxed on global income.
  Non-residents: taxed only on Dutch-sourced income.

---

## Special Cases

### Employees at/above state pension age

Tax rates differ once an employee reaches state pension age:

* **Born 1946 or later**:

  * Up to €40,502 → 17.92%
  * €40,502 – €76,817 → 37.48%
  * Above €76,817 → 49.50%

* **Born in or before 1945**:

  * Up to €38,441 → 35.82%
  * €38,441 – €76,817 → 37.48%
  * Above €76,817 → 49.50%

### Composition of Contributions (first bracket, below pension age)

* **Old Age Pensions Act (AOW):** 17.90%
* **Surviving Dependants Act (Anw):** 0.10%
* **Exceptional Medical Expenses Act (Wlz):** 9.65%
* **Wage tax:** 8.17%
* **Total:** 35.82%

For employees above pension age, AOW is not charged, which lowers the first-bracket rate.

---

## Tax Credits (Not Applied in Calculator)

The Dutch system includes tax credits such as:

* **Arbeidskorting (Labour Tax Credit)**
* **Algemene heffingskorting (General Tax Credit)**

These credits reduce the amount of tax owed, especially for lower and middle incomes.

**Important:** The current Salary Calculator implementation does **not** include these credits. As a result, disposable income estimates may appear lower than actual take-home pay in reality.

---

## Calculator Context

* The calculator applies the **2025 progressive tax brackets** only, without tax credits.
* If the **30% ruling** applies, it reduces the **taxable base** before these brackets are applied.
* Results show **disposable income** after payroll tax and common deductions.
* For simplicity, the calculator uses **below pension age brackets** as the default, unless specified otherwise.

---

## Sources

* Belastingdienst (Dutch Tax Authority)

---

### Disclaimer

This document provides **general reference values**. Individual tax outcomes depend on personal circumstances, eligibility for allowances, and employer arrangements. The Salary Calculator currently **does not apply arbeidskorting or algemene heffingskorting**, which means estimates are conservative compared to official net salary outcomes. Always consult the Belastingdienst for official guidance.
