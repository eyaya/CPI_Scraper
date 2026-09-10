"""Cameroon — unemployment / labour-force layout and parser.

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
# CAMEROON -- INS, Troisième Enquête sur l'Emploi et le Secteur Informel
# (EESI3), dépliant "Quelques indicateurs du marché du travail".
# Columns: Douala | Yaoundé | Urbain | Rural | Ensemble.
#
# Cameroon publishes indicators on the NEW (ICLS-19) framework for the 14+
# population -- data collected from 10+, indicators published on 14+ because
# 14 is the legal working age. The dépliant ALSO prints an old-framework table
# and explicitly forbids comparing the two ("ne sont pas à comparer"), so only
# the new-framework panel is captured here.
#
# FR conventions: comma decimals, space thousands. Two extraction hazards seen
# in this leaflet and handled by `to_number`/`drop_leading`: a lost leading
# zero (",4" for "0,4") and the "(SU1)" digit inside a row label.
#
# CROSS-CHECK (Ensemble): taux de main-d'oeuvre 54,2; chômage BIT (SU1) 6,1;
# SU2 23,0; SU3 10,0; SU4 26,3. Douala SU1 15,4; Yaoundé 11,7; rural 1,6.
# =========================================================================
LAYOUTS["cameroon"] = {
    # A DEPLIANT PRINTED IN TWO COLUMNS. Read whole-page, every line splices
    # the two together --
    #   Taux (en %) de chomage BIT (SU1) 15,4 11,7 9,4 1,6 6,1 Rural 93,3 96,7 94,9
    # -- and `take: trailing` then read the NEIGHBOURING table's numbers as
    # this one's, giving an urban unemployment rate of 93.3% (really an
    # informal-employment share). Cropping the page into its printed
    # columns is what makes the line mean what it looks like.
    "split_columns": 2,
    # This report's renderer wraps long row labels onto their own line, leaving
    # the numbers stranded on the next -- see `_rejoin_wrapped`.
    "join_wrapped_labels": True,
    "survey": "EESI3 -- Enquête sur l'Emploi et le Secteur Informel",
    "frequency": "ad_hoc",
    "working_age_base": "14+",
    "decimal": ",",
    "period": "2022",
    "reference_period": "2022",
    "tables": [{
        "page_contains": ["sous-utilisation de la main"],
        "take": "trailing",
        "columns": [
            {"geography": "Douala", "locality": "urban", "locality_label": "Douala"},
            {"geography": "Yaoundé", "locality": "urban", "locality_label": "Yaoundé"},
            {"locality": "urban", "locality_label": "Urbain"},
            {"locality": "rural", "locality_label": "Rural"},
            {"locality": "all", "locality_label": "Ensemble"},
        ],
        "rows": [
            {"match": r"Taux de main-d.{0,3}uvre \(en %\)",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Taux de main-d'oeuvre"},
            {"match": r"Taux de main-d.{0,3}uvre élargi",
             "topic": "labour_force_participation_rate", "definition": "broad",
             "label": "Taux de main-d'oeuvre élargi"},
            {"match": r"chômage BIT \(SU1\)", "topic": "unemployment_rate",
             "definition": "strict", "label": "Taux de chômage BIT (SU1)"},
            # THE SU2 AND SU3 LABELS WRAP, and unlike Rwanda's the numbers stay
            # with the label's TAIL rather than sitting on a line of their own:
            #     Taux combiné du sous-emploi lié au temps de
            #     travail et du chômage (SU2) 28,4 29,5 26,7 17,7 23,0
            # so a pattern spanning the line break matches neither half. Each
            # is anchored on the fragment that actually carries the data.
            {"match": r"travail et du chômage \(SU2\)",
             "topic": "underemployment_rate", "definition": "broad",
             "label": "Taux combiné du sous-emploi lié au temps de travail "
                      "et du chômage (SU2)"},
            {"match": r"potentielle \(SU3\)",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Taux combiné du chômage et de la main-d'oeuvre "
                      "potentielle (SU3)"},
            {"match": r"main-d.{0,3}uvre \(SU4\)",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Mesure composite de la sous-utilisation de la "
                      "main-d'oeuvre (SU4)"},
        ],
    }],
}


LAYOUT = LAYOUTS['cameroon']
parse = make_parser(LAYOUT)
