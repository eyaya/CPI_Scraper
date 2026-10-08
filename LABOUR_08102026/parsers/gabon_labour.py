"""Gabon — INSTAT (Institut National de la Statistique), RGPL-2013 (Recensement
Général de la Population et des Logements), "Résultats globaux" (December
2015), chapter 5.4 "Quelques caractéristiques du marché du travail".

A CENSUS, so the universe is the whole resident population: the employed
("occupés") aged 16-65, the census's own working-age definition (481 928
persons). Two distributions, each by milieu and sex:

* Tableau 71  situation dans l'occupation (7 categories + Non déclaré)
              -> employment_status
* Tableau 72  secteur institutionnel (Privé / Ménage et entrepreneur individuel
              / Public État, permanent and non-permanent / Collectivité locale /
              Autre + Non déclaré) -> sector

THE COLUMNS ARE Gabon | Urbain | Rural | Hommes | Femmes -- "Gabon" is printed
above the stub, not after the sexes, and the text layer gives no hint of it.
Settled by each table's own Effectif row: 481 928 = 424 865 + 57 063 (urban +
rural) = 311 908 + 170 020 (men + women), so the FIRST value column is the
national one. Every column must then sum to 100.

READ FROM THE TEXT LAYER BY A LABEL LIST, not the engine. Five of the fifteen
labels wrap AROUND their numbers ("Membre des coopératives" / 0,1 ... / "de
producteurs"; "Public Etat" / 19,6 ... / "(Fonctionnaire/Contractuel)"), in
three different shapes, and Tableau 72 breaks across pages 84-85 with no
repeated header. Rather than teach a line reader all three shapes, the labels
are stated (`_T71`, `_T72`, as printed) and the reader checks that the number
rows arrive in that count, that every stated label's words appear in the
table's text in order, and that each column sums to 100.

"NON DÉCLARÉ" IS LARGE AND IS COLLECTED: 10,0% of status and 11,2% of sector
(20,9% of rural sector) -- the report's own footnote calls these rates "assez
élevés". Any comparison of these shares must carry that.

NOT COLLECTED: the Effectif rows (employment levels -- `unemployment`'s
territory); Tableaux 64-70 (activity status, ages, training, education of the
labour-force categories). No occupation or branch table is published in this
volume. INSTAT's formal-employment bulletins are payroll records, and the
EGEP 2017 report carries no composition tables.

No nomenclature is named -> National. Period 2013 (census year).

CROSS-CHECK (Gabon): employé rémunéré 56,4; indépendant 30,0; privé 34,3;
ménage et entrepreneur individuel 31,5; public État (fonctionnaire /
contractuel) 19,6.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = "Recensement Général de la Population et des Logements (RGPL-2013)"
_COLS = [{}, {"locality": "urban", "locality_label": "Urbain"},
         {"locality": "rural", "locality_label": "Rural"},
         {"sex": "male"}, {"sex": "female"}]
_T71 = ["Employé rémunéré", "Indépendant", "Employeur",
        "Membre des coopératives de producteurs", "Aide familial",
        "Travailleur non rémunéré/ Apprenti", "Non déclaré", "Total"]
_T72 = ["Privé", "Ménage et Entrepreneur individuel",
        "Public Etat (Fonctionnaire/Contractuel)",
        "Public Etat (Main d'œuvre non permanente)", "Collectivité locale",
        "Autre", "Non déclaré", "Total"]
_TABLES = [
    (r"^Tableau 71 : R.partition \(%\) des occup.s selon la situation dans "
     r"l.occupation", "employment_status", _T71, "RGPL-2013 T71"),
    (r"^Tableau 72 : R.partition \(%\) des occup.s selon le secteur "
     r"institutionnel", "sector", _T72, "RGPL-2013 T72"),
]
_NUMS = re.compile(r"(?:^|\s)((?:\d{1,3},\d\s*){5})$")
# Furniture inside the region: running head, header cells, page numbers,
# footnotes (which start with their number and run to the next table line).
_FURNITURE = re.compile(r"^(?:\d{1,3}$|Recensement G.n.ral|Milieu de r.sidence|"
                        r"Situation dans|Secteur institutionnel|Urbain Rural|"
                        r"\d{1,2} (?:Ces|Cf\.))")


def _lines(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        # Chapter 5 sits around printed pages 80-86; search a window rather
        # than all 259 pages.
        out = []
        for page in pdf.pages[110:135]:
            out += (page.extract_text() or "").splitlines()
    return [ln.strip() for ln in out]


def _read(lines: list[str], caption: str, labels: list[str], where: str):
    start = next((i for i, ln in enumerate(lines) if re.search(caption, ln)), None)
    if start is None:
        raise ValueError(f"{where}: caption not found")
    rows, text = [], []
    for ln in lines[start + 1:]:
        if ln.startswith("Effectif"):
            break
        if _FURNITURE.search(ln) or ln == "Gabon":
            continue
        m = _NUMS.search(ln)
        if m:
            rows.append([float(v.replace(",", ".")) for v in m.group(1).split()])
            ln = ln[:m.start()].strip()
        if ln:
            text.append(re.sub(r"(?<=[a-zé])\d{1,2}$", "", ln))   # "déclaré9"
    if len(rows) != len(labels):
        raise ValueError(f"{where}: {len(rows)} value rows for {len(labels)} "
                         f"labels")
    flat = " ".join(text)
    pos = 0
    for lab in labels:
        for word in lab.split():
            k = flat.find(word, pos)
            if k < 0:
                raise ValueError(f"{where}: label {lab!r} not in order in {flat!r}")
            pos = k + len(word)
    for j in range(5):
        s = sum(r[j] for r in rows[:-1])
        if abs(s - 100) > 0.3 or rows[-1][j] != 100.0:
            raise ValueError(f"{where}: column {j} sums to {s:.1f}")
    return list(zip(labels, rows))


def parse(path: str) -> pd.DataFrame:
    lines = _lines(path)
    out = []
    for caption, topic, labels, code in _TABLES:
        for lab, vals in _read(lines, caption, labels, code):
            for ctx, v in zip(_COLS, vals):
                out.append(C.row(topic=topic, characteristic=lab,
                                 classification="National", value=v,
                                 survey=_SURVEY, period="2013",
                                 reference_period="RGPL-2013",
                                 frequency="ad_hoc", measure="share",
                                 unit="percent", working_age_base="16-65",
                                 series_code=code, **ctx))
    return pd.DataFrame(out)
