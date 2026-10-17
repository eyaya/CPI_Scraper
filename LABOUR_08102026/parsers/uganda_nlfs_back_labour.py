"""Uganda -- UBOS National Labour Force Survey 2016/17 report, composition.

The front matter that unemployment/parsers/uganda_nlfs_back.py reads for the
headline series; this module opens only the composition rows, so no figure is
written twice:

* 2016/17 ("SELECTED LABOUR MARKET INDICATORS", p. ii) -- shares of the
  EMPLOYED population (19th-ICLS employment) by status in employment, by
  industry sector and by occupation, Male | Female | Rural | Urban | Total.
* 2011/12 ("... FOR 2011/12 AND 2016/17", p. iv, the 2011/12 columns) -- shares
  of the WORKING POPULATION by status and by sector. The page's own note:
  employment was redefined after 2011/12 and the starred indicators "cannot be
  directly compared". These shares are of a different population (all working
  persons, subsistence included), so each characteristic carries
  "(working population)" and they never share a series with 2016/17. The
  page's 2016/17 columns are NOT read -- they are working-population shares,
  not the employed-population shares of p. ii.

CLASSIFICATIONS AS THE REPORT STATES THEM: occupation "according to ISCO-08"
(p. 53) -- the rows are ISCO-08 major groups, with the report's own "Others*"
(managers and clerical support workers) kept; industry is UBOS's grouping of
ISIC Rev 4 into agriculture / production / services (National, as the 2025
rows file it); status in employment names no standard (National).

Rows with fewer figures than the table's columns are not read (p. iv prints
"Other forms of work" and "Not stated" with five figures under ten columns,
and which survey they belong to cannot be told from the page).

Base 14-64; split-year periods take the end year (2016/17 -> 2017).
"""
from __future__ import annotations
import re

import fitz
import pandas as pd

from . import _common as C

SURVEY = {"2017": "National Labour Force Survey 2016/17",
          "2012": "National Labour Force and Child Activities Survey 2011/12"}
REF = {"2017": "2016/17", "2012": "2011/12"}
_COLS = [("male", "all", "Total"), ("female", "all", "Total"),
         ("total", "rural", "Rural"), ("total", "urban", "Urban"),
         ("total", "all", "Total")]
_NUM = re.compile(r"^\d{1,3}(?:,\d{3})+$|^\d+(?:\.\d+)?$")

# section header (as printed) -> (topic, classification, row labels in order)
_P2 = {
    "Status in employment": ("employment_status", "National",
        ["Paid employee", "Employer", "Own account worker",
         "Contributing family workers", "Total"]),
    "Industry (sector) of employment": ("industry", "National",
        ["Agriculture, forestry and fishing", "Production", "Services", "Total"]),
    "Occupation in the main job": ("occupation", "ISCO-08",
        ["Skilled agricultural, forestry and fishery", "Service and sales workers",
         "Elementary occupations", "Craft and related trades workers",
         "Plant and machine operators and assemblers", "Professionals",
         "Technicians and associate professionals", "Others*", "Total"]),
}
_P4 = {   # 2011/12 columns of p. iv
    "employment_status": ["Paid employment", "Self-employment",
                          "Contributing family workers"],
    "industry": ["Agriculture, forestry and fishing", "Manufacturing", "Services"],
}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def _groups(lines):
    label, nums, out = [], [], []
    for ln in lines:
        if _NUM.match(ln):
            nums.append(float(ln.replace(",", "")))
            continue
        if nums:
            out.append((_clean(" ".join(label)), nums))
            label, nums = [], []
        label.append(ln)
    if nums:
        out.append((_clean(" ".join(label)), nums))
    return out


def _emit(period, topic, cls, char, values, code):
    return [C.row(topic=topic, characteristic=char, classification=cls,
                  value=v, survey=SURVEY[period], period=period,
                  reference_period=REF[period], frequency="ad_hoc",
                  measure="share", unit="percent", sex=sex, locality=loc,
                  locality_label=ll, working_age_base="14-64", series_code=code)
            for (sex, loc, ll), v in zip(_COLS, values)]


def parse(local_path: str) -> pd.DataFrame:
    doc = fitz.open(local_path)
    p2 = p4 = None
    for p in doc:
        t = p.get_text()
        if "SELECTED LABOUR MARKET INDICATORS FOR 2011/12 AND 2016/17" in t:
            p4 = [_clean(x) for x in t.splitlines() if _clean(x)]
        elif ("SELECTED LABOUR MARKET INDICATORS" in t and "Status in employment" in t
              and p2 is None):
            p2 = [_clean(x) for x in t.splitlines() if _clean(x)]
        if p2 and p4:
            break
    if not (p2 and p4):
        raise ValueError("uganda_nlfs_back_labour: selected-indicator pages not found")
    rows = []
    # p. ii: each section header line is followed by its rows
    groups = _groups(p2)
    for header, (topic, cls, labels) in _P2.items():
        idx = next((i for i, (lab, _) in enumerate(groups) if lab.endswith(header)
                    or lab.endswith(header + " " + labels[0])), None)
        if idx is None:
            raise ValueError(f"uganda_nlfs_back_labour: section {header!r} not found")
        for k, want in enumerate(labels):
            lab, nums = groups[idx + k]
            if not lab.endswith(want) or len(nums) != 5:
                raise ValueError(f"uganda_nlfs_back_labour: {header}: got "
                                 f"{lab!r} ({len(nums)}), expected {want!r}")
            rows += _emit("2017", topic, cls, want, nums,
                          "UBOS NLFS 2016/17 selected indicators")
    # p. iv: 2011/12 = the first five of ten figures
    groups = _groups(p4)
    for topic, labels in _P4.items():
        for want in labels:
            hit = [(lab, n) for lab, n in groups
                   if lab.endswith(want) and len(n) == 10]
            if len(hit) != 1:
                raise ValueError(f"uganda_nlfs_back_labour: 2011/12 {want!r}: "
                                 f"{len(hit)} rows of ten figures")
            rows += _emit("2012", topic, "National", f"{want} (working population)",
                          hit[0][1][:5],
                          "UBOS NLFS 2016/17 selected indicators, 2011/12 column")
    return pd.DataFrame.from_records(rows)
