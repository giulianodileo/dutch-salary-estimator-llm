#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# pip install -qU langchain-community



"""
Rental price scraper -> JSON
- Load PDF (via LangChain PDFPlumberLoader)
- Flatten to text
- LLM extracts rental figures for Amsterdam, Rotterdam, The Hague
- Output: one item per (city, accommodation) combination
"""

# ========================= 0. Import Libraries ========================= #


import os
import re
import json
import argparse
from typing import List, Optional, Literal
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

from langchain_community.document_loaders import PDFPlumberLoader
from langchain.chat_models import init_chat_model

load_dotenv()


# ========================= 1. Schema ========================= #


Period = Literal["monthly"]
City = Literal["Amsterdam", "Rotterdam", "The Hague"]
Accommodation = Literal["Apartment", "Room", "Studio"]

class RentalData(BaseModel):
    city: City
    accommodation: Accommodation
    period: Period = "monthly"
    currency: str = "EUR"
    current_quarter: Optional[float] = None
    previous_quarter: Optional[float] = None
    last_year: Optional[float] = None
    change_vs_prev: Optional[float] = None
    change_vs_year: Optional[float] = None

class RentalsPage(BaseModel):
    rentals: List[RentalData]


# ========================= 2. LLM Setup ========================= #


llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
structured_llm = llm.with_structured_output(RentalsPage)

EXTRACTION_PROMPT = """
You extract rental data from a PDF report about Amsterdam, Rotterdam, and The Hague.

Return JSON: RentalsPage { rentals: RentalData[] }

Rules:
- One record per (city, accommodation type).
- Extract numeric values for current_quarter, previous_quarter, last_year (strip € and commas).
- Extract percentage changes (vs previous quarter, vs last year).
- Assume currency = EUR, period = monthly.
- Only include cities: Amsterdam, Rotterdam, The Hague.
- If a value is missing, leave it null.
"""


# ========================= 3. PDF to Text ========================= #


def pdf_to_text(path: str) -> str:
    loader = PDFPlumberLoader(path)
    docs = loader.load()
    text = "\n".join(doc.page_content for doc in docs if doc.page_content)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ========================= 4. Extraction Pipeline ========================= #


def extract_rentals_from_pdf(path: str) -> RentalsPage:
    text = pdf_to_text(path)
    prompt = f"{EXTRACTION_PROMPT}\n\nSOURCE FILE:\n{path}\n\nREPORT TEXT:\n{text}"
    parsed: RentalsPage = structured_llm.invoke(prompt)
    try:
        return RentalsPage.model_validate(parsed.model_dump())
    except ValidationError as e:
        raise e


# ========================= 5. CLI ========================= #


def main():
    parser = argparse.ArgumentParser(description="Extract rental data from PDF into JSON.")
    parser.add_argument("--file", required=True, help="PDF file with rental figures")
    parser.add_argument("--output", type=str, default="", help="Output JSON file (optional)")
    args = parser.parse_args()

    rentals = extract_rentals_from_pdf(args.file)
    payload = json.dumps([r.model_dump() for r in rentals.rentals], indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"Wrote {len(rentals.rentals)} records to {args.output}")
    else:
        print(payload)

if __name__ == "__main__":
    main()
