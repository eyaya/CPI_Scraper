"""Parser for the Ethiopian Statistical Service (ESS) monthly CPI bulletin (Tier 3, PARTIAL).

ESS publishes a 'Statistical Bulletin — Consumer Price Index' whose full COICOP
index is shown only as bar charts. Its clean, tabular data are the headline
inflation series: 'General … Inflation Rate (%, Year-on-Year)' (a 13-month table,
General/Food/Non-Food) and the 'General month-to-month' table. We capture the
national all-items (General) YoY and MoM series.

Dates use the Ethiopian fiscal-year tag (EFY); the report month is stated as
'<Month> EFY<YYYY>'. Ethiopian year N spans Gregorian Sept N+7 – Sept N+8, so a
Jan–Aug month maps to EFY+8 and a Sep–Dec month to EFY+7 (calendar fact, not
estimation). The two tables are 13 consecutive months; because ESS occasionally
mislabels a row, we anchor the LAST row to the report month and step back one
month per row. PARTIAL: all-items General only; by-division figures are chart-only.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_MONTHS = ["january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december"]
_MNUM = {m: i for i, m in enumerate(_MONTHS, 1)}
_MONTH_RE = "(" + "|".join(_MONTHS) + ")"
_ROW = re.compile(r"^\s*" + _MONTH_RE + r"\b", re.I)
_NUM = re.compile(r"-?\d+\.\d+")


def _report_period(text: str):
    m = re.search(r"month of\s+" + _MONTH_RE + r"[\s\-]*efy[\s\-]*(\d{4})", text, re.I)
    if not m:
        raise ValueError("Ethiopia CPI: report month (Month EFY YYYY) not found")
    mm = _MNUM[m.group(1).lower()]
    efy = int(m.group(2))
    greg = efy + 8 if mm <= 8 else efy + 7           # Ethiopian-year → Gregorian
    return greg, mm


def _step_back(y, m, k):                              # k months before (y, m)
    idx = (y * 12 + (m - 1)) - k
    return idx // 12, idx % 12 + 1


def _series(text: str, n_nums: int):
    """Ordered list of the (label-row) values with exactly n_nums numbers each,
    excluding annual 'EFY.. - ..EFY..' range rows."""
    out = []
    for ln in text.splitlines():
        if not _ROW.match(ln) or " - " in ln:
            continue
        nums = _NUM.findall(ln)
        if len(nums) == n_nums:
            out.append(float(nums[0]))               # General is the first column
    return out


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    text = "\n".join(pages)
    ry, rm = _report_period(text)

    yoy = next((_series(t, 3) for t in pages if len(_series(t, 3)) >= 12), [])
    mom = next((_series(t, 1) for t in pages if len(_series(t, 1)) >= 12), [])
    if not yoy:
        raise ValueError("Ethiopia CPI: year-on-year series not found")

    records = []
    for series, measure in [(yoy, "inflation_yoy"), (mom, "inflation_mom")]:
        last = len(series) - 1
        for i, val in enumerate(series):
            y, m = _step_back(ry, rm, last - i)      # last row = report month
            records.append(("00", "General (All items)", f"{y}-{m:02d}", measure,
                            round(val, 4), "percent", ""))

    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
