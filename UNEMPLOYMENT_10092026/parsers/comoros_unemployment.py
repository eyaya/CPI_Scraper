"""Comoros — INSEED Comores: three publications, three survey rounds.

The SAME three documents `labour/` retains (reached through INSEED's NADA
catalogue, nada.inseed-comores.org/index.php/catalog/<id>/download/<n>);
`labour` takes their composition tables, this module their headline series,
so no figure has two homes.

1. EEIC 2021 -- Enquête sur l'Économie Informelle aux Comores, analysis report
   (February 2023). Its opening table "Certains indicateurs du marché du
   travail" (pp. 4-6) is a full ICLS-19 key-indicators panel by Masculin /
   Féminin / Urbain / Rural / Total: working-age population, labour force,
   employed, LFPR, EPR, LU1-LU4, the youth (15-34) rates, NEET and informal
   employment outside agriculture. Working-age base 14-64 (report p. 10:
   "La population en âge de travailler (14-64 ans)"); youth is 15-34 (p. 11).
2. RGPH 2017 -- census thematic report "Caractéristiques économiques".
   Tableau 2.5 (net activity rate by island x sex), 2.6 (by milieu x sex),
   2.7 (by five-year age group x sex), 3.1 (employed / active / population
   15-64 and the taux d'occupation, by island), 3.8 (employment rate by
   education x sex), 4.1-4.3 (unemployment by milieu, island and education).
3. EESIC 2013 phase 1 -- Tableau 17 (employed, BIT unemployed and discouraged
   job-seekers, counts, by island / milieu / sex and age), Tableau 18 (EPR and
   youth 15-35 NEET), Tableau 25 (time-related underemployment).

THE COUNTS IN EEIC'S TABLE ARE SPLIT BY THE TEXT LAYER ("145" / "758" for
145 758) and its row labels say "(nombre '000)" over figures that are persons
(810 532 = the population, p. 10). Every count row is re-split under the
table's own arithmetic -- masculin + féminin = total and urbain + rural =
total, to within 2 -- and a row with no split, or more than one, raises.

CENSUS BASES, SETTLED BY THE TABLES' OWN ARITHMETIC. The census captions are
inconsistent: Tableau 2.5 says "15 ans et plus" and 2.6/2.7 say "15-64 ans",
over the SAME national net activity rate (58,7). Tableau 3.1 decides it:
249 491 actifs / 425 243 "Population de 15-64 ans" = 58,67, and its taux
d'occupation 45,7 = 194 290 / 425 243. So the net activity rates and the taux
d'occupation are on 15-64. Tableau 3.8's employment rates (Total 41,76) are
NOT -- 41,76 is not 45,7 -- and its caption states no base; it is recorded as
"not stated". The unemployment rates (4.1-4.3) carry their captions' "15 ans
ou plus"; 4.1's national 22,13 equals 1 - 194 290 / 249 491 to rounding.

CENSUS UNEMPLOYMENT: only the "Taux de chômage global" is collected, as the
unemployment rate. The report defines it (p. 19, p. 51) as the job-seeking and
available -- those who have worked and first-job seekers -- over the active
population, hence `strict`. Its "primaire" and "secondaire" rows are the two
COMPONENTS of that rate (8,61 + 13,52 = 22,13), each a share of the whole
labour force, and the report's own prose even defines them in opposite order
to its text on p. 10; filing them as unemployment rates would put three
different numbers under one topic. Not collected.

NOT COLLECTED, AND WHY:
* EEIC "Population active" (162 506): a second "active population" row that
  matches neither the labour force (236 226) nor any stated subset; no
  denominator can be named for it.
* EEIC rows repeated in its own table (labour force and employed are printed
  twice, LFPR twice under two labels): each repeat is CHECKED equal and
  emitted once.
* EEIC status / branch / occupation counts (`labour`'s), hours, earnings,
  the youth activity-status counts other than NEET, and the 5-17 block.
* RGPH taux brut d'activité (actifs / TOTAL population -- not a labour force
  participation rate) and Tableau 2.4 (repeats 2.5's national row).
* EESIC Tableau 13's "%" row (57 290 / 230 908 = 24,8, not the printed 13,5:
  denominator unknown); Tableau 17's percentage columns (age distribution
  within each group); Tableau 18's vulnerable / precarious / pluriactivity /
  wage-employment rows (no topic).

EESIC 2013's Tableau 17 "Total" is employed + BIT unemployed + DISCOURAGED
(173 618 + 15 379 + 41 911 = 230 908), so it is filed as a BROAD labour force
and the discouraged as the potential labour force. ITS BASE IS NOT STATED:
the report says its individual questionnaire covers those aged 15 and over
(p. 14), yet Tableau 17 counts 124 employed persons UNDER 15; with the two in
contradiction, EESIC rows carry "not stated" (the age columns of Tableau 17
travel in age_group regardless). Tableau 18's NEET band is 15-35 as printed.

CROSS-CHECK: EEIC 2021 LU1 6,5 (F 7,5, urbain 8,3); LU3 23,5; LFPR 47,9;
EPR 44,8; youth LU1 12,8; NEET 77 895. RGPH 2017 chômage global 22,13 (Mwali
27,5); net activity 58,7 (Ndzuwani 60,8); 15-19 net activity 16,4.
EESIC 2013 employed 173 618; chômeurs BIT 15 379; EPR 40,8; NEET 34,2;
sous-emploi lié à la durée 5,3.
"""
from __future__ import annotations

