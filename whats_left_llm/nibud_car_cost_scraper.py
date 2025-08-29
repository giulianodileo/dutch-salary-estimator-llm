#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Nibud Car Costs Scraper -> JSON
- Fetch HTML
- Parse "Cost of a car per month" table
- Extract fixed + variable costs per class
- Output JSON structured per car class
"""

import os
import re
import json
import time
import random
import argparse
from typing import List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

from langchain.chat_models import init_chat_model  # provider-agnostic

# =========================
# 1) Schema
# =========================

class FixedCosts(BaseModel):
    total: float
    depreciation_time: float
    insurance: float
    motor_vehicle_tax: float
    maintenance: float

class VariableCosts(BaseModel):
    total: float
    depreciation_kms: float
    maintenance_and_repair: float
    fuel: float

class CarCost(BaseModel):
    class_name: str
    fixed_costs: FixedCosts
    variable_costs: VariableCosts
    total_per_month: float
    average_km_per_year: int

class CarCostsPage(BaseModel):
    source_url: str
    currency: str
    period: str
    data: List[CarCost]

# =========================
# 2) LLM (optional fallback)
# =========================

llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
structured_llm = llm.with_structured_output(CarCostsPage)

EXTRACTION_SYSTEM_HINT = """
You extract ONLY the Nibud car costs table.

Return JSON: CarCostsPage { data: CarCost[] }

Rules:
- Each car class must appear exactly once (mini, compact, small_middle, middle).
- Extract fixed and variable cost rows and totals.
- Fill: class_name, fixed_costs, variable_costs, totals, km/year, km prices.
- currency = EUR, period = monthly.
- If table parsing fails, return an empty array.
"""

# =========================
# 3) Networking & HTML → text
# =========================

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

def build_session(cookie_env: str = "NIBUD_COOKIE") -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=4,
        backoff_factor=1.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.headers.update({"User-Agent": random.choice(DEFAULT_USER_AGENTS)})
    return s

def fetch_html(url: str, session: Optional[requests.Session] = None, timeout: int = 25) -> str:
    sess = session or build_session()
    r = sess.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text

def html_to_text(html: str, max_chars: int = 16000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))
    if len(text) > max_chars:
        head = text[: int(max_chars * 0.7)]
        tail = text[-int(max_chars * 0.3):]
        text = head + " ... [TRUNCATED] ... " + tail
    return text

# =========================
# 4) Parsing Helpers
# =========================

def clean_money(x: str) -> float:
    if not x:
        return 0.0
    x = x.replace("€", "").replace(",", ".").replace("\xa0", "").strip()
    try:
        return float(x)
    except:
        return 0.0

def parse_table_from_html(html: str, url: str) -> CarCostsPage:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        raise ValueError("No table found.")

    headers = [th.get_text(strip=True) for th in table.find("thead").find_all("th")][1:]
    rows = [[td.get_text(strip=True) for td in tr.find_all("td")] for tr in table.find("tbody").find_all("tr")]

    # organize per class
    out = []
    for i, h in enumerate(headers):
        # map row indices -> fields
        fc = FixedCosts(
            total=clean_money(rows[0][i]),
            depreciation_time=clean_money(rows[1][i]),
            insurance=clean_money(rows[2][i]),
            motor_vehicle_tax=clean_money(rows[3][i]),
            maintenance=clean_money(rows[4][i]),
        )
        vc = VariableCosts(
            total=clean_money(rows[6][i]),
            depreciation_kms=clean_money(rows[7][i]),
            maintenance_and_repair=clean_money(rows[8][i]),
            fuel=clean_money(rows[9][i]),
        )
        cost = CarCost(
            class_name=h.lower().replace(" ", "_"),
            fixed_costs=fc,
            variable_costs=vc,
            total_per_month=clean_money(rows[11][i]),
            average_km_per_year=int(re.sub(r"\D", "", rows[12][i])),
        )
        out.append(cost)

    page = CarCostsPage(
        source_url=url,
        currency="EUR",
        period="monthly",
        data=out
    )
    return page

# =========================
# 5) Extraction Pipeline
# =========================

def extract_car_costs(url: str, session: Optional[requests.Session] = None) -> CarCostsPage:
    html = fetch_html(url, session=session)
    text = html_to_text(html)
    try:
        page = parse_table_from_html(html, url)
    except Exception as e:
        # fallback to LLM extraction if parsing fails
        prompt = f"""{EXTRACTION_SYSTEM_HINT}

SOURCE URL:
{url}

PAGE TEXT:
{text}
"""
        page: CarCostsPage = structured_llm.invoke(prompt)
    return page

# =========================
# 6) Orchestrator
# =========================

def extract_from_inputs(
    urls: Optional[List[str]] = None,
    polite_delay_s: float = 1.5,
) -> List[CarCostsPage]:
    session = build_session()
    out: List[CarCostsPage] = []
    for url in urls or []:
        try:
            page = extract_car_costs(url, session=session)
            out.append(page)
            time.sleep(polite_delay_s + random.random())
        except Exception as e:
            print(f"[Error] {url}: {e}")
    return out

# =========================
# 7) CLI
# =========================

def main():
    DEFAULT_URL = "https://www.nibud.nl/onderwerpen/uitgaven/autokosten"

    parser = argparse.ArgumentParser(description="Extract car costs from Nibud into JSON.")
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="Nibud car costs page URL (repeatable)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Write JSON to this file (optional). Prints to stdout if omitted.",
    )
    args = parser.parse_args()

    urls = args.url if args.url else [DEFAULT_URL]
    results = extract_from_inputs(urls=urls)

    payload = json.dumps([r.model_dump() for r in results], indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"Wrote {len(results)} records to {args.output}")
    else:
        print(payload)

if __name__ == "__main__":
    main()
