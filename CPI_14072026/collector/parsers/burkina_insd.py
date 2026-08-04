"""Parser for the Burkina Faso INSD IHPC monthly note, Excel edition (Tier 2).

INSD publishes the WAEMU harmonised CPI (IHPC, base 2023 = 100) as the monthly
note exported to Excel (.xlsx or .xls). Its 'page1' sheet is 'Tableau 1', the
same UEMOA division table as the Togo PDF but in a clean grid:

  <Roman> | Libellé | Pondération | <index …> <index current> | Contribution | /1mois | /3mois | /12mois
          | INDICE GLOBAL | 10000 | 104.9 … 105.0 | 1.3 | 1.33 | 1.33 | 1.52
  I       | Produits alimentaires … | 2904 | … 109.2 | …

So we read, per COICOP-2018 division (Roman I..XIII) and 'INDICE GLOBAL' (All
items, 00): the current-month index (the last dated column) plus the '/1mois'
(MoM) and '/12mois' (YoY) variations -> index + inflation_mom + inflation_yoy.
One workbook = one month; history accumulates across runs. Reads both .xlsx and
.xls via pandas. Roman->code/label map is shared with the Togo PDF parser.
"""
from __future__ import annotations
import datetime as dt
import pandas as pd

from .togo_inseed import _DIVISIONS      # Roman numeral -> (code, French label)

_BASE_PERIOD = "2023 = 100"


def _is_date(c) -> bool:
    return isinstance(c, (dt.datetime, dt.date, pd.Timestamp))


def _period(ts) -> str:
    return f"{ts.year}-{ts.month:02d}"


def parse(xlsx_path: str) -> pd.DataFrame:
    xls = pd.ExcelFile(xlsx_path)          # engine auto-selected by extension
    for sheet in xls.sheet_names:
        raw = xls.parse(sheet, header=None)
        grid = raw.values.tolist()
        hi = next((i for i, row in enumerate(grid)
                   if sum(_is_date(c) for c in row) >= 3), None)
        if hi is None:
            continue
        hdr = grid[hi]
        label_col = next((j for j, c in enumerate(hdr)
                          if isinstance(c, str) and "libell" in c.lower()), None)
        date_cols = {j: c for j, c in enumerate(hdr) if _is_date(c)}
        if label_col is None or not date_cols:
            continue
        cur_col = max(date_cols, key=lambda j: date_cols[j])   # latest month = report
        mom_col = next((j for j, c in enumerate(hdr) if isinstance(c, str) and "1mois" in c.replace(" ", "").lower()), None)
        yoy_col = next((j for j, c in enumerate(hdr) if isinstance(c, str) and "12mois" in c.replace(" ", "").lower()), None)

        period = _period(date_cols[cur_col])
        records = []
        for row in grid[hi + 1:]:
            roman = str(row[0]).strip() if row[0] is not None else ""
            lab = row[label_col] if label_col < len(row) else None
            if isinstance(lab, str) and "indice global" in lab.lower():
                code, label = "00", "All items"
            elif roman in _DIVISIONS:
                code, label = _DIVISIONS[roman]
            else:
                continue

            def add(col, measure, unit, base):
                if col is not None and col < len(row):
                    v = row[col]
                    if isinstance(v, (int, float)) and pd.notna(v):
                        records.append((code, label, period, measure, round(float(v), 4), unit, base))
            add(cur_col, "index", "Index", _BASE_PERIOD)
            add(mom_col, "inflation_mom", "percent", "")
            add(yoy_col, "inflation_yoy", "percent", "")

        codes = {c for c, *_ in records}
        if "00" in codes and len(codes) >= 14:
            out = pd.DataFrame.from_records(
                records,
                columns=["coicop_code", "coicop_label", "period", "measure",
                         "value", "unit", "base_period"])
            out["geography"] = "National"
            out["frequency"] = "monthly"
            return out

    raise ValueError("Tableau 1 (division index table) not found in INSD workbook")