import itertools
import os
import re

import fitz  # PyMuPDF
import pandas as pd

from . import _common as C

_EEIC = "Enquête sur l'Économie Informelle aux Comores (EEIC) 2021"
_RGPH = "Recensement Général de la Population et de l'Habitation (RGPH) 2017"
_EESIC = "Enquête sur l'Emploi et le Secteur Informel aux Comores (EESIC) 2013, phase 1"

_M, _F = {"sex": "male"}, {"sex": "female"}
_U = {"locality": "urban", "locality_label": "Urbain"}
_R = {"locality": "rural", "locality_label": "Rural"}
_ISLANDS = ("Mwali", "Ndzuwani", "Ngazidja")


def _num(s: str) -> float:
    return float(s.replace(" ", "").replace("%", "").replace(",", "."))


def _which(doc) -> str:
    head = " ".join(doc[i].get_text() for i in range(min(8, len(doc))))
    if re.search(r"Certains indicateurs du march. du travail", head):
        return "eeic"
    # The census cover names the directorate; EESIC's text merely cites the
    # 2003 census, so the bare phrase would misclassify it.
    if re.search(r"DIRECTION NATIONALE DU RECENSEMENT", head):
        return "rgph"
    if re.search(r"Enqu.te sur l.emploi et le secteur informel", head, re.I):
        return "eesic"
    raise ValueError("Comoros: unrecognised document")


# --------------------------------------------------------------------------
# 1. EEIC 2021 key indicators
# --------------------------------------------------------------------------

def _split5(groups: list[str]) -> list[float]:
    """Digit groups -> (M, F, U, R, T) with M+F = T and U+R = T (to 2)."""
    n, sols = len(groups), []
    for cuts in itertools.combinations(range(1, n), 4):
        b = (0, *cuts, n)
        parts = [groups[x:y] for x, y in zip(b, b[1:])]
        if any(len(p[0]) > 3 or any(len(g) != 3 for g in p[1:]) for p in parts):
            continue
        m, f, u, r, t = (int("".join(p)) for p in parts)
        if abs(m + f - t) <= 2 and abs(u + r - t) <= 2:
            sols.append([float(v) for v in (m, f, u, r, t)])
    if len(sols) != 1:
        raise ValueError(f"EEIC: digit groups {groups} split {len(sols)} ways")
    return sols[0]


