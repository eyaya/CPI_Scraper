"""Namibia -- NSA Labour Force Survey BACK-SERIES: 2013, 2014, 2016, 2018.

The current Namibia rows (namibia_unemployment.py) are the 2023 Population and
Housing Census labour-force report. These are the four LFS rounds before it,
each read from the report NSA publishes:

    2013  Namibia Labour Force Survey 2013 Report      Tables 3.4 and 5.3
    2014  Namibia Labour Force Survey 2014 Report      Tables 3.4 and 5.3
    2016  Key Highlights of the NLFS 2016 Report       Table 5
    2018  The Namibia Labour Force Survey 2018 Report  Tables 3.4 and 5.3

Table 3.4 -- "Labour force participation rates by region and sex (broad)":
working-age population, labour force and LFPR. Table 5.3 (2016: Table 5) --
"Unemployment rate by sex and location/region": unemployed, labour force and
unemployment rate. Rows: Namibia, Urban, Rural, then each region; for each, a
triple of figures per sex.

THE BROAD DEFINITION. These reports measure unemployment "for the most part"
on NSA's broad (relaxed) definition, which "drops the requirement that the
person actively looked for work" (2014 report, 5.1). Every table read here is
the broad one, and every row says so: definition `broad` on the unemployed,
labour-force, participation and unemployment-rate rows. The 2023 census rows
are strict (19th ICLS); the two are never mixed. The working-age population
is definition-free.

SEX ORDER DIFFERS BY YEAR AND IS PINNED FROM THE PRINTED HEADERS (checked on
rendered pages): 2013 and 2014 print Female | Male | Both sexes; 2016 and 2018
print Both sexes | Male | Female. The parser also proves the "both" column
equals male + female on every row, so a wrong order cannot pass silently.

COLUMN ORDER inside Table 3.4 also differs: 2013 prints Labour force | Working
age | LFPR, 2014 and 2018 Working age | Labour force | LFPR.

ONE LABOUR FORCE PER CELL. Both tables print the labour force; it is taken
from Table 3.4 and Table 5.3's copy is CHECKED equal (2016 has only Table 5,
which supplies it).

NUMBERS. 2013 groups thousands with a space ("980 781 1 384 054"), the others
with a comma. Region names are kept as printed ("//Karas" 2013, "!karas"
2014, "!Karas" 2016-2018; "Kavango" before the 2013 split into East/West).

NOT READ: the strict-definition tables (2013 Table 5.8-5.9, 2014's two), the
age and education tables, and 2016-2018 employment composition.
"""
from __future__ import annotations
import os
import re

import fitz
import pandas as pd

from . import _common as C

_REGIONS = {"zambezi", "erongo", "hardap", "//karas", "!karas", "kavango",
            "kavango east", "kavango west", "khomas", "kunene", "ohangwena",
            "omaheke", "omusati", "oshana", "oshikoto", "otjozondjupa"}
_AREAS = {"namibia", "urban", "rural"}

# year -> {file key, tables: [(title regex, kind, column order, sex order)]}
#   kind "lfpr": columns among wap / lf / lfpr ; kind "unemp": u / lf / rate
_YEARS = {
    2013: dict(match=r"2013", sep="space", tables=[
        (r"Table 3\.4\s*:\s*Labour force participation rates by region and sex",
         "lfpr", ("lf", "wap", "lfpr"), ("female", "male", "total")),
        (r"Table 5\.3\s+Unemployment rate by sex and location",
         "unemp", ("u", "lf", "rate"), ("female", "male", "total")),
    ]),
    2014: dict(match=r"9b8e77842e3dec459407c2a76b9d79ab|2014", sep="comma", tables=[
        (r"Table 3\.4\s*:\s*Labour force participation rates by region and sex",
         "lfpr", ("wap", "lf", "lfpr"), ("female", "male", "total")),
        (r"Table 5\.3\s*:\s*Unemployment rate by sex and location",
         "unemp", ("u", "lf", "rate"), ("female", "male", "total")),
    ]),
    2016: dict(match=r"2016", sep="comma", tables=[
        (r"Table 5\s*:\s*Unemployed population by sex and by area",
         "unemp", ("u", "lf", "rate"), ("total", "male", "female")),
    ]),
    2018: dict(match=r"2018", sep="comma", tables=[
        (r"Table 3\.4\s*:\s*Labour force participation rates by sex and area",
         "lfpr", ("wap", "lf", "lfpr"), ("total", "male", "female")),
        (r"Table 5\.3\s*:\s*Unemployment rate by sex and region",
         "unemp", ("u", "lf", "rate"), ("total", "male", "female")),
    ]),
}

_SPEC = {   # column -> (topic, series_label, definition)
    "wap": ("working_age_population", "Working age population 15+ years",
            "not_applicable"),
    "lf": ("labour_force", "Labour force (broad definition)", "broad"),
    "lfpr": ("labour_force_participation_rate",
             "Labour force participation rate (broad definition)", "broad"),
    "u": ("unemployed", "Unemployed (broad definition)", "broad"),
    "rate": ("unemployment_rate", "Unemployment rate (broad definition)", "broad"),
}

