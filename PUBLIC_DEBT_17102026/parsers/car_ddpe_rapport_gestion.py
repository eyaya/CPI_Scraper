"""Central African Republic — Ministère des Finances et du Budget, Direction
de la Dette Publique et Extérieure (DDPE), annual "Rapport de gestion de la
dette" (finances.gouv.cf), editions 2021-2025.

Each edition prints a three-year table of the year-end debt, "Source : DDPE":
  2021, 2022 editions  "Stock de la dette 20xx-20xx" -- Extérieur (Bilatérale,
                       Multilatérale), Intérieur, Total général;
  2023 edition         "Stock de la dette 2021-2023" -- Total stock, Stock
                       Extérieur, Stock intérieur;
  2024, 2025 editions  "Evolution de l'encours" -- dette extérieure, dette
                       intérieure, TOTAL.
FCFA milliards, year-end, annual periods.

THE EDITIONS DO NOT AGREE, AND ARE NOT CHAINED. "Stock" (2021-2023 editions)
and "encours" (2024-2025) are different measures -- the bulletins print
encours + arrears = stock -- and the editions reclassify: end-2022 external
debt is 488,84 in the 2022 edition and 322,26 in the 2023 edition on the same
total 768,59; the 2025 edition moves the IMF ECF (FEC) into external debt
("sans modifier le stock total"). So every edition keeps its OWN series code
("DDPE Rapport de gestion <edition>: <table>"), every vintage is kept as
published, and none overwrites another. Pick one edition's series for a
consistent window.

Checked per year (to 0,02): total = external + domestic; and in the 2021-2022
editions external = bilateral + multilateral. Decimals print with "," or "."
("530.18"); both are read.

PUBLISHED INCONSISTENCY, kept and pinned: the 2024 edition's 2022 column,
external 358,20 + domestic 262,71 = 620,91 against TOTAL 621,21 (+0,30).
"""
from __future__ import annotations

import os
import re

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber

_CAPTIONS = [
    re.compile(r"Tableau \d+ : Stock de la dette (20\d\d)-(20\d\d)"),
    re.compile(r"Tableau \d+ ?: Evolution de l[’']encours \((?:en milliards FCFA|Mds FCFA)\)"),
]
_NUM = r"\d{1,3}(?: \d{3})*[.,]\d+"
# (edition, year) -> printed total minus (external + domestic)
_KNOWN_GAPS = {("2024", "2022"): 0.30}
# printed label -> (role in the checks)
_ROLES = {
    "Total général": "total", "Total stock": "total", "TOTAL": "total",
    "Extérieur": "ext", "Stock Extérieur": "ext", "dette extérieure": "ext",
    "Intérieur": "dom", "Stock intérieur": "dom", "dette intérieure": "dom",
    "Bilatérale": "bil", "Multilatérale": "mul",
}


def _f(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _edition(path: str, first_page: str) -> str:
    """From the descriptor's save_as name (DDPE_rapport_gestion_<YYYY>.pdf);
    most covers do not print the edition year in their text layer."""
    m = re.search(r"rapport_gestion_(20\d\d)", os.path.basename(path))
    if not m:
        m = re.search(r"Rapport de [Gg]estion de la [Dd]ette[^0-9]{0,10}(20\d\d)", first_page)
    if not m:
        raise ValueError(f"DDPE RG: edition year not found in {path}")
    return m.group(1)


def _read(path: str) -> list[dict]:
    with fitz.open(path) as doc:
        quick = [p.get_text() for p in doc]
    edition = _edition(path, " ".join(" ".join(quick[:3]).split()))
    for k, qt in enumerate(quick):
        if not any(c.search(" ".join(qt.split())) for c in _CAPTIONS) or "...." in qt:
            continue
        with pdfplumber.open(path) as pdf:
            t = pdf.pages[k].extract_text() or ""
        cap = next((m for c in _CAPTIONS for m in [c.search(t)] if m), None)
        if cap is None:
            continue
        body = t[cap.end():t.find("Source", cap.end())]
        lines = body.splitlines()
        hdr = next(ln for ln in lines if len(re.findall(r"\b20\d\d\b", ln)) == 3)
        years = re.findall(r"\b(20\d\d)\b", hdr)
        got = {}
        for ln in lines[lines.index(hdr) + 1:]:
            lab = re.split(r"\s+\d", ln, 1)[0].strip()
            if lab in _ROLES and lab not in got:
                vals = re.findall(_NUM, ln[len(lab):])
                if len(vals) != 3:
                    raise ValueError(f"DDPE RG {edition} {lab}: {vals}")
                got[lab] = [_f(v) for v in vals]
        role = {_ROLES[l]: v for l, v in got.items()}
        if not {"total", "ext", "dom"} <= set(role):
            raise ValueError(f"DDPE RG {edition}: rows {sorted(got)}")
        for j, y in enumerate(years):
            gap = role["total"][j] - role["ext"][j] - role["dom"][j]
            if abs(gap - _KNOWN_GAPS.get((edition, y), 0.0)) > 0.02:
                raise ValueError(f"DDPE RG {edition} {y}: total - (external + domestic) "
                                 f"= {gap:.2f}")
            if "bil" in role and abs(role["bil"][j] + role["mul"][j] - role["ext"][j]) > 0.02:
                raise ValueError(f"DDPE RG {edition} {y}: bilateral + multilateral != external")
        table = " ".join(cap.group(0).split(":", 1)[1].split())
        code = f"DDPE Rapport de gestion {edition}: {table}"
        return [{"component": lab, "period": y, "frequency": "annual", "measure": "stock",
                 "value": v, "unit": "FCFA milliards", "series_code": code}
                for lab, vals in got.items() for y, v in zip(years, vals)]
    raise ValueError(f"DDPE RG: no stock table in {path}")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        rows += _read(p)
    return pd.DataFrame(rows)
