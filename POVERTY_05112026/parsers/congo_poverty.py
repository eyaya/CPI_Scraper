"""Republic of Congo -- monetary-poverty layout (CNSEE, Profil de pauvreté au
Congo en 2005, ECOM 2005).

ECOM collected June-August 2005. ONE national line: the LOWER line ("seuil de
pauvreté inférieur", food line + minimal non-food allowance, cost of basic
needs at 2 450 Kcal) = 306 400 F CFA per adult equivalent per year. Welfare =
consumption expenditure per adult equivalent (FAO scale, Tableau 2).

UNIT OF ANALYSIS MATTERS HERE: Tableau 2.2.1 prints every index TWICE, over
HOUSEHOLDS ("situation par rapport aux ménages", P0 = 42,3%) and over PEOPLE
("par rapport à la population totale", P0 = 50,1%). Both kept, told apart by
`unit_of_analysis`. Tableaux 2.2.2 and 2.2.3 are household-level: their
national male/female-head figures (41,5 / 45,2-45,3) match 2.2.1's household
column, not the person one.

Collected:
  2.2.1  5 strata + Ensemble: P0 P1 P2 and their contributions, households
         and persons (the strata are survey strata: Brazzaville and
         Pointe-Noire are cities, "Semi urbain" is its own stratum).
  2.2.2  P0 P1 P2 by stratum x sex of the household head (households). The
         Ensemble columns are SKIPPED: 2.2.3 prints the same national figures
         and the two disagree by 0,1 for female heads (45,2 vs 45,3) -- one
         merge key, so only 2.2.3's is kept.
  2.2.3  P0 P1 P2 + contributions (households) by sex, education of the head,
         household type, activity status, institutional sector, aggregated and
         detailed branches. Activity/sector/branch rows carry their block's
         heading in `characteristic` ("Branches détaillées: Services"),
         because "Services" is printed in two blocks with DIFFERENT values
         (30,8 aggregated vs 30,3 detailed). The detailed block's
         "Agriculture" row repeats the aggregated one exactly and is skipped.
Not collected: 2.2.4 (poor-household COUNTS and mean expenditure) -- every
cell is a space-grouped number printed against the next ("91 310 180 267 112
374 ..."), so cell boundaries cannot be recovered from the text layer;
2.3.1 (income shares by quartile -- distribution, not poverty); 2.3.2 (Gini
and GE indices -- the inequality indicator's territory).

CROSS-CHECK (verbatim): households P0 42,3 / P1 15,3 / P2 7,6; persons 50,1 /
18,9 / 9,6; Pointe-Noire households 23,5, persons 32,2; semi urbain 55,1;
female-headed 45,3; head with no education 53,7, supérieur 23,3. Identity:
2.2.1 household P0 contributions of the five strata sum to 99,9-100.
"""
from __future__ import annotations

from ._vocab import label_rows
from .poverty_tables import make_parser

_FGT = ("headcount", "gap", "severity")
_CTR = ("poor_share", "gap_contribution", "severity_contribution")


def _cols(unit):
    return [{"metric": m, "unit_of_analysis": unit} for m in _FGT + _CTR]


_STRATA = [  # (printed label in 2.2.1, attrs)
    ("Brazzaville", {"locality": "other", "locality_label": "Brazzaville"}),
    ("Pointe-Noire", {"locality": "other", "locality_label": "Pointe-Noire"}),
    ("Autres communes", {"locality": "other", "locality_label": "Autres communes"}),
    ("Semi urbain", {"locality": "other", "locality_label": "Semi urbain"}),
    ("Milieu rural", {"locality": "rural", "locality_label": "Milieu rural"}),
]

# Tableau 2.2.2: columns are stratum x sex of head; the Ensemble pair skipped.
_T222_COLS = []
for _lab, _attrs in _STRATA:
    for _sx, _char in (("male", "Homme"), ("female", "Femme")):
        _T222_COLS.append({"topic": "sex_of_head", "characteristic": _char, "sex": _sx,
                           "unit_of_analysis": "household", **_attrs})
