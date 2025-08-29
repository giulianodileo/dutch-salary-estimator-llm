# Dutch Salary-to-Reality Calculator (with RAG integration)

# -------------------- LIBRARIES --------------------
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import re
from datetime import datetime
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import os

# -------------------- IMPORT TOOLS --------------------
from tools import get_gross_salary, calculate_income_tax, deduct_expenses

# -------------------- LANGCHAIN / LLM SETUP --------------------
try:
    from langchain.chat_models import init_chat_model
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from langchain_community.document_loaders import TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.vectorstores import InMemoryVectorStore
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.documents import Document
    from typing_extensions import List, TypedDict
    from langgraph.graph import START, StateGraph
    HAS_LLM = True
except ImportError:
    st.sidebar.error("⚠️ Could not import LangChain / Google GenAI modules. Check your installation.")
    HAS_LLM = False

# -------------------- LOAD ENV --------------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.sidebar.error("⚠️ GOOGLE_API_KEY not found. Please add it to your .env file.")

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- GLOBAL CONSTANTS --------------------
ACCOMMODATION = {
    "Room": 700,
    "Studio": 1100,
    "Apartment (1 bedroom)": 1600,
    "Apartment (2 bedroom)": 2200
}
CITIES = ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven", "Groningen"]
JOBS = [
    "Backend Engineer", "Data Analyst", "Data Scientist", "Data Engineer",
    "DevOps Engineer", "Frontend Engineer", "Security Engineer", "Software Engineer"
]
SENIORITY_LEVELS = ["Junior", "Mid-Level", "Senior"]

# -------------------- LLM + RAG SETUP --------------------
@st.cache_resource(show_spinner=True)
def load_llm():
    if not HAS_LLM:
        return None
    try:
        return init_chat_model("gemini-2.5-flash", model_provider="google_genai")
    except Exception as e:
        st.sidebar.error(f"⚠️ Could not load LLM: {e}")
        return None

llm = load_llm()

@st.cache_resource(show_spinner=True)
def load_vector_store():
    """Load and index Markdown docs for RAG once at startup."""
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        BASE_DIR = Path(__file__).resolve().parent
        DATA_DIR = BASE_DIR.parent / "data" / "RAG"

        docs = []
        for md_file in DATA_DIR.glob("*.md"):
            loader = TextLoader(str(md_file), encoding="utf-8")
            docs.extend(loader.load())

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        all_splits = text_splitter.split_documents(docs)

        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        vector_store = InMemoryVectorStore(embeddings)
        vector_store.add_documents(all_splits)

        st.sidebar.info(f"RAG initialized with {len(docs)} docs → {len(all_splits)} chunks")
        return vector_store
    except Exception as e:
        st.sidebar.error(f"⚠️ Could not initialize RAG: {e}")
        return None

vector_store = load_vector_store()

if HAS_LLM and llm and vector_store:
    rag_prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a specialized assistant helping professionals in the Netherlands "
         "understand salaries, taxes, housing, and living costs. "
         "Only answer using the provided context. "
         "If the context does not contain the answer, say you don't know. "
         "Keep answers concise (max 3 sentences), factual, and include SOURCE labels."),
        ("human", "Question: {question}\n\nContext:\n{context}\n\nAnswer:")
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
        sources_used, docs_content = [], []
        for doc in state["context"]:
            filename = Path(doc.metadata.get("source", "unknown")).name
            label = SOURCE_LABELS.get(filename, filename)
            sources_used.append(label)
            docs_content.append(doc.page_content)

        docs_text = "\n\n".join(docs_content)
        messages = rag_prompt.invoke({"question": state["question"], "context": docs_text})
        response = llm.invoke(messages)

        return {"answer": response.content.strip(), "sources": sorted(set(sources_used))}

    graph_builder = StateGraph(State).add_sequence([retrieve, generate])
    graph_builder.add_edge(START, "retrieve")
    rag_chain = graph_builder.compile()
else:
    rag_chain = None

def rag_answer(question: str):
    if not rag_chain:
        return {"answer": "⚠️ RAG not available.", "sources": []}
    try:
        return rag_chain.invoke({"question": question})
    except Exception as e:
        return {"answer": f"⚠️ RAG error: {e}", "sources": []}

