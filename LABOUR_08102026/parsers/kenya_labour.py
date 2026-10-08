"""Kenya — KNBS 2015/16 Kenya Integrated Household Budget Survey (KIHBS),
"Labour Force Basic Report", Table 3.8: usual hours worked by the employed.

THE ONLY COMPOSITION TABLE KNBS PUBLISHES FROM A HOUSEHOLD SURVEY, and it is
`hours`, not industry or occupation. What was searched (KNBS's WordPress
media API, /wp-json/wp/v2/media?search=..., which lists every upload):

* the Quarterly Labour Force Report (2019-2022, archived) -- ten tables, all
  labour-force status; `unemployment` collects it;
* this KIHBS 2015/16 Labour Force Basic Report -- twenty tables: dependency,
  activity status, participation, HOURS (3.8), part-time (3.9), education,
  "working patterns" (3.12/3.13), under-employment, LU1/LU2, inactivity. No
  industry, occupation, status-in-employment, sector or informality table;
* the 2019 KPHC Volume IV and 2009 KPHC Volume II (socio-economic
  characteristics) -- activity status only (working / seeking work / outside
  the labour force), the labour-force status `unemployment` covers, and no
  composition of the employed;
* the Economic Survey's Chapter 3 employment workbook -- REFUSED, unchanged:
  establishment and payroll records that exclude the informal sector and the
  agricultural self-employed. It would sit under the same `industry` merge key
  as household-survey composition while counting a different population.
  Collecting it would make the corpus look more complete and be less true;
* the 2026 Integrated Labour Force Survey -- in the field; KNBS's page carries
  only FAQs. It is what will bring industry/occupation/status for Kenya.

TABLE 3.8: each row is a group of the employed aged 15-64 (an age cohort, or
the total, for both sexes, males and females) and its distribution across
eleven bands of usual weekly hours; every row sums to 100. The universe is the
employed: the Total row's N, 17,875.7 thousand, is the employed 15-64 of
Table 3.12 ("out of the total employed persons aged 15 - 64").

THE BAND HEADERS ARE ROTATED and reach the text layer character-reversed
("naht sseL 51", "42-51", "92-52", ..., "99 evobA", "toN detatS"). The order is
asserted on every run against those reversed tokens, and confirmed by the
report's prose: 40-48 hours = 27.7 (column 6); "more than 58 hours ... 25.2"
= 18.5 + 5.5 + 1.2 (columns 8-10); males under 24 hours 13.2 = 5.6 + 7.6,
females 22.8 = 7.7 + 15.1.

LETTER-SPACED DIGITS: the text layer splits two-digit values ("2 1.1" for 21.1,
"2 7.7 1 0.2" for 27.7 10.2). Every value in the table carries one decimal, so
a lone digit followed by a "d.d" token is one value -- and each row must then
read exactly eleven cells summing to 100. "-" is an empty cell (males 25-29,
not stated), kept in position and not emitted.

NOT COLLECTED: the N column (employment levels by age and sex --
`unemployment`'s territory); Table 3.9 (part-time / full-time at a 35-hour
cut -- a regrouping of these same bands, which would double-count within the
topic); Tables 3.12/3.13 "working patterns" (full-time / part-time / seasonal
/ casual) -- no topic in this schema holds work arrangements, and the rule is
to drop rather than bend into a neighbour; their age rows are also
distributions of each pattern across ages (row percentages here).

Base 15-64. Period 2016 (fieldwork September 2015 - August 2016; the report
dates its figures "in 2016"), reference "KIHBS 2015/16".

CROSS-CHECK: total 40-48 hours 27.7; less than 15 hours 6.6; 15-19 year-olds
less than 15 hours 30.8; males 40-48 29.3; females 15-24 hours 15.1.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_CAPTION = re.compile(r"^Table 3\.8: Percentage Distribution of Population "
                      r"\(15 – 64\) by Hours Worked and Sex", re.M)
_BANDS = ["Less than 15", "15-24", "25-29", "30-34", "35-39", "40-48",
          "49-58", "59-83", "84-99", "99 and Above", "Not Stated"]
# The rotated header as the text layer gives it, in column order.
_REVERSED_HEADER = ["naht", "sseL", "51", "42-51", "92-52", "43-03", "93-53",
                    "84-04", "85-94", "38-95", "99-48", "99", "evobA", "toN",
                    "detatS"]
_BLOCKS = {"Males": "male", "Female": "female"}
_AGE = re.compile(r"^(\d\d-\d\d|Total)\s+([\d,]+\.\d)\s+(.*?)\s+100$")


def _cells(text: str) -> list[float | None]:
    toks = text.split()
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t == "-":
            out.append(None)
        elif re.fullmatch(r"\d", t) and i + 1 < len(toks) \
                and re.fullmatch(r"\d\.\d", toks[i + 1]):
            out.append(float(t + toks[i + 1]))
            i += 1
        elif re.fullmatch(r"\d{1,3}\.\d", t):
            out.append(float(t))
        else:
            raise ValueError(f"KIHBS T3.8: unreadable cell {t!r} in {text!r}")
        i += 1
    return out


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        text = next(t for t in (p.extract_text() or "" for p in pdf.pages)
                    if len(_CAPTION.findall(t)) and "evobA" in t)
    words = text.split()
    pos = 0
    for tok in _REVERSED_HEADER:
        try:
            pos = words.index(tok, pos) + 1
        except ValueError:
            raise ValueError(f"KIHBS T3.8: header token {tok!r} not in order -- "
                             f"the band columns may have moved")
    sex, rows = "total", []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln in _BLOCKS:
            sex = _BLOCKS[ln]
            continue
        m = _AGE.match(ln)
        if not m:
            continue
        vals = _cells(m.group(3))
        if len(vals) != len(_BANDS):
            raise ValueError(f"KIHBS T3.8: {ln!r} reads {len(vals)} cells")
        s = sum(v for v in vals if v is not None)
        if abs(s - 100) > 0.35:
            raise ValueError(f"KIHBS T3.8: {ln!r} sums to {s:.1f}")
        rows.append((sex, m.group(1), vals))
    # 10 age cohorts + Total, for each of three blocks.
    if len(rows) != 33 or {r[0] for r in rows} != {"total", "male", "female"}:
        raise ValueError(f"KIHBS T3.8: read {len(rows)} rows")
    out = []
    for sex, age, vals in rows:
        for band, v in zip(_BANDS, vals):
            if v is None:
                continue
            out.append(C.row(topic="hours", characteristic=band,
                             classification="Not applicable", value=v,
                             survey="Kenya Integrated Household Budget Survey "
                                    "(KIHBS) 2015/16",
                             period="2016", reference_period="KIHBS 2015/16",
                             frequency="ad_hoc", measure="share",
                             unit="percent", sex=sex,
                             age_group="Total" if age == "Total" else age,
                             working_age_base="15-64",
                             series_code="KIHBS T3.8"))
    return pd.DataFrame(out)
