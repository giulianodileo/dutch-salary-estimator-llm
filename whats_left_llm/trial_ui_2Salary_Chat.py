import streamlit as st
from pathlib import Path
import asyncio
import os
import re

# -------------------- LLM + RAG --------------------
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain.prompts import PromptTemplate
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from typing_extensions import List, TypedDict
from langgraph.graph import START, StateGraph
from whats_left_llm.ui_functions import apply_calculator_styling

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

# ----- Page Style -----
apply_calculator_styling()

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

        # st.sidebar.info(f"✅ RAG initialized with {len(docs)} docs → {len(all_splits)} chunks")
        return vector_store

    except Exception as e:
        st.sidebar.error(f"⚠️ Could not initialize RAG: {e}")
        return None

vector_store = load_vector_store()

# -------------------- RAG CHAIN --------------------

# # --- System Prompt and Inteaction ---

if HAS_LLM and llm and vector_store:
    rag_prompt = ChatPromptTemplate.from_messages([
        ("system",
        "You are a salary calculator explainer helping professionals in the Netherlands "
        "Your role is to clearly explain how disposable income is derived, using both user details and contextual rules (taxes, insurance, rent, etc.)."
        "You do not recalculate numbers, only explain the logic and influencing factors."

        "Always merge:\n"
        "1. User profile data (salary, disposable income, age, city, etc.)\n"
        "2. Knowledge base context (retrieved documents)\n\n"

        "Guidelines:\n"
        "- Always take the user's profile into account when answering.\n"
        "- Use retrieved documents for factual references (tax rules, averages).\n"
        "- If profile info is missing, state that.\n"
        "- Keep answers concise (aim for 3-4 sentences).\n"
        "- Your tone is clean, neutral, and explanatory.\n"
        "- Never mention file names, YAML metadata, or technical details from the knowledge base.\n"
        "- Do not reference “sources” or external links. Speak naturally and directly to the user."
        "- If neither profile nor docs answer the question, explicitly say so."),
        ("human",
        "Here is the user profile:\n{user_info}\n\n"
        "Here is relevant context from the knowledge base:\n{context}\n\n"
        "User's question: {question}")
    ])

    class State(TypedDict):
        question: str
        context: str
        answer: str


# # --- Retrieval Pipeline ---

# Step 1: Clean Markdown text (avoid mentions in the answer)
def clean_text(text: str) -> str:
    """Remove markdown headers, formatting, and excessive whitespace."""
    # Remove markdown headers like ## Something
    text = re.sub(r'^#+ .*$', '', text, flags=re.MULTILINE)
    # Remove bold/italic markdown markers
    text = re.sub(r'[*_`]', '', text)
    # Collapse multiple newlines
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip()

# Step 2: Run similarity search with metadata filters
def retrieve_docs(query, vector_store, filters=None, k=3):
    """
    Retrieve relevant docs with optional metadata filtering.
    Defaults to top-3.
    """
    if filters:
        docs = vector_store.similarity_search(query, k=k, filter=filters)
    else:
        docs = vector_store.similarity_search(query, k=k)
    return docs

# Step 2: Compress docs into short summaries
def compress_docs(docs, llm):
    combined_text = "\n\n".join([clean_text(doc.page_content) for doc in docs])
    compression_prompt = PromptTemplate.from_template(
        "Summarize the following text into 4-5 sentences in plain language. "
        "Do not include section titles, bullet points, or references. "
        "Keep only the essential rules, thresholds, and key numbers.\n\n{text}"
    )
    summary = llm.invoke(compression_prompt.format(text=combined_text))
    return summary.content if hasattr(summary, "content") else str(summary)

# Step 3: Prepare context for the LLM
def prepare_context(query, vector_store, llm, filters=None):
    docs = retrieve_docs(query, vector_store, filters=filters, k=3)
    if not docs:
        return "" # Specific for handling error with empty docs
    compressed = compress_docs(docs, llm)
    sources = []
    for doc in docs:
        filename = Path(doc.metadata.get("source", "unknown")).name
        sources.append(SOURCE_LABELS.get(filename, filename))
    return compressed, sources


SOURCE_LABELS = {
    "health_insurance.md": "Rijksoverheid",
    "rental_prices.md": "HousingAnywhere, RentHunter",
    "ruling_30_narrative.md": "Belastingdienst",
    "seniority_levels.md": "Google",
    "tax_narrative_NL.md": "Belastingdienst",
    "transportation.md": "Nibud",
    "utilities.md": "Nibud"
}

# Step 4: Retrieve context and user input
def generate(state: State):
    # Retrieve compressed context (summaries of top docs)
    context, sources_used = prepare_context(state["question"], vector_store, llm)

    # Format user info for the prompt
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
            f"- Gross Salary (monthly): €{user_info['outputs']['salary']['avg']:,.0f}\n"
            f"- Gross Salary (annually): €{user_info['outputs']['salary']['avg'] * 12:,.0f}\n"
            f"- Net Salary (calculated): €{user_info['net tax']:,.0f}\n"
            f"- Essential Costs: €{user_info['outputs']['essential_costs']:,.0f}\n"
            f"- Disposable Income (calculated): €{user_info['net tax'] - user_info['outputs']['essential_costs']:,.0f}\n"
        )

    # Build final prompt
    messages = rag_prompt.invoke({
        "question": state["question"],
        "context": context,  # compressed context here
        "user_info": user_context
    })
    response = llm.invoke(messages)

    return {
        "answer": response.content.strip(),
        "sources": sorted(set(sources_used)) # Keeping this for debugging, now showing to the user
    }

# Step 5: Create question-answer flowchart
graph_builder = StateGraph(State).add_sequence([generate])
graph_builder.add_edge(START, "generate")
rag_chain = graph_builder.compile()

def rag_answer(question: str):
    if not rag_chain:
        return {"answer": "⚠️ RAG not available."}
    try:
        result = rag_chain.invoke({"question": question})
        answer = result.get("answer", "").strip()
        if not answer:
            return {"answer": "⚠️ No relevant information was found in the knowledge base."}
        return {"answer": answer}
    except Exception as e:
        print(f"RAG error: {e}")
        return {"answer": "⚠️ Something went wrong while retrieving information. Please try again."}


# -------------------- PAGE 2: LLM CHAT --------------------
with st.container():
    st.title("Ask Alex 🧞")
    st.info("Please note: always consult the Netherlands Tax Administration (Belastingdienst) for all updates regarding taxation.")

    faq = [
        "Explain the 30% ruling in simple words.",
        "How's the housing market in the Netherlands?",
        "What are the costs of owning a car?"
    ]
    st.write(":bulb: Suggested questions:")
    for q in faq:
        if st.button(q):
            with st.spinner("Thinking..."):
                result = rag_answer(q)
            st.success(result["answer"])
            # Optional: print("Retrieved sources:", result.get("sources"))

    user_input = st.text_area("Or type your own question:", "")
    if st.button("Ask") and user_input:
        with st.spinner("Thinking..."):
            result = rag_answer(user_input)
        st.success(result["answer"])
        # Optional: print("Retrieved sources:", result.get("sources"))
