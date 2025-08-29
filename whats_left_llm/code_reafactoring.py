import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import datetime as dt
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, TypedDict # Import TypedDict here

# LangChain and RAG related imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langgraph.graph import START, StateGraph
from dotenv import load_dotenv
import os
import asyncio # For asyncio.get_running_loop() fix

# Local imports
from calculator_core import get_estimates, DB_URI
from calculate_30_rule import expat_ruling_calc
# The original `chart.py` and `return_net_income` are not provided.
# Assuming its logic was simple arithmetic, it has been integrated directly
# into `calculate_and_display_results` for self-containment.
# If `chart.py` has more complex logic for chart generation, it should be re-imported.


# --- Constants ---
# Colorblind-friendly palette
COLOR_PALETTE = ["#2E91E5", "#E15F99", "#1CA71C", "#FB0D0D"]
RAG_DATA_DIR = Path.cwd() / "data" / "RAG"
FEEDBACK_FILE = "feedback.jsonl"
DEFAULT_DURATION_YEARS = 10
DEFAULT_EXPERTISE = True

# --- LLM SETUP ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    st.sidebar.error("⚠️ GOOGLE_API_KEY not found. Please add it to your .env file.")

HAS_LLM = False
try:
    # Using init_chat_model for flexibility as in original code.
    # Alternatively, `from langchain_google_genai import ChatGoogleGenerativeAI`
    # and `ChatGoogleGenerativeAI(model="gemini-2.5-flash")` could be used directly.
    from langchain.chat_models import init_chat_model
    HAS_LLM = True
except ImportError:
    st.sidebar.error(
        ":warning: Could not import LangChain's chat_models. Install LangChain + Google GenAI."
    )

@st.cache_resource(show_spinner=True)
def load_llm():
    if not HAS_LLM:
        return None
    try:
        if not GOOGLE_API_KEY:
            st.sidebar.error("⚠️ Cannot load LLM: GOOGLE_API_KEY is missing.")
            return None
        return init_chat_model("gemini-2.5-flash", model_provider="google_genai")
    except Exception as e:
        st.sidebar.error(f":warning: Could not load LLM: {e}")
        return None

llm = load_llm()

# --- Database Helpers ---
def _sqlite_path(db_uri: str) -> str:
    assert db_uri.startswith("sqlite:///")
    return db_uri.replace("sqlite:///", "", 1)

def _open(db_uri: str) -> sqlite3.Connection:
    path = _sqlite_path(db_uri)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

@st.cache_data(show_spinner="Loading database options...")
def load_options(db_uri: str = DB_URI) -> Dict[str, List[str]]:
    opts = {"jobs": [], "seniorities": [], "cities": [], "accommodations": [], "cars": []}
    path = _sqlite_path(db_uri)
    if not Path(path).exists():
        st.error(f"Database file not found at: {path}. Please ensure it exists and has data.")
        return opts

    try:
        with _open(db_uri) as con:
            opts["jobs"] = [r[0] for r in con.execute("SELECT DISTINCT position_name FROM job_positions_seniorities ORDER BY position_name;").fetchall()]
            opts["seniorities"] = [r[0] for r in con.execute("SELECT DISTINCT seniority FROM job_positions_seniorities ORDER BY seniority;").fetchall()]
            opts["cities"] = [r[0] for r in con.execute("SELECT DISTINCT city FROM rental_prices ORDER BY city;").fetchall()]
            opts["accommodations"] = [r[0] for r in con.execute("SELECT DISTINCT accommodation_type FROM rental_prices WHERE accommodation_type IS NOT NULL ORDER BY accommodation_type;").fetchall()]
            opts["cars"] = [r[0] for r in con.execute("SELECT DISTINCT type FROM transportation_car_costs ORDER BY type;").fetchall()]
    except sqlite3.Error as e:
        st.error(f"Error loading options from database: {e}")
        return opts
    return opts

