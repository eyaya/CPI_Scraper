"""Botswana -- BCWIS 2009/10 Main Report, Volume 1 (Statistics Botswana, 2013).

The BMTHS 2015/16 brief (`botswana_poverty`) republishes the 2009/10 strata
and districts; this report adds what the brief does not print:
  Table 31  districts: share of HOUSEHOLDS poor and the number of poor
            households (the 2002/03 columns are POVERTY-MAPPING estimates --
            modelled from the 2001 census -- and are not read)
  Table 38  districts x sex: headcount and number of poor persons
  Table 39  age group x sex: headcount and number of poor persons, plus the
            report's own broad groups (children 0-11, youth 12-35, adults
            36-64, pensioners 65+)
Survey label "BCWIS 2009/10" and line "Poverty Datum Line (PDL)", as in
`botswana_poverty`, so rows the brief already gives coincide (same values).

The PDL is household-specific (age/sex composition), so no single amount.

CROSS-CHECK (verbatim): national 19.3 (male 18.1, female 20.4), 362,116 poor;
poor households 10.8% (58,285); Ngamiland West 46.2; Gaborone female 7.1;
age 0-4 25.7; pensioners 17.5; districts' poor persons sum to 362,116.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_B = dict(survey="BCWIS 2009/10", welfare_aggregate="consumption", line_type="national",
          line_level="overall", line_name="Poverty Datum Line (PDL)", period="2009",
          reference_period="2009/10", frequency="ad_hoc")
LAYOUT = {**_B, "unit_of_analysis": "person", "decimal": ".", "tables": []}
_NUM = r"(\d{1,3}(?:,\d{3})*|\d+(?:\.\d+)?)"


def _v(x):
    return float(x.replace(",", ""))


def _seg(text, caption):
    i = text.rindex(caption)
    j = text.index("BOTSWANA CORE WELFARE INDICATORS SURVEY", i)
    return [l.strip() for l in text[i:j].splitlines()]


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    rows = []

    def put(metric, v, uoa, **cut):
        rows.append(C.row(metric=metric, value=v, unit_of_analysis=uoa, **_B, **cut))

    got = 0
    for ln in _seg(text, "Table 31: Poverty Incidence by District -2002/03 & 2009/10"):
        m = re.match(rf"^([A-Z][A-Za-z /-]+?) {_NUM} {_NUM} {_NUM} {_NUM} {_NUM} {_NUM}$", ln)
        if not m:
            continue
        geo = "Total country" if m.group(1) == "National" else m.group(1)
        _, _, hc, hh, npers, nhh = m.groups()[1:]
        put("headcount", _v(hh), "household", geography=geo)
        put("poor_count", _v(nhh), "household", geography=geo, unit="households")
        got += 1
    if got != 27:
        raise ValueError(f"BCWIS Table 31: {got} rows, expected 27")
    for cap, kind in (("Table 38: Poverty Incidence by District & Sex", "district"),
                      ("Table 39: Poverty Incidence by Age Group & Sex", "age")):
        got = 0
        for ln in _seg(text, cap):
            m = re.match(rf"^(.+?) {_NUM} {_NUM} {_NUM} {_NUM} {_NUM} {_NUM}$", ln)
            if not m or m.group(1) in ("District", "Age Group"):
                continue
            lab = m.group(1)
            nm, nf, _na, hm, hf, ha = (_v(x) for x in m.groups()[1:])
            if kind == "district":
                if lab == "National":
                    base = {}
                else:
                    base = {"geography": lab}
                for sx, n, h in (("male", nm, hm), ("female", nf, hf)):
                    cut = {**base, "topic": "sex", "characteristic": sx.title(), "sex": sx}
                    put("headcount", h, "person", **cut)
                    put("poor_count", n, "person", **cut)
            else:
                if lab == "National":
                    continue
                band = re.sub(r"^(Youth|Children|Adults|Pensioners): ", "", lab).replace(" yrs.", "")
                band = band.replace(" Plus", "+")
                for sx, n, h in (("male", nm, hm), ("female", nf, hf), ("total", None, ha)):
                    cut = {"topic": "age", "characteristic": lab, "age_group": band, "sex": sx}
                    put("headcount", h, "person", **cut)
                    if n is not None:
                        put("poor_count", n, "person", **cut)
            got += 1
        want = 26 if kind == "district" else 21   # Table 38 has no Orapa row (0 poor)
        if got != want:
            raise ValueError(f"BCWIS {cap}: {got} rows, expected {want}")
    return pd.DataFrame.from_records(rows)
