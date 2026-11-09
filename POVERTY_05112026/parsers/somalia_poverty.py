"""Somalia -- monetary-poverty layout (SNBS, Somalia Poverty Report 2023, SIHBS 2022).

Real consumption per person per year, in USD (Somalia's economy is dollarised
and SNBS prices the lines in USD, Table 2.10): poverty line USD 754, food line
USD 425 per person per year. Extreme poverty = consumption below the FOOD line.
Residence has THREE strata: urban, rural and NOMADIC (locality "other").

Collected:
  4.1  P0 and the distribution of the poor for both lines, and the population
       distribution: rural / urban / nomadic, 17 regions (8 + 9 over two pages), total. The table runs
       over two pages; regions whose names wrap after their numbers ("Lower" /
       "Juba", "Waqooyi" / "Galbeed", "Middle" / "Shabelle") are re-joined.
  4.2  the poverty gap by residence (P0 and the poor distribution repeat 4.1;
       the population and number-of-poor cells are glyph-doubled in the text
       layer -- "33,,771471" -- and are not read).
  5.1  P0 and gap by sex of the household head within each residence and total.
  5.2  P0 by marital status of the head, overall and by sex of the head.
Not collected: 4.3 / 4.4 (quantiles, Gini -- inequality), 5.3 (household size
by poverty status, not a poverty measure), 5.4 (printed rotated; the text
layer is reversed and doubled), 5.5 (access to services; no topic).

CROSS-CHECK (verbatim): P0 54.4, extreme 20.9, gap 19.8; urban 46.1 / 13.8,
rural 65.5, nomadic 78.4 / 46.8; Middle Shabelle 87.4 / 54.7; Awdal 39.4;
female-headed 53.9 (gap 18.9); never-married heads 24.8.
"""
from __future__ import annotations

from ._vocab import label_rows
from .poverty_tables import make_parser

_POV = {"line_level": "overall", "line_name": "Poverty line (SNBS, CBN, SIHBS 2022)",
        "line_value": 754, "line_unit": "USD per person per year"}
_EXT = {"line_level": "extreme", "line_name": "Food poverty line (SNBS, CBN, SIHBS 2022)",
        "line_value": 425, "line_unit": "USD per person per year"}
_COLS41 = [{"metric": "headcount", **_POV}, {"metric": "poor_share", **_POV},
           {"metric": "headcount", **_EXT}, {"metric": "poor_share", **_EXT},
           {"metric": "population_share"}]
_RES = {"Rural": {"topic": "locality", "locality": "rural", "locality_label": "Rural"},
        "Urban": {"topic": "locality", "locality": "urban", "locality_label": "Urban"},
        "Nomadic": {"topic": "locality", "locality": "other", "locality_label": "Nomadic"}}
_REGION_SCAN = {"exclude_labels": ["Rural", "Urban", "Nomadic", "Total", "Region",
                                  "Nomadic Region"],  # the row joined to the next heading
                "label_ok": r"^[A-Z][A-Za-z ]+$"}


def _res_rows(cols=None, total=True):
    rows = [{"match": rf"^{k}(?=\s+\d)", **v, **({"columns": cols} if cols else {})}
            for k, v in _RES.items()]
    if total:
        rows.append({"match": r"^Total(?=\s+\d)", **({"columns": cols} if cols else {})})
    return rows


def _t51(block, attrs):
    return {"page_contains": ["table 5. 1 poverty incidences (%), by residence and sex"],
            "start": rf"^{block}$", "end": r"^(?:Rural|Urban|Nomadic|Total)$",
            "exact_numbers": True, "defaults": attrs,
            "columns": [{"metric": "headcount"}, {"metric": "gap"}],
            "rows": [{"match": r"^HH Head Male(?=\s)", "topic": "sex_of_head",
                      "characteristic": "HH Head Male", "sex": "male"},
                     {"match": r"^HH Head Female(?=\s)", "topic": "sex_of_head",
                      "characteristic": "HH Head Female", "sex": "female"}]}


LAYOUT = {
    "survey": "SIHBS 2022", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", **_POV, "period": "2022", "reference_period": "2022",
    "tables": [
        # Table 4.1, first page: residence rows + the first regions
        {"page_contains": ["table 4.1 summary of national, urban, rural, nomad"],
         "exact_numbers": True, "columns": _COLS41, "rows": _res_rows(total=False)},
        {"page_contains": ["table 4.1 summary of national, urban, rural, nomad"],
         "join_wrapped_labels": True, "columns": _COLS41,
         "row_scan": {"expect_rows": 8, **_REGION_SCAN}},
        # Table 4.1, continued (no caption on the page) + its Total row
        {"page_contains": ["4.2. depth of overall poverty (poverty gap)"],
         "join_wrapped_labels": True, "columns": _COLS41,
         "row_scan": {"expect_rows": 9, **_REGION_SCAN}},
        {"page_contains": ["4.2. depth of overall poverty (poverty gap)"],
         "exact_numbers": True, "columns": _COLS41,
         "rows": [{"match": r"^Total(?=\s+\d+\.\d\s+100\.0\s)"}]},
        # Table 4.2: the gap only
        {"page_contains": ["table 4.2 poverty incidence, by residence"],
         "start": r"^Place of Residence", "take": "leading",
         "columns": [{"skip": True}, {"skip": True}, {"metric": "gap"}],
         "rows": _res_rows()},
        _t51("Rural", _RES["Rural"]), _t51("Urban", _RES["Urban"]),
        _t51("Nomadic", _RES["Nomadic"]), _t51("Total", {}),
        # Table 5.2: marital status of the head x sex of the head
        {"page_contains": ["table 5.2 poverty and marital status of household head"],
         "start": r"^Marital status Total", "exact_numbers": True,
         "columns": [{"metric": "headcount"}, {"metric": "headcount", "sex": "male"},
                     {"metric": "headcount", "sex": "female"}],
         "rows": label_rows("marital_status_of_head",
                            ["Married", "Divorced", "Never married", "Widowed"])},
    ],
}

parse = make_parser(LAYOUT)
