"""Equatorial Guinea — INEGE Anuario Estadístico, chapter 13.2 "Financiación
estadística y deuda pública", table "Dinámica general de la deuda pública".

PUBLISHER: INEGE (the statistics office), reprinting the figures of the Caja
Autónoma de Amortización de la Deuda Pública (CAADP), the State's debt-
management agency, credited under the table ("Fuente: Caja Autónoma de
Amortización de la Deuda Pública"). Both are official national bodies; the
INEGE yearbook is the published, reachable document (the Ministry of Finance
and CAADP publish no debt bulletin on a reachable host).

COVERAGE: "Deuda pública" as the CAADP defines it -- external (bilateral,
multilateral) + domestic; the table names no wider perimeter.

WHAT IS READ: end-year stocks for the five years each edition prints, in MIL
MILLONES DE F.CFA (milliards FCFA): public debt, external debt and its
bilateral / multilateral split, domestic debt; and "Deuda Pública (% PIB)" as
printed (share_of_gdp). The debt-SERVICE table beside it is a flow, which this
schema does not hold.

EDITIONS DIFFER IN FORM: the 2023 Anuario capitalises the caption, heads
the table "Concepto", prints "( % PIB)" and drops the thousands dot in one
cell ("2041,9"). And they REVISE: 2021 public debt is 2.876,9 in the 2023
edition and 3.160,6 in the 2026 edition.

The 2026 Anuario (2021-2025) is the primary; the 2023 Anuario
(2018-2022), if passed as an extra, adds the earlier years. Where two editions
print the same year, the NEWER edition wins (read first; later duplicates are
dropped).

NUMBER FORMAT is Spanish: "3.160,6" = 3 160,6 (dot thousands, comma decimal).

CHECKS: public = external + domestic; external = bilateral + multilateral
(within 0,15).

CROSS-CHECK (Anuario 2026): public debt 2025 2.433,3 (32,6% of GDP); external
476,0 (bilateral 401,0); domestic 1.957,2; 2021 public debt 3.160,6.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber

_COV = "Deuda pública (CAADP): externa + interna"
# The 2023 edition capitalises "Deuda Pública" and says "Miles de millones".
_CAP = re.compile(r"Dinámica general de la deuda pública \((?:mil|miles de) millones de F\.CFA\)", re.I)
_NUM = r"\d{1,3}(?:\.\d{3})+,\d+|\d+,\d+"   # "2041,9" (2023) lacks the dot
_ROWS = [("Deuda Pública (% PIB)", "Deuda pública", "share_of_gdp", "percent"),
         ("Deuda Pública ( % PIB)", "Deuda pública", "share_of_gdp", "percent"),
         ("Deuda Pública", "Deuda pública", "stock", "FCFA milliards"),
         ("Deuda Externa", "Deuda externa", "stock", "FCFA milliards"),
         ("Bilateral", "Deuda externa: bilateral", "stock", "FCFA milliards"),
         ("Multilateral", "Deuda externa: multilateral", "stock", "FCFA milliards"),
         ("Deuda Interna", "Deuda interna", "stock", "FCFA milliards")]


def _f(t):
    return float(t.replace(".", "").replace(",", "."))


def _one(path):
    # The yearbook runs to 400+ pages; locate the page with PyMuPDF (fast),
    # then read that one page with pdfplumber.
    with fitz.open(path) as doc:
        idx = next((i for i, pg in enumerate(doc)
                    if _CAP.search(pg.get_text())
                    and "...." not in pg.get_text()), None)
    text = None
    if idx is not None:
        with pdfplumber.open(path) as pdf:
            text = pdf.pages[idx].extract_text() or ""
    if text is None:
        raise ValueError(f"INEGE: debt table not found in {path}")
    body = text[_CAP.search(text).end():text.index("Fuente", _CAP.search(text).end())]
    lines = [ln.strip() for ln in body.splitlines()]
    years = re.findall(r"20\d\d", next(ln for ln in lines
                                       if ln.startswith(("Stock de la Deuda", "Concepto"))))
    got = {}
    for i, ln in enumerate(lines):
        for label, comp, meas, unit in _ROWS:
            if ln.startswith(label) and (comp, meas) not in got:
                rest = ln[len(label):]
                if label == "Deuda Pública" and rest.lstrip().startswith("("):
                    continue
                nums = re.findall(_NUM, rest)
                # The 2023 edition wraps a row's values onto following lines
                # that carry only numbers; take them until the row is full.
                k = i + 1
                while len(nums) < len(years) and k < len(lines) and                         re.fullmatch(rf"(?:(?:{_NUM})\s*)+", lines[k]):
                    nums += re.findall(_NUM, lines[k])
                    k += 1
                if len(nums) != len(years):
                    raise ValueError(f"INEGE {label!r}: {nums} for {years}")
                got[(comp, meas)] = (unit, [_f(x) for x in nums])
                break
    if len(got) != len(_ROWS) - 1:
        raise ValueError(f"INEGE: read {sorted(got)}")
    s = {c: v for (c, m), (_, v) in got.items() if m == "stock"}
    for j in range(len(years)):
        if abs(s["Deuda pública"][j] - s["Deuda externa"][j] - s["Deuda interna"][j]) > 0.15:
            raise ValueError(f"INEGE {years[j]}: public != external + domestic")
        if abs(s["Deuda externa"][j] - s["Deuda externa: bilateral"][j]
               - s["Deuda externa: multilateral"][j]) > 0.15:
            raise ValueError(f"INEGE {years[j]}: external != bilateral + multilateral")
    out = []
    for (comp, meas), (unit, vals) in got.items():
        for y, v in zip(years, vals):
            out.append(dict(coverage=_COV, component=comp, period=y,
                            frequency="annual", measure=meas, value=v,
                            unit=unit, series_code="INEGE AEGE deuda"))
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        rows += _one(p)
    df = pd.DataFrame(rows)
    return df.drop_duplicates(["component", "period", "measure"], keep="first")
