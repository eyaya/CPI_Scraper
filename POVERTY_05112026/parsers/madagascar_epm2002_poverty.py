"""Madagascar -- EPM 2002, INSTAT rapport principal (novembre 2003), chapter 4.

Person level, national line; "Intensité" = P1.
Collected:
  31  2002 P0, P1, number of poor and contribution to national poverty for
      Madagascar, the six former provinces, and urban/rural x province
  33  P0, P1, contribution by sex of the head (all households block; the
      second block excludes singletons and households above 6 -- a
      sub-population)
  36  P0, P1, contribution by socio-economic group of the head
  37  1999 and 2001 P0/P1 for the same strata, filed "EPM <year> (as
      republished in EPM 2002)" -- the only source collected here for 1999
      province detail. (Its 2002 columns repeat Tableau 31.)
  38  2001 P0/P1 by GSE (its 2002 columns repeat 36; the wrapped
      "Commerçant entrepreneur" row prints only two cells and is skipped)
NOT collected: 32/34 (share of under-5s / of schooled members -- no topic),
35 (living practices), 39 (simulations), the "gap in billions" column.

TEXT REPAIR: the national row prints "13 293 000 100,0", which the
space-thousands rule reads as ONE number (13 293 000 100,0). On Tableau 31's
page only, a 3-digit group followed by a space and a decimal number is split
("000 | 100,0"); counts there are integers and every other cell a decimal.

CROSS-CHECK (verbatim): 80,7 / 47,6; 13 293 000 poor; Fianarantsoa 91,0;
Mahajanga rural 93,8 / 63,8; 1999 71,3 / 32,8; 2001 Antananarivo 48,3.
Province contributions sum to 100,1.
"""
from __future__ import annotations

import re

from .poverty_tables import make_parser

_PROV = ["Antananarivo", "Fianarantsoa", "Toamasina", "Mahajanga", "Toliara", "Antsiranana"]
_UL = {"topic": "locality", "locality": "urban", "locality_label": "Urbain"}
_RL = {"topic": "locality", "locality": "rural", "locality_label": "Rural"}
_C31 = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "poor_count"},
        {"metric": "poor_share"}, {"skip": True}]


def _yr(y):
    return {"period": y, "reference_period": y, "survey": f"EPM {y} (as republished in EPM 2002)"}


_C37 = [{"metric": "headcount", **_yr("1999")}, {"metric": "headcount", **_yr("2001")}, {"skip": True},
        {"metric": "gap", **_yr("1999")}, {"metric": "gap", **_yr("2001")}, {"skip": True}]


def _strata(caption, start, end, loc, cols, national):
    rows = [{"match": rf"^{p}(?=\s+\d)", "geography": f"{p} (province)", **loc} for p in _PROV]
    rows.append({"match": rf"^{national}(?=\s+\d)", **loc})
    return {"page_contains": [caption], "start": start, "start_inclusive": True, "end": end,
            "exact_numbers": True, "columns": cols, "rows": rows}


_T31 = "tableau 31 synthèses des indicateurs de pauvreté en 2002"
_T37 = "tableau 37 evolution de la pauvreté de 1999 à 2002"

LAYOUT = {
    "survey": "EPM 2002", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ",", "line_type": "national", "line_level": "overall",
    "line_name": "Seuil national de pauvreté", "period": "2002", "reference_period": "2002",
    "tables": [
        _strata(_T31, r"^Madagascar", r"^Urbain", {}, _C31, "Madagascar"),
        _strata(_T31, r"^Urbain", r"^Rural", _UL, _C31, "Urbain"),
        _strata(_T31, r"^Rural", r"^Source", _RL, _C31, "Rural"),
        _strata(_T37, r"^Madagascar", r"^Urbain", {}, _C37, "Madagascar"),
        _strata(_T37, r"^Urbain", r"^Rural", _UL, _C37, "Urbain"),
        _strata(_T37, r"^Rural", r"^Source", _RL, _C37, "Rural"),
        {"page_contains": ["tableau 33 indicateurs de pauvreté selon le genre du cm"],
         "start": r"^Genre du CM pauvreté", "end": r"^Ensemble", "exact_numbers": True,
         "columns": [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "poor_share"}],
         "rows": [{"match": r"^Masculin(?=\s)", "topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"},
                  {"match": r"^Féminin(?=\s)", "topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}]},
        {"page_contains": ["tableau 36 indicateurs de pauvreté selon les gse du cm"],
         "start": r"^GSE du chef de ménage", "end": r"^Ensemble", "exact_numbers": True,
         "columns": [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "poor_share"}],
         "rows": [{"match": r"^" + re.escape(g) + r"(?=\s+\d)", "topic": "employment_of_head", "characteristic": g}
                  for g in ("Grand exploitant agricole", "Moyen exploitant agricole", "Petit exploitant agricole",
                            "Eleveur, pêcheur", "Entrepreneur non agricole", "Commerçant/ entrepreneur",
                            "Cadre salarié", "Employés et ouvriers", "Main d’œuvre sans qualification", "Autre")]},
        {"page_contains": ["tableau 38 evolution de la pauvreté de 1999 à 2002 selon les strates"],
         "start": r"^Année 2001 2002", "end": r"^Ensemble", "exact_numbers": True,
         "columns": [{"metric": "headcount", **_yr("2001")}, {"skip": True},
                     {"metric": "gap", **_yr("2001")}, {"skip": True}],
         "rows": [{"match": r"^" + re.escape(lab) + r"(?=\s+\d)", "topic": "employment_of_head", "characteristic": ch}
                  for lab, ch in (("Grand exploitant agricole", "Grand exploitant agricole"),
                                  ("Moyen exploitant agricole", "Moyen exploitant agricole"),
                                  ("Petit exploitant agricole", "Petit exploitant agricole"),
                                  ("Eleveur pêcheur", "Eleveur, pêcheur"),
                                  ("Entrepreneur non agricole", "Entrepreneur non agricole"),
                                  ("Cadre salarie", "Cadre salarié"),
                                  ("Employés et ouvriers", "Employés et ouvriers"),
                                  ("Main d oeuvre sans qualification", "Main d’œuvre sans qualification"),
                                  ("Autre", "Autre"))]},
    ],
}

_base = make_parser(LAYOUT)


def parse(path: str):
    from . import poverty_tables as T
    orig = T._pages

    def pages(p, halves=True):
        out = orig(p, halves)
        out["full"] = [re.sub(r"(\d{3}) (\d{1,3},\d)", r"\1 | \2", t) if "Tableau 31 Synthèses" in t else t
                       for t in out["full"]]
        return out
    T._pages = pages
    try:
        return _base(path)
    finally:
        T._pages = orig
