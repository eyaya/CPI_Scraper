"""Mauritius — Statistics Mauritius CMPHS labour workbook, employment composition.

One module per country. The workbook is the one `unemployment` collects (its
headline rates; Tables 1, 3, 4 and 5 here).

WHY THIS IS BESPOKE RATHER THAN `excel_wide_labour`. That engine reads the
shape every other workbook here has -- periods ACROSS the columns, categories
DOWN the rows. Statistics Mauritius publishes the transpose: each sheet is a
block per sex, and within a block one ROW per quarter, with the categories
running across the columns.

    Table 3: Employment by industry
                 Total employed  Primary  Secondary  Tertiary   Manufacturing  ...
                      (000s)       (%)       (%)        (%)          (%)
    Both sexes                                                                  <- block
      2025 Q1         547.6        4.9      19.5       75.6         10.3
      ...
      2026 Q1         553.7        4.7      18.2       77.1          9.6
      % change ...                                                              <- derived
    Male                                                                        <- block
      2025 Q1         314.8        6.8      26.3       66.9         10.7

So the sex comes from the block header, the period from the row label, and the
category from the column -- and the columns are named here, from the sheet's
own two-row header.

FIVE QUARTERS PER ISSUE, AND THEY ACCUMULATE. Each release carries the last
five quarters, so a run collects 2025 Q1 through 2026 Q1 at once and the merge
keeps earlier quarters as issues roll forward. Revisions propagate: a quarter
restated in a later issue overwrites the earlier reading, which is the point of
merging on the key rather than appending.

WORKING-AGE BASE IS 16+, not 15+. Statistics Mauritius surveys the population
aged 16 and over ("Population aged 16 years"), and comparing a Mauritian share
against a 15+ one without saying so is a real error.

CLASSIFICATIONS, EXACTLY AS THE SHEETS STATE THEM:

* OCCUPATION is ISCO-08 -- Table 4's header says so outright ("ISCO-08"), and
  the categories carry their major-group numbers ("Managers, Professionals,
  Technicians ... 1,2,3"). Recorded as ISCO-08.
* INDUSTRY is NSIC, whose footnote reads "National version of ..." -- a
  Mauritian classification with ISIC-style section letters (C, F, G, H - U).
  National, on the same reasoning as Tanzania's TASCO.
* STATUS IN EMPLOYMENT names no standard: employees, employers, own account
  workers, contributing family workers. National.

WHAT IS DELIBERATELY LEFT:

* The "% change, latest quarter on previous quarter / same quarter a year ago"
  rows. They are derived from the levels above them, not separate observations.
* Table 1's population, unemployed and economically active/inactive columns --
  labour-force levels, which belong to `unemployment`, not to composition.
* Table 5's "Total hours worked (000s)" and "Average number of hours". The
  schema's units are persons, thousand_persons and percent; there is no hours
  unit, and inventing one to carry 38.1 would be worse than omitting it. The
  four "% having worked for" bands ARE collected, as the `hours` topic.
* Tables 6-9 (unemployed by education, age, work experience; population outside
  the labour force) -- all `unemployment`'s territory.

CROSS-CHECK (2026 Q1, Both sexes / Male / Female): employment 553.7 / 318.2 /
235.5 thousand; employees 442.0 / 237.1 / 204.9; own account workers 82.2 /
58.7 / 23.5; tertiary sector 77.1 / 69.2 / 87.8 percent; ISCO 1-3 managers and
professionals 31.5 / 28.4 / 35.7; elementary occupations 14.3 / 11.1 / 18.5;
worked 24 to 40 hours 51.9 / 48.6 / 56.2.
"""
from __future__ import annotations

import pandas as pd

from . import _common as C

SURVEY = "Continuous Multi Purpose Household Survey (CMPHS)"
# Statistics Mauritius surveys persons aged 16 and over.
BASE = "16+"

