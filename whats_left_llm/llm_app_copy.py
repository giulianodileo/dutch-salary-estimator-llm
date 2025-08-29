# Dutch Salary-to-Reality Calculator (Enhanced & Accessible)
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json

from whats_left_llm.data_base_code.calculator_core import get_estimates, DB_URI
from whats_left_llm.calculate_30_rule import expat_ruling_calc
from whats_left_llm.chart import return_net_income

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime as dt
import asyncio
import re
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from typing_extensions import List, TypedDict
from langgraph.graph import START, StateGraph
from dotenv import load_dotenv
import os

# --- load .env first ---
load_dotenv()

# API activation
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.sidebar.error("⚠️ GOOGLE_API_KEY not found. Please add it to your .env file.")



# -------------------- LLM SETUP --------------------
try:
    from langchain.chat_models import init_chat_model
    HAS_LLM = True
except ImportError:
    st.sidebar.error(
        ":warning: Could not import init_chat_model. Install LangChain + Google GenAI."
    )
    HAS_LLM = False

# Colorblind-friendly palette
COLOR_PALETTE = ["#2E91E5", "#E15F99", "#1CA71C", "#FB0D0D"]

# ---------- Helpers de DB para poblar selects ----------
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
        # Jobs & seniorities
        rows = con.execute("SELECT DISTINCT position_name FROM job_positions_seniorities ORDER BY position_name;").fetchall()
        opts["jobs"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT seniority FROM job_positions_seniorities ORDER BY seniority;").fetchall()
        opts["seniorities"] = [r[0] for r in rows]

        # Cities & accommodation types
        rows = con.execute("SELECT DISTINCT city FROM rental_prices ORDER BY city;").fetchall()
        opts["cities"] = [r[0] for r in rows]
        rows = con.execute("SELECT DISTINCT accommodation_type FROM rental_prices WHERE accommodation_type IS NOT NULL ORDER BY accommodation_type;").fetchall()
        opts["accommodations"] = [r[0] for r in rows]

        # Car classes
        rows = con.execute("SELECT DISTINCT type FROM transportation_car_costs ORDER BY type;").fetchall()
        opts["cars"] = [r[0] for r in rows]

    return opts

opts = load_options(DB_URI)
if not any(opts.values()):
    st.error("No encuentro la base de datos o las tablas están vacías. Asegúrate de haberla creado y cargado JSONs.")
    st.stop()

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Dutch Salary-to-Reality Calculator",
    page_icon=":euro:",
    layout="wide",
    initial_sidebar_state="expanded"
)
# -------------------- CACHED LLM LOADER --------------------
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


# -------------------- RAG CHAIN --------------------

if HAS_LLM and llm and vector_store:

    rag_prompt = ChatPromptTemplate.from_messages([

    ("system",
     "You are a specialized assistant helping professionals in the Netherlands "
     "understand salaries, taxes, housing, transportation, and related costs. "
     "You only answer using the provided context (retrieved documents). "
     "If the context does not contain the answer, explicitly say you don't know. "
     "Use simple words when interacting with the user. "
     "Keep answers concise (max 3 sentences), factual, and insightful. "
     "Always include the SOURCE LABEL in your answers."),
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
    "health_insurance.md": "Rijksoverheid (Government of the Netherlands)",
    "rental_prices.md": "HousingAnywhere, RentHunter",
    "ruling_30_narrative.md": "Belastingdienst (Tax and Customs Administration)",
    "seniority_levels.md": "Google",
    "tax_narrative_NL.md": "Belastingdienst (Tax and Customs Administration)",
    "transportation.md": "Nibud (National Institute for Family Finance Information)",
    "utilities.md": "Nibud (National Institute for Family Finance Information)"
}


    def generate(state: State):
        sources_used = []
        docs_content = []

        for doc in state["context"]:
            # Always fall back to our manual mapping
            filename = Path(doc.metadata.get("source", "unknown")).name
            label = SOURCE_LABELS.get(filename, filename)  # map filename → friendly name
            sources_used.append(label)
            docs_content.append(doc.page_content)  # keep only the content


        docs_text = "\n\n".join(docs_content)

        messages = rag_prompt.invoke({
            "question": state["question"],
            "context": docs_text
        })
        response = llm.invoke(messages)

        return {
            "answer": response.content.strip(),
            "sources": sorted(set(sources_used))  # dedup + sorted
        }




    graph_builder = StateGraph(State).add_sequence([retrieve, generate])
    graph_builder.add_edge(START, "retrieve")
    rag_chain = graph_builder.compile()
else:
    rag_chain = None

def rag_answer(question: str):
    if not rag_chain:
        return {"answer": "⚠️ RAG not available. Please check setup.", "sources": []}
    try:
        result = rag_chain.invoke({"question": question})
        return result  # <-- keep the dict {answer: ..., sources: [...]}
    except Exception as e:
        return {"answer": f"⚠️ RAG error: {e}", "sources": []}

# -------------------- HELPER FUNCTIONS --------------------
def calculate_salary(job, seniority, city, accommodation_type):
    """Returns gross, net, expenses, leftover"""
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
    """Accessible Pie Chart: Expenses vs Disposable Income with white text for disposable income"""
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
            "Essential + Housing Costs": "#2E91E5",
            "Disposable Income": "#1CA71C"
        })
    fig.update_traces(textinfo="label+percent+value",
                     textfont_color=["black", "white"])
    st.plotly_chart(fig)
