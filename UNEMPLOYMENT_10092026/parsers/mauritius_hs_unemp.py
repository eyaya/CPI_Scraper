"""Mauritius -- Statistics Mauritius "Historical Series on Labour", Table 1.1.

HS_Labour_Yr90-Yr25_<ddmmyy>.xls, sheet "T1.1 1983-2025": labour force,
employment and unemployment by sex, every year 1983-2025 ('000), plus the
unemployment rate. The composition tables of the same workbook are read by
labour/parsers/mauritius_hs_labour.py.

A DIFFERENT SERIES FROM THE CMPHS QUARTERLY ROWS (parsers/mauritius_excel).
These are the RECONCILED estimates ("a set of comparable employment estimates
obtained from different sources": CMPHS, the March Survey of Employment and
Earnings, administrative sources). Employment and the labour force INCLUDE
FOREIGN WORKERS; unemployment and its rate are MAURITIAN only -- footnote 2:
"Unemployment as a percentage of Mauritian labour force". Every series_label
is the column heading as printed, so nothing here can share a merge key with a
CMPHS row (whose periods are quarterly anyway).

Columns, as printed:
    Labour force:  Mauritian | Foreign workers | Total
    Employment (including foreign workers):
                   in large establishments (10+ persons) | outside | Total
    Unemployment:  Number | Rate (%)
1983-1989 print no Mauritian / foreign split of the labour force (blank, not
zero), so those cells are absent.

WORKING-AGE BASE, as the workbook states it: "aged 16 years & over for years
2000 onwards" (Table 1.4 note 3); "population aged 12 years and above" for the
early estimates (Table 1.3(a) note (c)), so 1990-1999 carry 12+. Nothing is
stated for 1983-1989: "not stated".

AS DISPLAYED: values are rounded to their cell's number format. Year markers
("2022 3" revised to the 2022 Census population, "2025 4" provisional) go to
reference_period.
"""
from __future__ import annotations
import re

import pandas as pd
import xlrd

from . import _common as C

SURVEY = ("Historical Series on Labour -- reconciled employment estimates "
          "(CMPHS, SEE and administrative sources; incl. foreign workers)")
SHEET_PREFIX = "T1.1"
CODE = "HS T1.1"

_SEX = {"both sexes": "total", "male": "male", "female": "female"}
_MARKERS = {"3": "revised estimate (2022 Population Census basis)",
            "4": "provisional"}

# column -> (topic, series_label, definition)
_COLS = {
    1: ("labour_force", "Labour force - Mauritian", "not_applicable"),
    2: ("labour_force", "Labour force - Foreign workers", "not_applicable"),
    3: ("labour_force", "Labour force - Total", "not_applicable"),
    4: ("employed", "Employment (including foreign workers) - in large "
        "establishments (employing 10 or more persons)", "not_applicable"),
    5: ("employed", "Employment (including foreign workers) - outside large "
        "establishments", "not_applicable"),
    6: ("employed", "Employment (including foreign workers) - Total",
        "not_applicable"),
    7: ("unemployed", "Unemployment - Number (Mauritians)", "not_applicable"),
    8: ("unemployment_rate", "Unemployment - Rate (% of Mauritian labour force)",
        "strict"),
}
# the printed headings each column must carry (checked, so a moved column fails)
_HEAD = {1: "mauritian", 2: "foreign", 3: "total", 4: "in large",
         5: "outside large", 6: "total", 7: "number", 8: "rate"}


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def _num(book, sh, r, c):
    cell = sh.cell(r, c)
    if cell.ctype != xlrd.XL_CELL_NUMBER:
        return None
    fmt = book.format_map[book.xf_list[cell.xf_index].format_key].format_str
    m = re.search(r"0\.(0+)", fmt)
    return round(cell.value, len(m.group(1))) if m else float(cell.value)


def _year(v):
    if isinstance(v, float):
        return (str(int(v)), str(int(v))) if v.is_integer() else None
    m = re.match(r"^\s*((?:19|20)\d\d)(?:\s+(\d))?\s*$", str(v))
    if not m:
        return None
    y, mark = m.group(1), m.group(2)
    if mark:
        if mark not in _MARKERS:
            raise ValueError(f"mauritius_hs_unemp: unknown year marker {v!r}")
        return y, f"{y} ({_MARKERS[mark]})"
    return y, y


def _base(y: str) -> str:
    y = int(y)
    return "16+" if y >= 2000 else ("12+" if y >= 1990 else "not stated")


def parse(local_path: str) -> pd.DataFrame:
    book = xlrd.open_workbook(local_path, formatting_info=True)
    sh = next((s for s in book.sheets() if s.name.startswith(SHEET_PREFIX)), None)
    if sh is None:
        raise ValueError(f"mauritius_hs_unemp: no {SHEET_PREFIX} sheet in "
                         f"{book.sheet_names()}")
    rows, sex, blocks = [], None, 0
    for r in range(sh.nrows):
        first = _norm(sh.cell_value(r, 0))
        if first.lower() in _SEX:
            sex = _SEX[first.lower()]
            blocks += 1
            continue
        if first.lower() == "year":
            for c, want in _HEAD.items():
                got = _norm(sh.cell_value(r, c)).lower()
                if want not in got:
                    raise ValueError(f"mauritius_hs_unemp: column {c} heading "
                                     f"{got!r}, expected {want!r}")
            continue
        y = _year(sh.cell_value(r, 0)) if sex else None
        if not y:
            continue
        for c, (topic, label, definition) in _COLS.items():
            v = _num(book, sh, r, c)
            if v is None:
                continue
            rows.append(C.row(
                topic=topic, value=v, series_label=label, survey=SURVEY,
                period=y[0], reference_period=y[1], frequency="annual",
                working_age_base=_base(y[0]), definition=definition,
                unit=("percent" if topic == "unemployment_rate"
                      else "thousand_persons"),
                sex=sex, series_code=CODE))
    if blocks != 3:
        raise ValueError(f"mauritius_hs_unemp: {blocks} sex blocks, expected 3")
    df = pd.DataFrame.from_records(rows)
    years = sorted(df["period"].unique())
    if years[0] != "1983" or len(years) != int(years[-1]) - 1982:
        raise ValueError(f"mauritius_hs_unemp: years {years[0]}..{years[-1]} "
                         f"({len(years)}) are not an unbroken run from 1983")
    return df
