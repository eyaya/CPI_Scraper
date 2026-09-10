"""Benin — unemployment / labour-force layout and parser.

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
# BENIN -- INStaD, ERI-ESI 2018, Tableau 1.8 "Principales caractéristiques de
# la sous-utilisation de la main d'œuvre".
#
# TRANSPOSED, like Sierra Leone: the ROWS are sociodemographic characteristics
# and the COLUMNS are indicators, so the topics live in the column specs.
#
# The two `Effectif` columns are INTERLEAVED at positions 3 and 6, not at the
# end -- confirmed twice against the printed table. They close two blocks with
# DIFFERENT denominators (3 833 655 for the unemployment/underemployment block,
# 4 143 534 for the underutilisation block), which is why there are two of them.
# The first is the labour force, the second the extended labour force.
#
# Printed typos preserved in the regexes: "sousutilisation" (no hyphen) and
# "main œuvre" (missing "de la").
#
# NOTE what this report does NOT contain: there is no participation rate and no
# employment-to-population ratio anywhere in it -- verified against the full
# 40-table Liste des tableaux. Do not go looking for them.
#
# CROSS-CHECK (Bénin row): 2,3 | 10,8 | 3 833 655 | 9,7 | 17,6 | 4 143 534.
# Cotonou and Littoral are identical by construction (Cotonou IS the Littoral
# département) -- a free consistency check on any parse.
# =========================================================================
LAYOUTS["benin"] = {
    "survey": "ERI-ESI -- Enquête Régionale Intégrée sur l'Emploi et le "
              "Secteur Informel",
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "decimal": ",",
    "period": "2018",
    "reference_period": "2018",
    "tables": [{
        "page_contains": ["sous-utilisation de la main"],
        "take": "trailing",
        "columns": [
            {"topic": "unemployment_rate", "definition": "strict",
             "label": "Taux de chômage BIT"},
            {"topic": "underemployment_rate", "definition": "broad",
             "label": "Taux combiné du sous-emploi lié au temps de travail "
                      "et du chômage"},
            {"topic": "labour_force", "label": "Effectif (main-d'oeuvre)"},
            {"topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Taux combiné du chômage et de la main d'oeuvre potentielle"},
            {"topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Taux de sous-utilisation de la main d'oeuvre"},
            {"topic": "potential_labour_force",
             "label": "Effectif (main-d'oeuvre élargie)"},
        ],
        "rows": [
            {"match": r"^Bénin\b", "geography": "Total country"},
            {"match": r"^Homme\b", "sex": "male"},
            {"match": r"^Femme\b", "sex": "female"},
            {"match": r"^15\s*-\s*24 ans", "age_group": "15-24", "drop_leading": 2},
            {"match": r"^25\s*-\s*34 ans", "age_group": "25-34", "drop_leading": 2},
            {"match": r"^15\s*-\s*34 ans", "age_group": "15-34", "drop_leading": 2},
            {"match": r"^35\s*-\s*44 ans", "age_group": "35-44", "drop_leading": 2},
            {"match": r"^45\s*-\s*54 ans", "age_group": "45-54", "drop_leading": 2},
            {"match": r"^55\s*-\s*64 ans", "age_group": "55-64", "drop_leading": 2},
            {"match": r"^65 ans et plus", "age_group": "65+", "drop_leading": 1},
            {"match": r"^Cotonou\b", "locality": "urban", "locality_label": "Cotonou",
             "geography": "Cotonou"},
            {"match": r"^Autres urbains", "locality": "other",
             "locality_label": "Autres urbains"},
            {"match": r"^Ens\. urbain|^Ensemble urbain", "locality": "urban",
             "locality_label": "Ensemble urbain"},
            {"match": r"^Rural\b", "locality": "rural", "locality_label": "Rural"},
            {"match": r"^Aucun\b", "education": "Aucun"},
            {"match": r"^Primaire\b", "education": "Primaire"},
            {"match": r"^Secondaire\b", "education": "Secondaire"},
            {"match": r"^Supérieur\b", "education": "Supérieur"},
        ],
    }],
}


LAYOUT = LAYOUTS['benin']
parse = make_parser(LAYOUT)
