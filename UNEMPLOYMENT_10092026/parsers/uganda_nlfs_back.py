"""Uganda -- UBOS National Labour Force Survey 2016/17 report: BACK-SERIES.

The current Uganda rows (uganda_unemployment.py) are the Labour Market Survey
2025. This module reads the front matter of UBOS's "Report on the National
Labour Force Survey 2016/17" (UBOS publications, 10_2018...pdf):

* "SELECTED LABOUR MARKET INDICATORS" (pp. ii-iii) -- 2016/17, columns
  Male | Female | Rural | Urban | Total.
* "SELECTED LABOUR MARKET INDICATORS FOR 2011/12 AND 2016/17" (p. iv) -- the
  2011/12 National Labour Force and Child Activities Survey beside 2016/17,
  the same five columns for each.

THE 2011/12 FIGURES ARE ON A DIFFERENT DEFINITION. The table's own note: the
starred indicators "cannot be directly compared because of change in
definition ... the definition of employment ... was revised after the survey
of 2011/12". 2011/12 rows are taken from p. iv only, with "(2011/12
definition)" in every label, so no 2011/12 figure shares a series with a later
one. The 2016/17 figures come from pp. ii-iii (p. iv repeats them; they are
checked equal, not filed twice).

BASE: the working-age population is 14-64 ("Distribution of the working age
population (14-64 years)", Table 3.1) -- the base the 2025 rows carry. Youth is
18-30, as each youth label prints. Counts are printed in thousands.

PERIODS: a split-year survey takes its END year (2016/17 -> 2017, 2011/12 ->
2012; reference_period keeps the survey's own span), as kenya's KIHBS 2015/16
is filed.

LABELS continue the 2025 layout's where the series is the same ("Labour Force
Participation Rate", "Unemployment Rate (LU1)", "Composite measure of Labour
underutilization (LU4)" ...).

NOT READ: total population, the subsistence-agriculture rows, health and
safety, youth transition stages, children 5-17, earnings and hours, and the
composition rows (status, industry, occupation -- read by
labour/parsers/uganda_nlfs_back_labour.py).
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

# label tail (fullmatch) -> (topic, series_label, definition, age, unit)
_R2017 = [
    (r"working age population \(number ‘000\)",
     ("working_age_population", "Working age population (14-64 years)",
      "not_applicable", "Total", "thousand_persons")),
    (r"size of the employed population \(number '000\)",
     ("employed", "Employed population", "not_applicable", "Total",
      "thousand_persons")),
    (r"employment-to-population ratio \(epr\)",
     ("employment_to_population_ratio", "Employment-to-Population Ratio",
      "not_applicable", "Total", "percent")),
    (r"youth \(18-30 years\) epr",
     ("employment_to_population_ratio", "Youth Employment-to-Population Ratio",
      "not_applicable", "18-30", "percent")),
    (r"size of the labour force \(number '000\)",
     ("labour_force", "Labour force", "not_applicable", "Total",
      "thousand_persons")),
    (r"labour force participation rate \(lfpr\)",
     ("labour_force_participation_rate", "Labour Force Participation Rate",
      "strict", "Total", "percent")),
    (r"youth \(18-30 years\) lfpr",
     ("labour_force_participation_rate", "Youth Labour Force Participation Rate",
      "strict", "18-30", "percent")),
    (r"unemployment rate \(lu1\)",
     ("unemployment_rate", "Unemployment Rate (LU1)", "strict", "Total",
      "percent")),
    (r"combined rate of unemployment and time-related underemployment \(lu2\)",
     ("labour_underutilisation_rate",
      "Combined Rate of Unemployment and Time Related Underemployment (LU2)",
      "broad", "Total", "percent")),
    (r"combined rate of unemployment and potential labour force \(lu3\)",
     ("labour_underutilisation_rate",
      "Combined Rate of Unemployment and Potential Labour Force (LU3)",
      "broad", "Total", "percent")),
    (r"composite labour underutilization \( ?lu4\)",
     ("labour_underutilisation_rate",
      "Composite measure of Labour underutilization (LU4)", "broad", "Total",
      "percent")),
    (r"youth unemployment rate \(lu1\)",
     ("youth_unemployment_rate", "Youth Unemployment Rate (LU1)", "strict",
      "18-30", "percent")),
    (r"youth composite labour underutilization \(lu4\)",
     ("labour_underutilisation_rate",
      "Youth composite labour underutilization (LU4)", "broad", "18-30",
      "percent")),
    (r"neither in employment nor education training \(neet\)",
     ("neet_rate", "Youth (18-30 years) neither in employment nor education "
      "or training (NEET)", "not_applicable", "18-30", "percent")),
]
_D = " (2011/12 definition)"
_R2012 = [
    (r"working age population 000's\)",
     ("working_age_population", "Working age population (14-64 years)",
      "not_applicable", "Total", "thousand_persons")),
    (r"labour force \(lf-‘000’s\)\*\*",
     ("labour_force", "Labour force" + _D, "not_applicable", "Total",
      "thousand_persons")),
    (r"labour force participation rate\*\*",
     ("labour_force_participation_rate", "Labour Force Participation Rate" + _D,
      "strict", "Total", "percent")),
    (r"a\) unemployment rate",
     ("unemployment_rate", "Unemployment rate" + _D, "strict", "Total",
      "percent")),
]
_C2017, _C2012 = ([(re.compile(p, re.I), s) for p, s in r] for r in (_R2017, _R2012))


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def walk(lines, width):
    """(label_lines, numbers) groups: a label then `width` or more figures."""
    label, nums, out = [], [], []
    for ln in lines:
        if _NUM.match(ln):
            nums.append(float(ln.replace(",", "")))
            continue
        if nums:
            out.append((label, nums))
            label, nums = [], []
        label.append(ln)
    if nums:
        out.append((label, nums))
    return out


def classify(label_lines, rules):
    for k in range(1, min(4, len(label_lines)) + 1):
        tail = _clean(" ".join(label_lines[-k:]))
        for rx, spec in rules:
            if rx.fullmatch(tail):
                return tail, spec
    return None, None


def pages(path):
    """{'summary': [lines of pp. ii-iii], 'compare': [lines of p. iv]}"""
    doc = fitz.open(path)
    summ, comp = [], []
    for p in doc:
        t = p.get_text()
        if "SELECTED LABOUR MARKET INDICATORS FOR 2011/12 AND 2016/17" in t:
            comp = [_clean(x) for x in t.splitlines() if _clean(x)]
        elif "SELECTED LABOUR MARKET INDICATORS" in t and "Selected Indicators" in t:
            summ += [_clean(x) for x in t.splitlines() if _clean(x)]
        if comp and len(summ) > 50:
            break
    if not summ or not comp:
        raise ValueError("uganda_nlfs_back: selected-indicator pages not found")
    return summ, comp


def _emit(period, spec, values, cols=_COLS, code=""):
    topic, label, definition, age, unit = spec
    out = []
    for (sex, loc, loc_label), v in zip(cols, values):
        out.append(C.row(
            topic=topic, value=v, series_label=label, survey=SURVEY[period],
            period=period, reference_period=REF[period], frequency="ad_hoc",
            working_age_base="14-64", measure="count" if unit != "percent"
            else "rate", unit=unit, definition=definition, sex=sex,
            age_group=age, locality=loc, locality_label=loc_label,
            series_code=code))
    return out


def parse(local_path: str) -> pd.DataFrame:
    summ, comp = pages(local_path)
    rows, seen17, got = [], {}, set()
    for lab, nums in walk(summ, 5):
        tail, spec = classify(lab, _C2017)
        if spec is None:
            continue
        if len(nums) != 5:
            raise ValueError(f"uganda_nlfs_back 2016/17 {tail!r}: {len(nums)} figures")
        seen17[spec[1] + spec[3]] = nums
        got.add(tail)
        rows += _emit("2017", spec, nums, code="UBOS NLFS 2016/17 selected indicators")
    if len(got) != len(_R2017):
        missing = [p for p, _ in _R2017 if not any(re.fullmatch(p, g, re.I) for g in got)]
        raise ValueError(f"uganda_nlfs_back: 2016/17 rows not found: {missing}")
    got12 = set()
    for lab, nums in walk(comp, 10):
        tail, spec = classify(lab, _C2012)
        if spec is None:
            continue
        if len(nums) != 10:
            raise ValueError(f"uganda_nlfs_back 2011/12 {tail!r}: {len(nums)} figures")
        got12.add(spec[0])
        rows += _emit("2012", spec, nums[:5],
                      code="UBOS NLFS 2016/17 selected indicators, 2011/12 column")
        # the 2016/17 half of the comparison must equal pp. ii-iii
        twin = {"working_age_population": "Working age population (14-64 years)Total",
                "labour_force": "Labour forceTotal",
                "labour_force_participation_rate": "Labour Force Participation RateTotal",
                "unemployment_rate": "Unemployment Rate (LU1)Total"}[spec[0]]
        if seen17.get(twin) != nums[5:]:
            raise ValueError(f"uganda_nlfs_back: p. iv 2016/17 {tail!r} = "
                             f"{nums[5:]}, pp. ii-iii = {seen17.get(twin)}")
    if len(got12) != len(_R2012):
        raise ValueError(f"uganda_nlfs_back: 2011/12 rows found {sorted(got12)}")
    return pd.DataFrame.from_records(rows)