opts = load_options(DB_URI)
if not any(opts.values()):
    st.error("No database found or tables are empty. Please ensure the database is created and JSONs are loaded.")
    st.stop() # Stop the app if essential data is missing

# --- RAG SETUP ---
@st.cache_resource(show_spinner="Initializing RAG knowledge base...")
def load_vector_store():
    try:
        # Fix for "RuntimeError: Event loop is already running" in some Streamlit environments
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        docs = []
        if not RAG_DATA_DIR.exists():
            st.sidebar.warning(f"⚠️ RAG data directory not found: {RAG_DATA_DIR}. RAG will be limited.")
            return None

        for md_file in RAG_DATA_DIR.glob("*.md"):
            loader = TextLoader(str(md_file), encoding="utf-8")
            docs.extend(loader.load())

        if not docs:
            st.sidebar.warning(f"⚠️ No .md documents found in {RAG_DATA_DIR}. RAG will be limited.")
            return None # Return None if no documents are found to indicate RAG is not fully functional

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        all_splits = text_splitter.split_documents(docs)

        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        vector_store = InMemoryVectorStore(embeddings)
        vector_store.add_documents(all_splits)

        st.sidebar.info(f"✅ RAG initialized with {len(docs)} docs → {len(all_splits)} chunks")
        return vector_store

    except Exception as e:
        st.sidebar.error(f"⚠️ Could not initialize RAG: {e}")
        return None

vector_store = load_vector_store()

# Source labels for RAG
SOURCE_LABELS = {
    "health_insurance.md": "Rijksoverheid (Government of the Netherlands)",
    "rental_prices.md": "HousingAnywhere, RentHunter",
    "ruling_30_narrative.md": "Belastingdienst (Tax and Customs Administration)",
    "seniority_levels.md": "Google", # Consider a more specific source if available
    "tax_narrative_NL.md": "Belastingdienst (Tax and Customs Administration)",
    "transportation.md": "Nibud (National Institute for Family Finance Information)",
    "utilities.md": "Nibud (National Institute for Family Finance Information)"
}

# Define the State for the LangGraph
class State(TypedDict):
    question: str
    context: List[Document]
    answer: str
    sources: List[str]

# Retrieval step for RAG
def retrieve(state: State) -> Dict[str, Any]:
    if not vector_store:
        return {"context": [], "sources": []}
    retrieved_docs = vector_store.similarity_search(state["question"])
    return {"context": retrieved_docs}

# Generation step for RAG
def generate(state: State) -> Dict[str, Any]:
    if not llm:
        return {"answer": "LLM not available for generation.", "sources": []}

    sources_used = []
    docs_content = []

    for doc in state["context"]:
        filename = Path(doc.metadata.get("source", "unknown")).name
        label = SOURCE_LABELS.get(filename, filename)
        sources_used.append(label)
        docs_content.append(doc.page_content)

    docs_text = "\n\n".join(docs_content)

    user_info_payload = st.session_state.get("last_payload")
    user_context = ""
    if user_info_payload:
        inputs = user_info_payload.get('inputs', {})
        extra = user_info_payload.get('extra', {})
        outputs = user_info_payload.get('outputs', {})

        user_context = (
            f"User Profile:\n"
            f"- Job: {inputs.get('job', 'N/A')}\n"
            f"- Seniority: {inputs.get('seniority', 'N/A')}\n"
            f"- City: {inputs.get('city', 'N/A')}\n"
            f"- Accommodation: {inputs.get('accommodation_type', 'N/A')}\n"
            f"- Age: {extra.get('age', 'N/A')}\n"
            f"- Net Salary (after tax, monthly): €{user_info_payload.get('net_salary_monthly_after_tax', 0):,.0f}\n"
            f"- Essential Costs (monthly): €{outputs.get('essential_costs', 0):,.0f}\n"
            f"- Disposable Income (monthly): €{user_info_payload.get('disposable_income_monthly', 0):,.0f}\n"
        )
    else:
        user_context = "User profile not available. Please run the calculator first to get personalized answers."

    rag_prompt = ChatPromptTemplate.from_messages([
        ("system",
        "You are a financial assistant helping professionals in the Netherlands "
        "understand salaries, taxes, housing, transportation, and related costs. "
        "Your answers must combine two sources:\n"
        "1. User profile data (salary, disposable income, age, city, etc.)\n"
        "2. Retrieved documents from the knowledge base.\n\n"
        "Guidelines:\n"
        "- Always take the user’s profile into account when answering.\n"
        "- Use retrieved documents for factual references (tax rules, averages).\n"
        "- If profile info is missing, state that you don't have it and provide general info from context.\n"
        "- Keep answers concise (max 3 sentences).\n"
        "- Mention the source labels when using document info.\n"
        "- If neither profile nor docs answer the question, explicitly say so."),
        ("human",
        "User info (if available):\n{user_info}\n\n"
        "Question: {question}\n\n"
        "Context from knowledge base:\n{context}\n\n"
        "Answer:")
    ])

    messages = rag_prompt.invoke({
        "question": state["question"],
        "context": docs_text,
        "user_info": user_context
    })
    response = llm.invoke(messages)

    return {
        "answer": response.content.strip(),
        "sources": sorted(list(set(sources_used))) # Ensure unique sources
    }

