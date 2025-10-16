# 💰 Dutch Salary-to-Reality Calculator

A Streamlit web application that helps professionals in the Netherlands understand their **real disposable income** — from gross salary to what’s actually left in your pocket.
It combines **taxation rules, housing costs, car expenses, and insurance data** with the official **30% ruling for expats**.

---

## 🚀 Features

* **Salary Estimation:** Pulls job- and seniority-specific salary data from a SQLite database.
* **Cost of Living Breakdown:** Includes rent, utilities, car, and health insurance.
* **Tax Calculation:** Implements Dutch 2025 tax brackets, *arbeidskorting*, and *algemene heffingskorting*.
* **Expat 30% Ruling Simulation:** Automatically applies the ruling over multiple years.
* **Interactive Visuals:**
  * Year-by-year disposable income chart
  * Pie chart for essential living costs
* **Chat Assistant (“Ask Harvey”):**
  A built-in RAG-based assistant that explains your results using Google’s Gemini models through LangChain.

---

## 🧱 Tech Stack

| Component         | Technology                        |
| ----------------- | --------------------------------- |
| **Frontend**      | [Streamlit](https://streamlit.io) |
| **Database**      | SQLite                            |
| **Data Handling** | pandas                            |
| **Visualization** | Plotly                            |
| **LLM / RAG**     | LangChain, Google Generative AI   |
| **Environment**   | Python 3.10+                      |

---

## 📁 Project Structure

```
.
├── .streamlit/
│   └── config.toml               # Streamlit theme and layout settings
│
├── core/
│   ├── calculations.py           # Salary & essential costs logic
│   ├── charts.py                 # Plotly visualizations (bar + pie charts)
│   ├── database.py               # SQLite data loading helpers
│   ├── styling.py                # Global Streamlit and chat styling
│   └── tax.py                    # Dutch tax rules + expat 30% ruling logic
│
├── data/
│   ├── RAG/                      # Knowledge base (.md files) for Ask Harvey
│   └── app.db                    # Public demo SQLite database (safe to share)
│
├── pages/
│   └── ask_harvey.py             # Gemini-powered RAG chatbot page
│
├── .env                          # Local API keys
├── .gitignore                    # Ignore caches, envs, secrets, etc.
├── calculator.py                 # Main Streamlit entry point
├── README.md
└── requirements.txt              # Dependencies list

```

---

## 🧠 Ask Harvey — The Chat Assistant

“Ask Harvey” uses **LangChain + Google Generative AI** to provide clear, factual explanations of your results.
It retrieves contextual info (tax, rent, etc.) from Markdown documents and summarizes them before answering.

> Harvey never recalculates numbers — he *explains* them.

---

## 🧩 Environment Variables

| Variable         | Description                                    |
| ---------------- | ---------------------------------------------- |
| `GOOGLE_API_KEY` | Required for the Gemini-powered chat assistant |
