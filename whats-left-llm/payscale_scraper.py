#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Payscale salary scraper -> JSON
- Fetch HTML
- Flatten to text
- LLM extracts ONLY the job title (single item)
- Seniority is derived from the URL suffix (authoritative)
- Compensation (min/avg/max, currency, period) parsed from HTML percentile chart
- Output: exactly one item per page
"""

import os
import re
import json
import time
import random
import argparse
from typing import List, Optional, Literal, Dict
from collections import OrderedDict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv
load_dotenv()

from langchain.chat_models import init_chat_model  # provider-agnostic

# =========================
# 1) Schema
# =========================

Period = Literal["hourly", "daily", "weekly", "monthly", "yearly"]
Seniority = Literal["junior", "mid-level", "senior"]

class Compensation(BaseModel):
    currency: Optional[str] = None
    period: Optional[Period] = None
    min_amount: Optional[float] = None
    avg_amount: Optional[float] = None
    max_amount: Optional[float] = None

class JobPosting(BaseModel):
    position: str
    seniority: Optional[Seniority] = None
    compensation: Optional[Compensation] = None
    source_url: str
    source_site: Optional[str] = None

class JobsPage(BaseModel):
    jobs: List[JobPosting]

# =========================
# 2) LLM (position only)
# =========================

llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
structured_llm = llm.with_structured_output(JobsPage)

EXTRACTION_SYSTEM_HINT = """
You extract ONLY the job title from a Payscale salary page.

Return JSON: JobsPage { jobs: JobPosting[] }

Rules:
- Return EXACTLY one item if a clear job title exists; otherwise return zero items.
- Fill ONLY: position (job title), source_url, source_site.
- seniority and compensation MUST be left null (caller will set them).
- Do NOT return more than one item.
"""

# =========================
# 3) Networking & HTML → text
# =========================

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

def build_session(cookie_env: str = "PAYSCALE_COOKIE") -> requests.Session:
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

    cookie_str = os.environ.get(cookie_env, "").strip()
    if cookie_str:
        for part in cookie_str.split(";"):
            if "=" in part:
                name, value = part.strip().split("=", 1)
                s.cookies.set(name.strip(), value.strip())
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
# 4) Helpers (period/currency + compensation parsing + seniority from URL)
# =========================

_PERIOD_MAP = {
    "h": "hourly", "hr": "hourly", "hour": "hourly", "/ hour": "hourly", "per hour": "hourly", "hourly": "hourly",
    "d": "daily", "day": "daily", "per day": "daily", "daily": "daily",
    "w": "weekly", "wk": "weekly", "week": "weekly", "per week": "weekly", "weekly": "weekly",
    "m": "monthly", "mo": "monthly", "/ month": "monthly", "per month": "monthly", "monthly": "monthly",
    "y": "yearly", "yr": "yearly", "year": "yearly", "/ year": "yearly", "per year": "yearly",
    "annual": "yearly", "annually": "yearly", "yearly": "yearly",
}

def normalize_period(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip().lower()
    v = re.sub(r"[/\-_.]", " ", v)
    v = re.sub(r"\s+", " ", v)
    return _PERIOD_MAP.get(v, _PERIOD_MAP.get(v.replace(" per ", " "), None))

def clean_money_to_float(x: str) -> Optional[float]:
    if not x:
        return None
    x = x.replace(",", "").replace("\u00a0", " ").strip()
    if re.search(r"\d+\s*k", x, flags=re.I):
        digits = re.sub(r"[^\d.]", "", x)
        try:
            return float(digits) * 1000.0
        except:
            return None
    nums = re.findall(r"\d+(?:\.\d+)?", x)
    if not nums:
        return None
    try:
        return float(nums[0])
    except:
        return None

def parse_compensation_from_html(html: str) -> Dict[str, Optional[float]]:
    soup = BeautifulSoup(html, "html.parser")
    comp = {"currency": None, "period": "yearly", "min_amount": None, "avg_amount": None, "max_amount": None}

    low = soup.select_one(".percentile-chart__low .percentile-chart__label div:nth-of-type(2)")
    med = soup.select_one(".percentile-chart__median")
    high = soup.select_one(".percentile-chart__high .percentile-chart__label div:nth-of-type(2)")

    if low:  comp["min_amount"] = clean_money_to_float(low.get_text())
    if med:  comp["avg_amount"] = clean_money_to_float(med.get_text())
    if high: comp["max_amount"] = clean_money_to_float(high.get_text())

    page_text = soup.get_text(" ", strip=True)
    if "€" in html or "EUR" in page_text:
        comp["currency"] = "EUR"
    elif "$" in html or "USD" in page_text:
        comp["currency"] = "USD"

    placeholder = soup.select_one(".Dropdown-placeholder")
    if placeholder:
        p = normalize_period(placeholder.get_text())
        comp["period"] = p or "yearly"

    comp["period"] = normalize_period(comp["period"]) or "yearly"
    return comp

def derive_bucket_from_url(url: str) -> Optional[Seniority]:
    """
    Map Payscale experience suffix from URL to {junior, mid-level, senior}.
    Examples:
      .../Entry-Level               -> junior
      .../Early-Career              -> junior
      .../Mid-Career                -> mid-level
      .../Late-Career               -> senior
      .../Experienced               -> senior
    """
    suffix = url.strip("/").split("/")[-1].lower()
    # allow trailing IDs before the label, e.g., ".../Salary/<id>/Experienced"
    # so check also the last TWO segments
    parts = url.strip("/").split("/")
    tail = [p.lower() for p in parts[-2:]]  # e.g., ["69c7df38", "Experienced"]

    labels = {
        "entry-level": "junior",
        "early-career": "junior",
        "mid-career": "mid-level",
        "late-career": "senior",
        "experienced": "senior",
    }
    # direct match on last segment
    if suffix in labels:
        return labels[suffix]  # type: ignore
    # match on last two segments (ID + label)
    for seg in tail:
        if seg in labels:
            return labels[seg]  # type: ignore
    return None

# =========================
# 5) Extraction pipeline
# =========================

def extract_jobs_from_text(page_text: str, source_url: str, html: str) -> JobsPage:
    # 1) Ask LLM ONLY for the job title (single item)
    prompt = f"""{EXTRACTION_SYSTEM_HINT}

