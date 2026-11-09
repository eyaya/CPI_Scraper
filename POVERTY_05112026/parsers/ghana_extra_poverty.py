"""Ghana -- the GSS poverty publications beyond the GLSS 7 profile (time and
geographic depth), one parse function and LAYOUT per report.

1. `parse_glss6` -- "Poverty Profile in Ghana 2005-2013" (GLSS 6, 2014),
   Appendix 5: GLSS 5 (2005/06) and GLSS 6 (2012/13) on the ORIGINAL 2005/06
   lines (GH¢370.89 upper, GH¢288.47 extreme). This is the method behind the
   28.5% figure GSS published for 2005/06 before rebasing; filed as line_level
   "other" with the old line's name, so it can never share an ID with the
   rebased GH¢1,314 / GH¢792.05 series (31.9% for the same survey).
   Its Appendix 1 (new lines) repeats the GLSS 7 profile's values and is not read.
   PUBLISHED DEFECT: A5.1's 2005/06 REGIONAL block is a cell-for-cell copy of
   A5.2's (extreme line) -- Western 8.1, Upper West 79.1 under a national 28.5,
   whereas the population-weighted regions give 18.2 = A5.2's national 18.1.
   That block is not read; A5.1 strata (both years) and regions (2012/13) are.

2. `parse_map2010` -- "Ghana Poverty Map" (GSS, 2015): small-area estimates
   from the 2010 Population and Housing Census and GLSS 6, upper line
   GH¢1,314, for 10 regions and 216 districts / sub-metros (Tables A1.1-A1.10):
   P0, P1, P2 and the estimated number of poor. Standard errors (printed as
   fractions) and the Gini (inequality) are not read. Period 2010 = the census
   population the estimates describe.

3. `parse_sae2017` -- "Ghana Poverty Mapping Brief 2016/17" (GSS, 2023):
   Fay-Herriot small-area P0 with its 95% CI for every district (Annex), and
   the GLSS 7 DIRECT regional 95% CIs (Table 1). The direct point estimates
   repeat the GLSS 7 profile exactly (Western 21.1 ... National 23.4) and are
   not re-emitted; only their CI bounds are added under the profile's survey.

Not usable (inventory): GLSS 3 / GLSS 4 main reports (no poverty tables --
GSS published those rounds in "Poverty Trends in Ghana in the 1990s" (2000)
and "Pattern and Trends of Poverty in Ghana 1991-2006" (2007), neither of
which survives on any GSS host or in the Wayback CDX).

4. `parse_map2005` -- "Ghana Census-Based Poverty Map" (GSS / DfID, 2005;
   GSS edition 2015): Census 2000 + GLSS 4 small-area estimates printed on
   0-1 (unit "index"): Table 3 strata (GLSS 4 actual and census-predicted)
   and Annexe 3 (10 regions, 110 districts x total / urban / rural).
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_BASE = {"welfare_aggregate": "consumption", "unit_of_analysis": "person",
         "line_type": "national", "frequency": "ad_hoc"}

_OLD_UP = {"line_level": "other",
           "line_name": "2005/06 upper poverty line GH¢370.89 (pre-2013 method)",
           "line_value": 370.89, "line_unit": "GHS per adult equivalent per year, 2005/06 method"}
_OLD_EX = {"line_level": "other",
           "line_name": "2005/06 extreme poverty line GH¢288.47 (pre-2013 method)",
           "line_value": 288.47, "line_unit": "GHS per adult equivalent per year, 2005/06 method"}
_UP_2013 = {"line_level": "overall", "line_name": "Poverty line GH¢1,314",
            "line_value": 1314, "line_unit": "GHS per adult equivalent per year, GLSS 6 basis"}

LAYOUT_GLSS6 = {**_BASE, **_OLD_UP, "survey": "GLSS 5 (2005/06), 2005/06 method",
                "period": "2005", "tables": []}
LAYOUT_MAP2010 = {**_BASE, **_UP_2013,
                  "survey": "Ghana Poverty Map 2015 (small-area estimates, PHC 2010 + GLSS 6)",
                  "period": "2010", "tables": []}
LAYOUT_SAE2017 = {**_BASE, "line_level": "overall", "line_name": "Poverty line GH¢1,314",
                  "survey": "Ghana Poverty Map 2016/17 (Fay-Herriot small-area estimates, GLSS 7 + PHC 2010)",
                  "period": "2016", "tables": []}

_STRATA = {"Accra (GAMA)": ("other", "Accra (GAMA)"), "Urban Coastal": ("other", "Urban Coastal"),
           "Urban Forest": ("other", "Urban Forest"), "Urban Savannah": ("other", "Urban Savannah"),
           "Rural Coastal": ("other", "Rural Coastal"), "Rural Forest": ("other", "Rural Forest"),
           "Rural Savannah": ("other", "Rural Savannah")}
_REGIONS = ["Western", "Central", "Greater Accra", "Volta", "Eastern", "Ashanti",
            "Brong Ahafo", "Northern", "Upper East", "Upper West"]
_NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def _pages(path: str, x_tolerance: float = 3) -> list[str]:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return [(p.crop((0, 0, p.width, p.height)).extract_text(x_tolerance=x_tolerance) or "")
                for p in pdf.pages]


def _nums(s: str) -> list[float]:
    out = []
    for t in _NUM.findall(s):
        t = t.replace(",", "")
        try:
            out.append(float(t))
        except ValueError:
            pass
    return out


def _row(cell: dict, layout: dict, metric: str, value: float) -> dict:
    a = {**layout, **cell}
    return C.row(metric=metric, value=value, survey=a["survey"],
                 welfare_aggregate=a["welfare_aggregate"], line_type=a["line_type"],
                 line_level=a["line_level"], line_name=a["line_name"],
                 line_value=a.get("line_value", ""), line_unit=a.get("line_unit", ""),
                 period=a["period"], reference_period=a.get("reference_period", a["period"]),
                 frequency="ad_hoc", unit_of_analysis="person",
                 topic=a.get("topic", "total"), characteristic=a.get("characteristic", "Total"),
                 geography=a.get("geography", "Total country"),
                 locality=a.get("locality", "all"), locality_label=a.get("locality_label", "Total"))


# ---------------------------------------------------------------- 1. GLSS 6
# Appendix 5 columns: share | welfare | P0 P1 P2 | P1/P0 | C0 C1 C2
_A5 = [("population_share", 0), ("headcount", 2), ("gap", 3), ("severity", 4),
       ("poor_share", 6), ("gap_contribution", 7), ("severity_contribution", 8)]


def _a5_blocks(text: str) -> list[tuple[str, list[str]]]:
    """Split an Appendix 5 page into its four (year, lines) blocks."""
    blocks, cur, year = [], [], None
    for ln in text.splitlines():
        m = re.match(r"^\s*(2005/06|2012/13)\s*$", ln)
        if m:
            if year:
                blocks.append((year, cur))
            year, cur = m.group(1), []
            continue
        if year:
            cur.append(ln.strip())
    if year:
        blocks.append((year, cur))
    return blocks


def parse_glss6(path: str) -> pd.DataFrame:
    pages = _pages(path)
    rows = []
    for page in pages:
        if "Table A5.1" in page:
            line, table = _OLD_UP, "A5.1"
        elif "Table A5.2" in page:
            line, table = _OLD_EX, "A5.2"
        else:
            continue
        for bi, (year, lines) in enumerate(_a5_blocks(page)):
            period = year[:4]
            survey = ("GLSS 5 (2005/06), 2005/06 method" if period == "2005"
                      else "GLSS 6 (2012/13), at the 2005/06 lines")
            regional = bi >= 2          # blocks 0-1 strata, 2-3 regions
            if table == "A5.1" and regional and period == "2005":
                continue                # the copied block (see module docstring)
            for ln in lines:
                lab = None
                if regional:
                    for r in _REGIONS + ["Ghana"]:
                        if re.match(rf"^{re.escape(r)}\s+\d", ln):
                            lab = r
                else:
                    for s in list(_STRATA) + ["Ghana"]:
                        if ln.startswith(s + " "):
                            lab = s
                if not lab:
                    continue
                # "Ghana 100.0 736.80 28.5 9.6 4.6 3 3.6 100.0 ..." -- the P1/P0
                # cell is split by the text layer; it is not read, so re-join
                # only to keep the column count right.
                tail = re.sub(r"(\s\d)\s(\d\.\d\s)", r"\1\2", ln[len(lab):])
                v = _nums(tail)
                if len(v) != 9:
                    continue
                if lab == "Ghana":
                    if regional:
                        continue        # the national row is read once, from the strata block
                    cell = {}
                elif regional:
                    cell = {"geography": lab}
                else:
                    loc, ll = _STRATA[lab]
                    cell = {"topic": "locality", "locality": loc, "locality_label": ll}
                lay = {**LAYOUT_GLSS6, **line, "survey": survey, "period": period,
                       "reference_period": year}
                for metric, idx in _A5:
                    if lab == "Ghana" and metric in ("population_share", "poor_share",
                                                     "gap_contribution", "severity_contribution"):
                        continue        # 100.0 by construction
                    rows.append(_row(cell, lay, metric, v[idx]))
    if not rows:
        raise ValueError(f"{path}: Appendix 5 not found")
    return pd.DataFrame(rows)


# ------------------------------------------------------------ 2. map 2010
# Region/District | Population | P0 se | P1 se | P2 se | Gini | number of poor
def parse_map2010(path: str) -> pd.DataFrame:
    pages = _pages(path)
    rows, seen = [], set()
    for page in pages:
        if not re.search(r"Table A1\.\d+:\s*Poverty and Inequality Estimates of", page):
            continue
        lines = [l.strip() for l in page.splitlines()]
        pending = ""
        for ln in lines:
            if re.match(r"^(Table|\(Poverty|Poverty|head|Household|Region/|0 1 2|Source)", ln):
                pending = ""
                continue
            if not re.search(r"\d", ln):
                pending = (pending + " " + ln).strip()   # a wrapped district name
                continue
            m = re.match(r"^([A-Za-z][^\d]*?)\s+(\d[\d,]*\s.*)$", ln)
            if not m:
                pending = ""
                continue
            name = (pending + " " + m.group(1)).strip()
            pending = ""
            v = _nums(m.group(2))
            if len(v) != 9:
                continue
            reg = re.sub(r"\s+Region$", "", name)
            if reg in _REGIONS:
                geo = reg
            else:
                geo = name
            if geo in seen:
                continue
            seen.add(geo)
            cell = {"geography": geo}
            for metric, idx in (("headcount", 1), ("gap", 3), ("severity", 5), ("poor_count", 8)):
                rows.append(_row(cell, {**LAYOUT_MAP2010, "reference_period": "PHC 2010 / GLSS 6 2012/13"},
                                 metric, v[idx]))
    n_geo = len(seen)
    if n_geo < 220:
        raise ValueError(f"{path}: {n_geo} regions/districts read, expected >= 220 (10 + 216)")
    return pd.DataFrame(rows)


# ------------------------------------------------------------ 3. SAE 2016/17
def parse_sae2017(path: str) -> pd.DataFrame:
    pages = _pages(path, x_tolerance=1)     # default tolerance glues "AhantaWest"
    rows, n = [], 0
    lay = {**LAYOUT_SAE2017, "reference_period": "2016/17"}
    for page in pages:
        if "Annex - Table of Poverty Estimates" in page or re.search(r"^Region Population Poverty 95%", page, re.M):
            for ln in page.splitlines():
                m = re.match(r"^(western|central|greater accra|volta|eastern|ashanti|brong ahafo|"
                             r"northern|upper east|upper west)\s+(.+?)\s+([\d,]+)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)\s*$",
                             ln.strip())
                if not m:
                    continue
                n += 1
                cell = {"geography": m.group(2).strip()}
                for metric, g in (("headcount", 4), ("headcount_ci_low", 5), ("headcount_ci_high", 6)):
                    rows.append(_row(cell, lay, metric, float(m.group(g))))
        if "Table 1: Direct estimates of headcount poverty" in page:
            glss7 = {**LAYOUT_SAE2017, "survey": "GLSS 7 (2016/17)", "reference_period": "2016/17",
                     "line_value": 1314,
                     "line_unit": "GHS per adult equivalent per year, Accra January 2017 prices"}
            for ln in page.splitlines():
                for r in _REGIONS + ["National"]:
                    m = re.match(rf"^{re.escape(r)}\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)\s*$", ln.strip())
                    if m:
                        cell = {} if r == "National" else {"geography": r}
                        rows.append(_row(cell, glss7, "headcount_ci_low", float(m.group(2))))
                        rows.append(_row(cell, glss7, "headcount_ci_high", float(m.group(3))))
    if n < 200:
        raise ValueError(f"{path}: {n} districts read from the annex, expected >= 200")
    return pd.DataFrame(rows)


LAYOUT = LAYOUT_GLSS6
parse = parse_glss6


# ------------------------------------------------------------ 4. map 2005
# "Ghana Census-Based Poverty Map: District and Sub-District level Results"
# (H. Coulombe for GSS / DfID, May 2005; "Edited by GSS 2015"). Every index is
# printed on 0-1: unit "index", kept as printed.
#   Table 3   P0 P1 P2 by the seven strata, GLSS 4 (actual) and Census 2000
#             (predicted); standard errors (bracketed lines) not read.
#   Annexe 3  P0 P1 P2 for 10 regions and 110 districts x total / urban /
#             rural (population and the standard-error lines not read).
# The GLSS 4 column uses the map's NEW urban/rural split ("slightly different
# from the ones already published by GSS"), so it is filed as its own survey.
_GLSS4_UP = {"line_level": "overall", "line_name": "GLSS 4 upper poverty line (GSS poverty profile 2000)"}
LAYOUT_MAP2005 = {**_BASE, **_GLSS4_UP,
                  "survey": "Ghana Poverty Map 2005 (small-area estimates, Census 2000 + GLSS 4)",
                  "period": "2000", "reference_period": "Census 2000 / GLSS 4 1998/99", "tables": []}
_GLSS4_MAP = {**LAYOUT_MAP2005, "survey": "GLSS 4 1998/99 (poverty-map strata, new urban/rural definition)",
              "period": "1998", "reference_period": "1998/99"}
_STRATA05 = ["Accra", "Urban Coastal", "Urban Forest", "Urban Savannah", "Rural Coastal",
             "Rural Forest", "Rural Savannah"]


def _idx05(cell, layout, metric, value):
    a = {**layout, **cell}
    return C.row(metric=metric, value=value, unit="index", survey=a["survey"],
                 welfare_aggregate=a["welfare_aggregate"], unit_of_analysis=a["unit_of_analysis"],
                 line_type=a["line_type"], line_level=a["line_level"], line_name=a["line_name"],
                 period=a["period"], reference_period=a["reference_period"], frequency=a["frequency"],
                 **{k: a[k] for k in ("topic", "characteristic", "locality", "locality_label", "geography")
                    if k in a})


def parse_map2005(path: str) -> pd.DataFrame:
    pages = _pages(path)
    rows = []
    t3 = next((p for p in pages if "Table 3: Poverty Rates based on GLSS 4 (actual)" in p), None)
    if t3 is None:
        raise ValueError("Table 3 not found")
    body = t3[t3.index("Table 3: Poverty Rates based on GLSS 4 (actual)"):].split("Sources:")[0]
    n = 0
    for ln in body.splitlines():
        m = re.match(r"^(" + "|".join(_STRATA05) + r")\s+((?:\d?\.\d{3}\s+){5}\d?\.\d{3})\s*$", ln.strip())
        if not m:
            continue
        v = [float(x) for x in m.group(2).split()]
        cell = {"topic": "locality", "locality": "other", "locality_label": m.group(1),
                "characteristic": m.group(1)}
        for k, metric in enumerate(("headcount", "gap", "severity")):
            rows.append(_idx05(cell, _GLSS4_MAP, metric, v[2 * k]))
            rows.append(_idx05(cell, LAYOUT_MAP2005, metric, v[2 * k + 1]))
        n += 1
    if n != 7:
        raise ValueError(f"Table 3: expected 7 strata, got {n}")
    seen = set()
    tok = r"(?:\d[\d,]*|n/a)"
    trip = r"((?:\d?\.\d{3}|n/a)\s+(?:\d?\.\d{3}|n/a)\s+(?:\d?\.\d{3}|n/a))"
    pat = re.compile(rf"^(\d{{1,4}})\s+(.+?)\s+{tok}\s+{trip}\s+{tok}\s+{trip}\s+{tok}\s+{trip}\s*$")
    for page in pages:
        if "Annexe 3: Regional and District Level Poverty Estimates" not in page:
            continue
        for ln in page.splitlines():
            m = pat.match(ln.strip())
            if not m:
                continue
            ident, name = m.group(1), m.group(2).strip()
            if len(ident) <= 2:
                if name not in _REGIONS:
                    raise ValueError(f"Annexe 3: unknown region {name!r}")
            if (ident, name) in seen:
                raise ValueError(f"Annexe 3: {name} twice")
            seen.add((ident, name))
            for loc, cells in zip(("all", "urban", "rural"), m.group(3, 4, 5)):
                vals = cells.split()
                if "n/a" in vals:
                    continue
                cell = {"geography": name}
                if loc != "all":
                    cell.update(topic="locality", locality=loc, locality_label=loc.capitalize(),
                                characteristic=loc.capitalize())
                for metric, x in zip(("headcount", "gap", "severity"), vals):
                    rows.append(_idx05(cell, LAYOUT_MAP2005, metric, float(x)))
    regions = sum(len(i) <= 2 for i, _ in seen)
    if regions != 10 or len(seen) - regions != 110:
        raise ValueError(f"Annexe 3: {regions} regions, {len(seen) - regions} districts (expected 10, 110)")
    return pd.DataFrame(rows)
