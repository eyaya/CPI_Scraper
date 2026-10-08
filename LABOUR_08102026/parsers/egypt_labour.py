"""Egypt — CAPMAS quarterly Labour Force Survey bulletin, employment composition.

One module per country, read by `pdf_tables_labour.make_parser`. The bulletin is
the one `unemployment` collects (its headline rates; Tables 16 and 17 here).

THIS IS THE FIRST TRANSPOSED SOURCE IN THE INDICATOR. Everywhere else a row is
a category and the columns are sexes or periods. CAPMAS lays its tables out the
other way: each COLUMN is an occupation or an economic activity, and each ROW is
a Male / Female / Total line. So the categories are named by the layout (from
the header cells, transcribed below) and the sex comes from the row label,
via `label_is_sex`.

AND IT IS PRINTED RIGHT TO LEFT, so the columns run in REVERSE order: the
economic-activity table starts at Financial and insurance and ends at
Agriculture, forestry and fishing. That order was NOT inferred from the values
looking plausible -- it was established from the page's geometry, by matching
each numeric column's x-centre to the header cell above it. The arithmetic then
confirms it: the male row sums to 83.7 on page 58 and 16.3 on its continuation,
which is 100.0 exactly, and female and total do the same.

WHAT IS COLLECTED, and only from the NATIONAL block:

    Table (16)  occupation, 9 groups          page 56
    Table (17)  economic activity, 21 sections  pages 58 + 59 (continued)

Each table also breaks every category down by geographical region, in blocks of
three rows (Male / Female / Total). Those are NOT taken yet: the region's name
is printed once per block, vertically centred, so it lands on the MIDDLE row in
reading order on some tables and the FIRST row on others -- and attributing a
region wrongly is silent corruption of exactly the kind this collector exists to
avoid. Each region scope therefore stops at its first "Total" row, which is the
national block. The regional detail is a known, deliberate omission.

TABLE (13), EMPLOYMENT STATUS, IS NOT COLLECTED AT ALL. Two of its four column
headers cannot be read from the page -- they come out as "Contributing
activity" and "Employed" with no way to tell which status each denotes -- and
naming a category by guesswork is worse than not publishing it. The values are
there; the labels are not.

CLASSIFICATIONS ARE NATIONAL, and CAPMAS says why in its own methodology: it
uses "the occupational classification of 2017 ... derived from the ...
International Standard Classification of Occupation (ISCO)" and "the Industry
Classification of 2021 ... derived from the International Standard Industry
Classification (ISIC) - Revision Four". Those are Egyptian classifications
derived from the international ones, exactly as Tanzania's TASCO and Namibia's
NASCO-96 are, and are recorded the same way.

CAPMAS'S OWN SPELLINGS ARE PRESERVED -- "proficinals", "agricltural",
"activites", "servics", "retailtrade", "gaz", "airconditioning",
"adminstration", "Adminstratve", "undifferentiatid" -- as Ethiopia's
"Constriction." is. The one place the text is corrected is "waste", which the
text layer splits mid-word as "wast e"; that is an extraction artefact, not
something a reader of the bulletin would see.

CROSS-CHECK (April-June 2026, Male / Female / Total): craft and related trades
21.3 / 2.6 / ...; service and shop sales workers 19.7 / 19.9 / ...; agriculture
17.2 / 24.3 / 18.6; wholesale and retail trade 17.2 / 17.3 / 17.2;
manufacturing 14.7 / 8.8 / 13.5; construction 14.7 / 0.4 / 11.9. Each sex's 21
activity shares sum to 100.0 across the two pages.
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser

_SKIP = {"skip": True}


def _cat(name: str) -> dict:
    """One category column; the sex comes from the row label."""
    return {"characteristic": name, "measure": "share", "unit": "percent"}


# Table (16), in printed (right-to-left) order.
_OCCUPATIONS = [
    "Ordinary job works",
    "Plant and machine operators and assemblers",
    "Craft and related trades workers",
    "Skilled agricltural and fishery workers",
    "Service workers and shop and market sales workers",
    "Clerks",
    "Technicians and associate professionals",
    "proficinals",
    "Legislators, senior officials and managers",
]

# Table (17) page 58: no sample-size columns on this page.
_ACTIVITIES_1 = [
    "Financial and insurance activites",
    "Information and communication",
    "Accommodation and food servics activities",
    "Transportation and storage",
    "Wholesale and retailtrade, repair of motor vehicles and motorcycles",
    "Construction",
    "Water supply,sewerage,waste management and remediation activities",
    "Electricity, gaz,steam and airconditioning supply",
    "Manufacturing",
    "Mining and quarrying",
    "Agriculture, forestry and fishing",
]

# Table (17) continued on page 59, behind a Column-% and a sample-size column.
_ACTIVITIES_2 = [
    "Activities of extraterritorial organizations and bodies",
    "Activities of households as employers undifferentiatid goods and services",
    "Other service activities",
    "Arts, entertainment and recreation",
    "Human health and social work activities",
    "Education",
    "Public adminstration and defence compulsory social security",
    "Adminstratve and support service activities",
    "Professional scientific and technical activities",
    "Real estate- activities",
]


def _table(caption: str, topic: str, columns: list, code: str, **extra) -> dict:
    return {
        "caption": caption, "topic": topic, "classification": "National",
        "columns": columns, "label_is_sex": True,
        # Stop at the national block's own "Total" row: everything after it is
        # the regional breakdown, whose block labels are not safely placed.
        "end_after": r"^Total\s+[\d(-]",
        "dash_placeholder": True, "series_code": code,
        # THE MALE ROW'S LABEL SITS ON A LINE OF ITS OWN. `extract_text` emits
        # "Male" alone and its twelve figures on the next line, while the
        # Female and Total rows keep label and figures together. Folding a
        # digit-free line onto the numbers-only line beneath it is exactly what
        # `join_wrapped_labels` does, so it is left ON (the default in line
        # mode); switching it off silently dropped that row, which is how this
        # layout first failed.
        "row_scan": {"expect_rows": 3},
        **extra,
    }


LAYOUT = {
    "survey": "Labour Force Survey quarterly bulletin",
    "frequency": "quarterly",
    "working_age_base": "15+",
    "decimal": ".",
    # READ AS LINES, NOT WORD POSITIONS -- and the distinction matters here.
    # Word geometry is what established the column ORDER above (each numeric
    # column's x-centre matched to the header cell over it), but the ROWS must
    # not be rebuilt that way: at this bulletin's nine-point row spacing the
    # Latin label and its own digits sit on slightly different baselines, so
    # clustering put them in different rows and shifted every label one row
    # down the table -- the national block arriving unlabelled while "Male"
    # landed on the next region's figures. `extract_text` keeps
    # "Male 100 17318 ..." on one line, which is what the scanner needs.
    #
    # The Arabic sits after the values and carries no Latin digits, so it never
    # reaches the number parser.
    # "Bulletinof Labour Force ( April -June) 2026" -> 2026-Q2.
    "period_patterns": [r"Labour Force\s*\(\s*([A-Za-z]+\s*-\s*[A-Za-z]+\)\s*20\d{2})"],
    "tables": [
        _table(r"Table No\.\s*\(16\)", "occupation",
               [_SKIP, _SKIP, _SKIP] + [_cat(c) for c in _OCCUPATIONS],
               "LFS T16"),
        _table(r"Table No\.\s*\(17\)", "industry",
               [_cat(c) for c in _ACTIVITIES_1], "LFS T17a",
               # The continuation page repeats this caption behind "Cont.".
               page_excludes=["cont.table no"]),
        _table(r"Cont\.Table No\.\s*\(17\)", "industry",
               [_SKIP, _SKIP] + [_cat(c) for c in _ACTIVITIES_2], "LFS T17b"),
    ],
}


parse = make_parser(LAYOUT)
