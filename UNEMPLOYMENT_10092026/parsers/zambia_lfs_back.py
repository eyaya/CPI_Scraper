"""Zambia -- ZamStats Labour Force Survey BACK-SERIES, 2017-2023.

The current report (2024) is read by zambia_unemployment.py. This module reads
the seven earlier annual LFS reports, each through its own front-matter
"Selected Key Indicators of the Labour Market by Sex and Rural/Urban" table
(2023: "Summary of 2023 Labour Force Survey"). Every report is its own round;
nothing is interpolated between them.

ONE SHAPE, SEVEN SPELLINGS. Each table is a label followed by five figures --
Total | Male | Female | Rural | Urban (RURAL BEFORE URBAN in every year, as in
2024) -- with an optional "Number"/"Percent" mode column (2022-2023). Labels
wrap over lines and section headers ("Rates", "Type of Employment", "Not in
the Labour Force") sit on lines of their own, so a row is identified by trying
each rule against the label's LAST line, then its last two lines, and so on --
the shortest tail that fully matches a rule wins, which strips the section
headers without a list of them.

SAME CONCEPTS AS 2024, SAME LABELS. All seven rounds are 19th-ICLS reports
(employment = "market production activities", the potential labour force and
CRUPLF are published), the concepts the 2024 report uses. Where a row is the
same series the 2024 layout files, it carries the 2024 series_label ("Labour
force", "Unemployment rate", ...) so the series continues across rounds; the
year's own wording is kept in the per-year notes below.

THE YOUTH BAND IS IN EVERY YOUTH LABEL. 2017-2022 use the National Youth
Policy's 15-35 (2017 and 2022 print it in the labels; 2018-2021 print only
"Youth", and each report defines youth as 15-35: 2018 p.18, 2019 "youths aged
15-35", 2020 p.25, 2021 table titles "Unemployed Youths (15-35 years)").
2023 prints 15-24 and 19-34 explicitly (the 2024 report keeps 19-34). Bands are
never aligned to one another.

PUBLISHED DEFECTS, kept or dropped as stated, and pinned by the checks below:
* 2017 Informal Employment, Rural prints "876,43" -- a malformed figure. A
  composition row: labour/parsers/zambia_lfs_back_labour.py drops and pins it.
* 2021 Formal sector, Rural and Urban print 1,065,821 and 2,098,928 -- the
  EMPLOYED totals for rural and urban. That is a labour (composition) row,
  read by labour/parsers/zambia_lfs_back_labour.py, which pins it.
* 2018 "Total unemployed persons plus potential labour force" prints exactly
  2017's figures (2,077,889 ...); it is not read (no topic takes the numerator
  of LU3 as a count), so the repetition is noted, not filed.

NOT READ: total population (not a labour-force series), NEET counts (2017;
the schema's NEET topic is a rate), "Other Outside Labour Force" (2017; its
definition is not given), hours of work and earnings.
"""
from __future__ import annotations
import os
import re

import fitz
import pandas as pd

from . import _common as C

_YEARS = range(2017, 2024)
_YOUTH = {y: "15-35" for y in range(2017, 2023)}

