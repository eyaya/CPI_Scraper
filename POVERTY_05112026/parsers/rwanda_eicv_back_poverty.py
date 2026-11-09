"""Rwanda -- EICV1-EICV5 back-series (2000/01-2016/17), beside EICV7 (`rwanda_poverty`).

Two NISR poverty-profile reports, each its own descriptor (Wayback `id_`
copies of NISR's own files -- statistics.gov.rw answers plain requests with a
bot check, which this project does not circumvent):

* `parse` -- "Rwanda Poverty Profile Report 2013/14" (EICV4):
    Table 9   national P0 / P1 / P2 for EICV1 2000/01, EICV2 2005/06, EICV3
              2010/11, EICV4 2013/14 (P2 printed "FGT2 *100", i.e. percent).
    Table 8   30 districts, poverty and extreme poverty, 2013/14.
    Table C.1 / C.2  provinces (+ urban/rural for 2005/06 and 2010/11) for
              EICV1-EICV3, poverty and extreme poverty.
    Table C3  30 districts, poverty and extreme poverty, 2010/11.
    Not read: C.4 (depth AMONG THE POOR, 0.414 = P1/P0 -- no schema metric),
    C.5 (Gini), Watts index.
* `parse_eicv5` -- "Rwanda Poverty Profile Report EICV5 2016/17":
    Table 1   P0 and poverty gap, EICV3 / EICV4 / EICV5 (national).
    Table 16  total and extreme P0 by urban/rural and province, EICV4 and EICV5.
    Table 17  distribution of the poor and of the population, same cuts.
    Table 26  P0 by demographic group (adult men/women, boys/girls < 16).
    Not read: Table 3 (an earlier print of Table 16 -- it gives EICV4 rural
    43.8 against Table 16's 43.7; Table 16 is the chapter table), Table 18
    (absolute contribution = P0 x share, derivable), panel transition
    matrices, characteristics of the poor (distributions, not rates).

ONE NISR SERIES, AS NISR PRINTS IT: both reports print the 2000/01-2013/14
headcounts identically (58.9 / 56.7 / 44.9 / 39.1), on the poverty line of
RWF 159,375 per adult equivalent per year (extreme RWF 105,064; January 2014
prices). That is a DIFFERENT line from EICV7's (RWF 560,127), so the line
name differs, and so does the 2016/17 estimate: 38.2 here, 39.x when NISR
re-predicts EICV5 on the EICV7 basis (collected separately, own survey
label). PERIOD = the END year of the round, as the existing Rwanda rows
(EICV7 2023/24 -> 2024) already do: 2001, 2006, 2011, 2014, 2017.

Provinces use the names the EICV7 rows use: Kigali City, South, West, North,
East.

CROSS-CHECK (verbatim): EICV1-4 58.9 / 56.7 / 44.9 / 39.1; gap 24.4 / 22.3 /
14.8 / 12.0; extreme 40 / 35.8 / 24.1 / 16.3; EICV5 38.2 (extreme 16.0, gap
11.7); Nyamasheke 2013/14 62.0 (extreme 39.2); Nyamagabe 2010/11 73.3;
Kigali City 2016/17 13.9.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T

_OVER = {"line_level": "overall", "line_name": "National poverty line (NISR, EICV4 basis, January 2014 prices)",
         "line_value": 159375, "line_unit": "RWF per adult equivalent per year"}
_EXT = {"line_level": "extreme",
        "line_name": "National extreme poverty line (NISR, EICV4 basis, January 2014 prices)",
        "line_value": 105064, "line_unit": "RWF per adult equivalent per year"}
_ROUNDS = {"2001": ("EICV1 2000/01", "2000/01"), "2006": ("EICV2 2005/06", "2005/06"),
           "2011": ("EICV3 2010/11", "2010/11"), "2014": ("EICV4 2013/14", "2013/14"),
           "2017": ("EICV5 2016/17", "2016/17")}
_PROV = {"Kigali city": "Kigali City", "Kigali City": "Kigali City",
         "Southern Province": "South", "Southern": "South",
         "Western Province": "West", "Western": "West",
         "Northern Province": "North", "Northern": "North",
         "Eastern Province": "East", "Eastern": "East"}

LAYOUT = {"survey": "EICV4 2013/14", "welfare_aggregate": "consumption",
          "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
          "line_type": "national", **_OVER, "period": "2014", "reference_period": "2013/14",
          "tables": []}
LAYOUT_EICV5 = {**LAYOUT, "survey": "EICV5 2016/17", "period": "2017", "reference_period": "2016/17"}


def _base(period, line, **kw) -> dict:
    survey, ref = _ROUNDS[period]
    d = dict(survey=survey, welfare_aggregate="consumption", unit_of_analysis="person",
             line_type="national", period=period, reference_period=ref, frequency="ad_hoc",
             **line)
    d.update(kw)
    return d


def _place(label: str) -> dict | None:
    s = re.sub(r"\s+", " ", label).strip()
    if s in ("Rwanda", "Total", "All Rwanda"):
        return {}
    if s in ("Urban", "Rural"):
        return {"topic": "locality", "locality": s.lower(), "locality_label": s}
    if s in _PROV:
        return {"geography": _PROV[s]}
    return None


def _page(pages, caption):
    for p in pages:
        if re.search(caption, p) and len(re.findall(r"\.{8,}", p)) < 5:
            return p
    raise ValueError(f"caption not found: {caption!r}")


def _block(text, start, end):
    m = re.search(start, text)
    body = text[m.end():]
    e = re.search(end, body, re.M) if end else None
    return (body[:e.start()] if e else body).splitlines()


_NUM = r"-?\d+(?:\.\d+)?"


def _districts(text, start, end, period, expect=30):
    """'No District Poverty Extreme' printed two-across:
    '1 Kicukiro 16.3 6.5 16 Nyamagabe 41.5 13.0'."""
    out, seen = [], set()
    pat = re.compile(rf"(\d{{1,2}})\s+([A-Z][a-z]+)\s+({_NUM})\s+({_NUM})")
    for ln in _block(text, start, end):
        for m in pat.finditer(ln):
            name = m.group(2)
            if name in seen:
                continue
            seen.add(name)
            geo = {"geography": f"{name} (district)"}
            out.append(C.row(metric="headcount", value=float(m.group(3)), **_base(period, _OVER), **geo))
            out.append(C.row(metric="headcount", value=float(m.group(4)), **_base(period, _EXT), **geo))
    if len(seen) != expect:
        raise ValueError(f"districts {period}: expected {expect}, got {len(seen)}")
    return out


def parse(path: str) -> pd.DataFrame:
    """EICV4 poverty profile (2013/14)."""
    P = T._pages(path, halves=False)["full"]
    out = []
    # Table 9 -- national, four rounds
    t9 = _page(P, r"Table 9: Summary of poverty measures at national level")
    lines = _block(t9, r"Table 9: Summary of poverty measures at national level", r"^Watts index")
    years = ["2001", "2006", "2011", "2014"]
    got = {}
    for ln in lines:
        for key, metric in (("Headcount ratio", "headcount"), ("Poverty gap ratio", "gap"),
                            ("measure \\(FGT2\\)", "severity")):
            if re.search(key, ln):
                nums = re.findall(_NUM, ln.split(")")[-1] if metric == "severity" else ln)
                nums = [float(x) for x in nums][-4:]
                got[metric] = nums
        # the FGT2 values print on the line ABOVE its label ("13 11.4 6.6 5.2")
    sev = [l for l in lines if re.fullmatch(rf"(?:Poverty severity\s+)?(?:{_NUM}\s+){{3}}{_NUM}", l.strip())]
    if "severity" not in got or len(got["severity"]) != 4:
        if sev:
            got["severity"] = [float(x) for x in re.findall(_NUM, sev[0])][-4:]
    for metric in ("headcount", "gap", "severity"):
        vals = got.get(metric, [])
        if len(vals) != 4:
            raise ValueError(f"Table 9: {metric} row not read ({vals})")
        for y, v in zip(years, vals):
            out.append(C.row(metric=metric, value=v, **_base(y, _OVER)))
    # Table 8 -- districts 2013/14
    t8 = _page(P, r"Table 8: Population \(%\) identified as poor and extremely poor by district")
    out += _districts(t8, r"Table 8: Population", r"^Figure 17", "2014")
    # Tables C.1 / C.2 -- provinces, 2000/01-2010/11
    c = _page(P, r"Table C\.1: Percentage of the Rwandan population identified as poor")
    for start, end, line in ((r"Table C\.1:[^\n]*\n", r"^Table C\.2", _OVER),
                             (r"Table C\.2:[^\n]*\n", r"^Table C3", _EXT)):
        n = 0
        for ln in _block(c, start, end):
            m = re.match(rf"^([A-Za-z][A-Za-z ]+?)\s+((?:{_NUM}\s*)+)$", ln.strip())
            if not m:
                continue
            pl = _place(m.group(1))
            if pl is None:
                continue
            nums = [float(x) for x in m.group(2).split()]
            yrs = years[:3] if len(nums) == 3 else years[1:3] if len(nums) == 2 else None
            if yrs is None:
                continue
            for y, v in zip(yrs, nums):
                # National P0 for these rounds is already read from Table 9.
                if not pl and line is _OVER:
                    continue
                out.append(C.row(metric="headcount", value=v, **_base(y, line), **pl))
            n += 1
        if n != 8:
            raise ValueError(f"{start}: expected 8 rows, got {n}")
    out += _districts(c, r"Table C3: Distribution of poverty", None, "2011")
    return pd.DataFrame(out)


def parse_eicv5(path: str) -> pd.DataFrame:
    """EICV5 poverty profile (2016/17)."""
    P = T._pages(path, halves=False)["full"]
    out = []
    t1 = _page(P, r"Table 1\. Summary of poverty rates, 2011-2017")
    for ln in _block(t1, r"Table 1\. Summary of poverty rates, 2011-2017", r"^Sample size"):
        for key, metric in (("Headcount Poverty rate", "headcount"), ("Poverty Gap rate", "gap")):
            if ln.startswith(key):
                vals = [float(x) for x in re.findall(_NUM, ln)]
                if len(vals) != 3:
                    raise ValueError(f"Table 1 {metric}: {vals}")
                for y, v in zip(("2011", "2014", "2017"), vals):
                    out.append(C.row(metric=metric, value=v, **_base(y, _OVER)))
    # Table 16 -- total & extreme P0, 2014 / 2017 (+ change, not read)
    t16 = _page(P, r"Table 16\. Poverty Headcount Rates by Province")
    n = 0
    for ln in _block(t16, r"Table 16\. Poverty Headcount Rates by Province", r"^Sources:"):
        m = re.match(rf"^([A-Za-z][A-Za-z ]+?)\s+({_NUM})\s+({_NUM})\s+{_NUM}\s*\*?\s+({_NUM})\s+({_NUM})\s+{_NUM}", ln.strip())
        if not m:
            continue
        pl = _place(m.group(1))
        if pl is None:
            continue
        for y, line, v in (("2014", _OVER, m.group(2)), ("2017", _OVER, m.group(3)),
                           ("2014", _EXT, m.group(4)), ("2017", _EXT, m.group(5))):
            # National total P0 2014 and 2017 come from Table 1.
            if not pl and line is _OVER:
                continue
            out.append(C.row(metric="headcount", value=float(v), **_base(y, line), **pl))
        n += 1
    if n != 8:
        raise ValueError(f"Table 16: expected 8 rows, got {n}")
    # Table 17 -- distribution of the poor / of the population
    t17 = _page(P, r"Table 17\. Poverty by Geographic Domain")
    n = 0
    for ln in _block(t17, r"Table 17\. Poverty by Geographic Domain", r"^Sources:"):
        m = re.match(rf"^([A-Za-z][A-Za-z ]+?)\s+({_NUM})\s+({_NUM})\s+{_NUM}\s+({_NUM})\s+({_NUM})\s+{_NUM}$", ln.strip())
        if not m:
            continue
        pl = _place(m.group(1))
        if pl is None or not pl:
            continue
        for y, metric, v in (("2014", "poor_share", m.group(2)), ("2017", "poor_share", m.group(3)),
                             ("2014", "population_share", m.group(4)), ("2017", "population_share", m.group(5))):
            out.append(C.row(metric=metric, value=float(v), **_base(y, _OVER), **pl))
        n += 1
    if n != 7:
        raise ValueError(f"Table 17: expected 7 rows, got {n}")
    # Table 26 -- demographic groups
    t26 = _page(P, r"Table 26\. Poverty rate by demographic group")
    groups = {"Adult males": ("male", "Adults"), "Adult females": ("female", "Adults"),
              "Boys (age < 16)": ("male", "age < 16"), "Girls (age < 16)": ("female", "age < 16")}
    n = 0
    for ln in _block(t26, r"Table 26\. Poverty rate by demographic group", r"^Sources:"):
        for lab, (sex, age) in groups.items():
            if ln.strip().startswith(lab):
                vals = [float(x) for x in re.findall(_NUM, ln[len(lab):])]
                for y, v in zip(("2014", "2017"), vals[-2:]):
                    out.append(C.row(metric="headcount", value=v, topic="sex", characteristic=lab,
                                     sex=sex, age_group=age, **_base(y, _OVER)))
                n += 1
    if n != 4:
        raise ValueError(f"Table 26: expected 4 rows, got {n}")
    return pd.DataFrame(out)
