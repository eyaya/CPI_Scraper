"""Djibouti — INSTAD, RGPH-3 (Troisième Recensement Général de la Population et
de l'Habitat, May 2024), Tome 3 "Caractéristiques économiques de la
population", chapter 3 "Population active occupée".

THE CENSUS, NOT THE YEARBOOK OR THE QUARTERLY NOTES. The Annuaire's employment
chapter counts EMPLOYEES by branch (Tableau 2.3.5 -- the employee universe,
excluded as Lesotho's sector tables were) and CNSS registrations
(administrative); the new quarterly EDST notes draw composition only as
charts. The census volume prints it as tables, for the employed aged 15+
(182 164 persons):

* Tableau n°8   grands groupes professionnels, Effectif and % -> `occupation`
* Tableau n°12  secteur formel / informel by region, milieu, sex, age group and
                education -> `formality`

THE VOLUME DOES NOT AGREE WITH ITSELF, AND TWO TABLES ARE LEFT OUT FOR IT:

* Tableau n°13 (branche d'activité) totals 127 526, not the 182 164 employed
  its caption names -- 70% of them, with no statement of who is missing, and
  Tableau n°2 (missing-value audit) reports ZERO missing cases for the
  activity variable. Its population is therefore unknown (the Zimbabwe 4.8
  rule), and it is not collected.
* Tableau n°15 (primaire / secondaire / tertiaire) claims all 182 164 employed
  and prints secondaire 8,8%, while n°13's own branches put industry at about
  15,8% (extractives + fabrication + électricité + eau + construction). One of
  them is wrong and the volume does not say which, so n°15 is not collected
  either.

TABLEAU n°8 IS KEPT AS PRINTED, including its "Aucune profession" row (61 193,
33,6% of the employed) -- an odd category for the employed, but a published
one, like Liberia's 43,5% "not elsewhere classified". Its counts must sum to
the Ensemble. NOTE: the chapter's prose quotes different shares (intellectual
professions 15,8%, intermediate 12,3%) from the table's 11,2% / 8,8%; the
table is collected.

TABLEAU n°11 (formal / informal by sex) repeats n°12's Sexe block and
Ensemble row digit for digit and is not read separately. n°12's marital-status
and nationality blocks have no column in this schema and are skipped; its
"Effectif" column (employment levels) belongs to `unemployment`.

The occupation groups are the ISCO-08 major-group titles in French, but no
scheme is named against the table -> National. Base 15+. Period 2024 (census
of May 2024; the volume is dated November 2025).

CROSS-CHECK: professions intellectuelles et scientifiques 20 397 (11,2%);
professions militaires 13 742 (7,5%); ensemble 182 164; secteur informel 49,1
(Obock 68,7; 15-19 ans 95,2; supérieur 4,8).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = ("Troisième Recensement Général de la Population et de l'Habitat "
           "(RGPH-3)")
_BASE = dict(survey=_SURVEY, period="2024", reference_period="RGPH-3, May 2024",
             frequency="ad_hoc", working_age_base="15+")

_T8 = ["Directeurs, cadres de direction et gérants",
       "Professions intellectuelles et scientifiques",
       "Professions intermédiaires", "Employés de type administratif",
       "Personnel des services directs aux particuliers, commerçants et vendeurs",
       "Agriculteurs et ouvriers qualifiés de l'agriculture, de la sylviculture et de la pêche",
       "Métiers qualifiés de l'industrie et de l'artisanat",
       "Conducteurs d'installations et de machines, et ouvriers de l'assemblage",
       "Professions élémentaires", "Professions militaires",
       "Aucune profession", "Ensemble"]

# Tableau n°12 sections -> the column each row label fills. Marital status and
# nationality have no home in the schema.
_SECTIONS = {"Région": "geography", "Milieu de résidence": "locality",
             "Sexe": "sex", "Groupe d'âges": "age_group",
             "Niveau d'instruction": "education",
             "Statut matrimonial": None, "Nationalité": None}
_EXPECT_12 = {"geography": 6, "locality": 2, "sex": 2, "age_group": 11,
              "education": 5}


def _pages(path: str, lo: int, hi: int) -> list[str]:
    with pdfplumber.open(path) as pdf:
        out = []
        for page in pdf.pages[lo:hi]:
            out += (page.extract_text() or "").splitlines()
    return [ln.strip() for ln in out]


def _after(lines: list[str], caption: str) -> list[str]:
    i = next((k for k, ln in enumerate(lines) if re.search(caption, ln)), None)
    if i is None:
        raise ValueError(f"RGPH-3: {caption!r} not found")
    return lines[i + 1:]


def _table_8(lines: list[str]) -> list[dict]:
    body = _after(lines, r"^Tableau n°8\. R.partition \(%\) des actifs occup.s")
    num = re.compile(r"(?:^|\s)(\d{1,3}(?: \d{3})*) (\d{1,3}(?:,\d)?)$")
    rows, text = [], []
    for ln in body:
        if ln.startswith("Source"):
            break
        m = num.search(ln)
        if m:
            rows.append((float(m.group(1).replace(" ", "")),
                         float(m.group(2).replace(",", "."))))
            ln = ln[:m.start()].strip()
        if ln and not re.match(r"(Actifs occup|Grands groupes|Effectif)", ln):
            text.append(ln)
    if len(rows) != len(_T8):
        raise ValueError(f"RGPH-3 T8: {len(rows)} value rows for {len(_T8)}")
    flat, pos = " ".join(text), 0
    for lab in _T8:
        for w in lab.split():
            k = flat.find(w, pos)
            if k < 0:
                raise ValueError(f"RGPH-3 T8: {lab!r} not found in order")
            pos = k + len(w)
    *groups, (tot_n, tot_p) = rows
    if sum(n for n, _ in groups) != tot_n or tot_p != 100:
        raise ValueError(f"RGPH-3 T8: groups sum to {sum(n for n, _ in groups)}"
                         f", Ensemble {tot_n}")
    if abs(sum(p for _, p in groups) - 100) > 0.3:
        raise ValueError("RGPH-3 T8: shares do not sum to 100")
    out = []
    for lab, (n, p) in zip(_T8, rows):
        name = "Total" if lab == "Ensemble" else lab
        for val, meas, unit in ((n, "count", "persons"), (p, "share", "percent")):
            out.append(C.row(topic="occupation", characteristic=name,
                             classification="National", value=val,
                             measure=meas, unit=unit,
                             series_code="RGPH-3 T8", **_BASE))
    return out


def _table_12(lines: list[str]) -> list[dict]:
    body = _after(lines, r"^Tableau n°12\. R.partition \(%\) de la population "
                         r"active occup.e")
    row = re.compile(r"^(.+?) (\d{1,3}(?:,\d)?) (\d{1,3}(?:,\d)?) 100 "
                     r"\d{1,3}(?: \d{3})*$")
    section, got, out = None, {}, []
    for ln in body:
        if ln.startswith("Source"):
            break
        if ln in _SECTIONS:
            section = ln
            continue
        m = row.match(ln)
        if not m:
            continue
        lab = m.group(1)
        f, i = (float(v.replace(",", ".")) for v in (m.group(2), m.group(3)))
        if abs(f + i - 100) > 0.15:
            raise ValueError(f"RGPH-3 T12: {lab!r} formel + informel = {f + i}")
        col = _SECTIONS.get(section) if lab != "Ensemble" else "national"
        if col is None:
            continue
        ctx = {}
        if col == "geography":
            ctx["geography"] = lab
        elif col == "locality":
            ctx.update(locality="urban" if lab == "Urbain" else "rural",
                       locality_label=lab)
        elif col == "sex":
            ctx["sex"] = C.normalise_sex(lab)
        elif col in ("age_group", "education"):
            ctx[col] = lab
        got[col] = got.get(col, 0) + 1
        for cat, v in (("Secteur formel", f), ("Secteur informel", i)):
            out.append(C.row(topic="formality", characteristic=cat,
                             classification="Not applicable", value=v,
                             measure="share", unit="percent",
                             series_code="RGPH-3 T12", **_BASE, **ctx))
    for col, n in _EXPECT_12.items():
        if got.get(col) != n:
            raise ValueError(f"RGPH-3 T12: {got.get(col)} {col} rows, expected {n}")
    if got.get("national") != 1:
        raise ValueError("RGPH-3 T12: no Ensemble row")
    return out


def parse(path: str) -> pd.DataFrame:
    # Chapter 3 sits on PDF pages 59-73; read a window, not all 147 pages.
    lines = _pages(path, 55, 76)
    return pd.DataFrame(_table_8(lines) + _table_12(lines))
