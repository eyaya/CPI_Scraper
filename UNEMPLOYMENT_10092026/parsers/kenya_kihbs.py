"""Kenya -- KNBS 2015/16 KIHBS Labour Force Basic Report, headline tables.

A HOUSEHOLD survey (the Kenya Integrated Household Budget Survey, fieldwork
September 2015 - August 2016), base 15-64, figures in THOUSANDS ("000'").
It is the only Kenyan household source before the QLFS began in 2019, and it
publishes what the QLFS does not: the 2016 headline by age cohort, by sex and
by residence.

Three tables, read from the text layer:

* Table 3.3  employment-to-population ratio by age, for Total / Rural / Urban
             (population and employed counts beside it);
* Table 3.6  labour force participation by age, for Total / Male / Female
             (population and active counts beside it);
* Table 3.17 the labour force by age: employed and unemployed by sex, and the
             unemployment rate (strict -- "not working, available and looking
             for work").

EVERY ROW IS HELD TO ITS OWN ARITHMETIC before it is emitted: ratio = employed
/ population, participation = active / population, employed and unemployed
male + female = total, employed + unemployed = labour force, and the rate =
unemployed / labour force -- each to rounding. A row that fails raises.

NOT READ:
  * Table 3.3's "Employment Ratio 2009" column -- printed for comparison, with
    no source named for it beside the table (the 2009 census, presumably);
    publishing it under this survey would mislabel it.
  * Table 3.19 (LU2) and most of the report's later pages: the text layer
    holds the page TWICE, interleaved ("2105--2149 2,13,2318.46.1 ..."), as
    NSA Namibia's census did. The clean copy of a row sits next to a fused
    one and no rule can tell them apart without guessing.
  * Male/female rates by age in 3.17 are not printed (only counts by sex), and
    none are computed.

The same population and employed totals print in more than one table; they
must agree, and each is emitted once.

CROSS-CHECK (15-64): population 24,955.5 thousand; labour force 19,311.4;
employed 17,875.7; unemployed 1,435.8; unemployment rate 7.4% (20-24: 19.2%);
participation 77.4% (male 79.2, female 75.6); employment ratio 71.6% (rural
73.2, urban 69.4).
"""
from __future__ import annotations

import re

import pdfplumber

from . import _common as C

_SURVEY = "Kenya Integrated Household Budget Survey (KIHBS) 2015/16 - Labour Force Basic Report"
_BASE = dict(survey=_SURVEY, period="2016", reference_period="2015/16",
             frequency="ad_hoc", working_age_base="15-64")
_AGES = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49",
         "50-54", "55-59", "60-64", "Total"]
_ROW = re.compile(r"^(\d{2}-\d{2}|Total)\s+((?:[\d,]+\.\d\s*){3,8})$")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _page(pdf, caption: str) -> list[str]:
    """Lines of the page holding the table's printed caption (not the list of
    tables, whose entry ends in dot leaders and a page number)."""
    rx = re.compile(caption)
    for page in pdf.pages:
        text = page.extract_text() or ""
        for m in rx.finditer(text):
            tail = text[m.end():m.end() + 120].split("\n")[0]
            if not re.search(r"\.{4}", tail):
                return [ln.strip() for ln in text[m.start():].splitlines()]
    raise ValueError(f"KIHBS: {caption!r} not found")


def _blocks(lines: list[str], heads: list[str], width: int) -> dict[str, dict]:
    """{block heading: {age: values}} for a table stacked in blocks."""
    out, cur = {}, heads[0]
    out[cur] = {}
    for ln in lines:
        if ln in heads[1:]:
            cur = ln
            out[cur] = {}
            continue
        m = _ROW.match(ln)
        if m and m.group(1) not in out[cur]:
            vals = [_num(v) for v in m.group(2).split()]
            if len(vals) != width:
                raise ValueError(f"KIHBS: {ln!r} has {len(vals)} values, "
                                 f"expected {width}")
            out[cur][m.group(1)] = vals
        if len(out) == len(heads) and len(out[cur]) == len(_AGES):
            break
    for h in heads:
        got = list(out.get(h, {}))
        if got != _AGES:
            raise ValueError(f"KIHBS: block {h!r} read {got}")
    return out


