"""Togo — INSEED Togo, ERI-ESI 2017 (Enquête Régionale Intégrée sur l'Emploi
et le Secteur Informel), "Rapport Global TOGO", chapter 5 "Emploi".

THE SAME UEMOA TEMPLATE AS NIGER, and the same split: chapter 5 is the
household employment survey; chapters 9-14 are the informal-sector (UPI)
module and stay excluded -- including 9.5 "Répartition des emplois des actifs
occupés", whose universe is informal units' jobs. Two chapter-5 tables describe
all the employed:

* Tableau 5.26 "Principaux acteurs de l'offre d'emploi" -- institutional sector
  by sex, milieu (Lomé / autres urbains / ensemble urbain / rural), the six
  regions and Togo -> `sector`;
* Tableau 5.32 "Principales caractéristiques des actifs occupés selon les grands
  groupes de la CITP" -- Effectif and Proportion per occupation group ->
  `occupation` (counts and shares). The other columns (youth share, income,
  years of study, formal/informal and sector WITHIN each group) are row
  characteristics, not composition.

BOTH ARE HIERARCHICAL, and only the leaves and the total are collected:
5.26's "Secteur privé" = Initiative privée + Autres acteurs and "Secteur
public" = Administration publique + Entreprise publique et parapublique; 5.32
interleaves four skill aggregates (Hautement qualifiés non manuels = groups
1-3, Peu qualifiés non manuels = 4-5, Qualifiés manuels = 6-8, Non qualifiés =
9 + militaires). Every aggregate is checked against its leaves (to within 1
person / 0,15 point -- INSEED's own rounding), then not emitted, so each topic
partitions the employed.

THE UNIVERSE WAS CHECKED, because Tableau 5.10 ("Bilan de l'emploi") failed
it: 5.10's total is 513 042, against 2 272 230 employed in 5.32 -- about 22%,
a population the table never states -- so 5.10 is NOT collected (the Zimbabwe
4.8 rule; Niger's 5.12, by contrast, matched its report's employed count and
was taken). 5.26's national column (public 6,7 / privé 92,5 / ménage 0,8)
reproduces 5.32's all-employed split (6,6 / 92,6 / 0,8), so 5.26 describes all
the employed. The prose beside 5.26 quotes 92,8% / 69,2%; the table's own
92,5 / 68,3 are collected.

NOT COLLECTED: 5.30 (branches of INFORMAL employment only -- the universe that
Burkina's Tableau 5 was refused for); 5.35/5.39 ("part de femmes", row %);
5.36/5.40 (text verdicts "Mixte / Masculin"); 5.27/5.28 (branches within the
public / private sector); 5.10 (above).

CLASSIFICATION: 5.32 names "la CITP" against the table but never its revision
(the labels are the 2008 French titles, but saying so would be inference) ->
National, as for Nigeria. 5.26 is INSEED's own grouping -> National. Base 15+.
Period 2017.

CROSS-CHECK (Togo): initiative privée 68,3; administration publique 4,5;
personnel des services directs aux particuliers 624 277 (27,5%); agriculteurs
690 294 (30,4%); total employed 2 272 230.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = ("Enquête Régionale Intégrée sur l'Emploi et le Secteur Informel "
           "(ERI-ESI) 2017")
_BASE = dict(survey=_SURVEY, period="2017", reference_period="ERI-ESI 2017",
             frequency="ad_hoc", working_age_base="15+")

# ---- Tableau 5.26 --------------------------------------------------------
_COLS_526 = (
    [{"sex": "male"}, {"sex": "female"},
     {"locality": "urban", "locality_label": "Lomé"},
     {"locality": "urban", "locality_label": "Autres urbains"},
     {"locality": "urban", "locality_label": "Ensemble urbain"},
     {"locality": "rural", "locality_label": "Rural"}]
    # The region header is letter-wrapped ("Maritim / e"); names as INSEED
    # prints them in full in Tableau 5.35.
    + [{"geography": g} for g in ("Maritime", "Plateaux", "Centrale", "Kara",
                                  "Savanes", "Grand Lomé")]
    + [{}])
_ROWS_526 = ["Initiative privée", "Autres acteurs", "Secteur privé",
             "Administration publique", "Entreprise publique et parapublique",
             "Secteur public", "Ménage employeur", "Total"]
_AGG_526 = {"Secteur privé": ("Initiative privée", "Autres acteurs"),
            "Secteur public": ("Administration publique",
                               "Entreprise publique et parapublique")}

# ---- Tableau 5.32 --------------------------------------------------------
_ROWS_532 = [
    "Directeurs, cadres de direction et gérants",
    "Professions intellectuelles et scientifiques",
    "Professions intermédiaires",
    "Hautement qualifiés non manuels",
    "Employés de type administratif",
    "Personnel des services directs aux particuliers, commerçants et vendeurs",
    "Peu qualifiés non manuels",
    "Agriculteurs et ouvriers qualifiés de l'agriculture, de la sylviculture et de la pêche",
    "Métiers qualifiés de l'industrie et de l'artisanat",
    "Conducteurs d'installations et de machines, et ouvriers de l'assemblage",
    "Qualifiés manuels",
    "Professions élémentaires",
    "Professions militaires",
    "Non qualifiés",
    "Togo",
]
_AGG_532 = {
    "Hautement qualifiés non manuels": _ROWS_532[0:3],
    "Peu qualifiés non manuels": _ROWS_532[4:6],
    "Qualifiés manuels": _ROWS_532[7:10],
    "Non qualifiés": _ROWS_532[11:13],
}


def _page_lines(path: str, caption: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[60:105]:
            text = page.extract_text() or ""
            m = re.search(caption, text)
            if m:
                return [ln.strip() for ln in text[m.end():].splitlines()]
    raise ValueError(f"ERI-ESI Togo: {caption!r} not found")


def _check_labels(text: list[str], labels: list[str], where: str) -> None:
    """Every stated label's words must appear in the table text, in order."""
    flat, pos = " ".join(text), 0
    for lab in labels:
        for word in lab.split():
            k = flat.find(word, pos)
            if k < 0:
                raise ValueError(f"{where}: label {lab!r} not found in order")
            pos = k + len(word)


