"""Parser for the Stats SL annual GDP report (PDF, English).

Layout: activities/components in ROWS, years (2020-2024) in COLUMNS. Six tables
are read (the back-casted historical tables 7-10 are left for a later pass):

  Table 1  GDP at Current Prices  (production, by activity)   -> level
  Table 2  GDP at 2018 Constant Prices (production)           -> level, base 2018
  Table 3  GDP Shares in %                                    -> share
  Table 4  GDP Growth Rates                                   -> growth_yoy (real)
  Table 5  GDP Deflator (base 2018=100)                       -> deflator
  Table 6  GDP by Expenditure, current & constant 2018        -> level (+GDP-E growth)

CURRENCY BREAK: Sierra Leone redenominated the Leone in July 2022 (1000 old = 1
new). The report prints the 2020 column of every LEVEL table in OLD leone
(e.g. Agriculture 2020 = 23,096,017) and 2021-2024 in NEW leone (25,172.2 ...).
The report carries no explicit unit label, so rather than infer/convert we DROP
the ambiguous 2020 column from level tables and keep 2021-2024 (new leone,
consistent, unit 'SLE million'). The unit-free tables (shares %, growth %,
deflator index) are kept for all five years. Nothing is derived or converted.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]

# table number -> (approach, price_basis, measure, base_period, unit, drop_2020)
_SPECS = {
    1: ("production",  "current",  "level",      "",     "SLE million", True),
    2: ("production",  "constant", "level",      "2018", "SLE million", True),
    3: ("production",  "current",  "share",      "",     "percent",     False),
    4: ("production",  "constant", "growth_yoy", "2018", "percent",     False),
    5: ("production",  "not_applicable", "deflator", "2018", "index",   False),
    6: ("expenditure", "current",  "level",      "",     "SLE million", True),
}

_CODE_RE = re.compile(r"^\s*(\d+(?:\.\d+)+|\d+\.)\s+")
# numeric token: optional (…) negative, digits with thousands commas, optional
# decimal, optional trailing % — must start with a digit so labels like "(CII)"
# or "HFCE" are never picked up.
_NUM_RE = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?%?")
_YEARS = ["2020", "2021", "2022", "2023", "2024"]


def _to_float(tok: str):
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()%").replace(",", "")
    if tok in ("", "-", "."):
        return None
    try:
        v = float(tok)
    except ValueError:
        return None
    return -v if neg else v


def _classify(label: str, approach: str):
    low = label.lower()
    if "total gross value added" in low or re.search(r"gross domestic product|gdp-e", low):
        return "aggregate"
    return approach


def parse(pdf_path: str) -> pd.DataFrame:
    rows = []
    table = None            # current table number
    basis_override = None   # for Table 6 CURRENT / CONSTANT sections
    pending_nums = None     # numbers-only line awaiting its wrapped label

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw in text.split("\n"):
                line = raw.strip()
                if not line:
                    continue

                # year-header row (may carry a stray "2018" from the caption)
                if re.search(r"2020\s+2021\s+2022\s+2023\s+2024", line):
                    continue

                m = re.match(r"Table\s+(\d+)\w?\s*:", line)
                if m:
                    n = int(m.group(1))
                    table = n if n in _SPECS else None
                    basis_override = None
                    pending_nums = None
                    continue
                if table is None:
                    continue

                # Table 6 price-basis section switches
                if table == 6:
                    up = line.upper()
                    if "CURRENT PRICE" in up:
                        basis_override = "current"; continue
                    if "CONSTANT" in up and "PRICE" in up:
                        basis_override = "constant"; continue

                approach, basis, measure, base, unit, drop20 = _SPECS[table]
                if basis_override is not None:
                    basis = basis_override

                # strip a leading dotted series code
                cm = _CODE_RE.match(line)
                code = ""
                body = line
                if cm:
                    code = cm.group(1).rstrip(".")
                    body = line[cm.end():]

                toks = _NUM_RE.findall(body)
                nums = [t for t in toks]
                # year-header line: its "numbers" are exactly the 4-digit years
                if [t.strip("()%").replace(",", "") for t in nums[:5]] == _YEARS:
                    continue

                if not nums:
                    # label-only line: complete a wrapped numbers-only row above
                    if pending_nums is not None and re.search(r"[A-Za-z]", body):
                        label = body.strip(" .:-")
                        vals = pending_nums
                        pending_nums = None
                        _emit(rows, code, label, vals, approach, basis, measure,
                              base, unit, drop20, table)
                    continue

                label = body[:body.find(nums[0])].strip(" .:-")
                if table == 6 and label.lower().startswith("growth rate"):
                    continue                 # derived % row, not a level
                if not re.search(r"[A-Za-z]", label):
                    # numbers-only line (wrapped label follows) -> hold it
                    if len(nums) >= 5:
                        pending_nums = nums
                    continue

                pending_nums = None
                _emit(rows, code, label, nums, approach, basis, measure,
                      base, unit, drop20, table)

    if not rows:
        raise ValueError("no GDP rows parsed from Stats SL report")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "series_code", "period", "measure", "price_basis"])


def _emit(rows, code, label, nums, approach, basis, measure, base, unit,
          drop20, table):
    if len(nums) < 5:
        return
    vals = nums[-5:]                       # align to the five year columns
    approach = _classify(label, approach)
    is_pct = measure in ("share", "growth_yoy") or unit == "percent"
    for year, tok in zip(_YEARS, vals):
        if measure == "level" and drop20 and year == "2020":
            continue                       # old-leone column, ambiguous scale
        v = _to_float(tok)
        if v is None:
            continue
        rows.append({
            "approach": approach, "category": label, "category_group": "",
            "series_code": code, "geography": "National", "period": year,
            "frequency": "annual", "price_basis": basis,
            "seasonal_adjustment": "nsa", "measure": measure,
            "value": v, "unit": unit, "base_period": base,
        })
