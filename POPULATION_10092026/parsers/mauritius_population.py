"""Statistics Mauritius — estimated resident population by age group and sex.

Parser for the "Demographic Statistics - Island of Mauritius" workbook (.xls),
Table 13: estimated resident population by age group and sex, mid-year 1984-2024.
The sheet is wide by year — a year header row ("1 July <YYYY>") every three columns,
each block holding Male / Female / Both sexes — with age groups down the rows.

We emit one tidy row per (age group, sex, year) as a mid-year population estimate
(series_type = estimate). National (Island of Mauritius); as published.
"""
from __future__ import annotations
import re
import pandas as pd

_SHEET = "T13"
_YEAR_RE = re.compile(r"(19|20)\d{2}")
_AGE_RE = re.compile(r"^(\d{1,3}\s*-\s*\d{1,3}|\d{1,3}\s*\+?|All ages|Total)$", re.I)
_SEX = {"male": "male", "female": "female", "both sexes": "total"}


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(str(v).replace(",", "").replace(" ", "").strip())
    except (TypeError, ValueError):
        return None


def _norm_age(a: str) -> str:
    a = a.strip()
    if a.lower() in ("all ages", "total"):
        return "Total"
    return re.sub(r"\s*\+", "+", re.sub(r"\s*-\s*", "-", a))


def parse(xls_path: str) -> pd.DataFrame:
    df = pd.ExcelFile(xls_path).parse(_SHEET, header=None)
    rows = df.values.tolist()

    # year-header row: the one with the most cells containing a 4-digit year
    hi = max(range(len(rows)),
             key=lambda i: sum(1 for c in rows[i] if _YEAR_RE.search(str(c))))
    year_cols = [(c, _YEAR_RE.search(str(v)).group(0))
                 for c, v in enumerate(rows[hi]) if _YEAR_RE.search(str(v))]
    sub = rows[hi + 1]                      # Male / Female / Both sexes per block

    out = []
    for r in rows[hi + 2:]:
        if not r or r[0] is None:
            continue
        age = str(r[0]).strip()
        if not _AGE_RE.match(age):
            continue
        age_group = _norm_age(age)
        for c, year in year_cols:
            # the block occupies columns c, c+1, c+2 in the sub-header's order
            for off in range(3):
                col = c + off
                sex = _SEX.get(str(sub[col]).strip().lower()) if col < len(sub) else None
                val = _num(r[col]) if col < len(r) else None
                if sex and val is not None:
                    out.append({
                        "series_type": "estimate", "sex": sex, "age_group": age_group,
                        "geography": "Total country", "period": year,
                        "frequency": "annual", "measure": "count",
                        "value": val, "unit": "persons", "series_code": "SM_DEMOG_T13",
                    })
    out_df = pd.DataFrame(out)
    if out_df.empty:
        raise ValueError("mauritius_population: no rows parsed")
    return out_df.drop_duplicates(["age_group", "sex", "period"])
