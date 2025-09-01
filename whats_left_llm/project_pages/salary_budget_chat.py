import streamlit as st
from pathlib import Path
from typing import List
import asyncio
import os

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


# -------------------- PAGE 2: LLM CHAT --------------------
def render():
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
