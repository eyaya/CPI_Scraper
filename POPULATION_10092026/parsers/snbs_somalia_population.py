"""SNBS Somalia — 2014 Population Estimation Survey (PESS), age/sex composition
(Tier-3 PDF).

Parser for Volume II of the PESS analytical series, 'Population Composition and
Demographic Characteristics of the Somali People', whose Appendix A carries the
tables this indicator needs:

    Table A. 1: Population by age group and sex
        Age in years   Male    Percent   Female   Percent   Both sexes  Percent
        0-4          815,629    13.1    864,734    14.2     1,680,363   13.6
        …
        All Ages   6,244,764   100.0  6,072,131   100.0    12,316,895  100.0

    Table A. 2: Median age by type of residence and region
        Awdal            20      20      20
        …

Table A.1 gives national counts by five-year age band and sex; each row is checked
against male + female = both sexes. Table A.2 gives the published median age,
emitted as the schema's `median_age` measure (unit: years).

`series_type` is 'estimate': the PESS is a large-scale household SAMPLE survey
used to estimate the population — Somalia's first in more than three decades — not
a census enumeration, so tagging it 'census' would overstate it.

Table A.2's 'Type of residence' block (Rural / Urban / IDP Camps / Nomadic) is NOT
emitted: those are residence categories rather than sub-national units, and the
schema's `geography` is the country or a place within it. Only the named regions
are taken, which are genuine administrative units. Table A.3 (sex ratio by age and
residence) is likewise skipped, since its columns are residence types.
"""
from __future__ import annotations
import re
import pandas as pd
import pdfplumber

_SERIES_CODE = "SO_PESS_2014"
_PERIOD = "2014"
_GEOGRAPHY_NATIONAL = "Total country"
_TOLERANCE = 5

_T1 = re.compile(r"Table\s*A\.\s*1\s*:\s*Population\s+by\s+age\s+group\s+and\s+sex", re.I)
_T2 = re.compile(r"Table\s*A\.\s*2\s*:\s*Median\s+age", re.I)
_NUM = r"[\d,]+"
# '0-4 815,629 13.1 864,734 14.2 1,680,363 13.6'  |  'All Ages 6,244,764 100.0 …'
_A1_ROW = re.compile(
    rf"^(?P<age>\d{{1,3}}\s*-\s*\d{{1,3}}|\d{{1,3}}\s*\+|All\s+Ages)\s+"
    rf"(?P<m>{_NUM})\s+[\d.]+\s+(?P<f>{_NUM})\s+[\d.]+\s+(?P<t>{_NUM})\s+[\d.]+$", re.I)
# 'Awdal 20 20 20'
_A2_ROW = re.compile(
    r"^(?P<name>[A-Z][A-Za-z' \-]{2,30}?)\s+"
    r"(?P<m>\d{1,3})\s+(?P<f>\d{1,3})\s+(?P<t>\d{1,3})$")
# residence categories in Table A.2 that are not sub-national units
_RESIDENCE = {"rural", "urban", "idp camps", "nomadic", "type of residence", "region"}


def _int(tok: str) -> int:
    return int(tok.replace(",", ""))


def parse(local_path: str) -> pd.DataFrame:
    records = []
    with pdfplumber.open(local_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]

    # --- Table A.1: national population by age band and sex ---
    # The report's list-of-tables repeats every caption, so a page carrying the
    # caption is not necessarily the page carrying the data: pick the candidate
    # with the most matching rows.
    def _best(caption, row_re):
        cands = [t for t in pages if caption.search(t)]
        if not cands:
            return None
        return max(cands, key=lambda t: sum(
            1 for ln in t.splitlines() if row_re.match(ln.strip())))

    page = _best(_T1, _A1_ROW)
    if page:
        for line in page.splitlines():
            m = _A1_ROW.match(line.strip())
            if not m:
                continue
            male, female, total = _int(m.group("m")), _int(m.group("f")), _int(m.group("t"))
            if abs(male + female - total) > _TOLERANCE:
                continue
            age = m.group("age").strip()
            age = "Total" if age.lower().startswith("all") else age.replace(" ", "")
            for sex, v in (("male", male), ("female", female), ("total", total)):
                records.append({
                    "series_type": "estimate", "sex": sex, "age_group": age,
                    "geography": _GEOGRAPHY_NATIONAL, "period": _PERIOD,
                    "frequency": "annual", "measure": "count", "value": float(v),
                    "unit": "persons", "series_code": _SERIES_CODE,
                })

    # --- Table A.2: median age by region ---
    page = _best(_T2, _A2_ROW)
    if page:
        for line in page.splitlines():
            m = _A2_ROW.match(line.strip())
            if not m:
                continue
            name = re.sub(r"\s+", " ", m.group("name")).strip()
            if name.lower() in _RESIDENCE:
                continue                    # residence category, not a place
            # the table's own national row is captioned 'Total'
            geography = (_GEOGRAPHY_NATIONAL if name.lower() == "total" else name)
            for sex, key in (("male", "m"), ("female", "f"), ("total", "t")):
                records.append({
                    "series_type": "estimate", "sex": sex, "age_group": "Total",
                    "geography": geography, "period": _PERIOD, "frequency": "annual",
                    "measure": "median_age", "value": float(m.group(key)),
                    "unit": "years", "series_code": _SERIES_CODE,
                })

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Somalia population: Appendix A tables not found")
    counts = df[df["measure"] == "count"]
    if counts.empty or "Total" not in set(counts["age_group"]):
        raise ValueError("Somalia population: Table A.1 (age x sex) did not parse")
    return df.drop_duplicates(["geography", "sex", "age_group", "period", "measure"])
