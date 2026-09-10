"""Kenya KNBS 2019 census — national population by age & sex (Tier-3 PDF).

Parser for Volume III ("Distribution of Population by Age and Sex"), Table 2.2
(national, Kenya). The report renders each figure with its leading digit in a
separate text run ("3 ,006,344" = 3,006,344), so we read the table by column
position and strip the internal spaces; every row then self-verifies as
Male + Female + Intersex = Total. Kenya publishes an Intersex category, which is
folded into the published Total (our sex vocabulary is male/female/total), so we
emit Male, Female and the Total column as published.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_TITLE = "Distribution of Population by Age and Sex, Kenya"
# an age-group label (5-year band, open-ended top, or the grand Total), optionally
# followed by a leading digit that bled left out of the Male column.
_GRP = re.compile(r"^(Total|[A-Za-z ]*Stated|\d{1,3}\s*-\s*\d{1,3}|\d{1,3}\+)\s*(\d*)$", re.I)
_TBL = {"vertical_strategy": "text", "horizontal_strategy": "text"}


def _clean(x: str) -> str:
    return (x or "").replace(" ", "").replace(",", "").strip()


def _int(x: str) -> int:
    x = _clean(x)
    return 0 if x in ("", "-") else int(x)


def _digits(x: str) -> int:
    """Keep only digits (the county table interleaves dot-leaders into numbers)."""
    d = re.sub(r"[^\d]", "", x or "")
    return int(d) if d else 0


_COUNTY_TITLE = "Distribution of Population by Sex and County"
_LEADERS = re.compile(r"[.…�]+")


def _parse_counties(path: str) -> list[dict]:
    """Volume I, Table 2.2 — population by sex and county (all ages). Names carry
    dot-leaders and the numbers have the same split-digit rendering; each row is
    checked as Male + Female + Intersex = Total (rejects a mis-parse)."""
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:40]:
            if _COUNTY_TITLE not in (page.extract_text() or ""):
                continue
            for tbl in page.extract_tables(_TBL):
                for r in tbl:
                    if len(r) < 5 or not r[0]:
                        continue
                    raw = _LEADERS.sub(" ", r[0]).strip()
                    m = re.match(r"^(.*?)\s*(\d*)$", raw)
                    name, bleed = m.group(1).strip(), m.group(2)
                    if not re.match(r"^[A-Za-z]", name) or \
                            name.lower() in ("kenya", "county", "national county"):
                        continue
                    male = _digits(bleed + (r[1] or ""))
                    female, intersex, total = _digits(r[2]), _digits(r[3]), _digits(r[4])
                    if total <= 1000 or male + female + intersex != total:
                        continue
                    for sex, val in (("male", male), ("female", female), ("total", total)):
                        rows.append({
                            "series_type": "census", "sex": sex, "age_group": "Total",
                            "geography": name, "period": "2019", "frequency": "annual",
                            "measure": "count", "value": float(val), "unit": "persons",
                            "series_code": "KPHC2019",
                        })
    return rows


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages[:60]:                 # national table is early
            text = page.extract_text() or ""
            if _TITLE not in text:                   # skips the Rural/Urban/county tables
                continue
            for tbl in page.extract_tables(_TBL):
                for r in tbl:
                    if len(r) < 5 or not r[0]:
                        continue
                    m = _GRP.match(r[0].strip())
                    if not m:
                        continue
                    lbl = m.group(1)
                    age = "Not stated" if "stated" in lbl.lower() \
                        else re.sub(r"\s*-\s*", "-", lbl)
                    male = _int(m.group(2) + _clean(r[1]))   # prepend any bled digit
                    female, intersex, total = _int(r[2]), _int(r[3]), _int(r[4])
                    if male + female + intersex != total:    # reject a mis-parse
                        continue
                    for sex, val in (("male", male), ("female", female), ("total", total)):
                        rows.append({
                            "series_type": "census", "sex": sex, "age_group": age,
                            "geography": "Total country", "period": "2019",
                            "frequency": "annual", "measure": "count",
                            "value": float(val), "unit": "persons",
                            "series_code": "KPHC2019",
                        })
    for ex in (extras or []):                    # county totals (Volume I)
        rows += _parse_counties(ex)

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("knbs_population: no rows parsed")
    return df.drop_duplicates(["geography", "sex", "age_group", "period"])
