"""Parser for the Central Bank of Libya GDP statistics (bilingual PDF, 2013-2019).

The CBL publishes 'GDP Statistics 2013-2019' as a three-page bilingual PDF
(English left, Arabic right), production approach by economic sector, in millions
of LYD:

  p1  Gross Domestic Product by Economic Sectors at Constant Prices  -> level, constant (base 2013)
  p2  Gross Domestic Product by Economic Sector (current prices)      -> level, current
  p3  Gross Domestic Product Deflator (2013 = 100)                    -> deflator

Each table: a header row 'No. Economic Sectors 2019 2018 … 2013' (years DESCENDING),
then one sector per row — a letter code, the English label, seven yearly figures,
then the Arabic label (ignored). We read the seven numbers per row and map them to
2019…2013. Verified: the mining sector dominates (constant 2013 = 55,673.4 m LYD)
and the deflator is 100.0 in the 2013 base year for every sector. Units million LYD
(levels), index (deflator, 2013=100). Everything as published; nothing derived.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]

_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_CODE_RE = re.compile(r"^([A-Z]{1,2}|\d{1,2})\s+")


def _spec(text: str):
    t = text.lower()
    if "deflator" in t:
        return ("deflator", "not_applicable", "2013", "index")
    if "constant" in t:
        return ("level", "constant", "2013", "million LYD")
    if "gross domestic product by economic sector" in t:
        return ("level", "current", "", "million LYD")
    return None


def parse(pdf_path: str) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            spec = _spec(text)
            if spec is None:
                continue
            measure, basis, base, unit = spec
            years = None
            for line in text.split("\n"):
                clean = re.sub(r"[^\x00-\x7f]+", " ", line)      # drop Arabic
                clean = re.sub(r"\s+", " ", clean).strip()
                yrs = re.findall(r"\b(20\d\d)\b", clean)
                if len(yrs) >= 5 and years is None:
                    years = [int(y) for y in yrs]
                    continue
                if years is None:
                    continue
                m = _CODE_RE.match(clean)
                code = m.group(1) if m else ""
                body = clean[m.end():] if m else clean
                nums = _NUM_RE.findall(body)
                if len(nums) < len(years):
                    continue
                label = body[:body.find(nums[0])].strip(" .:-")
                if not re.search(r"[A-Za-z]{3}", label):
                    continue
                low = label.lower()
                approach = "aggregate" if ("gross domestic product" in low
                                           or low.startswith("total")
                                           or low == "gdp") else "production"
                vals = nums[-len(years):]
                for year, tok in zip(years, vals):
                    try:
                        v = float(tok.replace(",", ""))
                    except ValueError:
                        continue
                    rows.append({
                        "approach": approach, "category": label,
                        "category_group": "", "series_code": code,
                        "geography": "National", "period": str(year),
                        "frequency": "annual", "price_basis": basis,
                        "seasonal_adjustment": "nsa", "measure": measure,
                        "value": v, "unit": unit, "base_period": base,
                    })
    if not rows:
        raise ValueError("no GDP rows parsed from CBL Libya PDF")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "series_code", "period", "measure", "price_basis"])
