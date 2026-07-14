"""Parser for the INE Angola IPC time-series workbook (Tier 2, Excel behind a SPA).

INE's 'Base de Dados de Séries Temporais' exposes, for inflation, a single
national headline series — the all-items year-on-year change ('Variação
Homóloga') — as a two-column sheet:

  Período           Variação Homóloga
  Dezembro - 2015   12,09
  …                 …
  Junho - 2026      10,11

INE does not publish a COICOP-division breakdown in this database (that lives in
separate monthly bulletins), so we capture what is reported here: the national
all-items YoY inflation (code 00) for every month. Decimal commas and stray extra
dashes in the period labels are tolerated.
"""
from __future__ import annotations
import re
import pandas as pd

_PT = {"janeiro": "01", "fevereiro": "02", "marco": "03", "março": "03",
       "abril": "04", "maio": "05", "junho": "06", "julho": "07", "agosto": "08",
       "setembro": "09", "outubro": "10", "novembro": "11", "dezembro": "12"}
_ROW = re.compile(r"([A-Za-zçãáéíóúÇ]+)\s*-+\s*(20\d\d)")


def parse(xlsx_path: str) -> pd.DataFrame:
    df = pd.ExcelFile(xlsx_path).parse("Sheet1", header=None)
    records = []
    for _, row in df.iterrows():
        m = _ROW.search(str(row.iloc[0]))
        mm = _PT.get(m.group(1).lower()) if m else None
        if not mm:
            continue
        try:
            val = float(str(row.iloc[1]).strip().replace(",", "."))
        except ValueError:
            continue
        period = f"{m.group(2)}-{mm}"
        records.append(("00", "All items", period, "inflation_yoy", round(val, 4), "percent", ""))

    if not records:
        raise ValueError("Angola IPC: no monthly rows parsed")
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
