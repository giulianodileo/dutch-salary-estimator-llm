# Dutch Salary-to-Reality Calculator Prototype (Enhanced)

import streamlit as st
import pandas as pd
import plotly.express as px
import re
from pathlib import Path
# pip install langgraph

# Import LangChain tools (salary calc)
from tools import get_gross_salary, calculate_income_tax, deduct_expenses

# Import LangChain (Gemini chat + embeddings)
try:
    from langchain.chat_models import init_chat_model
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from langchain_community.document_loaders import DirectoryLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.vectorstores import InMemoryVectorStore
    from langchain import hub
    from langchain_core.documents import Document
    from typing_extensions import List, TypedDict
    from langgraph.graph import START, StateGraph

    HAS_LLM = True
except ImportError:
    st.sidebar.error("⚠️ Could not import LangChain Google GenAI modules. Check your installation.")
    HAS_LLM = False

# -------------------- CONFIG --------------------
st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- LLM SETUP --------------------
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

# -------------------- RAG SETUP --------------------
@st.cache_resource(show_spinner=True)
def load_vector_store():
    """Load and index Markdown docs for RAG once at startup."""
    try:
        BASE_DIR = Path(__file__).resolve().parent
        DATA_DIR = BASE_DIR / "data" / "RAG"

        loader = DirectoryLoader(str(DATA_DIR), glob="*.md")
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        all_splits = text_splitter.split_documents(docs)

        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        vector_store = InMemoryVectorStore(embeddings)
        vector_store.add_documents(all_splits)

        return vector_store
    except Exception as e:
        st.sidebar.error(f"⚠️ Could not initialize RAG: {e}")
        return None

vector_store = load_vector_store()

# -------------------- RAG CHAIN --------------------
if HAS_LLM and llm and vector_store:
    prompt = hub.pull("rlm/rag-prompt")

    class State(TypedDict):
        question: str
        context: List[Document]
        answer: str

    def retrieve(state: State):
        retrieved_docs = vector_store.similarity_search(state["question"])
        return {"context": retrieved_docs}

    def generate(state: State):
        docs_content = "\n\n".join(doc.page_content for doc in state["context"])
        messages = prompt.invoke({"question": state["question"], "context": docs_content})
        response = llm.invoke(messages)
        return {"answer": response.content}

    graph_builder = StateGraph(State).add_sequence([retrieve, generate])
    graph_builder.add_edge(START, "retrieve")
    rag_chain = graph_builder.compile()
else:
    rag_chain = None

def rag_answer(question: str):
    if not rag_chain:
        return "⚠️ RAG not available. Please check setup."
    try:
        result = rag_chain.invoke({"question": question})
        return result["answer"]
    except Exception as e:
        return f"⚠️ RAG error: {e}"

# -------------------- VISUALIZATION --------------------
def render_salary_charts(net, city, leftover, expenses):
    df = pd.DataFrame({
        "Category": ["Net Salary", "Essential Costs", "Disposable Income"],
        "Amount": [net, expenses, leftover]
    })
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(px.bar(df, x="Category", y="Amount", color="Category", title="Breakdown"))
    with col2:
        st.plotly_chart(px.pie(df, values="Amount", names="Category", title="Salary Distribution"))

# -------------------- NAVIGATION --------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["💶 Salary Calculator", "🤖 LLM Chat", "❓ Help"])

# -------------------- PAGE 1: SALARY CALCULATOR --------------------
if page == "💶 Salary Calculator":
    st.title("💶 Dutch Salary-to-Reality Calculator")

    user_name = st.sidebar.text_input("What's your name?", "")
    if user_name:
        st.sidebar.success(f"Welcome, {user_name}! 😎")

    job = st.sidebar.selectbox("What is your job?", [
        "Backend Engineer",
        "Data Analyst",
        "Data Scientist",
        "Data Engineer",
        "DevOps Engineer",
        "Frontend Engineer",
        "Security Engineer",
        "Software Engineer",
    ])
    seniority = st.sidebar.selectbox("What is your seniority?", ["Junior", "Mid-Level", "Senior"])
    city = st.sidebar.selectbox("Where are you planning to live?", ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven", "Groningen"])

    if st.sidebar.button("Calculate"):
        gross = get_gross_salary.invoke({"job_title": job, "seniority": seniority})
        if gross == 0:
            st.error("No salary data available for that combination.")
        else:
            tax_result = calculate_income_tax.invoke({"gross_salary": gross})
            net = tax_result["net_after_tax"]
            expense_result = deduct_expenses.invoke({"net_salary": net, "city": city})
            leftover = expense_result["remaining"]
            expenses = expense_result["expenses"]

            st.subheader(f"What you can expect as a {seniority} {job} in the Netherlands if you want to live in {city}")
            st.metric("Your Gross Salary would be around", f"€{gross:,.0f}")
            st.metric("Your Net Salary (after tax) could be around", f"€{net:,.0f}")
            st.metric("Essential Living Costs", f"€{expenses:,.0f}")
            st.metric("💸 What's Left", f"€{leftover:,.0f}")

            render_salary_charts(net, city, leftover, expenses)

# -------------------- PAGE 2: LLM CHAT --------------------
elif page == "🤖 LLM Chat":
    st.title("🤖 Ask about your Salary Situation (with RAG)")
    st.info("Type a salary-related or NL-expat-related question. Answers are based on your knowledge base + Gemini.")

    user_input = st.text_area("Your Question:", "")
    if st.button("Ask") and user_input:
        with st.spinner("Thinking..."):
            answer = rag_answer(user_input)
            st.success(answer)

        # Optional chart extraction
        city_match = next((city for city in ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven", "Groningen"]
                           if city.lower() in user_input.lower()), None)
        salary_match = re.findall(r"\d+", user_input)
        if city_match and salary_match:
            gross = int(salary_match[0])
            tax_result = calculate_income_tax.invoke({"gross_salary": gross})
            net = tax_result["net_after_tax"]
            expense_result = deduct_expenses.invoke({"net_salary": net, "city": city_match})
            leftover = expense_result["remaining"]
            render_salary_charts(net, city_match, leftover, expense_result["expenses"])

# -------------------- PAGE 3: HELP --------------------
elif page == "❓ Help":
    st.title("Help & FAQ")
    st.write("""
    **Frequently Asked Questions:**
    - **How do I use the Salary Calculator?**
      Select your job role, location, and seniority to see your net salary and what's left after essential costs.

    - **What is the LLM Chat?**
      You can ask salary or Dutch-expat-related questions. Answers combine your Markdown knowledge base with Gemini (RAG).

    - **How can I provide feedback?**
      Use the feedback form below to share your thoughts or report issues.
    """)
    feedback = st.text_area("Your Feedback:", "")
    if st.button("Submit Feedback"):
        if feedback:
            st.success("Thank you for your feedback!")
        else:
            st.warning("Please enter your feedback before submitting.")
