"""South Sudan — NBS (then SSCCSE), "Southern Sudan Counts: Tables from the 5th
Sudan Population and Housing Census, 2008", chapter 5 "Economic Activity".

THE SAME VOLUME `labour/` READS (its Tables 5-3 to 5-8, composition); this
module reads the two rate tables it leaves here:

* Table 5-1  labour force participation rate
* Table 5-2  unemployment rate

each on TWO working-age bases printed side by side -- "population aged 10 and
above" and "population aged 15 and above" -- by total / male / female, and by
urban/rural, age group, the person's own educational attainment and state. Both
bases are collected, each row carrying its own `working_age_base`; the 10-14
row exists only on the 10+ base ("--" on the 15+ side, an empty cell).

DEFINITION. The volume's glossary (p.7): "Unemployment rate: Percentage of
those active in the labour force who are not in work and do not have a job to
go back to but are actively seeking work". That is a job-search criterion with
no availability test, and the census attaches no strict / broad label of its
own, so `definition` is `not_applicable` rather than a claim of ILO-strict.
Census rates are self-reported activity status and should not be read against a
labour force survey's without saying so.

ROUNDED TO WHOLE PERCENT, as printed.

NOT COLLECTED: the three household-HEAD blocks of both tables (sex,
educational attainment and occupational status of the head) -- they classify
the person by someone else's characteristic, which no column holds; labour/
leaves the same blocks out. Tables 5-9/5-10 (reasons for not seeking work).

THE ROWS ARE READ IN PRINTED ORDER against a stated list, each line checked to
begin with its expected first word, so the "Ghazal" halves of Northern and
Western Bahr El Ghazal (which wrap onto their own line) and the head blocks'
repeated education labels cannot be taken for one another.

PERIOD 2008 (census night, April 2008).

CROSS-CHECK: participation 71 (10+) / 74 (15+), urban 64 / 69; unemployment
14 (10+) / 12 (15+); 15-24 unemployment 19; Jonglei 22 / 20; Eastern Equatoria
unemployment 5 / 4.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = "5th Sudan Population and Housing Census 2008 (Southern Sudan)"
_PERIOD, _REF = "2008", "Census 2008"
_CELL = r"(\d{1,3}|--)"
_ROW_RE = re.compile(rf"^(.*?)\s*{_CELL}\s+{_CELL}\s+{_CELL}\s+{_CELL}\s+{_CELL}\s+{_CELL}$")

_STATES = ["Upper Nile", "Jonglei", "Unity", "Warrap", "Northern Bahr El Ghazal",
           "Western Bahr El Ghazal", "Lakes", "Western Equatoria",
           "Central Equatoria", "Eastern Equatoria"]
_HEAD = ["Male", "Female", "Never", "No", "Primary", "Secondary", "Paid",
         "Employer", "Own", "Unpaid", "Unpaid", "Not"]


def _groups(top_edu: str) -> list[tuple[str, dict | None]]:
    g = [("Southern", {}),
         ("Urban", {"locality": "urban", "locality_label": "Urban"}),
         ("Rural", {"locality": "rural", "locality_label": "Rural"})]
    g += [(a, {"age_group": a}) for a in
          ("10-14", "15-24", "25-34", "35-44", "45-54", "55-64", "65+")]
    g += [(e.split()[0], {"education": e}) for e in
          ("Never attended school", "Currently attending school",
           "No qualifications", "Primary", top_edu)]
    g += [(h, None) for h in _HEAD]                 # household-head blocks
    g += [(s.split()[0], {"geography": s}) for s in _STATES]
    return g


_TABLES = [
    (r"Table 5-1: Labour force participation rate by background",
     "labour_force_participation_rate", "Labour force participation rate",
     "Secondary", "Census T5-1"),
    (r"Table 5-2: Unemployment rate by background",
     "unemployment_rate", "Unemployment rate", "Secondary or higher",
     "Census T5-2"),
]


def _read(text: str, groups, where: str):
    out, i = [], 0
    for ln in text.splitlines():
        if i == len(groups):
            break
        m = _ROW_RE.match(ln.strip())
        if not m:
            continue
        first = groups[i][0]
        if not re.search(rf"(?:^|\s){re.escape(first)}", m.group(1)):
            raise ValueError(f"{where}: expected a {first!r} row, read {ln!r}")
        out.append((groups[i][1], [None if c == "--" else float(c)
                                   for c in m.groups()[1:]]))
        i += 1
    if i != len(groups):
        raise ValueError(f"{where}: read {i} of {len(groups)} rows")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    rows = []
    for caption, topic, label, top_edu, code in _TABLES:
        # The list of tables carries the caption too; the table's own page
        # opens with "Table 5-n:" and holds its Source line.
        page = next((t for t in pages if re.search(caption, t)
                     and "Source: 5th Sudan Population" in t), None)
        if page is None:
            raise ValueError(f"{code}: table page not found")
        body = page[re.search(caption, page).end():]
        for ctx, vals in _read(body, _groups(top_edu), code):
            if ctx is None:
                continue
            for base, sexes in (("10+", vals[:3]), ("15+", vals[3:])):
                for sex, v in zip(("total", "male", "female"), sexes):
                    if v is None:
                        continue
                    rows.append(C.row(
                        topic=topic, definition="not_applicable", value=v,
                        series_label=f"{label} - population aged {base[:-1]} "
                                     f"and above",
                        survey=_SURVEY, period=_PERIOD, reference_period=_REF,
                        frequency="ad_hoc", working_age_base=base, sex=sex,
                        series_code=code, **ctx))
    return pd.DataFrame(rows)
