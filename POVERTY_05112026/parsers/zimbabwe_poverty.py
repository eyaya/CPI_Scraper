"""Zimbabwe -- monetary-poverty layout (ZIMSTAT, Zimbabwe Poverty Report 2017,
PICES 2017, published May 2019).

Two lines: the upper Total Consumption Poverty Line (TCPL, the overall line)
and the lower Food Poverty Line (FPL, extreme). Welfare = consumption
expenditure PER CAPITA. Nearly every table is printed twice over -- once for
HOUSEHOLDS, once for PEOPLE -- and the two are kept apart by
`unit_of_analysis` (household P0 60.6, person P0 70.5 in 2017).

Collected
  2.5 / 2.6   P0 (TCPL), P0 (FPL), P1, P2 by rural / urban / national for
              PICES 2017, PICES 2011/12, ICES 2001 and ICES 1995 -- households
              and people. ZIMSTAT notes the 1995 and 2001 lines were NOT
              recalibrated to 2017 prices; each round is its own survey.
  2.7 / 2.8   the same four measures plus share of all poor, by 10 provinces
              (households / people)
  2.10/2.11   households by province within rural and within urban areas
  2.14        households by sex and marital status of the head
  2.15        P0 of households by main activity of the head, rural/urban/all
  2.16        P0 on both lines by sector of employment of the head, rural/urban
Not collected: 2.4 (repeats 2.5/2.6), 2.9 (a simulation), 2.12/2.13/2.22+
(not poverty measures), 2.17-2.21 (cuts by members' employment and income
source -- no topic for them), Gini (inequality, separate indicator).

PUBLISHED DEFECT DROPPED: Table 2.11's urban MANICALAND row prints
"22.3 0.9 5.3 1.8" -- digit for digit Table 2.7's BULAWAYO row -- beside a
share of urban poor (11.7) that cannot belong to Bulawayo's values. Its share
is kept; its four indices are not.

CROSS-CHECK (verbatim): households 60.6 / 21.9 / 26.9 / 14.7, people 70.5 /
29.3 / 33.3 / 18.9 (2017); 2011/12 households 62.6, people 72.3; rural people
86.0, urban 37.0; Mashonaland Central households 81.6 (FPL 41.2, P1 42.2,
P2 25.1); Bulawayo people 29.9; male-headed 61.6, female-headed 58.9.
"""
from __future__ import annotations

import re

from ._vocab import label_rows
from .poverty_tables import make_parser

_X = {"line_level": "extreme", "line_name": "Food Poverty Line (FPL)"}
_HH = {"unit_of_analysis": "household"}
_P = {"unit_of_analysis": "person"}
_SKIP = {"skip": True}


def _fgt(unit, **kw):
    """Poverty | Extreme poverty | Poverty gap | Poverty severity."""
    return [{"metric": "headcount", **unit, **kw}, {"metric": "headcount", **unit, **_X, **kw},
            {"metric": "gap", **unit, **kw}, {"metric": "severity", **unit, **kw}]


