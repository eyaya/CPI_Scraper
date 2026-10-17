"""Chad — Ministère des Finances et du Budget, Direction Générale des Services
du Trésor et de la Comptabilité Publique, DIRECTION DE LA DETTE (DD): the
quarterly "Bulletin statistique de la dette publique" and the annual "Rapport
de gestion de la dette".

ROUTE. finances.gouv.td answers 404 to every path (2026-10); these are Wayback
`id_` copies of the ministry's own K2 attachments. Only four attachments were
ever archived (2019 report; 2020 Q1 and Q2 bulletins; 2023 Q4 bulletin) --
the 2021, 2024 and 2025 bulletins' item pages were captured, their PDFs not.

THREE TABLES, each its own series code (different tables, measures and
vintages -- never chained):
* "DD Rapport de gestion 2019: Tableau 8" -- encours at year-end 2016-2019,
  milliards FCFA: Dette extérieure (multilatérale, bilatérale, commerciale),
  Dette intérieure (conventionnée, non conventionnée, BTA, OTA, autres), Dette
  publique; and the three "Taux d'endettement" rows (% of GDP, as printed).
  (The caption says 2015-2019; four years are printed.)
* "DD Bulletin trimestriel: encours" -- the 2020 bulletins' table of external,
  domestic and total public debt for five quarter-ends (2019-Q1 .. 2020-Q2),
  milliards FCFA, plus the public debt ratio. The newer bulletin wins where
  quarters overlap (it revises: 2019-Q2 domestic 1 065,0 -> 1 065,8).
* "DD Bulletin T4 2023: Tableau 1.1" -- STOCK = encours + arrears (its own
  footnote), 2021, 2022 year-ends and 2023 Q1-Q4, in milliards FCFA and
  millions USD, with the encours and arrears each split domestic / external,
  and the debt ratio excluding / including arrears.

Checked (one-decimal figures, to 0,15): totals = their parts.
"""
from __future__ import annotations

import os
import re

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber

_NUM = r"\d{1,3}(?: \d{3})*,\d+|\d+,\d+"
_TOL = 0.15
_UNIT = "FCFA milliards"


