#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Job extractor with seniority inference from years of experience.
- BeautifulSoup -> LLM structured output -> Pydantic validation
- Canonical compensation.period: hourly/daily/weekly/monthly/yearly
- Canonical seniority: Intern/Junior/Mid/Senior/Lead/Principal/Staff
- Parses "years of experience" strings like "1-3 jaar", "7–9 years", etc.
"""

import os
import re
import json
import math
import time
import random
import argparse
from typing import List, Optional, Literal, Dict, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError

from langchain.chat_models import init_chat_model  # provider-agnostic

# =========================
# 1) Schema
# =========================

Period = Literal["hourly", "daily", "weekly", "monthly", "yearly"]
Seniority = Literal["Intern","Junior","Mid","Senior","Lead","Principal","Staff"]

class Compensation(BaseModel):
    currency: Optional[str] = Field(None, description="ISO (e.g., EUR, USD) when inferable")
    period: Optional[Period] = Field(None, description="Canonical pay period")
    min_amount: Optional[float] = Field(None, description="Lower bound if range present")
    max_amount: Optional[float] = Field(None, description="Upper bound if range present")

class JobPosting(BaseModel):
    # Core
    position: str
    seniority: Optional[Seniority] = None
    company: Optional[str] = None
    location: Optional[str] = None

    # Format & logistics
    employment_type: Optional[Literal["full-time","part-time","contract","internship","temporary"]] = None
    work_mode: Optional[Literal["onsite","remote","hybrid"]] = None

    # Compensation (raw + normalized)
    salary_raw: Optional[str] = None
    compensation: Optional[Compensation] = None

    # Experience (raw + parsed)
    experience_years_raw: Optional[str] = Field(
        None, description="Experience requirement as text (e.g., '1-3 jaar', '5+ years')"
    )
    experience_min_years: Optional[float] = None
    experience_max_years: Optional[float] = None

    # Extras
    posted_date: Optional[str] = Field(None, description="As shown (e.g., '2025-08-15' or '3 days ago')")
    description_snippet: Optional[str] = None

    # Provenance
    source_url: str
    source_site: Optional[str] = None

class JobsPage(BaseModel):
    jobs: List[JobPosting]


# =========================
# 2) LLM (structured output)
# =========================

llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
structured_llm = llm.with_structured_output(JobsPage)

EXTRACTION_SYSTEM_HINT = """
You extract job postings from job-listing pages (e.g., Glassdoor, Indeed, company career pages).

Return JSON matching the schema:
JobsPage { jobs: JobPosting[] }

JobPosting fields (key ones):
- position (required)
- seniority (canonical; MUST be one of: Intern, Junior, Mid, Senior, Lead, Principal, Staff)
- company, location
- employment_type (one of: full-time, part-time, contract, internship, temporary)
- work_mode (one of: onsite, remote, hybrid)
- salary_raw (copy exact text)
- compensation { currency (ISO like EUR, USD), period (hourly/daily/weekly/monthly/yearly), min_amount, max_amount }
- experience_years_raw (copy exact text like '1-3 jaar', '5+ years')
- experience_min_years / experience_max_years (numeric if inferable)
- posted_date, description_snippet (~200 chars)
- source_url (required), source_site

