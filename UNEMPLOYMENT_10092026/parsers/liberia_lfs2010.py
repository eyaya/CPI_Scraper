"""Liberia — LISGIS / Ministry of Labour, Labour Force Survey 2010 (fieldwork
February to May 2010), the round before the 2016-17 LFS that
`liberia_unemployment` reads. Added 2026-10-12.

* Table 3.4  labour force participation rates by sex x age group, for Urban /
             Rural / Liberia. Its columns are age bands 5-14 ... 65+, then
             "Total" (all persons 5 and over), "15+" and "15-64". The 5-14 band
             and the "Total" column are on a 5+ base and are labelled so; the
             15+ column is the headline (age_group Total, base 15+).
* Table 6.1  the unemployed (counts) and unemployment rates by sex x age group
             for Urban / Rural / Liberia -- the report's RELAXED definition
             (job search not required), so `definition: broad`. The report
             gives no strict-definition rate table; Table 6.3 counts the
             strict unemployed only by search method.

Counts are printed rounded to thousands; "*" is a missing cell (fewer than
500), never 0.

CROSS-CHECK: LFPR 15+ Liberia total 62.8 (urban 54.9, rural 71.2); unemployment
rate total 3.7 (urban 5.5, rural 2.3; women 4.1); unemployed 42,000.
"""
from __future__ import annotations

import re

import pdfplumber

SURVEY = "Liberia Labour Force Survey 2010"
_BASE = dict(survey=SURVEY, education="Total", geography="Total country",
             period="2010", reference_period="February-May 2010",
             frequency="ad_hoc")
_CELL = r"(?:[\d,]+(?:\.\d+)?|\*|‐|-)"
_LOC = {"Urban": ("urban", "Urban"), "Rural": ("rural", "Rural"),
        "Liberia": ("all", "Total")}
_SEX = {"Male": "male", "Female": "female", "Total": "total"}


def _num(tok):
    return None if tok in ("*", "‐", "-") else float(tok.replace(",", ""))


def _page(pages, caption):
    for t in pages:
        m = re.search(caption, t, re.M)
        if m:
            return [ln.strip() for ln in t[m.end():].splitlines()]
    raise ValueError(f"LBR LFS 2010: {caption!r} not found")


def _table_3_4(pages):
    lines = _page(pages, r"^Table 3\.4 Labour force participation rates, by sex, age group and locality")
    head = next(ln for ln in lines if ln.startswith("5‐14") or ln.startswith("5-14"))
    cols = head.replace("‐", "-").split()
    if cols != ["5-14", "15-24", "25-34", "35-54", "55-64", "65+", "Total", "15+", "15-64"]:
        raise ValueError(f"LBR 2010 T3.4: header {cols}")
    row = re.compile(rf"^(Male|Female|Total)\s+((?:{_CELL}\s+){{8}}{_CELL})$")
    out, loc = [], None
    for ln in lines:
        if ln in _LOC:
            loc = _LOC[ln]
            continue
        m = row.match(ln)
        if not m or loc is None:
            continue
        for col, tok in zip(cols, m.group(2).split()):
            v = _num(tok)
            if v is None:
                continue
            if col == "15+":
                age, base = "Total", "15+"
            elif col == "Total":
                age, base = "Total (5 and over)", "5+"
            elif col == "5-14":
                age, base = "5-14", "5+"
            else:
                age, base = col, "15+"
            out.append(dict(_BASE, topic="labour_force_participation_rate",
                            definition="not_applicable",
                            series_label="Labour force participation rate",
                            sex=_SEX[m.group(1)], age_group=age,
                            locality=loc[0], locality_label=loc[1],
                            working_age_base=base, measure="rate", value=v,
                            unit="percent", series_code="LBR-LFS2010 T3.4"))
        if loc[0] == "all" and m.group(1) == "Total":
            break
    if len(out) < 80:
        raise ValueError(f"LBR 2010 T3.4: only {len(out)} cells read")
    return out


def _table_6_1(pages):
    lines = _page(pages, r"^Table 6\.1 The unemployed, and unemployment rates")
    row = re.compile(rf"^(15.24|25.34|35.54|55.64|65\+|Total)\s+((?:{_CELL}\s+){{8}}{_CELL})$")
    cols = [(loc, lab, sex) for loc, lab in (("urban", "Urban"), ("rural", "Rural"),
                                             ("all", "Total"))
            for sex in ("male", "female", "total")]
    out, block = [], "count"
    for ln in lines:
        if "Unemployment rates" in ln:
            block = "rate"
            continue
        m = row.match(ln)
        if not m:
            continue
        age = m.group(1).replace("‐", "-")
        for (loc, lab, sex), tok in zip(cols, m.group(2).split()):
            v = _num(tok)
            if v is None:
                continue
            if block == "count":
                rec = dict(topic="unemployed", definition="broad",
                           series_label="Unemployed (relaxed definition)",
                           measure="count", unit="persons")
            else:
                rec = dict(topic="unemployment_rate", definition="broad",
                           series_label="Unemployment rate (relaxed definition)",
                           measure="rate", unit="percent")
            out.append(dict(_BASE, **rec, sex=sex,
                            age_group="Total" if age == "Total" else age,
                            locality=loc, locality_label=lab,
                            working_age_base="15+", value=v,
                            series_code="LBR-LFS2010 T6.1"))
        if age == "Total" and block == "rate":
            break
    if len(out) < 80:
        raise ValueError(f"LBR 2010 T6.1: only {len(out)} cells read")
    return out


def parse_2010(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages[38:75]]
    return _table_3_4(pages) + _table_6_1(pages)
