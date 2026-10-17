"""Zambia -- ZamStats Labour Force Survey BACK-SERIES 2017-2023, composition.

The same seven reports and the same front-matter "Selected Key Indicators of
the Labour Market by Sex and Rural/Urban" table that
unemployment/parsers/zambia_lfs_back.py reads for the headline status series.
This module opens only the COMPOSITION rows of that table, so no figure is
written twice:

    Sector of employment   Formal sector | Informal sector | Household sector
    Type of employment     Formal employment | Informal employment
    Industrial sector      Agriculture | Non-agriculture

Five figures each: Total | Male | Female | Rural | Urban (rural before urban in
every year). Counts of employed persons (market production activities, 15+).
Labels are normalised across the years' spellings ("Household" 2019-2021 =
"Household sector"; "Non agriculture" = "Non-agriculture"); 2024's report is
read by zambia_labour.py (status in employment only), so nothing collides.

SAME TABLE SHAPE, SAME READER as the unemployment module (label lines, then
five figures; a rule is tried against the label's shortest matching tail so
section headers fall away). It is repeated here rather than imported across
indicators, as every labour parser is self-contained.

PUBLISHED DEFECTS, pinned (never corrected):
* 2017 Informal Employment, Rural prints "876,43" -- a malformed figure. The
  cell is DROPPED, not guessed; the other four figures are kept.
* 2021 Formal sector prints Rural 1,065,821 and Urban 2,098,928 -- exactly the
  EMPLOYED totals for rural and urban, so the sector rows no longer sum. KEPT
  as published, and pinned by the checks below.
* Four more rows whose sexes or localities do not sum to the printed total
  (2017 Informal employment; 2021 Agriculture, Formal employment, Formal
  sector) -- listed with their figures at _KNOWN_BREAKS. Kept, pinned.
"""
from __future__ import annotations
import os
import re

import fitz
import pandas as pd

from . import _common as C

_YEARS = range(2017, 2024)

_RULES = [
    (r"formal sector", "formality", "Formal sector"),
    (r"informal sector", "formality", "Informal sector"),
    (r"household( sector)?", "formality", "Household sector"),
    (r"formal employment", "formality", "Formal employment"),
    (r"informal employment", "formality", "Informal employment"),
    (r"agriculture", "industry", "Agriculture"),
    (r"non[- ]?agriculture", "industry", "Non-agriculture"),
]
_COMPILED = [(re.compile(p, re.I), t, l) for p, t, l in _RULES]
_COLS = [("total", "all", "Total"), ("male", "all", "Total"),
         ("female", "all", "Total"), ("total", "rural", "Rural"),
         ("total", "urban", "Urban")]
_MODES = {"number", "percent", "hours", "zmw"}
_NUM = re.compile(r"^-?\d{1,3}(,\d{3})+$|^-?\d+(\.\d+)?$")
_BAD = re.compile(r"^\d{1,3}(,\d{1,3})+$")

# (year, characteristic, column index) of malformed published cells, dropped
_KNOWN_BAD_CELLS = {(2017, "Informal employment", 3)}

# (year, characteristic, check) of published arithmetic breaks, each read off
# the printed page:
#   2017 Informal employment  M 1,002,741 + F 811,588 = 1,814,329 vs 1,874,337
#   2021 Agriculture          R 569,430 + U 187,607 = 757,037 vs 747,036
#   2021 Formal employment    M 548,557 + F 263,856 = 812,413 vs 848,413
#   2021 Formal sector        M 653,048 + F 283,293 = 936,341 vs 936,941
#   2021 Formal sector        R/U print the employed totals (see docstring)
_KNOWN_BREAKS = {
    (2017, "Informal employment", "male+female"),
    (2021, "Agriculture", "rural+urban"),
    (2021, "Formal employment", "male+female"),
    (2021, "Formal sector", "male+female"),
    (2021, "Formal sector", "rural+urban"),
}


