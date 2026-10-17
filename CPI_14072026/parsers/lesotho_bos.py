"""Parser for the Lesotho Bureau of Statistics monthly CPI report PDF (Tier 3).

The BOS report's 'Table 1: Monthly Consumer Price Indices by COICOP Divisions'
reads as text — one row per division + 'Overall CPI':

  <label>  <weight>  <idx m-12>  <idx m-1>  <idx current>  <M%>  <Y%>
  Overall CPI  100  117.59 120.37 121.74  1.1 3.5
  01. Food & Non-alcoholic beverages  32.61  124.21 125.88 126.29  0.3 1.7

Each row ends with 1-month and 12-month % changes, so the current index is
nums[-3], MoM nums[-2], YoY nums[-1]. Division 05's label wraps onto its number
row, so a label is carried forward. Analytical aggregates (Services, Non-durables,
…) don't match a division keyword and are skipped. Base Average 2022 = 100.
"""
from __future__ import annotations
import io
import os
import re
import zipfile
import pdfplumber
import pandas as pd

_BASE_PERIOD = "Average 2022 = 100"
_MONTHS = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
           "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
           "nov": "11", "dec": "12"}
_DIVS = [
    ("00", "Overall CPI (All items)", "overall cpi"),
    ("01", "Food and non-alcoholic beverages", "food"),
    ("02", "Alcoholic beverages and tobacco", "alcohol"),
    ("03", "Clothing and footwear", "clothing"),
    ("04", "Housing, water, electricity, gas and other fuels", "housing"),
    ("05", "Furnishings, household equipment and routine maintenance", "furnishing"),
    ("06", "Health", "health"),
    ("07", "Transport", "transport"),
    ("08", "Communications", "communication"),
    ("09", "Recreation and culture", "recreation"),
    ("10", "Education", "education"),
    ("11", "Restaurants and hotels", "restaurant"),
    ("12", "Miscellaneous goods and services", "miscellaneous"),
]
_NUM = re.compile(r"-?\d+\.\d+")
_FMONTHS = ("january|february|march|april|may|june|july|august|september|"
            "october|november|december")


def _period(path: str) -> str | None:
    m = re.search(r"(" + _FMONTHS + r")[-_ ]*(20\d\d)", os.path.basename(path), re.IGNORECASE)
    return f"{m.group(2)}-{_MONTHS[m.group(1).lower()[:3]]}" if m else None


def _code(label: str):
    low = label.lower()
    for c, lab, kw in _DIVS:
        if kw in low:
            return c, lab
    return None


_BASE_STATED = re.compile(r"2022\s*=\s*100")


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """The current report plus back issues handed in as extras.

    BACK ISSUES are the same 'CPI_<Month>_<Year>.zip' archives (URL pattern
    BoS_reports/Copy of Economics/), read in place: the PDF member is opened
    from the zip. Only back issues that STATE the 2022 = 100 base are taken
    (January 2023 on); the 2017-2022 reports print indices on an earlier base
    the report never names, so they are skipped with a message rather than
    labelled with a guessed base. One report = one month, so issues do not
    overlap; a layout that cannot be read is skipped.
    """
    frames = []
    for p in [pdf_path, *(extras or [])]:
        try:
            frames.append(_parse_one(p, require_base=p != pdf_path))
        except ValueError as e:
            print(f"  [lesotho_bos] skipped {os.path.basename(p)}: {e}")
    if not frames:
        raise ValueError("Lesotho CPI: no report could be read")
    out = pd.concat(frames, ignore_index=True)
    return out.drop_duplicates(["coicop_code", "period", "measure"]).reset_index(drop=True)


def _parse_one(pdf_path: str, require_base: bool = False) -> pd.DataFrame:
    if pdf_path.lower().endswith(".zip"):
        with zipfile.ZipFile(pdf_path) as z:
            members = [n for n in z.namelist() if n.lower().endswith(".pdf")]
            if not members:
                raise ValueError("no PDF in the archive")
            src = io.BytesIO(z.read(members[0]))
    else:
        src = pdf_path
    with pdfplumber.open(src) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    if require_base and not _BASE_STATED.search(text):
        raise ValueError("report does not state the 2022 = 100 base")
    period = _period(pdf_path)
    if not period:
        raise ValueError("Lesotho CPI: report month not found in filename")

    picked, pending = {}, ""
    for ln in text.splitlines():
        nums = _NUM.findall(ln)
        m = _NUM.search(ln)
        label_part = ln[:m.start()].strip() if m else ln.strip()
        if len(nums) >= 5:                        # (weight) + 3 indices + 2 rates; weight may be an int
            hit = _code((pending + " " + label_part).strip())
            pending = ""
            if hit and hit[0] not in picked:
                picked[hit[0]] = (hit[1], float(nums[-3]), float(nums[-2]), float(nums[-1]))
        elif label_part:
            pending = label_part

    missing = [c for c, _, _ in _DIVS if c not in picked]
    if missing:
        raise ValueError(f"Lesotho CPI incomplete: missing {missing}")

    records = []
    for code, (label, idx, mom, yoy) in picked.items():
        records.append((code, label, period, "index", round(idx, 4), "Index", _BASE_PERIOD))
        records.append((code, label, period, "inflation_mom", round(mom, 4), "percent", ""))
        records.append((code, label, period, "inflation_yoy", round(yoy, 4), "percent", ""))
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