# Build and compile the RAG graph
if HAS_LLM and llm and vector_store:
    graph_builder = StateGraph(State)
    graph_builder.add_node("retrieve", retrieve)
    graph_builder.add_node("generate", generate)
    graph_builder.add_edge(START, "retrieve")
    graph_builder.add_edge("retrieve", "generate")
    rag_chain = graph_builder.compile()
else:
    rag_chain = None # Set to None if LLM or vector_store is not loaded

def rag_answer(question: str) -> Dict[str, Any]:
    if not rag_chain:
        return {"answer": "⚠️ RAG not available. Please check LLM/Vector Store setup.", "sources": []}

    try:
        # LangGraph invoke expects a dictionary with keys matching the State TypedDict
        result = rag_chain.invoke({"question": question, "context": [], "answer": "", "sources": []})
        return {
            "answer": result.get("answer", "No answer could be generated."),
            "sources": result.get("sources", []),
        }
    except Exception as e:
        st.error(f"⚠️ RAG chain error: {e}")
        return {"answer": f"⚠️ An error occurred while processing your request: {e}", "sources": []}

# --- Helper Functions for UI and Calculations ---

def render_salary_charts(expenses: float, leftover: float):
    """Accessible Pie Chart: Expenses vs Disposable Income"""
    df = pd.DataFrame({
        "Category": ["Essential + Housing Costs", "Disposable Income"],
        "Amount": [expenses, leftover]
    })
    fig = px.pie(
        df,
        values="Amount",
        names="Category",
        title=":moneybag: Expenses vs Disposable Income",
        hole=0.4,
        color="Category",
        color_discrete_map={
            "Essential + Housing Costs": COLOR_PALETTE[0],
            "Disposable Income": COLOR_PALETTE[2]
        })
    fig.update_traces(textinfo="label+percent+value",
                     textfont_color=["black", "white"])
    st.plotly_chart(fig)

def render_disposable_income_gauge(disposable_income_monthly: float, total_net_income_monthly: float):
    """Displays a gauge chart for disposable income percentage."""
    if total_net_income_monthly <= 0:
        disposable_pct = 0
    else:
        disposable_pct = max(0, min(100, (disposable_income_monthly / total_net_income_monthly) * 100))

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=disposable_pct,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Disposable Income %"},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "green"},
            'steps': [
                    {'range': [0, 20], 'color': 'red'},
                    {'range': [20, 50], 'color': 'orange'},
                    {'range': [50, 100], 'color': 'lightgreen'}
            ],
            'threshold': {
                'line': {'color': "blue", 'width': 4},
                'thickness': 0.75,
                'value': disposable_pct
                }
            }
        ))
    st.plotly_chart(fig, use_container_width=True)

