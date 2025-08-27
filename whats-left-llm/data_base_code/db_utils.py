# db_utils.py
from pathlib import Path
import sqlite3
from langchain_community.utilities import SQLDatabase

def connect_sqlite_uri(db_uri: str) -> sqlite3.Connection:
    """Abre/crea un archivo SQLite desde un URI tipo sqlite:///db/app.db"""
    assert db_uri.startswith("sqlite:///"), "Use a sqlite:/// URI"
    sqlite_path = db_uri.replace("sqlite:///", "", 1)
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(sqlite_path)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def sqlite_schema(db: SQLDatabase) -> str:
    """
    Devuelve el esquema de la DB principal (main),
    suficiente para que el LLM sepa qué tablas y columnas hay.
    """
    try:
        return db.get_table_info()
    except Exception:
        return "-- Could not retrieve schema"
