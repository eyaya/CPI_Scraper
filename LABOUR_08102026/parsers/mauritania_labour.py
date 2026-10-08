"""Mauritania — ANSADE (Agence Nationale de la Statistique et de l'Analyse
Démographique et Economique, formerly ONS): ENESI 2017 and the RGPH 2013
census, employed by branch of activity and by status in employment.

TWO PUBLICATIONS, both HOUSEHOLD / census universes, both on ANSADE's own
14-64 working-age definition ("la limite inférieure est de 14 ans et la
limite supérieure est l'âge à la retraite situé à 64 ans" -- ENESI p.26; the
census volume adopts the same band, p.64):

* ENESI 2017 (Enquête Nationale sur l'Emploi et le Secteur Informel), annexe 4,
  Tableau A4.1 -- employed by 24 branches x sex, counts (total 734 277).
* RGPH 2013, Volume 3 "Caractéristiques socioculturelles et économiques",
  chapter 9 -- Tableau 9.25 branch x sex, 9.26 branch x milieu (Urbain /
  Rural / Nomade), 9.27 statut dans l'emploi x sex, counts (total 610 425).

WHAT WAS FOUND AND REFUSED ON THE WAY:

* ENESI's composition cuts in the body are charts, and its only other tables
  (A4.2-A4.5) distribute the same employed by age, education and wilaya --
  not topics here. Its informal-sector part (UPI) is excluded.
* ENRE-SI 2012's Tableaux 23-24 ("Travailleurs selon le statut", "par secteur
  d'activité") are the INFORMAL-UNIT module -- Tableau 24 is digit for digit
  Tableau 21, the distribution of UPI -- the Kenya trap.
* ENTE quarterly notes (2025-26): composition only as charts whose labels
  scramble across side-by-side plots. RGPH-5 (2023) general report and the
  2024/2025 sociodemographic yearbooks: no composition table.

READ BY STATED LABEL LISTS, like Gabon: labels wrap either side of their
numbers ("Sylviculture, exploitation forestière et 4884 788 5672" /
"cueillette"; the census puts some labels on a line above their numbers).
The reader takes each line ending in exactly the table's column count of
integers (or "-"), requires as many such rows as stated labels, requires every
stated label's words to appear in the table text in order, and holds each
table to its arithmetic: sexes (or strata) sum to the row total, and the
categories sum to the Total row -- within rounding, since BOTH publications
print weighted estimates rounded cell by cell (ENESI élevage et chasse 66 308 +
2 492 = 68 800 against a printed 68 799; census banques 2 409 + 1 059 = 3 468
against 3 467). Kept as printed.

LABELS AS PRINTED, typos included: "Construction (BTP°", "Administration et
servicesociaux", "Salarié privé permanant". "-" in 9.26 (banks, Nomade) is a
cell with no value, not collected as 0 (the row still sums without it).

9.26'S TOTAL COLUMN IS NOT COLLECTED: it repeats 9.25's Total column under the
same merge key; it is checked equal instead.

No nomenclature is named in either document -> National.

PERIODS: ENESI 2017 (the report's own year; it states no field dates); census
2013.

CROSS-CHECK: ENESI commerce 157 274 (M 72 425 / F 84 849), agriculture
129 555, total 734 277; census commerce 158 031, élevage 88 484 (nomade
16 477), indépendant 326 459, salariés public 88 274, total 610 425.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

from . import _common as C

_ENESI = "Enquête Nationale sur l'Emploi et le Secteur Informel (ENESI) 2017"
_RGPH = ("Recensement Général de la Population et de l'Habitat (RGPH) 2013, "
         "Volume 3")
_SEX = [{"sex": "male"}, {"sex": "female"}, {}]
_MILIEU = [{"locality": "urban", "locality_label": "Urbain"},
           {"locality": "rural", "locality_label": "Rural"},
           {"locality": "other", "locality_label": "Nomade"}, None]

_A41 = ["Agriculture", "Elevage et chasse",
        "Sylviculture, exploitation forestière et cueillette",
        "Pèche, pisciculture et aquaculture", "Activités extractives",
        "Fabrication de produits agro-alimentaires et à base de tabac",
        "Autres industries manufacturières",
        "Production et distribution d’électricité et de gaz",
        "Distribution d’eau, assainissement et traitement des déchets",
        "Construction", "Commerce", "Transports", "Hébergement et restauration",
        "Information et communication", "Activités financières et d’assurance",
        "Activités immobilières",
        "Activités spécialisées, scientifiques et techniques",
        "Activités de soutien et de bureau",
        "Activités d’administration publique", "Enseignement",
        "Activités pour la santé humaine, action sociale",
        "Activités à caractère collectif ou personnel", "Extraterritorialité",
        "N.D", "Total"]
_BRANCH_2013 = ["Agriculture", "Elevage", "Activités annexes", "Chasse",
                "Sylviculture", "Pêche", "Industrie extractive",
                "Industrie manufacturière", "Eau, gaz et électricité",
                "Construction (BTP°", "Commerce", "Transport et communication",
                "Banques et assurances", "Administration et servicesociaux",
                "ND", "Total"]
_STATUS_2013 = ["Indépendant", "Employeur", "Salarié privé permanant",
                "Salariés privé temporaire", "Salariés public", "Apprentis",
                "Aides familiaux", "Total"]


def _lines(path: str, pages: range) -> list[str]:
    with pdfplumber.open(path) as pdf:
        out = []
        for i in pages:
            if i < len(pdf.pages):
                out += (pdf.pages[i].extract_text() or "").splitlines()
    return [ln.strip() for ln in out]


def _read(lines: list[str], caption: str, labels: list[str], ncols: int,
          where: str, rounded: bool = False) -> list[tuple[str, list]]:
    """`rounded`: the table prints independently rounded weighted estimates,
    so a sum may miss its printed total by rounding -- at most 1 across a row,
    half a person per category down a column. Every table read here is of
    that kind (the census volume too: banques 2 409 + 1 059 = 3 468 against a
    printed 3 467)."""
    start = next((i for i, ln in enumerate(lines) if re.search(caption, ln)), None)
    if start is None:
        raise ValueError(f"{where}: caption not found")
    num = re.compile(rf"(?:^|\s)((?:(?:\d+|-)\s+){{{ncols - 1}}}(?:\d+|-))$")
    rows, text = [], []
    for ln in lines[start + 1:]:
        if re.match(r"^(Tableau|Source|Annexe)\b", ln):
            break
        m = num.search(ln)
        if m:
            rows.append([None if v == "-" else float(v) for v in m.group(1).split()])
            ln = ln[:m.start()]
        text.append(ln)
        if len(rows) == len(labels):
            # the Total row closes the table; a trailing label fragment of the
            # row before it cannot follow it.
            break
    if len(rows) != len(labels):
        raise ValueError(f"{where}: {len(rows)} value rows for {len(labels)} labels")
    # "agro-" / "alimentaires": a label hyphenated across its wrap.
    flat, pos = re.sub(r"-\s+", "-", " ".join(text)), 0
    for lab in labels:
        for word in lab.split():
            k = flat.find(word, pos)
            if k < 0:
                raise ValueError(f"{where}: label {lab!r} not found in order")
            pos = k + len(word)
    # arithmetic: parts sum to the row total, categories to the Total row
    *cats, total = rows
    row_tol = 1 if rounded else 0
    col_tol = len(cats) / 2 if rounded else 0
    for r, lab in zip(rows, labels):
        if abs(sum(v or 0 for v in r[:-1]) - r[-1]) > row_tol:
            raise ValueError(f"{where}: {lab!r} parts {r[:-1]} != total {r[-1]}")
    for j in range(ncols):
        if abs(sum(r[j] or 0 for r in cats) - total[j]) > col_tol:
            raise ValueError(f"{where}: column {j} does not sum to its Total")
    return list(zip(labels, rows))


def _emit(rows, cols, topic, survey, period, code) -> list[dict]:
    out = []
    for lab, vals in rows:
        for ctx, v in zip(cols, vals):
            if ctx is None or v is None:
                continue
            out.append(C.row(topic=topic, characteristic=lab,
                             classification="National", value=v,
                             survey=survey, period=period,
                             reference_period=period, frequency="ad_hoc",
                             measure="count", unit="persons",
                             working_age_base="14-64", series_code=code,
                             **ctx))
    return out


def _enesi(path: str) -> list[dict]:
    lines = _lines(path, range(70, 80))
    rows = _read(lines, r"^Tableau A4\.1 : R.partition de la population en "
                        r"emploi selon la branche", _A41, 3, "ENESI A4.1", rounded=True)
    return _emit(rows, _SEX, "industry", _ENESI, "2017", "ENESI 2017 A4.1")


def _rgph(path: str) -> list[dict]:
    lines = _lines(path, range(88, 96))
    b_sex = _read(lines, r"^Tableau 9\. ?25 :\s*Population occup.e par branche",
                  _BRANCH_2013, 3, "RGPH 9.25", rounded=True)
    b_mil = _read(lines, r"^Tableau 9\. ?26 :\s*Population occup.e par branche",
                  _BRANCH_2013, 4, "RGPH 9.26", rounded=True)
    status = _read(lines, r"^Tableau 9\. ?27 :\s*Population occup.e selon le "
                          r"statut", _STATUS_2013, 3, "RGPH 9.27", rounded=True)
    for (lab, a), (_, b) in zip(b_sex, b_mil):
        if a[-1] != b[-1]:
            raise ValueError(f"RGPH: 9.25 and 9.26 disagree on {lab!r} total")
    return (_emit(b_sex, _SEX, "industry", _RGPH, "2013", "RGPH 2013 T9.25")
            + _emit(b_mil, _MILIEU, "industry", _RGPH, "2013", "RGPH 2013 T9.26")
            + _emit(status, _SEX, "employment_status", _RGPH, "2013",
                    "RGPH 2013 T9.27"))


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        name = os.path.basename(p).lower()
        if "enesi" in name:
            rows += _enesi(p)
        elif "rgph" in name or "volume3" in name:
            rows += _rgph(p)
        else:
            raise ValueError(f"ANSADE: unrecognised file {p!r}")
    return pd.DataFrame(rows)