def save_feedback(feedback_text: str):
    """Save feedback locally to a JSONL file."""
    try:
        with open(FEEDBACK_FILE, "a") as f:
            json.dump({"timestamp": str(dt.datetime.now()), "feedback": feedback_text}, f)
            f.write("\n")
        st.success("Thank you for your feedback!")
    except Exception as e:
        st.error(f"Could not save feedback: {e}")

def get_user_calculator_inputs(options: Dict[str, List[str]]) -> Optional[Dict[str, Any]]:
    """Collects all user inputs for the salary calculator from the sidebar."""
    st.sidebar.title("Your Profile")
    user_name = st.sidebar.text_input("What's your name?", "", key="user_name_input")
    if user_name:
        st.sidebar.success(f"Welcome, {user_name}! :sunglasses:")

    age = st.sidebar.number_input("What is your age?", min_value=18, max_value=70, step=1, key="age_input")

    has_masters_nl_choice = "No"
    if age < 30:
        has_masters_nl_choice = st.sidebar.radio(
            "Do you have a Master’s Degree (or higher) obtained in the Netherlands?",
            ["Yes", "No"], key="master_degree_input"
        )
    has_masters_nl = (has_masters_nl_choice == "Yes")

    job = st.sidebar.selectbox("Job Role", options["jobs"], key="job_input")
    seniority = st.sidebar.selectbox("Seniority", options["seniorities"], key="seniority_input")
    city = st.sidebar.selectbox("City", options["cities"], key="city_input")
    accommodation_type = st.sidebar.selectbox("Accommodation Type", options["accommodations"], key="accommodation_input")
    start_date = st.sidebar.date_input("Start date (MM/DD/YYYY)", value=dt.date.today(), key="start_date_input")

    has_car_choice = st.sidebar.radio("Do you have a car?", ["No", "Yes"], key="has_car_input")
    car_type = 0
    if has_car_choice == "Yes":
        car_type = st.sidebar.selectbox("Select your car type:", options["cars"], key="car_type_input")

    submitted = st.sidebar.button("Calculate", key="calculate_button")

    if submitted:
        return {
            "user_name": user_name,
            "age": age,
            "has_masters_nl": has_masters_nl,
            "job": job,
            "seniority": seniority,
            "city": city,
            "accommodation_type": accommodation_type,
            "start_date": start_date,
            "duration_years": DEFAULT_DURATION_YEARS, # Use constant
            "expertise": DEFAULT_EXPERTISE,           # Use constant
            "car_type": car_type,
            "has_car": has_car_choice == "Yes",
        }
    return None

