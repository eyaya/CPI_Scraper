"""Parser for INS Côte d'Ivoire monthly merchandise-trade summaries (Tier 3 PDF / Tier 2 Excel).

The former Institut National de la Statistique (INS, now ANStat; Direction de la
Comptabilité Nationale, service Commerce Extérieur -- "SOURCE: INS/DCN/CE")
published one small file per year, "DONNEES DU COMMERCE EXTERIEUR EN <année>
(en milliards F CFA)": exports, imports, the trade balance and the coverage rate
for each month (www.ins.ci/documents/CommercesExterieurs/commerceExterieur<YYYY>
.pdf, 2018/2019 also as .xlsx/.xls). ins.ci is gone; the files are read from
Wayback id_ copies of ins.ci. The coverage rate (a ratio) is not collected.

In the PDFs a negative balance prints its minus sign as a separate text item
AFTER the figure ("35,73" then "-"): the sign is attached to the preceding figure
(verified: Oct 2011 exports 303,60 - imports 339,33 = -35,73).
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import row, to_number

_MONTHS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre",
           "octobre", "novembre", "decembre"]
_FLOWS = {"exportations": "export", "importations": "import", "balance commerciale": "balance",
          "balancecommerciale": "balance"}   # 2017/2018 files fuse the label
_NUM = re.compile(r"^-?\d{1,3}(?:[   ]\d{3})*(?:,\d+)?$")


def _fold(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def _parse_pdf(path: str) -> list[dict]:
    import fitz
    doc = fitz.open(path)
    try:
        text = "\n".join(p.get_text() for p in doc)
    finally:
        doc.close()
    m = re.search(r"COMMERCE EXTERIEUR EN (\d{4})\s*\(en (milliards|millions) F\s*CFA\)", text, re.I)
    if not m:
        return []
    year = int(m.group(1))
    mult = 1e9 if m.group(2).lower() == "milliards" else 1e6
    # "- 44,25" (2017): a minus detached from its figure by a space
    lines = [re.sub(r"^-\s+(?=\d)", "-", ln.strip()) for ln in text.split("\n")]
    # 2015 prints a 13th "TOTAL" column (the calendar year)
    has_total = any(_fold(ln) == "total" for ln in lines)
    out, flow, vals = [], None, []

    def emit(v, period, freq):
        out.append(row(tradeflow=flow, period=period, frequency=freq, value=v,
                       unit="XOF", unit_multiplier=mult,
                       price_basis={"export": "fob", "import": "cif"}.get(flow, ""),
                       series_code=f"INS commerce exterieur {year}"))

    def flush():
        if not flow or not vals:
            return
        if has_total and len(vals) == 13:
            for i, v in enumerate(vals[:12]):
                emit(v, f"{year}-{i + 1:02d}", "monthly")
            emit(vals[12], str(year), "annual")
        elif len(vals) <= 12 and not has_total:
            # a provisional file (2018) fills January onward and leaves later months blank
            for i, v in enumerate(vals):
                emit(v, f"{year}-{i + 1:02d}", "monthly")
        else:
            raise ValueError(f"Cote d'Ivoire {year}: {flow} has {len(vals)} figures "
                             f"({'with' if has_total else 'without'} a TOTAL column)")
    for ln in lines:
        f = _fold(ln)
        if f in _FLOWS:
            flush()
            flow, vals = _FLOWS[f], []
            continue
        if flow is None:
            continue
        if f.startswith("taux") or f.startswith("source"):
            flush()
            flow, vals = None, []
            continue
        if ln.strip() == "-" and vals:
            vals[-1] = -abs(vals[-1])
            continue
        if _NUM.match(ln):
            v = to_number(ln, decimal=",")
            if v is not None:
                vals.append(v)
    flush()
    return out


def _parse_xlsx(path: str) -> list[dict]:
    df = pd.read_excel(path, header=None, dtype=object)
    text = " ".join(str(x) for x in df.values.ravel() if x is not None and str(x) != "nan")
    m = re.search(r"COMMERCE EXTERIEUR EN (\d{4})\s*\(en (milliards|millions) F\s*CFA\)", text, re.I)
    if not m:
        return []
    year = int(m.group(1))
    mult = 1e9 if m.group(2).lower() == "milliards" else 1e6
    # the month header row
    hdr = None
    for i, r in df.iterrows():
        cells = [_fold(x) for x in r.values]
        if sum(c in _MONTHS for c in cells) >= 12:
            hdr = (i, {j: _MONTHS.index(c) + 1 for j, c in enumerate(cells) if c in _MONTHS})
            break
    if hdr is None:
        return []
    out = []
    for i, r in df.iterrows():
        lab = next((_fold(x) for x in r.values if isinstance(x, str) and _fold(x) in _FLOWS), None)
        if not lab:
            continue
        flow = _FLOWS[lab]
        for j, mo in hdr[1].items():
            v = r.values[j]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                continue
            v = to_number(v, decimal=",") if isinstance(v, str) else float(v)
            if v is None:
                continue
            out.append(row(tradeflow=flow, period=f"{year}-{mo:02d}", frequency="monthly", value=v,
                           unit="XOF", unit_multiplier=mult,
                           price_basis={"export": "fob", "import": "cif"}.get(flow, ""),
                           series_code=f"INS commerce exterieur {year}"))
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path] + list(extras or []):
        low = p.lower()
        if low.endswith(".pdf"):
            rows += _parse_pdf(p)
        elif low.endswith((".xlsx", ".xls")):
            rows += _parse_xlsx(p)
    df = pd.DataFrame(rows)
    # the Excel copy of a year repeats its PDF: identical keys collapse in validation
    return df
