# --- add to requirements if you haven't ---
# pip install -qU requests beautifulsoup4 pydantic langchain langchain-core "langchain[google-genai]" python-dotenv

import os
import time
import json
import re
import random
from typing import List, Optional, Dict
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from pydantic import BaseModel
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv

# Load .env for GOOGLE_API_KEY
load_dotenv()

# -----------------------------
# Pydantic Schema for Utilities
# -----------------------------
class ExpenseItem(BaseModel):
    category: str                    # "Gas", "Electricity", "Water"
    value: float                      # cost as float
    period: str                       # e.g., "per month"
    year: Optional[int] = None        # Year as integer
    source_url: str

class UtilitiesPage(BaseModel):
    expenses: List[ExpenseItem]

# -----------------------------
# LangChain LLM setup
# -----------------------------
llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
structured_llm = llm.with_structured_output(UtilitiesPage)

# -----------------------------
# HTTP Session + retries + headers
# -----------------------------
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "DNT": "1",
}

def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD", "OPTIONS"]
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.headers.update({
        **BASE_HEADERS,
        "User-Agent": random.choice(DEFAULT_USER_AGENTS),
        "Upgrade-Insecure-Requests": "1",
    })
    return s

# -----------------------------
# Fetch HTML + convert to text
# -----------------------------
def fetch_html(url: str, session: Optional[requests.Session] = None, timeout: int = 20) -> str:
    sess = session or build_session()
    r = sess.get(url, timeout=timeout)
    if r.status_code == 403:
        raise PermissionError(f"403 Forbidden on {url}")
    r.raise_for_status()
    return r.text

def html_to_text(html: str, max_chars: int = 15000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_chars:
        text = text[: int(max_chars * 0.7)] + " ... [TRUNCATED] ... " + text[-int(max_chars * 0.3):]
    return text

# -----------------------------
# Extraction system hint
# -----------------------------
EXTRACTION_SYSTEM_HINT = """
You are an information extractor for household utility costs from Dutch consumer pages (e.g., Nibud).
Return exactly three ExpenseItem entries for categories:
- Gas (apartment/flat value)
- Electricity (average household)
- Water (average household)

STRICT RULES for each ExpenseItem:
- category: must be exactly one of ["Gas","Electricity","Water"].
- value: must be a float greater than 0 if mentioned in text.
         If multiple values are shown (e.g., water for different household sizes),
         pick the average monthly cost across the table.
         If unsure, pick the 1-person household monthly cost.
- period: must always be non-empty.
          Use the exact text if available ("per month", "per year").
          If unclear, default to "per month".
- year: integer if explicitly stated in the text, otherwise null.
- source_url: must be the input URL.

Do not invent or guess costs.
Do not leave any field blank.
Deduplicate entries so only one per category.
"""

# -----------------------------
# Helper: ensure all categories present and enforce defaults
# -----------------------------
def ensure_all_categories(expenses: List[ExpenseItem], source_url: str, page_text: str = "") -> List[ExpenseItem]:
    required = {"Gas", "Electricity", "Water"}
    present = {e.category for e in expenses}

    for e in expenses:
        if not e.period or e.period.strip() == "":
            e.period = "per month"
        # keep LLM extracted values if >0, only fallback later
        if e.value <= 0:
            if e.category == "Water":
                # Fallback: parse water table from page text
                water_matches = re.findall(r"\b\d{1,3},\d{1,2}\b", page_text)
                if water_matches:
                    # Convert e.g. "17,50" -> 17.50
                    values = [float(m.replace(",", ".")) for m in water_matches]
                    e.value = round(sum(values) / len(values), 2)  # mean of table
                else:
                    e.value = -1.0  # truly missing
            else:
                e.value = -1.0

    missing = required - present
    for cat in missing:
        fallback_value = -1.0
        if cat == "Water":
            water_matches = re.findall(r"\b\d{1,3},\d{1,2}\b", page_text)
            if water_matches:
                values = [float(m.replace(",", ".")) for m in water_matches]
                fallback_value = round(sum(values) / len(values), 2)
        expenses.append(ExpenseItem(
            category=cat,
            value=fallback_value,
            period="per month",
            year=None,
            source_url=source_url
        ))
    return expenses

# -----------------------------
# Extract using LLM (updated to pass page_text to ensure_all_categories)
# -----------------------------
def extract_expenses_from_text(page_text: str, source_url: str) -> UtilitiesPage:
    prompt = f"{EXTRACTION_SYSTEM_HINT}\nSOURCE URL:\n{source_url}\nPAGE TEXT:\n{page_text}"
    parsed: UtilitiesPage = structured_llm.invoke(prompt)
    for e in parsed.expenses:
        e.source_url = source_url
    parsed.expenses = ensure_all_categories(parsed.expenses, source_url, page_text)
    return parsed


def dedupe_expenses(items: List[ExpenseItem]) -> List[ExpenseItem]:
    seen = set()
    out = []
    for e in items:
        key = (e.category.strip().lower(), str(e.value), e.period.strip().lower())
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out

# -----------------------------
# Hybrid orchestrator
# -----------------------------
def extract_from_inputs(
    urls: Optional[List[str]] = None,
    files: Optional[List[str]] = None,
    raw_html_blobs: Optional[List[Dict[str, str]]] = None,
    polite_delay_s: float = 2.5,
) -> List[ExpenseItem]:
    session = build_session()
    urls = urls or []
    files = files or []
    raw_html_blobs = raw_html_blobs or []
    all_expenses: List[ExpenseItem] = []

    for url in urls:
        try:
            html = fetch_html(url, session=session)
            text = html_to_text(html)
            all_expenses.extend(extract_expenses_from_text(text, source_url=url).expenses)
            time.sleep(polite_delay_s + random.random())
        except Exception as e:
            print(f"[URL Error] {url}: {e}")

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                html = f.read()
            text = html_to_text(html)
            all_expenses.extend(extract_expenses_from_text(text, source_url=f"file://{os.path.abspath(path)}").expenses)
        except Exception as e:
            print(f"[File Error] {path}: {e}")

    for blob in raw_html_blobs:
        try:
            html = blob.get("html", "")
            src = blob.get("source_url", "about:blank")
            text = html_to_text(html)
            all_expenses.extend(extract_expenses_from_text(text, source_url=src).expenses)
        except Exception as e:
            print(f"[Raw HTML Error] {src}: {e}")

    return dedupe_expenses(all_expenses)

# -----------------------------
# Runner
# -----------------------------
if __name__ == "__main__":
    URLS = [
        "https://www.nibud.nl/onderwerpen/uitgaven/kosten-energie-water/"
    ]
    FILES = []
    RAW_HTML = []

    results = extract_from_inputs(urls=URLS, files=FILES, raw_html_blobs=RAW_HTML)

    print(json.dumps([e.model_dump() for e in results], indent=2, ensure_ascii=False))

    with open("utilities_expenses.json", "w", encoding="utf-8") as f:
        json.dump([e.model_dump() for e in results], f, ensure_ascii=False, indent=4)

    print("\n✅ Saved extracted data to utilities_expenses.json")
