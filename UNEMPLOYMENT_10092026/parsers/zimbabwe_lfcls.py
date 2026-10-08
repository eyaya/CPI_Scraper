"""Zimbabwe -- ZIMSTAT 2019 Labour Force and Child Labour Survey (LFCLS),
annual report: headline tables by age group, area and sex.

The quarterly QLFS the main descriptor follows prints one key-findings table.
The 2019 annual round prints the same headline as cross-tabs, and three of
them share a shape -- a block per area, then one row per age group of

    (denominator, numerator, rate) x Male | Female | Total

* Table 3.6b  population, labour force, LFPR      -> participation
* Table 4.2   population, employed, EPR           -> employment ratio
* Table 9.6   extended LF, unemployed + potential LF, combined rate -> LU3

THE COUNTS USE SPACE THOUSANDS ("542 908 104 837 19.3"), which reads more than
one way. Each (denominator, numerator) pair is split the ONE way that
reproduces the printed rate to rounding, and a row with no such split, or two,
raises. That is also the guard against a column misread: a wrong pairing does
not reproduce its rate.

Base: 15+ ("Persons Age 15 Years and Above") for these tables, unlike the
QLFS's 16+ -- carried on every row. Period 2019 (fieldwork 5 June - 7 July
2019, the same reference the labour/ indicator uses for this report).

NOT READ: Tables 9.1-9.5 distribute the unemployed rather than state a rate
by group in this shape; chapter 10's youth tables repeat the age bands above.
"""
from __future__ import annotations

import itertools
import re

import pdfplumber

from . import _common as C

_BASE = dict(survey="Labour Force and Child Labour Survey (LFCLS) 2019",
             period="2019", reference_period="LFCLS 2019 (5 June - 7 July 2019)",
             frequency="ad_hoc", working_age_base="15+")
_AREAS = {"Rural": {"locality": "rural", "locality_label": "Rural"},
          "Urban": {"locality": "urban", "locality_label": "Urban"},
          "Total": {}, "Zimbabwe": {}, "National": {}}
_AGE = re.compile(r"^(\d{2}\s*-\s*\d{2}|65\s*\+|Total(?: [A-Za-z ]+?)?)\s+(\d[\d .]*)$")

# caption -> (denominator topic/def/label, numerator topic/def/label,
#             rate topic/def/label)
TABLES = {
    r"Table 3\.6b: Labour Force Participation Rate by Age Group, Area and Sex": (
        ("working_age_population", None, "Population"),
        ("labour_force", "strict", "Labour Force"),
        ("labour_force_participation_rate", "strict", "LFPR")),
    r"Table 4\.2: Employment to Population Ratio \(EPR\) by Age Group, Area and Sex": (
        ("working_age_population", None, "Population"),
        ("employed", None, "Employed"),
        ("employment_to_population_ratio", None, "EPR")),
}


def _split(groups: list[str], rate: float) -> tuple[float, float]:
    """(denominator, numerator) from space-separated digit groups, the one way
    that reproduces `rate`."""
    hits = []
    for cut in range(1, len(groups)):
        a, b = groups[:cut], groups[cut:]
        if any(len(g) != 3 for g in a[1:] + b[1:]) or len(a[0]) > 3 or len(b[0]) > 3:
            continue
        den, num = int("".join(a)), int("".join(b))
        if den and abs(100 * num / den - rate) <= 0.06:
            hits.append((float(den), float(num)))
    if len(hits) != 1:
        raise ValueError(f"LFCLS: {groups} with rate {rate} splits {len(hits)} ways")
    return hits[0]


def _row(text: str) -> list[tuple[float, float, float]]:
    toks = text.split()
    cells, groups = [], []
    for t in toks:
        if "." in t:
            den, num = _split(groups, float(t))
            cells.append((den, num, float(t)))
            groups = []
        else:
            groups.append(t)
    if groups or len(cells) != 3:
        raise ValueError(f"LFCLS: cannot read {text!r}")
    return cells


def _table(pages, caption: str, spec) -> list[dict]:
    rx = re.compile(caption)
    start = next((i for i, t in enumerate(pages) if rx.search(t)
                  and not re.search(r"\.{4}", t[rx.search(t).end():][:60])), None)
    if start is None:
        raise ValueError(f"LFCLS: {caption!r} not found")
    text = "\n".join(pages[start:start + 2])
    text = text[rx.search(text).end():]
    out, area, seen = [], None, set()
    for ln in text.splitlines():
        ln = ln.strip()
        if ln in _AREAS:
            area = ln
            continue
        if ln.startswith(("Source", "Table ")) and area and len(seen) >= 20:
            break
        m = _AGE.match(ln)
        if not m or area is None:
            continue
        age = re.sub(r"\s+", "", m.group(1)) if m.group(1)[0].isdigit() else "Total"
        key = (area, age)
        if key in seen:
            continue
        seen.add(key)
        for sex, (den, num, rate) in zip(("male", "female", "total"), _row(m.group(2))):
            ctx = {**_AREAS[area], "sex": sex, "age_group": age}
            for (topic, defn, label), val, meas, unit in (
                    (spec[0], den, "count", "persons"),
                    (spec[1], num, "count", "persons"),
                    (spec[2], rate, "rate", "percent")):
                out.append(C.row(topic=topic, definition=defn or "not_applicable",
                                 series_label=label, value=val, measure=meas,
                                 unit=unit, series_code="LFCLS 2019", **_BASE, **ctx))
    areas = {a for a, _ in seen}
    if len(seen) < 24 or not {"Rural", "Urban"} <= areas:
        raise ValueError(f"LFCLS {caption}: read {sorted(seen)}")
    return out


def parse(path: str):
    import pandas as pd
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages[70:95]]
    rows = []
    for caption, spec in TABLES.items():
        rows += _table(pages, caption, spec)
    df = pd.DataFrame(rows)
    # Both tables print the working-age population; they must agree, and it is
    # emitted once.
    key = ["topic", "sex", "age_group", "locality"]
    pop = df[df.topic == "working_age_population"]
    clash = pop.groupby(key).value.nunique()
    if (clash > 1).any():
        raise ValueError(f"LFCLS: 3.6b and 4.2 disagree on population: "
                         f"{clash[clash > 1].index.tolist()[:5]}")
    return df.drop_duplicates(subset=key + ["series_label", "measure"]).reset_index(drop=True)