# (rule regex, fullmatched against a normalised label tail) -> spec
# spec: topic, label (may use {band}), age (None | "youth" | "group1-2"),
#       definition
_RULES: list[tuple[str, dict]] = [
    (r"working[- ]age population,? 15 ?(years|yrs) or older",
     dict(topic="working_age_population",
          label="Working-age population 15 years or older")),
    (r"youth population \(age (\d\d)-(\d\d) years\)",
     dict(topic="working_age_population", age="groups",
          label="Youth population ({band} years)")),
    (r"labour force", dict(topic="labour_force", label="Labour force")),
    (r"youth \(lf\)", dict(topic="labour_force", age="youth",
                           label="Youth ({band} years) labour force")),
    (r"youth labour force \((\d\d)-(\d\d) years\)",
     dict(topic="labour_force", age="groups",
          label="Youth ({band} years) labour force")),
    (r"employed \(market production( activities)?\)",
     dict(topic="employed", label="Employed (market production activities)")),
    (r"youth employed \(market production activities\)",
     dict(topic="employed", age="youth",
          label="Youth ({band} years) employed (market production activities)")),
    (r"youth \((\d\d)-(\d\d) years\) employed \(market production activities\)",
     dict(topic="employed", age="groups",
          label="Youth ({band} years) employed (market production activities)")),
    (r"unemployed( population| persons)?|total unemployed persons",
     dict(topic="unemployed", label="Unemployed population")),
    (r"youth unemployment",
     dict(topic="unemployed", age="youth",
          label="Youth ({band} years) unemployed population")),
    (r"youth unemployed persons \((\d\d)-(\d\d) years\)",
     dict(topic="unemployed", age="groups",
          label="Youth ({band} years) unemployed population")),
    (r"youth \((\d\d)-(\d\d) years\) unemployed population",
     dict(topic="unemployed", age="groups",
          label="Youth ({band} years) unemployed population")),
    (r"potential labour force( \(plf\))?",
     dict(topic="potential_labour_force", label="Potential labour force (PLF)")),
    (r"youth potential labour force",
     dict(topic="potential_labour_force", age="youth",
          label="Youth ({band} years) potential labour force")),
    (r"youth \((\d\d)-(\d\d) years\) potential labour force \(yplf\)",
     dict(topic="potential_labour_force", age="groups",
          label="Youth ({band} years) potential labour force")),
    (r"(population )?outside the labour force|total population not in the labour force",
     dict(topic="outside_labour_force",
          label="Population outside the labour force")),
    (r"employment[- ]to[- ]population ratio",
     dict(topic="employment_to_population_ratio",
          label="Employment-to-population ratio")),
    (r"labour force participation rate",
     dict(topic="labour_force_participation_rate", definition="strict",
          label="Labour force participation rate")),
    (r"unemployment rate",
     dict(topic="unemployment_rate", definition="strict",
          label="Unemployment rate")),
    (r"youth unemployment rate",
     dict(topic="youth_unemployment_rate", definition="strict", age="youth",
          label="Youth ({band} years) unemployment rate")),
    (r"youth \((\d\d)-(\d\d) years\) unemployment rate",
     dict(topic="youth_unemployment_rate", definition="strict", age="groups",
          label="Youth ({band} years) unemployment rate")),
    (r"time[- ]related underemployment rate",
     dict(topic="underemployment_rate",
          label="Time-related underemployment rate")),
    (r"cruplf|combined rate of unemployment and potential labour force \(cruplf\)",
     dict(topic="labour_underutilisation_rate", definition="broad",
          label="Combined rate of unemployment and potential labour force (CRUPLF)")),
    (r"youth cruplf",
     dict(topic="labour_underutilisation_rate", definition="broad", age="youth",
          label="Youth ({band} years) combined rate of unemployment and "
                "potential labour force (YCRUPLF)")),
    (r"youth \((\d\d)-(\d\d) years\) combined rate of unemployment and "
     r"potential labour force \(ycruplf\)",
     dict(topic="labour_underutilisation_rate", definition="broad",
          age="groups",
          label="Youth ({band} years) combined rate of unemployment and "
                "potential labour force (YCRUPLF)")),
]
_COMPILED = [(re.compile(p, re.I), s) for p, s in _RULES]

_COLS = [("total", "all", "Total"), ("male", "all", "Total"),
         ("female", "all", "Total"), ("total", "rural", "Rural"),
         ("total", "urban", "Urban")]
_MODES = {"number", "percent", "hours", "zmw"}
_NUM = re.compile(r"^-?\d{1,3}(,\d{3})+$|^-?\d+(\.\d+)?$")
_BAD = re.compile(r"^\d{1,3}(,\d{1,3})+$")      # "876,43": malformed grouping

# Published malformed cells in rows THIS module reads, dropped and pinned:
# (year, label tail, column index). The one known malformed cell (2017
# Informal Employment, Rural) is a composition row, pinned in the labour module.
_KNOWN_BAD_CELLS: set = set()


