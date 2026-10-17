"""Parser for the INE São Tomé e Príncipe IPC monthly workbook (Tier 2).

INE publishes the CPI (IPC, base 2014 = 100) as a small Excel workbook per
month, 'Resultado_IPC_<Mês><Ano>_Publicação1.xls' — one sheet, one row per
COICOP-1999 group, one column per month of the current year plus December of the
previous one, so a single workbook carries the year to date rather than a single
month:

                       Ponderação  Base 1995 | ANO 2025 | ANO 2026 …
  GRUPOS DE PRODUTOS                          Dezembro   Janeiro  …  Julho
  IPC GERAL             100.00076             289.399…   289.920…   302.355…
  01-Produtos Alimentares, bebidas não Alc…    333.569…   333.937…   346.553…

The year lives in a banner row ABOVE the month names and spans its columns, so
each month column takes the nearest banner year at or to its left. Group codes
are the '01-' … '12-' prefixes of the labels (spacing varies between issues).

Below the group block, a 'Por memória' section repeats the general index with
its rates: 'Variação em cadeia' (month on month) and 'Taxa inflação homóloga'
(year on year), both for every month shown. We emit index for all groups and
those two rates for the all-items series. 'Taxa inflação acumulada' (the
year-to-date rate) has no measure in the CPI schema and is dropped, as is the
legacy empty 'Base 1995' column. Portuguese labels kept as published, minus the
code prefix the code column already carries.
"""
from __future__ import annotations
import re
import unicodedata
import pandas as pd

_GEOGRAPHY = "National"
_ALL_ITEMS = "IPC GERAL"
_MONTHS = {"janeiro": "01", "fevereiro": "02", "marco": "03", "abril": "04",
           "maio": "05", "junho": "06", "julho": "07", "agosto": "08",
           "setembro": "09", "outubro": "10", "novembro": "11",
           "dezembro": "12"}
_CODE = re.compile(r"^(\d{2})\s*[-.]\s*(.+)$")
_BASE = re.compile(r"base\s*\(?\s*(\d{4})\s*=\s*100", re.I)
_YEAR = re.compile(r"ano\s*(20\d\d)", re.I)
# 'Por memória' rate rows -> the measure they carry
_RATES = {"variacaoemcadeia": "inflation_mom", "taxainflacaohomologa": "inflation_yoy"}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def _key(s) -> str:
    return re.sub(r"[^a-z]", "", _norm(s))


def parse(xls_path: str) -> pd.DataFrame:
    raw = pd.read_excel(xls_path, sheet_name=0, header=None)

    base = _BASE.search(" ".join(str(v) for v in raw.values.ravel() if pd.notna(v)))
    if not base:
        raise ValueError("São Tomé IPC: base period not stated in the workbook")
    base_period = f"{base.group(1)} = 100"

    head = next((i for i in raw.index
                 if any(_key(v) == "gruposdeprodutos" for v in raw.iloc[i])), None)
    if head is None:
        raise ValueError("São Tomé IPC: 'GRUPOS DE PRODUTOS' header row not found")
    label_col = next(c for c in raw.columns
                     if _key(raw.iat[head, c]) == "gruposdeprodutos")

    # month columns, each dated by the nearest 'ANO <year>' banner to its left
    banners = raw.iloc[head - 1] if head else None
    periods, year = {}, None
    for col in raw.columns:
        if banners is not None and pd.notna(banners[col]):
            y = _YEAR.search(str(banners[col]))
            if y:
                year = int(y.group(1))
        mon = _MONTHS.get(_norm(raw.iat[head, col]))
        if mon and year:
            periods[col] = f"{year}-{mon}"
    if len(periods) < 2:
        raise ValueError(f"São Tomé IPC: {len(periods)} dated month columns found")

    records, seen = [], set()
    for i in range(head + 1, len(raw)):
        label = raw.iat[i, label_col]
        if pd.isna(label):
            continue
        text = re.sub(r"\s+", " ", str(label)).strip()
        m = _CODE.match(text)
        if m:
            code, name = f"{int(m.group(1)):02d}", m.group(2).strip()
        elif _key(text) == _key(_ALL_ITEMS) and "00" not in seen:
            code, name = "00", _ALL_ITEMS
        elif _key(text) in _RATES:
            measure = _RATES[_key(text)]
            for col, period in periods.items():
                v = pd.to_numeric(raw.iat[i, col], errors="coerce")
                if pd.notna(v):
                    records.append(("00", _ALL_ITEMS, period, measure,
                                    round(float(v), 4), "percent", ""))
            continue
        else:
            continue
        if code in seen:                 # 'Por memória' repeats the general index
            continue
        seen.add(code)
        for col, period in periods.items():
            v = pd.to_numeric(raw.iat[i, col], errors="coerce")
            if pd.notna(v):
                records.append((code, name, period, "index",
                                round(float(v), 4), "Index", base_period))

    if "00" not in seen or len(seen) < 13:
        raise ValueError(f"São Tomé IPC: got groups {sorted(seen)}, expected 00..12")

    out = pd.DataFrame.from_records(
        records,
        columns=["coicop_code", "coicop_label", "period", "measure", "value",
                 "unit", "base_period"])
    out["geography"] = _GEOGRAPHY
    out["frequency"] = "monthly"
    return out
