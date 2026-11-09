"""Uganda -- UNHS back-series, 1992/93-2012/13 (one descriptor per UBOS report).

Every UBOS UNHS report prints the same FGT table shape:

    Location  Pop. share  Mean CPAE  P0 P1 P2  Contribution to: P0 P1 P2

for the nation, rural/urban, 4 regions and region x residence (and, from
2009/10, sub-regions), on the official national line (Appleton 2001,
cost of basic needs, re-valued to each report's price base -- the HEADCOUNTS
are comparable, the mean CPAE columns are not, and are not read).

ROUNDS, each taken from the report that first published it:

  parse_2002 -- UNHS 2002/03 report:
    T6.3.1   UNHS 2002/03, full sample (Pader not surveyed)
    T6.3.2a  UNHS 2002/03 on COMPARABLE COVERAGE (excl. Kitgum, Gulu,
             Bundibugyo, Kasese, Pader), b UNHS 1999/00, c MS-4 1997, d IHS
             1992 -- all on that coverage (the section says so; 1992's 55.7 is
             the 2005/06 report's "IHS 1992/93 excluding ..." figure, while the
             full-coverage IHS is 56.4). Every place in these tables carries the
             suffix " [excl. Kitgum, Gulu, Bundibugyo, Kasese, Pader]": the
             universe differs, and so do population shares and contributions.
    T6.3.6a/b poverty by sector of the household head, 2002/03 and 1999/00
             (comparable coverage).
  parse_2005 -- UNHS 2005/06 report:
    T6.9     UNHS 2005/06; T6.10b IHS 1992/93 FULL coverage (first published
             here); A1(a) UNHS 2005/06 on comparable coverage. T6.15/T6.16
             sector of head 2005/06 and 2002/03 (full coverage); T6.17
             employment status of head 2005/06 and 2002/03.
    Not read: T6.10a and A1(b)-(d) -- republish the 2002/03 report's tables.
  parse_2009 -- UNHS 2009/10 report: T6.8 and T6.9 (10 sub-regions).
    Not read: T6.10/6.11 (republish 2005/06 and 2002/03, identical).
  parse_2012 -- UNHS 2012/13 report: T6.4. Its SUB-REGION block is printed
    with the P1 / P2 / contribution columns misaligned (Mid-West P1 13.9
    against P0 9.8; each row's "P1" equals the next row's P0 contribution),
    so only population share and P0 are read for sub-regions -- those two
    reproduce the national 19.7 (population-weighted 19.74). Not read: T6.6 /
    6.7, which reprint the 2009/10 and 2005/06 tables with decimal points lost
    ("76", "58", "846").

PUBLISHED DIFFERENCES kept, not reconciled: the 2005/06 report prints
Northern rural P2 2005/06 as 9.9 (T6.9) and the 2009/10 report as 10.0
(T6.10) -- the round's own report is the one collected.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T

_LINE = {"line_level": "overall",
         "line_name": "Official national poverty line (UBOS; Appleton 2001 cost of basic needs)"}
_EXCL = " [excl. Kitgum, Gulu, Bundibugyo, Kasese, Pader]"
_REG = {"Central": "Central", "East": "Eastern", "Eastern": "Eastern", "West": "Western",
        "Western": "Western", "North": "Northern", "Northern": "Northern"}
_FGT8 = ("population_share", None, "headcount", "gap", "severity",
         "poor_share", "gap_contribution", "severity_contribution")

LAYOUT = {"survey": "UNHS 2002/03", "welfare_aggregate": "consumption",
          "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
          "line_type": "national", **_LINE, "period": "2002", "reference_period": "2002/03",
          "tables": []}
LAYOUT_2005 = {**LAYOUT, "survey": "UNHS 2005/06", "period": "2005", "reference_period": "2005/06"}
LAYOUT_2009 = {**LAYOUT, "survey": "UNHS 2009/10", "period": "2009", "reference_period": "2009/10"}
LAYOUT_2012 = {**LAYOUT, "survey": "UNHS 2012/13", "period": "2012", "reference_period": "2012/13"}

_SUB = {"Kampala", "Central 1", "Central 2", "Central I", "Central II", "East central",
        "East Central", "Eastern", "Mid-northern", "Mid-North", "North-east", "North-East",
        "West Nile", "West-Nile", "Mid-western", "Mid-West", "South-western", "South-Western"}


def _base(survey, period, ref, **kw) -> dict:
    d = dict(survey=survey, welfare_aggregate="consumption", unit_of_analysis="person",
             line_type="national", period=period, reference_period=ref, frequency="ad_hoc",
             line_value="", line_unit="", **_LINE)
    d.update(kw)
    return d


def _place(label: str, restricted: bool, subregions: bool) -> dict | None:
    s = re.sub(r"\s+", " ", label).strip().rstrip("*")
    suf = _EXCL if restricted else ""
    nat = "Uganda" + _EXCL if restricted else "Total country"
    if s in ("National", "Uganda"):
        return {"geography": nat}
    if s in ("Rural", "Urban"):
        return {"geography": nat, "topic": "locality", "locality": s.lower(), "locality_label": s}
    m = re.fullmatch(r"(Central|Eastern|Northern|Western|East|North|West) (rural|urban|Rural|Urban)", s)
    if m:
        return {"geography": _REG[m.group(1)] + suf, "topic": "locality",
                "locality": m.group(2).lower(), "locality_label": m.group(2).capitalize()}
    if subregions and s in _SUB:
        # "Eastern" in a sub-region block is the Eastern SUB-REGION (Mbale,
        # Tororo ...), not the Eastern region.
        # Sub-regions keep their printed names (Kampala and West Nile are the
        # places the 2016/17+ reports also use); only the one that shares a
        # REGION's name is marked.
        return {"geography": "Eastern (sub-region)" if s == "Eastern" else s}
    if s in _REG:
        return {"geography": _REG[s] + suf}
    return None


_NUM = r"-?[\d,]+(?:\.\d+)?"
_ROW = re.compile(rf"^([A-Za-z][A-Za-z .&/'*-]*?)\s+((?:{_NUM}\s+)*{_NUM})\s*$")
_NUMS_ONLY = re.compile(rf"^((?:{_NUM}\s+)*{_NUM})\s*$")


def _nums(s: str) -> list[float]:
    return [float(x.replace(",", "")) for x in s.split()]


def _lines(pages, caption: str, end: str, follow: int = 1) -> list[str]:
    """Lines from `caption` (its own page, not the contents list) to `end`."""
    for i, p in enumerate(pages):
        if re.search(caption, p, re.I) and len(re.findall(r"\.{8,}", p)) < 5:
            text = "\n".join(pages[i:i + 1 + follow])
            m = re.search(caption, text, re.I)
            body = text[m.end():]
            e = re.search(end, body, re.I | re.M) if end else None
            return (body[:e.start()] if e else body).splitlines()
    raise ValueError(f"caption not found: {caption!r}")


def _table(pages, caption, end, survey, period, ref, *, restricted=False, subregions=False,
           expect=None, follow=1, label_after=False, sub_cols=None) -> list[dict]:
    lines = [l.strip() for l in _lines(pages, caption, end, follow) if l.strip()]
    # (label, numbers, in_sub_block). `subregions="all"`: every row is a
    # sub-region; True: rows after a "Sub-regions" heading are.
    pairs, in_sub = [], subregions == "all"
    for k, ln in enumerate(lines):
        if re.match(r"^Sub.{0,2}regions?$", ln, re.I):
            in_sub = True
            continue
        if label_after:
            nxt = lines[k + 1] if k + 1 < len(lines) else ""
            if _NUMS_ONLY.match(ln) and nxt and not re.search(r"\d", nxt):
                pairs.append((nxt, _nums(ln), in_sub))
        else:
            m = _ROW.match(ln)
            if m:
                pairs.append((m.group(1), _nums(m.group(2)), in_sub))
    out, n = [], 0
    for lab, nums, sub in pairs:
        # "Central 1 11.2 101,418 ..." -- the digit belongs to the label.
        if len(nums) == 9 and lab.strip() == "Central" and nums[0] in (1, 2):
            lab, nums = f"Central {int(nums[0])}", nums[1:]
        if len(nums) != 8:
            continue
        pl = _place(lab, restricted, sub)
        if pl is None:
            continue
        cols = sub_cols if (sub and sub_cols) else _FGT8
        for metric, v in zip(cols, nums):
            if metric:
                out.append(C.row(metric=metric, value=v, **_base(survey, period, ref), **pl))
        n += 1
    if expect is not None and n != expect:
        raise ValueError(f"{caption}: expected {expect} rows, got {n}")
    return out


def _sector(pages, caption, end, survey, period, ref, block, *, restricted=False,
            expect=None, follow=1, label_parts=None) -> list[dict]:
    lines = [l.strip() for l in _lines(pages, caption, end, follow) if l.strip()]
    nat = "Uganda" + _EXCL if restricted else "Total country"
    out, n = [], 0
    for i, ln in enumerate(lines):
        m = _ROW.match(ln)
        if not m:
            continue
        lab, nums = m.group(1).strip(), _nums(m.group(2))
        if len(nums) != 8 or lab in ("National",):
            continue
        # a label wrapped onto the next line ("Crop" / "Agriculture")
        if label_parts and lab in label_parts and i + 1 < len(lines):
            lab = f"{lab} {lines[i + 1]}"
        for metric, v in zip(_FGT8, nums):
            if metric:
                out.append(C.row(metric=metric, value=v, topic="employment_of_head",
                                 characteristic=f"{block}: {lab}", geography=nat,
                                 **_base(survey, period, ref)))
        n += 1
    if expect is not None and n != expect:
        raise ValueError(f"{caption}: expected {expect} rows, got {n}")
    return out


def _pages(path):
    return T._pages(path, halves=False)["full"]


def parse(path: str) -> pd.DataFrame:
    """UNHS 2002/03 report."""
    P = _pages(path)
    out = []
    out += _table(P, r"Table 6\. ?3\.1: Poverty statistics for UNHS2002/03", r"^To evaluate poverty",
                  "UNHS 2002/03", "2002", "2002/03", expect=15)
    for cap, end, survey, period, ref in (
            (r"Table 6\.3\.2: \(a\) Poverty Estimates in 2002/03", r"^Table 6\.3\.2: \(b\)",
             "UNHS 2002/03", "2002", "2002/03"),
            (r"Table 6\.3\.2: \(b\) Poverty in the 1999/00", r"^Table 6\.3\.2: \(c\)|^Uganda National",
             "UNHS 1999/00", "1999", "1999/00"),
            (r"Table 6\.3\.2: \(c\) Poverty Rates in MS-4, 1997", r"^Table 6\.3\.2: \(d\)",
             "MS-4 1997 (Monitoring Survey)", "1997", "1997"),
            (r"Table 6\.3\.2: \(d\) Poverty in the IHS, 1992", r"^Table 6\. ?3\.3",
             "IHS 1992/93", "1992", "1992/93")):
        # (b) runs over the page break: the North urban row ends on the next page.
        out += _table(P, cap, end, survey, period, ref, restricted=True, expect=15,
                      follow=1)
    out += _sector(P, r"Table 6\.3\.6: \(a\) Poverty by Sector of Household Head, 2002/03",
                   r"^growing only food|^6\.4", "UNHS 2002/03", "2002", "2002/03",
                   "Sector of household head", restricted=True, expect=12)
    out += _sector(P, r"Table 6\.3\.6: \(b\) Poverty by Sector of Household Head, 1999/00",
                   r"^6\.4 Summary", "UNHS 1999/00", "1999", "1999/00",
                   "Sector of household head", restricted=True, expect=12,
                   label_parts={"Crop"})
    return pd.DataFrame(out)


def parse_2005(path: str) -> pd.DataFrame:
    """UNHS 2005/06 report."""
    P = _pages(path)
    out = []
    out += _table(P, r"Table 6\.9: Poverty Statistics in the UNHS 2005/06", r"^To evaluate poverty",
                  "UNHS 2005/06", "2005", "2005/06", expect=15)
    out += _table(P, r"Table 6\.10: \(b\) Poverty in the IHS, 1992/93", r"^Table 6\.11",
                  "IHS 1992/93", "1992", "1992/93", expect=15, follow=0)
    out += _table(P, r"Table A ?1: \(a\) Poverty in the UNHS 2005/06", r"^Table A1: \(b\)",
                  "UNHS 2005/06", "2005", "2005/06", restricted=True, expect=15, follow=0)
    out += _sector(P, r"Table 6\.15: Poverty by Sector of Household Head, 2005/06",
                   r"^Table 6\.16", "UNHS 2005/06", "2005", "2005/06",
                   "Sector of household head", expect=10, follow=0)
    out += _sector(P, r"Table 6\.16: Poverty by Sector of Household Head, 2002/03",
                   r"^An alternative disaggregation", "UNHS 2002/03", "2002", "2002/03",
                   "Sector of household head", expect=10, follow=1)
    t617 = _lines(P, r"Table 6\.17: Poverty by Employment Status of Household Head",
                  r"^Notes: Employment status", 0)
    txt = "\n".join(t617)
    for yr, ref, survey, chunk in (("2005", "2005/06", "UNHS 2005/06",
                                    txt.split("2005/06", 1)[1].split("2002/03", 1)[0]),
                                   ("2002", "2002/03", "UNHS 2002/03", txt.split("2002/03", 1)[1])):
        rows = _sector([f"Table X\n{chunk}"], r"Table X", None, survey, yr, ref,
                       "Employment status of household head", expect=5, follow=0)
        out += rows
    return pd.DataFrame(out)


def parse_2009(path: str) -> pd.DataFrame:
    """UNHS 2009/10 report."""
    P = _pages(path)
    out = []
    out += _table(P, r"Table 6\.8: Poverty Estimate in the UNHS IV 2009/10", r"^\d{2}\s*$",
                  "UNHS 2009/10", "2009", "2009/10", expect=15, follow=0)
    out += _table(P, r"Table 6\.9: Poverty Estimates in the UNHS IV \(2009/10\) by Sub-region",
                  r"^Notes:", "UNHS 2009/10", "2009", "2009/10", subregions="all", expect=10,
                  follow=0)
    return pd.DataFrame(out)


def parse_2012(path: str) -> pd.DataFrame:
    """UNHS 2012/13 report."""
    P = _pages(path)
    sub_cols = ("population_share", None, "headcount", None, None, None, None, None)
    out = _table(P, r"Table 6\.4: Poverty Estimates in the UNHS V, 2012/13", r"^\*Kampala has",
                 "UNHS 2012/13", "2012", "2012/13", subregions=True, label_after=True,
                 expect=17, follow=0, sub_cols=sub_cols)
    return pd.DataFrame(out)
