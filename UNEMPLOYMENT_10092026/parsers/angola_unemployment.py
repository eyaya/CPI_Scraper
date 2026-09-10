"""Angola — unemployment / labour-force layout and parser.

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
# ANGOLA -- INE, Inquérito sobre o Emprego em Angola (IEA), quarterly.
# "Quadro 1 - Principais indicadores sobre o mercado de trabalho".
# Columns: Indicadores | I trimestre <ano> | II trimestre <ano> | Diferença | Variação
#
# The SAME ELEVEN ROW LABELS appear twice -- once under "População com 15 ou
# mais anos" and again under "População com 18 ou mais anos". A label-keyed
# parser silently overwrites the first block with the second, so the two
# headings are declared as `blocks` that re-scope `working_age_base`, and the
# dedupe key is (row, block).
#
# Only the two period columns are captured: `Diferença` and `Variação` are
# derived quantities, and the collector does not store derivations.
# PT conventions: comma decimals, SPACE thousands ("23 006 410").
#
# CROSS-CHECK (Q2 2026, 15+): WAP 23,006,410; força de trabalho 12,962,065;
# empregada 10,171,244; desempregada 2,790,821; taxa da força de trabalho 56,3;
# taxa de emprego 44,2; taxa de emprego informal 80,1; taxa de desemprego 21,5.
# =========================================================================
LAYOUTS["angola"] = {
    "survey": "Inquérito sobre o Emprego em Angola (IEA)",
    "frequency": "quarterly",
    "working_age_base": "15+",
    "decimal": ",",
    "period_patterns": [
        r"referente ao\s+((?:primeiro|segundo|terceiro|quarto)\s+trimestre\s+de\s+20\d{2})",
        r"\b((?:I|II|III|IV)\s+trimestre\s+de\s+20\d{2})\b",
    ],
    "tables": [{
        "page_contains": ["principais indicadores sobre o mercado de trabalho"],
        "take": "leading",
        # Only the CURRENT quarter's column is captured. The previous-quarter
        # column is a restatement that the previous run already collected, and
        # dating it correctly from this document alone is not reliable.
        "columns": [{"skip": True}, {}],
        "blocks": [
            {"id": "15+", "match": r"População com 15 ou mais anos",
             "working_age_base": "15+"},
            {"id": "18+", "match": r"População com 18 ou mais anos",
             "working_age_base": "18+"},
        ],
        "rows": [
            {"match": r"^Força de trabalho", "topic": "labour_force",
             "label": "Força de trabalho"},
            {"match": r"^População fora da força de trabalho",
             "topic": "outside_labour_force",
             "label": "População fora da força de trabalho"},
            {"match": r"^População empregada", "topic": "employed",
             "label": "População empregada"},
            {"match": r"^População desempregada", "topic": "unemployed",
             "label": "População desempregada"},
            {"match": r"^Taxa da força de trabalho",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Taxa da força de trabalho"},
            {"match": r"^Taxa de emprego\b", "exclude": r"informal",
             "topic": "employment_to_population_ratio", "label": "Taxa de emprego"},
            {"match": r"^Taxa de emprego informal",
             "topic": "informal_employment_share", "label": "Taxa de emprego informal"},
            {"match": r"^Taxa de desemprego", "topic": "unemployment_rate",
             "definition": "strict", "label": "Taxa de desemprego"},
        ],
    }],
}


LAYOUT = LAYOUTS['angola']
parse = make_parser(LAYOUT)
