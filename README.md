# GitHub README

## Document Structure & Sections

## ⭐Project "What is left: Dutch salary to realiy"

![Project Logo]

*Our project is about leveraging LLM capabilities together with data retrieval and augumentation, which includes tax calculations to allow expats make better descsisions regarding thier job search & relocation strategies*

[🚀 Live Demo](https://your-demo-link.com)


**Challenge**: As an expat applying for a job in the Netherlands one may need to be familiar with certain tax rules, costs of living and other important questions to make the right descision

- Job offer is about gross salary, but what about net disposable income?
- What is 30% ruling and it's impact on my income long-term?
- What are my expenses to consdier?


Our tool will help to address these challenges and to make better descisions for anyone looking for a job in the Netherlands.


## 1. About The Project

![Product Screenshot](images/screenshot.png)

We used different tools to address the challenge and present the solutuon to user in an easy to use UI with interactive elements and LLM interface for humanl like queries. We took following steps:

Obtained data on salaries ranges for specific roles using scraping on two data sources
Normalzied data and transformed it into JSON objects which can be used later
Implemented logic for tax & 30% ruling calculation considering various inputs
Implemented RAG (retrieval augumented generation) by leveraging Google Gemeni Flash 2.5 model with
augumentation on specific tax caluclation so the model has a good understanding of the context
Built front-end interface using Streamlit with interactive controls, charts and LLM window

### User Benefits:


✅ Full insights in salary ranges, costs and tax impact
✅ Making better descisions
✅ Negotiating a better deal



## 2. Built With

Python
PY/Beautiful soup
PY/Langchain
PY/Streamlit
SQL Lite database

## 3. Getting Started
This is the make-or-break section. Developers will abandon your project if setup is painful.

## 4. Usage Examples
Show, don't just tell. Provide concrete, copy-paste examples:

## 5. Calculation methodologies

### Salary brackets
From 2024: For newcomers who became eligible from 1 January 2024 onward, the tax-exempt benefit now follows a laddered structure over the five-year period:

**30% tax-free for the first 20 months**
**20% tax-free for the next 20 months**
**10% tax-free for the final 20 months**

Applicants with a ruling in place before 2024 are grandfathered, meaning they continue to enjoy the full 30% tax-free allowance for up to five years under the old rules.But a reversal is already underway. Following widespread criticism, the government decided to reverse the 30-20-10 structure:

From 1 January 2025 through 31 December 2026, all eligible expats (including new ones) will receive a **flat 30% tax-free allowance**, without scaling. Then, starting 1 January 2027, the allowance will be permanently **adjusted to a flat 27%**, with updated salary thresholds.

The 2025 Tax Plan, including the amendments, still requires approval from the Dutch Parliament. Should the proposals be adopted, these changes may have implications for certain employees.

### Maximum allowable salary for 30% ruling

30% facility applies to amounts up to €233,000
The tax-free allowance applies to salary amounts of up to €233,000 a year (amount for 2024).

https://www.belastingdienst.nl/wps/wcm/connect/en/individuals/content/coming-to-work-in-the-netherlands-30-percent-facility

### Expertise Requirements

To qualify for the 30%-ruling, an incoming employee must possess specific expertise that is either not available or scarcely available in the Dutch labor market. This expertise requirement is primarily determined based on a salary norm.

Your specific expertise is hardly found on the labour market in the Netherlands. You have a specific expertise if your annual salary, not including the tax-free allowance in the Netherlands, is more than the annual salary in the table.

Table: specific expertise
Year	Your annual salary is more than
**2025	€46,660**
2024	€46,107
2023	€41,954

You are younger than 30, and you have a Dutch academic master's degree
Or you have obtained an equivalent title in another country. You have a specific expertise if your annual salary, not including the tax-free allowance in the Netherlands, is more than the annual salary in the table.
Table: specific expertise for people younger than 30
Year	Your annual salary is more than
**2025	€35,468**
2024	€35,048
2023	€31,891

https://www.belastingdienst.nl/wps/wcm/connect/en/individuals/content/coming-to-work-in-the-netherlands-30-percent-facility

## Acknowledgments

Special thanks to: Juan, Jen and other teaches from Le Wagon who helped us during the bootcamp
