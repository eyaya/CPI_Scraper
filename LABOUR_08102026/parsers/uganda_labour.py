"""Uganda — UBOS Labour Market Survey (LMS) 2025, main report.

THE MAIN REPORT, NOT THE FINDINGS DECK. The earlier sweep saw only the
presentation deck, where the sector split is a bar chart, and recorded Uganda
as "industry as a three-sector chart". The 247-page report prints it as a
TABLE, twice:

* Table 3.2, "Sector of employment in the main job by Selected
  Characteristics; (%, 15 years and above)" -- the ILO 15+ base;
* Table A4.7, "Sectors of employment in the main job by Selected
  Characteristics (14-64)" -- the National Employment Policy's 14-64 base,
  which UBOS publishes alongside the ILO one throughout.

Both are TRANSPOSED: the three broad sectors plus Total run ACROSS the columns,
and the rows are characteristics in three blocks -- Sex, Location (rural /
urban) and Sub regions (14, Kampala first) -- closed by a National row.

A4.7 prints three column groups: March-May 2025, June-August 2025 and
Overall. ONLY OVERALL IS TAKEN. The two waves straddle quarter boundaries and
the schema's periods are YYYY, YYYY-Qn or YYYY-Hn; dating March-May as Q2 or
H1 would claim a reference period UBOS did not use. Table 3.2 is overall only.

The sector labels are printed as UBOS words them -- "Industry" in Table 3.2,
"Production" in A4.7 -- and are not harmonised. UBOS names no scheme for the
grouping, so `National`, as for the other broad-sector tables here.

WHAT IS LEFT: chapters 7 and 8 ("Employment in formal / informal businesses")
are ESTABLISHMENT data -- employment counted through enterprises -- the
universe that blocks Kenya; they are not household composition. Informal
employment shares (Tables 3.3/3.4) belong to `unemployment`. No status in
employment or occupation table exists in the household chapters.

CROSS-CHECK (National): 15+ agriculture 37.1, industry 12.4, services 50.5;
14-64 overall 36.6 / 12.4 / 51.0. Kampala 15+ services 79.6; female 15+
services 56.4.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from ._common import row

SURVEY = "Labour Market Survey (LMS) 2025"
_BLOCKS = {"Sex", "Location", "Sub regions"}

_TABLES = [
    # caption, working-age base, category names in printed order,
    # number of values per row, index of the first value taken
    (r"^Table 3\.2: Sector of employment in the main job", "15+",
     ["Agriculture, Forestry and Fishing", "Industry", "Services", "Total"],
     4, 0, "LMS2025 T3.2"),
    (r"^Table A4\.7: Sectors of employment in the main job", "14-64",
     ["Agriculture, forestry and fishing", "Production", "Services", "Total"],
     12, 8, "LMS2025 TA4.7 overall"),
]


def _table(pages: list[str], caption, base, cats, n, first, code) -> list[dict]:
    cap = re.compile(caption)
    text = next((t for t in pages if cap.search(t) and "....." not in
                 t[cap.search(t).start():cap.search(t).start() + 250]), None)
    if text is None:
        raise ValueError(f"{code}: caption not found")
    lines = text[cap.search(text).start():].splitlines()
    head = " ".join(lines[:6]).lower()
    for c in cats[:-1]:
        if c.split(",")[0].lower() not in head:
            raise ValueError(f"{code}: column {c!r} not in the printed header")
    out, block, got = [], None, set()
    for ln in lines[1:]:
        s = ln.strip()
        if s in _BLOCKS:
            block = s
            continue
        m = re.match(r"^(.*?[A-Za-z)])\s+([\d.\s]+)$", s)
        if not m or (block is None and not s.startswith("National")):
            continue
        label, nums = m.group(1).strip(), m.group(2).split()
        if len(nums) != n:
            continue
        vals = [float(x) for x in nums[first:first + 4]]
        if abs(sum(vals[:3]) - vals[3]) > 0.3:
            raise ValueError(f"{code} {label}: {vals[:3]} do not sum to "
                             f"{vals[3]}")
        sex, loc, loc_lab, geo = "total", "all", "Total", "Total country"
        if label == "National":
            pass
        elif block == "Sex":
            sex = "male" if label == "Male" else "female"
        elif block == "Location":
            loc, loc_lab = label.lower(), label
        elif block == "Sub regions":
            geo = label
        else:
            raise ValueError(f"{code}: row {label!r} outside a block")
        got.add(label)
        for c, v in zip(cats, vals):
            out.append(row(topic="industry", characteristic=c,
                           classification="National", survey=SURVEY,
                           period="2025", reference_period="March-August 2025",
                           frequency="ad_hoc", working_age_base=base,
                           sex=sex, locality=loc, locality_label=loc_lab,
                           geography=geo, value=v, measure="share",
                           unit="percent", series_code=code))
        if label == "National":
            break
    # 2 sexes + 2 locations + 14 sub-regions + National
    if len(got) != 19:
        raise ValueError(f"{code}: read {len(got)} rows, expected 19: {sorted(got)}")
    return out


def parse(local_path: str) -> pd.DataFrame:
    with pdfplumber.open(local_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    rows = []
    for spec in _TABLES:
        rows += _table(pages, *spec)
    return pd.DataFrame(rows)
