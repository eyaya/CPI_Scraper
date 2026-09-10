"""Angola — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import _URBAN, _RURAL, _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# ANGOLA -- INE, "Índice de Pobreza Multidimensional de Angola" (IPM-A,
# IIMS 2015-2016).
#
# REWRITTEN against the downloaded PDF, which turned out to be the richest
# document in the set -- eight result tables in three different shapes:
#
#   Quadro 2  national, TRANSPOSED: one metric per row, value + 95% CI.
#             The incidence row also carries the cutoff in a merged cell
#             ("30% Incidência (H, %) 54,0 51,7 56,3"), so its leading number
#             is dropped -- it is the k, not a measurement.
#   Quadro 3  by área de residência: ten numbers, share + value/CI x3.
#   Quadro 5/6/7  by província: share + value/CI, for M0, H and A separately.
#   Quadro 8  by age group: same ten-number shape as Quadro 3.
#   Quadro 9  by sex of head: male and female side by side, and the incidence
#             row carries each side's household share, so it has eight numbers
#             where the index and intensity rows have six.
#   Quadro 4  uncensored and censored headcount ratios, urban and rural.
#
# The first version of this layout assumed a single `share | IPM | H | A`
# table and failed the M0 range check on the confidence bounds.
#
# CROSS-CHECK (verbatim):
#   National IPM-A 0,264 (0,252-0,276); H 54,0 (51,7-56,3); A 48,9 (48,2-49,6)
#   Urbana 62,9% | 0,152 | 35,0 | 43,4      Rural 37,1% | 0,463 | 87,8 | 52,8
#   Cunene 0,405   Bié 0,400   Luanda 0,094   Cabinda 0,153
#   Bié H 78,3   Cuanza Sul A 53,3
#   0-9 anos 0,326 | 64,3 | 50,8            65 anos e mais 0,283 | 64,0 | 44,2
#   Male-headed IPM 0,260   Female-headed IPM 0,276
# =========================================================================
# share, then value | CI low | CI high for each of IPM, H and A.
_AO_COLS10 = [
    {"skip": True},
    {"metric": "index_M0"}, {"skip": True}, {"skip": True},
    {"metric": "incidence_H"}, {"skip": True}, {"skip": True},
    {"metric": "intensity_A"}, {"skip": True}, {"skip": True},
]


def _ao_province(metric: str) -> list[dict]:
    """Quadros 5, 6 and 7 print one metric each: share | value | CI lo | CI hi."""
    return [{"skip": True}, {"metric": metric}, {"skip": True}, {"skip": True}]


# The province tables each repeat the national figure on an "Angola" line;
# Quadro 2 already carries it with all three metrics, so it is not listed here.
_AO_PROVINCES = [
    "Cunene", "Bié", "Lunda Norte", "Cuanza Sul", "Huíla", "Moxico",
    "Cuando Cubango", "Uíge", "Huambo", "Lunda Sul", "Malanje", "Cuanza Norte",
    "Bengo", "Benguela", "Namibe", "Zaire", "Cabinda", "Luanda",
]


def _ao_province_rows() -> list[dict]:
    rows = []
    for p in _AO_PROVINCES:
        esc = p.replace("í", "[íi]").replace("é", "[ée]").replace("ú", "[úu]")
        rows.append({"match": rf"^{esc}\b", "geography": p})
    return rows


LAYOUT = {
    "mpi_type": "national",
    "measure_name": "IPM-A",
    "survey": "IIMS 2015-2016 (Inquérito de Indicadores Múltiplos e de Saúde)",
    "k_cutoff": 30, "n_dimensions": 4, "n_indicators": 16,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "period": "2016", "reference_period": "IIMS 2015-2016",
    "tables": [
        {   # Quadro 2 -- national, metrics in rows
            "page_contains": ["linha de pobreza"],
            "columns": [{"metric": "index_M0"}, {"skip": True}, {"skip": True}],
            "rows": [
                {"match": r"^IPM-A\s", **_NATIONAL},
                {"match": r"Incid[êe]ncia \(H", "drop_leading": 1, **_NATIONAL,
                 "columns": [{"metric": "incidence_H"}, {"skip": True},
                             {"skip": True}]},
                {"match": r"^Intensidade \(A", **_NATIONAL,
                 "columns": [{"metric": "intensity_A"}, {"skip": True},
                             {"skip": True}]},
            ],
        },
        {   # Quadro 3 -- área de residência
            "page_contains": ["área de", "residência"],
            "exact_numbers": True,
            "columns": _AO_COLS10,
            "rows": [
                {"match": r"^Urbana\b", **_URBAN, "locality_label": "Urbana"},
                {"match": r"^Rural\b", **_RURAL, "locality_label": "Rural"},
            ],
        },
        {   # Quadro 5 -- IPM-A por província
            "page_contains": ["ipm-a por província"],
            "exact_numbers": True,
            "columns": _ao_province("index_M0"),
            "rows": _ao_province_rows(),
        },
        {   # Quadro 6 -- incidência por província
            "page_contains": ["incidência da pobreza por província"],
            "exact_numbers": True,
            "columns": _ao_province("incidence_H"),
            "rows": _ao_province_rows(),
        },
        {   # Quadro 7 -- intensidade por província
            "page_contains": ["intensidade da pobreza por província"],
            "exact_numbers": True,
            "columns": _ao_province("intensity_A"),
            "rows": _ao_province_rows(),
        },
        {   # Quadro 8 -- grupo etário
            "page_contains": ["grupo etário"],
            "exact_numbers": True,
            "columns": _AO_COLS10,
            "rows": [
                # The age BAND is printed in the label, so its own digits
                # lead the row: "0-9 anos 34,7 0,326 ..." parses as 0, 9, then
                # the data. They are dropped, not read as measurements.
                {"match": r"^0-9 anos", "age_group": "0-9", "topic": "age",
                 "characteristic": "0-9 anos", "drop_leading": 2},
                {"match": r"^10-17 anos", "age_group": "10-17", "topic": "age",
                 "characteristic": "10-17 anos", "drop_leading": 2},
                {"match": r"^18-24 anos", "age_group": "18-24", "topic": "age",
                 "characteristic": "18-24 anos", "drop_leading": 2},
                {"match": r"^25-64 anos", "age_group": "25-64", "topic": "age",
                 "characteristic": "25-64 anos", "drop_leading": 2},
                {"match": r"^65 anos e mais", "age_group": "65+",
                 "topic": "age", "characteristic": "65 anos e mais",
                 "drop_leading": 1},
            ],
        },
        {   # Quadro 9 -- sexo do chefe do agregado
            "page_contains": ["chefiados por mulheres"],
            "columns": [{"skip": True}],
            "rows": [
                {"match": r"^IPM\s", "topic": "sex_of_head",
                 "columns": [
                     {"metric": "index_M0", "sex": "male",
                      "characteristic": "Chefe homem"},
                     {"skip": True}, {"skip": True},
                     {"metric": "index_M0", "sex": "female",
                      "characteristic": "Chefe mulher"},
                     {"skip": True}, {"skip": True}]},
                {"match": r"^Incid[êe]ncia \(H", "topic": "sex_of_head",
                 "columns": [
                     {"skip": True},                  # share of male-headed hh
                     {"metric": "incidence_H", "sex": "male",
                      "characteristic": "Chefe homem"},
                     {"skip": True}, {"skip": True},
                     {"skip": True},                  # share of female-headed hh
                     {"metric": "incidence_H", "sex": "female",
                      "characteristic": "Chefe mulher"},
                     {"skip": True}, {"skip": True}]},
                {"match": r"^Intensidade \(A", "topic": "sex_of_head",
                 "columns": [
                     {"metric": "intensity_A", "sex": "male",
                      "characteristic": "Chefe homem"},
                     {"skip": True}, {"skip": True},
                     {"metric": "intensity_A", "sex": "female",
                      "characteristic": "Chefe mulher"},
                     {"skip": True}, {"skip": True}]},
            ],
        },
        {   # Quadro 4 -- uncensored and censored headcounts, by locality
            "page_contains": ["taxa não censurada", "taxa censurada"],
            "exact_numbers": True,
            "columns": [
                {"metric": "uncensored_headcount", "locality": "urban",
                 "locality_label": "Urbana", "topic": "locality"},
                {"metric": "uncensored_headcount", "locality": "rural",
                 "locality_label": "Rural", "topic": "locality"},
                {"metric": "censored_headcount", "locality": "urban",
                 "locality_label": "Urbana", "topic": "locality"},
                {"metric": "censored_headcount", "locality": "rural",
                 "locality_label": "Rural", "topic": "locality"},
            ],
            "row_scan": {
                "label": r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\- ]{3,45}?)\s+(?=\d)",
                "attr": "mpi_indicator",
                "expect_rows": 10,
                "exclude_labels": ["Quadro", "Gráfico", "Cartograma"],
            },
        },
    ],
}


parse = make_parser(LAYOUT)
