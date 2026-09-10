"""Burkina Faso — unemployment / labour-force layout and parser.

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
# BURKINA FASO -- INSD, "Note synthétique -- Enquête nationale sur l'emploi et
# le secteur informel (ENB-ESI) 2023".
#
# WHY THIS DOCUMENT AND NOT THE ENSE BULLETIN: the recurring semestrial ENSE
# bulletin has 26 `Graphique` captions and ZERO `Tableau` -- its numbers exist
# only as chart data labels, which lose trailing zeros and carry no category
# names. Verified twice, including against INSD's own NADA related-materials
# listing, which attaches no Excel or CSV to any ENSE round. The ENB-ESI note
# is the one INSD labour publication that actually contains numbered tables.
#
# Tableau 2 -- rows National / Urbain / Rural / 13 régions; columns
# Proportion main d'œuvre | Taux d'emploi | Taux de chômage (SU1) | SU2 | SU3 | SU4.
#
# WORKING-AGE BASE IS 16+, not 15+ -- unusual for the region and shared with
# the ENSE bulletins.
#
# CROSS-CHECK (National row): proportion main d'oeuvre 49,3; taux d'emploi
# 46,7; taux de chômage 5,3. Labour force 5 532 715. Reference Jan-Apr 2023.
# =========================================================================
LAYOUTS["burkina_faso"] = {
    "survey": "ENB-ESI -- Enquête nationale sur l'emploi et le secteur informel",
    "frequency": "ad_hoc",
    "working_age_base": "16+",
    "decimal": ",",
    "period": "2023",
    "reference_period": "January-April 2023",
    "tables": [{
        # ANCHORED ON THE CAPTION, because "Taux de chômage" never appears
        # contiguously anywhere on this page: the header is stacked, and the
        # phrase is split across two printed lines --
        #     Proportion de   Taux    Taux de    Taux combiné du ...
        #     la main         d'emploi chômage   sous-emploi ...
        # -- so the old anchor selected other pages and this table was never
        # reached.
        "page_contains": ["principaux indicateurs de la main"],
        "take": "trailing",
        "columns": [
            {"topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Proportion de la main d'oeuvre"},
            {"topic": "employment_to_population_ratio", "label": "Taux d'emploi"},
            {"topic": "unemployment_rate", "definition": "strict",
             "label": "Taux de chômage (SU1)"},
            {"topic": "underemployment_rate", "definition": "broad",
             "label": "Taux combiné du sous-emploi lié au temps de travail "
                      "et du chômage (SU2)"},
            {"topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Taux combiné du chômage et de la main d'oeuvre "
                      "potentielle (SU3)"},
            {"topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Mesure composite de la sous-utilisation de la main "
                      "d'oeuvre (SU4)"},
        ],
        # Region names are as PRINTED, which is not always the official
        # spelling: the report writes "Boucle de Mouhoun" (not "du"),
        # "Hauts Bassins" unhyphenated, and "Plateau central" lower-case.
        # `\s+(?=[\d])` ends each label at its first value -- without it
        # "Centre" also matches "Centre-Est" and the four other Centre-*
        # regions, and the first one seen wins for all five.
        "rows": [
            {"match": r"^National\s+(?=[\d])", "geography": "Total country"},
            {"match": r"^Urbain\s+(?=[\d])", "locality": "urban",
             "locality_label": "Urbain"},
            {"match": r"^Rural\s+(?=[\d])", "locality": "rural",
             "locality_label": "Rural"},
            {"match": r"^Boucle de Mouhoun\s+(?=[\d])",
             "geography": "Boucle du Mouhoun"},
            {"match": r"^Cascades\s+(?=[\d])", "geography": "Cascades"},
            {"match": r"^Centre\s+(?=[\d])", "geography": "Centre"},
            {"match": r"^Centre-Est\s+(?=[\d])", "geography": "Centre-Est"},
            {"match": r"^Centre-Nord\s+(?=[\d])", "geography": "Centre-Nord"},
            {"match": r"^Centre-Ouest\s+(?=[\d])", "geography": "Centre-Ouest"},
            {"match": r"^Centre-Sud\s+(?=[\d])", "geography": "Centre-Sud"},
            {"match": r"^Est\s+(?=[\d])", "geography": "Est"},
            {"match": r"^Hauts[- ]Bassins\s+(?=[\d])",
             "geography": "Hauts-Bassins"},
            {"match": r"^Nord\s+(?=[\d])", "geography": "Nord"},
            {"match": r"^Plateau[- ][Cc]entral\s+(?=[\d])",
             "geography": "Plateau-Central"},
            {"match": r"^Sahel\s+(?=[\d])", "geography": "Sahel"},
            {"match": r"^Sud-Ouest\s+(?=[\d])", "geography": "Sud-Ouest"},
        ],
    }],
}


LAYOUT = LAYOUTS['burkina_faso']
parse = make_parser(LAYOUT)
