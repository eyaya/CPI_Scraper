"""South Africa -- monetary poverty (Stats SA, Poverty Trends in South Africa).

PRIMARY: "Poverty Trends in South Africa: An examination of absolute poverty
between 2006 and 2023" (Report 03-10-06, published 2025, "PTR 2025"), a
Wayback `id_` copy of Stats SA's own file (statssa.gov.za answers plain
requests with an Incapsula challenge; the browser-fingerprint route was not
used). FIVE rounds on ONE line series (NPL 2023, rebased on IES 2022/23):
IES 2005/06, LCS 2008/09, IES 2010/11, LCS 2014/15, IES 2022/23, dated as the
report dates them (2006, 2009, 2011, 2015, 2023).

Three cost-of-basic-needs lines per PERSON per month (rand, Table 1.4.1):
  FPL  food poverty line        -> line_level extreme
  LBPL lower-bound poverty line -> line_level other   (the NDP's official line)
  UBPL upper-bound poverty line -> line_level overall
(the same mapping as Namibia's FPL/LBPL/UBPL). Welfare = expenditure per
capita (the WCA), i.e. consumption.

Tables are uniform: a metric block header ("Poverty Headcount (P0)",
"Incidence of Poverty (P0)", "Poverty Gap (P1)", "Severity of Poverty (P2)",
"Poverty Shares"), a line of years, then `label v1 .. vN` rows. They are read
by a small block reader over each caption's text segment (caption to next
caption, last occurrence -- the first is the contents list). A row is taken
only when the line ENDS in exactly N numeric/'*' cells after a non-empty
label, which rejects prose and chart data labels. '*' (boundary changes) is
skipped, never zero. Table 4.6.1 prints P2 with decimal POINTS, the rest with
commas; every cell here is below 1 000, so both are read as decimals.

Collected
  2.1.1 / 2.1.2 / 2.1.3  national P0, P1, P2 on all three lines (persons)
  2.2.4.1                P0 on the FPL by province
  3.2-3.9 (.1 and .2)    LBPL P0/P1/P2 and poverty shares of PERSONS by sex,
                         age, education (18+), province, settlement type,
                         household size, metro
  4.1.1                  household P0 on all three lines
  4.2-4.9 (.1 and .2)    LBPL household P0/P1/P2 and shares by sex, age,
                         education of the head, province, settlement type,
                         household size, metro
  6.8.1-6.8.3, 6.8.7-6.8.9  95% confidence limits of P0 by sex and province on
                         each line, plus the P0 values not printed elsewhere
                         (FPL/UBPL by sex, LBPL/UBPL by province are in 3.x
                         only for LBPL)
Not collected: population group (3.3.x, 4.3.x, 6.8.4-6.8.6 -- no schema
topic), counts of poor persons/households (printed in MILLIONS; no unit),
Gini (2.2.2.x, inequality), the "South Africa"/"All metros" 100 rows of
share tables, characteristic tables' own "South Africa" rows (they repeat
2.1.x/4.1.1; Table 4.5.1's prints 42,2 against 42,1 everywhere else), and
the coefficients of variation.

CROSS-CHECK (verbatim): LBPL P0 57,5 / 55,7 / 45,8 / 46,7 / 37,9; FPL 27,4 /
31,7 / 20,8 / 22,4 / 17,6; UBPL 78,7 / 76,2 / 71,0 / 71,1 / 66,7; LBPL P1 2023
14,4, P2 7,3; Limpopo 2006 75,1; households LBPL 2023 22,9; female-headed
2023 29,8.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

UNIT = "ZAR per person per month"
_LINE = {  # Table 1.4.1, NPL 2023 series
    "FPL": ("extreme", "Food poverty line (FPL)",
            {"2006": 228, "2009": 328, "2011": 348, "2015": 454, "2023": 777}),
    "LBPL": ("other", "Lower-bound poverty line (LBPL)",
             {"2006": 461, "2009": 614, "2011": 656, "2015": 827, "2023": 1300}),
    "UBPL": ("overall", "Upper-bound poverty line (UBPL)",
             {"2006": 1054, "2009": 1344, "2011": 1443, "2015": 1777, "2023": 2635}),
}
_SURVEY = {"2006": ("IES 2005/06", "2005/06"), "2009": ("LCS 2008/09", "2008/09"),
           "2011": ("IES 2010/11", "2010/11"), "2015": ("LCS 2014/15", "2014/15"),
           "2023": ("IES 2022/23", "2022/23")}
_EDITION = " (Poverty Trends 2025, NPL 2023 series)"
_PROV = {"Kwazulu-Natal": "KwaZulu-Natal"}
_EXPECT_ROWS = 1500

_CAPTION = re.compile(r"^Table (\d+(?:\.\d+)+)[:\s]\s*(?=[A-Z])")
_FIGURE = re.compile(r"^Figure \d+(?:\.\d+)+[:\s]")
_METRIC_HEAD = [(re.compile(r"^(?:Poverty Headcount|Incidence of Poverty)\b.*\(P0\)"), "headcount"),
                (re.compile(r"^Poverty Gap \(P1\)"), "gap"),
                (re.compile(r"^Severity of Poverty \(P2\)"), "severity"),
                (re.compile(r"^(?:Poverty [Ss]hares?|Share)$"), "poor_share")]
_YEARS = re.compile(r"^(?:[A-Z][A-Za-z ]{0,30}\s)?((?:(?:19|20)\d{2}\s*)+)$")
_NUM = re.compile(r"^-?\d+(?:[.,]\d+)?%?$")

# table id -> (topic, unit_of_analysis, extra cell attributes)
_TABLES = {
    "3.2.1": ("sex", "person", {}), "3.2.2": ("sex", "person", {}),
    "3.4.1": ("age", "person", {}), "3.4.2": ("age", "person", {}),
    "3.5.1": ("education", "person", {"age_group": "18 years and older"}),
    "3.5.2": ("education", "person", {"age_group": "18 years and older"}),
    "3.6.1": ("province", "person", {}), "3.6.2": ("province", "person", {}),
    "3.7.1": ("locality", "person", {}), "3.7.2": ("locality", "person", {}),
    "3.8.1": ("household_size", "person", {}), "3.8.2": ("household_size", "person", {}),
    "3.9.1": ("metro", "person", {}), "3.9.2": ("metro", "person", {}),
    "4.2.1": ("sex_of_head", "household", {}), "4.2.2": ("sex_of_head", "household", {}),
    "4.4.1": ("age_of_head", "household", {}), "4.4.2": ("age_of_head", "household", {}),
    "4.5.1": ("education_of_head", "household", {}), "4.5.2": ("education_of_head", "household", {}),
    "4.6.1": ("province", "household", {}), "4.6.2": ("province", "household", {}),
    "4.7.1": ("locality", "household", {}), "4.7.2": ("locality", "household", {}),
    "4.8.1": ("household_size", "household", {}), "4.8.2": ("household_size", "household", {}),
    "4.9.1": ("metro", "household", {}), "4.9.2": ("metro", "household", {}),
}
LAYOUT = {"survey": "IES 2022/23" + _EDITION, "welfare_aggregate": "consumption",
          "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
          "line_type": "national", "line_level": "other",
          "line_name": _LINE["LBPL"][1], "line_unit": UNIT,
          "period": "2023", "reference_period": "2022/23", "tables": []}


def _years(ln: str):
    """A header of survey years, optionally after a stub word ("Province 2006
    2009 ..."): the years, [] for a year line naming other years (a chart
    axis), None for any other line."""
    m = _YEARS.match(ln)
    if not m:
        return None
    ys = m.group(1).split()
    return ys if set(ys) <= set(_SURVEY) else []


def _val(tok: str):
    if tok == "*":
        return None
    return float(tok.rstrip("%").replace(",", "."))


def _segments(pages: list[str]) -> dict[str, list[str]]:
    """table id -> its lines, from its LAST caption occurrence to the next caption."""
    flat = []
    for t in pages:
        for ln in t.splitlines():
            s = ln.strip()
            if not s or "Poverty Trends in South Africa |" in s or s.startswith("Chapter "):
                continue
            flat.append(s)
    starts, ends = {}, []
    for i, s in enumerate(flat):
        m = _CAPTION.match(s)
        if m:
            starts[m.group(1)] = i
            ends.append(i)
        elif _FIGURE.match(s):
            ends.append(i)   # a figure caption also closes the table before it
    order = sorted(ends)
    out = {}
    for tid, i in starts.items():
        nxt = [j for j in order if j > i]
        out[tid] = flat[i + 1:(nxt[0] if nxt else i + 120)]
    return out


def _row(line: str, n: int):
    toks = line.split()
    if len(toks) <= n:
        return None
    cells = toks[-n:]
    if not all(c == "*" or _NUM.match(c) for c in cells):
        return None
    label = " ".join(toks[:-n]).strip()
    if not label or not re.match(r"^[A-Za-z0-9]", label) or "%" in label:
        return None
    # the label must not itself end in a number that belongs to the data
    if _NUM.match(toks[-n - 1]) and not re.search(r"[–\-]\s*\d+$|^\d+$", label):
        return None
    return label, [_val(c) for c in cells]


def _base(period: str, line: str, unit: str) -> dict:
    level, name, vals = _LINE[line]
    survey, ref = _SURVEY[period]
    return dict(survey=survey + _EDITION, welfare_aggregate="consumption",
                unit_of_analysis=unit, line_type="national", line_level=level,
                line_name=name, line_value=vals[period], line_unit=UNIT,
                period=period, reference_period=ref, frequency="ad_hoc")


# Every row label each topic may carry, as printed. A label outside its
# topic's set is not read: the reader scans whole text segments, and a stray
# line of prose ending in N numbers must not become a province or an age band.
_PROVINCES = {"Western Cape", "Eastern Cape", "Northern Cape", "Free State",
              "KwaZulu-Natal", "Kwazulu-Natal", "North West", "Gauteng",
              "Mpumalanga", "Limpopo"}
_METROS = {"All metros", "City of Cape Town", "Buffalo City", "Nelson Mandela Bay",
           "eThekwini Metropolitan", "Mangaung Metropolitan", "City of Johannesburg",
           "Ekurhuleni", "City of Tshwane"}
# The share tables shorten two metro names; filed under the names the
# measures tables print, so a metro is one geography.
_METRO_ALIAS = {"eThekwini": "eThekwini Metropolitan", "Mangaung": "Mangaung Metropolitan"}
_EDU = {"None", "Some primary", "Primary", "Some secondary", "Matric", "Higher"}
_OK = {
    "province": lambda l: l in _PROVINCES, "metro": lambda l: _METRO_ALIAS.get(l, l) in _METROS,
    "sex": lambda l: l in ("Male", "Female"), "sex_of_head": lambda l: l in ("Male", "Female"),
    "locality": lambda l: l in ("Urban", "Rural"),
    "age": lambda l: bool(re.fullmatch(r"\d+ ?[–-] ?\d+|\d+\+", l)),
    "age_of_head": lambda l: bool(re.fullmatch(r"\d+ ?[–-] ?\d+|\d+\+", l)),
    "education": lambda l: l in _EDU, "education_of_head": lambda l: l in _EDU,
    "household_size": lambda l: bool(re.fullmatch(r"(?:\d+|\d+ - \d+|\d+\+) (?:household )?members?", l)),
}


def _cut(topic: str, label: str, unit: str) -> dict | None:
    """Cell attributes for one characteristic row; None = do not read it."""
    if not _OK[topic](label):
        return None
    if label in ("South Africa", "All metros") and topic != "metro":
        return None
    if topic == "metro":
        return {"topic": "total", "geography": _METRO_ALIAS.get(label, label)}
    if topic == "province":
        return {"topic": "total", "geography": _PROV.get(label, label)}
    if topic in ("sex", "sex_of_head"):
        sx = {"Male": "male", "Female": "female"}.get(label)
        return {"topic": topic, "characteristic": label, "sex": sx} if sx else None
    if topic == "locality":
        loc = {"Urban": "urban", "Rural": "rural"}.get(label)
        return {"topic": "locality", "locality": loc, "locality_label": label} if loc else None
    return {"topic": topic, "characteristic": label}


def _emit(rows, metric, value, base, cut, extra):
    if value is None:
        return
    rows.append(C.row(metric=metric, value=value, **base, **cut, **extra))


def _block_table(rows, seg, topic, unit, extra):
    metric, years = None, None
    for ln in seg:
        for rx, m in _METRIC_HEAD:
            if rx.match(ln):
                metric, years = m, None
                break
        else:
            if _years(ln) is not None:
                years = _years(ln) or None
                continue
            if not (metric and years):
                continue
            r = _row(ln, len(years))
            if not r:
                continue
            label, vals = r
            # 3.5.1's "South Africa" row is the 18+ population, not a repeat
            if label == "South Africa" and topic == "education" and metric != "poor_share" and unit == "person":
                cut = {"topic": "total"}
            elif label == "All metros" and metric == "poor_share":
                continue
            else:
                cut = _cut(topic, label, unit)
            if cut is None:
                continue
            for y, v in zip(years, vals):
                _emit(rows, metric, v, _base(y, "LBPL", unit), cut, extra)


_YRS5 = ["2006", "2009", "2011", "2015", "2023"]


def _national(rows, segs):
    """2.1.1 headcount / 2.1.2 gap / 2.1.3 severity (persons), 4.1.1 households."""
    joined = {t: " ".join(segs.get(t, [])) for t in ("2.1.1", "2.1.2", "2.1.3", "4.1.1")}
    num = r"((?:\s+-?\d+,\d%?){5})"
    specs = [
        ("2.1.1", r"Percentage of the population that is UBPL poor" + num, "headcount", "UBPL", "person"),
        ("2.1.1", r"Percentage of the population that is LBPL poor" + num, "headcount", "LBPL", "person"),
        ("2.1.1", r"Percentage of the population living in extreme" + num, "headcount", "FPL", "person"),
        ("2.1.2", r"Poverty gap for the FPL" + num, "gap", "FPL", "person"),
        ("2.1.2", r"Poverty gap for the LBPL" + num, "gap", "LBPL", "person"),
        ("2.1.2", r"Poverty gap for the UBPL" + num, "gap", "UBPL", "person"),
        ("2.1.3", r"Severity of poverty for the FPL" + num, "severity", "FPL", "person"),
        ("2.1.3", r"Severity of poverty for the LBPL" + num, "severity", "LBPL", "person"),
        ("2.1.3", r"Severity of poverty for the UBPL" + num, "severity", "UBPL", "person"),
        ("4.1.1", r"Percentage of the households that is UBPL poor" + num, "headcount", "UBPL", "household"),
        ("4.1.1", r"Percentage of the households that is below the LBPL" + num, "headcount", "LBPL", "household"),
        ("4.1.1", r"Percentage of the households living in extreme poverty" + num, "headcount", "FPL", "household"),
    ]
    for tid, rx, metric, line, unit in specs:
        m = re.search(rx, joined[tid])
        if not m:
            raise ValueError(f"Stats SA PTR: Table {tid} row {rx[:50]!r} not found")
        for y, tok in zip(_YRS5, m.group(1).split()):
            _emit(rows, metric, _val(tok), _base(y, line, unit), {"topic": "total"}, {})


def _fpl_provinces(rows, segs):
    years = None
    for ln in segs["2.2.4.1"]:
        if _years(ln) is not None:
            years = _years(ln) or None
            continue
        r = years and _row(ln, len(years))
        if r and r[0] in _PROVINCES:
            for y, v in zip(years, r[1]):
                _emit(rows, "headcount", v, _base(y, "FPL", "person"),
                      {"topic": "total", "geography": _PROV.get(r[0], r[0])}, {})


_CI = {"6.8.1": ("sex", "FPL"), "6.8.2": ("sex", "LBPL"), "6.8.3": ("sex", "UBPL"),
       "6.8.7": ("province", "FPL"), "6.8.8": ("province", "LBPL"), "6.8.9": ("province", "UBPL")}
# P0 values that 6.8.x is the ONLY table to print (the rest repeat 3.2.1/3.6.1/2.2.4.1)
_CI_NEW_P0 = {("sex", "FPL"), ("sex", "UBPL"), ("province", "UBPL")}
_CI_ROW = re.compile(r"^(.+?)\s+((?:19|20)\d{2})\s+(\d+,\d)\s+(\d+,\d)\s+(\d+,\d)\s+(\d+,\d+)$")


def _ci(rows, segs):
    for tid, (topic, line) in _CI.items():
        n = 0
        for ln in segs.get(tid, []):
            m = _CI_ROW.match(ln)
            if not m or m.group(2) not in _SURVEY:
                continue
            label = m.group(1)
            if label == "South Africa":
                continue
            cut = _cut(topic, label, "person")
            if cut is None:
                continue
            base = _base(m.group(2), line, "person")
            lo, p0, hi = (_val(m.group(k)) for k in (3, 4, 5))
            _emit(rows, "headcount_ci_low", lo, base, cut, {})
            _emit(rows, "headcount_ci_high", hi, base, cut, {})
            if (topic, line) in _CI_NEW_P0:
                _emit(rows, "headcount", p0, base, cut, {})
            n += 1
        if n == 0:
            raise ValueError(f"Stats SA PTR: no confidence-limit rows read from Table {tid}")


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    segs = _segments(pages)
    rows: list[dict] = []
    _national(rows, segs)
    _fpl_provinces(rows, segs)
    for tid, (topic, unit, extra) in _TABLES.items():
        if tid not in segs:
            raise ValueError(f"Stats SA PTR: Table {tid} not found")
        before = len(rows)
        _block_table(rows, segs[tid], topic, unit, extra)
        if len(rows) == before:
            raise ValueError(f"Stats SA PTR: Table {tid} produced no rows")
    _ci(rows, segs)
    if len(rows) < _EXPECT_ROWS:
        raise ValueError(f"Stats SA PTR: {len(rows)} rows, expected >= {_EXPECT_ROWS}")
    return pd.DataFrame.from_records(rows)