# (label regex on the accumulated label text, topic, extra) -- in table order.
# `None` topic = read and checked, not emitted.
_EEIC_ROWS = [
    (r"Population totale", None, {}),
    (r"Population en .ge de travailler \(nombre", "working_age_population", {}),
    (r"Proportion de la population en .ge de travailler dans la population",
     None, {}),
    (r"^Taille de la main d.%uvre|^Taille de la main d.œuvre", "labour_force",
     {"key": "labour_force"}),
    (r"Proportion de la population active dans la population en .ge", None,
     {"key": "lfpr"}),
    (r"^Taille de la population occup.e", "employed", {"key": "employed"}),
    (r"Nombre de la population occup.e dans agriculture", None, {}),
    (r"Proportion de la population occup.e dans l.agriculture", None, {}),
    (r"^Emploi Taille de la population occup.e", None, {"key": "employed"}),
    (r"^Ratio emploi-population \(EPR\)", "employment_to_population_ratio", {}),
    (r"^Jeune \(15-34 ans\) \(EPR\)", "employment_to_population_ratio",
     {"age_group": "15-34"}),
    (r"^Population active$", None, {}),
    (r"^Taille de la population active", None, {"key": "labour_force"}),
    (r"^Taux de participation . la population active \(LFPR\)",
     "labour_force_participation_rate", {"definition": "strict", "key": "lfpr"}),
    (r"^Jeune \(15-34 ans\) \(LFPR\)", "labour_force_participation_rate",
     {"definition": "strict", "age_group": "15-34"}),
]
_EEIC_ROWS_2 = [   # after the composition block (p. 5 tail, p. 6)
    (r"^Proportion de l.emploi informel dans l.emploi total hors agriculture",
     "informal_employment_share", {}),
    (r"^Proportion de jeunes \(18-30 ans\) dans l.emploi informel hors",
     "informal_employment_share", {"age_group": "18-30"}),
    (r"^Taux de ch.mage \(LU1\)", "unemployment_rate", {"definition": "strict"}),
    (r"^Taux combin. de ch.mage et d.emploi sous-emploi \(LU2\)",
     "underemployment_rate", {"definition": "broad"}),
    (r"^Taux de ch.mage combin. et population active potentielle \(LU3\)",
     "labour_underutilisation_rate", {"definition": "broad"}),
    (r"^Sous-utilisation composite de la main-d.%uvre \( ?LU4\)|"
     r"^Sous-utilisation composite de la main-d.œuvre \( ?LU4\)",
     "labour_underutilisation_rate", {"definition": "broad"}),
    (r"^Proportion de la population en .ge de travailler en dehors", None, {}),
    (r"^En emploi seulement", None, {}),
    (r"^A l..cole seulement", None, {}),
    (r"^A la fois l..cole et l.emploi", None, {}),
    (r"^Ni en emploi ni en formation \(NEET\)", "neet_rate",
     {"age_group": "15-34", "measure": "count", "unit": "persons"}),
    (r"^Total$", None, {}),
    (r"^Taux de ch.mage des jeunes \(LU1\)", "youth_unemployment_rate",
     {"definition": "strict", "age_group": "15-34"}),
    (r"^Sous-utilisation composite de la main-d..uvre des jeunes \(LU4\)",
     "labour_underutilisation_rate", {"definition": "broad", "age_group": "15-34"}),
]
_NUMTOK = re.compile(r"^\d[\d ]*(?:,\d+)?%?$")
_EEIC_COLS = [_M, _F, _U, _R, {}]


def _runs(tokens: list[str]) -> list[tuple[str, list[str]]]:
    """(label text, numeric tokens) runs, in reading order."""
    out, label, nums = [], [], []
    for t in tokens:
        if _NUMTOK.match(t):
            nums.append(t)
            continue
        if nums:
            out.append((" ".join(label), nums))
            label, nums = [], []
        label.append(t)
    if nums:
        out.append((" ".join(label), nums))
    return out


def _vals(nums: list[str]) -> list[float]:
    if any("," in n for n in nums):          # a rate row: five decimals
        if len(nums) != 5:
            raise ValueError(f"EEIC: rate row reads {nums}")
        return [_num(n) for n in nums]
    return _split5(" ".join(nums).split())