def _clean(s: str) -> str:
    s = s.replace("­", "").replace("�", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _summary_page(doc) -> int:
    for i, p in enumerate(doc):
        t = p.get_text()
        if (re.search(r"key indicators of\s+(the\s+)?labour market|summary of 20\d\d "
                      r"labour force survey", t, re.I)
                and re.search(r"unemployment rate", t, re.I)
                and re.search(r"\bRural\b", t) and re.search(r"\bUrban\b", t)
                and len(re.findall(r"\d{1,3}(?:,\d{3})+", t)) > 40):
            return i
    raise ValueError("zambia_lfs_back_labour: no key-indicators summary page")


def _walk(lines):
    label, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if _NUM.match(ln) or _BAD.match(ln):
            cells = []
            while i < len(lines) and len(cells) < 5 and (
                    _NUM.match(lines[i]) or _BAD.match(lines[i])):
                tok = lines[i]
                cells.append("BAD" if not _NUM.match(tok)
                             else float(tok.replace(",", "")))
                i += 1
            yield label, cells
            label = []
            continue
        if ln.lower() not in _MODES:
            label.append(ln)
        i += 1


def _classify(label_lines):
    for k in range(1, min(3, len(label_lines)) + 1):
        tail = _clean(" ".join(label_lines[-k:]))
        for rx, topic, char in _COMPILED:
            if rx.fullmatch(tail):
                return topic, char
    return None, None


def _year_of(path: str) -> int:
    m = re.search(r"(20\d\d)", os.path.basename(path))
    if not m or int(m.group(1)) not in _YEARS:
        raise ValueError(f"zambia_lfs_back_labour: no year 2017-2023 in {path!r}")
    return int(m.group(1))


def _read(path: str):
    year = _year_of(path)
    doc = fitz.open(path)
    lines = [l for l in (_clean(x) for x in
                         doc[_summary_page(doc)].get_text().splitlines()) if l]
    rows, bad, seen = [], set(), set()
    for label_lines, cells in _walk(lines):
        topic, char = _classify(label_lines)
        if topic is None:
            continue
        if char in seen:
            raise ValueError(f"zambia_lfs_back_labour {year}: {char!r} twice")
        seen.add(char)
        if len(cells) != 5:
            raise ValueError(f"zambia_lfs_back_labour {year}: {char!r} has "
                             f"{len(cells)} figures, expected 5")
        for j, v in enumerate(cells):
            if v == "BAD":
                bad.add((year, char, j))
                continue
            sex, loc, loc_label = _COLS[j]
            rows.append(C.row(
                topic=topic, characteristic=char,
                classification="National" if topic == "industry" else "Not applicable",
                value=v, survey=f"Labour Force Survey {year}", period=str(year),
                reference_period=str(year), frequency="annual",
                measure="count", unit="persons", sex=sex, locality=loc,
                locality_label=loc_label, working_age_base="15+",
                series_code=f"ZamStats LFS {year} key indicators"))
    if seen != {c for _, _, c in _RULES}:
        raise ValueError(f"zambia_lfs_back_labour {year}: rows {sorted(seen)}")
    want = {b for b in _KNOWN_BAD_CELLS if b[0] == year}
    if bad != want:
        raise ValueError(f"zambia_lfs_back_labour {year}: malformed cells {bad}, "
                         f"pinned {want}")
    return rows


def _check(df: pd.DataFrame) -> set:
    breaks = set()
    for (y, char), g in df.groupby(["period", "characteristic"]):
        s = {(r.sex, r.locality): r.value for r in g.itertuples()}
        t = s.get(("total", "all"))
        for name, parts in (("male+female", [("male", "all"), ("female", "all")]),
                            ("rural+urban", [("total", "rural"), ("total", "urban")])):
            if t is not None and all(p in s for p in parts) \
                    and abs(sum(s[p] for p in parts) - t) > 3:
                breaks.add((int(y), char, name))
    # NOT checked: that the three sectors sum to employment. They need not --
    # 2018's sectors sum to 2,947,813 against 2,948,971 employed (a remainder
    # not printed) -- while the type and agriculture pairs do sum exactly.
    return breaks


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows, years = [], set()
    for p in [local_path] + list(extras or []):
        y = _year_of(p)
        if y in years:
            raise ValueError(f"zambia_lfs_back_labour: two reports for {y}")
        years.add(y)
        rows += _read(p)
    df = pd.DataFrame.from_records(rows)
    breaks = _check(df)
    in_scope = {b for b in _KNOWN_BREAKS if b[0] in years}
    if breaks != in_scope:
        raise ValueError(f"zambia_lfs_back_labour: arithmetic breaks changed: "
                         f"new {sorted(breaks - in_scope)}, gone "
                         f"{sorted(in_scope - breaks)}")
    return df
