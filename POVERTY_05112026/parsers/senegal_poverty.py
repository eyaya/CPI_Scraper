"""Senegal -- monetary-poverty layout (ANSD, EHCVM 2018/2019 final report).

Welfare = annual consumption per capita ("dépenses de consommation par tête").
Lines, from the report's "Tableau des principaux résultats":
    Seuil de pauvreté annuel             333 440 FCFA
    Seuil de l'extrême pauvreté annuel   186 869 FCFA

THE 2011 COLUMNS ARE ANSD'S RE-LINKED ("raccordés") ESPS-II ESTIMATES, made
comparable with EHCVM by the bridging described in chapter II -- NOT the
originally published ESPS-II 2011 figures (which put P0 at 46,7%). They are
filed under their own `survey` so they can never overwrite or be confused
with the original round. Their line amount is not printed, so line_value is
blank on 2011 cells.

Every Chapter III/IV table shares its row labels ("Dakar Urbain", "Rural",
"Total") with its neighbours on the same page, so each table is bounded by
`start` (its caption) and `end` ("Source").

Collected:
  III-1  strata: P0 2011 & 2018/19, absolute contribution (points of the
         national P0; strata sum to it) 2011 & 2018/19
  III-2  strata: number of poor 2011 & 2018/19
  III-3  strata: P1, P2 2011 & 2018/19
  III-6  strata: extreme P0 and absolute contribution 2011 & 2018; counts of
         the extreme poor for Dakar urbain / Autres urbains only
  IV-1   all-urban P0 P1 P2, population share, share of the poor; rural
         population share and share of the poor
  IV-2   14 regions: population share, P0, P1, P2, share of the poor
  IV-3   household size: P0 P1 P2, P0 urban / rural, share of the poor
  IV-4   age of head x sex of head: P0 and extreme P0 (Homme/Femme/National),
         population share, share of the poor
  IV-5   education of head x sex of head: same, without population share
  IV-6..IV-10  marital status, activity status, institutional sector, status in
         employment, branch of the head: population share, P0, P1, P2, share
         of the poor. IV-8..IV-10 cover ONLY people whose household head is
         employed -- their shares are of that sub-population.
Not collected: Totals that repeat a value already taken (national P0/P1/P2 of
IV-1/IV-2, Total contributions = the national P0), mean consumption and Gini
(inequality, a separate indicator), Variation columns (derived), population
counts, III-4 (decile consumption), III-5 (elasticities), the key-results
table (duplicates III-1/III-3/III-6), and the RURAL and TOTAL extreme-poor
COUNTS of III-6, whose cells wrap over three lines in the text layer
("1 424" / "882 145 ..." / "022") -- rebuilding them would mean guessing which
fragment belongs to which column.

CROSS-CHECK (verbatim): P0 37,8 (2018/19), 42,8 (2011); P1 10,3 / 13,8;
P2 3,9 / 6,3; extreme 6,8 / 12,2; Dakar urbain 8,7; rural 53,6; urban 19,8;
Sédhiou 65,6, Dakar 9,0; poor 6 032 056 (2018/19), 5 832 008 (2011);
female-headed P0 21,8 is in a chart only (Graphique IV-5), not a table.
"""
from __future__ import annotations

import re

from . import poverty_tables as T
from ._vocab import label_rows
from .poverty_tables import make_parser

_LINE18 = {"line_value": 333440, "line_unit": "XOF per person per year"}
_XLINE = {"line_level": "extreme", "line_name": "Seuil de l'extrême pauvreté",
          "line_value": 186869, "line_unit": "XOF per person per year"}
_Y11 = {"period": "2011", "survey": "ESPS-II 2011 (raccordé EHCVM)",
        "reference_period": "2011", "line_value": "", "line_unit": ""}
_Y18 = {"period": "2018", "survey": "EHCVM 2018/19", "reference_period": "2018/19"}
_SKIP = {"skip": True}

_STRATA = [
    {"match": r"^Dakar Urbain(?=\s)", "topic": "locality", "locality": "other",
     "locality_label": "Dakar urbain"},
    {"match": r"^Autres Urbains(?=\s)", "topic": "locality", "locality": "other",
     "locality_label": "Autres urbains"},
    {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural",
     "locality_label": "Rural"},
]
_TOTAL = {"match": r"^Total(?=\s)"}


