"""Uganda Bureau of Statistics (UBOS) national population projections.

Parser for the "National Population Projections by 5 year age groups and sex"
workbook: a single sheet of stacked blocks, each covering three years across the
columns and the 17 five-year age bands down the rows.

    (year header)     2015            2016            2017
    Age group     Male  Female    Male  Female    Male  Female
     0-4          ...   ...       ...   ...       ...   ...

Each block sits at a year-header row (years in columns 1, 4, 7; Male in the year's
column, Female in the next), followed by the age rows. We emit one tidy row per
(age band, sex, year) as a projected head count, national only. Values are kept
exactly as published (UBOS publishes male/female, no combined total in this file).
"""
from __future__ import annotations
import re
import pandas as pd
from openpyxl import load_workbook

_AGE = {"0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
        "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80+"}
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")
_YEAR_COLS = (1, 4, 7)          # a year label sits in each of these columns


def _year(v):
    if v is None:
        return None
    s = str(v).strip().split(".")[0]
    return int(s) if _YEAR_RE.match(s) else None


def _num(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def _parse_district(path: str) -> list[dict]:
    """The 'Projected population by district' workbook: district name in column 1,
    then Male/Female/Total for each year (year labels every three columns). One
    all-ages row per (district, sex, year); UBOS publishes the total, kept as-is."""
    wb = load_workbook(path, read_only=True, data_only=True)
    rows = [list(r) for r in wb[wb.sheetnames[0]].iter_rows(values_only=True)]
    # the year-header row is the one with the most 4-digit years
    hdr_i = max(range(len(rows)), key=lambda i: sum(1 for c in rows[i] if _year(c)))
    years = [(c, _year(rows[hdr_i][c])) for c in range(len(rows[hdr_i]))
             if _year(rows[hdr_i][c])]
    out = []
    for r in rows[hdr_i + 2:]:              # skip the Male/Female/Total sub-header
        name = str(r[1]).strip() if len(r) > 1 and r[1] is not None else ""
        if not name or _year(name):
            continue
        for c, year in years:
            for sex, off in (("male", 0), ("female", 1), ("total", 2)):
                val = _num(r[c + off]) if c + off < len(r) else None
                if val is not None:
                    out.append({
                        "series_type": "projection", "sex": sex,
                        "age_group": "Total", "geography": name.title(),
                        "period": str(year), "frequency": "annual",
                        "measure": "count", "value": val, "unit": "persons",
                        "series_code": "UBOS_PROJ_DIST",
                    })
    return out


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    wb = load_workbook(local_path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]

    out = []
    for i, r in enumerate(rows):
        # a year-header row carries a year in >=2 of the year columns
        years = [(c, _year(r[c])) for c in _YEAR_COLS if c < len(r) and _year(r[c])]
        if len(years) < 2:
            continue
        # read the age rows that follow, stopping at the next block's year header
        started = False
        for rr in rows[i + 1:]:
            if len([c for c in _YEAR_COLS if c < len(rr) and _year(rr[c])]) >= 2:
                break                 # next block starts here
            age = str(rr[0]).strip() if rr and rr[0] is not None else ""
            if age not in _AGE:
                if started:
                    break             # age rows of this block are done
                continue              # header / spacer before the age rows
            started = True
            for c, year in years:
                male, female = _num(rr[c]) if c < len(rr) else None, \
                    _num(rr[c + 1]) if c + 1 < len(rr) else None
                for sex, val in (("male", male), ("female", female)):
                    if val is not None:
                        out.append({
                            "series_type": "projection", "sex": sex,
                            "age_group": age, "geography": "Total country",
                            "period": str(year), "frequency": "annual",
                            "measure": "count", "value": val, "unit": "persons",
                            "series_code": "UBOS_PROJ",
                        })
    # optional: district-level all-ages projections from an extra workbook
    for ex in (extras or []):
        out.extend(_parse_district(ex))

    df = pd.DataFrame(out)
    if df.empty:
        raise ValueError("ubos_population: no rows parsed")
    # a block boundary can re-encounter years already read; keep one row each
    return df.drop_duplicates(["geography", "sex", "age_group", "period"])
