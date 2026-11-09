"""São Tomé and Príncipe -- monetary-poverty layout (INE, IOF 2017 report).

"Inquérito aos Orçamentos Familiares 2017", chapter II (Análise da pobreza
monetária). Cost-of-basic-needs line built with the World Bank: STD 19.017,00
per capita per year (STD 52,10 a day) -- printed in "STD" although the
magnitude is that of thousand old dobras (= STN after the 2018
redenomination); kept as printed. Welfare = consumption per capita (DPC).

TWO DECIMAL CONVENTIONS IN ONE REPORT: Tabelas 4, 6 and 11 print "66.7"
(point), Tabelas 12 and 13 print "29,9" (comma). The engine takes one
`decimal` per layout, so this module runs two layouts and concatenates them.

Collected:
  Tabela 4   national P0 P1 P2 for the total line AND the extreme/food line
  Tabela 6   P0 P1 P2 by sex of the person, household type, welfare quintile
  Tabela 11  95% CI of the 2017 P0; 2010 P0 (+CI) by S2S imputation
  Tabelas 12/13  2010 P1 and P2 by S2S imputation
The 2010 values are the S2S imputation onto IOF 2017 prices and line -- a
separate `survey` -- NOT the official IOF 2010 estimate (66,2%, prose only),
which the report itself says is not comparable.

Not collected: Tabela 6 contributions (printed as FRACTIONS 0.49769; the
schema's shares are percent and a value is never rescaled); Tabela 6 sections
3-4 (employment situation / socio-economic group) -- the report does not say
whether the status is the person's or the head's; Tabelas 12/13 2017 rows
(P1 29,9 vs Tabela 4's 30.0 -- the same key, a published rounding
discrepancy; Tabela 4 is kept); standard errors; Tabela 7 (household
distribution); all figures (charts only).

CROSS-CHECK (verbatim): P0 66.7 / P1 30.0 / P2 17.3; extreme 47.0 / 18.4 /
9.9; men 66.7, women 66.5; 2010 S2S P0 68.4 (66.0-70.7), P1 35,3, P2 22,5.
"""
from __future__ import annotations

import pandas as pd

from ._vocab import label_rows
from .poverty_tables import make_parser

_FGT = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}]
_SKIP3 = [{"skip": True}] * 3
_EXTREME = {"line_level": "extreme", "line_name": "Linha de pobreza extrema/alimentar 2017",
            "line_value": "", "line_unit": ""}
_S2S = {"survey": "IOF 2010 (S2S imputation, IOF 2017 prices and line)",
        "period": "2010", "reference_period": "2010"}
_T6 = ["tabela 6. perfil de pobreza da população"]

_BASE = {
    "survey": "IOF 2017", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc",
    "line_type": "national", "line_level": "overall",
    "line_name": "Linha de pobreza 2017 (custo das necessidades básicas)",
    "line_value": 19017, "line_unit": "STD per capita per year (as printed)",
    "period": "2017", "reference_period": "2017",
}

LAYOUT = {
    **_BASE, "decimal": ".",
    "tables": [
        {   # Tabela 4 -- total and extreme lines
            "page_contains": ["tabela 4. pobreza total e extrema"],
            "exact_numbers": True,
            "columns": _FGT + [dict(c, **_EXTREME) for c in _FGT],
            "rows": [{"match": r"^Nacional\b"}],
        },
        {   # Tabela 6 -- 1. Sexo (of the person: the prose gives 66,66 / 66,53
            # "no nível individual")
            "page_contains": _T6, "start": r"^1\. Sexo", "end": r"^2\. ",
            "columns": _FGT + _SKIP3,
            "rows": [{"match": r"^Homens(?=\s)", "topic": "sex", "characteristic": "Homens", "sex": "male"},
                     {"match": r"^Mulheres(?=\s)", "topic": "sex", "characteristic": "Mulheres", "sex": "female"}],
        },
        {   # Tabela 6 -- 2. Tipologia do agregado familiar
            "page_contains": _T6, "start": r"^2\. Tipologia", "end": r"^3\. ",
            "columns": _FGT + _SKIP3,
            "rows": label_rows("household_type", [
                "Unipessoal", "Casal", "Casal com Filhos", "Monoparental Nuclear",
                "Monoparental Alargada", "Família Alargada"]),
        },
        {   # Tabela 6 -- 5. Quintil (first row on p.12, the rest overleaf)
            "page_contains": _T6, "start": r"^5\. Quintil",
            "columns": _FGT + _SKIP3,
            "rows": label_rows("quintile", ["20% mais pobres"]),
        },
        {
            "page_contains": ["tabela 7. perfil da repartição"], "end": r"^Fonte",
            "columns": _FGT + _SKIP3,
            "rows": label_rows("quintile", ["2º quintil", "3º quintil", "4º quintil",
                                            "20% mais ricos"]),
        },
        {   # Tabela 11 -- P0 with standard error and 95% CI
            "page_contains": ["tabela 11. taxa de pobreza em 2017 e 2010"],
            "exact_numbers": True,
            "columns": [{"skip": True}, {"skip": True},
                        {"metric": "headcount_ci_low"}, {"metric": "headcount_ci_high"}],
            "rows": [
                {"match": r"^IOF 2017 Taxa de pobreza FGT\(α = 0\)"},
                {"match": r"^S2S 2010 Taxa de pobreza FGT\(α = 0\)", **_S2S,
                 "columns": [{"metric": "headcount"}, {"skip": True},
                             {"metric": "headcount_ci_low"}, {"metric": "headcount_ci_high"}]},
            ],
        },
    ],
}

LAYOUT_COMMA = {
    **_BASE, "decimal": ",",
    "tables": [
        {   # Tabela 12 -- 2010 gap (S2S); the 2017 row repeats Tabela 4 (29,9 vs 30.0)
            "page_contains": ["tabela 12. gap de pobreza em 2017 e 2010"],
            "start": r"^Tabela 12\.", "end": r"^Fonte",
            "columns": [{"metric": "gap", **_S2S}, {"skip": True}, {"skip": True}, {"skip": True}],
            "rows": [{"match": r"^S2S 2010"}],
        },
        {   # Tabela 13 -- its S2S row is overleaf, on the page with Figura 17
            "page_contains": ["incidência de crescimento no dpc"], "end": r"^Fonte",
            "columns": [{"metric": "severity", **_S2S}, {"skip": True}, {"skip": True}, {"skip": True}],
            "rows": [{"match": r"^S2S 2010"}],
        },
    ],
}

_dot = make_parser(LAYOUT)
_comma = make_parser(LAYOUT_COMMA)


def parse(path: str) -> pd.DataFrame:
    return pd.concat([_dot(path), _comma(path)], ignore_index=True)
