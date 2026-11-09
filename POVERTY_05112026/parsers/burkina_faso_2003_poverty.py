"""Burkina Faso -- the older INSD rounds, from two Wayback `id_` copies of
INSD's own files (insd.bf/contenu/...).

parse  -- "Burkina Faso : La Pauvreté en 2003" (Profil_Pauvrete_2003.pdf),
          EP III 2003 (Enquête burkinabè sur les conditions de vie des
          ménages, avril-juillet 2003). Line 82 672 FCFA per person per year.
          Tableau 2 (13 regions: P0 C0 P1 C1 P2), 3 (HOUSEHOLD P0 by milieu,
          "Pauvres" row), 4 (milieu), 5 (sex of the person), 6 (sex of the
          head), 10 (national P0 P1 P2 for EP I 1994, EP II 1998, EP III 2003
          with each round's line) and 11 (milieu x 1994 / 1998 / 2003).
          1994 and 1998 are the series as republished in this report.
          PUBLISHED INCONSISTENCY kept as printed: Tableau 11's 2003 Ensemble
          P1/P2 read 15,5 / 7,0 against 15,6 / 7,1 in Tableaux 2, 4, 10 -- so
          the 2003 national row is taken from Tableau 4 only.
parse_eicvm -- "Analyse succincte des résultats provisoires de l'EICVM
          2009-2010" (resultats_provisoires_eicvm.pdf): Tableau 1, HOUSEHOLD
          P0 and 95% CI for Urbain and Rural (line 108 454 FCFA). INSD calls
          these PROVISIONAL and the survey's method new; the national 43,9%
          [41,2; 46,6] and the regional values appear only in prose / a chart
          and are not taken.

CROSS-CHECK (verbatim): 2003 46,4 / 15,6 / 7,1; Nord 68,6; Centre 22,3;
households 37,5; female head 36,5; 1994 44,5 / 13,9 / 6,0; 1998 45,3;
EICVM urban 19,9 [16,7; 23,1], rural 50,7.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T

_EP = {"1994": ("EP I 1994", "oct. 1994-janv. 1995", 41099),
       "1998": ("EP II 1998", "mai-août 1998", 72690),
       "2003": ("EP III 2003", "avril-juillet 2003", 82672)}
_LINE = "Seuil de pauvreté absolue (Enquêtes prioritaires)"
_FIVE = [{"metric": "headcount"}, {"metric": "poor_share"}, {"metric": "gap"},
         {"metric": "gap_contribution"}, {"metric": "severity"}]
_REGIONS = ["Hauts Bassins", "Boucle du Mouhoun", "Sahel", "Est", "Sud Ouest", "Centre Nord",
            "Centre Ouest", "Plateau central", "Nord", "Centre Est", "Centre", "Cascades",
            "Centre Sud"]
_GEO = {"Hauts Bassins": "Hauts-Bassins", "Sud Ouest": "Sud-Ouest", "Centre Nord": "Centre-Nord",
        "Centre Ouest": "Centre-Ouest", "Plateau central": "Plateau-Central",
        "Centre Est": "Centre-Est", "Centre Sud": "Centre-Sud"}

LAYOUT = {
    "survey": "EP III 2003", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall", "line_name": _LINE,
    "line_value": 82672, "line_unit": "XOF per person per year",
    "period": "2003", "reference_period": "avril-juillet 2003",
    "tables": [
        {"page_contains": ["tableau 2 : indices de pauvreté par région"], "exact_numbers": True,
         "columns": _FIVE,
         "rows": [{"match": rf"^{re.escape(r)}(?=\s+[\d,])", "geography": _GEO.get(r, r)}
                  for r in _REGIONS]},
        {"page_contains": ["tableau 3 : incidence de la pauvreté au sein des ménages"],
         "start": r"^Tableau 3 :", "end": r"^Total", "exact_numbers": True,
         "defaults": {"unit_of_analysis": "household"},
         "columns": [{"metric": "headcount", "topic": "locality", "locality": "rural",
                      "locality_label": "Rural", "characteristic": "Rural"},
                     {"metric": "headcount", "topic": "locality", "locality": "urban",
                      "locality_label": "Urbain", "characteristic": "Urbain"},
                     {"metric": "headcount"}],
         "rows": [{"match": r"^Pauvres(?=\s)"}]},
        {"page_contains": ["tableau 4 :", "au sein de la population selon le milieu"],
         "start": r"^Tableau 4 :", "end": r"^Indices de pauvret. selon le genre",
         "exact_numbers": True, "columns": _FIVE,
         "rows": [{"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
                  {"match": r"^Urbain(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Urbain"},
                  {"match": r"^Ensemble(?=\s)"}]},
        {"page_contains": ["tableau 5 :", "de la population selon le genre"],
         "start": r"^Tableau 5 :", "exact_numbers": True, "columns": _FIVE,
         "rows": [{"match": r"^Masculin(?=\s)", "topic": "sex", "characteristic": "Masculin", "sex": "male"},
                  {"match": r"^Féminin(?=\s)", "topic": "sex", "characteristic": "Féminin", "sex": "female"}]},
        {"page_contains": ["tableau 6 :", "selon le genre du chef"],
         "start": r"^Tableau 6 :", "end": r"^2\.2", "exact_numbers": True, "columns": _FIVE,
         "rows": [{"match": r"^Masculin(?=\s)", "topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"},
                  {"match": r"^Féminin(?=\s)", "topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}]},
    ],
}


def _row(per, metric, value, **kw):
    sv, ref, line = _EP[per]
    if per != "2003":
        sv += " (républié, profil 2003)"
    return C.row(metric=metric, value=value, survey=sv, welfare_aggregate="consumption",
                 line_type="national", line_level="overall", line_name=_LINE, line_value=line,
                 line_unit="XOF per person per year", period=per, reference_period=ref,
                 frequency="ad_hoc", **kw)


def _trend(pages: list[str]) -> list[dict]:
    out = []
    t10 = next((t for t in pages if "Tableau 10 : Evolution des indices" in t), "")
    # "oct. 1994-janv. 1995 41 099 FCFA 44, 5 13,9 6,0": a split "44, 5".
    for per, pat in (("1994", r"1995\s+41 099 FCFA\s+(.*)"), ("1998", r"mai-août 1998\s+72 690 FCFA\s+(.*)")):
        m = re.search(pat, t10)
        nums = C.numbers_in(re.sub(r"(\d+), (\d)\b", r"\1,\2", m.group(1)), decimal=",") if m else []
        if len(nums) != 3:
            raise ValueError(f"Tableau 10 {per}: expected P0 P1 P2, got {nums}")
        out += [_row(per, mt, v) for mt, v in zip(("headcount", "gap", "severity"), nums)]
    t11 = next((t for t in pages if "Tableau 11 : Evolution des indices" in t), "")
    for lab, loc in (("Rural", "rural"), ("Urbain", "urban")):
        m = re.search(rf"^{lab}\s+(.*)$", t11, re.M)
        nums = C.numbers_in(m.group(1), decimal=",") if m else []
        if len(nums) != 15:
            raise ValueError(f"Tableau 11 {lab}: expected 15 numbers, got {nums}")
        for k, metric in enumerate(("headcount", "poor_share", "gap", "gap_contribution", "severity")):
            for j, per in enumerate(("1994", "1998")):       # 2003 comes from Tableau 4
                out.append(_row(per, metric, nums[3 * k + j], topic="locality", characteristic=lab,
                                locality=loc, locality_label=lab))
    return out


def parse(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)
    rows: list[dict] = []
    for tbl in LAYOUT["tables"]:
        got, _ = T._parse_table(pages, LAYOUT, tbl, "2003", "avril-juillet 2003")
        rows.extend(got)
    rows += _trend(pages["full"])
    return pd.DataFrame.from_records(rows)


LAYOUT_EICVM = {
    "survey": "EICVM 2009-2010 (résultats provisoires)", "welfare_aggregate": "consumption",
    "unit_of_analysis": "household", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil global de pauvreté (EICVM)", "line_value": 108454,
    "line_unit": "XOF per person per year", "period": "2009", "reference_period": "2009-2010",
    "tables": [
        {"page_contains": ["tableau 1 : incidence de la pauvreté selon le milieu"],
         "start": r"^Tableau 1 :", "end": r"^Source", "exact_numbers": True,
         "columns": [{"metric": "headcount"}, {"metric": "headcount_ci_low"},
                     {"metric": "headcount_ci_high"}],
         "rows": [{"match": r"^URBAIN(?=\s)", "topic": "locality", "locality": "urban",
                   "locality_label": "Urbain", "characteristic": "Urbain"},
                  {"match": r"^RURAL(?=\s)", "topic": "locality", "locality": "rural",
                   "locality_label": "Rural", "characteristic": "Rural"}]},
    ],
}


def parse_eicvm(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)
    got, _ = T._parse_table(pages, LAYOUT_EICVM, LAYOUT_EICVM["tables"][0], "2009", "2009-2010")
    if len(got) != 6:
        raise ValueError(f"EICVM Tableau 1: expected 6 cells, got {len(got)}")
    return pd.DataFrame.from_records(got)
