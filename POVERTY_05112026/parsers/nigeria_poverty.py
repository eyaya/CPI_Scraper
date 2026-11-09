"""Nigeria -- monetary-poverty layout (NBS, "2019 Poverty and Inequality in
Nigeria: Executive Summary", May 2020; NLSS 2018-19).

National line 137,430 Naira per person per year (food 81,767; lower 124,948;
the UPPER line is the official one). Welfare = regionally adjusted per capita
consumption. EVERY ESTIMATE EXCLUDES BORNO (its sample covered accessible areas
only), including the "NIGERIA" rows, which are filed as the national figure
with that caveat in the descriptor.

Read from the Annex (pp. 23-24, the tabular repeat of the infographics):
  Table 4  NIGERIA / Urban / Rural + 36 states and FCT: P0, P1, P2
  Table 5  P0 by education of head x sex of head, NIGERIA / Urban / Rural
  Table 6  P0 by income-generating activity of head x sex, same rows
  Table 7  P0 by household size, same rows
Not read: Table 3 (rounded repeat of Table 4 + Gini), quintile means, Gini
(inequality), the infographic pages (same numbers as the annex).
NLSS 2018-19 is NOT comparable with NLSS 2003-04 / HNLSS 2009-10 (para 17).

CROSS-CHECK (verbatim): 40.09 / 12.85 / 5.63; Urban 18.04; Rural 52.10;
Sokoto 87.73; Lagos 4.50; Taraba P2 24.44; female head with post-secondary
education 5.66; 20+ person households 77.66.
"""
from __future__ import annotations

from .poverty_tables import make_parser

_LOC_ROWS = [
    {"match": r"^NIGERIA(?=\s+\d)"},
    {"match": r"^Urban(?=\s+\d)", "locality": "urban", "locality_label": "Urban"},
    {"match": r"^Rural(?=\s+\d)", "locality": "rural", "locality_label": "Rural"},
]


def _by_sex(topic, cats):
    out = []
    for c in cats:
        for sx, lab in (("male", "Male"), ("female", "Female")):
            out.append({"metric": "headcount", "topic": topic, "characteristic": c, "sex": sx})
    return out


LAYOUT = {
    "survey": "NLSS 2018-19", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall",
    "line_name": "National poverty line (upper) 2019",
    "line_value": 137430, "line_unit": "NGN per person per year",
    "period": "2018", "reference_period": "2018-19",
    "tables": [
        {   # Table 4 -- national, urban, rural
            "page_contains": ["table 4: poverty and inequality indices by states"],
            "exact_numbers": True,
            "columns": [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}],
            "rows": [dict(r, topic="locality") if "locality" in r else r for r in _LOC_ROWS],
        },
        {   # Table 4 -- 36 states + FCT (Borno prints no figures)
            "page_contains": ["table 4: poverty and inequality indices by states"],
            "columns": [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}],
            "row_scan": {"expect_rows": 36, "exclude_labels": ["NIGERIA", "Urban", "Rural"]},
        },
        {   # Table 5 -- education of head x sex
            "page_contains": ["table 5 poverty headcount rate by household head"],
            "start": r"^Table 5\b", "end": r"^Table 6\b",
            "columns": _by_sex("education_of_head", [
                "No education/ less than primary education", "Primary education",
                "Secondary education", "Post-secondary education"]),
            "rows": _LOC_ROWS,
        },
        {   # Table 6 -- income-generating activity of head x sex
            "page_contains": ["table 6 poverty headcount rate by household head"],
            "start": r"^Table 6\b", "end": r"^Table 7\b",
            "columns": _by_sex("employment_of_head", [
                "Agriculture only", "Nonfarm enterprise only", "Wage work only",
                "Diversified", "Apprenticeship/ Not working"]),
            "rows": _LOC_ROWS,
        },
        {   # Table 7 -- household size
            "page_contains": ["table 7 poverty headcount rate by household size"],
            "start": r"^Table 7\b",
            "columns": [{"metric": "headcount", "topic": "household_size", "characteristic": c}
                        for c in ("1 person", "2-4 people", "5-9 people", "10-19 people",
                                  "20 or more people")],
            "rows": _LOC_ROWS,
        },
    ],
}

parse = make_parser(LAYOUT)