# REMOVED: render_comparison_chart function
# def render_comparison_chart(net_salary, city_avg_expenses):
#    """Compare user's net vs average city expenses"""
#    df = pd.DataFrame({
#        "Category": ["Your Net Salary", "Avg City Expenses"],
#        "Amount": [net_salary, city_avg_expenses]
#    })
#    st.plotly_chart(
#        px.bar(
#            df, x="Category", y="Amount",
#            title=":bar_chart: Net Salary vs Average City Expenses",
#            color="Category", color_discrete_sequence=COLOR_PALETTE
#        )
#    )
def llm_answer(question: str):
    """Query the LLM"""
    if not HAS_LLM or not llm:
        return ":warning: LLM not available."
    try:
        return llm.invoke(question).content
    except Exception as e:
        return f":warning: LLM error: {e}"
def save_feedback(feedback_text):
    """Save feedback locally"""
    try:
        with open("feedback.jsonl", "a") as f:
            json.dump({"timestamp": str(datetime.now()), "feedback": feedback_text}, f)
            f.write("\n")
        st.success("Thank you for your feedback!")
    except Exception as e:
        st.error(f"Could not save feedback: {e}")
# -------------------- NAVIGATION --------------------

st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", [":euro: Salary Calculator",
                                   ":robot_face: Salary & Budget Chat",
                                   ":question: Help"])

# -------------------- PAGE 1: SALARY CALCULATOR --------------------

submitted = False

if page == ":euro: Salary Calculator":
    st.title(":euro: Dutch Salary-to-Reality Calculator")

    # Sidebar Inputs
    user_name = st.sidebar.text_input("What's your name?", "")
    if user_name:
        st.sidebar.success(f"Welcome, {user_name}! :sunglasses:")

    age = st.sidebar.number_input("What is your age?", min_value=18, max_value=70, step=1)
    # Degree question immediately after age

    if age < 30:
        choice = st.sidebar.radio(
        "Do you have a Master’s Degree (or higher) obtained in the Netherlands?",
        ["Yes", "No"],
    )
        has_masters_nl = (choice == "Yes")   # <- bool True/False
    else:
        has_masters_nl = False

    # Remaining sidebar inputs
    job = st.sidebar.selectbox("Job Role", opts["jobs"])
    seniority = st.sidebar.selectbox("Seniority", opts["seniorities"])
    city = st.sidebar.selectbox("City", opts["cities"])
    accommodation_type = st.sidebar.selectbox("Accommodation Type", opts["accommodations"])
    start_date = st.sidebar.date_input("Start date (MM/DD/YYYY)", value=dt.date.today())
    duration_years = 10
    has_car = st.sidebar.radio("Do you have a car?", ["No", "Yes"])

    if has_car == "Yes":
        car_type = st.sidebar.selectbox(
            "Select your car type:", opts["cars"]
        )
    else:
        car_type = 0

    expertise = True

    # Complete calculation
    submitted = st.sidebar.button("Calculate")