# -------------------- HELPER FUNCTIONS --------------------
def calculate_salary(job, seniority, city, accommodation_type):
    try:
        gross = get_gross_salary.invoke({"job_title": job, "seniority": seniority})
        if gross == 0:
            return None, None, None, None
        tax_result = calculate_income_tax.invoke({"gross_salary": gross})
        net = tax_result["net_after_tax"]
        expense_result = deduct_expenses.invoke({"net_salary": net, "city": city})
        expenses = expense_result["expenses"] + ACCOMMODATION[accommodation_type]
        leftover = net - expenses
        return gross, net, expenses, leftover
    except Exception as e:
        st.error(f"Error calculating salary: {e}")
        return None, None, None, None

def render_salary_charts(expenses, leftover):
    df = pd.DataFrame({
        "Category": ["Costs", "Disposable Income"],
        "Amount": [expenses, leftover]
    })
    fig = px.pie(
        df,
        values="Amount",
        names="Category",
        title="💰 Expenses vs Disposable Income",
        hole=0.4,
        color="Category",
        color_discrete_map={
            "Costs": "#2E91E5",
            "Disposable Income": "#1CA71C"
        }
    )
    fig.update_traces(
        textinfo="percent",
        textfont=dict(color="white", size=18, family="Arial Black"),
        insidetextorientation="horizontal"
    )
    fig.update_layout(title_x=0.5, legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

def save_feedback(feedback_text):
    try:
        with open("feedback.jsonl", "a") as f:
            json.dump({"timestamp": str(datetime.now()), "feedback": feedback_text}, f)
            f.write("\n")
        st.success("Thank you for your feedback!")
    except Exception as e:
        st.error(f"Could not save feedback: {e}")

# -------------------- NAVIGATION --------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["💶 Salary Calculator", "🤖 Salary & Budget Chat", "❓ Help"])

# -------------------- PAGE 1: SALARY CALCULATOR --------------------
if page == "💶 Salary Calculator":
    st.title("💶 Dutch Salary-to-Reality Calculator")
    user_name = st.sidebar.text_input("What's your name?", "")
    if user_name:
        st.sidebar.success(f"Welcome, {user_name}! 😎")

    age = st.sidebar.number_input("What is your age?", min_value=18, max_value=70, step=1)
    has_masters_nl = None
    if age < 30:
        has_masters_nl = st.sidebar.radio("Do you have a Master’s Degree obtained in NL?", ["Yes", "No"])

    job = st.sidebar.selectbox("Job Role", JOBS)
    seniority = st.sidebar.selectbox("Seniority", SENIORITY_LEVELS)
    city = st.sidebar.selectbox("City", CITIES)
    accommodation_type = st.sidebar.selectbox("Accommodation Type", list(ACCOMMODATION.keys()))

    if st.sidebar.button("Calculate"):
        gross, net, expenses, leftover = calculate_salary(job, seniority, city, accommodation_type)
        if gross is None:
            st.error("Salary data not available.")
        else:
            st.subheader(f"Expected salary for a {seniority} {job} in {city}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Gross Salary", f"€{gross:,.0f}")
            col2.metric("Net Salary", f"€{net:,.0f}")
            col3.metric("Costs", f"€{expenses:,.0f}")
            col4.metric("Disposable Income", f"€{leftover:,.0f}")

            render_salary_charts(expenses, leftover)

# -------------------- PAGE 2: RAG CHAT --------------------
elif page == "🤖 Salary & Budget Chat":
    st.title("🤖 Ask about Salary & Budget")
    user_input = st.text_area("Your Question:", "")
    if st.button("Ask") and user_input:
        with st.spinner("Thinking..."):
            result = rag_answer(user_input)
            st.success(result["answer"])
            if result.get("sources"):
                st.caption("📌 Source(s): " + ", ".join(result["sources"]))

# -------------------- PAGE 3: HELP --------------------
elif page == "❓ Help":
    st.title("Help & FAQ")
    st.write("""
    **Frequently Asked Questions:**
    - **How do I use the Salary Calculator?** Select your job, location, and seniority.
    - **Why age & degree?** If under 30, degree info may affect benefits like the 30% ruling.
    - **What is the Chat?** Answers are based on your uploaded Markdown docs (RAG) + Gemini.
    """)
    feedback = st.text_area("Your Feedback:", "")
    if st.button("Submit Feedback") and feedback:
        save_feedback(feedback)
