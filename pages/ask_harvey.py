# ---------- Imports and libraries --------- #

import streamlit as st
from pathlib import Path
import asyncio
import os
import re
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain.prompts import PromptTemplate
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from typing_extensions import TypedDict
from langgraph.graph import START, StateGraph
from core.styling import apply_chat_styling


# ---------- Environment setup ---------- #

load_dotenv()

GOOGLE_API_KEY = (
        st.secrets.get("GOOGLE_API_KEY")
    if "GOOGLE_API_KEY" in st.secrets
    else os.getenv("GOOGLE_API_KEY")
)

if not GOOGLE_API_KEY:
    st.sidebar.error("⚠️ GOOGLE_API_KEY not found. Please add it to your .env file.")

try:
    from langchain.chat_models import init_chat_model
    HAS_LLM = True
except ImportError:
    st.sidebar.error(":warning: Could not import init_chat_model. Install LangChain + Google GenAI.")
    HAS_LLM = False


# ---------- LLM and Vector initialization --------- #

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


# ---------- Prompt and State definition --------- #

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


# ---------- RAG helper functions --------- #

# 1. Text cleaning
def clean_text(text: str) -> str:
    """Remove markdown headers, formatting, and excessive whitespace."""
    text = re.sub(r'^#+ .*$', '', text, flags=re.MULTILINE) # Remove markdown headers
    text = re.sub(r'[*_`]', '', text) # Remove bold/italic markdown markers
    text = re.sub(r'\n{2,}', '\n', text) # Collapse multiple newlines
    return text.strip()

# 2. Document retrieval
def retrieve_docs(query, vector_store, filters=None, k=3):
    """
    Retrieve the top-k most relevant documents for a given query.

    Args:
        query (str): User question or text query.
        vector_store: The in-memory vector store.
        filters (dict, optional): Metadata filters.
        k (int, optional): Number of documents to retrieve.

    Returns:
        list: List of LangChain document objects.
    """
    if filters:
        docs = vector_store.similarity_search(query, k=k, filter=filters)
    else:
        docs = vector_store.similarity_search(query, k=k)
    return docs


# 3. Document compression
def compress_docs(docs, llm):
    """
    Summarize retrieved documents into a concise paragraph.

    Args:
        docs (list): Retrieved documents.
        llm: The loaded chat model.

    Returns:
        str: A summarized version of the combined documents.
    """
    combined_text = "\n\n".join([clean_text(doc.page_content) for doc in docs])
    compression_prompt = PromptTemplate.from_template(
        "Summarize the following text into 4-5 sentences in plain language. "
        "Do not include section titles, bullet points, or references. "
        "Keep only the essential rules, thresholds, and key numbers.\n\n{text}"
    )

    summary = llm.invoke(compression_prompt.format(text=combined_text))
    return summary.content if hasattr(summary, "content") else str(summary)


# 4. Context preparation
SOURCE_LABELS = {
    "health_insurance.md": "Rijksoverheid",
    "rental_prices.md": "HousingAnywhere, RentHunter",
    "ruling_30_narrative.md": "Belastingdienst",
    "seniority_levels.md": "Google",
    "tax_narrative_NL.md": "Belastingdienst",
    "transportation.md": "Nibud",
    "utilities.md": "Nibud"
}


def prepare_context(query, vector_store, llm, filters=None):
    """
    Retrieve and compress relevant context for a user query.

    Args:
        query (str): The user’s question.
        vector_store: The in-memory vector store.
        llm: The loaded language model.
        filters (dict, optional): Metadata filters.

    Returns:
        tuple(str, list): Compressed text summary and list of source labels.
    """
    docs = retrieve_docs(query, vector_store, filters=filters, k=3)
    if not docs:
        return "" # Specific for handling error with empty docs
    compressed = compress_docs(docs, llm)
    sources = []
    for doc in docs:
        filename = Path(doc.metadata.get("source", "unknown")).name
        sources.append(SOURCE_LABELS.get(filename, filename))
    return compressed, sources

# 5. Answer generation
def generate(state: State):
    """
    Execute the full RAG generation process:
    1. Retrieve relevant documents.
    2. Summarize them.
    3. Combine with user profile.
    4. Invoke LLM for explanation.

    Args:
        state (State): Dictionary containing the user question.

    Returns:
        dict: Generated answer and the list of sources used.
    """
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
            f"- Net Salary (calculated): €{user_info['net']:,.0f}\n"
            f"- Essential Costs: €{user_info['outputs']['essential_costs']:,.0f}\n"
            f"- Disposable Income (calculated): €{user_info['pocket']:,.0f}\n"
            f"- Netto Disposable: €{user_info['netto_disposable']}\n"
            f"- Net Tax: €{user_info['net_tax']}\n"
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
        "sources": sorted(set(sources_used)) # Not showing to the user
    }


# 6. Chain compilation and question-answer flowchart
graph_builder = StateGraph(State).add_sequence([generate])
graph_builder.add_edge(START, "generate")
rag_chain = graph_builder.compile()


def rag_answer(question: str):
    """
    Public API for answering user queries via RAG.

    Args:
        question (str): User question.

    Returns:
        dict: Contains the model's answer (and optionally sources).
    """
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


# ---------- Page setup and UI --------- #

apply_chat_styling()

# 1. Title and description
st.title("Ask Harvey 👨‍⚖️")
st.info("Please note: always consult the Netherlands Tax and Customs Administration (Belastingdienst) for all updates regarding taxation.")

# 2. Suggested questions
faq = [
    "Explain the 30% ruling in simple words.",
    "How's the housing market in the Netherlands?",
    "What are the costs of owning a car?"
]

st.write(":bulb: Suggested questions:")

for q in faq:
    if st.button(q):
        with st.spinner("Connecting the dots..."):
            result = rag_answer(q)
        st.success(result["answer"])

# 3. User input
user_input = st.text_input("Or type your own question:")
if user_input:
    with st.spinner("Connecting the dots..."):
        result = rag_answer(user_input)
    st.success(result["answer"])
