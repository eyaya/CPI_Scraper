"""South Africa — QLFS employment composition.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `excel_wide_labour.make_parser`; the comments beside it
record what each sheet actually contains and the published figures used to
prove the layout still holds.

Stats SA's QLFS Trends workbook is the deepest labour source on the continent:
74 quarters from 2008 Q1, every table repeated for Both sexes / Women / Men.

WHAT THE CLASSIFICATION COLUMN IS FOR, IN ONE SHEET PAIR. Stats SA publishes
status in employment TWICE:

    Table3.6   Employed by sex and status in employment            (ICSE-93)
    Table3.6b  ... status in employment 20th ICLS (ICSE-18)        (ICSE-18)

Same country, same quarter, same people, two international standards and
different category sets. Collected without the scheme attached they would look
like contradictory duplicates; with it they are what they are -- the old basis
and the new one, both published, both kept.

INDUSTRY IS A NATIONAL SCHEME, NOT ISIC. The ten groups Stats SA prints
(Agriculture, Mining, Manufacturing, Utilities, Construction, Trade, Transport,
Finance, Community and social services, Private households) are its own
aggregation. "Trade" here is not ISIC Rev.4's "Wholesale and retail trade"
section, and labelling it ISIC would invite exactly the join that misleads.

LEVELS ARE IN THOUSANDS, as the workbook's own second header row says, and are
emitted as `thousand_persons` rather than multiplied out -- multiplying is
recomputation, and 14,437.74 thousand is not an error.

CROSS-CHECK (2008 Q1, Both sexes, thousands): total employed 14,437.740;
Agriculture 838.059; Manufacturing 2,111.300; Trade 3,318.579; Private
households 1,232.633. Women's total 6,202.059 with Agriculture 294.070.
"""
from __future__ import annotations

from .excel_wide_labour import make_parser

# The three blocks every Table 3.x repeats. Stats SA writes "Women" and "Men"
# rather than Female/Male; `_common.normalise_sex` knows both, but the mapping
# is stated here so the layout reads as the sheet does.
_SEX_BLOCKS = [
    {"match": r"^\s*Both sexes\s*$", "sex": "total"},
    {"match": r"^\s*Women\s*$", "sex": "female"},
    {"match": r"^\s*Men\s*$", "sex": "male"},
]

LAYOUT = {
    "survey": "Quarterly Labour Force Survey (QLFS)",
    "frequency": "quarterly",
    "working_age_base": "15-64",
    "decimal": ".",
    "min_periods": 4,
    # Only the sheets read below are opened. The workbook also holds the
    # headline status series (Tables 1, 2, 2.x) -- those are the `unemployment`
    # indicator's, and collecting them here too would put the same figure in
    # two places.
    "sheet_contains": ["table3."],
    "tables": [
        {"sheet": "Table3.1", "topic": "industry",
         "classification": "National",
         "unit": "thousand_persons", "blocks": _SEX_BLOCKS,
         "expect_rows": 9},
        {"sheet": "Table3.5", "topic": "occupation",
         "classification": "National",
         "unit": "thousand_persons", "blocks": _SEX_BLOCKS,
         "expect_rows": 8},
        # The two ICLS bases, kept apart by their classification rather than
        # by which sheet they came from.
        {"sheet": "Table3.6", "topic": "employment_status",
         "classification": "ICSE-93",
         "unit": "thousand_persons", "blocks": _SEX_BLOCKS,
         "expect_rows": 3},
        {"sheet": "Table3.6b", "topic": "employment_status",
         "classification": "ICSE-18",
         "unit": "thousand_persons", "blocks": _SEX_BLOCKS,
         "expect_rows": 3},
        # Table 3.10 words its blocks differently -- "Employed (Both sexes)"
        # rather than "Both sexes" -- carries two categories rather than three,
        # and then repeats the whole formal/informal split by AGE BAND below.
        # `max_blocks` stops at the three sex blocks; the age version is a
        # separate cut and is deferred rather than silently merged into them.
        {"sheet": "Table3.10", "topic": "formality",
         "classification": "Not applicable",
         "unit": "thousand_persons",
         "blocks": [
             {"match": r"^\s*Employed \(Both sexes\)", "sex": "total"},
             {"match": r"^\s*Employed \(Women\)", "sex": "female"},
             {"match": r"^\s*Employed \(Men\)", "sex": "male"},
         ],
         "max_blocks": 3,
         # Exactly two categories per block. Past them the sheet moves on to
         # formal/informal by age, education, industry and occupation -- real
         # data, but a different cut, and deferred rather than merged in.
         "max_rows_per_block": 2,
         "expect_rows": 2},
    ],
}


parse = make_parser(LAYOUT)
