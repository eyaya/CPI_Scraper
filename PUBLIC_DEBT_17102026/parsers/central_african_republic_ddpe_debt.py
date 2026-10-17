"""Central African Republic — Ministère des Finances et du Budget, Direction de
la Dette Publique et Extérieure (DDPE), "Bulletin statistique de la dette
publique" (quarterly), on finances.gouv.cf.

PUBLISHER: the DDPE ("Source : DDPE" under every table) -- an official
national compiler, accepted under the 2026-10-08 source policy.

COVERAGE: the State's public debt (external + domestic, central government);
SOE and Bangui city-hall debts are reported in separate tables (17-19) and are
not read.

WHAT IS READ (the 2026 bulletin layout), each table giving the previous and
the current quarter, in MILLIARDS DE FCFA, with shares as printed:

* Tableau 3 "Évolution du Stock" -- the STOCK (outstanding + arrears):
  external by creditor class, domestic by instrument (market debt, other,
  domestic arrears), total;
* Tableau 2 "Évolution de l'Encours" -- the ENCOURS (outstanding, excluding
  arrears), same breakdown;
* Tableau 1 -- debt-to-GDP for both quarters ("Dette/PIB").

STOCK vs ENCOURS are kept apart in the component label ("Stock: ..." /
"Encours: ..."): the bulletin's own headline mixes them (Dette/PIB is on the
stock).

PUBLISHED ROUNDING DIFFERENCES, KEPT: the bulletin prints the same quantity
with a last-digit difference in different places (external stock T2 515,81 in
Tableau 3, 515,82 in Tableau 1; total encours T2 963,60 vs 963,61), and Tableau
3's T1 external classes sum to 512,66 against a printed 512,57. Sum checks
therefore allow 0,15 milliard; anything larger raises.

LAYOUT DEPENDENCE: the 2024-2025 bulletins use a different table set (encours
in Tableau n°7, stock in n°8); the parser recognises only the 2026 layout and
raises on another rather than misreading it. The labels are stated
(`_T3`, `_T2`) as printed and must appear in order.

CROSS-CHECK (T2 2026): total stock 1 136,53 (Dette/PIB 61,20%); external
515,81; domestic 620,71; market debt 437,23; total encours 963,60.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_COV = "Dette publique de l'Etat (DDPE; entreprises publiques et Mairie de Bangui publiées séparément)"
_NUM = r"\d{1,3}(?: \d{3})*,\d+|\d+,\d+|\d+"
_PCT = r"\d+(?:,\d+)?\s*%\.?"

_T3 = [("DETTE EXTÉRIEURE", "Stock: Dette extérieure"),
       ("Bilatéraux", "Stock: Bilatéraux (encours + arriérés)"),
       ("Multilatéraux", "Stock: Multilatéraux (encours + arriérés)"),
       ("DETTE INTÉRIEURE", "Stock: Dette intérieure"),
       ("Dette du marché", "Stock: Dette du marché (BTA/OTA)"),
       ("Autre dette intérieure", "Stock: Autre dette intérieure"),
       ("Arriérés intérieurs", "Stock: Arriérés intérieurs"),
       ("TOTAL STOCK", "Stock: Total")]
_T2 = [("ENCOURS EXTÉRIEUR", "Encours: Dette extérieure"),
       ("Bilatéraux", "Encours: Bilatéraux"),
       ("Multilatéraux", "Encours: Multilatéraux"),
       ("ENCOURS INTÉRIEUR", "Encours: Dette intérieure"),
       ("Dette du marché", "Encours: Dette du marché (BTA/OTA)"),
       ("Autre dette intérieure", "Encours: Autre dette intérieure"),
       ("TOTAL ENCOURS", "Encours: Total")]
_ROW = re.compile(rf"^(?:—\s*)?(?P<lab>.*?)\s*(?P<a>{_NUM})\s+(?P<pa>{_PCT})\s+"
                  rf"(?P<b>{_NUM})\s+(?P<pb>{_PCT})\s*$")


def _f(t):
    return float(t.replace(" ", "").replace("%", "").rstrip(".").replace(",", "."))


def _table(text, start, spec, name):
    i = text.index(start)
    lines = text[i:text.find("Source", i)].splitlines()
    rows = []
    for ln in lines:
        m = _ROW.match(ln.strip())
        if m:
            rows.append((m.group("lab"), [_f(m.group(k)) for k in "a pa b pb".split()]))
    if len(rows) != len(spec):
        raise ValueError(f"DDPE {name}: {len(rows)} rows for {len(spec)} labels "
                         f"({[r[0] for r in rows]})")
    flat = " ".join(lines)
    pos = 0
    for lab, _ in spec:
        k = flat.find(lab, pos)
        if k < 0:
            raise ValueError(f"DDPE {name}: {lab!r} not in order")
        pos = k + len(lab)
    return {comp: vals for (_, comp), (_, vals) in zip(spec, rows)}


def _quarter(text):
    m = re.search(r"Tableau 1 : Indicateurs de bord de la dette publique – T([1-4]) (20\d\d)", text)
    if not m:
        raise ValueError("DDPE: not the 2026 bulletin layout (no Tableau 1 "
                         "'Indicateurs de bord')")
    q, y = int(m.group(1)), int(m.group(2))
    prev = (y, q - 1) if q > 1 else (y - 1, 4)
    return f"{prev[0]}-Q{prev[1]}", f"{y}-Q{q}"


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages[4:12])
    p_prev, p_cur = _quarter(text)
    t3 = _table(text, "Tableau 3 : Évolution du Stock", _T3, "Tableau 3")
    t2 = _table(text, "Tableau 2 : Évolution de l’Encours", _T2, "Tableau 2")

    for t, ext, classes, dom, parts, tot in (
            (t3, "Stock: Dette extérieure", ["Stock: Bilatéraux (encours + arriérés)", "Stock: Multilatéraux (encours + arriérés)"],
             "Stock: Dette intérieure", ["Stock: Dette du marché (BTA/OTA)", "Stock: Autre dette intérieure", "Stock: Arriérés intérieurs"], "Stock: Total"),
            (t2, "Encours: Dette extérieure", ["Encours: Bilatéraux", "Encours: Multilatéraux"],
             "Encours: Dette intérieure", ["Encours: Dette du marché (BTA/OTA)", "Encours: Autre dette intérieure"], "Encours: Total")):
        for j in (0, 2):
            for whole, ps in ((ext, classes), (dom, parts)):
                if abs(t[whole][j] - sum(t[p][j] for p in ps)) > 0.15:
                    raise ValueError(f"DDPE: {whole} parts do not sum")
            if abs(t[tot][j] - t[ext][j] - t[dom][j]) > 0.15:
                raise ValueError(f"DDPE: {tot} != external + domestic")

    out = []
    for t in (t3, t2):
        code = "DDPE T3" if t is t3 else "DDPE T2"
        for comp, (a, pa, b, pb) in t.items():
            for per, v, s in ((p_prev, a, pa), (p_cur, b, pb)):
                out.append(dict(coverage=_COV, component=comp, period=per,
                                frequency="quarterly", measure="stock", value=v,
                                unit="FCFA milliards", series_code=code))
                out.append(dict(coverage=_COV, component=comp, period=per,
                                frequency="quarterly", measure="share", value=s,
                                unit="percent", series_code=code))
    m = re.search(r"^Dette/PIB\s+(" + _PCT + r")\s+(" + _PCT + r")", text, re.M)
    if not m:
        raise ValueError("DDPE Tableau 1: no Dette/PIB row")
    for per, tok in ((p_cur, m.group(1)), (p_prev, m.group(2))):
        out.append(dict(coverage=_COV, component="Stock: Total", period=per,
                        frequency="quarterly", measure="share_of_gdp",
                        value=_f(tok), unit="percent", series_code="DDPE T1"))
    return pd.DataFrame(out)
