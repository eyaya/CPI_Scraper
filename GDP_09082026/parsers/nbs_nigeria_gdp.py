"""Parser for the Nigeria NBS GDP quarterly report workbook (catalog 147).

This is the (post-2025-rebasing, base 2019) quarterly GDP report, PRODUCTION /
activity approach. It is a formatted report, not a tidy time series:

  * Sheet 'GDP_Curr_K_dfl_%Distrn' stacks five blocks down column A, each the
    46 activity sectors + aggregates against the same quarter columns:
      1 GDP at current basic prices (level, current)
      2 GDP at 2019 constant basic prices (level, constant)
      3 Implicit price deflators (deflator)
      4 % distribution at current prices (share, current)
      5 % distribution at constant prices (share, constant)
    Blocks 1/2 vs 4/5 share the same "…Basic Price" header text, so level vs
    share is told apart by value magnitude (levels are ₦-millions; shares ≤ 100).
  * Sheets 'nominal gdp growth rate %' / 'real gdp growth rate %' are single
    year-on-year growth tables (NBS headline GDP growth is YoY).

Columns run 2024 Q1..Q4, 2024 Total, 2025 Q1..Q4, 2025 Total, 2026 Q1 — the
"Total" columns are the published annual figures (emitted as annual periods).

Everything is taken as published by NBS (levels, deflator, % distribution, YoY
growth). Nothing is derived. The expenditure/income-approach file and the broad-
sector contribution sheet are separate NBS products, left for a later pass.
"""
from __future__ import annotations
import re
import pandas as pd

_SECTOR_RE = re.compile(r"^\s*(\d+)\.\s*(.+)$")     # "24. CONSTRUCTION" -> 24, name
_YEAR_RE = re.compile(r"(\d{4})")
_Q_RE = re.compile(r"Q\s*([1-4])", re.I)
_BLOCK_HEAD_RE = re.compile(r"gross domestic|implicit price", re.I)

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _norm(s: str) -> str:
    """Collapse the irregular internal whitespace NBS leaves in labels
    ('GDP  Current Market  Price') so substring matching is reliable."""
    return re.sub(r"\s+", " ", str(s)).strip()


def _is_gdp_total(l: str) -> bool:
    # headline totals: "GDP Current Market Price", "GDP Current Basic Price",
    # "GDP at 2019 constant price" (the real-growth total), etc.
    return "gdp" in l and "price" in l


def _approach(label: str) -> str:
    l = _norm(label).lower()
    if "net indirect tax" in l:
        return "production"
    if _is_gdp_total(l):
        return "aggregate"
    return "production"


def _row_texts(df: pd.DataFrame, i: int) -> list[str]:
    return ["" if pd.isna(df.iat[i, c]) else str(df.iat[i, c]).strip()
            for c in range(df.shape[1])]


def _find_period_map(df: pd.DataFrame) -> dict[int, tuple[str, str]]:
    """Locate the year row + quarter row and map each data column to
    (period, frequency). 'Total' columns become annual periods."""
    year_row = q_row = None
    for i in range(min(12, len(df))):
        texts = _row_texts(df, i)
        joined = " ".join(texts)
        if year_row is None and len(re.findall(r"\b20\d\d\b", joined)) >= 2:
            year_row = i
        if q_row is None and sum(bool(_Q_RE.fullmatch(t)) for t in texts) >= 2:
            q_row = i
    if year_row is None or q_row is None:
        raise ValueError("could not locate year/quarter header rows")

    yr, qr = _row_texts(df, year_row), _row_texts(df, q_row)
    pmap, cur_year = {}, None
    for c in range(1, df.shape[1]):
        m = _YEAR_RE.search(yr[c]) if yr[c] else None
        if m:
            cur_year = m.group(1)
        q = qr[c]
        if not cur_year or not q:
            continue
        if q.lower() == "total":
            pmap[c] = (cur_year, "annual")
        else:
            qm = _Q_RE.fullmatch(q)
            if qm:
                pmap[c] = (f"{cur_year}-Q{qm.group(1)}", "quarterly")
    return pmap


def _emit_rows(df, r, pmap, measure, basis, unit, base_period):
    label_raw = _norm(df.iat[r, 0])
    m = _SECTOR_RE.match(label_raw)
    if m:
        series_code, category = m.group(1), m.group(2).strip()
    else:
        series_code, category = "", label_raw
    out = []
    for c, (period, freq) in pmap.items():
        if c >= df.shape[1]:
            continue
        v = pd.to_numeric(df.iat[r, c], errors="coerce")
        if pd.isna(v):
            continue
        out.append({
            "approach": _approach(category), "category": category,
            "category_group": "", "series_code": series_code,
            "geography": "National", "period": period, "frequency": freq,
            "price_basis": basis, "seasonal_adjustment": "not_applicable",
            "measure": measure, "value": float(v), "unit": unit,
            "base_period": base_period,
        })
    return out


def _is_data_label(label: str) -> bool:
    s = _norm(label)
    if _SECTOR_RE.match(s):
        return True
    l = s.lower()
    return _is_gdp_total(l) or "net indirect tax" in l


def _parse_main(xlsx_path: str) -> list[dict]:
    df = pd.read_excel(xlsx_path, sheet_name="GDP_Curr_K_dfl_%Distrn",
                       header=None, dtype=str)
    pmap = _find_period_map(df)

    # split into blocks at each "Gross Domestic…/Implicit…" header row
    starts = [i for i in range(len(df))
              if isinstance(df.iat[i, 0], str) and _BLOCK_HEAD_RE.search(df.iat[i, 0])]
    starts.append(len(df))

    rows = []
    for b in range(len(starts) - 1):
        top, end = starts[b], starts[b + 1]
        header = str(df.iat[top, 0]).lower()
        data_idx = [i for i in range(top + 1, end)
                    if isinstance(df.iat[i, 0], str) and _is_data_label(df.iat[i, 0])]
        if not data_idx:
            continue
        basis = "constant" if "constant" in header else "current"
        if "implicit" in header:
            measure, basis, unit, base = "deflator", "not_applicable", "index", "2019=100"
        else:
            # level vs share: block-wide magnitude (levels are ₦-millions)
            mx = 0.0
            for i in data_idx:
                for c in pmap:
                    v = pd.to_numeric(df.iat[i, c], errors="coerce")
                    if pd.notna(v):
                        mx = max(mx, abs(v))
            if mx <= 1000:
                measure, unit, base = "share", "percent", ""
            else:
                measure, unit = "level", "NGN million"
                base = "2019 constant basic prices" if basis == "constant" else ""
        for i in data_idx:
            rows.extend(_emit_rows(df, i, pmap, measure, basis, unit, base))
    return rows


def _parse_growth(xlsx_path: str, sheet: str, basis: str) -> list[dict]:
    df = pd.read_excel(xlsx_path, sheet_name=sheet, header=None, dtype=str)
    pmap = _find_period_map(df)
    rows = []
    for i in range(len(df)):
        if isinstance(df.iat[i, 0], str) and _is_data_label(df.iat[i, 0]):
            rows.extend(_emit_rows(df, i, pmap, "growth_yoy", basis, "percent", ""))
    return rows


def parse(xlsx_path: str) -> pd.DataFrame:
    rows = []
    rows += _parse_main(xlsx_path)
    rows += _parse_growth(xlsx_path, "nominal gdp growth rate %", "current")
    rows += _parse_growth(xlsx_path, "real gdp growth rate %", "constant")
    if not rows:
        raise ValueError("no GDP rows parsed from Nigeria workbook")
    return pd.DataFrame.from_records(rows)[_OUT_COLS]
