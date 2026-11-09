"""Malawi -- monetary-poverty layout (NSO, Monetary Poverty and Inequality
Report, IHS6 2024/25, published October 2026).

Cost of Basic Needs; welfare = real per-capita consumption; person-weighted.
Two lines, both per person per day in each round's own nominal prices:
  total poverty line   IHS6 MWK 1,562.6   IHS5 MWK 454.5
  food = ULTRA-poverty line  IHS6 MWK 1,071.1   IHS5 MWK 277.5
The report says outright that the nominal lines are not a welfare comparison;
the HEADCOUNTS are presented as comparable (IHS5 reproduced from the 2020
Malawi Poverty Report).

TEXT LAYER: at pdfplumber's default x_tolerance the words run together
("NkhataBay", "RuralNorth"); x_tolerance=1 restores the printed spacing, so
this module builds its own page text and runs the shared table reader on it.

Collected
  Table 1      national P0, P1, P2 on both lines, IHS5 and IHS6
  Table B.1    P0 with 95% CI by urban/rural, rural region and 32 districts,
               IHS5 and IHS6 (IHS5 national row skipped: it prints the
               appendix's 50.8 where Table 1 and the main series give 50.7 --
               one published figure per key, and the report calls 50.7 the
               main-results series)
  Table B.2    the same on the ultra-poverty line. IHS5 CIs are NOT taken:
               they use a symmetric approximation and print NEGATIVE lower
               bounds (Nkhata Bay -0.3), which no rescaling would make honest.
  Table B.3    IHS6 P0 and ultra-P0 by the three regions, and population
               share / share of the poor / share of the ultra-poor for
               urban/rural, regions and districts
Not collected: standard errors; Figures 4.5-4.19 (sex of head, household
size, P1/P2 by residence -- charts only); Gini and consumption tables
(inequality, a separate indicator).

CROSS-CHECK (verbatim): P0 47.3 (IHS6) / 50.7 (IHS5); ultra 24.0 / 20.5;
P1 15.7 / 17.0; P2 7.1 / 7.6; ultra P1 6.4 / 4.8; ultra P2 2.5 / 1.7;
rural 52.6, urban 20.9; Southern Region 55.8; Rural South 62.3 (ultra 35.0);
Mulanje 77.5, Blantyre City 17.2; Rural Centre IHS5 62.8 CI 61.1-64.4.
"""
from __future__ import annotations

import pandas as pd

from . import poverty_tables as T

_IHS5 = {"period": "2019", "survey": "IHS5 2019/20", "reference_period": "2019/20",
         "line_value": 454.5}
_IHS6 = {"period": "2024", "survey": "IHS6 2024/25", "reference_period": "2024/25",
         "line_value": 1562.6}
_X = {"line_level": "extreme", "line_name": "Food (ultra-)poverty line"}
_IHS5X = {**_IHS5, **_X, "line_value": 277.5}
_IHS6X = {**_IHS6, **_X, "line_value": 1071.1}
_SKIP = {"skip": True}


def _est_ci(year: dict, ci: bool = True):
    """Estimate | Std. error | CI lower | CI upper."""
    if not ci:
        return [{"metric": "headcount", **year}, _SKIP, _SKIP, _SKIP]
    return [{"metric": "headcount", **year}, _SKIP,
            {"metric": "headcount_ci_low", **year}, {"metric": "headcount_ci_high", **year}]


def _rural(label: str, region: str) -> dict:
    # "Rural North" = the rural part of the Northern Region: the region goes in
    # `geography`, so the stratum is plainly "Rural" there (and codes as RUR).
    return {"match": rf"^{label}(?=\s+\d)", "topic": "locality", "locality": "rural",
            "locality_label": "Rural", "geography": region}