def _f(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _page(path: str, needle: str) -> str:
    with fitz.open(path) as doc:
        idx = [k for k, p in enumerate(doc) if needle in " ".join(p.get_text().split())
               and "...." not in p.get_text()]
    if not idx:
        raise ValueError(f"DD Tchad: {needle!r} not in {os.path.basename(path)}")
    with pdfplumber.open(path) as pdf:
        return pdf.pages[idx[0]].extract_text() or ""


def _rows(lines, labels, n):
    got = {}
    for ln in lines:
        for lab in labels:
            if lab not in got and ln.startswith(lab + " "):
                vals = re.findall(_NUM + r"|\d+(?:,\d+)?%", ln[len(lab):])
                if len(vals) >= n:
                    got[lab] = [_f(v.rstrip("%")) for v in vals[:n]]
    return got


def _check(where, total, parts):
    for j in range(len(total)):
        s = sum(p[j] for p in parts)
        if abs(s - total[j]) > _TOL:
            raise ValueError(f"DD Tchad {where} col {j}: {total[j]} != {s:.2f}")


def _report_2019(path):
    t = _page(path, "Tableau 8 : Evolution de l’encours de la dette publique")
    body = t[t.index("Tableau 8"):]
    lines = body.splitlines()
    years = re.findall(r"\b(20\d\d)\b", next(l for l in lines if l.startswith("Rubrique")))
    n = len(years)
    labs = ["Dette extérieure", "Dette multilatérale", "Dette bilatérale",
            "Dette commerciale", "Dette intérieure", "Conventionnée", "Non conventionnée",
            "BTA", "OTA", "Autres dettes", "Dette publique",
            "Taux d'endettement extérieur", "Taux d'endettement intérieur",
            "Taux d'endettement public"]
    g = _rows(lines, labs, n)
    if set(g) != set(labs):
        raise ValueError(f"DD Tchad report: rows {sorted(set(labs) - set(g))} missing")
    _check("T8 ext", g["Dette extérieure"], [g[k] for k in labs[1:4]])
    _check("T8 dom", g["Dette intérieure"], [g[k] for k in labs[5:10]])
    _check("T8 pub", g["Dette publique"], [g["Dette extérieure"], g["Dette intérieure"]])
    code = "DD Rapport de gestion 2019: Tableau 8"
    out = []
    parent = {"Dette multilatérale": "Dette extérieure", "Dette bilatérale": "Dette extérieure",
              "Dette commerciale": "Dette extérieure"}
    for k in labs[:11]:
        comp = (f"{parent[k]}: {k}" if k in parent
                else f"Dette intérieure: {k}" if k in labs[5:10] else k)
        out += [{"component": comp, "period": y, "frequency": "annual", "measure": "stock",
                 "value": v, "unit": _UNIT, "series_code": code} for y, v in zip(years, g[k])]
    for k in labs[11:]:
        out += [{"component": k, "period": y, "frequency": "annual", "measure": "share_of_gdp",
                 "value": v, "unit": "percent", "series_code": code} for y, v in zip(years, g[k])]
    return out


def _bulletin_2020(path):
    with fitz.open(path) as doc:
        txt = [" ".join(p.get_text().split()) for p in doc]
    k = next(i for i, t in enumerate(txt)
             if re.search(r"(Tableau 6 : Evolution de l'encours de la dette publique"
                          r"|A1\. DETTTE PUBLIQUE)", t))
    with pdfplumber.open(path) as pdf:
        t = pdf.pages[k].extract_text() or ""
    m = re.search(r"Tableau 6 : Evolution de l'encours de la dette publique|A1\. DETTTE PUBLIQUE", t)
    lines = t[m.start():].splitlines()
    qline = next(l for l in lines if re.fullmatch(r"(?:T[1-4]\s*){5}(Variation en %)?\s*", l.strip()) or
                 re.match(r"^T[1-4] T[1-4] T[1-4] T[1-4] T[1-4]", l.strip()))
    yline = next(l for l in lines if re.match(r"^\s*(?:20\d\d\s+){4}20\d\d", l))
    qs = re.findall(r"T([1-4])", qline)[:5]
    ys = re.findall(r"20\d\d", yline)[:5]
    periods = [f"{y}-Q{q}" for y, q in zip(ys, qs)]
    labs = ["Dette extérieure", "Dette intérieure", "Dette publique totale", "Dette publique",
            "Taux d'endettement public", "Taux d'endettement"]
    g = _rows(lines, labs, 5)
    tot = g.get("Dette publique totale") or g.get("Dette publique")
    ratio = g.get("Taux d'endettement public") or g.get("Taux d'endettement")
    if not tot or not ratio or "Dette extérieure" not in g or "Dette intérieure" not in g:
        raise ValueError(f"DD Tchad bulletin {path}: rows {sorted(g)}")
    _check("bulletin", tot, [g["Dette extérieure"], g["Dette intérieure"]])
    code = "DD Bulletin trimestriel: encours"
    out = []
    for comp, vals, meas, unit in (("Dette extérieure", g["Dette extérieure"], "stock", _UNIT),
                                   ("Dette intérieure", g["Dette intérieure"], "stock", _UNIT),
                                   ("Dette publique", tot, "stock", _UNIT),
                                   ("Dette publique", ratio, "share_of_gdp", "percent")):
        out += [{"component": comp, "period": p, "frequency": "quarterly", "measure": meas,
                 "value": v, "unit": unit, "series_code": code} for p, v in zip(periods, vals)]
    return out


def _bulletin_2023(path):
    t = _page(path, "Tableau 1.1. Stock de la dette publique totale")
    body = t[t.index("Tableau 1.1"):t.index("Source")]
    lines = body.splitlines()
    annual = re.findall(r"20\d\d", next(l for l in lines if re.fullmatch(r"\s*20\d\d\s+20\d\d\s*", l)))
    qyear = next(l.strip() for l in lines if re.fullmatch(r"\s*20\d\d\s*", l))
    qs = re.findall(r"T([1-4])", next(l for l in lines if re.fullmatch(r"\s*(?:T[1-4]\s*){4}", l)))
    periods = [(y, "annual") for y in annual] + [(f"{qyear}-Q{q}", "quarterly") for q in qs]
    n = len(periods)
    code = "DD Bulletin T4 2023: Tableau 1.1"
    out = []
    usd = next(i for i, l in enumerate(lines) if l.startswith("En millions de USD"))
    rat = next(i for i, l in enumerate(lines) if l.startswith("Taux d'endettement"))
    for blk, unit in ((lines[:usd], _UNIT), (lines[usd:rat], "USD millions")):
        seq = [l for l in blk if re.match(r"^(Stock de la dette publique|Dette intérieure|"
                                          r"Dette extérieure|Arriérés) ", l)]
        names = ["Stock de la dette publique", "Stock de la dette publique: Dette intérieure",
                 "Stock de la dette publique: Dette extérieure", "Arriérés",
                 "Arriérés: Dette intérieure", "Arriérés: Dette extérieure"]
        if len(seq) != 6:
            raise ValueError(f"DD Tchad T1.1 {unit}: {len(seq)} rows")
        vals = []
        for l in seq:
            v = re.findall(_NUM, l)
            if len(v) != n:
                raise ValueError(f"DD Tchad T1.1: {l!r}")
            vals.append([_f(x) for x in v])
        # stock = encours (domestic + external) + arrears; arrears = its parts
        _check(f"T1.1 {unit} stock", vals[0], [vals[1], vals[2], vals[3]])
        _check(f"T1.1 {unit} arrears", vals[3], [vals[4], vals[5]])
        for name, vs in zip(names, vals):
            out += [{"component": name, "period": p, "frequency": f, "measure": "stock",
                     "value": v, "unit": unit, "series_code": code}
                    for (p, f), v in zip(periods, vs)]
    for lab in ("Hors arriérés", "Arriérés inclus"):
        l = next(x for x in lines[rat:] if x.startswith(lab + " "))
        v = re.findall(_NUM, l)
        if len(v) != n:
            raise ValueError(f"DD Tchad T1.1 ratio: {l!r}")
        out += [{"component": f"Taux d'endettement: {lab}", "period": p, "frequency": f,
                 "measure": "share_of_gdp", "value": _f(x), "unit": "percent",
                 "series_code": code} for (p, f), x in zip(periods, v)]
    return out


def _read(path: str) -> list[dict]:
    name = os.path.basename(path).lower()
    if "rapport" in name:
        return _report_2019(path)
    if "2023" in name:
        return _bulletin_2023(path)
    return _bulletin_2020(path)


def _order(path: str):
    m = re.search(r"(20\d\d)_t([1-4])", os.path.basename(path).lower())
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    # oldest first, the primary (newest) last: newer printings win
    files = sorted(set(extras or []) - {path}, key=_order) + [path]
    rows = []
    for f in files:
        rows += _read(f)
    df = pd.DataFrame(rows)
    return df.drop_duplicates(["component", "period", "frequency", "measure", "unit",
                               "series_code"], keep="last").reset_index(drop=True)
