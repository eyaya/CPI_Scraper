"""Zambia -- monetary-poverty layout (ZamStats, 2022 Living Conditions
Monitoring Survey Report).

EVERY RESULT IN CHAPTER 12 IS A CHART. Its data labels reach the text layer,
but as a run of values followed by a run of category names, so pairing them
means inferring the series order -- not done (the Zimbabwe/Senegal rule). The
report's TABLES are in its annexes, and they carry the official series:

  Annex VI Table 7 / Annex VII Tables 14-15 (Swift methodology annex)
      national / rural / urban P0 on three lines -- Food, Lower, Upper -- for
      the official 2015 LCMS and for 2022
  Annex VIII  P0 on the lower (official) line, 10 provinces, 2015 and 2022

THE 2022 FIGURES ARE SWIFT IMPUTATIONS. The 2022 questionnaire changed, so
ZamStats estimated a 2015-comparable 2022 rate from the comparable part of
consumption (World Bank SWIFT). The official 2022 headline -- 60.0 national,
78.8 rural, 31.9 urban, 46.1 extreme -- is the "Swift (OLS)" column of Table 15
(fees treated as non-comparable), which Table 7 and Annex VIII confirm. That
is the column collected; the Deaton, PMM, "non-comparable" and "school fees
comparable" (Table 16) variants are model alternatives, not published rates.
The survey name says so, so a user can never mistake 2022 for a direct estimate.

Column order of Table 15 ("2015 official | Non-comparable | Swift (OLS) |
Swift (PMM) | Deaton" in value order) was established from Table 7, which
prints Official 54.4 | Swift 60.0 | Deaton 59.6 | Non-comparable 63.1, and
from the chapter-12 prose (extreme 46.1, rural 78.8, urban 31.9).

Lines (ZamStats' terms): the FOOD line is the extreme line; the LOWER line is
the official absolute ("total") poverty line; the UPPER line is a higher
alternative printed alongside. No line amounts are collected (they are given
per adult equivalent per month by province in Chapter 12 text only).

CROSS-CHECK (verbatim): 2015 official 54.4 / food 40.8 / upper 74.0; rural
76.6, urban 23.4; 2022 60.0 / food 46.1 / upper 79.4; rural 78.8 (food 64.6),
urban 31.9 (food 18.3); Muchinga 69.3 -> 82.6; Lusaka 20.2 -> 27.0.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_S15 = {"period": "2015", "survey": "LCMS 2015", "reference_period": "2015"}
_S22 = {"period": "2022", "survey": "LCMS 2022 (SWIFT OLS imputation, comparable with 2015)",
        "reference_period": "2022"}
_LINES = {
    "Food poverty line": {"line_level": "extreme", "line_name": "Food poverty line"},
    "Lower poverty line": {"line_level": "overall", "line_name": "Lower poverty line"},
    "Upper poverty line": {"line_level": "other", "line_name": "Upper poverty line"},
}
_AREA = {
    "NATIONAL": {},
    "RURAL": {"topic": "locality", "characteristic": "Rural", "locality": "rural", "locality_label": "Rural"},
    "URBAN": {"topic": "locality", "characteristic": "Urban", "locality": "urban", "locality_label": "Urban"},
}
_PROVINCES = ["Central", "Copperbelt", "Eastern", "Luapula", "Lusaka", "Muchinga",
              "Northern", "North Western", "Southern", "Western"]

LAYOUT = {
    "survey": _S22["survey"], "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall", "line_name": "Lower poverty line",
    "period": "2022", "reference_period": "2022",
    "tables": [],   # read by the bespoke parse below
}


def _row(value, survey, line, area=None, **kw):
    return C.row(metric="headcount", value=value, welfare_aggregate="consumption",
                 line_type="national", frequency="ad_hoc", **survey, **line,
                 **(area or {}), **kw)


def _area_blocks(lines, first, stop, take, n, survey):
    """Rows of one Annex VII table: area headings, then one line per poverty line."""
    out, area, inside = [], None, False
    for ln in lines:
        if re.match(first, ln):
            inside = True
            continue
        if inside and stop and re.match(stop, ln):
            break
        if not inside:
            continue
        if ln.strip() in _AREA:
            area = ln.strip()
            continue
        for name, line in _LINES.items():
            if ln.startswith(name) and area:
                nums = C.numbers_in(ln[len(name):])
                if len(nums) != n:
                    raise ValueError(f"zambia: {first!r} {area} {name}: {len(nums)} numbers, want {n}")
                out.append(_row(nums[take], survey, line, _AREA[area]))
    if len(out) != 9:
        raise ValueError(f"zambia: table {first!r} gave {len(out)} rows, want 9 (3 areas x 3 lines)")
    return out


def _pages(path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return [(p.crop((0, 0, p.width, p.height)).extract_text() or "") for p in pdf.pages]


def parse(path: str) -> pd.DataFrame:
    pages = _pages(path)
    rows: list[dict] = []

    t14 = [p for p in pages if "Table 14. Model predictions for 2015" in p and "Table 15:" in p]
    if len(t14) != 1:
        raise ValueError(f"zambia: Annex VII page with Tables 14-15 found {len(t14)} times")
    lines = [l.strip() for l in t14[0].splitlines()]
    # Table 14: the first column is the OFFICIAL 2015 estimate (seven values a row).
    rows += _area_blocks(lines, r"^Table 14\.", r"^Table 15:", 0, 7, _S15)
    # Table 15: 2015 official | Non-comparable | Swift (OLS) | Swift (PMM) | Deaton.
    rows += _area_blocks(lines, r"^Table 15:", None, 2, 5, _S22)

    ann = [p for p in pages if "ANNEX VIII: POVERTY ESTIMATES AT THE PROVINCE LEVEL" in p]
    if len(ann) != 1:
        raise ValueError(f"zambia: Annex VIII page found {len(ann)} times")
    seen = set()
    low = _LINES["Lower poverty line"]
    for ln in ann[0].splitlines()[ann[0].splitlines().index(
            next(l for l in ann[0].splitlines() if l.startswith("ANNEX VIII"))):]:
        ln = ln.strip()
        for prov in _PROVINCES:
            m = re.match(rf"^{prov}(?=\s+-?\d)", ln)
            if m and prov not in seen:
                nums = C.numbers_in(ln[m.end():].replace("*", " "))
                if len(nums) != 3:
                    raise ValueError(f"zambia: Annex VIII {prov}: {nums}")
                rows.append(_row(nums[0], _S15, low, geography=prov))
                rows.append(_row(nums[1], _S22, low, geography=prov))
                seen.add(prov)
    if len(seen) != 10:
        raise ValueError(f"zambia: Annex VIII gave {len(seen)} provinces, want 10")
    return pd.DataFrame.from_records(rows)