def _c(metric, *specs, **kw):
    """A column spec; later specs override earlier ones (so _Y11 blanks the
    line amount an extreme-line spec carries)."""
    out = {"metric": metric}
    for d in specs:
        out.update(d)
    out.update(kw)
    return out


def _tbl(caption, start, columns, rows, **kw):
    return {"page_contains": caption, "start": start, "end": r"^Source", "columns": columns,
            "rows": rows, **kw}


# P0 | P1 | P2 | share of the poor, preceded by the population share (IV-6..IV-10)
_POP_P012_C0 = [_c("population_share", _Y18), _c("headcount", _Y18, **_LINE18),
                _c("gap", _Y18, **_LINE18), _c("severity", _Y18, **_LINE18),
                _c("poor_share", _Y18, **_LINE18)]
# Homme | Femme | National for P0, then for extreme P0 (IV-4, IV-5)
_HFN = [{"sex": "male"}, {"sex": "female"}, {"sex": "total"}]
_P0_HFN = [_c("headcount", _Y18, **_LINE18, **s) for s in _HFN]
_XP0_HFN = [_c("headcount", _Y18, **_XLINE, **s) for s in _HFN]

LAYOUT = {
    "survey": "EHCVM 2018/19", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall", "line_name": "Seuil de pauvreté",
    "period": "2018", "reference_period": "2018/19",
    "tables": [
        _tbl(["tableau iii-1", "evolution du taux de pauvreté"], r"^Tableau III-1\b",
             [_c("headcount", _Y11), _c("headcount", _Y18, **_LINE18), _SKIP,
              _c("absolute_contribution", _Y11), _c("absolute_contribution", _Y18, **_LINE18), _SKIP],
             _STRATA + [dict(_TOTAL, columns=[_c("headcount", _Y11),
                                              _c("headcount", _Y18, **_LINE18)])],
             exact_numbers=False),
        _tbl(["tableau iii-3", "profondeur et de la sévérité"], r"^Tableau III-3\b",
             [_c("gap", _Y11), _c("gap", _Y18, **_LINE18), _SKIP,
              _c("severity", _Y11), _c("severity", _Y18, **_LINE18), _SKIP],
             _STRATA + [_TOTAL]),
        _tbl(["tableau iii-6", "evolution de l'extrême pauvreté"], r"^Tableau III-6\b",
             [_c("headcount", _XLINE, _Y11),
              _c("headcount", _Y18, **_XLINE), _SKIP,
              _c("absolute_contribution", _XLINE, _Y11),
              _c("absolute_contribution", _Y18, **_XLINE), _SKIP],
             [dict(r, columns=None) for r in _STRATA[:2]]
             + [dict(_STRATA[2], take="leading")]
             + [dict(_TOTAL, columns=[
                 _c("headcount", _XLINE, _Y11),
                 _c("headcount", _Y18, **_XLINE)])],
             take="leading"),
        _tbl(["tableau iv-1", "indicateurs de la pauvreté selon le milieu"], r"^Tableau IV-1\s*:",
             [_c("population_share", _Y18), _SKIP, _c("headcount", _Y18, **_LINE18),
              _c("gap", _Y18, **_LINE18), _c("severity", _Y18, **_LINE18),
              _c("poor_share", _Y18, **_LINE18), _SKIP],
             [{"match": r"^Urbain(?=\s)", "topic": "locality", "locality": "urban",
               "locality_label": "Urbain"},
              {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural",
               "locality_label": "Rural",
               "columns": [_c("population_share", _Y18), _SKIP, _SKIP, _SKIP, _SKIP,
                           _c("poor_share", _Y18, **_LINE18), _SKIP]}],
             exact_numbers=True),
        {"page_contains": ["tableau iv-2", "indicateurs de la pauvreté selon la région"],
         "start": r"^Tableau IV-2\s*:", "end": r"^Source", "exact_numbers": True,
         "columns": [_c("population_share", _Y18), _SKIP, _c("headcount", _Y18, **_LINE18),
                     _c("gap", _Y18, **_LINE18), _c("severity", _Y18, **_LINE18),
                     _c("poor_share", _Y18, **_LINE18), _SKIP],
         "row_scan": {"expect_rows": 14, "exclude_labels": ["SENEGAL"],
                      "label_ok": r"^[A-Z][A-Z\-]+$"}},
        _tbl(["tableau iv-3", "pauvreté et taille du ménage"], r"^Tableau IV-3\s*:",
             [_c("headcount", _Y18, **_LINE18), _c("gap", _Y18, **_LINE18),
              _c("severity", _Y18, **_LINE18),
              _c("headcount", _Y18, **_LINE18, locality="urban", locality_label="Urbain"),
              _c("headcount", _Y18, **_LINE18, locality="rural", locality_label="Rural"),
              _c("poor_share", _Y18, **_LINE18), _SKIP],
             label_rows("household_size", ["1-4 personnes", "5-9 personnes", "10-14 personnes",
                                           "15-19 personnes", "20 personnes ou plus"]),
             exact_numbers=True),
        _tbl(["tableau iv-4", "pauvreté selon l'âge et le sexe du cm"], r"^Tableau IV-4\s*:",
             _P0_HFN + _XP0_HFN + [_c("population_share", _Y18), _c("poor_share", _Y18, **_LINE18)],
             label_rows("age_of_head", ["Moins de 24 ans", "25 à 39 ans", "40 à 49 ans",
                                        "50 à 59 ans", "60 ans ou plus"]),
             exact_numbers=True),
        _tbl(["tableau iv-5", "niveau d'instruction et le sexe du cm"], r"^Tableau IV-5\s*:",
             _P0_HFN + _XP0_HFN + [_c("poor_share", _Y18, **_LINE18)],
             label_rows("education_of_head", ["Aucun niveau", "Primaire", "Secondaire", "Supérieur"]),
             exact_numbers=True),
        _tbl(["tableau iv-6", "pauvreté selon la situation matrimoniale"], r"^Tableau IV-6\s*:",
             _POP_P012_C0,
             label_rows("marital_status_of_head", ["Jamais marié", "Marié monogame",
                                                   "Marié polygame", "Divorcé ou veuf"]),
             exact_numbers=True),
        _tbl(["tableau iv-7", "statut d’occupation du cm"], r"^Tableau IV-7\s*:", _POP_P012_C0,
             label_rows("employment_of_head", ["Actif occupé", "Chômeurs", "Inactifs"]),
             exact_numbers=True),
        _tbl(["tableau iv-8", "secteur (institutionnel) d’activité du cm"], r"^Tableau IV-8\s*:",
             _POP_P012_C0,
             label_rows("employment_of_head", [
                 "Administration, entreprise publique, organisme international",
                 "Entreprise privée/ONG", "Ménage comme employeur de personnel domestique"]),
             exact_numbers=True),
        _tbl(["tableau iv-9", "statut dans la profession du cm"], r"^Tableau IV-9\s*:",
             _POP_P012_C0,
             label_rows("employment_of_head", ["Salarié", "Tâcheron/aide familial et autres",
                                               "Compte propre"]),
             exact_numbers=True),
        _tbl(["tableau iv-10", "branche d’activité du cm"], r"^Tableau IV-10\s*:", _POP_P012_C0,
             label_rows("employment_of_head", [
                 "Agriculture", "Elevage/pêche", "Industries extractives", "Autres industries,",
                 "BTP", "Commerce", "Restaurant/Hôtel", "Transports/Communications",
                 "Education/Sante", "Services personnel", "Autres services"]),
             exact_numbers=True),
    ],
}