# 2018 prints Zambezi's male unemployed as "7,249.67": grouped AND decimal.
_NUM = {"comma": re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d,])|\d+\.\d+|\d+"),
        "space": re.compile(r"\d{1,3}(?: \d{3})+(?!\d)|\d+\.\d+|\d+")}


def _year_of(path: str) -> int:
    name = os.path.basename(path)
    hits = [y for y, c in _YEARS.items() if re.search(c["match"], name)]
    if len(hits) != 1:
        raise ValueError(f"namibia_lfs_back: cannot tell the round of {name!r}")
    return hits[0]


def _tokens(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", l).strip() for l in text.splitlines() if l.strip()]


def _table_rows(doc, title: str, sep: str) -> list[tuple[str, list[float]]]:
    """Rows of the first page where `title` is followed by data rows."""
    rx = re.compile(title, re.I)
    for page in doc:
        text = page.get_text()
        m = rx.search(re.sub(r"\s+", " ", text))
        if not m:
            continue
        toks = _tokens(text)
        # restart the token stream at the title
        flat = " | ".join(toks)
        start = rx.search(flat)
        if not start:
            continue
        body = flat[start.end():]
        nxt = re.search(r"\|\s*Table\s+\d", body)
        if nxt:
            body = body[:nxt.start()]
        rows, label, nums = [], None, []
        for tok in [t.strip() for t in body.split("|")]:
            low = tok.lower()
            if low in _AREAS or low in _REGIONS:
                if label and nums:
                    rows.append((label, nums))
                label, nums = tok, []
                continue
            if label is None:
                continue
            found = _NUM[sep].findall(tok)
            if found and re.fullmatch(r"[\d ,.%]+", tok):
                nums += [float(x.replace(",", "").replace(" ", "")) for x in found]
        if label and nums:
            # the LAST row runs into whatever follows the table on the page
            # (a page number, a figure caption); its own figures come first
            rows.append((label, nums[:9]))
        if len(rows) >= 3:
            return rows
    raise ValueError(f"namibia_lfs_back: table {title!r} not found with data")


def _read(path: str) -> list[dict]:
    year = _year_of(path)
    cfg = _YEARS[year]
    doc = fitz.open(path)
    rows, lf_seen, spelling = [], {}, {}
    for title, kind, cols, sexes in cfg["tables"]:
        code = f"NSA LFS {year} Table " + re.sub(r"\\", "", title.split()[1].split(r"\s")[0])
        got = _table_rows(doc, title, cfg["sep"])
        labels = [l.lower() for l, _ in got]
        if labels[:3] != ["namibia", "urban", "rural"] or len(got) < 16:
            raise ValueError(f"namibia_lfs_back {year} {title!r}: rows {labels}")
        for label, nums in got:
            if len(nums) != 9:
                raise ValueError(f"namibia_lfs_back {year} {label!r}: "
                                 f"{len(nums)} figures, expected 9")
            cell = {(sexes[k // 3], cols[k % 3]): nums[k] for k in range(9)}
            # the 'total' triple must be male + female on the two counts
            for c in cols:
                if _SPEC[c][0] in ("labour_force", "working_age_population",
                                   "unemployed"):
                    if abs(cell[("male", c)] + cell[("female", c)]
                           - cell[("total", c)]) > 2:
                        raise ValueError(
                            f"namibia_lfs_back {year} {label} {c}: male + female "
                            f"!= both sexes -- sex order wrong or a published "
                            f"break to pin")
            low = label.lower()
            # one spelling per region within a round: 2014 prints "!karas" in
            # Table 3.4 and "!Karas" in Table 5.3; the first printing is kept
            label = spelling.setdefault(low, label)
            geo = "Total country" if low in _AREAS else label
            loc = low if low in ("urban", "rural") else "all"
            loc_label = label if loc != "all" else "Total"
            for (sex, c), v in cell.items():
                key = (geo, loc, sex)
                if c == "lf":
                    if key in lf_seen:
                        if abs(lf_seen[key] - v) > 0.5:
                            raise ValueError(
                                f"namibia_lfs_back {year} {label} {sex}: labour "
                                f"force {lf_seen[key]} vs {v} in two tables")
                        continue
                    lf_seen[key] = v
                topic, slabel, definition = _SPEC[c]
                rows.append(C.row(
                    topic=topic, value=v, series_label=slabel,
                    survey=f"Namibia Labour Force Survey {year}",
                    period=str(year), reference_period=str(year),
                    frequency="ad_hoc", working_age_base="15+",
                    definition=definition, sex=sex, geography=geo,
                    locality=loc, locality_label=loc_label,
                    series_code=code))
    return rows


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows, years = [], set()
    for p in [local_path] + list(extras or []):
        y = _year_of(p)
        if y in years:
            raise ValueError(f"namibia_lfs_back: two reports for {y}")
        years.add(y)
        rows += _read(p)
    return pd.DataFrame.from_records(rows)