# PUBLISHED, PINNED (checked on the printed pages, never corrected):
# * 2022 Youth (15-35) unemployed: Rural 116,117 + Urban 257,657 = 373,774
#   against Total 380,968.
# * 2023 Youth (15-24) employed: Rural 270,581 + Urban 288,842 = 559,423
#   against Total 553,965.
_KNOWN_BREAKS = {
    (("2022", "Youth (15-35 years) unemployed population", "15-35"), "total/total"),
    (("2023", "Youth (15-24 years) employed (market production activities)",
      "15-24"), "total/total"),
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
    raise ValueError("zambia_lfs_back: no key-indicators summary page")


def walk(lines: list[str]):
    """Yield (label_lines, [5 cells]) where a cell is a float, None (dash) or
    the string 'BAD' (a malformed figure)."""
    label: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if _NUM.match(ln) or _BAD.match(ln):
            cells = []
            while i < len(lines) and len(cells) < 5 and (
                    _NUM.match(lines[i]) or _BAD.match(lines[i])):
                tok = lines[i]
                cells.append("BAD" if (_BAD.match(tok) and not _NUM.match(tok))
                             else float(tok.replace(",", "")))
                i += 1
            yield label, cells
            label = []
            continue
        if ln.lower() not in _MODES:
            label.append(ln)
        i += 1


def classify(label_lines: list[str], rules=None):
    rules = rules or _COMPILED
    for k in range(1, min(4, len(label_lines)) + 1):
        tail = _clean(" ".join(label_lines[-k:]))
        for rx, spec in rules:
            m = rx.fullmatch(tail)
            if m:
                return tail, spec, m
    return None, None, None


def _year_of(path: str) -> int:
    m = re.search(r"(20\d\d)", os.path.basename(path))
    if not m or int(m.group(1)) not in _YEARS:
        raise ValueError(f"zambia_lfs_back: no report year 2017-2023 in {path!r}")
    return int(m.group(1))


def _read(path: str) -> list[dict]:
    year = _year_of(path)
    doc = fitz.open(path)
    pg = _summary_page(doc)
    lines = [_clean(l) for l in doc[pg].get_text().splitlines()]
    lines = [l for l in lines if l]
    rows, bad = [], set()
    for label_lines, cells in walk(lines):
        tail, spec, m = classify(label_lines)
        if spec is None:
            continue
        if len(cells) != 5:
            raise ValueError(f"zambia_lfs_back {year}: {tail!r} has {len(cells)} "
                             f"figures, expected 5")
        band, age = "", "Total"
        if spec.get("age") == "youth":
            band = _YOUTH[year]
        elif spec.get("age") == "groups":
            band = f"{m.group(m.lastindex - 1)}-{m.group(m.lastindex)}"
        if band:
            age = band
        label = spec["label"].format(band=band)
        for j, v in enumerate(cells):
            if v == "BAD":
                bad.add((year, tail, j))
                continue
            sex, loc, loc_label = _COLS[j]
            rows.append(C.row(
                topic=spec["topic"], value=v, series_label=label,
                survey=f"Labour Force Survey {year}", period=str(year),
                reference_period=str(year), frequency="annual",
                working_age_base="15+",
                definition=spec.get("definition", "not_applicable"),
                sex=sex, age_group=age, locality=loc, locality_label=loc_label,
                series_code=f"ZamStats LFS {year} key indicators"))
    want_bad = {b for b in _KNOWN_BAD_CELLS if b[0] == year}
    if bad != want_bad:
        raise ValueError(f"zambia_lfs_back {year}: malformed cells {bad}, "
                         f"pinned {want_bad}")
    return rows


def _check(df: pd.DataFrame) -> None:
    """Arithmetic the tables publish: LF = employed + unemployed, WAP = LF +
    outside, male + female = total, rural + urban = total. Rounding of up to 3
    persons is allowed; anything else raises (pin it here if it is published)."""
    cnt = df[df["measure"] == "count"]
    v = cnt.pivot_table(index=["period", "sex", "locality", "age_group"],
                        columns="series_label", values="value", aggfunc="first")
    bad = []
    for (a, b, c) in [("Labour force", "Employed (market production activities)",
                       "Unemployed population"),
                      ("Working-age population 15 years or older", "Labour force",
                       "Population outside the labour force")]:
        if {a, b, c} <= set(v.columns):
            g = (v[a] - v[b] - v[c]).dropna()
            bad += [(i, a) for i in g[g.abs() > 3].index]
    for lab, grp in cnt.groupby(["period", "series_label", "age_group"]):
        s = {(r.sex, r.locality): r.value for r in grp.itertuples()}
        t = s.get(("total", "all"))
        if t is None:
            continue
        for parts in ((("male", "all"), ("female", "all")),
                      (("total", "rural"), ("total", "urban"))):
            if all(p in s for p in parts) and abs(sum(s[p] for p in parts) - t) > 3:
                bad.append((lab, parts[0][0] + "/" + parts[1][0]))
    if set(bad) != _KNOWN_BREAKS:
        raise ValueError(f"zambia_lfs_back: published arithmetic breaks changed: "
                         f"new {sorted(set(bad) - _KNOWN_BREAKS)[:6]}, gone "
                         f"{sorted(_KNOWN_BREAKS - set(bad))} -- verify against "
                         f"the PDF and pin")


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    paths = [local_path] + list(extras or [])
    rows, years = [], []
    for p in paths:
        y = _year_of(p)
        if y in years:
            raise ValueError(f"zambia_lfs_back: two reports for {y}")
        years.append(y)
        rows += _read(p)
    df = pd.DataFrame.from_records(rows)
    _check(df)
    return df