STRICT rules:
- seniority MUST be one of: Intern, Junior, Mid, Senior, Lead, Principal, Staff. If the page lists experience ranges like '1-3 jaar', ALSO fill experience_years_raw and numeric min/max; then choose a canonical seniority that best matches.
- salary_raw MUST be copied EXACTLY from the page (no edits).
- compensation.period MUST be one of: hourly, daily, weekly, monthly, yearly (lowercase). If unclear, set null.
- Do NOT invent currency or salary. Be conservative.
- Prefer page-visible titles and companies. Deduplicate obvious duplicates.
- Infer source_site from the domain if obvious (e.g., 'glassdoor', 'indeed').
"""


# =========================
# 3) Networking & parsing
# =========================

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}

def build_session(cookie_env: str = "GLASSDOOR_COOKIE") -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=4,
        backoff_factor=1.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.headers.update({**BASE_HEADERS, "User-Agent": random.choice(DEFAULT_USER_AGENTS)})

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
    if r.status_code == 403:
        raise PermissionError(
            f"403 Forbidden on {url}. Use authenticated cookies (env GLASSDOOR_COOKIE) or offline/manual HTML."
        )
    r.raise_for_status()
    return r.text

def html_to_text(html: str, max_chars: int = 16000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_chars:
        head = text[: int(max_chars * 0.7)]
        tail = text[-int(max_chars * 0.3):]
        text = head + " ... [TRUNCATED] ... " + tail
    return text


# =========================
# 4) Normalization helpers
# =========================

# Period normalization (unchanged)
_PERIOD_MAP = {
    "h": "hourly", "hr": "hourly", "hour": "hourly", "hourly": "hourly", "per hour": "hourly",
    "d": "daily", "day": "daily", "daily": "daily", "per day": "daily",
    "w": "weekly", "wk": "weekly", "week": "weekly", "weekly": "weekly", "per week": "weekly",
    "m": "monthly", "mo": "monthly", "mon": "monthly", "month": "monthly", "monthly": "monthly", "per month": "monthly",
    "y": "yearly", "yr": "yearly", "year": "yearly", "annual": "yearly", "annually": "yearly",
    "yearly": "yearly", "per year": "yearly", "p.a.": "yearly", "pa": "yearly",
}

def normalize_period(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip().lower()
    v = re.sub(r"[/\-_.]", " ", v)
    v = re.sub(r"\s+", " ", v).strip()
    return _PERIOD_MAP.get(v, _PERIOD_MAP.get(v.replace(" per ", " "), None))

def normalize_currency(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    r = raw.upper()
    if "EUR" in r or "€" in r:
        return "EUR"
    if "USD" in r or "$" in r:
        return "USD"
    if "GBP" in r or "£" in r:
        return "GBP"
    if "AUD" in r:
        return "AUD"
    if "CAD" in r:
        return "CAD"
    return None

# --- Experience parsing & seniority inference ---

# Matches patterns like:
#  "1-3 jaar", "7–9 years", "5 + years", "3+ jaar", "min. 2 years", "0-1 jaar"
_EXPERIENCE_RE = re.compile(
    r"(?P<min>\d+(\.\d+)?)\s*[-–to]{0,3}\s*(?P<max>\d+(\.\d+)?)?\s*(\+)?\s*(jaar|years|year|yr|yrs|jaren|exp|experience)?",
    re.IGNORECASE,
)

def parse_experience_range(raw: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    if not raw:
        return (None, None)
    m = _EXPERIENCE_RE.search(raw)
    if not m:
        return (None, None)
    gmin = m.group("min")
    gmax = m.group("max")
    plus = "+" in raw
    min_y = float(gmin) if gmin else None
    max_y = float(gmax) if gmax else None
    # Handle "3+" → min=3, max=None
    if plus and min_y is not None and max_y is None:
        return (min_y, None)
    return (min_y, max_y)

def infer_seniority_from_years(min_y: Optional[float], max_y: Optional[float]) -> Optional[Seniority]:
    """
    Transparent thresholds (tweak as you like):
      < 1           -> Intern
      1–2.9         -> Junior
      3–4.9         -> Mid
      5–7.9         -> Senior
      8–10.9        -> Lead
      >= 11         -> Principal
    (If only min is present, use it; if only max is present, use it; else use midpoint.)
    """
    if min_y is None and max_y is None:
        return None
    if min_y is not None and max_y is None:
        v = min_y
    elif min_y is None and max_y is not None:
        v = max_y
    else:
        v = (min_y + max_y) / 2.0

    if v < 1:
        return "Intern"
    if 1 <= v < 3:
        return "Junior"
    if 3 <= v < 5:
        return "Mid"
    if 5 <= v < 8:
        return "Senior"
    if 8 <= v < 11:
        return "Lead"
    return "Principal"

def is_canonical_seniority(value: Optional[str]) -> bool:
    if not value:
        return False
    return value in {"Intern","Junior","Mid","Senior","Lead","Principal","Staff"}


# =========================
# 5) Extraction pipeline
# =========================

def extract_jobs_from_text(page_text: str, source_url: str) -> JobsPage:
    prompt = f"""{EXTRACTION_SYSTEM_HINT}

SOURCE URL:
{source_url}

