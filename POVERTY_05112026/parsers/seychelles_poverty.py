"""Seychelles -- monetary poverty (National Bureau of Statistics), INCOME-based.

Seychelles measures poverty on GROSS INCOME per adult equivalent (not
consumption): welfare_aggregate "income", so no row shares an ID with a
consumption headcount.

`parse` -- "A Poverty Profile of the Republic of the Seychelles. Poverty
Report for the Household Budget Survey 2013" (NBS with the World Bank, June
2016; every table "National Bureau of Statistics' calculations based on the
2013 HBS"). Wayback `id_` copy of NBS's own download.
  Lines (SCR per adult equivalent per month, 2013): poverty line 3,945
  (overall), ultra-poverty line 3,193 (extreme).
  T1 / T3   national P0 P1 P2 on both lines
  T6 / T7   6 regions: P0, P1, P2, their contributions, population share
  T9        individuals by sex, age group, marital status, nationality
  T11-T13   household head: sex, age, marital status; education; labour-force
            and employment status
  T20 / T21 95% CI of P0 by region, both lines
Not collected: T2 (other countries), T10 / T14 (individuals' labour status
and sector -- no topic), T15 / T16 (income source, social-protection receipt),
the P1/P2 confidence limits (the schema bounds only the headcount).

`parse_2018` -- "Poverty & Inequality in Seychelles. A Joint NBS-World Bank
Summary Report" (January 2021), Table 2: P0 P1 P2 on the 2018 upper poverty
line (SCR 4,376 per adult per month) for HBS 2018 AND 2013 re-estimated on
it (38.4 vs the 2016 report's 39.3) -- its own survey labels.

The NBS-only 2017/18 Poverty Profiling Regional Survey (non-probabilistic
sample) and the World-Bank-only 2022 Poverty and Equity Assessment stay
uncollected (sources_blocked note superseded).

CROSS-CHECK (verbatim): 2013 39.3 / 12.6 / 6.6, ultra 24.3 / 8.2 / 4.6;
Central 2 52.5; North 28.6; female heads 42.9; regional contributions sum to
100.0; 2018 25.3 / 8.0 / 3.8.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

UNIT = "SCR per adult equivalent per month"
_S13 = ("HBS 2013", "2013", "2013")
_LINES = {"overall": ("Poverty line (gross income)", 3945), "extreme": ("Ultra-poverty line (gross income)", 3193)}
REGIONS = ["Central 1", "Central 2", "East/South", "West", "North", "Praslin/La Digue"]
LAYOUT = {"survey": "HBS 2013", "welfare_aggregate": "income", "unit_of_analysis": "person",
          "frequency": "ad_hoc", "decimal": ".", "line_type": "national", "line_level": "overall",
          "line_name": _LINES["overall"][0], "line_value": 3945, "line_unit": UNIT,
          "period": "2013", "reference_period": "2013", "tables": []}
LAYOUT_2018 = {**LAYOUT, "survey": "HBS 2018 (NBS-World Bank summary 2021)", "line_name": "Upper poverty line (2018)",
               "line_value": 4376, "period": "2018", "reference_period": "2018/19"}
_N = r"(\d+(?:\.\d+)?)"


def _text(path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _seg(t, cap):
    i = t.rindex(cap)
    return [l.strip() for l in t[i:t.index("Source:", i)].splitlines()]


def _b(level, s=_S13):
    name, val = _LINES[level]
    return dict(survey=s[0], welfare_aggregate="income", line_type="national", line_level=level,
                line_name=name, line_value=val, line_unit=UNIT, period=s[1],
                reference_period=s[2], frequency="ad_hoc")


def _age(lab):
    lab = lab.replace("–", "-").replace(" years", "")
    return {"Less than 15": "Less than 15"}.get(lab, lab)


def parse(path: str) -> pd.DataFrame:
    t = _text(path)
    rows = []
    put = lambda m, v, lv, **c: rows.append(C.row(metric=m, value=float(v), **_b(lv), **c))  # noqa: E731
    for cap, lv in (("Table 1. Poverty and inequality estimates based on estimated gross income, 2013", "overall"),
                    ("Table 3. Ultra-poverty estimates based on estimated gross income, 2013", "extreme")):
        seg = "\n".join(_seg(t, cap))
        for lab, m in (("Poverty headcount ratio", "headcount"), ("Poverty gap index", "gap"),
                       ("Poverty gap squared index", "severity")):
            v = re.search(rf"^{lab} \(%\) {_N}", seg, re.M).group(1)
            if lab == "Poverty headcount ratio" and v == "39.316":
                v = "39.3"     # a footnote marker "16" printed after 39.3
            put(m, v, lv)
    for cap, lv in (("Table 6. Regional distribution of poverty, 2013", "overall"),
                    ("Table 7.Regional distribution of ultra-poverty, 2013", "extreme")):
        got = 0
        for ln in _seg(t, cap):
            m = re.match(rf"^({'|'.join(map(re.escape, REGIONS))}) {_N} {_N} {_N} {_N} {_N} {_N} {_N}$", ln)
            if m:
                c = {"geography": m.group(1)}
                for metric, v in zip(("headcount", "poor_share", "gap", "gap_contribution", "severity",
                                      "severity_contribution", "population_share"), m.groups()[1:]):
                    put(metric, v, lv, **c)
                got += 1
        if got != 6:
            raise ValueError(f"Seychelles {cap}: {got} regions")
    # T9 individuals, T11 head: Index | Contribution | P1 | P2 | population share
    for cap, head in (("Table 9.Distribution of poverty across demographic characteristics, 2013", False),
                      ("Table 11. Poverty by the demographic characteristics of the household head, 2013", True)):
        block = None
        for ln in _seg(t, cap):
            if ln in ("Gender", "Age group", "Marital status", "Nationality"):
                block = ln
                continue
            m = re.match(rf"^(.+?) {_N} {_N} {_N} {_N} {_N}$", ln)
            if not (m and block):
                continue
            lab = m.group(1)
            if block == "Gender":
                sx = lab.lower()
                c = ({"topic": "sex_of_head", "characteristic": lab, "sex": sx} if head
                     else {"topic": "sex", "characteristic": lab, "sex": sx})
            elif block == "Age group":
                c = ({"topic": "age_of_head", "characteristic": lab} if head
                     else {"topic": "age", "characteristic": lab, "age_group": _age(lab)})
            elif block == "Marital status":
                if not head:
                    continue          # individuals' marital status: no topic
                c = {"topic": "marital_status_of_head", "characteristic": lab}
            else:
                continue              # nationality: no topic
            p0, sh, p1, p2, pop = m.groups()[1:]
            for metric, v in (("headcount", p0), ("poor_share", sh), ("gap", p1),
                              ("severity", p2), ("population_share", pop)):
                put(metric, v, "overall", **c)
    for cap, topic in (("Table 12. Poverty by educational attainment of the household head, 2013", "education_of_head"),
                       ("Table 13. Poverty by labor force status and status in employment of the household head, 2013",
                        "employment_of_head")):
        got = 0
        for ln in _seg(t, cap):
            m = re.match(rf"^([A-Z][A-Za-z/ -]+?†?) {_N} {_N} {_N} {_N} {_N}$", ln)
            if not m:
                continue
            c = {"topic": topic, "characteristic": m.group(1).rstrip("†")}
            p0, sh, p1, p2, pop = m.groups()[1:]
            for metric, v in (("headcount", p0), ("poor_share", sh), ("gap", p1),
                              ("severity", p2), ("population_share", pop)):
                put(metric, v, "overall", **c)
            got += 1
        if got < 6:
            raise ValueError(f"Seychelles {cap}: {got} rows")
    for cap, lv in (("Table 20. Confidence intervals (95 percent) for poverty by region, 2013", "overall"),
                    ("Table 21. Confidence intervals (95 percent) for ultra-poverty by region, 2013", "extreme")):
        seg = _seg(t, cap)
        seg = [l.replace("Praslin/La ", "Praslin/La Digue ") if l.startswith("Praslin/La ") else l
               for l in seg if l != "Digue"]
        got = 0
        for ln in seg:
            m = re.match(rf"^({'|'.join(map(re.escape, REGIONS))}|National) {_N} {_N} {_N}", ln)
            if m:
                c = {} if m.group(1) == "National" else {"geography": m.group(1)}
                put("headcount_ci_low", m.group(3), lv, **c)
                put("headcount_ci_high", m.group(4), lv, **c)
                got += 1
        if got != 7:
            raise ValueError(f"Seychelles {cap}: {got} rows")
    return pd.DataFrame.from_records(rows)


def parse_2018(path: str) -> pd.DataFrame:
    t = _text(path)
    seg = "\n".join(_seg(t, "Table 2: Poverty and inequality results"))
    rows = []
    for lab, metric in (("Poverty headcount rate", "headcount"), ("Poverty gap", "gap"),
                        ("Poverty gap squared", "severity")):
        m = re.search(rf"^{lab} ([\d.]+)% ([\d.]+)%$", seg, re.M)
        for (survey, period, ref), v in ((("HBS 2013 (re-estimated, NBS-World Bank summary 2021)", "2013", "2013"), m.group(1)),
                                         (("HBS 2018 (NBS-World Bank summary 2021)", "2018", "2018/19"), m.group(2))):
            rows.append(C.row(metric=metric, value=float(v), survey=survey, welfare_aggregate="income",
                              line_type="national", line_level="overall", line_name="Upper poverty line (2018)",
                              line_value=4376 if period == "2018" else "", line_unit=UNIT if period == "2018" else "",
                              period=period, reference_period=ref, frequency="ad_hoc"))
    if len(rows) != 6:
        raise ValueError("Seychelles 2021 summary Table 2 not read")
    return pd.DataFrame.from_records(rows)
