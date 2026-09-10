"""Guinea Bissau — unemployment / labour-force layout and parser.

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
# GUINEA-BISSAU -- INE, ERI-ESI / IRIESI 2017-2018, "Principais indicadores de
# emprego". Columns: SAB | Outros urbanos | Total urbano | Rural | Guiné-Bissau.
#
# SAB = Setor Autónomo de Bissau (the capital district). Note there is a
# `Total urbano` AGGREGATE column sitting between the two urban strata and
# Rural -- five columns, not four.
#
# Like Niger, this is a BLOCK table: an indicator header line with no numbers,
# then Total / Homem / Mulher sub-rows (and for two indicators, age sub-rows).
#
# The document is Portuguese with French-language residue in some captions and
# heavy typos ("RALATÓRIO SÍNTESE", "Taux de pluriativitdade", "maão-de-obra").
# Regexes are kept loose accordingly.
#
# The headline "Taxa de subutilização da mão-de-obra" is SU4 -- the general
# report's Tabela 24 names it explicitly as the composite measure.
#
# CROSS-CHECK (Guiné-Bissau column, Total rows): desemprego OIT 7,1;
# 15-34 anos 10,5; subemprego combinado 13,1; subutilização 23,7;
# 15-34 anos 26,2; emprego formal não agrícola 7,8; emprego vulnerável 41,9.
# SAB desemprego 13,0 against rural 5,2 -- the urban/rural gap is the check.
# =========================================================================
_GW_COLS = [
    {"geography": "Bissau", "locality": "urban", "locality_label": "SAB"},
    {"locality": "other", "locality_label": "Outros urbanos"},
    {"locality": "urban", "locality_label": "Total urbano"},
    {"locality": "rural", "locality_label": "Rural"},
    {"locality": "all", "locality_label": "Guiné-Bissau"},
]
_GW_SEX_ROWS = [
    {"match": r"^Total\b", "sex": "total"},
    {"match": r"^Homem\b", "sex": "male"},
    {"match": r"^Mulher\b", "sex": "female"},
]

LAYOUTS["guinea_bissau"] = {
    "survey": "ERI-ESI / IRIESI -- Inquérito Regional Integrado sobre Emprego "
              "e Setor Informal",
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "decimal": ",",
    "period": "2018",
    "reference_period": "2017-2018",
    "tables": [{
        "page_contains": ["principais indicadores de emprego"],
        "take": "trailing",
        "columns": _GW_COLS,
        "first_match_only": False,
        # The recap table lists indicators this schema has no topic for --
        # schooling rates, out-of-school children, income. They are not
        # declared as blocks, so without this the block above them stayed
        # open and their rows were read as its values.
        "block_ends_on_heading": True,
        "blocks": [
            {"id": "des", "match": r"^Taxa de desemprego da OIT\s*$",
             "topic": "unemployment_rate", "definition": "strict",
             "label": "Taxa de desemprego da OIT"},
            {"id": "sub", "match": r"^Taxa combinada de subemprego",
             "topic": "underemployment_rate", "definition": "broad",
             "label": "Taxa combinada de subemprego relacionada com o tempo "
                      "de trabalho e desemprego"},
            {"id": "su4", "match": r"^Taxa de subutilização da m[aã]o",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Taxa de subutilização da mão-de-obra (SU4)"},
            {"id": "formal", "match": r"^Percentual de emprego formal no setor",
             "topic": "informal_employment_share",
             "label": "Percentual de emprego formal no setor não agrícola"},
        ],
        "rows": [
            *[dict(r, block=b) for b in ("des", "sub", "su4", "formal")
              for r in _GW_SEX_ROWS],
            # THE AGE ROWS ARE THEIR OWN LINES, not a suffix on the heading.
            # These expected "Taxa de desemprego da OIT ... 15 - 34" on one
            # line; the recap prints the heading again and then
            #     15 - 34 anos 17,8 3,6 12,9 8,2 10,5
            #     35 anos e mais 7,7 1,7 5,5 2,6 3,9
            # so neither matched and both age splits were dropped.
            #
            # `block` is what makes "15 - 34 anos" unambiguous -- it appears
            # under the OIT heading and again under subutilizacao -- and it is
            # also what closes the repeated block: with no data row beneath it,
            # the second heading's block stayed open into the NEXT indicator
            # and read its values as its own.
            {"match": r"^15\s*-\s*34 anos", "block": "des",
             "topic": "youth_unemployment_rate", "definition": "strict",
             "age_group": "15-34", "drop_leading": 2,
             "label": "Taxa de desemprego da OIT, 15-34 anos"},
            {"match": r"^35 anos e mais", "block": "des",
             "topic": "unemployment_rate", "definition": "strict",
             "age_group": "35+", "drop_leading": 1,
             "label": "Taxa de desemprego da OIT, 35 anos e mais"},
            {"match": r"^15\s*-\s*34 anos", "block": "su4",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "age_group": "15-34", "drop_leading": 2,
             "label": "Taxa de subutilização da mão-de-obra, 15-34 anos"},
            {"match": r"^35 anos e mais", "block": "su4",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "age_group": "35+", "drop_leading": 1,
             "label": "Taxa de subutilização da mão-de-obra, 35 anos e mais"},
        ],
    }],
}


LAYOUT = LAYOUTS['guinea_bissau']
parse = make_parser(LAYOUT)