#22222222222222282828282828828828282828828288282828282828282882828282882882828288282828282882
    if submitted:
        try:
            res: Dict[str, Any] = get_estimates(
                job=job,
                seniority=seniority,
                city=city,
                accommodation_type=accommodation_type,
                car_type=car_type,
                db_uri=DB_URI,
            )

            out = res["outputs"]


            # ---- armar "extra" y "payload" para pasar a otras funciones / guardar ----
            extra = {
                "age": int(age),
                "start_date_us": start_date.strftime("%m/%d/%Y"),
                "start_date_iso": start_date.isoformat(),
                "duration_years": int(duration_years),
                "expertise": bool(expertise),
                "master_diploma": bool(has_masters_nl),
            }

            res_tax = expat_ruling_calc(
                age=extra["age"],
                salary=out['salary']['avg']*12,
                date_string=extra["start_date_iso"],
                duration=extra["duration_years"],
                expertise=extra["expertise"],
                master_dpl=extra["master_diploma"])

            return_net_incomee = return_net_income(res_tax, out['essential_costs'])

            payload = {
                "inputs": res["inputs"],   # job, seniority, city, accommodation_type, car_type
                "extra": extra,            # 👈 tus nuevos inputs
                "outputs": out,            # salary, rent, car_total_per_month
                "tax dic": res_tax,
                "net tax": return_net_incomee,
            }
            st.session_state["last_payload"] = payload  # opcional, por si quieres usarlo luego

        # -------------------- METRICS --------------------
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Gross Salary", f"€{out['salary']['avg']:,.0f}")
            col2.metric("Net Salary", f"€{((return_net_incomee/12)+out['essential_costs']):,.0f}")
            col3.metric("Essential Living Costs", f"€{out['essential_costs']:,.0f}")
            col4.metric("Disposable Income", f"€{return_net_incomee/12:,.0f}")

        #         # -------------------- PIE CHART --------------------
            render_salary_charts(out['essential_costs'], return_net_incomee)
                # REMOVED: COMPARISON CHART
                # city_avg_expenses = 1200
                # render_comparison_chart(net, city_avg_expenses)
                # -------------------- DISPOSABLE INCOME GAUGE --------------------
            disposable_pct = max(0, return_net_incomee / (((return_net_incomee/12)+out['essential_costs']) * 100))
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


            # ---- métricas arriba ----
            # st.subheader(f"Result for {job} — {seniority} in {city} ({accommodation_type} and {out['essential_costs']})")
            # m1, m2, m3, m4, m5 = st.columns(5)
            # m1.metric("Salary (avg)", f"€{out['salary']['avg']:,.0f}")
            # m2.metric("Rent (avg)",   f"€{out['rent']['avg']:,.0f}")
            # m3.metric("Car / month",  f"€{out['car_total_per_month']:,.0f}")
            # m4.metric("Essential Living Costs", f"€{out['essential_costs']:,.0f}")
            # m5.metric("Your Net Salary after Tax", f"€{return_net_incomee/12:,.0f}" )

            # ---- Details con tabs: Inputs / Extra / Outputs ----
            st.markdown("### Details")
            tab1, tab2, tab3 = st.tabs(["Inputs", "Extra", "Outputs"])

            with tab1:
                st.write({
                    "job": res["inputs"]["job"],
                    "seniority": res["inputs"]["seniority"],
                    "city": res["inputs"]["city"],
                    "accommodation_type": res["inputs"]["accommodation_type"],
                    "car_type": res["inputs"]["car_type"],
                })

            with tab2:
                st.write({
                    "age": extra["age"],
                    "start_date (US)": extra["start_date_us"],
                    "start_date (ISO)": extra["start_date_iso"],
                    "duration_years": extra["duration_years"],
                    "expertise": extra["expertise"],
                    "master_diploma": extra["master_diploma"],
                })

            with tab3:
                st.write({
                    "salary": out["salary"],                  # {min, avg, max}
                    "rent": out["rent"],                      # {min, avg, max}
                    "car_total_per_month": out["car_total_per_month"],
                })

            # (opcional) también mostrar el JSON crudo
            with st.expander("Raw payload (JSON)"):
                import json
                st.code(json.dumps(payload, indent=2), language="json")



        except ValueError as ve:
            st.warning(str(ve))
        except Exception as e:
            st.error(f"Unexpected error: {e}")
    else:
        st.info("Completa los campos y presiona **Calculate**.")


