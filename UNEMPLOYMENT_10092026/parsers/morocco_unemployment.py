"""Morocco — unemployment / labour-force layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `pdf_key_indicators.make_parser`; the comments beside
it record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

import re  # noqa: F401  -- some layouts build their rows with it

from ._vocab import *  # noqa: F401,F403
from .pdf_key_indicators import make_parser

LAYOUTS: dict[str, dict] = {}

# =========================================================================
# MOROCCO -- HCP, "Activité, emploi et chômage, résultats annuels".
# Tableau 2 (activité) and Tableau 3 (chômage), both with the header
# `Indicateurs | Masculin | Féminin | Urbain | Rural | National`.
#
# Two structural hazards, both handled:
#  * The "Taux de féminisation" and "selon le sexe" sub-rows print only THREE
#    values (Masculin and Féminin cells are empty); the parser skips a row with
#    fewer numbers than columns rather than shifting them left.
#  * Tableau 2 breaks across a page and its caption is REPEATED with "(suite)".
#
# HCP replaced the ENE with the EMO2026 survey from Q1 2026 and the two series
# are NOT comparable (annual 2025 = 13,0%; Q2 2026 = 9,5%). This layout reads
# the ANNUAL ENE report; the retropolated 2017-2025 EMO bridge workbook is the
# Tier-2 upgrade noted in the descriptor.
#
# FR conventions: comma decimals; stocks are `en milliers`.
#
# CROSS-CHECK (2025, National): population active 12 488 mille;
# taux d'activité 43,5; population active en chômage 1 621 mille;
# taux de chômage 13,0 (Masculin 10,8 / Féminin 20,5 / Urbain 16,4 / Rural 6,6).
# =========================================================================
_MA_COLS = [
    {"sex": "male", "locality": "all", "locality_label": "Masculin"},
    {"sex": "female", "locality": "all", "locality_label": "Féminin"},
    {"sex": "total", "locality": "urban", "locality_label": "Urbain"},
    {"sex": "total", "locality": "rural", "locality_label": "Rural"},
    {"sex": "total", "locality": "all", "locality_label": "National"},
]

LAYOUTS["morocco"] = {
    # HCP's annual report wraps long row labels around their own numbers, and
    # does it TWO different ways on the same page -- see `_rejoin_wrapped`.
    "join_wrapped_labels": True,
    "survey": "Activité, emploi et chômage (résultats annuels)",
    "frequency": "annual",
    "working_age_base": "15+",
    "decimal": ",",
    "period_patterns": [
        r"ACTIVIT[ÉE], EMPLOI ET CHOMAGE\s+Ann[ée]e\s+(20\d{2})",
        r"\bAnn[ée]e\s+(20\d{2})\s+R[ée]sultats annuels\b",
    ],
    # TWO TABLES, AND THE OLD ANCHOR ONLY EVER REACHED ONE OF THEM.
    # `page_contains: ["les indicateurs de l"]` matches Tableau 2 ("Les
    # indicateurs de l'activité") but NOT Tableau 3 ("Les indicateurs DU
    # chômage"), so the unemployment table -- the point of this indicator --
    # was never selected and the layout produced the labour-force count alone.
    # Both captions also appear in the SOMMAIRE, which is excluded by name.
    "tables": [
        {
            "page_contains": ["indicateurs de l’activité selon le milieu"],
            "page_excludes": ["sommaire"],
            "take": "trailing",
            "columns": _MA_COLS,
            "rows": [
                # Renders as one line once the wrapped tail is folded back:
                #   Population active âgée de 15 ans et plus (en milliers) 9717 ...
                {"match": r"^Population active âgée de 15 ans et plus",
                 "topic": "labour_force", "unit": "thousand_persons",
                 "measure": "count",
                 "label": "Population active âgée de 15 ans et plus (en milliers)"},
                # This one wraps the OTHER way -- the label's middle carries the
                # numbers and neither half is foldable:
                #   Taux d’activité de la
                #   population âgée de 15 68,5 19,0 42,2 46,1 43,5
                #   ans et plus (en %)
                # so the pattern is anchored on the fragment that holds the data.
                {"match": r"^population âgée de 15\s+\d",
                 "topic": "labour_force_participation_rate",
                 "definition": "strict",
                 "label": "Taux d'activité de la population âgée de 15 ans et plus"},
            ],
        },
        {
            "page_contains": ["indicateurs du chômage selon le milieu"],
            "page_excludes": ["sommaire", "diplôme"],
            "take": "trailing",
            "columns": _MA_COLS,
            # THE AGE BREAKDOWN IS DELIBERATELY NOT READ. The label
            # "15-24 ans" appears under at least four headings in this report
            # -- activity rate by age, unemployment rate by age, structure of
            # the active population by age, and the same again in the "(suite)"
            # continuation pages -- and `blocks` could not be made to scope it
            # reliably, because the heading itself wraps ("Taux de chômage
            # selon / l'âge (en %)") and the continuation pages repeat the
            # column header without the heading.
            #
            # Read unscoped it produced youth unemployment of 10.6% -- which is
            # the 15-24 SHARE OF THE ACTIVE POPULATION from Tableau 2, not a
            # rate at all. The published figure is 37.2%. A plausible number in
            # the right column and the wrong meaning is the worst outcome here,
            # so the rows are left out until the scoping is solved. See
            # PENDING.md.
            "rows": [
                {"match": r"^Population active en chômage",
                 "exclude": r"féminisation", "topic": "unemployed",
                 "unit": "thousand_persons", "measure": "count",
                 "label": "Population active en chômage (en milliers)"},
                {"match": r"^Taux de chômage \(en %\)",
                 "topic": "unemployment_rate", "definition": "strict",
                 "label": "Taux de chômage"},
            ],
        },
    ],
}


LAYOUT = LAYOUTS['morocco']
parse = make_parser(LAYOUT)
