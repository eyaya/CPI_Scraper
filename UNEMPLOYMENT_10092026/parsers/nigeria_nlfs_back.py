"""Nigeria -- NBS NLFS: the current bulletin, the 2023 annual report, PLUS
the earlier quarterly reports under the 2022 (19th ICLS) methodology.

`nigeria_unemployment` reads the newest quarterly bulletin (primary) and the
2023 annual report (an extra whose name contains "annual"). This module adds
the back issues, each an `extra_urls` entry named `nigeria_nlfs_<YYYY>Q<n>.pdf`:

    2023 Q3  Annex A Table 1, nine columns [Total|Urban|Rural] x [T|M|F] --
             the layout `nigeria_unemployment` already reads.
    2024 Q1  Annex A, FIVE columns: National | Male | Female | Urban | Rural
             (the urban and rural columns are both sexes). Same row labels.

and, from the newest back issue that prints it, the summary table

    "Labour Market Indicators by Quarters"
    Key Labour Market Indicators | Q4 2022 | Q1 2023 | Q2 2023 | Q3 2023 | Q1 2024

-- national figures only -- for the quarters NO report gives in detail
(2022 Q4, 2023 Q1, 2023 Q2). A quarter read from an annex is never read again
from the summary table, so no figure is filed twice under two labels. The Q4
2022 & Q1 2023 report and the Q2 2023 report print only this kind of summary
(and charts), so they are not read themselves; the Q1 2024 report's table
carries their quarters, as revised.

ROWS TAKEN FROM THE SUMMARY TABLE, labels as printed (the footnote digit that
follows "Labour Underutilisation 2/3/4" is dropped): participation rate,
employment-to-population ratio, time-related underemployment, unemployment
rate, LU2-LU4, youth (15-24) unemployment rate, urban and rural unemployment
rate, informal employment. Not read: self-employment, own-use producers and
wage employment shares (composition, not headline status).

NOT READ AT ALL: the pre-2022 "Labor Force Statistics" reports (2016-2020).
They use NBS's old national definition (working age 15-64, unemployment
including those working under 20 hours a week) and must not be chained to
this series.

CROSS-CHECK (Q1 2024): summary-table unemployment 5.3 = Annex A national 5.3;
youth 8.4 = "Young unemployed (aged 15-24)" 8.4; LU2 15.3 = 15.3.
"""
from __future__ import annotations

import copy
import os
import re

import pandas as pd

from . import nigeria_unemployment as base
from .pdf_key_indicators import make_parser

_NAME = re.compile(r"nigeria_nlfs_(20\d{2})Q([1-4])\.pdf$", re.I)

# Annex A in five columns (2024 Q1).
_FIVE = copy.deepcopy(base.LAYOUT)
_FIVE["tables"][0]["page_contains"] = ["labour market indicators by sex and place of residence"]
_FIVE["tables"][0]["columns"] = [
    {"sex": "total", "locality": "all", "locality_label": "Total"},
    {"sex": "male", "locality": "all", "locality_label": "Total"},
    {"sex": "female", "locality": "all", "locality_label": "Total"},
    {"sex": "total", "locality": "urban", "locality_label": "Urban"},
    {"sex": "total", "locality": "rural", "locality_label": "Rural"},
]
_five = make_parser(_FIVE)

_SUMMARY_ROWS = [
    (r"^Labour Force Participation Rate", "labour_force_participation_rate", "strict", {}),
    (r"^Employment-to-[Pp]opulation Ratio", "employment_to_population_ratio", "not_applicable", {}),
    (r"^Time-related underemployment", "underemployment_rate", "not_applicable", {}),
    (r"^Unemployment Rate", "unemployment_rate", "strict", {}),
    (r"^Labour Underutilisation (2)\d?", "labour_underutilisation_rate", "broad", {}),
    (r"^Labour Underutilisation (3)\d?", "labour_underutilisation_rate", "broad", {}),
    (r"^Labour Underutilisation (4)\d?", "labour_underutilisation_rate", "broad", {}),
    (r"^Youth Unemployment Rate", "youth_unemployment_rate", "strict", {"age_group": "15-24"}),
    (r"^Urban Unemployment Rate", "unemployment_rate", "strict",
     {"locality": "urban", "locality_label": "Urban"}),
    (r"^Rural Unemployment Rate", "unemployment_rate", "strict",
     {"locality": "rural", "locality_label": "Rural"}),
    (r"^Informal Employment", "informal_employment_share", "not_applicable", {}),
]
_NUM = r"-?\d+(?:\.\d+)?"


def _summary(path: str) -> pd.DataFrame:
    import pdfplumber
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "Labour Market Indicators by Quarters" not in text:
                continue
            lines = text.splitlines()
            hdr = next(l for l in lines if l.startswith("Key Labour Market Indicators"))
            quarters = [f"{y}-Q{q}" for q, y in re.findall(r"Q([1-4])\s+(20\d{2})", hdr)]
            if len(quarters) < 2:
                raise ValueError(f"{path}: summary header {hdr!r} names no quarters")
            for line in lines:
                for rx, topic, definition, extra in _SUMMARY_ROWS:
                    m = re.match(rx, line)
                    if not m:
                        continue
                    nums = re.findall(_NUM, line[m.end():])
                    if len(nums) < len(quarters):
                        raise ValueError(f"{path}: summary row {line!r} has "
                                         f"{len(nums)} values for {len(quarters)} quarters")
                    label = (f"Labour Underutilisation {m.group(1)}" if m.groups()
                             else m.group(0).strip())
                    for period, v in zip(quarters, nums[-len(quarters):]):
                        rows.append({
                            "topic": topic, "definition": definition,
                            "series_label": label, "sex": "total",
                            "age_group": "Total", "education": "Total",
                            "geography": "Total country", "locality": "all",
                            "locality_label": "Total", **extra,
                            "working_age_base": "15+", "period": period,
                            "reference_period": period, "frequency": "quarterly",
                            "measure": "rate", "unit": "percent", "value": float(v),
                            "survey": "Nigeria Labour Force Survey (NLFS) -- "
                                      "Labour Market Indicators by Quarters",
                            "series_code": "NLFS quarters summary",
                        })
                    break
            break
    return pd.DataFrame(rows)


def _back_issue(path: str) -> pd.DataFrame:
    m = _NAME.search(os.path.basename(path))
    if not m:
        raise ValueError(f"NLFS back issue {path!r}: name must be nigeria_nlfs_<YYYY>Q<n>.pdf")
    want = f"{m.group(1)}-Q{m.group(2)}"
    try:
        df = base._bulletin(path)
    except ValueError:
        df = _five(path)
    got = set(df["period"].astype(str))
    if got != {want}:
        raise ValueError(f"{os.path.basename(path)}: filed as {want}, reads {sorted(got)}")
    return df


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    extras = extras or []
    back = [p for p in extras if _NAME.search(os.path.basename(p))]
    rest = [p for p in extras if p not in back]
    frames = [base.parse(path, extras=rest)]
    frames += [_back_issue(p) for p in back]
    detailed = set(pd.concat(frames)["period"].astype(str))
    # The summary table from the newest back issue that prints one.
    for p in sorted(back, reverse=True):
        s = _summary(p)
        if len(s):
            frames.append(s[~s["period"].isin(detailed)])
            break
    return pd.concat(frames, ignore_index=True)