_ROUNDS = [  # heading in Tables 2.5/2.6, next heading, survey attrs
    (r"^PICES 2017$", r"^PICES 2011/12$", {"survey": "PICES 2017", "period": "2017", "reference_period": "2017"}),
    (r"^PICES 2011/12$", r"^ICES 2001$", {"survey": "PICES 2011/12", "period": "2011", "reference_period": "2011/12"}),
    (r"^ICES 2001$", r"^ICES 1995$", {"survey": "ICES 2001", "period": "2001", "reference_period": "2001"}),
    (r"^ICES 1995$", r"^Source", {"survey": "ICES 1995", "period": "1995", "reference_period": "1995"}),
]
_RES_ROWS = [
    {"match": r"^Rural(?=\s+\d)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
    {"match": r"^Urban(?=\s+\d)", "topic": "locality", "locality": "urban", "locality_label": "Urban"},
    {"match": r"^All Zimbabwe(?=\s+\d)"},
]
_PROV = ["Manicaland", "Mashonaland Central", "Mashonaland East", "Mashonaland West",
         "Matabeleland North", "Matabeleland South", "Midlands", "Masvingo", "Bulawayo"]


def _prov_rows(names, harare_label, **attrs):
    rows = [{"match": rf"^{p}(?=\s+\d)", "geography": p, **attrs} for p in names]
    if harare_label:
        rows.append({"match": rf"^{harare_label}(?=\s+\d)", "geography": "Harare", **attrs})
    return rows


def _rounds(caption, unit):
    return [{"page_contains": [caption], "start": a, "end": b, "exact_numbers": True,
             "columns": _fgt(unit, **s), "rows": _RES_ROWS} for a, b, s in _ROUNDS]


def _headship(sex, head, start, end):
    """Table 2.14 block: the headship row, then its marital-status sub-rows."""
    ch = "Male-headed" if sex == "male" else "Female headed"
    sub = [("-Married", "Married (de facto)"), ("-Divorced", "Divorced (de jure)"),
           ("-Widowed", "Widowed (de jure)"), ("Never Married", "Never married")]
    return [
        {"page_contains": ["table 2.14: household poverty by household headship"],
         "exact_numbers": True, "columns": _fgt(_HH),
         "rows": [{"match": rf"^{head}(?=\s+\d)", "topic": "sex_of_head",
                   "characteristic": ch, "sex": sex}]},
        {"page_contains": ["table 2.14: household poverty by household headship"],
         "start": start, "end": end, "start_inclusive": False, "exact_numbers": True,
         "columns": _fgt(_HH),
         "rows": [{"match": rf"^{re.escape(a)}(?=\s+\d)", "topic": "marital_status_of_head",
                   "characteristic": b, "sex": sex} for a, b in sub]},
    ]


LAYOUT = {
    "survey": "PICES 2017", "welfare_aggregate": "consumption",
    "unit_of_analysis": "household", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall",
    "line_name": "Total Consumption Poverty Line (TCPL)",
    "period": "2017", "reference_period": "2017",
    "tables": [
        *_rounds("table 2.5: household measured prevalence of poverty", _HH),
        *_rounds("table 2.6: individual measured prevalence of poverty", _P),
        {   # 2.7 households by province
            "page_contains": ["table 2.7: household poverty indices by province"],
            "exact_numbers": True,
            "columns": [{"metric": "poor_share", **_HH}] + _fgt(_HH),
            "rows": _prov_rows(_PROV, "Harare Province"),
        },
        {   # 2.8 people by province
            "page_contains": ["table 2.8: prevalence of poor and severely poor people"],
            "exact_numbers": True,
            "columns": [{"metric": "poor_share", **_P}] + _fgt(_P),
            "rows": _prov_rows(_PROV, "Harare Province"),
        },
        {   # 2.10 rural households by province (no Bulawayo / Harare)
            "page_contains": ["table 2.10: household poverty in percentages by province in rural"],
            # 2.10 and 2.11 share a page and the same province labels.
            "start": r"^Table 2\.10:", "end": r"^Table 2\.11:",
            "exact_numbers": True,
            "columns": [{"metric": "poor_share", **_HH}] + _fgt(_HH),
            "rows": _prov_rows(_PROV[:-1], None, topic="locality", locality="rural",
                               locality_label="Rural"),
        },
        {   # 2.11 urban households by province -- Manicaland dropped (see docstring)
            "page_contains": ["table 2.11: household poverty prevalence by province in urban"],
            "start": r"^Table 2\.11:",
            "exact_numbers": True,
            "columns": [{"metric": "poor_share", **_HH}] + _fgt(_HH),
            "rows": _prov_rows(_PROV[1:], "Harare", topic="locality", locality="urban",
                               locality_label="Urban"),
        },
        {   # 2.11 Manicaland: share of urban poor only
            "page_contains": ["table 2.11: household poverty prevalence by province in urban"],
            "start": r"^Table 2\.11:",
            "exact_numbers": True,
            "columns": [{"metric": "poor_share", **_HH}] + [_SKIP] * 4,
            "rows": _prov_rows(["Manicaland"], None, topic="locality", locality="urban",
                               locality_label="Urban"),
        },
        *_headship("male", "Male-headed", r"^Male-headed", r"^Female headed"),
        *_headship("female", "Female headed", r"^Female headed", r"^Source"),
        {   # 2.15 main activity of head: Rural | Urban | All Zimbabwe
            "page_contains": ["table 2.15: prevalence of household poverty by main activity"],
            "exact_numbers": True,
            "columns": [{"metric": "headcount", **_HH, "locality": "rural", "locality_label": "Rural"},
                        {"metric": "headcount", **_HH, "locality": "urban", "locality_label": "Urban"},
                        {"metric": "headcount", **_HH}],
            "rows": label_rows("employment_of_head", [
                "Paid employee-permanent", "Paid employee casual", "Employer",
                "Communal and resettlement farmer", "Own account worker (other)",
                "Unpaid family worker", "Unemployed"]),
        },
        {   # 2.16 sector of employment: Rural poor | extreme | Urban poor | extreme
            "page_contains": ["table 2.16: prevalence of household poverty by sector of employment"],
            "exact_numbers": True,
            "columns": [{"metric": "headcount", **_HH, "locality": "rural", "locality_label": "Rural"},
                        {"metric": "headcount", **_HH, **_X, "locality": "rural", "locality_label": "Rural"},
                        {"metric": "headcount", **_HH, "locality": "urban", "locality_label": "Urban"},
                        {"metric": "headcount", **_HH, **_X, "locality": "urban", "locality_label": "Urban"}],
            "rows": [dict(r, characteristic="Sector: " + r["characteristic"]) for r in label_rows(
                "employment_of_head", ["Own account worker other", "Government worker",
                                       "Parastatal worker", "Private sector", "Formal sector",
                                       "Informal sector"])],
        },
        {   # 2.16 farmers: urban cells are "-" (not applicable) -- rural only
            "page_contains": ["table 2.16: prevalence of household poverty by sector of employment"],
            "exact_numbers": True,
            "columns": [{"metric": "headcount", **_HH, "locality": "rural", "locality_label": "Rural"},
                        {"metric": "headcount", **_HH, **_X, "locality": "rural", "locality_label": "Rural"}],
            "rows": [dict(r, characteristic="Sector: " + r["characteristic"]) for r in label_rows(
                "employment_of_head", ["Communal farmer", "Resettlement farmer"])],
        },
    ],
}

parse = make_parser(LAYOUT)