def _eeic(doc, path) -> list[dict]:
    start = next(i for i in range(len(doc))
                 if "Certains indicateurs du marché du travail" in doc[i].get_text())
    tokens = []
    for i in range(start, start + 3):
        lines = [ln.strip() for ln in doc[i].get_text().splitlines() if ln.strip()]
        tokens += [ln for ln in lines if not re.match(r"^\d\d:\d\d ", ln)]
    runs = _runs(tokens)
    # Strip the header words that precede the first row.
    runs[0] = (re.sub(r"^.*?Total\s+", "", runs[0][0]), runs[0][1])
    k_comp = next(i for i, (lab, _) in enumerate(runs)
                  if lab.startswith("Statut dans l'emploi"))
    k_tail = next(i for i, (lab, _) in enumerate(runs)
                  if lab.startswith("Proportion de l'emploi informel"))
    head, tail = runs[:k_comp], runs[k_tail:]
    seen: dict[str, list[float]] = {}
    out = []
    for block, specs in ((head, _EEIC_ROWS), (tail, _EEIC_ROWS_2)):
        if len(block) < len(specs):
            raise ValueError(f"EEIC: {len(block)} rows for {len(specs)} specs")
        for (lab, nums), (pat, topic, extra) in zip(block, specs):
            # section headings ("Emploi", "Sous-utilisation de la main-d'œuvre",
            # "Statut d'activité du jeune") run into the next label
            clean = re.sub(r"^(Sous-utilisation de la main- d'œuvre |Statut "
                           r"d'activité du jeune )", "", re.sub(r"\s+", " ", lab))
            if not re.search(pat, clean):
                raise ValueError(f"EEIC: expected /{pat}/, read {clean!r}")
            vals = _vals(nums)
            # The table prints LF, employed and LFPR twice each (once under a
            # second label); every repeat must agree, and is emitted once.
            key = extra.get("key")
            if key:
                if key in seen:
                    if seen[key] != vals:
                        raise ValueError(f"EEIC: repeated {key} row {vals} "
                                         f"differs from {seen[key]}")
                    if topic is None:
                        continue
                seen[key] = vals
            if topic is None:
                continue
            label = re.sub(r"\s*\(nombre ['‘]000\)", "", clean)
            for ctx, v in zip(_EEIC_COLS, vals):
                out.append(C.row(
                    topic=topic, value=v, series_label=label, survey=_EEIC,
                    period="2021", reference_period="EEIC 2021", frequency="ad_hoc",
                    working_age_base="14-64",
                    definition=extra.get("definition", "not_applicable"),
                    age_group=extra.get("age_group", "Total"),
                    measure=extra.get("measure"), unit=extra.get("unit"),
                    series_code="EEIC 2021 indicateurs", **ctx))
    if seen.get("lfpr") is None:
        raise ValueError("EEIC: LFPR not read")
    return out


# --------------------------------------------------------------------------
# 2. RGPH 2017
# --------------------------------------------------------------------------

def _page_of(doc, caption: str) -> str:
    for p in doc:
        t = p.get_text()
        m = re.search(caption, t)
        # A list-of-tables entry is followed by dot leaders (RGPH) or straight
        # by the next caption (EESIC): neither is the table.
        nxt = t[m.end():m.end() + 250] if m else ""
        if (m and not re.search(r"\.{4}", nxt[:150])
                and not re.search(r"\n\s*Tableau \d+\s*:", nxt)):
            return t[m.start():]
    raise ValueError(f"RGPH: {caption!r} not found")


def _lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines() if ln.strip()]


_DEC = r"\d+,\d+"
_CNT = r"\d{1,3}(?: \d{3})+|\d+"


def _after(lines, label_re, n, where, val=_DEC):
    """The n values that follow a label -- on its own line or the next ones
    (PyMuPDF gives these tables one cell per line)."""
    for i, ln in enumerate(lines):
        if re.match(label_re, ln):
            vals = re.findall(val, ln[re.match(label_re, ln).end():])
            j = i + 1
            while len(vals) < n and j < len(lines) and re.fullmatch(r"[\d, ]+", lines[j]):
                vals += re.findall(val, lines[j])
                j += 1
            if len(vals) != n:
                raise ValueError(f"{where}: {label_re} reads {vals}")
            return [_num(v) for v in vals]
    raise ValueError(f"{where}: {label_re} not found")


def _dec_after(lines, label_re, n, where):
    return _after(lines, label_re, n, where)


def _rgph_row(**kw):
    return C.row(survey=_RGPH, period="2017", reference_period="RGPH 2017",
                 frequency="ad_hoc", **kw)


