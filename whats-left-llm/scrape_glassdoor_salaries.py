# pip install playwright
# playwright install

import os
import re
import time
import json
import random
from typing import List, Optional

from pydantic import BaseModel
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# =========================
# 1) Schema (con experience_bucket)
# =========================
class JobPosting(BaseModel):
    position: str
    seniority: Optional[str] = None
    salary: Optional[str] = None
    source_url: str
    site: str

class JobsPage(BaseModel):
    jobs: List[JobPosting]

# =========================
# 2) Utilidades pequeñas
# =========================
HEADLINE_RE = re.compile(
    r"(?i)(?:€|eur|£|\$)\s*[\d\.,]+(?:\s*[kKmM])?\s*[-–]\s*"
    r"(?:€|eur|£|\$)?\s*[\d\.,]+(?:\s*[kKmM])?\s*/\s*"
    r"(?:mnd|maand|jr|jaar|año|años|anio|year|years|yr|an)"
)


def role_from_url(url: str) -> Optional[str]:
    """
    Heurística: extrae el 'slug' del rol del path del URL de Glassdoor Salaries.
    Ej: '/Salarissen/nederland-data-scientist-salarissen-...' -> 'Data Scientist'
    """
    path = re.sub(r"%[0-9A-Fa-f]{2}", "-", url)  # muy defensivo con escapes
    path = path.lower()
    m = re.search(r"-([a-z0-9\-]+)-(?:salarissen|salaries)", path)
    if m:
        slug = m.group(1)
        return slug.replace("-", " ").title().strip()
    return None

def buckets_for_locale(locale: str) -> List[str]:
    loc = (locale or "nl-NL").lower()
    if loc.startswith("nl"):
        return ["1-3 jaar","4-6 jaar","7-9 jaar"]
    if loc.startswith("es"):
        return ["1-3 años","4-6 años","7-9 años"]
    # en-US por defecto
    return ["1-3 years","4-6 years","7-9 years"]

# =========================
# 3) Playwright helpers
# =========================
def _accept_cookies_if_any(page) -> None:
    for label in ["Akkoord","Alles accepteren","Accepteer alle","Aceptar todo","Aceptar","Accept all","Allow all","I agree"]:
        try:
            page.get_by_role("button", name=re.compile(label, re.I)).click(timeout=800)
            page.wait_for_timeout(300)
            return
        except Exception:
            pass

def _current_headline_text(page) -> Optional[str]:
    try:
        txt = page.inner_text("body", timeout=2000)
    except Exception:
        return None
    m = HEADLINE_RE.search(txt)
    return m.group(0) if m else None

def _role_from_h1(page) -> Optional[str]:
    try:
        h1 = page.locator("h1").first.inner_text(timeout=2000).strip()
        # Respaldo: intenta detectar el rol dentro del H1 si viene una frase larga
        m = re.search(r"(data scientist|machine learning engineer|ai engineer|artificial intelligence engineer)", h1, re.I)
        return (m.group(1).title() if m else h1.strip())
    except Exception:
        return None

# =========================
# 4) Scraper principal por URL
# =========================
def scrape_glassdoor_salaries_by_experience(
    url: str,
    locale: str = "nl-NL",
    headless: bool = False,                  # visible para depurar
    max_wait_s: float = 10.0,                # espera máx. por cambio de titular
    custom_buckets: Optional[List[str]] = None
) -> List[JobPosting]:

    bucket_labels = custom_buckets or buckets_for_locale(locale)
    out: List[JobPosting] = []


    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(locale=locale, viewport={"width": 1280, "height": 960})
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")

        _accept_cookies_if_any(page)

        # Posición: primero del URL, fallback al H1
        position = role_from_url(url) or _role_from_h1(page) or "Unknown Role"

        # Encuentra el combobox de experiencia
        try:
            combo = page.get_by_role("combobox").first
        except PlaywrightTimeoutError:
            combo = None

        # Titular base al cargar ("Alle jaren")
        last_headline = _current_headline_text(page)

        for label in bucket_labels:
            # Abrir y seleccionar opción
            if combo:
                try:
                    combo.click()
                except Exception:
                    # si falla, intenta scroll y reintenta
                    combo.scroll_into_view_if_needed()
                    combo.click()
            else:
                # Fallback: click en texto "Ervaring/Experiencia/Experience"
                try:
                    page.get_by_text(re.compile("Ervaring|Experiencia|Experience", re.I)).first.click()
                except Exception:
                    pass

            # click en la opción por texto
            page.get_by_role("option", name=re.compile(label, re.I)).click()

            # Esperar a que cambie el titular
            deadline = time.time() + max_wait_s
            new_headline = None
            while time.time() < deadline:
                time.sleep(0.2)
                new_headline = _current_headline_text(page)
                if new_headline and new_headline != last_headline:
                    break
            # Si no cambió, usa lo que haya (aunque sea igual)
            last_headline = new_headline or last_headline


            out.append(JobPosting(
                position=position,
                seniority=label,
                salary=last_headline,          # ← titular verde tal cual
                source_url=page.url,
                site="GLASSDOR"
            ))

        browser.close()

    return out

