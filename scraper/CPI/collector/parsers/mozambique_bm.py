"""Parser for the Banco de Moçambique (BM) CPI workbook (Tier 2, CB fallback).

Mozambique's NSO (INE) portal is auth-gated (Liferay 403), so we use the central
bank, which republishes INE's official CPI workbook without re-estimating it.
Sheet 'Publicação pag3 a 7' holds 'Quadro 8. Índices de Preços por Divisão e
Grupos', base 2023 = 100. Layout: col 0 = COICOP code, col 1 = label, then several
'Pond. <year>' weight columns, then a wide monthly index block whose header is
'Mon.YY' (e.g. 'Jan.16' … 'Jun.26').

We capture the 12 COICOP-1999 divisions (2-digit codes) + Total (code '0' → 00) as
index for every reported month; 3-digit sub-group codes are skipped.
"""
from __future__ import annotations
import re
import pandas as pd

_SHEET = "Publicação pag3 a 7"
_BASE_PERIOD = "2023 = 100"
_PT = {"jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05", "jun": "06",
       "jul": "07", "ago": "08", "set": "09", "out": "10", "nov": "11", "dez": "12"}
_HDR = re.compile(r"^([A-Za-z]{3})\.?\s*(\d{2})$")


def parse(xlsx_path: str) -> pd.DataFrame:
    try:
        df = pd.ExcelFile(xlsx_path).parse(_SHEET, header=None)
    except Exception:
        df = pd.ExcelFile(xlsx_path, engine="xlrd").parse(_SHEET, header=None)

    # period header: the row with the most 'Mon.YY' cells
    hdr_row, periods = None, {}
    for r in range(min(12, df.shape[0])):
        mp = {}
        for c in range(2, df.shape[1]):
            m = _HDR.match(str(df.iloc[r, c]).strip())
            mm = _PT.get(m.group(1).lower()) if m else None
            if mm:
                mp[c] = f"20{m.group(2)}-{mm}"
        if len(mp) > len(periods):
            hdr_row, periods = r, mp
    if len(periods) < 12:
        raise ValueError("Mozambique CPI: monthly index header not found")

    records, seen = [], set()
    for r in range(hdr_row + 1, df.shape[0]):
        code = str(df.iloc[r, 0]).strip()
        if code == "0":
            cc, label = "00", "Total (All items)"
        elif re.fullmatch(r"0[1-9]|1[0-2]", code):
            cc = code
            lab = str(df.iloc[r, 1]).strip()
            label = lab if lab and lab.lower() != "nan" else f"Division {code}"
        else:
            continue                              # 3-digit sub-group or noise
        if cc in seen:
            continue                              # first block = national índices (Quadro 8)
        seen.add(cc)
        for c, period in periods.items():
            v = df.iloc[r, c]
            if pd.notna(v) and isinstance(v, (int, float)):
                records.append((cc, label, period, "index", round(float(v), 4),
                                "Index", _BASE_PERIOD))

    if not records:
        raise ValueError("Mozambique CPI: no division rows parsed")
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
