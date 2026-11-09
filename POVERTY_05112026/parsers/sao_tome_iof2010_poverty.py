"""São Tomé and Príncipe -- IOF 2010 poverty profile ("Profil de la pauvreté à
Sao Tomé et Principe", Enquête Budget Consommation 2010, PNUD/INE), in French.

INE's own file (ine.st Phoca upload). The OFFICIAL 2010 measure is the
ABSOLUTE cost-of-basic-needs line, 10 975 730 Dobras (old STD) per person per
year: P0 66,2 / P1 24,8 / P2 12,0 (Tableau 4). This is NOT the "IOF 2010
(S2S imputation, IOF 2017 prices and line)" series the IOF 2017 report
republishes (68,4) -- that one is a re-estimate on the 2017 method and stays
under its own survey label.

The report ALSO prints the RELATIVE measure on which the 2000 profile was
based (2/3 of mean harmonised expenditure per head): 2000 line 2 638 618 STD,
2010 line 8 680 490 STD (Tableau 3). Filed as line_type relative; they are not
comparable with the absolute line and the report says the absolute one is to
be kept for the future.

Collected:
  3  relative line, 2000 and 2010: P0/P1/P2 for the 7 districts + Ensemble
     (transposed: metrics in rows, districts in columns). Its third block
     (absolute 2010) repeats Tableau 4 and is not read twice.
  4  absolute line: P0/P1/P2 and each district's contribution, over
     HOUSEHOLDS and over PERSONS.
  5  P0/P1/P2 by sex of the person within each district (Ensemble columns
     and the national row repeat Tableaux 4/6).
  6  by sex (with contributions), household type and household-welfare
     quintile, persons.
NOT collected: Tableau 6 "Situation dans l'activité" and "Groupes
socioéconomiques" -- whose status (person or head) is not stated, and the
activity block prints its columns interleaved (P0, C0, P1, C1 ...); also
Tableau 2 (district lines; no metric for a line itself).

CROSS-CHECK (verbatim): absolute 66,2 / 24,8 / 12,0 (households 54,4 / 18,6 /
8,6); Caué 84,5; Mé-Zochi 56,6; relative 2000 53,8 / 19,2 / 9,3, 2010 49,6 /
15,9 / 6,9; women 71,3, men 63,4. District contributions sum to 100,1 (P0,
persons).
"""
from __future__ import annotations

from ._vocab import label_rows
from .poverty_tables import make_parser

_D = ["Agua-Grande", "Mé-Zochi", "Cantagalo", "Caué", "Lemba", "Lobata", "Principe"]
_DCOLS = [{"geography": d} for d in _D] + [{"geography": "Total country"}]

_REL = lambda year, value: {  # noqa: E731
    "line_type": "relative", "line_level": "other",
    "line_name": "Seuil relatif (2/3 de la dépense moyenne par tête harmonisée)",
    "line_value": value, "line_unit": "STD per person per year",
    "period": year, "reference_period": year,
    "survey": "IOF 2010" if year == "2010" else "Enquête sur les conditions de vie 2000 (as republished in IOF 2010)"}


def _rel_block(start, end, year, value):
    return {"page_contains": ["tableau 3: bilan synoptique des estimations de la pauvreté"],
            "start": start, "end": end, "exact_numbers": True, "columns": _DCOLS,
            "defaults": _REL(year, value),
            "rows": [{"match": r"^Ratio de pauvreté \(P0\)", "metric": "headcount"},
                     {"match": r"^Gap de pauvreté \(P1\)", "metric": "gap"},
                     {"match": r"^Sévérité de la pauvreté \(P2\)", "metric": "severity"}]}


def _dist_rows():
    return [{"match": r"^" + d + r"(?=\s+\d)", "geography": d} for d in _D]


_T4 = [{"metric": m, "unit_of_analysis": u} for u in ("household", "person") for m in
       ("headcount", "gap", "severity", "poor_share", "gap_contribution", "severity_contribution")]
_SEX = lambda m: [{"metric": m, "topic": "sex", "characteristic": "Homme", "sex": "male"},  # noqa: E731
                  {"metric": m, "topic": "sex", "characteristic": "Femme", "sex": "female"},
                  {"skip": True}]
_T6 = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"},
       {"metric": "poor_share"}, {"metric": "gap_contribution"}, {"metric": "severity_contribution"}]


def _t6(start, end, rows):
    return {"page_contains": ["tableau 6 : profil de pauvreté de la population suivant"],
            "start": start, "end": end, "exact_numbers": True, "columns": _T6, "rows": rows}


LAYOUT = {
    "survey": "IOF 2010", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ",", "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté absolu IOF 2010 (coût des besoins essentiels)",
    "line_value": 10975730, "line_unit": "STD per person per year",
    "period": "2010", "reference_period": "2010",
    "tables": [
        _rel_block(r"^Situation en 2000", r"^Situation en 2010 sur la base de l’analyse de la pauvreté relative",
                   "2000", 2638618),
        _rel_block(r"^Situation en 2010 sur la base de l’analyse de la pauvreté relative",
                   r"^Situation en 2010 sur la base de l’analyse de la pauvreté absolue", "2010", 8680490),
        {"page_contains": ["tableau 4 : indices de la pauvreté absolue suivant"], "start": r"^P0 P1 P2",
         "end": r"^Source", "exact_numbers": True, "columns": _T4,
         "rows": _dist_rows() + [{"match": r"^Ensemble(?=\s)"}]},
        {"page_contains": ["tableau 5 : indices de pauvreté par sexe suivant les strates"],
         "start": r"^Homme Femme Ensemble", "end": r"^Ensemble", "exact_numbers": True,
         "columns": _SEX("headcount") + _SEX("gap") + _SEX("severity"), "rows": _dist_rows()},
        _t6(r"^1\. Sexe", r"^2\. Typologie", [
            {"match": r"^Homme(?=\s)", "topic": "sex", "characteristic": "Homme", "sex": "male"},
            {"match": r"^Femme(?=\s)", "topic": "sex", "characteristic": "Femme", "sex": "female"}]),
        _t6(r"^2\. Typologie", r"^3\. Situation", label_rows("household_type", [
            "Unipersonnel", "Couples sans enfant", "Couples avec enfants", "Monoparental nucléaire",
            "Monoparental élargi", "Famille élargie"])),
        _t6(r"^5\. Quintile", r"^Ensemble", [
            {"match": r"^" + q + r"(?=\s+\d)", "topic": "quintile", "characteristic": c,
             "unit_of_analysis": "person"}
            for q, c in (("20% les plus pauvres", "20% les plus pauvres"), ("2ème quintile", "2ème quintile"),
                         ("3ème quintile", "3ème quintile"), ("4ème quintile", "4ème quintile"),
                         ("20% les plus riches", "20% les plus riches"))]),
    ],
}

parse = make_parser(LAYOUT)
