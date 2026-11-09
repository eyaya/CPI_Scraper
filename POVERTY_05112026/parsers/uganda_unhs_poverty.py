"""Uganda -- UNHS rounds beyond the 2019/20 report (`uganda_poverty`).

Each UBOS report is its own descriptor and its own parse function here:

* `parse` -- UNHS 2023/24 report (2025), chapter 6:
    Table 6.8  official line (the "one US dollar per person per day" line; its
               2019/20 column in Table 6.15 reproduces the 20.3 of the 2019/20
               report, so it is the same official line and keeps its name):
               national, rural/urban, 4 regions, region x residence, 15
               sub-regions -- population share, P0 P1 P2, contributions.
    Box 1      food poverty 2023/24 (2019/20 is already collected).
    Table 6.9a the UPPER line of US$1.77 per person per day, P0 P1 P2 for
               2016/17, 2019/20 and 2023/24 by the same geography.
    Table 6.12 2023/24 columns: employment status and industrial sector of the
               household head (its 2019/20 columns re-tabulate categories the
               2019/20 report printed differently, so they are not read).
    Table 6.14 monetary CHILD poverty 2016/17-2023/24 by sex, residence and
               sub-region (the age band is not printed: age_group "Children").
  Not read: mean consumption, poor in millions (6.8, 6.9a, 6.16), Table 6.11
  (household enterprise -- no topic), 6.13 (bottom 40%, not a poverty
  measure), 6.15 (pre/during-COVID sub-samples), wage/enterprise combinations.

CROSS-CHECK (verbatim, 2023/24): P0 16.1 / P1 4.2 / P2 1.6; rural 19.4, urban
10.3; Karamoja 74.2 / 31.5 / 16.7; Kampala 1.1; food poverty 6.8; US$1.77
line 26.4 / 7.4 / 3 (2016/17 31.6, 2019/20 30.1); child poverty 18.5.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T

_OFFICIAL = {"line_level": "overall",
             "line_name": "Official national poverty line (UBOS, regional, 2009/10 prices)"}
_FOOD = {"line_level": "extreme", "line_name": "Food poverty line (UBOS)"}
_UPPER = {"line_level": "other", "line_name": "Upper poverty line of US$1.77 per person per day (UBOS)"}
_ROUND = {"2016": ("UNHS 2016/17", "2016/17"), "2019": ("UNHS 2019/20", "2019/20"),
          "2023": ("UNHS 2023/24", "2023/24")}
_REGIONS = {"Central", "Eastern", "Northern", "Western"}
_SUBREGIONS = {"Kampala", "Buganda South", "Buganda North", "Busoga", "Bukedi", "Elgon", "Teso",
               "Karamoja", "Lango", "Acholi", "West Nile", "Bunyoro", "Tooro", "Toro", "Ankole",
               "Kigezi"}
_REG_ALIAS = {"East": "Eastern", "North": "Northern", "West": "Western"}

LAYOUT = {
    "survey": "UNHS 2023/24", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ".", "line_type": "national", **_OFFICIAL,
    "period": "2023", "reference_period": "2023/24", "tables": [],
}


def _place(label: str) -> dict | None:
    """Map a printed row label to geography / locality, or None if it is not a place."""
    s = re.sub(r"\s+", " ", label).strip()
    if s == "Uganda":
        return {}
    if s in ("Rural", "Urban"):
        return {"topic": "locality", "locality": s.lower(), "locality_label": s}
    if s in _REGIONS:
        return {"geography": s}
    m = re.fullmatch(r"(Central|Eastern|Northern|Western|East|North|West) (rural|urban)", s)
    if m:
        reg = _REG_ALIAS.get(m.group(1), m.group(1))
        return {"geography": reg, "topic": "locality", "locality": m.group(2),
                "locality_label": m.group(2).capitalize()}
    if s in _SUBREGIONS:
        return {"geography": "Tooro" if s == "Toro" else s}
    return None


def _base(year="2023", line=None, **kw) -> dict:
    survey, ref = _ROUND[year]
    d = dict(survey=survey, welfare_aggregate="consumption", unit_of_analysis="person",
             line_type="national", period=year, reference_period=ref, frequency="ad_hoc",
             line_value="", line_unit="", **(line or _OFFICIAL))
    d.update(kw)
    return d


_ROW = re.compile(r"^([A-Za-z][A-Za-z .&/'-]*?)\s+((?:-?[\d,]+(?:\.\d+)?\s+)*-?[\d,]+(?:\.\d+)?)\s*$")


def _rows(lines):
    for ln in lines:
        m = _ROW.match(ln.strip())
        if m:
            yield m.group(1), [float(x.replace(",", "")) for x in m.group(2).split()]


def _page_after(pages, caption: str, n_follow: int = 1) -> list[str]:
    """The lines of the page whose text carries `caption` as a heading (not the
    contents page), plus the next `n_follow` pages (tables run over a break)."""
    for i, p in enumerate(pages):
        # A contents page lists every caption with dot leaders: skip it.
        if caption.lower() in p.lower() and len(re.findall(r"\.{8,}", p)) < 5:
            out = []
            for q in pages[i:i + 1 + n_follow]:
                out += q.splitlines()
            return out
    raise ValueError(f"caption not found: {caption!r}")


def _between(lines, start: str, end: str | None):
    on = False
    for ln in lines:
        if not on and re.search(start, ln, re.I):
            on = True
            continue
        if on and end and re.search(end, ln, re.I):
            break
        if on:
            yield ln


def parse(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)["full"]
    out: list[dict] = []

    # Table 6.8 -- pop share, mean cpae, P0 P1 P2, contributions P0 P1 P2, poor (mill.)
    t68 = list(_between(_page_after(pages, "Table 6.8: Income poverty statistics"),
                        r"^Pop\. Share", r"^Notes:"))
    n68 = 0
    for lab, nums in _rows(t68):
        pl = _place(lab)
        if pl is None or len(nums) != 9:
            continue
        for metric, v in zip(("population_share", None, "headcount", "gap", "severity",
                              "poor_share", "gap_contribution", "severity_contribution", None), nums):
            if metric:
                out.append(C.row(metric=metric, value=v, **_base(), **pl))
        n68 += 1
    if n68 != 30:
        raise ValueError(f"Table 6.8: expected 30 rows (Uganda, 2, 4, 8, 15), got {n68}")

    # Box 1 -- food poverty, 2019/20 and 2023/24 (share, millions); 2023/24 share only.
    box = list(_between(_page_after(pages, "Box 1: Food poverty estimates", 0),
                        r"^Share, %", r"^Source:"))
    nb = 0
    for lab, nums in _rows(box):
        pl = _place(lab)
        if pl is None or len(nums) != 4:
            continue
        out.append(C.row(metric="headcount", value=nums[2], **_base(line=_FOOD), **pl))
        nb += 1
    if nb != 7:
        raise ValueError(f"Box 1: expected 7 rows, got {nb}")

    # Table 6.9a -- US$1.77 line: 2016/17, 2019/20, 2023/24 x (P0 P1 P2), poor persons.
    t69 = list(_between(_page_after(pages, "Table 6.9a: Trends in poverty estimates", 0),
                        r"^P0 P1 P2", r"^Progress in income poverty"))
    n69 = 0
    for lab, nums in _rows(t69):
        pl = _place(lab)
        if pl is None or len(nums) != 10:
            continue
        for k, year in enumerate(("2016", "2019", "2023")):
            for metric, v in zip(("headcount", "gap", "severity"), nums[3 * k:3 * k + 3]):
                out.append(C.row(metric=metric, value=v, **_base(year, line=_UPPER), **pl))
        n69 += 1
    if n69 != 30:
        raise ValueError(f"Table 6.9a: expected 30 rows, got {n69}")

    # Table 6.12 -- 2023/24 columns (the last 8 numbers of 16).
    t612 = _page_after(pages, "Table 6.12: Poverty profile by selected socio-economic", 0)
    n612 = 0
    for block, start, end in (("Employment status", r"^Employment status$", r"^Industrial sector$"),
                              ("Industrial sector", r"^Industrial sector$", r"^Wage/enterprise")):
        for lab, nums in _rows(_between(t612, start, end)):
            if len(nums) != 16:
                continue
            for metric, v in zip(("population_share", None, "headcount", "gap", "severity",
                                  "poor_share", "gap_contribution", "severity_contribution"),
                                 nums[8:]):
                if metric:
                    out.append(C.row(metric=metric, value=v, topic="employment_of_head",
                                     characteristic=f"{block}: {lab.strip()}", **_base()))
            n612 += 1
    if n612 != 12:
        raise ValueError(f"Table 6.12: expected 12 category rows, got {n612}")

    # Table 6.14 -- monetary child poverty, three rounds.
    t614 = list(_between(_page_after(pages, "Table 6.14: Monetary Child Poverty in Uganda", 0),
                         r"^UNHS 2016/2017", r"^\d+$"))
    n614 = 0
    for lab, nums in _rows(t614):
        s = lab.strip()
        if len(nums) != 3:
            continue
        if s in ("Female", "Male"):
            pl = {"topic": "sex", "characteristic": s, "sex": s.lower()}
        else:
            pl = _place(s)
            if pl is None:
                continue
        for year, v in zip(("2016", "2019", "2023"), nums):
            out.append(C.row(metric="headcount", value=v, age_group="Children", **_base(year), **pl))
        n614 += 1
    if n614 != 20:
        raise ValueError(f"Table 6.14: expected 20 rows, got {n614}")
    return pd.DataFrame(out)
