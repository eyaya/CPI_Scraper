"""Zimbabwe -- ZIMSTAT QLFS BACK-SERIES 2021-2024, sector of employment.

The same four QLFS reports and the same "Table 1: Key findings" that
unemployment/parsers/zimbabwe_qlfs_back.py reads; this module opens only the
"Sector of Employment" block, so no figure is written twice:

    Formal (non-agriculture) | Informal (non-agriculture) | Agriculture |
    Household  (2024 reports: "Activities of Households as an Employer")

each as a count of employed persons AND the published percent of total
employment, for two quarters per report:

    Fourth_Quarter_Labour_Force_Report_2021.pdf   2021 Q3 | 2021 Q4
    QLFS_SecondQter2022.pdf                       2022 Q1 | 2022 Q2
    2024_First_Quarter_QLFS_Report.pdf            2023 Q4 | 2024 Q1
    2024_Third_Quarter_QLFS_Report.pdf            2024 Q1 | 2024 Q3

ZIMSTAT's sector-of-employment scheme splits employment by formality of the
production unit with agriculture and households apart; filed under `formality`
(classification Not applicable), as the existing LFCLS rows file Formal /
Informal / Household. Labels as printed, so the 2024 wording of the household
row stays distinct.

A QUARTER PRINTED TWICE (2024 Q1) is taken from the newer report. The two
printings differ on one figure, pinned below and never resolved silently:
the household count is 186,995 in the Q1 report and 186,955 in the Q3 report
(percent 5.7 in both); the Q3 report's figure is filed.

WORKING-AGE BASE as each report prints it: 15+ for 2021-2022, 16+ from 2023 Q4
(the national rows of the same table say so).
"""
from __future__ import annotations
import os
import re

import fitz
import pandas as pd

from . import _common as C

_ORD = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4}
_REPORTS = {
    "fourth_quarter_labour_force_report_2021": (1, ("2021-Q3", "2021-Q4"), "15+"),
    "qlfs_secondqter2022": (2, ("2022-Q1", "2022-Q2"), "15+"),
    "2024_first_quarter_qlfs_report": (3, ("2023-Q4", "2024-Q1"), "16+"),
    "2024_third_quarter_qlfs_report": (4, ("2024-Q1", "2024-Q3"), "16+"),
}
_SECTORS = {"formal (non-agriculture)", "informal (non-agriculture)",
            "agriculture", "household", "activities of households as an employer"}
_NUM = re.compile(r"\d{1,3}(?:,\d{3})+|\d+\.\d+|\d+")

# (period, characteristic, measure) -> (older printing, newer printing)
_KNOWN_REPRINT_DIFFS = {
    ("2024-Q1", "Activities of Households as an Employer", "count"):
        (186995.0, 186955.0),
}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def _report(path: str):
    name = os.path.basename(path).lower()
    hits = [k for k in _REPORTS if k in name]
    if len(hits) != 1:
        raise ValueError(f"zimbabwe_qlfs_back_labour: unknown report {name!r}")
    return _REPORTS[hits[0]]


def _rows(path: str) -> list[dict]:
    order, expect, base = _report(path)
    for page in fitz.open(path):
        toks = [_clean(x) for x in page.get_text().splitlines() if _clean(x)]
        st = next((i for i, x in enumerate(toks)
                   if re.match(r"Table 1\s*:\s*Key Findings", x, re.I)), None)
        if st is None:
            continue
        ind = next((i for i in range(st + 1, min(st + 12, len(toks)))
                    if toks[i].lower() == "indicator"), None)
        if ind is None:
            continue
        head = " ".join(toks[st + 1:ind])
        year = re.search(r"Year\s+(20\d\d)", head)
        qs = [f"{m.group(2) or (year.group(1) if year else '')}-Q{_ORD[m.group(1).lower()]}"
              for m in re.finditer(r"(1st|2nd|3rd|4th)\s+Quarter(?:\s+(20\d\d))?",
                                   head, re.I)]
        if qs != list(expect):
            raise ValueError(f"zimbabwe_qlfs_back_labour {path}: quarters {qs}")
        out, label, nums, in_block = [], [], [], False
        def flush():
            lab = _clean(" ".join(label))
            lab = re.sub(r"^Sector of Employment\s+", "", lab)
            if lab.lower() in _SECTORS:
                if len(nums) != 4:
                    raise ValueError(f"zimbabwe_qlfs_back_labour: {lab!r} has "
                                     f"{len(nums)} figures, expected 4")
                for qi in (0, 1):
                    out.append(dict(_order=order, period=qs[qi], char=lab,
                                    measure="count", value=nums[2 * qi]))
                    out.append(dict(_order=order, period=qs[qi], char=lab,
                                    measure="share", value=nums[2 * qi + 1]))
        for tok in toks[ind + 1:]:
            if re.fullmatch(r"[\d,. ]+", tok):
                nums += [float(x.replace(",", "")) for x in _NUM.findall(tok)]
                continue
            if nums:
                flush()
                label, nums = [], []
            if tok.lower() in ("number", "percent"):
                continue
            label.append(tok)
        if nums:
            flush()
        if {r["char"].lower() for r in out} != (
                _SECTORS - ({"household"} if base == "16+" else
                            {"activities of households as an employer"})):
            raise ValueError(f"zimbabwe_qlfs_back_labour {path}: sectors "
                             f"{sorted({r['char'] for r in out})}")
        for r in out:
            r["base"] = base
        return out
    raise ValueError(f"zimbabwe_qlfs_back_labour: no Key findings table in {path}")


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    recs = []
    for p in [local_path] + list(extras or []):
        recs += _rows(p)
    df = pd.DataFrame(recs)
    key = ["period", "char", "measure"]
    diffs = {}
    for k, g in df.groupby(key):
        if g["_order"].nunique() > 1:
            g = g.sort_values("_order")
            if abs(g["value"].iloc[0] - g["value"].iloc[-1]) > 1e-9:
                diffs[tuple(k)] = (g["value"].iloc[0], g["value"].iloc[-1])
    if diffs != _KNOWN_REPRINT_DIFFS:
        raise ValueError(f"zimbabwe_qlfs_back_labour: reprint differences "
                         f"{diffs}, pinned {_KNOWN_REPRINT_DIFFS}")
    df = df.sort_values("_order").drop_duplicates(key, keep="last")
    rows = [C.row(
        topic="formality", characteristic=r.char,
        classification="Not applicable", value=r.value,
        survey="Quarterly Labour Force Survey (QLFS)", period=r.period,
        reference_period=r.period.replace("-", " "), frequency="quarterly",
        measure=r.measure, unit="persons" if r.measure == "count" else "percent",
        working_age_base=r.base,
        series_code="ZIMSTAT QLFS Table 1 Key findings (sector of employment)")
        for r in df.itertuples()]
    return pd.DataFrame.from_records(rows)
