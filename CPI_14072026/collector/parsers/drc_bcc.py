"""Parser for the Banque Centrale du Congo (DRC) annual CPI workbook (Tier 2, PARTIAL).

The DRC's national statistics institute (INS-RDC) is not reachable, so we fall back
to the central bank (BCC), whose 'ipc_annuel_bcc.xlsx' publishes the national
all-items CPI as an **annual** series: one row per year with the price index
(base 2012 = 100) and the year-on-year inflation ('taux en glissement annuel').

This is a documented PARTIAL capture: national all-items only, ANNUAL frequency,
and it ends in 2020 (the file has not been updated since). Annual figures are dated
to year-end (YYYY-12) to fit the monthly period schema; frequency is 'annual'. The
COICOP-division breakdown is not published in this file.
"""
from __future__ import annotations
import re
import pandas as pd

_BASE_PERIOD = "2012 = 100"


def parse(xlsx_path: str) -> pd.DataFrame:
    df = pd.ExcelFile(xlsx_path).parse("Prix  Annuel (2)", header=None)
    # locate the header row ('ANNEE' + 'Indice des prix') then read year rows
    hdr = next((r for r in range(df.shape[0])
                if "annee" in str(df.iloc[r, 0]).strip().lower()), None)
    if hdr is None:
        raise ValueError("DRC BCC: 'ANNEE' header row not found")

    records = []
    for r in range(hdr + 1, df.shape[0]):
        yr = str(df.iloc[r, 0]).strip()
        if not re.fullmatch(r"(19|20)\d\d", yr):
            continue
        period = f"{yr}-12"                        # annual value, dated to year-end
        idx = df.iloc[r, 1]                        # Indice des prix (base 2012=100)
        if pd.notna(idx) and isinstance(idx, (int, float)) and idx >= 1:
            records.append(("00", "All items", period, "index", round(float(idx), 4),
                            "Index", _BASE_PERIOD))
        yoy = df.iloc[r, 5]                        # taux en glissement annuel (YoY %)
        if pd.notna(yoy) and isinstance(yoy, (int, float)):
            records.append(("00", "All items", period, "inflation_yoy", round(float(yoy), 4),
                            "percent", ""))

    if not records:
        raise ValueError("DRC BCC: no annual rows parsed")
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "annual"
    return out