def calculate_and_display_results(user_inputs: Dict[str, Any]):
    """
    Performs calculations and displays results for the salary calculator.
    Stores the full payload in st.session_state["last_payload"].
    """
    try:
        # Step 1: Get base estimates (salary, rent, car costs)
        estimates_outputs: Dict[str, Any] = get_estimates(
            job=user_inputs["job"],
            seniority=user_inputs["seniority"],
            city=user_inputs["city"],
            accommodation_type=user_inputs["accommodation_type"],
            car_type=user_inputs["car_type"],
            db_uri=DB_URI,
        )

        # Step 2: Calculate tax ruling (e.g., 30% rule)
        annual_gross_salary = estimates_outputs['salary']['avg'] * 12
        tax_calculation_results: Dict[int, float] = expat_ruling_calc( # Assuming it returns year -> net income dict
            age=user_inputs["age"],
            salary=annual_gross_salary,
            date_string=user_inputs["start_date"].isoformat(),
            duration=user_inputs["duration_years"],
            expertise=user_inputs["expertise"],
            master_dpl=user_inputs["has_masters_nl"]
        )

        # Determine net income for the relevant year (e.g., start year or current year)
        relevant_year = user_inputs["start_date"].year
        # Fallback if the exact year isn't in results, pick the first available or default to 0
        net_income_yearly_after_tax = tax_calculation_results.get(relevant_year, 0.0)
        if not net_income_yearly_after_tax and tax_calculation_results:
             net_income_yearly_after_tax = next(iter(tax_calculation_results.values())) # Take the first available year's data

        net_salary_monthly_after_tax = net_income_yearly_after_tax / 12 if net_income_yearly_after_tax else 0.0

        # Step 3: Calculate essential costs and disposable income
        essential_costs_monthly = estimates_outputs['essential_costs']
        disposable_income_monthly = net_salary_monthly_after_tax - essential_costs_monthly

        # Prepare payload for session state
        payload = {
            "inputs": {
                "job": user_inputs["job"],
                "seniority": user_inputs["seniority"],
                "city": user_inputs["city"],
                "accommodation_type": user_inputs["accommodation_type"],
                "car_type": user_inputs["car_type"],
            },
            "extra": {
                "age": user_inputs["age"],
                "start_date_iso": user_inputs["start_date"].isoformat(),
                "duration_years": user_inputs["duration_years"],
                "expertise": user_inputs["expertise"],
                "master_diploma": user_inputs["has_masters_nl"],
            },
            "outputs": {
                "salary_gross_monthly": estimates_outputs['salary']['avg'],
                "rent_monthly": estimates_outputs['rent'],
                "car_total_per_month": estimates_outputs.get('car_total_per_month', 0),
                "essential_costs": essential_costs_monthly,
            },
            "tax_details": tax_calculation_results,
            "net_salary_monthly_after_tax": net_salary_monthly_after_tax,
            "disposable_income_monthly": disposable_income_monthly,
        }
        st.session_state["last_payload"] = payload

        # --- Display Metrics ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Gross Salary (Monthly)", f"€{estimates_outputs['salary']['avg']:,.0f}")
        col2.metric("Net Salary (Monthly, after tax)", f"€{net_salary_monthly_after_tax:,.0f}")
        col3.metric("Essential Living Costs (Monthly)", f"€{essential_costs_monthly:,.0f}")
        col4.metric("Disposable Income (Monthly)", f"€{disposable_income_monthly:,.0f}")

        # --- Charts ---
        # Ensure the leftover for the pie chart is non-negative for visualization purposes
        pie_chart_disposable_income = max(0, disposable_income_monthly)
        render_salary_charts(essential_costs_monthly, pie_chart_disposable_income)
        render_disposable_income_gauge(disposable_income_monthly, net_salary_monthly_after_tax)

        # --- Savings Recommendation ---
        st.markdown("### :moneybag: Suggested Savings")
        if net_salary_monthly_after_tax > 0:
            disposable_income_ratio = disposable_income_monthly / net_salary_monthly_after_tax
            if disposable_income_monthly <= 0:
                st.warning("You are spending all of your net income or more. Consider reviewing your budget, especially housing or other essential costs.")
            elif disposable_income_ratio < 0.2:
                st.info("Your disposable income is relatively low. Aim to save at least 5-10% of your net salary. Every little bit helps!")
            elif disposable_income_ratio < 0.4:
                st.success("Good! You have a decent disposable income. Consider saving 15-25% of your net salary each month to build your financial future.")
            else:
                st.success("Excellent! You have a high disposable income. This is a great opportunity to save 25-40% or more, or explore investment options.")
        else:
            st.info("No net income data available to provide savings recommendations.")

        st.info(f":bulb: Tip: Track your spending monthly. In {user_inputs['city']}, typical accommodation costs for a {user_inputs['accommodation_type']} are estimated at €{estimates_outputs['rent']:,.0f}.")

        # --- Details Section ---
        st.markdown("### Details")
        with st.expander("Raw calculation data (JSON)"):
            st.code(json.dumps(payload, indent=2), language="json")

    except ValueError as ve:
        st.warning(str(ve))
    except Exception as e:
        st.error(f"An unexpected error occurred during calculation: {e}")

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    page_icon=":euro:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Navigation ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", [":euro: Salary Calculator", ":robot_face: Salary & Budget Chat", ":question: Help"])

