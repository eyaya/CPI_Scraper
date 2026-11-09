"""Malawi -- back rounds of monetary poverty (NSO Malawi), one parser per report.

The IHS6 report (`malawi_poverty`) carries IHS6 2024/25 and IHS5 2019/20.
This module adds the earlier rounds from NSO's own reports, all Wayback
`id_` copies of nsomalawi.mw (NSO's rebuilt CMS no longer lists them):

`parse_ihs4` -- "Malawi Poverty Report 2018" (IHS4 2016/17, published 2019):
  IHS3 2010/11 AND IHS4 2016/17 on the IHS4 method, Tables 3-2..3-8:
  P0 (with 95% CI), ultra-poverty P0 (with CI), P1, P2, ultra P1, ultra P2 by
  national, urban/rural, rural region and 32 districts; Table 3-4 (IHS4) adds
  region P0 / ultra P0 and population / poor / ultra-poor shares. Lines
  (Table 3-1, MWK per person per year): total 37,002 (IHS3) / 137,428 (IHS4),
  food = ultra-poverty 22,956 / 85,260. Gap/severity CIs are not collected
  (the schema bounds only the headcount); a CI pair with a NEGATIVE lower
  bound (symmetric interval on a small rate) is skipped. Likoma has no IHS3
  estimate ("_").
  Tables 3-6 and 3-8 print each LABEL ON THE LINE AFTER its numbers; the
  reader pairs them.

`parse_ihs2` -- "Integrated Household Survey 2004-2005" report, ch. 12:
  Tables 12.2-12.4 (IHS2 2004/05): P0 and ultra P0 with 95% CI by national,
  urban/rural, rural region and the 31 survey strata, plus population and
  poor shares by region; the "$1/day (PPP adjusted)" national rate (no PPP
  base year printed). Lines MK 16,165 / 10,029 per person per year.

District names are filed in the IHS6 report's spelling so a district is one
geography across rounds: Nkhatabay/NkhataBay -> Nkhata Bay; Lilongwe Rural ->
Lilongwe; Zomba Rural -> Zomba Non-City; Blantyre rural -> Blantyre; the
IHS2 report's truncated "Nkhotako"/"Chiradzu" -> Nkhotakota/Chiradzulu, and
its urban strata "Mzuzu city"/"Lilongwe Urban"/"Zomba Urban"/"Blantyre Urban"
-> the "... City" names the later reports print for the same strata. Rural
regions ("Northern Rural", "North Rural", "Rural North") -> geography
"<X> Region", locality rural, as in `malawi_poverty`.

Each round is its own survey label; IHS3 here is the IHS4-report
re-estimate ("IHS3 2010/11 (IHS4 report)"), not the IHS3 report's own.

CROSS-CHECK (verbatim): IHS4 P0 51.5, ultra 20.1, P1 16.8, P2 7.4; IHS3
50.7 / 24.5 / 18.9 / 9.3; Phalombe IHS4 83.2; Blantyre City 8.0; Likoma
31.4; region shares (Table 3-4) sum to 100.1 / 100.0. IHS2 52.4 / 22.4;
Nsanje 76.0; $1/day 28.0; rural-region + urban poor shares sum to 100.0.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_GEO = {"Nkhatabay": "Nkhata Bay", "NkhataBay": "Nkhata Bay", "Lilongwe Rural": "Lilongwe",
        "Lilongwe rural": "Lilongwe", "Zomba Rural": "Zomba Non-City",
        "Zomba rural": "Zomba Non-City", "Blantyre rural": "Blantyre",
        "Nkhotako": "Nkhotakota", "Chiradzu": "Chiradzulu", "Mzuzu city": "Mzuzu City",
        "Lilongwe Urban": "Lilongwe City", "Zomba Urban": "Zomba City",
        "Blantyre Urban": "Blantyre City"}
_DISTRICTS = {"Chitipa", "Karonga", "Nkhata Bay", "Rumphi", "Mzimba", "Likoma", "Mzuzu City",
              "Kasungu", "Nkhotakota", "Ntchisi", "Dowa", "Salima", "Lilongwe", "Mchinji",
              "Dedza", "Ntcheu", "Lilongwe City", "Mangochi", "Machinga", "Zomba Non-City",
              "Chiradzulu", "Blantyre", "Mwanza", "Thyolo", "Mulanje", "Phalombe", "Chikwawa",
              "Nsanje", "Balaka", "Neno", "Zomba City", "Blantyre City"}
_RREG = {"north": "Northern Region", "northern": "Northern Region", "centre": "Central Region",
         "central": "Central Region", "south": "Southern Region", "southern": "Southern Region"}
UNIT = "MWK per person per year (nominal, survey prices)"


def _cut(label: str):
    lab = label.strip()
    if lab == "Malawi":
        return {}
    if lab in ("Urban", "Rural"):
        return {"topic": "locality", "locality": lab.lower(), "locality_label": lab}
    m = re.fullmatch(r"(?:Rural )?(North|Northern|Centre|Central|South|Southern)(?: rural)?(?: Rural)?(?: region)?",
                     lab, re.I) or re.fullmatch(r"Rural (northern|central|southern) region", lab, re.I)
    if m and "rural" in lab.lower():
        return {"topic": "locality", "locality": "rural", "locality_label": "Rural",
                "geography": _RREG[m.group(1).lower()]}
    m = re.fullmatch(r"(Northern|Central|Southern) Region", lab)
    if m:
        return {"geography": lab}
    g = _GEO.get(lab, lab)
    return {"geography": g} if g in _DISTRICTS else None


def _num(tok):
    return None if tok in ("_", "-", "–") else float(tok.rstrip("%"))


def _segment(pages, caption, stop=r"^Source:"):
    """Lines from the LAST page carrying `caption` (the first is the contents)."""
    hits = [i for i, t in enumerate(pages) if caption.lower() in t.lower()]
    if not hits:
        raise ValueError(f"caption not found: {caption!r}")
    lines = pages[hits[-1]].splitlines()
    i = next(k for k, l in enumerate(lines) if caption.lower() in l.lower())
    out = []
    for l in lines[i + 1:]:
        if re.match(stop, l.strip()):
            break
        out.append(l.strip())
    return out


_TOK = r"(?:-?\d+(?:\.\d+)?%?|[_\-–])"


def _pairs(lines, n):
    """(label, [n values]) whether a label precedes its numbers or follows them."""
    out, pending = [], None
    for l in lines:
        toks = l.split()
        k = 0
        while k < len(toks) and not re.fullmatch(_TOK, toks[-1 - k]):
            break
        nums = []
        for t in reversed(toks):
            if re.fullmatch(_TOK, t):
                nums.insert(0, t)
            else:
                break
        label = " ".join(toks[:len(toks) - len(nums)])
        if nums and len(nums) == n:
            if label:
                out.append((label, [_num(x) for x in nums]))
                pending = None
            else:
                pending = [_num(x) for x in nums]
        elif not nums and pending is not None and label:
            out.append((label, pending))
            pending = None
        else:
            pending = None
    return out


def _base(survey, period, ref, level, value, **kw):
    name = "Food (ultra-)poverty line" if level == "extreme" else "Total poverty line"
    return dict(survey=survey, welfare_aggregate="consumption", line_type="national",
                line_level=level, line_name=name, line_value=value, line_unit=UNIT,
                period=period, reference_period=ref, frequency="ad_hoc", **kw)


def _pages(path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return [(p.extract_text(x_tolerance=1) or "") for p in pdf.pages]


_IHS3 = ("IHS3 2010/11 (IHS4 report)", "2010", "2010/11")
_IHS4 = ("IHS4 2016/17", "2016", "2016/17")
_LV = {("2010", "overall"): 37002, ("2010", "extreme"): 22956,
       ("2016", "overall"): 137428, ("2016", "extreme"): 85260}

LAYOUT_IHS4 = {"survey": _IHS4[0], "welfare_aggregate": "consumption",
               "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
               "line_type": "national", "line_level": "overall",
               "line_name": "Total poverty line", "line_unit": UNIT,
               "period": "2016", "reference_period": "2016/17", "tables": []}


def parse_ihs4(path: str) -> pd.DataFrame:
    pages = _pages(path)
    rows = []
    specs = [("Table 3-2: Poverty incidence by urban", "headcount", "overall", True),
             ("Table 3-3: Ultra-Poverty incidence by urban", "headcount", "extreme", True),
             ("Table 3-5: Poverty gap by rural", "gap", "overall", False),
             ("Table 3-6: Poverty gap squared by rural", "severity", "overall", False),
             ("Table 3-7: Ultra-poverty gap by urban", "gap", "extreme", False),
             ("Table 3-8: Ultra-poverty gap squared by rural", "severity", "extreme", False)]
    for cap, metric, level, ci in specs:
        seg = _segment(pages, cap)
        got = 0
        for label, vals in _pairs(seg, 8) + [(l, [None] * 4 + v) for l, v in _pairs(seg, 4)]:
            cut = _cut(label)
            if cut is None:
                continue
            for (sv, p, r), block in ((_IHS3, vals[:4]), (_IHS4, vals[4:])):
                est, _se, lo, hi = block
                if est is None:
                    continue
                b = _base(sv, p, r, level, _LV[(p, level)])
                rows.append(C.row(metric=metric, value=est, **b, **cut))
                # A symmetric (normal) interval can print a NEGATIVE lower bound
                # for a small rate (Blantyre City ultra-poverty -0.9): that pair
                # is not a bound on a share, so it is skipped (as malawi_poverty
                # skips IHS5's).
                if ci and lo is not None and lo >= 0:
                    rows.append(C.row(metric="headcount_ci_low", value=lo, **b, **cut))
                    rows.append(C.row(metric="headcount_ci_high", value=hi, **b, **cut))
            got += 1
        if got < 38:
            raise ValueError(f"Malawi IHS4 report {cap!r}: {got} rows, expected 38")
    # Table 3-4 (IHS4): region P0 / ultra P0, population / poor / ultra-poor shares
    seg = _segment(pages, "Table 3-4: Poverty Incidence and share of population")
    got = 0
    for label, (p0, u0, pop, poor, upoor) in _pairs(seg, 5):
        cut = _cut(label)
        if cut is None or label == "Malawi":
            continue
        b, bx = _base(*_IHS4, "overall", 137428), _base(*_IHS4, "extreme", 85260)
        if re.fullmatch(r"(Northern|Central|Southern) Region", label):
            rows.append(C.row(metric="headcount", value=p0, **b, **cut))
            rows.append(C.row(metric="headcount", value=u0, **bx, **cut))
        rows.append(C.row(metric="population_share", value=pop, **b, **cut))
        rows.append(C.row(metric="poor_share", value=poor, **b, **cut))
        rows.append(C.row(metric="poor_share", value=upoor, **bx, **cut))
        got += 1
    if got < 37:
        raise ValueError(f"Malawi IHS4 report Table 3-4: {got} rows, expected 37")
    return pd.DataFrame.from_records(rows)


_IHS2 = ("IHS2 2004/05", "2004", "2004/05")
LAYOUT_IHS2 = {**LAYOUT_IHS4, "survey": _IHS2[0], "period": "2004", "reference_period": "2004/05"}


def parse_ihs2(path: str) -> pd.DataFrame:
    pages = _pages(path)
    rows = []
    for cap, level, value in (("Table 12.3 Poverty headcount and percentage distribution of Malawi’s poor", "overall", 16165),
                              ("Table 12.4 Poverty headcount and percentage distribution of Malawi’s Ultra", "extreme", 10029)):
        hits = [i for i, t in enumerate(pages) if cap.lower() in t.lower()]
        i = hits[-1]
        text = pages[i] + "\n" + pages[i + 1]   # the strata run onto the next page
        text = text.split("Percent of population living below $1/day")[0]
        seen = set()
        b = _base(*_IHS2, level, value)
        for label, (p0, lo, hi) in _pairs(text.splitlines(), 3):
            cut = _cut(label)
            if cut is None or label in seen:
                continue
            seen.add(label)
            rows.append(C.row(metric="headcount", value=p0, **b, **cut))
            rows.append(C.row(metric="headcount_ci_low", value=lo, **b, **cut))
            rows.append(C.row(metric="headcount_ci_high", value=hi, **b, **cut))
        if len(seen) < 36:
            raise ValueError(f"Malawi IHS2 {cap[:12]}: {len(seen)} rows, expected 36")
    # $1/day (PPP adjusted), national
    dol = [t for t in pages if "living below $1/day" in t][-1]
    m = re.search(r"Malawi (\d+\.\d)% (\d+\.\d)% (\d+\.\d)%", dol.split("living below $1/day")[1])
    b = {**_base(*_IHS2, "other", ""), "line_type": "international",
         "line_name": "US$1 a day (PPP adjusted; base year not printed)", "line_value": "",
         "line_unit": ""}
    for metric, v in zip(("headcount", "headcount_ci_low", "headcount_ci_high"), m.groups()):
        rows.append(C.row(metric=metric, value=float(v), **b))
    # Table 12.2: shares of the poor and of the population by rural region / urban
    seg = _segment(pages, "Table 12.2 Poverty headcount and percentage distribution")
    for label, (_p0, _u0, poor, pop) in _pairs(seg, 4):
        cut = _cut(label)
        if cut is None or label == "Malawi":
            continue
        b = _base(*_IHS2, "overall", 16165)
        rows.append(C.row(metric="poor_share", value=poor, **b, **cut))
        rows.append(C.row(metric="population_share", value=pop, **b, **cut))
    return pd.DataFrame.from_records(rows)
