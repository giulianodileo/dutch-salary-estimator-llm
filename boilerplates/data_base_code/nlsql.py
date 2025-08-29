# nlsql.py
import os, re
from typing_extensions import TypedDict, Annotated

from langchain_community.utilities import SQLDatabase
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ✅ usar el nuevo helper
from db_utils import sqlite_schema

def init_llm():
    # Requires GOOGLE_API_KEY in env for google_genai provider
    if not os.getenv("GOOGLE_API_KEY"):
        raise EnvironmentError(
            "Missing GOOGLE_API_KEY. Set it in your environment, e.g.:\n"
            "  export GOOGLE_API_KEY='your-key-here'"
        )
    return init_chat_model("gemini-2.5-flash", model_provider="google_genai")

class QueryOutput(TypedDict):
    query: Annotated[str, ..., "Return ONLY a valid SQL query. No markdown, no prose."]

def strip_fences(q: str) -> str:
    import re as _re
    if not q: return ""
    q = q.strip()
    q = _re.sub(r"^```(?:\w+)?\s*", "", q, flags=_re.IGNORECASE)
    q = _re.sub(r"\s*```$", "", q)
    return q.strip()

DB_HINT_RE = re.compile(
    r"\b(salary|salaries|position|seniority|avg|average|min|max|median|count|sum|"
    r"top|by|group|filter|where|roles?|engineer|scientist|mlops|data|pay|compensation|"
    r"premium|insurance|health|rent|housing|accommodation|utilities?|gas|electricity|water|"
    r"car|vehicle|fuel|maintenance|depreciation)\b",
    re.IGNORECASE,
)

def is_db_question(q: str) -> bool:
    return bool(DB_HINT_RE.search(q or ""))

# ✅ Texto ajustado a una sola DB (sin aliases)
SQL_SYSTEM = """
You are a SQL generator for a jobs & living-costs advisor assistant.
Output ONLY a syntactically correct {dialect} SQL query based on the latest user question.
NEVER invent tables or columns.

Use table names exactly as they appear in the schema below (single database).
Avoid joins across unrelated tables; prefer per-table aggregation and combine with UNION ALL
only when appropriate. If unsure, keep the query simple and focused.

Schema (tables & columns):
{table_info}
"""

SQL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SQL_SYSTEM),
    MessagesPlaceholder("history"),
    ("user", "Question: {question}\nReturn ONLY a SQL query."),
])

ANSWER_PROMPT = ChatPromptTemplate.from_template(
    "You are a professional jobs & salaries advisor.\n\n"
    "User question: {question}\n\n"
    "SQL executed:\n```sql\n{sql}\n```\n"
    "Raw result: {raw}\n\n"
    "Provide a concise, professional answer."
)

CASUAL_SYSTEM = """
You are a professional, friendly jobs & salaries advisor.
- Keep replies brief and conversational.
- Do NOT fabricate data or query results.
- Do NOT include SQL in your response.
"""
CASUAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", CASUAL_SYSTEM),
    MessagesPlaceholder("history"),
    ("user", "{input}"),
])

def build_sql_writer(db: SQLDatabase, llm):
    # ✅ obtener el schema simple de la DB principal
    schema_text = sqlite_schema(db)
    return (
        SQL_PROMPT.partial(dialect=db.dialect, table_info=schema_text)
        | llm.with_structured_output(QueryOutput)
    )

def build_casual_chain(llm):
    return CASUAL_PROMPT | llm

def execute_sql(db: SQLDatabase, sql: str):
    tool = QuerySQLDatabaseTool(db=db)
    try:
        return tool.invoke(sql)
    except Exception as e:
        return f"ERROR: {e}"

def answer_from_result(llm, question: str, sql: str, raw_result: str) -> str:
    if isinstance(raw_result, str) and raw_result.startswith("ERROR:"):
        return f"Query failed.\n\n```sql\n{sql}\n```\n{raw_result}"
    return llm.invoke(
        ANSWER_PROMPT.invoke({"question": question, "sql": sql, "raw": raw_result})
    ).content