# --- Page Content Logic ---

if page == ":euro: Salary Calculator":
    st.title(":euro: Dutch Salary-to-Reality Calculator")
    user_calculator_inputs = get_user_calculator_inputs(opts)

    if user_calculator_inputs:
        calculate_and_display_results(user_calculator_inputs)
    else:
        st.info("Complete the fields in the sidebar and press **Calculate**.")

elif page == ":robot_face: Salary & Budget Chat":
    st.title(":robot_face: Ask about Your Salary & Budget")

    if not HAS_LLM or not llm or not vector_store:
        st.warning("⚠️ The chat feature is not available. Please ensure the LLM and RAG knowledge base are configured correctly.")
    else:
        if "last_payload" not in st.session_state or not st.session_state["last_payload"]:
            st.info("💡 Run the **Salary Calculator** first to get personalized answers based on your profile!")
        else:
            st.success("Your profile is loaded from the calculator for personalized answers. Ask away!")

        st.markdown("---")
        st.write("### Suggested questions:")
        suggested_questions = [
            "What is the average salary for a Data Scientist in Amsterdam?",
            "How much should I budget for rent in Utrecht for my accommodation type?",
            "Considering my profile, how much disposable income do I have?",
            "Tell me about the 30% ruling and if it applies to me."
        ]
        for q in suggested_questions:
            if st.button(q, key=f"suggested_q_{q[:20]}"): # Use a slice for key to avoid long keys
                user_input = q
                with st.spinner("Thinking..."):
                    result = rag_answer(user_input)
                st.write(f"**You asked:** {user_input}")
                st.success(result["answer"])
                if result.get("sources"):
                    st.caption("📌 Source(s): " + ", ".join(result["sources"]))

        st.markdown("---")
        user_input = st.text_area("### Or type your own question:", "", key="chat_input")
        if st.button("Ask", key="ask_button") and user_input:
            with st.spinner("Thinking..."):
                result = rag_answer(user_input)
            st.write(f"**You asked:** {user_input}")
            st.success(result["answer"])
            if result.get("sources"):
                st.caption("📌 Source(s): " + ", ".join(result["sources"]))

elif page == ":question: Help":
    st.title("Help & FAQ")
    st.markdown("""
    This application helps you understand your potential salary and living costs in the Netherlands.

    ### Frequently Asked Questions:
    - **How do I use the Salary Calculator?**
      Select your job role, seniority level, preferred city, age, and accommodation type in the sidebar. Then click "Calculate" to see an estimate of your gross salary, net salary, essential costs, and disposable income.

    - **Why do you ask for age and degree?**
      For individuals under 30, having a Master's Degree (or higher) obtained in the Netherlands can influence eligibility and benefits for certain expat rulings or tax advantages, like the 30% ruling. This helps in providing a more accurate net salary calculation.

    - **What is the Salary & Budget Chat?**
      This is an AI assistant that can answer questions about salaries, taxes, housing, transportation, and other related costs in the Netherlands. It uses a knowledge base and, if you've run the calculator, your personal profile to give personalized and factual answers.

    - **Is the data real-time?**
      The data used for estimates (salaries, rents, costs) is based on a pre-loaded database. While efforts are made to keep it current, it may not reflect the absolute latest market fluctuations. The RAG system uses markdown documents as its knowledge base.

    ### Provide Feedback:
    We'd love to hear your thoughts or if you encounter any issues!
    """)
    feedback = st.text_area("Your Feedback:", "", key="feedback_input")
    if st.button("Submit Feedback", key="submit_feedback_button") and feedback:
        save_feedback(feedback)