def _table_526(path: str) -> list[dict]:
    lines = _page_lines(path, r"Tableau 5\.26\s*:\s*Principaux acteurs de "
                              r"l.offre d.emploi")
    num = re.compile(r"(?:^|\s)((?:\d{1,3},\d\s+){12}\d{1,3},\d)$")
    rows, text = [], []
    for ln in lines:
        if ln.startswith("Source"):
            break
        m = num.search(ln)
        if m:
            rows.append([float(v.replace(",", ".")) for v in m.group(1).split()])
            ln = ln[:m.start()].strip()
        if ln and rows:          # header lines precede the first value row
            text.append(ln)
        elif ln and not rows and re.match(r"Initiative", ln):
            text.append(ln)
    if len(rows) != len(_ROWS_526):
        raise ValueError(f"ERI-ESI T5.26: {len(rows)} value rows for "
                         f"{len(_ROWS_526)} labels")
    _check_labels(text, _ROWS_526, "ERI-ESI T5.26")
    by = dict(zip(_ROWS_526, rows))
    for j in range(13):
        for agg, parts in _AGG_526.items():
            if abs(by[agg][j] - sum(by[p][j] for p in parts)) > 0.15:
                raise ValueError(f"ERI-ESI T5.26 col {j}: {agg} is not the sum "
                                 f"of {parts}")
        leaves = [r for r in _ROWS_526 if r not in _AGG_526 and r != "Total"]
        s = sum(by[r][j] for r in leaves)
        if abs(s - 100) > 0.3 or by["Total"][j] != 100:
            raise ValueError(f"ERI-ESI T5.26 col {j}: leaves sum to {s:.1f}")
    out = []
    for lab in (r for r in _ROWS_526 if r not in _AGG_526):
        for ctx, v in zip(_COLS_526, by[lab]):
            out.append(C.row(topic="sector", characteristic=lab,
                             classification="National", value=v,
                             measure="share", unit="percent",
                             series_code="ERI-ESI T5.26", **_BASE, **ctx))
    return out


def _table_532(path: str) -> list[dict]:
    lines = _page_lines(path, r"Tableau 5\.32\s*:\s*Principales caract.ristiques "
                              r"des actifs occup.s selon les grands groupes")
    # "<label?> 82 878 3,6 35,6 88 180 ..." -- Effectif is the run of space-
    # grouped digits before the first decimal; Proportion is that decimal.
    # Income further along is space-grouped too, and is not read.
    num = re.compile(r"(?:^|\s)(\d{1,3}(?: \d{3})*) (\d{1,3},\d)(?= )")
    rows, text = [], []
    for ln in lines:
        if ln.startswith("Source"):
            break
        m = num.search(ln)
        if m and re.search(r"\d,\d.*\d,\d.*\d,\d", ln[m.start():]):
            rows.append((float(m.group(1).replace(" ", "")),
                         float(m.group(2).replace(",", "."))))
            ln = ln[:m.start()].strip()
        if ln and (rows or ln.startswith("Directeurs")):
            text.append(ln)
    if len(rows) != len(_ROWS_532):
        raise ValueError(f"ERI-ESI T5.32: {len(rows)} value rows for "
                         f"{len(_ROWS_532)} labels")
    _check_labels(text, _ROWS_532, "ERI-ESI T5.32")
    by = dict(zip(_ROWS_532, rows))
    for agg, parts in _AGG_532.items():
        if abs(by[agg][0] - sum(by[p][0] for p in parts)) > 1:
            raise ValueError(f"ERI-ESI T5.32: {agg} count is not the sum of "
                             f"its groups")
    leaves = [r for r in _ROWS_532 if r not in _AGG_532 and r != "Togo"]
    n = sum(by[r][0] for r in leaves)
    if abs(n - by["Togo"][0]) > 3:
        raise ValueError(f"ERI-ESI T5.32: groups sum to {n}, Togo "
                         f"{by['Togo'][0]}")
    if abs(sum(by[r][1] for r in leaves) - 100) > 0.3:
        raise ValueError("ERI-ESI T5.32: proportions do not sum to 100")
    out = []
    for lab in leaves + ["Togo"]:
        count, share = by[lab]
        name = "Total" if lab == "Togo" else lab
        for val, meas, unit in ((count, "count", "persons"),
                                (share, "share", "percent")):
            out.append(C.row(topic="occupation", characteristic=name,
                             classification="National", value=val,
                             measure=meas, unit=unit,
                             series_code="ERI-ESI T5.32", **_BASE))
    return out


def parse(path: str) -> pd.DataFrame:
    return pd.DataFrame(_table_526(path) + _table_532(path))