_engine = make_parser(LAYOUT)

# --- counts of the poor, read from WORD GEOMETRY ----------------------------
# Tableaux III-2 and III-6 print space-grouped counts side by side
# ("448 197 308 867 -139 330"), which no text pattern can split: "448 197 308
# 867" is equally one number. On the page the gap INSIDE a number is ~3pt and
# BETWEEN columns >= 18pt, so numbers are rebuilt from word x-gaps. In III-6
# the Rural and Total count cells wrap over two lines ("1 424" above the label
# line, "022" below); those fragments are collected by column band within
# +-8pt of the row's label. Either way the result is ACCEPTED ONLY IF the
# three strata sum exactly to the printed Total, for every column read.
_GAP = 8.0


def _numbers(words) -> list[tuple[float, float]]:
    """(x0, value) per number in a run of words, joined by x-gap."""
    out, cur, x0, last = [], "", None, None
    for w in sorted(words, key=lambda w: w["x0"]):
        t = w["text"]
        if not re.fullmatch(r"-?\d{1,3}", t):
            continue
        if cur and last is not None and w["x0"] - last < _GAP and re.fullmatch(r"\d{3}", t):
            cur += t
        else:
            if cur:
                out.append((x0, float(cur)))
            cur, x0 = t, w["x0"]
        last = w["x1"]
    if cur:
        out.append((x0, float(cur)))
    return out


