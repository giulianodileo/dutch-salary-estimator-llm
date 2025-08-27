import json
import re
from pathlib import Path

# --- 1) Paths ---
input_path = Path("/Users/andresgentile/Desktop/dutch-salary-estimator-llm/data/scrape_rental_house.json")
output_path = Path("data/clean_data/cleaning_rental_house.json")

# --- 2) Cargar el JSON scrapeado ---
with open(input_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# --- 3) Función para parsear rangos ---
def parse_eur_range(s: str):
    s_clean = s.replace("€", "").replace(" ", "").replace(",", "")
    lo, hi = map(int, s_clean.split("-"))
    return lo, hi

# --- 4) Transformación al nuevo schema ---
def transform(data: dict):
    mapping = {
        "studio_per_month": "studio",
        "one_bedroom_per_month": "one_bedroom",
        "two_bedroom_per_month": "two_bedroom",
    }
    out_rows = []
    for row in data["rows"]:
        for k, accomodation in mapping.items():
            raw = row.get(k)
            if not raw:
                continue
            lo, hi = parse_eur_range(raw)
            avg = (lo + hi) / 2
            out_rows.append({
                "city": row["city"],
                "accomodation": accomodation,
                "period": "month",
                "currency": "EUR",
                "min_amount": lo,
                "max_amount": hi,
                "avg_amount": avg,
                "source_url": data["source_url"],
            })
    return out_rows

cleaned = transform(data)

# --- 5) Guardar como lista plana ---
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cleaned, f, indent=2, ensure_ascii=False)
