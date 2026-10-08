"""Parser for the Stats SA GDP (P0441) time-series workbook.

Layout (wide time series, same H-code convention as the CPI workbook):
  Level sheets   'Annual' / 'Quarterly'   -> value levels, H17 = "R million"
  Growth sheets  'AnnualP' / 'QuarterlyP' -> % change,     H17 = the change type

  Columns: H03=series code, H04=SNA table (approach), H05=component/sector label,
    H15=price basis ("Current prices" / "Constant 2015 prices"),
    H16=valuation (quarterly only: "Actual values" / "Seasonally adjusted and
    annualised values"), H17=unit-or-measure, H25=frequency; then one value column
    per period — annual 'Y<YYYY>', quarterly '<YYYY><QQ>' (QQ=01..04).

We read H15/H16/H17 directly (self-describing) rather than decoding the series-code
prefixes (AN/AR/QNU/QNS/QRU/QRS...), so the parser doesn't depend on that scheme.
The four SNA approaches are mapped from H04. The two 'Coe seasonal' sheets
(seasonally adjusted compensation of employees, an extra table) are not split out
in v1 — CoE already appears in the main sheets at actual values.
"""
from __future__ import annotations
import re
import pandas as pd

# H04 (SNA table) -> approach. Exact labels first; the parenthetical/footnoted
# variants ("Gross fixed capital formation (type of asset)", "... 1") by prefix.
_APPROACH = {
    "GDP at market prices": "aggregate",
    "Value added at basic prices": "production",
    "Taxes less subsidies on products": "production",
    "Expenditure on GDP": "expenditure",
    "Final consumption expenditure by households": "expenditure",
    "Final consumption expenditure by general government": "expenditure",
    "Residual (production less expenditure)": "expenditure",
    "Compensation of employees": "income",
}
_APPROACH_PREFIX = [
    ("gross fixed capital formation", "expenditure"),
    ("change in inventories", "expenditure"),
    ("gross operating surplus", "income"),
]

_FOOTNOTE = re.compile(r"\s+\d+$")            # trailing " 1" footnote marker
_ANNUAL_COL = re.compile(r"^Y(\d{4})$")
_QUARTER_COL = re.compile(r"^(\d{4})(0[1-4])$")

# sheet name -> is_growth
_SHEETS = [("Annual", False), ("Quarterly", False),
           ("AnnualP", True), ("QuarterlyP", True)]

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _approach(group: str) -> str | None:
    g = _FOOTNOTE.sub("", str(group).strip())
    if g in _APPROACH:
        return _APPROACH[g]
    gl = g.lower()
    for pref, ap in _APPROACH_PREFIX:
        if gl.startswith(pref):
            return ap
    return None


def _period_map(cols) -> tuple[dict, str]:
    """Map each period column label to a canonical period string; return the map
    and the sheet frequency ('annual' or 'quarterly')."""
    pmap, freq = {}, None
    for c in cols:
        s = str(c)
        m = _ANNUAL_COL.match(s)
        if m:
            pmap[c] = m.group(1)
            freq = "annual"
            continue
        m = _QUARTER_COL.match(s)
        if m:
            pmap[c] = f"{m.group(1)}-Q{int(m.group(2))}"
            freq = "quarterly"
    return pmap, freq


def _melt_sheet(df: pd.DataFrame, sheet: str, is_growth: bool) -> pd.DataFrame:
    pmap, freq = _period_map(df.columns)
    if not pmap:
        raise ValueError(f"no period columns in sheet {sheet!r}")

    has_h16 = "H16" in df.columns
    id_cols = ["H03", "H04", "H05", "H15", "H17"] + (["H16"] if has_h16 else [])
    long = df.melt(id_vars=id_cols, value_vars=list(pmap),
                   var_name="_p", value_name="value")

    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"]).copy()

    long["category_group"] = long["H04"].astype(str).str.replace(
        _FOOTNOTE, "", regex=True).str.strip()
    long["approach"] = long["category_group"].map(_approach)
    long = long[long["approach"].notna()].copy()

    long["period"] = long["_p"].map(pmap)
    long["frequency"] = freq
    long["series_code"] = long["H03"].astype(str).str.strip()
    long["category"] = long["H05"].astype(str).str.strip()
    # some series (e.g. the production-less-expenditure residual) carry no H05
    # component label; fall back to the group so `category` is never blank.
    blank = long["category"].isin(["", "nan", "None"]) | long["H05"].isna()
    long.loc[blank, "category"] = long.loc[blank, "category_group"]
    long["geography"] = "Total country"

    h15 = long["H15"].astype(str).str.lower()
    long["price_basis"] = pd.Series(
        pd.NA, index=long.index, dtype="object")
    long.loc[h15.str.contains("current"), "price_basis"] = "current"
    long.loc[h15.str.contains("constant"), "price_basis"] = "constant"
    long["price_basis"] = long["price_basis"].fillna("not_applicable")

    if has_h16:
        h16 = long["H16"].astype(str).str.lower()
        long["seasonal_adjustment"] = h16.map(
            lambda s: "saa" if "seasonal" in s else "nsa")
    else:
        long["seasonal_adjustment"] = "not_applicable"

    if is_growth:
        h17 = long["H17"].astype(str).str.lower()
        long["measure"] = h17.map(
            lambda s: "growth_qoq" if "quarter-on-quarter" in s
            else "growth_yoy" if "year-on-year" in s else "growth")
        long["unit"] = "percent"
        long["base_period"] = ""
    else:
        long["measure"] = "level"
        long["unit"] = long["H17"].astype(str).str.strip()      # "R million"
        # keep the constant-price base label (e.g. "Constant 2015 prices")
        long["base_period"] = ""
        long.loc[long["price_basis"] == "constant", "base_period"] = \
            long["H15"].astype(str).str.strip()

    return long[_OUT_COLS]


def parse(xlsx_path: str) -> pd.DataFrame:
    xl = pd.ExcelFile(xlsx_path)
    frames = []
    for sheet, is_growth in _SHEETS:
        if sheet not in xl.sheet_names:
            continue
        df = pd.read_excel(xlsx_path, sheet_name=sheet, header=0, dtype=str)
        frames.append(_melt_sheet(df, sheet, is_growth))
    if not frames:
        raise ValueError("no GDP sheets found in workbook")
    return pd.concat(frames, ignore_index=True)
