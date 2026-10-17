"""Mali — Direction Générale de la Dette Publique (DGDP), Ministère de
l'Economie et des Finances, half-yearly "Bulletin Statistique de la Dette
Publique" (finances.ml/dette-publique/bulletins).

WHAT IS READ: only the "A.3 Chiffres clés de la dette publique" box, the one
part of these bulletins with a text layer -- the stock tables are images (no
OCR), and the two 2025 bulletins open with no readable page. For the
bulletin's own date ("A fin juin 2026"):
  Taux d'endettement public / extérieur (en % du PIB)   -> share_of_gdp
  Part dette extérieure / intérieure (en % de l'encours total) -> share
Average life and interest rate are not debt figures and are not read.
Period: end-June -> YYYY-Q2 (quarterly); end-December -> YYYY (annual).
Checked: the two shares sum to 100 (to 0,1).

PUBLISHED FOOTNOTE MARKER: the 1st-semester 2022 bulletin prints "52,21",
the ratio 52,2 followed by footnote "1" ("1 Ce taux est défini sur la base du
PIB en fin d'année 2021"); when that footnote is present the marker is
dropped.

Coverage: the bulletins do not restate a perimeter in the key-figure box;
recorded as the DGDP's public debt, beside mali.yaml (INSTAT yearbook stocks).
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd

_MOIS = {"juin": ("Q2", "quarterly"), "décembre": (None, "annual"), "decembre": (None, "annual")}
_ROWS = [
    (r"Taux d’endettement public \(en % du PIB\)", "Dette publique", "share_of_gdp"),
    (r"Taux d’endettement extérieur ?\(en % du PIB\)", "Dette extérieure", "share_of_gdp"),
    (r"Part dette extérieure \(en % de l’encours total\)", "Dette extérieure", "share"),
    (r"Part dette intérieure \(en % de l’encours total\)", "Dette intérieure", "share"),
]


def _read(path: str) -> list[dict]:
    with fitz.open(path) as doc:
        t = " ".join(" ".join(p.get_text() for p in doc).split())
    m = re.search(r"Chiffres cl[ée]s de la dette publique Rubrique A fin (\w+) (20\d\d)", t, re.I)
    if not m:
        raise ValueError(f"DGDP Mali: no key-figure box in {path}")
    q, freq = _MOIS[m.group(1).lower()]
    period = f"{m.group(2)}-{q}" if q else m.group(2)
    box = t[m.end():m.end() + 700]
    footnote = re.search(r"\b1 Ce taux est défini", t) is not None
    out, vals = [], {}
    for pat, comp, meas in _ROWS:
        r = re.search(pat + r" (\d{1,3},\d{1,2})", box)
        if not r:
            raise ValueError(f"DGDP Mali {period}: {pat!r} not found")
        s = r.group(1)
        if footnote and meas == "share_of_gdp" and comp == "Dette publique" \
                and re.fullmatch(r"\d+,\d1", s):
            s = s[:-1]
        v = float(s.replace(",", "."))
        vals[(comp, meas)] = v
        out.append({"component": comp, "period": period, "frequency": freq,
                    "measure": meas, "value": v, "unit": "percent",
                    "series_code": "DGDP Bulletin: chiffres clés"})
    if abs(vals[("Dette extérieure", "share")] + vals[("Dette intérieure", "share")] - 100) > 0.1:
        raise ValueError(f"DGDP Mali {period}: shares do not sum to 100")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        rows += _read(p)
    return pd.DataFrame(rows)