_LOC_ROWS = [
    {"match": r"^Rural(?=\s+\d)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
    {"match": r"^Urban(?=\s+\d)", "topic": "locality", "locality": "urban", "locality_label": "Urban"},
    _rural("Rural North", "Northern Region"),
    _rural("Rural Centre", "Central Region"),
    _rural("Rural South", "Southern Region"),
]


def _b12(caption: str, five, six):
    """B.1 / B.2: the urban/rural and rural-region rows, then the 32 districts.
    The national row is read separately (its estimate comes from Table 1)."""
    cols = five + six
    return [
        {"page_contains": [caption], "exact_numbers": True, "columns": cols, "rows": _LOC_ROWS},
        {"page_contains": [caption], "start": r"^District$", "columns": cols,
         "row_scan": {"expect_rows": 32}},
    ]


LAYOUT = {
    "survey": "IHS6 2024/25", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall", "line_name": "Total poverty line",
    "line_unit": "MWK per person per day (nominal, survey prices)",
    "period": "2024", "reference_period": "2024/25",
    "tables": [
        {   # Table 1 -- results summary (IHS5 | IHS6 | change)
            "page_contains": ["table 1: results summary"],
            "columns": [{"metric": "headcount", **_IHS5}, {"metric": "headcount", **_IHS6}],
            "rows": [
                {"match": r"^Poverty headcount \(%\)"},
                {"match": r"^Ultra-poverty headcount \(%\)", "columns": [
                    {"metric": "headcount", **_IHS5X}, {"metric": "headcount", **_IHS6X}]},
                {"match": r"^Poverty gap \(%\)", "columns": [
                    {"metric": "gap", **_IHS5}, {"metric": "gap", **_IHS6}]},
                {"match": r"^Squared poverty gap \(%\)", "columns": [
                    {"metric": "severity", **_IHS5}, {"metric": "severity", **_IHS6}]},
                {"match": r"^Ultra-poverty gap \(%\)", "columns": [
                    {"metric": "gap", **_IHS5X}, {"metric": "gap", **_IHS6X}]},
                {"match": r"^Squared ultra-poverty gap \(%\)", "columns": [
                    {"metric": "severity", **_IHS5X}, {"metric": "severity", **_IHS6X}]},
            ],
        },
        # Table B.1 -- poverty incidence; national P0 comes from Table 1
        *_b12("table b.1: poverty incidence by place of residence", _est_ci(_IHS5), _est_ci(_IHS6)),
        # Table B.1, national row: IHS6 CI only (estimate already in Table 1)
        {"page_contains": ["table b.1: poverty incidence by place of residence"],
         "exact_numbers": True, "columns": [_SKIP] * 6 + [
             {"metric": "headcount_ci_low", **_IHS6}, {"metric": "headcount_ci_high", **_IHS6}],
         "rows": [{"match": r"^Malawi(?=\s+\d)"}]},
        # Table B.2 -- ultra-poverty incidence (IHS5 CIs skipped, see docstring)
        *_b12("table b.2: ultra-poverty incidence by place of residence",
              _est_ci(_IHS5X, ci=False), _est_ci(_IHS6X)),
        {"page_contains": ["table b.2: ultra-poverty incidence by place of residence"],
         "exact_numbers": True, "columns": [_SKIP] * 6 + [
             {"metric": "headcount_ci_low", **_IHS6X}, {"metric": "headcount_ci_high", **_IHS6X}],
         "rows": [{"match": r"^Malawi(?=\s+\d)"}]},
        # Table B.3 -- regions (P0 new here) and the distribution columns
        {"page_contains": ["table b.3: poverty incidence and population distribution"],
         "exact_numbers": True,
         "columns": [{"metric": "headcount", **_IHS6}, {"metric": "headcount", **_IHS6X},
                     {"metric": "population_share", **_IHS6}, {"metric": "poor_share", **_IHS6},
                     {"metric": "poor_share", **_IHS6X}],
         "rows": [{"match": rf"^{r} Region(?=\s+\d)", "geography": f"{r} Region"}
                  for r in ("Northern", "Central", "Southern")]},
        {"page_contains": ["table b.3: poverty incidence and population distribution"],
         "exact_numbers": True,
         "columns": [_SKIP, _SKIP, {"metric": "population_share", **_IHS6},
                     {"metric": "poor_share", **_IHS6}, {"metric": "poor_share", **_IHS6X}],
         "rows": [{"match": r"^Urban(?=\s+\d)", "topic": "locality", "locality": "urban",
                   "locality_label": "Urban"},
                  {"match": r"^Rural(?=\s+\d)", "topic": "locality", "locality": "rural",
                   "locality_label": "Rural"}]},
        {"page_contains": ["table b.3: poverty incidence and population distribution"],
         "start": r"^District$",
         "columns": [_SKIP, _SKIP, {"metric": "population_share", **_IHS6},
                     {"metric": "poor_share", **_IHS6}, {"metric": "poor_share", **_IHS6X}],
         "row_scan": {"expect_rows": 32}},
    ],
}


def _pages(path: str) -> dict[str, list[str]]:
    """Page text at x_tolerance=1 (the default glues words), inside the page box."""
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page = page.crop((0, 0, page.width, page.height))
            out.append(page.extract_text(x_tolerance=1) or "")
    return {"full": out}


def parse(path: str) -> pd.DataFrame:
    pages = _pages(path)
    if not any(p.strip() for p in pages["full"]):
        raise ValueError(f"{path}: no extractable text")
    rows, misses = [], []
    for t, tbl in enumerate(LAYOUT["tables"]):
        got, matched = T._parse_table(pages, LAYOUT, tbl, LAYOUT["period"], LAYOUT["reference_period"])
        rows.extend(got)
        misses += [f"table[{t}].{r['match']!r}" for i, r in enumerate(tbl.get("rows", []))
                   if i not in matched]
    if misses:
        raise ValueError(f"malawi: {len(misses)} row spec(s) matched nothing: {misses[:10]}")
    return pd.DataFrame.from_records(rows)
