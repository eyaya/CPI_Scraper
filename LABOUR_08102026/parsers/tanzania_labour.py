"""Tanzania — NBS Integrated Labour Force Survey key indicators, employment composition.

One module per country, read by `pdf_tables_labour.make_parser`. The report is
the one `unemployment` collects; this layout opens Tables 3.3-3.5.

THREE GEOGRAPHIES IN EVERY TABLE: TZM (Tanzania Mainland), ZNZ (Zanzibar) and
URT (United Republic of Tanzania, emitted as "Total country"), each by
M / F / T -- the same naming `unemployment` uses for this report. All three are
published; none is derived.

WHY `text_mode: "words"`. These tables wrap their category labels over up to
five lines, put the numbers on whichever line is vertically central, and
capitalise continuation lines ("Water Supply, Sewerage," / "Waste Management
and 0.2 ..." / "Remediation Activities"). A line-by-line reader cannot tell
whose label "Fishing" is. Rebuilding rows from word positions can.

CLASSIFICATIONS, only as stated:
* OCCUPATION is TASCO, the Tanzania Standard Classification of Occupations,
  "domesticated from ISCO-08" -- a national scheme with ISCO-88-style group
  names (Clerks; Service workers and shop sales workers). National.
* INDUSTRY: the report does not name its scheme. National.
* STATUS IN EMPLOYMENT: the six categories are ICSE-18's (the report lists
  them), but it does not say which hierarchy. ICSE-18.

ALL VALUES ARE COLUMN PERCENTAGES; the report publishes no counts for these.

TABLE 3.5 CARRIES TWO YEARS (2024 and 2025), each dated from its own header.

CROSS-CHECK (ILFS 2025, URT): dependent contractors 51.5% (M 54.6 / F 48.1);
contributing family workers 20.4% (F 26.8); agriculture, forestry and fishing
54.4%; skilled agricultural and fishery workers 51.6% (52.9% in 2024).
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser

_GEOS = ("Tanzania Mainland", "Zanzibar", "Total country")


def _cols(**kw) -> list[dict]:
    return [{"geography": g, "sex": s, "measure": "share", "unit": "percent", **kw}
            for g in _GEOS for s in ("male", "female", "total")]


LAYOUT = {
    "survey": "Integrated Labour Force Survey (ILFS)",
    "frequency": "annual",
    "working_age_base": "15+",
    "decimal": ".",
    "text_mode": "words",
    "period_patterns": [r"INTEGRATED LABOUR FORCE SURVEY,?\s*(20\d{2})"],
    "tables": [
        {
            "caption": r"Table 3\.3\s*:",
            "topic": "employment_status", "classification": "ICSE-18",
            "columns": _cols(), "dash_placeholder": True,
            "series_code": "ILFS T3.3",
            "row_scan": {"expect_rows": 7},
        },
        {
            "caption": r"Table 3\.4\s*:",
            "topic": "industry", "classification": "National",
            "columns": _cols(), "dash_placeholder": True,
            "series_code": "ILFS T3.4",
            "row_scan": {"expect_rows": 20},
        },
        {
            "caption": r"Table 3\.5\s*:",
            "topic": "occupation", "classification": "National",
            "period_header": r"\b20\d{2}\b", "period_count": 2,
            "columns": _cols(period_index=0) + _cols(period_index=1),
            "dash_placeholder": True, "series_code": "ILFS T3.5",
            "row_scan": {"expect_rows": 10},
        },
    ],
}


parse = make_parser(LAYOUT)