# Sheet -> how to read it. `columns` maps a zero-based column index to the
# category it holds; anything not listed is skipped, which is how the
# labour-force levels and the derived averages are left out.
_TABLES = [
    {
        "sheet": "Table 1",
        "topic": "employment_status",
        "classification": "National",
        "series_code": "CMPHS T1",
        "unit": "thousand_persons",
        "measure": "count",
        "columns": {
            3: "Employees",
            4: "Employers",
            5: "Own account workers",
            6: "Contrib. family workers",
            7: "Total",
        },
    },
    {
        "sheet": "Table 3",
        "topic": "industry",
        # The footnote reads "National version of ..." -- NSIC is Mauritius's
        # own, with ISIC-style section letters.
        "classification": "National",
        "series_code": "CMPHS T3",
        "unit": "percent",
        "measure": "share",
        "columns": {
            3: "Primary sector",
            4: "Secondary sector",
            5: "Tertiary sector",
            6: "Manufacturing (NSIC C)",
            7: "Construction (NSIC F)",
            8: "Wholesale and retail trade (NSIC G)",
            9: "Other services (NSIC H - U)",
        },
    },
    {
        "sheet": "Table 4",
        "topic": "occupation",
        # Table 4's own header names the standard.
        "classification": "ISCO-08",
        "series_code": "CMPHS T4",
        "unit": "percent",
        "measure": "share",
        "columns": {
            3: "Managers, Professionals, Technicians (ISCO 1,2,3)",
            4: "Clerical support workers (ISCO 4)",
            5: "Service and sales workers (ISCO 5)",
            6: "Agricultural, Craft & related, Plant & machine operators (ISCO 6,7,8)",
            7: "Elementary occupations (ISCO 9)",
        },
    },
    {
        "sheet": "Table 5",
        "topic": "hours",
        "classification": "Not applicable",
        "series_code": "CMPHS T5",
        "unit": "percent",
        "measure": "share",
        # Column 2 is total employed and column 3 TOTAL HOURS WORKED (20,000
        # thousand), so the bands start at 4. Reading them from 3 would have
        # emitted 20000 as the share "1 to 23 hours" -- a number that looks
        # like nothing in particular until someone plots it.
        "columns": {
            4: "1 to 23 hours",
            5: "24 to 40 hours",
            6: "41 to 50 hours",
            7: "51 and above",
        },
    },
]

_SEX_BLOCKS = {"both sexes": "total", "male": "male", "female": "female"}


def _cell(v):
    """A published number, or None for a blank / footnote marker cell."""
    if v is None or (isinstance(v, float) and v != v):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return C.to_number(v)


def _parse_sheet(df: pd.DataFrame, spec: dict) -> list[dict]:
    """Walk the sheet top to bottom, tracking which sex block we are in."""
    rows: list[dict] = []
    sex = None
    for _, raw in df.iterrows():
        cells = raw.tolist()
        label = "" if cells[0] is None or pd.isna(cells[0]) else str(cells[0]).strip()
        low = label.lower()
        if low in _SEX_BLOCKS:
            sex = _SEX_BLOCKS[low]
            continue
        if not label or sex is None:
            continue
        # "% change, latest quarter on ..." and its two rows are derived.
        if low.startswith("%") or "change" in low or "quarter a year" in low:
            continue
        period = C.parse_period(label)
        if not period:
            continue
        for idx, characteristic in spec["columns"].items():
            value = _cell(cells[idx]) if idx < len(cells) else None
            if value is None:
                continue
            rows.append(C.row(
                topic=spec["topic"], characteristic=characteristic,
                classification=spec["classification"], value=value,
                survey=SURVEY, period=period, reference_period=label,
                frequency="quarterly",
                measure=spec["measure"], unit=spec["unit"], sex=sex,
                working_age_base=BASE, series_code=spec["series_code"],
            ))
    return rows


def parse(local_path: str) -> pd.DataFrame:
    xl = pd.ExcelFile(local_path)
    have = {s.strip().lower(): s for s in xl.sheet_names}
    rows: list[dict] = []
    missing: list[str] = []
    for spec in _TABLES:
        name = have.get(spec["sheet"].strip().lower())
        if name is None:
            missing.append(spec["sheet"])
            continue
        df = pd.read_excel(local_path, sheet_name=name, header=None)
        got = _parse_sheet(df, spec)
        # Five quarters x three sex blocks x the columns this table publishes.
        want = 3 * len(spec["columns"])
        if len(got) < want:
            raise ValueError(
                f"mauritius_labour: {spec['sheet']} yielded {len(got)} values "
                f"but at least {want} were expected (three sex blocks x "
                f"{len(spec['columns'])} categories). Re-read the sheet rather "
                f"than lowering the guard -- the workbook's shape has changed.")
        rows += got
    if missing:
        raise ValueError(
            f"mauritius_labour: sheet(s) {missing} absent; the workbook holds "
            f"{xl.sheet_names}")
    if not rows:
        raise ValueError("mauritius_labour: no rows parsed")
    return pd.DataFrame.from_records(rows)
