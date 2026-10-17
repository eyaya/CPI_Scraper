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

BACK ISSUES (extras): the 2019-2024 'Country and Regional Level CPI' bulletins
print 'Table 1a' -- the index itself (December 2016 = 100) for General, Food and
the 11 non-food divisions -- which `_parse_table1a` reads; the current bulletin
still yields rates only. Newest issue wins on a shared period (ESS revises
recent months by 0.1-0.3 points between issues).
"""
from __future__ import annotations
import difflib
import re
import pdfplumber
import pandas as pd

from .ihpc_note_pdf import over_issues

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


def _parse_rates(pages: list[str]) -> pd.DataFrame:
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


# --- the 2019 - 2024 bulletin: 'Table 1a', the index itself -------------------
# Until late 2024 ESS published 'Country and Regional Level Consumer Price
# Indices', whose 'Table 1a: General Consumer Price Index and Its Components
# Country Level' (December 2016 = 100) prints, per month, the General index,
# Food, the Non-food aggregate and the 11 non-food COICOP-1999 divisions:
#
#   <Amharic month EFY>  302.0 341.2 256.9 253.4 … 276.2  July 2022
#   <Amharic month EFY>  310.8 352.3 263.0 262.3 … 287.7  August ''
#
# Each monthly row ends with its English month and either a year or '' (ditto).
# Rows are consecutive months; the rows that print a year anchor the run, every
# anchor must agree, and every row's month name must match its computed month,
# or the table is refused. Fiscal-year average rows ('July 2017 - June 2018') and
# the closing percent-change row (no month) and the base row (all 100.0) are
# not monthly rows. The Non-food
# aggregate is not a COICOP division and is skipped, as elsewhere in the corpus.
_T1A_COLS = [("00", "General (All items)"),
             ("01", "Food and non-alcoholic beverages"),
             (None, "Non-food"),
             ("02", "Alcoholic beverages and tobacco"),
             ("03", "Clothing and footwear"),
             ("04", "Housing, water, electricity, gas and other fuels"),
             ("05", "Furnishings, household equipment and routine maintenance"),
             ("06", "Health"), ("07", "Transport"), ("08", "Communication"),
             ("09", "Recreation and culture"), ("10", "Education"),
             ("11", "Restaurants and hotels"),
             ("12", "Miscellaneous goods and services")]
_T1A_ROW = re.compile(r"([A-Za-z]{3,})\s*(\d{4}|''|\"|”)?\s*$")


def _month_of(word: str) -> int | None:
    hit = difflib.get_close_matches(word.lower(), _MONTHS, n=1, cutoff=0.75)
    return _MNUM[hit[0]] if hit else None


def _parse_table1a(pages: list[str]) -> pd.DataFrame:
    page = next((t for t in pages
                 if re.search(r"table\s*1\s*a\s*:", t, re.I)
                 and len(_NUM.findall(t)) > 100), None)
    if page is None:
        raise ValueError("Ethiopia CPI: 'Table 1a' not found")
    base = re.search(r"([A-Z][a-z]+\s+\d{4})\s*=\s*100", page)
    if not base:
        raise ValueError("Ethiopia CPI: Table 1a base period not stated")
    rows = []
    for ln in page.splitlines():
        nums = _NUM.findall(ln)
        m = _T1A_ROW.search(ln)
        if len(nums) != len(_T1A_COLS) or " - " in ln or not m:
            continue
        if all(float(x) == 100.0 for x in nums):
            continue                    # the base-period row ('December 2016')
        mm = _month_of(m.group(1))
        if mm is None:
            continue
        year = int(m.group(2)) if m.group(2) and m.group(2).isdigit() else None
        rows.append((mm, year, [float(x) for x in nums]))
    anchors = {i - (y * 12 + mm - 1) for i, (mm, y, _) in enumerate(rows) if y}
    if len(rows) < 2 or len(anchors) != 1:
        raise ValueError(f"Ethiopia CPI: Table 1a rows not consecutive/anchored "
                         f"({len(rows)} rows, anchors {sorted(anchors)[:3]})")
    shift = anchors.pop()
    records = []
    for i, (mm, _, vals) in enumerate(rows):
        idx = i - shift
        y, m = idx // 12, idx % 12 + 1
        if m != mm:
            raise ValueError(f"Ethiopia CPI: Table 1a row {i} reads month {mm}, "
                             f"expected {m}")
        for (code, label), v in zip(_T1A_COLS, vals):
            if code:
                records.append((code, label, f"{y}-{m:02d}", "index", v, "Index",
                                f"{base.group(1)} = 100"))
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out


def _parse_issue(pdf_path: str) -> pd.DataFrame:
    """Whatever the issue carries: the headline rate tables (bulletins from
    late 2024 on) and/or Table 1a's index (2019 - 2024 bulletins)."""
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    frames, errors = [], []
    for reader in (_parse_rates, _parse_table1a):
        try:
            frames.append(reader(pages))
        except ValueError as e:
            errors.append(str(e))
    if not frames:
        raise ValueError(" | ".join(errors))
    return pd.concat(frames, ignore_index=True)


parse = over_issues(_parse_issue, "ethiopia_ess")
