"""Malawi -- NSO Malawi Labour Force Survey 2024 report, employment composition.

The current Malawi labour rows (malawi_nso_labour.py) are the 2018 census
Series D tables. This module reads two composition tables of the 2024 LFS
report (the report the `unemployment` indicator reads for its headline rows):

* Table 5.2 "Status in Employment (ICSE-18)" -- percent of the employed, 14
  ICSE-18 categories + Total, columns Malawi | Male | Female | Urban | Rural
  (URBAN BEFORE RURAL, as printed). Classification ICSE-18, as the title says
  (the report does not name the A or R hierarchy; the categories are the
  ICSE-18 detailed groups).
* Table 9.2 "Rate of employment in the informal / formal sector" -- percent of
  the employed in the informal sector, the formal sector and households, for
  Malawi, by sex, region, residence, age group and education.

All figures are the report's published percentages; nothing is derived. The
"Number of individuals" columns are not filed (they are the employed counts
behind each row, `unemployment`'s territory). Country of birth and functional
difficulty breakdowns are not read (no schema dimension).

NOT READ: Table 5.3 "Employment by Major occupation groups". As printed its
columns do not cohere -- "Skilled Agricultural, Forestry and Fishery Workers"
is 25.5 for Malawi but 13.4 (male), 12 (female), 2.4 (urban), 16.1 (rural),
all below the national figure; "Managers" is 12.3 nationally against 13.4 /
15.5 by sex. A table no column of which can be trusted is left out rather
than filed.

Base 15+ (the report's working-age population, "15 years and above").
"""
from __future__ import annotations
import re

import fitz
import pandas as pd

from . import _common as C

SURVEY = "Malawi Labour Force Survey 2024"
_NUM = re.compile(r"^\d{1,3}(?:,\d{3})+$|^\d+(?:\.\d+)?$")

_STATUS = ["Employers in corporations",
           "Employers in household market enterprises",
           "Employers not elsewhere classified",
           "Owner-operators of corporations without employees",
           "Own-account workers in household market enterprises without employees",
           "Own-account workers not elsewhere classified",
           "Dependent contractors", "Permanent employees", "Fixed-term employees",
           "Short-term and casual employees",
           "Paid apprentices, trainees and interns",
           "Employees not elsewhere classified", "Contributing family workers",
           "Workers not classifiable by status", "Total"]
_STATUS_COLS = [("total", "all", "Total"), ("male", "all", "Total"),
                ("female", "all", "Total"), ("total", "urban", "Urban"),
                ("total", "rural", "Rural")]

_SECTORS = ["Employment in Informal Sector", "Employment in Formal Sector",
            "Households"]
# Table 9.2 row label -> dimension
_REGIONS = {"North", "Central", "South"}
_EDU = {"None or Preschool", "Primary", "Secondary", "Technical", "University",
        "Other tertiary"}


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


def _page_after(doc, title_rx):
    for p in doc:
        t = p.get_text()
        m = re.search(title_rx, t)
        if m:
            lines = [_clean(x) for x in t[m.end():].splitlines() if _clean(x)]
            # the list of tables names the table too: the real one is
            # followed by its figures
            if sum(bool(_NUM.match(x)) for x in lines) >= 40:
                return lines
    raise ValueError(f"malawi_lfs_labour: {title_rx!r} not found")


def _status(doc):
    lines = _page_after(doc, r"Table 5\.2: Status in Employment \(ICSE-18\)")
    rows, i = [], 0
    groups = _groups(lines)
    want = list(_STATUS)
    for lab, nums in groups:
        if not want:
            break
        if not lab.endswith(want[0]):
            continue
        if len(nums) != 5:
            raise ValueError(f"malawi_lfs_labour 5.2 {want[0]!r}: {len(nums)} figures")
        for (sex, loc, ll), v in zip(_STATUS_COLS, nums):
            rows.append(C.row(
                topic="employment_status", characteristic=want[0],
                classification="ICSE-18", value=v, survey=SURVEY, period="2024",
                reference_period="2024", frequency="ad_hoc", measure="share",
                unit="percent", sex=sex, locality=loc, locality_label=ll,
                series_code="NSO LFS 2024 Table 5.2"))
        want.pop(0)
    if want:
        raise ValueError(f"malawi_lfs_labour 5.2: rows not found {want}")
    return rows


def _formality(doc):
    lines = _page_after(doc, r"Table 9\.2 Rate of employment in the informal / formal sector")
    rows, section = [], None
    for lab, nums in _groups(lines):
        # a group label may carry its section header in front ("Sex Male")
        for sec in ("Sex", "Region", "Residence", "Age group",
                    "Highest education level", "Country of birth"):
            if lab.startswith(sec + " "):
                section, lab = sec, lab[len(sec) + 1:]
        lab = re.sub(r"^.*\bindividual\s+", "", lab)    # header run-in
        if len(nums) != 4:
            continue
        dims = dict(sex="total", geography="Total country", locality="all",
                    locality_label="Total", age_group="Total", education="Total")
        if lab == "Malawi":
            pass
        elif section == "Sex" and lab in ("Male", "Female"):
            dims["sex"] = lab.lower()
        elif section == "Region" and lab in _REGIONS:
            dims["geography"] = f"{lab} Region"
        elif section == "Residence" and lab in ("Urban", "Rural"):
            dims["locality"], dims["locality_label"] = lab.lower(), lab
        elif section == "Age group" and re.fullmatch(r"\d\d-\d\d", lab):
            dims["age_group"] = lab
        elif section == "Highest education level" and lab in _EDU:
            dims["education"] = lab
        else:
            continue
        for char, v in zip(_SECTORS, nums[:3]):
            rows.append(C.row(
                topic="formality", characteristic=char,
                classification="Not applicable", value=v, survey=SURVEY,
                period="2024", reference_period="2024", frequency="ad_hoc",
                measure="share", unit="percent",
                series_code="NSO LFS 2024 Table 9.2", **dims))
    n = {r["sex"] + r["geography"] + r["locality"] + r["age_group"] + r["education"]
         for r in rows}
    # Malawi + 2 sexes + 3 regions + 2 residences + 5 age groups + 6 levels
    if len(n) != 19:
        raise ValueError(f"malawi_lfs_labour 9.2: {len(n)} breakdown rows, expected 19")
    return rows


def parse(local_path: str) -> pd.DataFrame:
    doc = fitz.open(local_path)
    return pd.DataFrame.from_records(_status(doc) + _formality(doc))