def _rgph(doc) -> list[dict]:
    out = []
    # Tableau 2.5 -- net activity by island x sex (brut columns skipped).
    L = _lines(_page_of(doc, r"Tableau 2\.5 : Taux d.activit"))
    for isl in (*_ISLANDS, "Comores"):
        v = _dec_after(L, rf"^{isl}$", 6, "RGPH T2.5")
        geo = {} if isl == "Comores" else {"geography": isl}
        for ctx, x in zip((_M, _F, {}), v[3:]):
            out.append(_rgph_row(topic="labour_force_participation_rate",
                                 definition="strict", value=x,
                                 series_label="Taux net d'activité",
                                 working_age_base="15-64",
                                 series_code="RGPH2017 T2.5", **geo, **ctx))
    # Tableau 2.6 -- by milieu x sex (net columns only).
    L = _lines(_page_of(doc, r"Tableau 2\.6 : Taux d.activit"))
    for lab, loc in (("Urbain", _U), ("Rural", _R)):
        v = _dec_after(L, rf"^{lab}\b", 6, "RGPH T2.6")
        for ctx, x in zip((_M, _F, {}), v[3:]):
            out.append(_rgph_row(topic="labour_force_participation_rate",
                                 definition="strict", value=x,
                                 series_label="Taux net d'activité",
                                 working_age_base="15-64",
                                 series_code="RGPH2017 T2.6", **loc, **ctx))
    # Tableau 2.7 -- net activity by age group: Ensemble | Masculin | Féminin.
    L = _lines(_page_of(doc, r"Tableau 2\.7 : Taux net d.activit"))
    for a in range(15, 65, 5):
        v = _dec_after(L, rf"^{a} à {a + 4}\b", 3, "RGPH T2.7")
        for ctx, x in zip(({}, _M, _F), v):
            out.append(_rgph_row(topic="labour_force_participation_rate",
                                 definition="strict", value=x,
                                 series_label="Taux net d'activité",
                                 age_group=f"{a}-{a + 4}", working_age_base="15-64",
                                 series_code="RGPH2017 T2.7", **ctx))
    # Tableau 3.1 -- counts and the taux d'occupation by island.
    L = _lines(_page_of(doc, r"Tableau 3\.1 : Population active occup"))
    geos = [{"geography": g} for g in ("Mwali", "Ndzuwani", "Ngazidja")] + [{}]
    rows31 = {
        "occ": _after(L, r"^Actifs occupés", 4, "RGPH T3.1", _CNT),
        "act": _after(L, r"^Actifs$", 4, "RGPH T3.1", _CNT),
        "pop": _after(L, r"^Population de 15-64 ?ans", 4, "RGPH T3.1", _CNT),
        "rate": _after(L, r"^Taux d.occupation", 4, "RGPH T3.1"),
    }
    for k in ("occ", "act", "pop", "rate"):
        if len(rows31[k]) != 4:
            raise ValueError(f"RGPH T3.1 {k}: {rows31[k]}")
    for k in ("occ", "act", "pop"):
        # Within 2: the actifs row is 249 490 by island against 249 491
        # printed -- INSEED's rounding, kept as published.
        if abs(sum(rows31[k][:3]) - rows31[k][3]) > 2:
            raise ValueError(f"RGPH T3.1 {k}: islands do not sum to Comores")
    if abs(rows31["act"][3] / rows31["pop"][3] * 100 - 58.7) > 0.05:
        raise ValueError("RGPH T3.1: actifs / 15-64 no longer the 58,7 net rate")
    spec = (("occ", "employed", "Actifs occupés"),
            ("act", "labour_force", "Actifs"),
            ("pop", "working_age_population", "Population de 15-64ans"),
            ("rate", "employment_to_population_ratio", "Taux d'occupation"))
    for k, topic, lab in spec:
        for g, v in zip(geos, rows31[k]):
            out.append(_rgph_row(topic=topic, value=v, series_label=lab,
                                 working_age_base="15-64",
                                 series_code="RGPH2017 T3.1", **g))
    # Tableau 3.8 -- employment rate by education: Homme | femme | Total.
    L = _lines(_page_of(doc, r"Tableau 3\.8 : Taux d.emploi par niveau"))
    for lev in ("Aucun", "Primaire", "Collège", "Lycée", "Supérieur", "TOTAL"):
        v = _dec_after(L, rf"^{lev}\b", 3, "RGPH T3.8")
        ed = {} if lev == "TOTAL" else {"education": lev}
        for ctx, x in zip((_M, _F, {}), v):
            out.append(_rgph_row(topic="employment_to_population_ratio", value=x,
                                 series_label="Taux d'emploi",
                                 working_age_base="not stated",
                                 series_code="RGPH2017 T3.8", **ed, **ctx))
    # Tableaux 4.1 / 4.2 -- the "global" block: rows Homme / Femme / Ensemble.
    for cap, cols, code in (
            (r"Tableau 4\.1 : Taux de ch.mage", [_U, _R, {}], "RGPH2017 T4.1"),
            (r"Tableau 4\.2 : Taux de ch.mage",
             [{"geography": g} for g in _ISLANDS] + [{}], "RGPH2017 T4.2")):
        text = _page_of(doc, cap)
        g = text[text.index("Taux de Chômage global" if "Chômage global" in text
                            else "Taux de chômage global"):]
        L = _lines(g)[1:]
        n = len(cols)
        nums = []
        for ln in L:
            if ln.startswith("Source"):
                break
            nums += re.findall(r"\d+,\d+", ln)
        if len(nums) != 3 * n:
            raise ValueError(f"{code}: global block reads {nums}")
        vals = [_num(x) for x in nums]
        for si, sx in enumerate((_M, _F, {})):
            for ctx, x in zip(cols, vals[si * n:(si + 1) * n]):
                if code.endswith("4.2") and not ctx and sx == {}:
                    continue         # national total = 4.1's
                if code.endswith("4.2") and not ctx:
                    continue         # national by sex = 4.1's
                out.append(_rgph_row(topic="unemployment_rate", definition="strict",
                                     value=x, series_label="Taux de chômage global",
                                     working_age_base="15+", series_code=code,
                                     **ctx, **sx))
    # Tableau 4.3 -- by education: Homme | Femme | Total.
    L = _lines(_page_of(doc, r"Tableau 4\.3 : Taux de ch.mage"))
    for lev in ("Sans niveaux", "Primaire", "Secondaire", "Supérieur",
                "Ecole coranique"):
        v = _dec_after(L, rf"^{lev}\b", 3, "RGPH T4.3")
        for ctx, x in zip((_M, _F, {}), v):
            out.append(_rgph_row(topic="unemployment_rate", definition="strict",
                                 value=x, series_label="Taux de chômage global",
                                 education=lev, working_age_base="15+",
                                 series_code="RGPH2017 T4.3", **ctx))
    nat = _dec_after(L, r"^Ensemble\b", 3, "RGPH T4.3")
    t41 = [r["value"] for r in out if r["series_code"] == "RGPH2017 T4.1"
           and r["locality"] == "all"]
    if [round(x, 1) for x in nat] != [round(x, 1) for x in t41]:
        raise ValueError(f"RGPH: 4.3's Ensemble {nat} disagrees with 4.1 {t41}")
    return out


