"""Ethiopia — ESS Labour Force and Migration Survey 2021, key findings.

One module per country, read by `pdf_tables_labour.make_parser`. The report is
the one `unemployment` collects (Summary Table 3 there, Summary Table 2 here).

FOUR SURVEY ROUNDS IN ONE TABLE. Summary Table 2 sets occupation, industry and
status side by side for March 1999, March 2005, June 2013 and February 2021,
each by Total / Male / Female -- twelve numeric columns per row, and the only
four-round back-series in this indicator outside South Africa's QLFS.

WORKING-AGE BASE IS 10+, not 15+. ESS says so in its own caption ("Age 10 years
and above"), and an Ethiopian share is not comparable with a 15+ one without
saying so, which is why the base travels on every row.

THE COLUMN HEADER IS SHARED BY THREE STACKED BLOCKS. "Mar-99 Mar-05 Jun-13
Feb-21" is printed once, above all three, so each block reads it from the page
rather than from its own region (`period_header_scope: "page"`), and
`period_map` states what those labels mean rather than leaving a parser to
invent a century for "99".

NO CLASSIFICATION IS NAMED ANYWHERE IN THE REPORT -- ISIC, ISCO and ICSE do not
appear in it. The occupation groups read like ISCO-08's, but the industry list
is ESS's own coarse grouping ("Manufacturing, Mining, Quarrying &
Constriction.", "Other Service Sectors *") and the status categories are
national ("Unpaid Family Workers", "Member of Small & Micro enterprise"). All
National.

FOUR LABELS ARE REPAIRED BY `label_map`, and this is the one place in this
layout where care is needed. Two pairs of categories are printed so close
together that the reader attaches the head of the next category to the row
above:

    Whole sale & Retail Trade Other Service   5.9 2.2 3.7 ...   <- Wholesale's values
    Sectors *                                 9.1 3.5 5.6 ...   <- Other Service Sectors'
    Accommodation and Arts, entertainment Agriculture,  - - - ... 1.0 0.5 1.6
    Hunting, Forestry and Fishing             79.6 48.6 31 ...  <- Agriculture's

THE VALUES ARE CORRECT IN EVERY CASE -- each row carries the figures the report
prints for it, verified against the plain text rendering -- so only the labels
are restored, to exactly what the report prints. Nothing is inferred from
magnitude.

THE STATUS BLOCK SPANS A PAGE BREAK and the continuation carries no caption of
its own, only the repeated "Key Indicators Mar-99 ..." header. It is therefore
a second table spec, bounded so that the mean-wage, literacy, disability and
youth-unemployment sections below it -- which belong to `unemployment`, not
here -- cannot be swept in.

ONE ROW IS DELIBERATELY LOST. "Member of Small & Micro enterprise" prints nine
cells where the table has twelve, with no way to tell which rounds the three
figures belong to; it is skipped rather than aligned by guesswork. That is why
the status blocks expect 3 and 6 categories rather than 3 and 7.

TIGRAY IS EXCLUDED from the 2021 round -- a coverage gap in the source that any
2021 national figure carries. See the descriptor.

CROSS-CHECK (Feb-21, Total / Male / Female): skilled agricultural, forestry and
fishery workers 51.1 / 58.3 / 41.3; elementary occupations 28.0 / 22.6 / 35.5;
agriculture, hunting, forestry and fishing 64.9 / 71.6 / 55.7; other service
sectors 24.0 / 17.7 / 32.4; self-employed 49.6 / 54.4 / 43.2; unpaid family
workers 36.7 / 30.4 / 45.3. Mar-99 anchors: elementary occupations 41.9;
agriculture 79.6; unpaid family workers 47.
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser

# Total | Male | Female for each of the four rounds, in printed order.
_COLS = [{"sex": sex, "measure": "share", "unit": "percent", "period_index": i}
         for i in range(4)
         for sex in ("total", "male", "female")]

_HEADER = r"(?:Mar|Jun|Feb|Jan|Apr|May|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}"
_PERIOD_MAP = {"Mar-99": "1999", "Mar-05": "2005",
               "Jun-13": "2013", "Feb-21": "2021"}
# The three blocks are stacked with no rule between them, so each one's region
# ends where the next block's heading begins.
_BLOCK_END = r"^\s*(?:Percentage Distribution of Employed Population|Paid Employee|Table|Summary Table)"


def _block(caption: str, topic: str, expect: int, code: str, **extra) -> dict:
    return {
        "caption": caption, "end": _BLOCK_END,
        "topic": topic, "classification": "National",
        "columns": _COLS,
        "period_header": _HEADER, "period_count": 4,
        "period_map": _PERIOD_MAP, "period_header_scope": "page",
        "dash_placeholder": True, "series_code": code,
        "row_scan": {"expect_rows": expect},
        **extra,
    }


LAYOUT = {
    "survey": "Labour Force and Migration Survey (LMS)",
    # National rounds roughly every 8-12 years: 1999, 2005, 2013, 2021.
    "frequency": "ad_hoc",
    "working_age_base": "10+",
    "decimal": ".",
    "text_mode": "words",
    "period_patterns": [r"(20\d{2}) LABOUR FORCE AND MIGRATION SURVEY"],
    "tables": [
        _block(r"Percentage Distribution of Employed Population by Occupational Groups",
               "occupation", 10, "LMS ST2-occupation"),
        _block(r"Percentage Distribution of Employed Population by Industrial Divisions",
               "industry", 8, "LMS ST2-industry",
               label_map={
                   # Each row's VALUES are its own; only the run-on labels are
                   # restored to what the report prints.
                   "Whole sale & Retail Trade Other Service": "Whole sale & Retail Trade",
                   "Sectors *": "Other Service Sectors",
                   "Accommodation and Arts, entertainment Agriculture":
                       "Accommodation and Arts, entertainment",
                   "Hunting, Forestry and Fishing": "Agriculture, Hunting, Forestry and Fishing",
               }),
        _block(r"Percentage Distribution of Employed Population by Employment Status",
               "employment_status", 3, "LMS ST2-status"),
        # The continuation overleaf, under the repeated header and bounded
        # before the mean-wage and unemployment sections.
        _block(r"Key Indicators\s+Mar-99", "employment_status", 6,
               "LMS ST2-status-cont", end=r"^\s*Paid Employee"),
    ],
}


parse = make_parser(LAYOUT)
