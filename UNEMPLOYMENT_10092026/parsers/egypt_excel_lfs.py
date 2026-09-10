"""CAPMAS Egypt quarterly Labour Force Survey workbook.

`excel_wide_series` expects PERIODS ACROSS THE COLUMNS. This workbook has no
period columns at all: it is a SINGLE-QUARTER release whose 27 sheets each show
one indicator, with SEX across the columns and the characteristic down the
rows. All 27 sheets therefore reported "no period header row found" — one wrong
model, not 27 changed layouts.

Three sheets carry the headline rates, and they share one shape:

    الخصائص        النوع                    Gender    Characteristics
                   ذكور    إناث    جملة
                   Males   Females Total
    الإجمالى        3.6     14.3    6         Total
    فئات السن                                 Age group
    15 - 19        7.2     26.6    9.8        15- 19
    ...
    الحالة التعليمية                           Educational Status
    أمى             1.4     3.7     2.1       Illiterate
    ...
    الأقاليم الجغرافية                          Geograghical regions
    المحافظات الحضرية 8.1    20.8    11        Urban governorates

  Table 1  contribution (participation) rates
  Table 2  employment rates
  Table 3  unemployment rates

THE ROW LABELS ARE READ FROM THE ENGLISH COLUMN (the last one), not the Arabic
first column, so the output does not depend on Arabic normalisation. The
SECTION HEADINGS ("Age group", "Educational Status", "Geograghical regions" —
CAPMAS's own spelling) carry no numbers and are used to scope the rows beneath
them, which is what keeps an age band from being filed as a region.

THE REFERENCE QUARTER IS NOT IN THE WORKBOOK. Nothing inside the file says
which quarter it is; only CAPMAS's publication API does, as
`quarter` / `year` on the publication detail. Dating this from the download
date or the release date would be wrong — the Q2 2026 issue was released in
August and re-published in September. So the quarter is fetched from the API
once and cached in a sidecar beside the workbook, which also keeps offline
re-parsing working.

Egypt's geographic strata are urban/rural CROSSED with region (Urban Lower
Egypt, Rural Upper Egypt, ...). Both parts are kept: `locality` takes the
urban/rural half for joining and `geography` keeps the published stratum whole.

CROSS-CHECK (Q2 2026): national unemployment 6.0 (males 3.6, females 14.3);
15-19 9.8; 20-24 16.2; university & post-graduate 11.3; urban governorates
11.0; rural Lower Egypt 4.5.
"""
from __future__ import annotations

import json
import os
import re

import pandas as pd

from . import _common as C

_SERIES = "EG_LFS"
_BASE = "15+"
_SURVEY = "Quarterly Labour Force Survey"
_API = "https://www.capmas.gov.eg:8080/api/Publication/11"

_SHEETS = {
    "جدول 1 Table": ("labour_force_participation_rate", "strict"),
    "جدول 2 Table": ("employment_to_population_ratio", "not_applicable"),
    "جدول 3 Table": ("unemployment_rate", "strict"),
}

# Section headings, in the English column, exactly as CAPMAS spells them.
_SECTIONS = {
    "age group": "age",
    "educational status": "education",
    "geograghical regions": "geography",   # the report's own misspelling
    "geographical regions": "geography",
}

# Published stratum -> the coarse locality it belongs to.
_LOCALITY = {
    "urban governorates": "urban",
    "urban lower egypt": "urban",
    "rural lower egypt": "rural",
    "urban upper egypt": "urban",
    "rural upper egypt": "rural",
    "urban frontier governorates": "urban",
    "rural frontier governorates": "rural",
}

_SEX_COLS = {1: "male", 2: "female", 3: "total"}


def _period(path: str) -> tuple[str, str]:
    """The reference quarter, from CAPMAS's API, cached beside the workbook."""
    side = os.path.splitext(path)[0] + ".period.json"
    if os.path.exists(side):
        with open(side, encoding="utf-8") as fh:
            got = json.load(fh)
        return got["period"], got["reference_period"]

    import requests
    import urllib3
    urllib3.disable_warnings()
    r = requests.get(_API, timeout=90, verify=False,
                     headers={"User-Agent": "Mozilla/5.0", "locale": "en",
                              "Accept": "application/json"})
    r.raise_for_status()
    detail = (r.json().get("data") or {}).get("publicationDetail") or {}
    q, y = detail.get("quarter"), detail.get("year")
    if not (q and y):
        raise ValueError(
            "Egypt LFS: CAPMAS's publication detail carries no quarter/year, "
            "and the workbook itself never states its reference quarter. "
            "Refusing to date it from the download or release date -- the "
            "Q2 2026 issue was released in August and re-published in "
            "September.")
    got = {"period": f"{int(y)}-Q{int(q)}",
           "reference_period": f"Q{int(q)} {int(y)}"}
    try:
        with open(side, "w", encoding="utf-8") as fh:
            json.dump(got, fh)
    except OSError:
        pass
    return got["period"], got["reference_period"]


def _english(row) -> str:
    """The row's English label -- the last non-empty cell on the line."""
    for v in reversed(list(row)):
        s = str(v).strip()
        if s and s.lower() != "nan":
            return s
    return ""


def parse(path: str) -> pd.DataFrame:
    period, reference = _period(path)
    xl = pd.ExcelFile(path)
    rows: list[dict] = []

    for sheet, (topic, definition) in _SHEETS.items():
        if sheet not in xl.sheet_names:
            raise ValueError(
                f"{path}: sheet {sheet!r} is missing. CAPMAS has renumbered "
                f"its tables; read the workbook before editing this map.")
        d = pd.read_excel(path, sheet_name=sheet, header=None)
        section = None
        for _, r in d.iterrows():
            label = _english(r)
            low = re.sub(r"\s+", " ", label).strip().lower()
            nums = [C.to_number(r.iloc[c]) if c < len(r) else None
                    for c in _SEX_COLS]
            if low in _SECTIONS:
                section = _SECTIONS[low]
                continue
            if not label or all(v is None for v in nums):
                continue
            if low == "total":
                section = None

            attrs = {"age_group": "Total", "education": "Total",
                     "geography": "Total country", "locality": "all",
                     "locality_label": "Total"}
            if section == "age":
                attrs["age_group"] = re.sub(r"\s*-\s*", "-", label)
            elif section == "education":
                attrs["education"] = label
            elif section == "geography":
                attrs["geography"] = label
                attrs["locality"] = _LOCALITY.get(low, "other")
                attrs["locality_label"] = label

            for col, sex in _SEX_COLS.items():
                v = C.to_number(r.iloc[col]) if col < len(r) else None
                if v is None:
                    continue
                rows.append({
                    "topic": topic, "definition": definition, "measure": "rate",
                    "unit": "percent", "value": v, "sex": sex,
                    "period": period, "reference_period": reference,
                    "frequency": "quarterly", "survey": _SURVEY,
                    "working_age_base": _BASE, "series_code": _SERIES,
                    "series_label": label, **attrs,
                })

    if not rows:
        raise ValueError(f"{path}: no rows read from Tables 1-3.")
    df = pd.DataFrame(rows)
    if "unemployment_rate" not in set(df["topic"]):
        raise ValueError(f"{path}: Table 3 produced no unemployment rate.")
    return df.drop_duplicates(
        ["topic", "definition", "sex", "age_group", "education", "geography",
         "period", "measure"])