# --------------------------------------------------------------------------
# 3. EESIC 2013
# --------------------------------------------------------------------------

def _eesic_row(**kw):
    return C.row(survey=_EESIC, period="2013", reference_period="EESIC 2013",
                 frequency="ad_hoc", **kw)


_EESIC_GROUPS = [("Moroni", {"geography": "Moroni"}),
                 ("Reste de Ngazidja", {"geography": "Reste de Ngazidja"}),
                 ("Ndzouani", {"geography": "Ndzouani"}),
                 ("Mwali", {"geography": "Mwali"}),
                 ("Urbain", _U), ("Rural", _R),
                 ("Masculin", _M), ("Féminin", _F), ("Ensemble", {})]


def _eesic_runs(lines: list[str]) -> list[tuple[str, list[float]]]:
    """(label, values) runs from one-cell-per-line text; ",8" is 0,8."""
    out, label, vals = [], [], []
    for ln in lines:
        toks = ln.split()
        if toks and all(re.fullmatch(r"\d+|\d*,\d+", t) for t in toks):
            vals += [_num("0" + t if t.startswith(",") else t) for t in toks]
            continue
        if vals:
            out.append((" ".join(label), vals))
            label, vals = [], []
        label.append(ln)
    if vals:
        out.append((" ".join(label), vals))
    return out


