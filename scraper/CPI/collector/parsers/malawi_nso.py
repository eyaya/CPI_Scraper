"""Parser for the NSO Malawi monthly CPI 'Stats Flash' workbook (Tier 2, Excel via CMS).

One sheet, three stacked sections (National / Urban / Rural). Each section has a
weight row, a 'Dec, 2021 = 100' base row, then monthly rows newest-first:

  <year> <month> <MoM%> <Food MoM%> <NonFood MoM%> <Food> <Alcohol> … <All items>
  2026   May     -0.2    -1.0        1.0            318.2  289.4    … 285.2

Columns 5–17 are the index (base Dec 2021 = 100) for the 12 COICOP-1999 divisions
+ 'All items' (col 17). Column 2 is the overall month-on-month inflation. The year
appears only on the first month of each year-block, so it is carried forward. We
emit the index for every division and geography, plus all-items MoM, for every
reported month.
"""
from __future__ import annotations
import re
import pandas as pd

_BASE_PERIOD = "Dec 2021 = 100"
_GEOS = {"national": "National", "urban": "Urban", "rural": "Rural"}
_MON = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"}
# column index -> (coicop code, canonical label)
_COLS = {
    5:  ("01", "Food and non-alcoholic beverages"),
    6:  ("02", "Alcoholic beverages and tobacco"),
    7:  ("03", "Clothing and footwear"),
    8:  ("04", "Housing, water, electricity, gas and other fuels"),
    9:  ("05", "Furnishings, household equipment and routine maintenance"),
    10: ("06", "Health"),
    11: ("07", "Transport"),
    12: ("08", "Communication"),
    13: ("09", "Recreation and culture"),
    14: ("10", "Education"),
    15: ("11", "Restaurants and hotels"),
    16: ("12", "Miscellaneous goods and services"),
    17: ("00", "All items"),
}


def _mm(x):
    return _MON.get(str(x).strip().lower()[:3])


def parse(xlsx_path: str) -> pd.DataFrame:
    df = pd.ExcelFile(xlsx_path).parse("Sheet1", header=None)
    records = []
    geo, year = None, None
    for i in range(df.shape[0]):
        c0 = str(df.iloc[i, 0]).strip()
        low = c0.lower()
        if low in _GEOS:                       # section header resets the year
            geo, year = _GEOS[low], None
            continue
        if re.fullmatch(r"20\d\d", c0):        # year label (first month of a block)
            year = c0
        mm = _mm(df.iloc[i, 1])
        if not (geo and year and mm):
            continue
        period = f"{year}-{mm}"
        for col, (code, label) in _COLS.items():
            v = df.iloc[i, col]
            if pd.notna(v) and isinstance(v, (int, float)):
                records.append((code, label, geo, period, "index",
                                round(float(v), 4), "Index", _BASE_PERIOD))
        mom = df.iloc[i, 2]                     # overall month-on-month inflation
        if pd.notna(mom) and isinstance(mom, (int, float)):
            records.append(("00", "All items", geo, period, "inflation_mom",
                            round(float(mom), 4), "percent", ""))

    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "geography", "period",
                          "measure", "value", "unit", "base_period"])
    out["frequency"] = "monthly"
    return out
