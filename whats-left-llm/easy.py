# # --- add to requirements if you haven't ---
# # pip install -qU requests beautifulsoup4 pydantic langchain langchain-core "langchain[google-genai]"

import os
import time
import json
import re
import math
import random
from typing import List, Optional, Dict, Iterable, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError

from langchain.chat_models import init_chat_model

# # ----- SCHEMA (unchanged) -----
class JobPosting(BaseModel):
    position: str
    seniority: Optional[str] = None
    salary: Optional[str] = None
    source_url: str

class JobsPage(BaseModel):
    jobs: List[JobPosting]

llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
structured_llm = llm.with_structured_output(JobsPage)

# # ----- SESSION + RETRIES + HEADERS + OPTIONAL COOKIES -----
DEFAULT_USER_AGENTS = [
#     # rotate a few realistic desktop UA strings
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

def build_session(cookies_str_env: str = "GLASSDOOR_COOKIE") -> requests.Session:
    s = requests.Session()
    # Retries for transient failures (NOT for 403 usually, but helpful for 429/5xx)
    retries = Retry(
        total=5,
        backoff_factor=1.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD", "OPTIONS"]
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))

    # Rotate UA per session build
    s.headers.update({
        **BASE_HEADERS,
        "User-Agent": random.choice(DEFAULT_USER_AGENTS),
        "Upgrade-Insecure-Requests": "1",
    })

    # Optional cookie injection (only if you have permission)
    cookie_str = os.environ.get(cookies_str_env, "").strip()
    if cookie_str:
        # Accept "name=value; name2=value2" format pasted from browser
        for part in cookie_str.split(";"):
            if "=" in part:
                name, value = part.strip().split("=", 1)
                s.cookies.set(name.strip(), value.strip(), domain=".glassdoor.com")
    return s

# ----- FETCH with graceful 403 handling -----
def fetch_html(url: str, session: Optional[requests.Session] = None, timeout: int = 20) -> str:
    sess = session or build_session()
    r = sess.get(url, timeout=timeout)
    if r.status_code == 403:
        # Provide a helpful hint and let caller decide to switch to offline/manual mode
        raise PermissionError(
            f"403 Forbidden on {url}. This page likely requires login/JS or is blocking bots. "
            f"Try setting an authenticated cookie (env GLASSDOOR_COOKIE), slowing down, "
            f"or using manual/offline HTML input."
        )
    r.raise_for_status()
    return r.text

def html_to_text(html: str, max_chars: int = 15000) -> str:
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

EXTRACTION_SYSTEM_HINT = """
You extract job postings from job-listing pages (e.g., Glassdoor, Indeed).
Return a structured list of jobs with fields:
- position (string, required)
- seniority (string, optional; Intern/Junior/Mid/Senior/Lead/Principal/Staff)
- salary (string, optional; copy exactly as shown)
Guidelines:
- Prefer visible job titles.
- If a search/results page lists multiple jobs, return multiple.
- If salary absent, set null. Do not invent.
- Keep salary text EXACTLY as written (e.g., '€65,000–€80,000 a year + bonus').
- Deduplicate where possible.
"""

def extract_jobs_from_text(page_text: str, source_url: str) -> JobsPage:
    prompt = f"""{EXTRACTION_SYSTEM_HINT}

SOURCE URL:
{source_url}

PAGE TEXT:
{page_text}
"""
    parsed: JobsPage = structured_llm.invoke(prompt)
    for job in parsed.jobs:
        job.source_url = source_url
    return parsed

def dedupe_jobs(jobs: List[JobPosting]) -> List[JobPosting]:
    seen = set()
    out = []
    for j in jobs:
        key = (
            j.position.strip().lower(),
            (j.seniority or "").strip().lower(),
            (j.salary or "").strip().lower(),
            j.source_url,
        )
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out

# ----- NEW: hybrid orchestrator that supports URLs, local files, or raw HTML -----
def extract_from_inputs(
    urls: Optional[List[str]] = None,
    files: Optional[List[str]] = None,
    raw_html_blobs: Optional[List[Dict[str, str]]] = None,  # [{"html": "...", "source_url": "..."}]
    polite_delay_s: float = 2.5,
) -> List[JobPosting]:
    session = build_session()
    all_jobs: List[JobPosting] = []
    urls = urls or []
    files = files or []
    raw_html_blobs = raw_html_blobs or []

    # 1) URLs (online)
    for url in urls:
        try:
            html = fetch_html(url, session=session)
            txt = html_to_text(html)
            all_jobs.extend(extract_jobs_from_text(txt, source_url=url).jobs)
            time.sleep(polite_delay_s + random.random())  # small jitter
        except PermissionError as e:
            print(f"[403 Blocked] {e}")
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", "?")
            print(f"[HTTP {code}] {url}: {e}")
        except Exception as e:
            print(f"[Error] {url}: {e}")

    # 2) Local files (offline/manual mode)
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                html = f.read()
            txt = html_to_text(html)
            all_jobs.extend(extract_jobs_from_text(txt, source_url=f"file://{os.path.abspath(path)}").jobs)
        except Exception as e:
            print(f"[File Error] {path}: {e}")

    # 3) Raw HTML strings
    for blob in raw_html_blobs:
        try:
            html = blob.get("html", "")
            src = blob.get("source_url", "about:blank")
            txt = html_to_text(html)
            all_jobs.extend(extract_jobs_from_text(txt, source_url=src).jobs)
        except Exception as e:
            print(f"[Raw HTML Error] {blob.get('source_url', 'about:blank')}: {e}")

    return dedupe_jobs(all_jobs)

if __name__ == "__main__":
    # Choose ONE or mix:
    URLS = [
        "https://www.glassdoor.nl/Salarissen/nederland-data-scientist-salarissen-SRCH_IL.0,9_IN178_KO10,24.htm",

    ]

    FILES = [
        # "saved_pages/glassdoor_salaries_generative_ai_engineer.html",
    ]

    RAW_HTML = [
        # {"html": "<html>...your pasted HTML...</html>", "source_url": "manual://pasted-glassdoor-page"},
    ]

    results = extract_from_inputs(urls=URLS, files=FILES, raw_html_blobs=RAW_HTML)
    print(json.dumps([r.model_dump() for r in results], indent=2, ensure_ascii=False))