def _close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def parse(path: str):
    import pandas as pd
    rows: list[dict] = []

    def emit(topic, label, value, measure, unit, definition="not_applicable",
             **ctx):
        rows.append(C.row(topic=topic, definition=definition,
                          series_label=label, value=value, measure=measure,
                          unit=unit, series_code="KIHBS 2015/16", **_BASE, **ctx))

    with pdfplumber.open(path) as pdf:
        # --- Table 3.3: employment ratio, Total / Rural / Urban -------------
        t33 = _blocks(_page(pdf, r"Table 3\.3: Distribution of Working Age Population"),
                      ["Total", "Rural", "Urban"], 4)
        # --- Table 3.6: participation, Total / Male / Female -----------------
        # Table 3.6's own caption is doubled glyph by glyph in the text layer
        # ("TaTabblele 3 3.6.6: :P Paart..."), so it is found by its column
        # header, which is clean and unique to it.
        t36 = _blocks(_page(pdf, r"Active Participation"),
                      ["Total", "Male", "Female"], 3)
        # --- Table 3.17: labour force, employed / unemployed by sex ----------
        t317 = _blocks(_page(pdf, r"Table 3\.17: Distribution of Labour Force"),
                       ["Total"], 8)["Total"]

    loc = {"Total": {}, "Rural": {"locality": "rural", "locality_label": "Rural"},
           "Urban": {"locality": "urban", "locality_label": "Urban"}}
    sex = {"Total": {}, "Male": {"sex": "male"}, "Female": {"sex": "female"}}

    for blk, by_age in t33.items():
        for age, (pop, emp, ratio, _ratio_2009) in by_age.items():
            if not _close(100 * emp / pop, ratio, 0.1):
                raise ValueError(f"KIHBS 3.3 {blk} {age}: {ratio} != {emp}/{pop}")
            ctx = {**loc[blk], "age_group": age}
            emit("working_age_population", "Population (15-64)", pop,
                 "count", "thousand_persons", **ctx)
            emit("employed", "Employed", emp, "count", "thousand_persons", **ctx)
            emit("employment_to_population_ratio", "Employment Ratio 2016",
                 ratio, "rate", "percent", **ctx)

    for blk, by_age in t36.items():
        for age, (pop, active, rate) in by_age.items():
            if not _close(100 * active / pop, rate, 0.1):
                raise ValueError(f"KIHBS 3.6 {blk} {age}: {rate} != {active}/{pop}")
            if blk == "Total" and not _close(pop, t33["Total"][age][0], 0.05):
                raise ValueError(f"KIHBS 3.6 {age}: population disagrees with 3.3")
            ctx = {**sex[blk], "age_group": age}
            if blk != "Total":       # Total's population is Table 3.3's
                emit("working_age_population", "Population (15-64)", pop,
                     "count", "thousand_persons", **ctx)
            emit("labour_force", "Active Population", active, "count",
                 "thousand_persons", definition="strict", **ctx)
            emit("labour_force_participation_rate", "Participation Rate", rate,
                 "rate", "percent", definition="strict", **ctx)

    for age, (lf, em, ef, et, um, uf, ut, rate) in t317.items():
        if not (_close(em + ef, et, 0.15) and _close(um + uf, ut, 0.15)
                and _close(et + ut, lf, 0.15)
                and _close(100 * ut / lf, rate, 0.1)):
            raise ValueError(f"KIHBS 3.17 {age}: counts do not add up "
                             f"({lf}, {em}+{ef}={et}, {um}+{uf}={ut}, {rate})")
        if not (_close(lf, t36["Total"][age][1], 0.05)
                and _close(et, t33["Total"][age][1], 0.05)):
            raise ValueError(f"KIHBS 3.17 {age}: totals disagree with 3.3/3.6")
        ctx = {"age_group": age}
        for s, e, u in (("male", em, um), ("female", ef, uf)):
            emit("employed", "Employed", e, "count", "thousand_persons",
                 sex=s, **ctx)
            emit("unemployed", "Unemployed", u, "count", "thousand_persons",
                 definition="strict", sex=s, **ctx)
        emit("unemployed", "Unemployed", ut, "count", "thousand_persons",
             definition="strict", **ctx)
        emit("unemployment_rate", "Unemployment Rate", rate, "rate", "percent",
             definition="strict", **ctx)
    return pd.DataFrame(rows)
