"""Eswatini — CSO Integrated Labour Force Survey 2023, key findings booklet.

One module per country, read by `pdf_tables_labour.make_parser`. The booklet is
the one `unemployment` collects (Tables 6.7 and 6.25 there, Chapters 4 and 5
here).

EVERY VALUE IS A PERCENTAGE. The booklet publishes counts only as a base line
above each table ("Employed population 131 586 128 770 260 356"), and that line
is not collected: it is an employment LEVEL, which belongs to `unemployment`.
It is also written with SPACE thousands separators, so it reads as six numbers
rather than three and is skipped by the column count anyway.

NO CLASSIFICATION IS NAMED ANYWHERE IN THE BOOKLET -- ISIC, ISCO and ICSE do
not appear in it at all. The occupation groups read like ISCO-08's and the
economic-activity groups like ISIC Rev.4's sections, but saying so would be
inference published as fact, so both are National.

WHAT IS AND IS NOT COLLECTED FROM CHAPTER 5. Tables 5.1, 5.3 and 5.4 break the
INFORMALLY EMPLOYED down by unit of production, occupation and economic
activity -- formality crossed with a second category, which this schema cannot
hold in one row. Table 5.2 distributes the informally employed ACROSS regions
while 5.5 gives informal employment as a PROPORTION OF employment WITHIN each
region; both would land on the same merge key, so 5.5 is taken (the
interpretable one) and 5.2 is left.

TWO SHAPES THE WORD-POSITION READER HAS TO HANDLE HERE:

* THE COLUMN STUB MERGES INTO THE FIRST DATA ROW -- "Unit of Production
  Employment in Informal Sector 46.5 ...", "Occupation Managers 5.8 ...". The
  stub is stripped as a block marker, which is the same machinery Botswana uses
  for its sex blocks.
* A LOWER-CASE CONTINUATION LINE. "Electricity, gas, steam and air conditioning
  1.1 0.4 0.7" / "supply" / "Water supply; ..." -- giving "supply" to the row
  below balances both rows perfectly and is wrong. That is why the engine now
  treats a lower-case fragment as strong evidence of continuing the row above
  rather than as a tie-break.

REGIONS COME FROM THE ROW LABEL in Table 5.5 (`label_is_geography`), with "All
regions" mapped to the schema's "Total country".

CADENCE IS TRIENNIAL and the booklet gives no fieldwork dates -- only "a
specified brief period of one week" -- so the period is pinned to 2023 rather
than guessed, exactly as the `unemployment` descriptor does.

CROSS-CHECK (ILFS 2023, Male / Female / Both sexes): service and sales workers
18.4 / 32.3 / 25.3; elementary occupations 18.4 / 24.4 / 21.3; manufacturing
14.5 / 18.7 / 16.6; wholesale and retail trade 14.5 / 21.4 / 17.9; employment
in the informal sector 46.5 / 46.2 / 46.3; informal employment in Manzini
62.3 / 60.6 / 61.4 and nationally 53.6 / 58.9 / 56.2.
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser

# Male | Female | Both sexes, every cell a percentage.
_SHARE = [{"sex": s, "measure": "share", "unit": "percent"}
          for s in ("male", "female", "total")]

# CSO writes a category out in full ("Activities of households as employers
# undifferentiated goods and services-producing act" is 87 characters), past
# the engine's 80-character default.
_LABEL = r"^([A-Za-zÀ-ſ][^\d]{2,140}?)\s+(?=\d|[-–](?:\s|$))"


def _stub(*words: str) -> list[dict]:
    """Strip the table's column-stub header off its first data row."""
    return [{"match": rf"^(?:{'|'.join(words)})\s+(?=[A-Za-z])", "name": ""}]


LAYOUT = {
    "survey": "Integrated Labour Force Survey 2023",
    # Sixth round since 2007; the booklet dates no fieldwork.
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "decimal": ".",
    "text_mode": "words",
    "period": "2023",
    "reference_period": "ILFS 2023",
    "tables": [
        {
            "caption": r"Table 4\.1:\s*Percentage distribution of employed population by sex and unit of production",
            "topic": "formality", "classification": "Not applicable",
            "columns": _SHARE, "blocks": _stub("Unit of Production"),
            "series_code": "ILFS2023 T4.1",
            "row_scan": {"expect_rows": 4},
        },
        {
            "caption": r"Table 4\.\s*5:\s*Percentage distribution of employed population by occupation",
            "topic": "occupation", "classification": "National",
            "columns": _SHARE, "blocks": _stub("Occupation"),
            "series_code": "ILFS2023 T4.5",
            "row_scan": {"expect_rows": 12},
        },
        {
            "caption": r"Table 4\.6:\s*Percentage distribution of employed population by sex and economic activity",
            "topic": "industry", "classification": "National",
            "columns": _SHARE, "blocks": _stub("Economic activity"),
            "series_code": "ILFS2023 T4.6",
            "row_scan": {"expect_rows": 23},
        },
        {
            "caption": r"Table 5\.5:\s*Proportion of informal employment by region",
            "topic": "formality", "classification": "Not applicable",
            "columns": [{**c, "characteristic": "Informal employment"} for c in _SHARE],
            "label_is_geography": True,
            "geography_map": {"All regions": "Total country"},
            "series_code": "ILFS2023 T5.5",
            "row_scan": {"expect_rows": 5},
        },
    ],
}

# Every table ends on its own "All ..." row, and the long label pattern would
# otherwise be free to match the prose that follows one.
for _table in LAYOUT["tables"]:
    _table.setdefault("end_after", r"^All\s+\w+\s+[\d(-]")
    _table["row_scan"].setdefault("label", _LABEL)


parse = make_parser(LAYOUT)