def _eesic(doc) -> list[dict]:
    out = []
    # Tableau 17: per group four rows -- Actif occupé / Chômeur BIT / Chômeur
    # découragé / Total -- each 4 counts (<15, 15-64, 65+, Total) then 4
    # percentages (the age distribution within the row: not collected).
    L = _lines(_page_of(doc, r"Tableau 17 : Structure de la population active"))
    L = L[:next(i for i, x in enumerate(L) if x.startswith("Source"))]
    runs = [(lab, v) for lab, v in _eesic_runs(L) if v]
    if len(runs) != 36 or any(len(v) != 8 for _, v in runs):
        raise ValueError(f"EESIC T17: {len(runs)} rows, widths "
                         f"{sorted({len(v) for _, v in runs})}")
    kinds = [(r"Actif occup", "employed", "Actif occupé", "not_applicable"),
             (r"Ch.meur BIT", "unemployed", "Chômeur BIT", "strict"),
             (r"Ch.meur d.courag", "potential_labour_force", "Chômeur découragé",
              "not_applicable"),
             (r"Total$", "labour_force",
              "Total (actifs occupés, chômeurs BIT et découragés)", "broad")]
    ages = ["Moins de 15 ans", "15-64 ans", "65 et plus", "Total"]
    for gi, (gname, ctx) in enumerate(_EESIC_GROUPS):
        block = runs[gi * 4:(gi + 1) * 4]
        if not block[0][0].replace(" ", "").endswith("Actifoccupé") or \
                not re.sub(r"\s", "", block[0][0]).find(re.sub(r"\s", "", gname)) >= 0:
            raise ValueError(f"EESIC T17: group {gname!r} starts with {block[0][0]!r}")
        for j in range(4):
            if abs(sum(b[1][j] for b in block[:3]) - block[3][1][j]) > 2:
                raise ValueError(f"EESIC T17 {gname}: rows do not sum to Total")
        for (pat, topic, lab, dfn), (text, v) in zip(kinds, block):
            if not re.search(pat, text):
                raise ValueError(f"EESIC T17 {gname}: expected {lab}, read {text!r}")
            if abs(sum(v[:3]) - v[3]) > 2:
                raise ValueError(f"EESIC T17 {gname} {lab}: ages do not sum: {v[:4]}")
            for age, x in zip(ages, v[:4]):
                out.append(_eesic_row(topic=topic, definition=dfn, value=x,
                                      series_label=lab, age_group=age if age != "Total"
                                      else "Total", working_age_base="not stated",
                                      series_code="EESIC2013 T17", **ctx))
    # Tableau 18: Moroni | Reste Ngazidja | Ndzouani | Mwali | Urbain | Rural |
    # Masculin | Féminin | Total -- the header prints them in that order.
    L = _lines(_page_of(doc, r"Tableau 18 : Indicateurs de l.insertion"))
    runs = _eesic_runs(L[:next(i for i, x in enumerate(L) if x.startswith("Source"))])
    cols18 = [c for _, c in _EESIC_GROUPS]
    want = {r"Ratio emploi- population$": ("employment_to_population_ratio",
                                          "Ratio emploi-population", "Total"),
            r"Jeunes de 15-35 ans ni dans l'emploi ni dans le système éducatif$":
                ("neet_rate", "Jeunes de 15-35 ans ni dans l'emploi ni dans le "
                              "système éducatif", "15-35")}
    got = 0
    for text, v in runs:
        for pat, (topic, lab, age) in want.items():
            if re.search(pat, text):
                if len(v) != 9:
                    raise ValueError(f"EESIC T18 {lab}: {v}")
                got += 1
                for ctx, x in zip(cols18, v):
                    out.append(_eesic_row(topic=topic, value=x, series_label=lab,
                                          age_group=age, working_age_base="not stated",
                                          series_code="EESIC2013 T18", **ctx))
    if got != 2:
        raise ValueError(f"EESIC T18: {got} of 2 rows read")
    # Tableau 25: sous-emploi lié à la durée is the first of three columns.
    L = _lines(_page_of(doc, r"Tableau 25 : Indicateurs des conditions"))
    runs = dict((t.split(" ")[-1] if t else t, v) for t, v in
                _eesic_runs(L[:next(i for i, x in enumerate(L) if x.startswith("Source"))]))
    names = {"Moroni": "Moroni", "Reste de Ngazidja": "Ngazidja",
             "Ndzouani": "Ndzouani", "Mwali": "Mwali", "Urbain": "Urbain",
             "Rural": "Rural", "Masculin": "Masculin", "Féminin": "Féminin",
             "Ensemble": "Total"}
    for gname, ctx in _EESIC_GROUPS:
        v = runs.get(names[gname])
        if not v or len(v) != 3:
            raise ValueError(f"EESIC T25: {gname} reads {v}")
        out.append(_eesic_row(topic="underemployment_rate", value=v[0],
                              series_label="Taux de sous emploi lié à la durée",
                              working_age_base="not stated", series_code="EESIC2013 T25",
                              **ctx))
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        with fitz.open(p) as doc:
            kind = _which(doc)
            rows += {"eeic": lambda: _eeic(doc, p), "rgph": lambda: _rgph(doc),
                     "eesic": lambda: _eesic(doc)}[kind]()
    return pd.DataFrame(rows)
