from langchain_community.utilities import SQLDatabase

from loaders import build_normalized_main_db, ingest_new_jsons
from nlsql import init_llm, build_sql_writer, execute_sql, answer_from_result, strip_fences

DB_URI = "sqlite:///db/app.db"

def demo_query_normalized():
    # 1) Construir DB si no existe
    build_normalized_main_db(db_uri=DB_URI)

    # 2) (Opcional) Ejemplo: ingerir un JSON nuevo
    #    -> comenta esta parte si no quieres usarlo en cada corrida
    # ingest_new_jsons(DB_URI, {
    #     "gd": "data/clean_data/le_wagon.json"
    # })

    # 3) Conectarse a la DB y preguntar
    db = SQLDatabase.from_uri(DB_URI)
    llm = init_llm()
    writer = build_sql_writer(db, llm)

    # question = "tell me the highest salary and the highest cost of renting in Amsterdam"
    question = "How much does water cost per month according to nibud?"

    res = writer.invoke({"history": [], "question": question})
    sql = strip_fences(res["query"])
    raw = execute_sql(db, sql)
    answer = answer_from_result(llm, question, sql, raw)

    print("SQL:\n", sql)
    print("\nANSWER:\n", answer)

def main():
    demo_query_normalized()