def _label_tops(words, labels):
    tops = {}
    for w in words:
        for lab in labels:
            if w["text"] == lab.split()[0] and lab not in tops and w["x0"] < 110:
                tops[lab] = w["top"]
    return tops


_LABELS = ["Dakar Urbain", "Autres Urbains", "Rural", "Total"]
_SPEC = {s["locality_label"]: s for s in _STRATA}
_SPEC_BY_PRINTED = {"Dakar Urbain": _SPEC["Dakar urbain"], "Autres Urbains": _SPEC["Autres urbains"],
                    "Rural": _SPEC["Rural"], "Total": {}}


def _check_sum(name, vals):
    parts = [vals[k] for k in _LABELS[:3]]
    if any(v is None for v in parts + [vals["Total"]]) or sum(parts) != vals["Total"]:
        raise ValueError(f"{name}: strata {parts} do not sum to the printed Total "
                         f"{vals['Total']} -- the count layout changed; re-read the PDF")


def _geometry_counts(path: str) -> list[dict]:
    import pdfplumber
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # the List of Tables repeats both captions, with no data under them
            if "Dakar Urbain" not in text:
                continue
            if "Tableau III-2. Evolution des effectifs" in text:
                words = page.extract_words()
                cap = min(w["top"] for w in words if w["text"] == "III-2.")
                words = [w for w in words if w["top"] > cap]
                tops = _label_tops(words, _LABELS)
                per = {}
                for lab, top in tops.items():
                    nums = _numbers([w for w in words if abs(w["top"] - top) < 3 and w["x0"] > 150])
                    per[lab] = nums[:2]
                for i, (spec_y, col) in enumerate(((_Y11, None), (_Y18, _LINE18))):
                    vals = {lab: (per[lab][i][1] if len(per.get(lab, [])) > i else None) for lab in _LABELS}
                    _check_sum(f"III-2 {spec_y['period']}", vals)
                    for lab, v in vals.items():
                        cell = T._merge(_SPEC_BY_PRINTED[lab], _c("poor_count", spec_y, **(col or {})))
                        rows.append(T._emit(cell, v, LAYOUT, "2018", "2018/19", f"III-2 {lab}"))
            if "Tableau III-6. Evolution de l'extrême pauvreté" in text:
                words = page.extract_words()
                tops = _label_tops(words, _LABELS)
                bands = {"2011": (375, 420), "2018": (425, 465)}
                for year, (lo, hi) in bands.items():
                    vals = {}
                    for lab, top in tops.items():
                        frag = sorted([w for w in words if lo <= w["x0"] < hi and abs(w["top"] - top) <= 8
                                       and re.fullmatch(r"\d{1,3}", w["text"])],
                                      key=lambda w: (round(w["top"]), w["x0"]))
                        vals[lab] = float("".join(w["text"] for w in frag)) if frag else None
                    _check_sum(f"III-6 {year}", vals)
                    spec_y = _Y11 if year == "2011" else _Y18
                    for lab, v in vals.items():
                        cell = T._merge(_SPEC_BY_PRINTED[lab], _c("poor_count", _XLINE, spec_y))
                        rows.append(T._emit(cell, v, LAYOUT, "2018", "2018/19", f"III-6 {lab}"))
    if len(rows) != 16:
        raise ValueError(f"expected 16 count rows from III-2 and III-6, got {len(rows)}")
    return rows


def parse(path: str):
    import pandas as pd
    df = _engine(path)
    return pd.concat([df, pd.DataFrame(_geometry_counts(path))], ignore_index=True)
