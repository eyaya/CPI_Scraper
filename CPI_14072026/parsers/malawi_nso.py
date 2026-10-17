"""Parser for the NSO Malawi monthly CPI 'Stats Flash' workbook (Tier 2, Excel via CMS).

One sheet, three stacked sections (National / Urban / Rural). Each section has a
weight row, a 'Dec, 2021 = 100' base row, then monthly rows newest-first:

  <year> <month> <MoM%> <Food MoM%> <NonFood MoM%> <Food> <Alcohol> … <All items>
  2026   May     -0.2    -1.0        1.0            318.2  289.4    … 285.2

The index (base Dec 2021 = 100, read from the base row) for the 12 COICOP-1999
divisions + 'All items', and the overall month-on-month inflation, are located
by their HEADER labels (the column order differs between workbook vintages). The year
appears only on the first month of each year-block, so it is carried forward. We
emit the index for every division and geography, plus all-items MoM, for every
reported month.
"""
from __future__ import annotations
import re
import pandas as pd

from .ihpc_note_pdf import over_issues

_GEOS = {"national": "National", "urban": "Urban", "rural": "Rural"}
_MON = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"}
# header label (normalised prefix) -> (coicop code, canonical label). Columns
# are located by their header, not by position: the 2022-23 workbook
# ('MtM_CPI_Stats_Flash.xlsx', old NSO site) puts the index columns FIRST and
# the three inflation columns last; the 2024+ Stats Flash puts them first.
_HEADERS = [
    ("food in", None),                      # 'Food  Inflation' -- a rate, not the index
    ("non-food in", None),
    ("month to month", ("00", "All items", "inflation_mom")),
    ("food", ("01", "Food and non-alcoholic beverages")),
    ("alcoholic", ("02", "Alcoholic beverages and tobacco")),
    ("clothing", ("03", "Clothing and footwear")),
    ("housing", ("04", "Housing, water, electricity, gas and other fuels")),
    ("furnishing", ("05", "Furnishings, household equipment and routine maintenance")),
    ("health", ("06", "Health")),
    ("transport", ("07", "Transport")),
    ("communication", ("08", "Communication")),
    ("recreation", ("09", "Recreation and culture")),
    ("education", ("10", "Education")),
    ("restaurant", ("11", "Restaurants and hotels")),
    ("misc", ("12", "Miscellaneous goods and services")),
    ("all items", ("00", "All items")),
]


def _columns(df: pd.DataFrame) -> tuple[dict, int]:
    """{column: (code, label[, measure])} from the header row, and the MoM column."""
    for i in range(min(6, df.shape[0])):
        cols, mom = {}, None
        for j in range(df.shape[1]):
            h = re.sub(r"\s+", " ", str(df.iloc[i, j])).strip().lower()
            hit = next((v for k, v in _HEADERS if h.startswith(k)), "none")
            if hit == "none" or hit is None:
                continue
            if len(hit) == 3:
                mom = j
            else:
                cols[j] = hit
        if len(cols) == 13 and mom is not None:
            return cols, mom
    raise ValueError("Malawi CPI: header row with the 13 index columns not found")


def _mm(x):
    return _MON.get(str(x).strip().lower()[:3])


def _parse_one(xlsx_path: str) -> pd.DataFrame:
    df = pd.ExcelFile(xlsx_path).parse("Sheet1", header=None)
    cols, mom_col = _columns(df)
    base = next((str(v).strip() for v in df.iloc[:, 0]
                 if re.fullmatch(r"[A-Za-z]{3},?\s*\d{4}", str(v).strip())), None)
    if base is None:
        raise ValueError("Malawi CPI: base-period row ('Dec, 2021') not found")
    base_period = re.sub(r",?\s+", " ", base) + " = 100"
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
        for col, (code, label) in cols.items():
            v = df.iloc[i, col]
            if pd.notna(v) and isinstance(v, (int, float)):
                records.append((code, label, geo, period, "index",
                                round(float(v), 4), "Index", base_period))
        mom = df.iloc[i, mom_col]               # overall month-on-month inflation
        if pd.notna(mom) and isinstance(mom, (int, float)):
            records.append(("00", "All items", geo, period, "inflation_mom",
                            round(float(mom), 4), "percent", ""))

    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "geography", "period",
                          "measure", "value", "unit", "base_period"])
    out["frequency"] = "monthly"
    return out


# Back issues (`extras`): each workbook shows 25 months; the newest wins on a
# shared (code, geography, period, measure).
parse = over_issues(_parse_one, "malawi_nso")