_T222_COLS += [{"skip": True}, {"skip": True}]

_T223_COLS = [{"metric": m, "unit_of_analysis": "household"} for m in _FGT + _CTR]
_T223 = ["tableau 2.2.3", "indices de pauvreté suivant certaines caractéristiques des ménages"]


def _blk(start, end, topic, labels, prefix=None, **extra):
    rows = label_rows(topic, labels, **extra)
    if prefix:
        for r in rows:
            r["characteristic"] = f"{prefix}: {r['characteristic']}"
    return {"page_contains": _T223, "start": start, "end": end,
            "exact_numbers": True, "columns": _T223_COLS, "rows": rows}


LAYOUT = {
    "survey": "ECOM 2005", "welfare_aggregate": "consumption",
    "unit_of_analysis": "household", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté inférieur 2005",
    "line_value": 306400, "line_unit": "XAF per adult equivalent per year",
    "period": "2005", "reference_period": "juin-août 2005",
    "tables": [
        {   # Tableau 2.2.1 -- strata, households then persons
            "page_contains": ["tableau 2.2.1", "situation par rapport aux ménages"],
            "exact_numbers": True,
            "columns": _cols("household") + _cols("person"),
            "rows": [{"match": rf"^{lab}(?=\s+\d)", "topic": "locality", **a}
                     for lab, a in _STRATA]
                    + [{"match": r"^Ensemble(?=\s+\d)"}],
        },
        {   # Tableau 2.2.2 -- metrics in rows, stratum x sex in columns
            "page_contains": ["tableau 2.2.2", "suivant le sexe du chef de ménage"],
            "start": r"^Tableau 2\.2\.2", "end": r"^Source",
            "exact_numbers": True,
            "columns": _T222_COLS,
            "rows": [{"match": r"^P0(?=\s+\d)", "metric": "headcount"},
                     {"match": r"^P1(?=\s+\d)", "metric": "gap"},
                     {"match": r"^P2(?=\s+\d)", "metric": "severity"}],
        },
        # Tableau 2.2.3 -- characteristics of the household / its head
        _blk(r"^1\. Sexe", r"^2\. Niveau", "sex_of_head", []) | {"rows": [
            {"match": r"^Homme(?=\s+\d)", "topic": "sex_of_head",
             "characteristic": "Homme", "sex": "male"},
            {"match": r"^Femme(?=\s+\d)", "topic": "sex_of_head",
             "characteristic": "Femme", "sex": "female"}]},
        _blk(r"^2\. Niveau d", r"^3\. Typologie", "education_of_head",
             ["Aucun", "Primaire", "Secondaire", "Supérieur"]),
        _blk(r"^3\. Typologie", r"^4\. Situation", "household_type",
             ["Unipersonnel", "Couples sans enfant", "Couples avec enfants",
              "Monoparental nucléaire", "Monoparental élargi", "Famille élargie"]),
        _blk(r"^4\. Situation", r"^5\. Secteur", "employment_of_head",
             ["Actifs occupés", "Chômeurs", "Inactifs"], prefix="Situation dans l’activité"),
        _blk(r"^5\. Secteur", r"^6\. Branches", "employment_of_head",
             ["Secteur public", "Secteur privé", "Secteur informel"],
             prefix="Secteur institutionnel"),
        _blk(r"^6\. Branches agrégées", r"^7\. Branches", "employment_of_head",
             ["Agriculture", "BTP, Transformation, Mines", "Commerce", "Services"],
             prefix="Branches agrégées"),
        _blk(r"^7\. Branches détaillées", r"^Ensemble", "employment_of_head",
             ["Mines/carrière", "Transformation/production", "BTP", "Transport",
              "Commerce/vente", "Services", "Education/santé", "Administration",
              "Autres"], prefix="Branches détaillées"),
    ],
}

parse = make_parser(LAYOUT)
