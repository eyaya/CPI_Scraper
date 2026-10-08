"""Somalia — SNBS Somali Labour Force Survey 2019, employment composition.

One module per country, read by `pdf_tables_labour.make_parser`. The report is
the one `unemployment` collects (Table 1.1 there, Tables 4.3-4.7 here).

COVERAGE CAVEAT, MATERIAL AND PERMANENT: the survey EXCLUDES the nomadic and
pastoralist population and non-liberated areas. These are not national
estimates in the sense the other countries' are, and any cross-country use has
to carry that. It is also ONE ROUND, seven years old, with no repeat announced.

THE CATEGORY LABELS ARE TRUNCATED IN THE REPORT ITSELF, and that is the
distinctive thing about this source. SNBS's table export clips every label at
about 38 characters, mid-word:

    Production and specialized services ma      26,327.64   2.6
    Technicians and assoc                       20,254      2.8
    Market-oriented skilled forestry, fish       3,339.96    0.3

They are collected exactly as printed. Completing them ("...managers",
"...associate professionals") would be writing text the NSO did not publish,
and guessing which ISCO group a clipped string denotes is precisely the
inference this collector refuses. A reader can see the truncation and decide;
a silently "helpful" repair would hide it.

NO SCHEME IS RECORDED, and the reasoning matters because this is the closest
call in the indicator so far. ISIC and ISCO DO appear in the report -- in the
abbreviation list, and defined generically in the back glossary ("ISCO is a
tool for organizing jobs into a clearly defined set of groups...") -- but
NOWHERE against a table, and no revision is ever given. The evidence that they
were used is strong: Table 4.4's branches are ISIC Rev.4's twenty-one sections
verbatim, and 4.5/4.6 are ISCO-08 sub-major and major groups. But a glossary
entry is not a statement that a particular table was classified on that
standard, so these rows say National, as Botswana's and Tanzania's do. The
evidence is written down here so the call can be revisited deliberately rather
than rediscovered.

FOUR CUTS, AND ONE DELIBERATE OMISSION:

    4.3  broad economic sector      Agriculture / Industry / Service
    4.4  branch of economic activity  22 branches (ISIC Rev.4's sections)
    4.5  occupation, detailed       42 groups, total only
    4.6  occupation, major groups   9 groups, by sex (no "both sexes" column)
    4.7  unit of production         informal / formal / households

Table 4.3's "Total" is NOT collected. It is the same 955,820 persons as Table
4.4's Total under the same topic, category and measure -- one merge key, two
rows -- so 4.4's is kept and 4.3's dropped. Everything else in 4.3 is a
different category from anything in 4.4 ("Industry" against "Manufacturing"),
so the two coexist.

COUNTS CARRY DECIMALS in Table 4.5 (35,068.01 persons) because SNBS published
weighted estimates unrounded. They are emitted as printed rather than rounded.

THE REPORT'S OWN TOTALS DO NOT AGREE ACROSS TABLES, and both are kept as
published. Industry (4.4) and unit of production (4.7) total 955,820 employed
persons -- the same figure the `unemployment` indicator collects from Table 1.1
-- while the occupation tables total 1,028,709 (4.5, and 4.6's 710,930 male +
317,779 female, which reconcile to it exactly). The 72,889 difference is SNBS's
own and is not reconciled here: adjusting either side would publish a figure
the report does not contain. Anyone summing across topics needs to know it.

PERIOD IS PINNED TO 2019 and must stay pinned: the published file is named
"Labour-Force-Survey-Reports-2021.pdf" but is the 2019 survey, released in
September 2021. There is exactly one Somali LFS.

CROSS-CHECK (2019): employed 955,820; services 572,135 = 59.9%; industry
171,965 = 18.0%; agriculture 128,941 = 13.5%; other service activities 169,773
= 17.8%; "Other (specify)" occupations 277,969.17 = 27.0%; teaching
professionals 77,836.35 = 7.6%; elementary occupations 268,960 male (37.8%)
against 149,746 female (47.1%); informal sector 491,100 = 51.4%.
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser

_N_PCT = [{"sex": "total", "measure": "count", "unit": "persons"},
          {"sex": "total", "measure": "share", "unit": "percent"}]
# Table 4.6 gives Male then Female, each as a count and a percentage, and
# publishes no "both sexes" column at all.
_BY_SEX = [{"sex": "male", "measure": "count", "unit": "persons"},
           {"sex": "male", "measure": "share", "unit": "percent"},
           {"sex": "female", "measure": "count", "unit": "persons"},
           {"sex": "female", "measure": "share", "unit": "percent"}]

# A value starts at a digit or a free-standing dash, never at "(" -- otherwise
# the occupation residual "Other (specify) 277,969.17 27.0" is read as the
# category "Other", which is not what the report prints.
_LABEL = r"^([A-Za-zÀ-ſ][^\d]{2,140}?)\s+(?=\d|[-–](?:\s|$))"


def _table(caption: str, topic: str, columns: list, expect: int, code: str,
           classification: str = "National", **scan) -> dict:
    return {
        "caption": caption, "topic": topic, "classification": classification,
        "columns": columns, "dash_placeholder": True, "series_code": code,
        "row_scan": {"label": _LABEL, "expect_rows": expect, **scan},
    }


LAYOUT = {
    "survey": "Somali Labour Force Survey 2019",
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "decimal": ".",
    "text_mode": "words",
    # NOT read from the filename: the file says 2021, the survey is 2019.
    "period": "2019",
    "reference_period": "SLFS 2019",
    "tables": [
        _table(r"Table 4\.3:\s*Share of workforce by broad branch of economic activity",
               "industry", _N_PCT, 4, "SLFS T4.3",
               # Its Total is Table 4.4's Total: same key, same 955,820.
               exclude_labels=["Total"]),
        _table(r"Table 4\.4:\s*Employed persons by branch of economic activity",
               "industry", _N_PCT, 23, "SLFS T4.4"),
        _table(r"Table 4\.5:\s*Employed persons by occupation in main job",
               "occupation", _N_PCT, 43, "SLFS T4.5"),
        _table(r"Table 4\.6:\s*Employed persons by occupation in main job and sex",
               "occupation", _BY_SEX, 10, "SLFS T4.6"),
        _table(r"Table 4\.7:\s*Formal and informal sector employment",
               "formality", _N_PCT, 4, "SLFS T4.7",
               classification="Not applicable"),
    ],
}

# Each table ends on its own Total row and is followed by commentary that
# quotes its figures -- the Botswana trap.
for _table_spec in LAYOUT["tables"]:
    _table_spec.setdefault("end_after", r"^Total\s+[\d(-]")


parse = make_parser(LAYOUT)