PAGE TEXT:
{page_text}
"""
    parsed: JobsPage = structured_llm.invoke(prompt)

    # Ensure source_url & source_site
    try:
        domain = re.search(r"https?://([^/]+)/?", source_url).group(1).lower()
    except Exception:
        domain = None
    site = None
    if domain:
        if "glassdoor" in domain:
            site = "glassdoor"
        elif "indeed" in domain:
            site = "indeed"
        else:
            site = domain.split(":")[0]

    for job in parsed.jobs:
        job.source_url = source_url
        job.source_site = job.source_site or site

    parsed = post_validate_and_normalize(parsed)

    # Re-validate after normalization; drop any residual invalid entries
    try:
        parsed = JobsPage.model_validate(parsed.model_dump())
    except ValidationError:
        cleaned = []
        for job in parsed.jobs:
            try:
                cleaned.append(JobPosting.model_validate(job.model_dump()))
            except ValidationError:
                pass
        parsed = JobsPage(jobs=cleaned)
    return parsed

def post_validate_and_normalize(page: JobsPage) -> JobsPage:
    for j in page.jobs:
        # Compensation normalization
        if j.compensation:
            j.compensation.period = normalize_period(j.compensation.period)
            if not j.compensation.currency and j.salary_raw:
                j.compensation.currency = normalize_currency(j.salary_raw)

        # ---- Experience parsing & seniority inference ----
        # If seniority is non-canonical (e.g., '4-6 jaar'), try to parse experience & infer.
        needs_infer = not is_canonical_seniority(j.seniority)

        # Parse experience from either experience_years_raw (preferred) or the non-canonical seniority text
        raw_exp = j.experience_years_raw or (j.seniority if needs_infer else None)
        min_y, max_y = parse_experience_range(raw_exp)

        # Backfill numeric fields
        if (min_y is not None or max_y is not None):
            j.experience_min_years = j.experience_min_years or min_y
            j.experience_max_years = j.experience_max_years or max_y
            if j.experience_years_raw is None and raw_exp:
                j.experience_years_raw = raw_exp

        # Infer canonical seniority if needed
        if needs_infer and (min_y is not None or max_y is not None):
            inferred = infer_seniority_from_years(min_y, max_y)
            j.seniority = inferred

        # If still non-canonical, null it out (avoid validation errors)
        if not is_canonical_seniority(j.seniority):
            j.seniority = None

    return page

def dedupe_jobs(jobs: List[JobPosting]) -> List[JobPosting]:
    seen = set()
    out = []
    for j in jobs:
        key = (
            j.position.strip().lower(),
            (j.company or "").strip().lower(),
            (j.location or "").strip().lower(),
            (j.seniority or "").strip().lower(),
            (j.salary_raw or "").strip().lower(),
            j.source_url,
        )
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


# =========================
# 6) Orchestrator (URLs, files, raw HTML)
# =========================

def html_to_text_from_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    return html_to_text(html)

def extract_from_inputs(
    urls: Optional[List[str]] = None,
    files: Optional[List[str]] = None,
    raw_html_blobs: Optional[List[Dict[str, str]]] = None,
    polite_delay_s: float = 2.5,
) -> List[JobPosting]:
    session = build_session()
    all_jobs: List[JobPosting] = []

    # URLs
    for url in urls or []:
        try:
            html = fetch_html(url, session=session)
            text = html_to_text(html)
            page = extract_jobs_from_text(text, source_url=url)
            all_jobs.extend(page.jobs)
            time.sleep(polite_delay_s + random.random())
        except PermissionError as e:
            print(f"[403 Blocked] {e}")
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", "?")
            print(f"[HTTP {code}] {url}: {e}")
        except Exception as e:
            print(f"[Error] {url}: {e}")

    # Files
    for path in files or []:
        try:
            txt = html_to_text_from_file(path)
            page = extract_jobs_from_text(txt, source_url=f"file://{os.path.abspath(path)}")
            all_jobs.extend(page.jobs)
        except Exception as e:
            print(f"[File Error] {path}: {e}")

    # Raw HTML blobs
    for blob in raw_html_blobs or []:
        try:
            html = blob.get("html", "")
            src = blob.get("source_url", "about:blank")
            txt = html_to_text(html)
            page = extract_jobs_from_text(txt, source_url=src)
            all_jobs.extend(page.jobs)
        except Exception as e:
            print(f"[Raw HTML Error] {blob.get('source_url', 'about:blank')}: {e}")

    return dedupe_jobs(all_jobs)


# =========================
# 7) CLI
# =========================

def main():
    parser = argparse.ArgumentParser(description="Extract structured jobs from URLs, files, or raw HTML.")
    parser.add_argument("--url", action="append", default=["https://www.glassdoor.nl/Salaries/amsterdam-netherlands-artificial-intelligence-engineer-salary-SRCH_IL.0,21_IM1112_KO22,54.htm?countryRedirect=true"], help="Job page URL (repeatable)")
    parser.add_argument("--file", action="append", default=[], help="Saved HTML file (repeatable)")
    parser.add_argument("--demo", action="store_true", help="Run a built-in RAW_HTML demo")
    args = parser.parse_args()

    RAW_HTML = []
    if args.demo:
        RAW_HTML = [{
            "source_url": "manual://demo",
            "html": """
            <html><body>
              <h2>Senior Generative AI Engineer</h2>
              <div>Company: SynthLabs</div>
              <div>Location: Amsterdam, NL</div>
              <div>Experience: 5-7 years</div>
              <div>Compensation: €85,000–€110,000 per year + bonus</div>
              <p>We build LLM features. Remote-friendly hybrid.</p>

              <h2>ML Engineer (LLMs)</h2>
              <div>Company: NeoAI</div>
              <div>Location: Rotterdam, NL</div>
              <div>Ervaring: 1-3 jaar</div>
              <div>Salary: €7,000 per month</div>
              <p>Onsite role. Model training and eval. Full-time.</p>

              <h2>AI Intern</h2>
              <div>Company: StartIQ</div>
              <div>Location: Utrecht, NL</div>
              <div>Experience: 0-1 year</div>
              <div>Stipend: €15 per hour</div>
              <p>Great for students. Onsite or hybrid.</p>
            </body></html>
            """
        }]

    results = extract_from_inputs(urls=args.url, files=args.file, raw_html_blobs=RAW_HTML)
    print(json.dumps([r.model_dump() for r in results], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