elif page == ":robot_face: Salary & Budget Chat":
    st.title(":robot_face: Ask about Your Salary & Budget")
    st.info("Ask questions like: 'Disposable income in Amsterdam with €5000 gross?'")

    # Suggested questions
    suggested_questions = [
        "Average salary for Data Scientist in Amsterdam?",
        "How much to budget for rent in Utrecht?",
        "How much disposable income with €4500 net in Rotterdam?"
    ]
    st.write(":bulb: Suggested questions:")
    for q in suggested_questions:
        if st.button(q):
            user_input = q
            with st.spinner("Thinking..."):
                result = rag_answer(user_input)
            st.success(result["answer"])
            if result.get("sources"):
                st.caption("📌 Source(s): " + ", ".join(result["sources"]))

    # Free text input
    user_input = st.text_area("Or type your own question:", "")
    if st.button("Ask") and user_input:
        with st.spinner("Thinking..."):
            result = rag_answer(user_input)
        st.success(result["answer"])
        if result.get("sources"):
            st.caption("📌 Source(s): " + ", ".join(result["sources"]))

    # if st.sidebar.button("Calculate"):
    #     gross, net, expenses, leftover = calculate_salary(job, seniority, city, accommodation_type)
    #     if gross is None:
    #         st.error("Salary data not available for this combination.")
    #     else:
    #         st.subheader(f"Expected salary for a {seniority} {job} in {city}")
    #         # -------------------- METRICS --------------------
    #         col1, col2, col3, col4 = st.columns(4)
    #         col1.metric("Gross Salary", f"€{gross:,.0f}")
    #         col2.metric("Net Salary", f"€{net:,.0f}")
    #         col3.metric("Essentials + Housing Costs", f"€{expenses:,.0f}", help="Monthly essential expenses including housing.")
    #         col4.metric("Disposable Income", f"€{leftover:,.0f}", help="Money left after paying essentials + housing.")
    #         # -------------------- PIE CHART --------------------
    #         render_salary_charts(expenses, leftover)
    #         # REMOVED: COMPARISON CHART
    #         # city_avg_expenses = 1200
    #         # render_comparison_chart(net, city_avg_expenses)
    #         # -------------------- DISPOSABLE INCOME GAUGE --------------------
    #         disposable_pct = max(0, leftover / net * 100)
    #         fig = go.Figure(go.Indicator(
    #             mode="gauge+number",
    #             value=disposable_pct,
    #             domain={'x': [0, 1], 'y': [0, 1]},
    #             title={'text': "Disposable Income %"},
    #             gauge={
    #                 'axis': {'range': [0, 100]},
    #                 'bar': {'color': "green"},
    #                 'steps': [
    #                     {'range': [0, 20], 'color': 'red'},
    #                     {'range': [20, 50], 'color': 'orange'},
    #                     {'range': [50, 100], 'color': 'lightgreen'}
    #                 ],
    #                 'threshold': {
    #                     'line': {'color': "blue", 'width': 4},
    #                     'thickness': 0.75,
    #                     'value': disposable_pct
    #                 }
    #             }
    #         ))
    #         st.plotly_chart(fig, use_container_width=True)
            # -------------------- SAVINGS RECOMMENDATION --------------------
            # st.markdown("### :moneybag: Suggested Savings")
            # if leftover <= 0:
            #     st.warning("You are spending all of your net income. Consider reducing housing or essentials costs.")
            # elif leftover / net < 0.2:
            #     st.info("Your disposable income is low. Aim to save at least 5-10% of your net salary.")
            # elif leftover / net < 0.4:
            #     st.success("Good! You can save 15-25% of your net salary each month.")
            # else:
            #     st.success("Excellent! You have a high disposable income. Consider saving 25-40% or investing for growth.")
            # st.info(f":bulb: Tip: Track your spending monthly. In {city}, typical accommodation costs range around {ACCOMMODATION[accommodation_type]} €.")
##...........................................................................................................................................................................................................
