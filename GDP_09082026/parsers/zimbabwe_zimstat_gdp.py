"""Parser for the ZimStat Quarterly GDP workbook (Zimbabwe, ZWG series).

Clean Excel. Each 'Table 1.x' sheet is quarterly GDP by industry: a two-row header
(year row + Q1..Q4 row) across the columns and the industries down the rows.

Sheets used (the current ZWG series, 2023 onward):
  Table 1.1  QGDP current prices    -> production level current
  Table 1.2  QGDP constant prices   -> production level constant
  Table 1.3  Q-o-Q growth rate      -> production real QoQ growth
  Table 1.5  Y-o-Y growth rate      -> production real YoY growth
  Table 1.4  constant contribution  -> contribution to growth
  Implied deflators                 -> deflator

Values are in ZWG (Zimbabwe Gold) for levels, percent for growth, index for the
deflator (2023 = 100). Table 1.4 is a percent DISTRIBUTION of GDP (the column
sums to 100 at 'GDP at Market Prices'), so it is a `share` -- it was filed as a
`contribution` in percentage points until 2026-10-13.

The 2.x tables re-state 2019-2023 in the old ZWL currency at constant 2023
prices: a separate series (unit ZWL, category_group 'ZWL series 2019-2023').

EXTRAS (back series, each tagged in category_group):
  * GDP_Tables_2019_2024*.xlsx -- ANNUAL GDP by industry, expenditure and income
    at current and constant 2023 prices, with percent distributions and growth:
    the ZWL series 2019-2023 and the ZWG series 2023-2024.
  * GDP_Trends_2009to2018.xls -- the previous, 2012-base series in US$ million,
    annual: industry 2009-2017, expenditure 2009-2018. A SEPARATE base, never
    chained to the 2023 base.
Everything as published; nothing derived.
"""
from __future__ import annotations
import re
import pandas as pd

# sheet-name prefix -> (measure, price_basis, unit)
_SHEETS = [
    ("Table 1.1", ("level", "current", "ZWG")),
    ("Table 1.2", ("level", "constant", "ZWG")),
    ("Table 1.3", ("growth_qoq", "constant", "percent")),
    ("Table 1.5", ("growth_yoy", "constant", "percent")),
    ("Table 1.4", ("share", "constant", "percent")),
    ("Implied deflators", ("deflator", "not_applicable", "index")),
    # the ZWL re-statement of 2019-2023 (same layout)
    ("Table 2.1", ("level", "current", "ZWL")),
    ("Table 2.2", ("share", "current", "percent")),
    ("Table 2.3", ("level", "constant", "ZWL")),
    ("Table2.4", ("share", "constant", "percent")),
    ("Table 2.5", ("growth_yoy", "constant", "percent")),
    ("Table 2.6", ("growth_qoq", "constant", "percent")),
]

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _cell(v):
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def _period_map(df):
    """Find the year row and the Q1..Q4 row; map each column to a period."""
    year_row = q_row = None
    for i in range(min(6, len(df))):
        texts = [_cell(df.iat[i, c]) for c in range(df.shape[1])]
        if year_row is None and sum(bool(re.fullmatch(r"20\d\d", t)) for t in texts) >= 3:
            year_row = i
        if q_row is None and sum(bool(re.fullmatch(r"Q[1-4]", t)) for t in texts) >= 3:
            q_row = i
    if year_row is None or q_row is None:
        return None, {}
    pmap, cur = {}, None
    for c in range(df.shape[1]):
        y = _cell(df.iat[year_row, c])
        if re.fullmatch(r"20\d\d", y):
            cur = y
        q = _cell(df.iat[q_row, c])
        if cur and re.fullmatch(r"Q[1-4]", q):
            pmap[c] = f"{cur}-{q}"
    return q_row, pmap


def _parse_sheet(df, measure, basis, unit, group=""):
    q_row, pmap = _period_map(df)
    if not pmap:
        return []
    base = ("2023 prices" if basis == "constant" else
            "2023=100" if measure == "deflator" else "")
    label_col = min(pmap) - 1 if min(pmap) > 0 else 0
    rows = []
    for r in range(q_row + 1, len(df)):
        label = re.sub(r"\s+", " ", _cell(df.iat[r, label_col])).strip()
        if not label or len(label) < 3:
            continue
        low = label.lower()
        if any(k in low for k in ("source", "table", "note", "industry")):
            continue
        approach = "aggregate" if ("gross domestic product" in low or low == "gdp"
                                   or "gdp at market" in low or low.startswith("total")) else "production"
        for c, period in pmap.items():
            if c >= df.shape[1]:
                continue
            v = pd.to_numeric(_cell(df.iat[r, c]), errors="coerce")
            if pd.isna(v):
                continue
            rows.append({
                "approach": approach, "category": label, "category_group": group,
                "series_code": "", "geography": "National", "period": period,
                "frequency": "quarterly", "price_basis": basis,
                "seasonal_adjustment": "nsa", "measure": measure,
                "value": float(v), "unit": unit, "base_period": base,
            })
    return rows


# --- annual extras ------------------------------------------------------------
_SKIP = ("exchange rate", "population", "per capita", "percapita")


