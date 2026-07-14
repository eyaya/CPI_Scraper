"""Parser for the Zambia ZamStats 'The Monthly' bulletin PDF (Tier 3).

ZamStats publishes a monthly statistical bulletin; its 'Table 1.2: Consumer Price
Index by Division' is a wide monthly time series (from 2022) with the divisions
as COLUMNS and the months as ROWS:

  Period          | All Items | Food … | Alcoholic … | Clothing … | …
  Weight:         | 1 000.00  | 534.85 | 15.21       | 80.78      | …
  2023  Jan       | 377.25    | 408.33 | 280.64      | 329.05     | …

Divisions are COICOP-1999 (12 + All items), in a non-standard column order, so we
map each column to a code by a keyword in its header rather than by position (a
header wrap even leaves a phantom empty column, which the keyword map skips). The
year sits in the first column of each January row and is carried forward. We emit
the index level for every month. Base as published by ZamStats.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

# (code, label, keyword tested — in order, so 'food and non' wins before 'alcoholic')
_DIVS = [
    ("00", "All items", "all items"),
    ("01", "Food and non-alcoholic beverages", "food and non"),
    ("02", "Alcoholic beverages and tobacco", "alcoholic"),
    ("03", "Clothing and footwear", "clothing"),
    ("04", "Housing, water, electricity, gas and other fuels", "housing"),
    ("05", "Furnishings, household equipment and routine maintenance", "furnishing"),
    ("06", "Health", "health"),
    ("07", "Transport", "transport"),
    ("08", "Communication", "communication"),
    ("09", "Recreation and culture", "recreation"),
    ("10", "Education services", "education"),
    ("11", "Restaurants and hotels", "restaurant"),
    ("12", "Miscellaneous goods and services", "miscellaneous"),
]
_MONTHS = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
           "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
           "nov": "11", "dec": "12"}


def _code(header: str) -> tuple[str, str] | None:
    h = re.sub(r"\s+", " ", header.replace("\n", " ")).lower()
    for code, label, kw in _DIVS:
        if kw in h:
            return code, label
    return None


def _value(cell) -> float | None:
    if isinstance(cell, (int, float)):
        return float(cell)
    if isinstance(cell, str) and re.fullmatch(r"[\d ]+\.\d+", cell.strip()):
        return float(cell.strip().replace(" ", ""))
    return None


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for tb in page.extract_tables():
                flat = " ".join(str(c) for r in tb for c in r if c).lower()
                if not ("weight" in flat and "all items" in flat and "clothing" in flat):
                    continue
                hi = next((i for i, r in enumerate(tb)
                           if any(isinstance(c, str) and "all items" in c.lower() for c in r)), None)
                if hi is None:
                    continue
                col_map = {}
                for j, c in enumerate(tb[hi]):
                    if isinstance(c, str) and (cl := _code(c)):
                        col_map.setdefault(cl[0], (j, cl[1]))
                if len(col_map) < 13:
                    continue

                records, year = [], None
                for r in tb[hi + 1:]:
                    y = str(r[0]).strip() if r and r[0] else ""
                    if re.fullmatch(r"\d{4}", y):
                        year = y
                    mon = (str(r[1]).strip().lower()[:3] if len(r) > 1 and r[1] else "")
                    if year is None or mon not in _MONTHS:
                        continue
                    period = f"{year}-{_MONTHS[mon]}"
                    for code, (j, label) in col_map.items():
                        v = _value(r[j] if j < len(r) else None)
                        if v is not None:
                            records.append((code, label, period, round(v, 4)))

                if len({c for c, *_ in records if c != "00"}) >= 12:
                    out = pd.DataFrame.from_records(
                        records, columns=["coicop_code", "coicop_label", "period", "value"])
                    out = out.drop_duplicates(["coicop_code", "period"])
                    out["geography"] = "National"
                    out["measure"] = "index"
                    out["unit"] = "Index"
                    out["base_period"] = ""
                    out["frequency"] = "monthly"
                    return out

    raise ValueError("Zambia 'CPI by Division' table not found in bulletin")