# =========================
# 5) Orquestador simple (URLs → Jobs)
# =========================
def extract_from_inputs(
    urls: Optional[List[str]] = None,
    polite_delay_s: float = 1.5,
    locale: str = "nl-NL",
    headless: bool = False,
    custom_buckets: Optional[List[str]] = None
) -> List[JobPosting]:
    urls = urls or []
    all_jobs: List[JobPosting] = []
    for url in urls:
        try:
            jobs = scrape_glassdoor_salaries_by_experience(
                url=url,
                locale=locale,
                headless=headless,
                custom_buckets=custom_buckets
            )
            all_jobs.extend(jobs)
            time.sleep(polite_delay_s + random.random())
        except Exception as e:
            print(f"[Error] {url}: {e}")
    return all_jobs  # (dedupe no necesario: un bucket = un registro)

# =========================
# 6) Ejemplo de uso
# =========================
if __name__ == "__main__":
    URLS = [
        "https://www.glassdoor.nl/Salarissen/nederland-data-scientist-salarissen-SRCH_IL.0,9_IN178_KO10,24.htm",
        # "https://www.glassdoor.nl/Salarissen/nederland-data-analyst-salarissen-SRCH_IL.0,9_IN178_KO10,22.htm",
        # "https://www.glassdoor.nl/Salarissen/nederland-data-engineer-salarissen-SRCH_IL.0,9_IN178_KO10,23.htm",
        # "https://www.glassdoor.nl/Salarissen/nederland-software-engineer-salarissen-SRCH_IL.0,9_IN178_KO10,27.htm",
        # "https://www.glassdoor.nl/Salarissen/nederland-cloud-engineer-salarissen-SRCH_IL.0,9_IN178_KO10,24.htm",
        # "https://www.glassdoor.nl/Salarissen/nederland-ai-engineer-salarissen-SRCH_IL.0,9_IN178_KO10,21.htm",
        # "https://www.glassdoor.nl/Salarissen/nederland-frontend-engineer-salarissen-SRCH_IL.0,9_IN178_KO10,27.htm",
        # "https://www.glassdoor.nl/Salarissen/nederland-backend-engineer-salarissen-SRCH_IL.0,9_IN178_KO10,26.htm",
        # "https://www.glassdoor.nl/Salarissen/nederland-devops-engineer-salarissen-SRCH_IL.0,9_IN178_KO10,25.htm",
        # "https://www.glassdoor.nl/Salarissen/nederland-security-engineer-salarissen-SRCH_IL.0,9_IN178_KO10,27.htm"

        # agrega más URLs aquí (50+ sin problema; va secuencial)""
    ]
    # Puedes cambiar a "es-ES" o "en-US" y automáticamente usa labels de buckets en ese idioma.
    results = extract_from_inputs(
        urls=URLS,
        locale="nl-NL",
        headless=False,                 # ventana visible para depurar
        custom_buckets=None             # o pasa tu propia lista si quieres
    )
    print(json.dumps([r.model_dump() for r in results], indent=2, ensure_ascii=False))


SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))   # .../whatsleft
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)                  # sube a .../<repo-root>
RAW_DIR      = os.path.join(PROJECT_ROOT, "raw_data")       # .../<repo-root>/raw_data
os.makedirs(RAW_DIR, exist_ok=True)                         # crea si no existe

data = [r.model_dump() for r in results]
out_path = os.path.join(RAW_DIR, f"salaray_raw_data_{int(time.time())}.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n[OK] saved to {out_path}")