def _annual_rows(df, approach, basis, measure, unit, base, group):
    """Generic annual table: label in column 0, a header row of years, then
    rows until the next header/title. Only the FIRST contiguous run of year
    columns is read (some sheets repeat the years in a second, rescaled or
    alternative block to the right)."""
    hdr = cols = None
    for i in range(min(8, len(df))):
        cols = [(c, int(float(_cell(df.iat[i, c])))) for c in range(1, df.shape[1])
                if re.fullmatch(r"20\d\d(\.0)?", _cell(df.iat[i, c]))]
        if len(cols) >= 2:
            hdr = i
            break
    if hdr is None:
        return []
    run = [cols[0]]
    for c, y in cols[1:]:
        if c == run[-1][0] + 1 and y == run[-1][1] + 1:
            run.append((c, y))
        else:
            break
    if measure.startswith("growth"):
        # a base year's growth column is printed as 0.0 (or '-') throughout:
        # a placeholder, not a published rate
        vals = {c: pd.to_numeric(pd.Series([_cell(df.iat[r, c]) for r in range(hdr + 1, len(df))]),
                                 errors="coerce").dropna() for c, _ in run}
        run = [(c, y) for c, y in run if len(vals[c]) and not (vals[c] == 0).all()]
    rows = []
    for r in range(hdr + 1, len(df)):
        label = re.sub(r"\s+", " ", _cell(df.iat[r, 0])).strip()
        if re.match(r"(table|scenario|item/|industry ?/|expenditure on)", label, re.I):
            break                                   # next stacked block
        if not label or any(k in label.lower() for k in _SKIP):
            continue
        low = label.lower()
        ap = approach
        if approach == "production" and ("gdp at market" in low or
                                          "gross domestic product at market" in low):
            ap = "aggregate"
        for c, y in run:
            v = pd.to_numeric(_cell(df.iat[r, c]), errors="coerce")
            if pd.isna(v):
                continue
            rows.append({
                "approach": ap, "category": label, "category_group": group,
                "series_code": "", "geography": "National", "period": str(y),
                "frequency": "annual", "price_basis": basis,
                "seasonal_adjustment": "not_applicable", "measure": measure,
                "value": float(v), "unit": unit if measure == "level" else "percent",
                "base_period": base if basis == "constant" else "",
            })
    return rows


def _tables_2019_2024(path):
    """ZimStat 'GDP Tables 2019-2024' (June 2025 revision): annual, 2023 base.
    Table 1 (old-versus-new 2023 comparison) is skipped."""
    import os
    xl = pd.ExcelFile(path)
    tag = re.sub(r"\.xlsx?$", "", os.path.basename(path))
    rows = []
    for sheet in xl.sheet_names:
        m = re.match(r"\s*Table\s*(\d)\.?(\d*)", sheet)
        if not m or (m.group(1) == "1" and not m.group(2)):
            continue
        df = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str)
        title = " ".join(_cell(v) for v in df.iloc[:2, 0])
        tl, nl = title.lower(), sheet.lower()
        approach = {"4": "expenditure", "5": "income"}.get(m.group(1), "production")
        basis = "constant" if ("constant" in tl or " kp" in nl) else "current"
        if "cont" in nl or "con kp" in nl or "contribution" in tl:
            measure = "share"
        elif "grow" in nl or "growth" in tl:
            measure = "growth_yoy"
        else:
            measure = "level"
        # the ZWL re-statement spans 2019-2023; the ZWG tables 2023-2024
        zwl = any(re.fullmatch(r"2019(\.0)?", _cell(v)) for v in df.iloc[:4].values.ravel())
        series = "ZWL series 2019-2023" if zwl else "ZWG series 2023-2024"
        rows += _annual_rows(df, approach, basis, measure, "ZWL" if zwl else "ZWG",
                             "2023 prices", f"ZimStat {tag}, {series}")
    return rows


# sheet -> (approach, price_basis, measure)
_TRENDS = {
    "cL CURRENT": ("production", "current", "level"),
    "CLCONTRIBUTION": ("production", "current", "share"),
    "cL gROWTH RATE": ("production", "current", "growth_yoy"),
    "cL CONSTANT": ("production", "constant", "level"),
    "K% contribution": ("production", "constant", "share"),
    "% growth rate": ("production", "constant", "growth_yoy"),
    "expend appro": ("expenditure", "current", "level"),
    "Expenditure KP": ("expenditure", "constant", "level"),
    "ExpendK growth r": ("expenditure", "constant", "growth_yoy"),
}


def _trends_2009_2018(path):
    """ZimStat 'GDP Trends 2009 to 2018': the previous 2012-base series in
    US$ million. Only the clean summary sheets (the others are stacked
    working blocks)."""
    xl = pd.ExcelFile(path)
    group = "ZimStat GDP Trends 2009-2018 (2012 base, US$)"
    rows = []
    for sheet, (ap, basis, measure) in _TRENDS.items():
        if sheet not in xl.sheet_names:
            continue
        df = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str)
        rows += _annual_rows(df, ap, basis, measure, "USD million", "2012 prices",
                             group)
    return rows


def parse(xlsx_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    xl = pd.ExcelFile(xlsx_path)
    rows = []
    for prefix, spec in _SHEETS:
        sheet = next((s for s in xl.sheet_names if s.strip().startswith(prefix)), None)
        if sheet:
            df = pd.read_excel(xlsx_path, sheet_name=sheet, header=None, dtype=str)
            group = "ZWL series 2019-2023" if prefix.replace(" ", "").startswith("Table2") else ""
            rows.extend(_parse_sheet(df, *spec, group=group))
    if not rows:
        raise ValueError("no GDP rows parsed from ZimStat workbook")
    for x in extras or []:
        name = re.split(r"[\\/]", x)[-1].lower()
        if name.startswith("gdp_tables_2019"):
            rows.extend(_tables_2019_2024(x))
        elif name.startswith("gdp_trends_2009"):
            rows.extend(_trends_2009_2018(x))
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "category_group", "period", "frequency",
         "measure", "price_basis", "unit"])
