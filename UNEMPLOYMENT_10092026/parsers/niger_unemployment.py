"""Niger — unemployment / labour-force layout and parser.

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
# NIGER -- INS, Enquête Régionale Intégrée sur l'Emploi et le Secteur
# Informel (ERI-ESI) 2017. Front-matter "Principaux indicateurs de l'emploi".
# Columns: Niamey urbain | Autres urbains | Ensemble urbain | Rural | Niger.
#
# STRUCTURE: most indicators are a BLOCK -- a header line carrying the
# indicator name and NO numbers, followed by indented `Ensemble` / `Homme` /
# `Femme` sub-rows that carry the five values. A few indicators are single
# lines with their own five numbers (the two age-split unemployment rows).
# That is exactly what `blocks` is for: the block header sets the topic, the
# sub-rows set the sex.
#
# The recap table also carries migration, schooling, income, wage and hours
# rows. Only the labour-market indicators in the topic vocabulary are taken;
# income (FCFA) and unemployment duration (years) have no topic and are left.
#
# FR conventions: comma decimals, space thousands.
#
# CROSS-CHECK (Niger column): chômage BIT ensemble 7,9 (H 8,0 / F 7,7);
# 15-34 ans 12,2; 35+ 5,0; taux combiné sous-emploi+chômage 29,8;
# sous-utilisation 60,2 (H 51,9 / F 72,6); 15-34 ans 69,2.
# =========================================================================
_NE_COLS = [
    {"geography": "Niamey", "locality": "urban", "locality_label": "Niamey urbain"},
    {"locality": "other", "locality_label": "Autres urbains"},
    {"locality": "urban", "locality_label": "Ensemble urbain"},
    {"locality": "rural", "locality_label": "Rural"},
    {"locality": "all", "locality_label": "Niger"},
]
_NE_SEX_ROWS = [
    {"match": r"^Ensemble\b", "sex": "total"},
    {"match": r"^Homme\b", "sex": "male"},
    {"match": r"^Femme\b", "sex": "female"},
]

LAYOUTS["niger"] = {
    "survey": "ERI-ESI -- Enquête Régionale Intégrée sur l'Emploi et le "
              "Secteur Informel",
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "decimal": ",",
    "period": "2017",
    "reference_period": "2017",
    "tables": [{
        "page_contains": ["principaux indicateurs de l'emploi"],
        "take": "trailing",
        "columns": _NE_COLS,
        "first_match_only": False,     # the sex sub-rows repeat under each block
        # The recap table also lists indicators this schema has no topic for --
        # average unemployment DURATION in years, income, hours. They are not
        # declared as blocks, so without this the block above them stayed open
        # and their rows were read as its values: 6.65 YEARS of average
        # unemployment duration went out as a 6.65% underutilisation rate.
        "block_ends_on_heading": True,
        "blocks": [
            {"id": "bit", "match": r"^Taux de chômage BIT\s*$",
             "topic": "unemployment_rate", "definition": "strict",
             "label": "Taux de chômage BIT"},
            {"id": "su2", "match": r"^Taux combiné du sous-emploi lié au temps",
             "topic": "underemployment_rate", "definition": "broad",
             "label": "Taux combiné du sous-emploi lié au temps de travail "
                      "et du chômage"},
            {"id": "su4", "match": r"^Taux de sous-utilisation de la main",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Taux de sous-utilisation de la main d'oeuvre"},
            {"id": "informel", "match": r"Pourcentage d.emplois formels dans le secteur",
             "topic": "informal_employment_share",
             "label": "Pourcentage d'emplois formels dans le secteur non agricole"},
        ],
        "rows": [
            # Block sub-rows. `block` scopes each to its own indicator so the
            # bare label "Ensemble" cannot leak across blocks.
            *[dict(r, block=b) for b in ("bit", "su2", "su4", "informel")
              for r in _NE_SEX_ROWS],
            # THE AGE ROWS ARE THEIR OWN LINES, not a suffix on the heading.
            # These patterns expected "Taux de chomage BIT (%) 15 - 34 ans ..."
            # on one line; the recap prints the heading, then
            #     15 - 34 ans 13,6 12,4 12,8 12,0 12,2
            #     35 ans et plus 3,9 3,0 3,4 5,6 5,0
            # so none of them matched and both age splits were lost.
            #
            # Scoping them by block is what makes "15 - 34 ans" unambiguous --
            # the same two labels appear under the BIT heading and again under
            # sous-utilisation -- and it is also what CLOSES the second
            # sous-utilisation block: without a data row under it, the block
            # stayed open into "Duree moyenne de chomage (en annees)" and read
            # 6.65 YEARS as a 6.65% rate.
            {"match": r"^15\s*-\s*34 ans", "block": "bit",
             "topic": "youth_unemployment_rate", "definition": "strict",
             "age_group": "15-34", "drop_leading": 2,
             "label": "Taux de chômage BIT 15-34 ans"},
            {"match": r"^35 ans et plus", "block": "bit",
             "topic": "unemployment_rate", "definition": "strict",
             "age_group": "35+", "drop_leading": 1,
             "label": "Taux de chômage BIT 35 ans et plus"},
            {"match": r"^15\s*-\s*34 ans", "block": "su4",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "age_group": "15-34", "drop_leading": 2,
             "label": "Taux de sous-utilisation de la main d'oeuvre 15-34 ans"},
            {"match": r"^35 ans et plus", "block": "su4",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "age_group": "35+", "drop_leading": 1,
             "label": "Taux de sous-utilisation de la main d'oeuvre 35 ans et plus"},
        ],
    }],
}


LAYOUT = LAYOUTS['niger']
parse = make_parser(LAYOUT)
