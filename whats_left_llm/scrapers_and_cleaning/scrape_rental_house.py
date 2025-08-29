# whatsleft/scrape_rental_house.py
# pip install requests beautifulsoup4 pydantic

import os, re, time, json, requests
from typing import List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel

URL = "https://renthunter.nl/what-influences-rent-prices-in-the-netherlands-in-2025/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# ---------- Schema ----------
class RentRow(BaseModel):
    city: str
    studio_per_month: str
    one_bedroom_per_month: str
    two_bedroom_per_month: str

class RentTable(BaseModel):
    source_url: str
    scraped_at: str
    rows: List[RentRow]

# ---------- Fetch ----------
def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

# ---------- Parse helpers ----------
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip().lower()

def find_rent_table(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """
    Busca la tabla cuyo header contenga City / Studio / 1-bedroom / 2-bedroom.
    """
    for table in soup.find_all("table"):
        # intenta con <thead><th>
        headers = [ _norm(th.get_text(" ", strip=True)) for th in table.select("thead th") ]
        # o con la primera fila si no hay thead
        if not headers:
            first_row = table.find("tr")
            if first_row:
                headers = [ _norm(td.get_text(" ", strip=True)) for td in first_row.find_all(["th","td"]) ]

        if not headers:
            continue

        has_city   = any("city"       in h for h in headers)
        has_studio = any("studio"     in h for h in headers)
        has_1bed   = any(("1" in h and "bed" in h) for h in headers)
        has_2bed   = any(("2" in h and "bed" in h) for h in headers)

        if has_city and has_studio and has_1bed and has_2bed:
            return table
    return None

def parse_rent_table(html: str, source_url: str) -> RentTable:
    soup = BeautifulSoup(html, "html.parser")
    table = find_rent_table(soup)
    if not table:
        raise ValueError("No encontré la tabla con City / Studio / 1-bedroom / 2-bedroom.")

    # header indices (soporta ordenes distintos)
    header_cells = table.select("thead th")
    if not header_cells:
        header_cells = table.find("tr").find_all(["th","td"])

    headers = [ _norm(th.get_text(" ", strip=True)) for th in header_cells ]
    idx_city = next(i for i,h in enumerate(headers) if "city" in h)
    idx_stud = next(i for i,h in enumerate(headers) if "studio" in h)
    idx_1bed = next(i for i,h in enumerate(headers) if ("1" in h and "bed" in h))
    idx_2bed = next(i for i,h in enumerate(headers) if ("2" in h and "bed" in h))

    # body rows
    body_rows = table.select("tbody tr")
    if not body_rows:
        trs = table.find_all("tr")
        body_rows = trs[1:] if len(trs) > 1 else []

    rows: List[RentRow] = []
    for tr in body_rows:
        tds = tr.find_all(["td","th"])
        if len(tds) < 4:
            continue
        cell = lambda i: re.sub(r"\s+", " ", tds[i].get_text(" ", strip=True).replace("\xa0"," ")).strip()
        rows.append(RentRow(
            city=cell(idx_city),
            studio_per_month=cell(idx_stud),
            one_bedroom_per_month=cell(idx_1bed),
            two_bedroom_per_month=cell(idx_2bed),
        ))

    return RentTable(
        source_url=source_url,
        scraped_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        rows=rows
    )

# ---------- Save to <repo-root>/raw_data/scrape_rental_house.json ----------
def save_to_raw_data(obj: BaseModel, filename: str = "scrape_rental_house.json") -> str:
    script_dir   = os.path.dirname(os.path.abspath(__file__))  # .../whatsleft
    project_root = os.path.dirname(script_dir)                 # subir 1 nivel (repo root)
    raw_dir      = os.path.join(project_root, "data")
    os.makedirs(raw_dir, exist_ok=True)
    out_path = os.path.join(raw_dir, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(obj.model_dump(), f, ensure_ascii=False, indent=2)
    return out_path

# ---------- Main ----------
if __name__ == "__main__":
    html = fetch_html(URL)
    rent_table = parse_rent_table(html, URL)
    out_file = save_to_raw_data(rent_table, filename="scrape_rental_house.json")
    print(json.dumps(rent_table.model_dump(), indent=2, ensure_ascii=False))
    print(f"\n[OK] saved to {out_file}")
