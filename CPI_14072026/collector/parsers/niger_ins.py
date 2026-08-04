"""Parser for the Niger INS IHPC monthly note PDF (Tier 3).

Niger (INS) publishes the WAEMU harmonised CPI (IHPC, base 2023 = 100) as a
monthly PDF. Its 'Tableau 1' national table reads as text, one row per
COICOP-2018 division plus an 'Indice global' all-items row:

  10 000)  Juin-  Mars-  Avril-  Mai-  Juin-   1 mois  3 mois  1 an
  Indice global  10 000  105,2  98,1  98,8  100,3  102,1   1,8  4,0  -2,9
  1 Produits alimentaires …  4 701  110,0  94,8  95,9  99,4  102,8   3,4  8,5  -6,6

Codes are single- or double-digit (1..13); the all-items row is 'Indice global'.
The column headers don't carry the year, so the report month is read from the
title ('… juin 2026 …'). Each row is <code> <label> <weight> <indices…> then
the 1-/3-/12-month variations, so the current index is nums[-4], MoM nums[-3],
YoY nums[-1] — we emit index + inflation_mom + inflation_yoy for the report
month. Weights carry thousands spaces ('4 701'); French comma decimals.
"""
from __future__ import annotations
import re
import unicodedata
import pdfplumber
import pandas as pd

from .togo_inseed import _DIVISIONS      # Roman -> (code, French label)

_BASE_PERIOD = "2023 = 100"
_CODE_LABEL = {code: label for code, label in _DIVISIONS.values()}
_FULL_MONTHS = {"janvier": "01", "fevrier": "02", "mars": "03", "avril": "04",
                "mai": "05", "juin": "06", "juillet": "07", "aout": "08",
                "septembre": "09", "octobre": "10", "novembre": "11",
                "decembre": "12"}
_TITLE = re.compile(
    r"(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|"
    r"octobre|novembre|d[eé]cembre)\s+(20\d\d)", re.IGNORECASE)
_NUM = r"-?\d+(?:,\d+)?"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _nums(s: str) -> list[float]:
    s = re.sub(r"(\d)\s(\d{3})(?!,)", r"\1\2", s)   # join thousands spaces
    return [float(t.replace(",", ".")) for t in re.findall(_NUM, s)]


def _report_period(text: str) -> str:
    m = _TITLE.search(text)
    if not m:
        raise ValueError("Niger IHPC: report month not found in title")
    return f"{m.group(2)}-{_FULL_MONTHS[_norm(m.group(1))]}"


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    period = _report_period(text)

    rows = {}   # code -> (label, index, mom, yoy)
    for ln in text.splitlines():
        s = ln.strip()
        m = re.match(r"^(\d{1,2})\s+(.+)$", s)
        if m and 1 <= int(m.group(1)) <= 13:
            code, nums = f"{int(m.group(1)):02d}", _nums(m.group(2))
            label = _CODE_LABEL.get(code, "")
        elif re.match(r"indice global|indice national|ensemble", s, re.I):
            code, nums, label = "00", _nums(s), "All items"
        else:
            continue
        if code in rows or len(nums) < 8:          # weight + indices + 3 variations
            continue
        rows[code] = (label, nums[-4], nums[-3], nums[-1])

    missing = [c for c, _ in _DIVISIONS.values() if c not in rows]
    if "00" not in rows or missing:
        raise ValueError(f"Niger IHPC table incomplete: got {sorted(rows)}")

    records = []
    for code, (label, idx, mom, yoy) in rows.items():
        records.append((code, label, period, "index", idx, "Index", _BASE_PERIOD))
        records.append((code, label, period, "inflation_mom", mom, "percent", ""))
        records.append((code, label, period, "inflation_yoy", yoy, "percent", ""))

    out = pd.DataFrame.from_records(
        records,
        columns=["coicop_code", "coicop_label", "period", "measure", "value",
                 "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
