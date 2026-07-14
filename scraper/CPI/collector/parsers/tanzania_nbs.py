"""Parser for the Tanzania NBS monthly NCPI release PDF (Tier 3).

NBS publishes the National CPI (COICOP-2018, base Jan–Dec 2020 = 100) as a
monthly PDF. Its 'Main Groups' table shows, per division, the index for three
months (year-ago, previous, current) plus 1-/12-month % changes:

  S/N | Main Groups | Weight | Febr. 2025 | Jan. 2026 | Febr. 2026 | 1M% | 12M%
  1..13 | Food … / Alcoholic … / …          (13 divisions, stacked in one cell)
  TOTAL – ALL ITEMS | 100.0 | 118.28 | 121.41 | 122.01 | …

pdfplumber returns the 13 division rows collapsed into a single row whose cells
each hold the 13 values newline-separated; the S/N column and the index columns
each split into 13 aligned parts (the label column wraps, so we key on S/N =
COICOP division number and use canonical labels). The 'All Items' total is a
separate row. We emit the index for each of the three dated columns.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

from ..coicop import DIVISIONS

_BASE_PERIOD = "Jan-Dec 2020 = 100"
_MONTHS = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
           "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
           "nov": "11", "dec": "12"}
_HDR = re.compile(r"([A-Za-z]{3})[a-z]*\.?,?\s*(20\d\d)")


def _period(cell) -> str | None:
    if not isinstance(cell, str):
        return None
    m = _HDR.search(cell.replace("\n", " "))
    return f"{m.group(2)}-{_MONTHS[m.group(1).lower()]}" if m and m.group(1).lower() in _MONTHS else None


def _num(s) -> float | None:
    if isinstance(s, (int, float)):
        return float(s)
    if isinstance(s, str) and re.fullmatch(r"\d+\.\d+", s.strip()):
        return float(s.strip())
    return None


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for tb in page.extract_tables():
                flat = " ".join(str(c) for r in tb for c in r if c).lower()
                if "food and non" not in flat or "clothing" not in flat or "main group" not in flat:
                    continue
                hdr = next((r for r in tb if any(_period(c) for c in r)), None)
                if hdr is None:
                    continue
                pcols = {j: p for j, c in enumerate(hdr) if (p := _period(c))}

                records = []
                for r in tb:
                    sn = [x.strip() for x in (str(r[0]).split("\n") if r and r[0] else []) if x.strip()]
                    rowtext = " ".join(str(c) for c in r if c).lower()
                    if len(sn) >= 13 and all(x.isdigit() for x in sn[:13]):
                        for ci, period in pcols.items():
                            vals = str(r[ci]).split("\n") if ci < len(r) and r[ci] else []
                            for k, s in enumerate(sn[:13]):
                                v = _num(vals[k]) if k < len(vals) else None
                                if v is not None and 1 <= int(s) <= 13:
                                    code = f"{int(s):02d}"
                                    records.append((code, DIVISIONS.get(code, ""), period, v))
                    elif "all items" in rowtext and "less" not in rowtext:
                        for ci, period in pcols.items():
                            v = _num(r[ci]) if ci < len(r) else None
                            if v is not None:
                                records.append(("00", "All items", period, v))

                if len({c for c, *_ in records if c != "00"}) >= 13:
                    out = pd.DataFrame.from_records(
                        records, columns=["coicop_code", "coicop_label", "period", "value"])
                    out = out.drop_duplicates(["coicop_code", "period"])
                    out["geography"] = "National"
                    out["measure"] = "index"
                    out["unit"] = "Index"
                    out["base_period"] = _BASE_PERIOD
                    out["frequency"] = "monthly"
                    return out

    raise ValueError("Tanzania NCPI 'Main Groups' table not found in release")
