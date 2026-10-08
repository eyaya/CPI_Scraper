"""Namibia — NSA 2023 Population and Housing Census, Labour Force Report.

One module per country, read by `pdf_tables_labour.make_parser`. The report is
the one `unemployment` collects (Table 0.1 there, Chapter 4 and Section 6 here).

CENSUS, NOT A SURVEY. NSA has run no labour force survey since 2018, so these
figures come from the census of 24 September 2023 and the cadence is
multi-year: a scheduled run will find nothing new for years at a time.

THE TEXT LAYER CONTAINS THE WHOLE REPORT TWICE, and that is the only real
difficulty here. The two copies sit three to five points apart with slightly
different glyph heights, so a row of one copy sometimes merges with a row of
the other and the words interleave:

    NTootta el lsewhere classified 546,82005 100.00 300,71934 100.00 ...
    EEmmppllooyyemee nt status 462,996 84.7 257,250 85.5 205,746 83.6
    OHewlpne-arc (cwoiuthnot uwto prakye)r ... 8,828 1.6 4,151 1.4 4,677 1.9

THE SECOND AND THIRD OF THOSE ARE THE DANGEROUS ONES: the label is destroyed
but the NUMBERS ARE CORRECT AND WELL FORMED, so nothing downstream would
question the row -- it would simply publish a category that does not exist.
They are excluded by their own signatures, none of which a clean row has:

    ,\\d{4,}                  two numbers fused      546,82005
    (?:([A-Za-z])\\1){3,}     doubled characters     EEmmppllooyyee
    [A-Za-z][A-Z][a-z]       interleaved case       OHewlpne, tThaebrlee

THE TWO COPIES ARE COMPLEMENTARY, which is what makes the occupation table
recoverable at all. On page 38 every row is clean EXCEPT "Skilled agricultural,
forestry and fishery workers", whose label line is swallowed by the running
header ("26Skilled agricultural, forestry and fishery 2023 POPULATION AND
HOUSING CENSUS ...") leaving its values on a line labelled only "workers". On
page 39 that row is clean and the last two rows are fused instead. Both pages
are read and the labels dedupe, so each category arrives once, from whichever
copy printed it properly; the orphan "workers" is excluded by name.

TWO LABELS ARE REJOINED BY `label_map`, where each copy printed one half of a
wrapped label and no copy printed it whole -- "Own-account worker (without
hired" + "employees)" in Table 4.12, and "Technicians and associate" +
"professionals" in Table 6.4. The full label is the report's own printed text,
taken from the line the other half sits on; nothing is invented.

CLASSIFICATIONS, only as stated:
* OCCUPATION is NASCO-96, the Namibia Standard Classification of Occupations,
  "based on the ISCO-88" -- a national scheme, so National.
* INDUSTRY: "The broad structure of the ISIC revision 4 was used to classify
  the employed population" -> ISIC Rev.4.
* STATUS IN EMPLOYMENT: the report names no standard anywhere (ICSE appears
  nowhere in it), and its categories are its own -- "Paid apprentice, intern",
  "Helper (without pay) in a family business", "Don't Know". National.

YOUTH IS 15-34, the report's own definition ("Section 6: Youth (15-34) Economic
Activity Status"), and the youth tables carry that as their age band.

ROW PERCENTAGES NOT TAKEN: Table 6.4 gives each occupation's male and female
counts with the sex split WITHIN the category (Managers 48.6% male). Only the
counts are collected, as everywhere else in this indicator. Table 6.5's
percentages are column shares (39,389 of 141,165 employed young men = 27.9%)
and are kept.

CROSS-CHECK (PHC 2023): employed 546,805 (M 300,794 / F 246,011); employees
462,996 = 84.7% (M 85.5 / F 83.6); own-account workers 50,564 = 9.2%;
agriculture, forestry and fishing 88,277 = 16.1% (M 23.1 / F 7.6); elementary
occupations 118,947 = 21.8%; armed forces 18,642 = 3.4%; employed youth
252,886, of whom 59,555 in elementary occupations and 47,515 = 18.8% in
agriculture.
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser

_SKIP = {"skip": True}


def _n(sex: str) -> dict:
    return {"sex": sex, "measure": "count", "unit": "persons"}


def _p(sex: str) -> dict:
    return {"sex": sex, "measure": "share", "unit": "percent"}


# Total | Male | Female, each as a count then a percentage.
_N_PCT = [_n("total"), _p("total"), _n("male"), _p("male"), _n("female"), _p("female")]

# Lines produced by the duplicate text layer, never by a clean row. The first
# two alternatives are the engine's own table-of-contents guards, kept because
# naming `exclude_lines` replaces them.
_ARTEFACT = (r"…|\.{4,}"
             r"|,\d{4,}"                 # 546,82005  -- two numbers fused
             r"|(?:([A-Za-z])\1){3,}"    # EEmmppllooyyee -- doubled characters
             r"|[A-Za-z][A-Z][a-z]")     # OHewlpne, tThaebrlee -- interleaved

# TWO REASONS THIS TABLE NEEDS ITS OWN LABEL PATTERN.
#
# LENGTH: NSA writes an ISIC section name out in full, and the engine's default
# stops at 80 characters -- which silently dropped "Activities of households as
# employers; undifferentiated goods- and services-producing activities of
# households for own use" (122 characters), the industry employing 43,149
# people. `expect_rows` caught it, which is exactly what it is for.
#
# PARENTHESES: the default treats "(" as the start of a value, because some
# sources print a negative or suppressed cell as "(0)". Namibia has no such
# cell, but it does have parentheses INSIDE its category names, so the default
# truncated "Employer (with hired employees)" to "Employer" and "Helper
# (without pay) in a family business" to "Helper" -- plausible-looking labels
# that are not what the report prints. Here a value starts only at a digit or a
# free-standing dash.
_LONG_LABEL = r"^([A-Za-zÀ-ſ][^\d]{2,140}?)\s+(?=\d|[-–](?:\s|$))"


LAYOUT = {
    "survey": "Population and Housing Census 2023 Labour Force Report",
    # NSA has run no LFS since 2018; this is a census round, not a cadence.
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "decimal": ".",
    # The doubled layer defeats line-by-line reading outright; word positions
    # keep each copy's rows intact so the clean one can be recognised.
    "text_mode": "words",
    "period_patterns": [r"(20\d{2}) POPULATION AND HOUSING CENSUS"],
    "tables": [
        {
            "caption": r"Table 4\.4:\s*Number and Percentage Distribution of Employed Population by Occupation",
            "topic": "occupation", "classification": "National",
            "columns": _N_PCT, "dash_placeholder": True,
            "series_code": "PHC2023 T4.4",
            "row_scan": {
                "exclude_lines": _ARTEFACT,
                # The orphan left when the running header swallows the
                # "Skilled agricultural..." label on page 38; page 39 prints
                # that row properly.
                "exclude_labels": ["workers"],
                "expect_rows": 12,
            },
        },
        {
            "caption": r"Table 4\.6:\s*Number and Percentage Distribution of Employed Population by Industry",
            "topic": "industry", "classification": "ISIC Rev.4",
            "columns": _N_PCT, "dash_placeholder": True,
            "series_code": "PHC2023 T4.6",
            "row_scan": {"exclude_lines": _ARTEFACT, "expect_rows": 23},
        },
        {
            "caption": r"Table 4\.12:\s*Number and Percentage Distribution of the employed population by status",
            "topic": "employment_status", "classification": "National",
            "columns": _N_PCT, "dash_placeholder": True,
            "series_code": "PHC2023 T4.12",
            "label_map": {
                "Own-account worker (without hired":
                    "Own-account worker (without hired employees)",
            },
            "row_scan": {
                "exclude_lines": _ARTEFACT,
                # The other half of that wrapped label, printed by the other copy.
                "exclude_labels": ["employees)"],
                "expect_rows": 7,
            },
        },
        {
            "caption": r"Table 6\.4:\s*Number and Percentage Distribution of Employed youth by Occupation",
            "topic": "occupation", "classification": "National",
            # Total | Male count and row % | Female count and row %.
            "columns": [_n("total"), _n("male"), _SKIP, _n("female"), _SKIP],
            "age_group": "15-34", "dash_placeholder": True,
            "series_code": "PHC2023 T6.4",
            "label_map": {"professionals": "Technicians and associate professionals"},
            "row_scan": {"exclude_lines": _ARTEFACT, "expect_rows": 12},
        },
        {
            "caption": r"Table 6\.5:\s*Number and Percentage Distribution of Employed youth by Industry",
            "topic": "industry", "classification": "ISIC Rev.4",
            "columns": _N_PCT, "age_group": "15-34", "dash_placeholder": True,
            "series_code": "PHC2023 T6.5",
            "row_scan": {"exclude_lines": _ARTEFACT, "expect_rows": 23},
        },
    ],
}


# Applied to every table here rather than repeated in each: NSA's category
# names run long, and each table ends on its own Total row followed by
# commentary that a 140-character label pattern could otherwise match
# ("percent of the total employed population. In urban areas, males dominated
# the sector with 11.8 percent" is a well-formed-looking row of numbers).
for _table in LAYOUT["tables"]:
    _table.setdefault("end_after", r"^Total\s+[\d(-]")
    _table["row_scan"].setdefault("label", _LONG_LABEL)


parse = make_parser(LAYOUT)