SOURCE URL:
{source_url}

PAGE TEXT:
{page_text}
"""
    parsed: JobsPage = structured_llm.invoke(prompt)

    # If LLM returns nothing, try to read title from DOM as fallback
    position = None
    if parsed.jobs:
        position = (parsed.jobs[0].position or "").strip() or None
    if not position:
        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.select_one("h1")
        if h1:
            position = re.sub(r"^Average\s+|\s+Salary.*$", "", h1.get_text(strip=True)) or None
    if not position:
        raise ValueError("Failed to detect job title (position).")

    # 2) Derive seniority bucket from URL (authoritative)
    bucket = derive_bucket_from_url(source_url)
    if not bucket:
        # If no suffix, we leave seniority None or choose to default; here we keep None.
        bucket = None

    # 3) Parse compensation once from HTML
    comp = parse_compensation_from_html(html)
    period = normalize_period(comp.get("period")) or "yearly"

    # 4) Build exactly ONE JobPosting
    one = JobPosting(
        position=position,
        seniority=bucket,  # may be None if base page without suffix
        compensation=Compensation(
            currency=comp.get("currency"),
            period=period,
            min_amount=comp.get("min_amount"),
            avg_amount=comp.get("avg_amount"),
            max_amount=comp.get("max_amount"),
        ),
        source_url=source_url,
        source_site="payscale",
    )

    # 5) Validate and return
    try:
        page = JobsPage.model_validate(JobsPage(jobs=[one]).model_dump())
    except ValidationError as e:
        raise e
    return page

# =========================
# 6) Orchestrator
# =========================

def extract_from_inputs(
    urls: Optional[List[str]] = None,
    polite_delay_s: float = 1.5,
) -> List[JobPosting]:
    session = build_session()
    out: List[JobPosting] = []
    for url in urls or []:
        try:
            html = fetch_html(url, session=session)
            text = html_to_text(html)
            page = extract_jobs_from_text(text, source_url=url, html=html)
            out.extend(page.jobs)
            time.sleep(polite_delay_s + random.random())
        except Exception as e:
            print(f"[Error] {url}: {e}")
    return out

# =========================
# 7) CLI
# =========================

def main():
    # Default links used only if no --url is provided
    HARDCODED_URLS = [
        "https://www.payscale.com/research/NL/Job=Data_Scientist/Salary/66c296ce/Early-Career",
        "https://www.payscale.com/research/NL/Job=Data_Scientist/Salary/176b7682/Mid-Career",
        "https://www.payscale.com/research/NL/Job=Data_Scientist/Salary/b8a6498d/Experienced",
        "https://www.payscale.com/research/NL/Job=Data_Analyst/Salary/01cd0898/Early-Career",
        "https://www.payscale.com/research/NL/Job=Data_Analyst/Salary/1e283078/Mid-Career",
        "https://www.payscale.com/research/NL/Job=Data_Analyst/Salary/69c7df38/Experienced",
        "https://www.payscale.com/research/NL/Job=Data_Engineer/Salary/4b1fe314/Early-Career",
        "https://www.payscale.com/research/NL/Job=Data_Engineer/Salary/1eadd5f9/Mid-Career",
        "https://www.payscale.com/research/NL/Job=Data_Engineer/Salary/6573bec6/Experienced",
        "https://www.payscale.com/research/NL/Job=Software_Engineer/Salary/c2c49a35/Early-Career",
        "https://www.payscale.com/research/NL/Job=Software_Engineer/Salary/35417996/Mid-Career",
        "https://www.payscale.com/research/NL/Job=Software_Engineer/Salary/0ddc8bd9/Experienced",
        "https://www.payscale.com/research/NL/Job=Front_End_Developer_%2F_Engineer/Salary/ea22a1a1/Early-Career",
        "https://www.payscale.com/research/NL/Job=Front_End_Developer_%2F_Engineer/Salary/646df80c/Mid-Career",
        "https://www.payscale.com/research/NL/Job=Front_End_Developer_%2F_Engineer/Salary/9da6bdec/Experienced",
        "https://www.payscale.com/research/NL/Job=Back_End_Developer%2F_Engineer/Salary/885c2de8/Early-Career",
        "https://www.payscale.com/research/NL/Job=Back_End_Developer%2F_Engineer/Salary/78e1afd0/Mid-Career",
        "https://www.payscale.com/research/NL/Job=Back_End_Developer%2F_Engineer/Salary/9f4dfa33/Experienced",
        "https://www.payscale.com/research/NL/Job=Development_Operations_(DevOps)_Engineer/Salary/0a254828/Early-Career",
        "https://www.payscale.com/research/NL/Job=Development_Operations_(DevOps)_Engineer/Salary/a4e3664f/Mid-Career",
        "https://www.payscale.com/research/NL/Job=Development_Operations_(DevOps)_Engineer/Salary/bf0c5f79/Experienced",
        "https://www.payscale.com/research/NL/Job=Security_Engineer/Salary/0108b7bf/Early-Career",
        "https://www.payscale.com/research/NL/Job=Security_Engineer/Salary/faa029f1/Mid-Career",
        "https://www.payscale.com/research/NL/Job=Security_Engineer/Salary/63ba72d9/Experienced"
    ]

    parser = argparse.ArgumentParser(description="Extract salary data from Payscale into JSON.")
    parser.add_argument(
        "--url",
        action="append",
        default=[],  # no default here; we'll fallback to HARDCODED_URLS if empty
        help="Payscale salary page URL (repeatable)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Write JSON to this file (optional). Prints to stdout if omitted.",
    )
    args = parser.parse_args()

    urls = args.url if args.url else HARDCODED_URLS
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
