# Dutch Salary-to-Reality Calculator (Enhanced & Accessible)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import datetime as dt
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
import asyncio
import os

from calculator_core import get_estimates, DB_URI
from calculate_30_rule import expat_ruling_calc

# -------------------- LLM + RAG --------------------
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from typing_extensions import List, TypedDict
from langgraph.graph import START, StateGraph

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.sidebar.error("⚠️ GOOGLE_API_KEY not found. Please add it to your .env file.")

try:
    from langchain.chat_models import init_chat_model
    HAS_LLM = True
except ImportError:
    st.sidebar.error(":warning: Could not import init_chat_model. Install LangChain + Google GenAI.")
    HAS_LLM = False

COLOR_PALETTE = ["#2E91E5", "#E15F99", "#1CA71C", "#FB0D0D"]

# -------------------- DB HELPERS --------------------
def _sqlite_path(db_uri: str) -> str:
    assert db_uri.startswith("sqlite:///")
    return db_uri.replace("sqlite:///", "", 1)

def _open(db_uri: str) -> sqlite3.Connection:
    path = _sqlite_path(db_uri)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def load_options(db_uri: str = DB_URI) -> Dict[str, List[str]]:
    opts = {"jobs": [], "seniorities": [], "cities": [], "accommodations": [], "cars": []}
    path = _sqlite_path(db_uri)
    if not Path(path).exists():
        return opts

    with _open(db_uri) as con:
        rows = con.execute("SELECT DISTINCT position_name FROM job_positions_seniorities ORDER BY position_name;").fetchall()
        opts["jobs"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT seniority FROM job_positions_seniorities ORDER BY seniority;").fetchall()
        opts["seniorities"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT city FROM rental_prices ORDER BY city;").fetchall()
        opts["cities"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT accommodation_type FROM rental_prices WHERE accommodation_type IS NOT NULL ORDER BY accommodation_type;").fetchall()
        opts["accommodations"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT type FROM transportation_car_costs ORDER BY type;").fetchall()
        opts["cars"] = [r[0] for r in rows]

    return opts

opts = load_options(DB_URI)
if not any(opts.values()):
    st.error("Database not found or empty. Load it before using the app.")
    st.stop()

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    page_icon=":euro:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- LLM LOADER --------------------
@st.cache_resource(show_spinner=True)
def load_llm():
    if not HAS_LLM:
        return None
    try:
        return init_chat_model("gemini-2.5-flash", model_provider="google_genai")
    except Exception as e:
        st.sidebar.error(f":warning: Could not load LLM: {e}")
        return None
llm = load_llm()

@st.cache_resource(show_spinner=True)
def load_vector_store():
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        DATA_DIR = Path.cwd() / "data" / "RAG"
        docs = []
        for md_file in DATA_DIR.glob("*.md"):
            loader = TextLoader(str(md_file), encoding="utf-8")
            docs.extend(loader.load())

        if not docs:
            st.sidebar.warning("⚠️ No .md documents found in data/RAG.")

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

# -------------------- RAG CHAIN --------------------
if HAS_LLM and llm and vector_store:
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
        "- If profile info is missing, state that.\n"
        "- Keep answers concise (max 3 sentences).\n"
        "- Mention the source labels when using document info.\n"
        "- If neither profile nor docs answer the question, explicitly say so."),
        ("human",
        "User info (if available):\n{user_info}\n\n"
        "Question: {question}\n\n"
        "Context from knowledge base:\n{context}\n\n"
        "Answer:")
    ])

    class State(TypedDict):
        question: str
        context: List[Document]
        answer: str

    def retrieve(state: State):
        retrieved_docs = vector_store.similarity_search(state["question"])
        return {"context": retrieved_docs}

    SOURCE_LABELS = {
        "health_insurance.md": "Rijksoverheid",
        "rental_prices.md": "HousingAnywhere, RentHunter",
        "ruling_30_narrative.md": "Belastingdienst",
        "seniority_levels.md": "Google",
        "tax_narrative_NL.md": "Belastingdienst",
        "transportation.md": "Nibud",
        "utilities.md": "Nibud"
    }

    def generate(state: State):
        sources_used = []
        docs_content = []
        for doc in state["context"]:
            filename = Path(doc.metadata.get("source", "unknown")).name
            label = SOURCE_LABELS.get(filename, filename)
            sources_used.append(label)
            docs_content.append(doc.page_content)

        docs_text = "\n\n".join(docs_content)
        user_info = st.session_state.get("last_payload")
        user_context = ""
        if user_info:
            user_context = (
                f"User Profile:\n"
                f"- Job: {user_info['inputs']['job']}\n"
                f"- Seniority: {user_info['inputs']['seniority']}\n"
                f"- City: {user_info['inputs']['city']}\n"
                f"- Accommodation: {user_info['inputs']['accommodation_type']}\n"
                f"- Age: {user_info['extra']['age']}\n"
                f"- Net Salary (2026): €{user_info['net tax']:,.0f}\n"
                f"- Essential Costs: €{user_info['outputs']['essential_costs']:,.0f}\n"
                f"- Disposable Income (2026): €{user_info['net tax'] - user_info['outputs']['essential_costs']:,.0f}\n"
            )

        messages = rag_prompt.invoke({
            "question": state["question"],
            "context": docs_text,
            "user_info": user_context
        })
        response = llm.invoke(messages)

        return {"answer": response.content.strip(), "sources": sorted(set(sources_used))}

    graph_builder = StateGraph(State).add_sequence([retrieve, generate])
    graph_builder.add_edge(START, "retrieve")
    rag_chain = graph_builder.compile()

    def rag_answer(question: str):
        if not rag_chain:
            return {"answer": "⚠️ RAG not available.", "sources": []}
        try:
            result = rag_chain.invoke({"question": question})
            return {"answer": result.get("answer", ""), "sources": result.get("sources", [])}
        except Exception as e:
            return {"answer": f"⚠️ RAG error: {e}", "sources": []}

# -------------------- NAVIGATION --------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", [":euro: Salary Calculator", ":robot_face: Salary & Budget Chat"])

# -------------------- PAGE 1: SALARY CALCULATOR --------------------
if page == ":euro: Salary Calculator":
    st.title(":euro: Dutch Salary-to-Reality Calculator")

    # Sidebar inputs
    user_name = st.sidebar.text_input("What's your name?", "")
    if user_name:
        st.sidebar.success(f"Welcome, {user_name}! :sunglasses:")

    age = st.sidebar.number_input("What is your age?", min_value=18, max_value=70, step=1)
    has_masters_nl = False
    if age < 30:
        choice = st.sidebar.radio("Do you have a Master’s Degree (NL or equivalent)?", ["Yes", "No"])
        has_masters_nl = (choice == "Yes")

    job = st.sidebar.selectbox("Job Role", opts["jobs"])
    seniority = st.sidebar.selectbox("Seniority", opts["seniorities"])
    city = st.sidebar.selectbox("City", opts["cities"])
    accommodation_type = st.sidebar.selectbox("Accommodation Type", opts["accommodations"])
    has_car = st.sidebar.radio("Do you have a car?", ["No", "Yes"])
    car_type = st.sidebar.selectbox("Select your car type:", opts["cars"]) if has_car == "Yes" else None

    submitted = st.sidebar.button("Calculate")

    if submitted:
        try:
            res: Dict[str, Any] = get_estimates(
                job=job, seniority=seniority, city=city,
                accommodation_type=accommodation_type, car_type=car_type, db_uri=DB_URI
            )
            out = res["outputs"]

            extra = {"age": int(age), "master_diploma": bool(has_masters_nl)}
            res_tax = expat_ruling_calc(age=extra["age"], gross_salary=out['salary']['avg']*12,
                                        master_dpl=extra["master_diploma"], duration=10)

            # First year values
            first_year = min(res_tax.keys())
            net_first_year = res_tax[first_year] / 12
            disposable_first_year = net_first_year - out['essential_costs']

            payload = {
                "inputs": res["inputs"], "extra": extra, "outputs": out,
                "tax dict": res_tax, "net tax": net_first_year
            }
            st.session_state["last_payload"] = payload

            # ---- Metrics ----
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Gross Salary", f"€{out['salary']['avg']:,.0f}")
            col2.metric("Net Salary (2026)", f"€{net_first_year:,.0f}")
            col3.metric("Essential Costs", f"€{out['essential_costs']:,.0f}")
            col4.metric("Disposable (2026)", f"€{disposable_first_year:,.0f}")

            # ---- Projection Table ----
            projection_data = []
            for year, net_annual in res_tax.items():
                net_monthly = net_annual / 12
                disposable = net_monthly - out['essential_costs']
                projection_data.append({"Year": year,
                                        "Net Monthly (€)": round(net_monthly, 0),
                                        "Disposable Monthly (€)": round(disposable, 0)})
            df_proj = pd.DataFrame(projection_data)
            st.markdown("### 📈 Net Income Projection (2026–2035)")
            st.dataframe(df_proj, use_container_width=True)

            # ---- Projection Chart ----
            fig = px.line(df_proj, x="Year", y=["Net Monthly (€)", "Disposable Monthly (€)"],
                          markers=True, title="Net & Disposable Income Projection")
            st.plotly_chart(fig, use_container_width=True)

        except ValueError as ve:
            st.warning(str(ve))
        except Exception as e:
            st.error(f"Unexpected error: {e}")
    else:
        st.info("Fill in the fields and press **Calculate**.")

# -------------------- PAGE 2: LLM CHAT --------------------
elif page == ":robot_face: Salary & Budget Chat":
    st.title(":robot_face: Ask about Your Salary & Budget")
    st.info("Ask things like: 'Disposable income in Amsterdam with €5000 gross?'")

    suggested_questions = [
        "Average salary for Data Scientist in Amsterdam?",
        "How much to budget for rent in Utrecht?",
        "How much disposable income with €4500 net in Rotterdam?"
    ]
    st.write(":bulb: Suggested questions:")
    for q in suggested_questions:
        if st.button(q):
            with st.spinner("Thinking..."):
                result = rag_answer(q)
            st.success(result["answer"])
            if result.get("sources"):
                st.caption("📌 Source(s): " + ", ".join(result["sources"]))

    user_input = st.text_area("Or type your own question:", "")
    if st.button("Ask") and user_input:
        with st.spinner("Thinking..."):
            result = rag_answer(user_input)
        st.success(result["answer"])
        if result.get("sources"):
            st.caption("📌 Source(s): " + ", ".join(result["sources"]))
