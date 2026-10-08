"""Parser for the INE Cabo Verde IPC series workbook (Tier 2).

INE publishes the CPI (IPC, série 2018 = 100) as a 'Principais Quadros' workbook
covering the WHOLE series rather than a single month — 'Séries IPC2018 <Mês>
<Ano>.xlsx', refreshed each month. 'Tabela 1' is the national index by CCIO class:

  CCIO 2018  DESIGNAÇÃO                       2019                    2020   …
                                              Jan     Fev     Mar     Jan    …
  00         TOTAL                          100.31  100.19  100.45   …
  01         PRODUTOS ALIMENTARES E BEBIDAS NÃO ALCOÓLICAS …

so the code column gives the division code directly (00 = TOTAL plus classes
01..12) and one file yields every month from January 2019 to the latest.

The month header is written two ways in the same row — a Portuguese abbreviation
under a year banner for the early years, a real date cell for the later ones — so
each column takes its period from the date cell when there is one and from the
nearest banner year otherwise. Columns for months not yet published are present
but empty and drop out with their blank values.

Index levels only. The workbook's 'Tabela 5' rate is the TWELVE-MONTH MOVING
AVERAGE ('taxa de inflação', 1,4% for July 2026 against a year-on-year 0,4%),
which is neither of the schema's rate measures, so it is not emitted rather than
mislabelled. 'Tabela 2'/'Tabela 3' (groups and sub-groups) and 'Tabela 4'
(special aggregates) would add depth later. Portuguese labels kept as published.
"""
from __future__ import annotations
import datetime as dt
import re
import unicodedata
import pandas as pd

_SHEET = "Tabela 1"
_GEOGRAPHY = "National"
_MONTHS = {"jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05",
           "jun": "06", "jul": "07", "ago": "08", "set": "09", "out": "10",
           "nov": "11", "dez": "12"}
_BASE = re.compile(r"(\d{4})\s*=\s*100")
_CODE = re.compile(r"^\d{1,2}$")


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def _year(v) -> int | None:
    if pd.isna(v):                       # NaT is a Timestamp: check before .year
        return None
    if isinstance(v, (dt.datetime, pd.Timestamp)):
        return int(v.year)
    if isinstance(v, (int, float)) and pd.notna(v) and 2000 < float(v) < 2100:
        return int(v)
    m = re.fullmatch(r"(20\d\d)(?:\.0)?", str(v).strip()) if pd.notna(v) else None
    return int(m.group(1)) if m else None


def parse(xlsx_path: str) -> pd.DataFrame:
    book = pd.read_excel(xlsx_path, sheet_name=None, header=None)
    if _SHEET not in book:
        raise ValueError(f"Cabo Verde IPC: sheet '{_SHEET}' not in the workbook")

    base = None
    for sheet in book.values():
        for v in sheet.values.ravel():
            m = _BASE.search(str(v)) if pd.notna(v) else None
            if m:
                base = f"{m.group(1)} = 100"
                break
        if base:
            break
    if not base:
        raise ValueError("Cabo Verde IPC: base period not stated in the workbook")

    raw = book[_SHEET]
    hdr = next((i for i in raw.index
                if any(_norm(v).startswith("ccio") for v in raw.iloc[i])), None)
    if hdr is None:
        raise ValueError("Cabo Verde IPC: 'CCIO' header row not found")
    code_col = next(c for c in raw.columns if _norm(raw.iat[hdr, c]).startswith("ccio"))
    label_col = next(c for c in raw.columns
                     if _norm(raw.iat[hdr, c]).startswith("designacao"))

    # month columns: a date cell dates itself, a 'Jan' takes the last banner year
    periods, year = {}, None
    for col in raw.columns:
        year = _year(raw.iat[hdr, col]) or year
        cell = raw.iat[hdr + 1, col]
        if pd.isna(cell):
            continue                     # a month not yet published
        if isinstance(cell, (dt.datetime, pd.Timestamp)):
            periods[col] = f"{cell.year}-{cell.month:02d}"
        elif _norm(cell)[:3] in _MONTHS and year:
            periods[col] = f"{year}-{_MONTHS[_norm(cell)[:3]]}"
    if len(periods) < 12:
        raise ValueError(f"Cabo Verde IPC: {len(periods)} dated month columns found")

    records, seen = [], set()
    for i in range(hdr + 2, len(raw)):
        code_cell = raw.iat[i, code_col]
        if pd.isna(code_cell):
            continue
        code = str(code_cell).strip().split(".")[0]
        if not _CODE.fullmatch(code):
            continue
        code = code.zfill(2)
        if code in seen:
            continue
        seen.add(code)
        label = re.sub(r"\s+", " ", str(raw.iat[i, label_col])).strip()
        for col, period in periods.items():
            v = pd.to_numeric(raw.iat[i, col], errors="coerce")
            if pd.notna(v):
                records.append((code, label, period, "index",
                                round(float(v), 4), "Index", base))

    if "00" not in seen or len(seen) < 13:
        raise ValueError(f"Cabo Verde IPC: got classes {sorted(seen)}, expected 00..12")

    out = pd.DataFrame.from_records(
        records,
        columns=["coicop_code", "coicop_label", "period", "measure", "value",
                 "unit", "base_period"])
    out["geography"] = _GEOGRAPHY
    out["frequency"] = "monthly"
    return out
