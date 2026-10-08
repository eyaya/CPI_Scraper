"""Malawi NSO 2018 census — labour / economic activity (Series D tables).

Two clean tables of the "Series D. Economic Tables" workbook:

* D1 — the population aged 15-64 by activity status (economically active,
  employed) and sex, at national level;
* D7 — the employed population by industry and employment status.

D1 is read as an `activity_status` topic (the total 15-64 population, the
economically active, and the employed — as published counts, by sex). D7 is read
as an `industry` topic (employed persons by industry). Everything is emitted as
published; Malawi's own labels are kept.
"""
from __future__ import annotations
import re
import pandas as pd
from openpyxl import load_workbook


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


# The classification each topic's categories belong to, read off the labels
# themselves rather than assumed: the industry rows are verbatim ISIC Rev.4
# SECTION names ("Accommodation and food service activities", "Activities of
# extraterritorial organizations and bodies") and the occupation rows are the
# ISCO-08 major groups ("Managers", "Clerical support workers", "Elementary
# occupations", "Armed forces occupations").
CLASSIFICATION = {
    "industry": "ISIC Rev.4",
    "occupation": "ISCO-08",
    "activity_status": "Not applicable",
}


def _row(topic, characteristic, sex, value, unit="persons", measure="count"):
    return {"topic": topic, "characteristic": characteristic,
            "classification": CLASSIFICATION.get(topic, "National"),
            "sex": sex,
            "age_group": "Total", "education": "Total",
            "geography": "Total country", "locality": "all",
            "locality_label": "Total",
            # Table D1 counts the population aged 15-64, so that is the base
            # every row here is drawn from.
            "working_age_base": "15-64",
            "survey": "Population and Housing Census 2018",
            "period": "2018", "reference_period": "MPHC 2018",
            "frequency": "annual", "measure": measure,
            "value": value, "unit": unit, "series_code": "MPHC2018"}


# the five (Total/Male/Female) column blocks of Table D1, first column of each
# block -> the activity-status category it counts.
_D1_BLOCKS = {
    1: "15-64 population",
    4: "Economically active",
    7: "Employed",
    10: "Unemployed",
    13: "Economically inactive",
}


def _parse_d1(ws) -> list[dict]:
    """National activity status: the 'Malawi' row carries five (Total, Male,
    Female) blocks — the 15-64 population, the economically active, the employed,
    the unemployed and the economically inactive."""
    rows = list(ws.iter_rows(values_only=True))
    mrow = next((r for r in rows
                 if r and r[0] and str(r[0]).strip().lower() == "malawi"), None)
    if mrow is None:
        return []
    out = []
    for first, category in _D1_BLOCKS.items():
        for off, sex in enumerate(("total", "male", "female")):
            c = first + off
            n = _num(mrow[c]) if c < len(mrow) else None
            if n is not None:
                out.append(_row("activity_status", category, sex, n))
    return out


def _parse_d7(ws) -> list[dict]:
    """Employed population by industry (col A), Total-employment column. The sheet
    stacks a both-sexes block then a Males block then a Females block, each
    repeating the industry list; we read only the first (both-sexes) block, which
    starts at its 'Total' row and ends at the next section header ('Industry')."""
    rows = list(ws.iter_rows(values_only=True))
    ti = next((i for i, r in enumerate(rows)
               if r and r[0] and str(r[0]).strip().lower() == "total"), None)
    if ti is None:
        return []
    out = []
    for r in rows[ti:]:
        name = str(r[0]).strip() if r and r[0] is not None else ""
        if name.lower() in ("industry", "males", "females"):
            break                      # next block -> stop
        val = _num(r[1]) if len(r) > 1 else None
        if not name or val is None:
            continue
        characteristic = "Total" if name.lower() == "total" else name
        out.append(_row("industry", characteristic, "total", val))
    return out


def _parse_d9(ws) -> list[dict]:
    """Employed population by occupation (col A), national block: Total/Male/Female
    at columns 1/2/3. Starts at the 'Total' row (= total employed); each following
    row is one occupation."""
    rows = list(ws.iter_rows(values_only=True))
    ti = next((i for i, r in enumerate(rows)
               if r and r[0] and str(r[0]).strip().lower() == "total"), None)
    if ti is None:
        return []
    out = []
    for r in rows[ti:]:
        name = str(r[0]).strip() if r and r[0] is not None else ""
        if name.lower() in ("occupation", "males", "females"):
            break
        if not name or _num(r[1]) is None:
            continue
        characteristic = "Total" if name.lower() == "total" else name
        for off, sex in ((0, "total"), (1, "male"), (2, "female")):
            v = _num(r[1 + off]) if 1 + off < len(r) else None
            if v is not None:
                out.append(_row("occupation", characteristic, sex, v))
    return out


def parse(local_path: str) -> pd.DataFrame:
    wb = load_workbook(local_path, read_only=True, data_only=True)
    rows = []
    if "D1" in wb.sheetnames:
        rows += _parse_d1(wb["D1"])
    if "D7" in wb.sheetnames:
        rows += _parse_d7(wb["D7"])
    if "D9" in wb.sheetnames:
        rows += _parse_d9(wb["D9"])
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("malawi_nso_labour: no rows parsed")
    return df.drop_duplicates(["topic", "characteristic", "sex", "period"])
