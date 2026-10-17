"""Namibia -- Bank of Namibia, "Total Government Debt" workbook (Government
finance statistics page), sheet "Debt and gurantees " (sic).

PUBLISHER: Bank of Namibia; the sheet's own source line is "MoF and BoN".

TWO TABLES, TWO PERIMETERS -- `coverage` is set per row:
  * Table 1 "Central Government debt (N$ million)" -> coverage
    "Central government debt": foreign debt (bilateral, multilateral, Eurobond,
    JSE-listed bonds, external debt excluding Rand), domestic debt (Treasury
    bills, internal registered stock, RFP), gross central government debt,
    government deposits with depository corporations, net central government
    debt;
  * Table 2 "Central Government loan guarantees (N$ million)" -> coverage
    "Central government loan guarantees" -- PARTLY: see below.

MEASURES, all as printed: levels -> `stock` (unit "N$ million"); each
"As % of total" row -> `share` of the level row immediately above it;
the "Proportion of total debt" block -> `share`; the "As % of GDP" block ->
`share_of_gdp`. The GDP row and the debt-SERVICE rows (flows, not stocks) are
not collected.

TABLE 2'S LABELS ARE SHIFTED AGAINST ITS NUMBERS -- a published defect, proved
by the table's own arithmetic (2008/09 Q1): the row labelled "Foreign
Guarantees" holds 36.53, which is domestic's SHARE of the total (1 230.79 /
3 369.53); "As % of GDP" under it holds 2 138.74, a LEVEL; "Total Guarantees"
holds 3.00, a ratio; "Foreign guarantees as % of GDP" holds 3 369.53 =
1 230.79 + 2 138.74, the total LEVEL. Only three rows carry their own label:
"Domestic Guarantees" (level), the "As % of GDP" directly under it (1 230.79 /
71 234.5 GDP = 1.728) and "Total guarantees as % of GDP" (1.728 + 3.002 =
4.730). Those three are collected; the rest are refused rather than relabelled
by inference, and every run re-proves the three by the arithmetic above, so a
corrected reissue raises and is looked at. FROM FY 2024/25 THE ROWS SHIFT
AGAIN, differently, and are not decoded: Table 2 is collected through FY
2023/24 Q4 (2024-Q1) only.

FISCAL QUARTERS, RELABELLED TO CALENDAR QUARTERS. Columns are headed by
Namibia's fiscal year (April-March) and its quarters: "2008/09 Q1" is
April-June 2008. Each is dated to the calendar quarter of the same three
months -- FY Q1 -> Q2 of the first year, Q2 -> Q3, Q3 -> Q4, Q4 -> Q1 of the
second year -- a faithful relabel, not an aggregation. (The newest column,
"2026/27 Q1", can only be fiscal: a calendar 2027-Q1 has not happened.)

Values carry float residue from Excel formulas (3264.363866032098); kept as
stored. PINNED: FY 2016/17 Q2 prints domestic guarantees at 0.659% of GDP,
where 1 043.6 / 154 091 = 0.677; kept as printed (the published total, 4.03,
is built from it). Every Table 1 quarter is checked: foreign + domestic = gross (to
N$1 million).

CROSS-CHECK: gross central government debt 2008/09 Q1 = 12 436.35 (N$ m);
foreign 3 264.36, domestic 9 171.99; total debt 17.46% of GDP; 2026/27 Q1
gross debt 181 894.23, 65.10% of GDP.
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd

_UNIT = "N$ million"
_SHEET = "Debt and gurantees "
_FYQ = {1: (0, 2), 2: (0, 3), 3: (0, 4), 4: (1, 1)}   # FY quarter -> (year offset, calendar Q)
# Quarters whose printed domestic-guarantee % of GDP is NOT domestic / GDP.
# Kept as printed (the published total uses the printed value); listed so a
# correction is noticed: the check below raises if one of these now agrees.
_KNOWN_T2_RATIO_GAP = {"2016-Q3": 0.659}    # FY 2016/17 Q2: 1 043.6 / 154 091 = 0.677
# From FY 2024/25 the guarantee rows shift AGAIN, in a different pattern (the
# row under "Domestic Guarantees" holds ~26 where domestic / GDP is ~1.0, and
# the next rows hold levels). Not decoded; Table 2 is collected through FY
# 2023/24 Q4 only.
_T2_LAST = "2024-Q1"


def _norm(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _periods(rows, hdr_i):
    """Column index -> calendar quarter, from the fiscal-year/quarter header."""
    years, quarters = rows[hdr_i], rows[hdr_i + 1]
    out, fy = {}, None
    for j, q in enumerate(quarters):
        y = _norm(years[j]) if j < len(years) else ""
        m = re.fullmatch(r"(\d{4})/(\d{2})", y)
        if m:
            fy = int(m.group(1))
        qm = re.fullmatch(r"Q([1-4])", _norm(q))
        if qm and fy is not None:
            off, cq = _FYQ[int(qm.group(1))]
            out[j] = f"{fy + off}-Q{cq}"
    return out


def _header(rows, start, end):
    return next(i for i in range(start, end) if any(
        re.fullmatch(r"\d{4}/\d{2}", _norm(v)) for v in rows[i]))


def _rec(comp, period, measure, value, unit, coverage, code):
    return {"coverage": coverage, "component": comp, "period": period,
            "frequency": "quarterly", "measure": measure, "value": float(value),
            "unit": unit, "series_code": code}


def _table1(rows, start, end):
    hdr = _header(rows, start, end)
    cols = _periods(rows, hdr)
    out, parent, section = [], None, ""
    for i in range(hdr + 2, end):
        label = _norm(rows[i][1])
        if not label or label.startswith("Source"):
            continue
        low = label.lower()
        if low == "gdp" or "debt service" in low:
            parent = None
            continue
        if low in ("proportion of total debt", "as % of gdp"):
            section = low
            continue
        if low.startswith("as % of total"):
            if parent is None:
                raise ValueError(f"BoN T1: '{label}' with no level row above it")
            comp, measure, unit = parent, "share", "percent"
        elif section == "proportion of total debt":
            comp, measure, unit = label, "share", "percent"
        elif section == "as % of gdp":
            comp, measure, unit = label, "share_of_gdp", "percent"
        else:
            comp, measure, unit, parent = label, "stock", _UNIT, label
        for j, period in cols.items():
            v = rows[i][j] if j < len(rows[i]) else None
            if v is not None and _norm(v) != "":
                out.append(_rec(comp, period, measure, v, unit,
                                "Central government debt", "BoN T1"))
    return out


def _table2(rows, start, end):
    """The three correctly labelled rows of the guarantees table, re-proved."""
    hdr = _header(rows, start, end)
    cols = _periods(rows, hdr)
    lab = {_norm(rows[i][1]).lower(): i for i in range(hdr + 2, end)
           if _norm(rows[i][1])}
    gdp_i = lab["gdp"]
    dom_i = lab["domestic guarantees"]
    dom_pct_i = dom_i + 1                       # "As % of GDP" directly under it
    tot_pct_i = lab["total guarantees as % of gdp"]
    if _norm(rows[dom_pct_i][1]).lower() != "as % of gdp":
        raise ValueError("BoN T2: layout changed -- no 'As % of GDP' under Domestic Guarantees")
    # The shifted rows used ONLY to prove the three kept ones (see docstring).
    foreign_level_i, foreign_pct_i = dom_i + 3, dom_i + 4
    out = []
    for j, period in cols.items():
        if period > _T2_LAST:
            continue
        g, d = rows[gdp_i][j], rows[dom_i][j]
        dp, tp = rows[dom_pct_i][j], rows[tot_pct_i][j]
        if d is None:
            continue
        agrees = abs(d / g * 100 - dp) <= 0.01
        if period in _KNOWN_T2_RATIO_GAP:
            if agrees or abs(dp - _KNOWN_T2_RATIO_GAP[period]) > 0.001:
                raise ValueError(f"BoN T2 {period}: the pinned published ratio "
                                 f"changed -- BoN revised it; update the pin")
        elif not agrees:
            raise ValueError(f"BoN T2 {period}: domestic % of GDP no longer "
                             f"= domestic / GDP")
        fp = rows[foreign_pct_i][j]
        if fp is None or abs(dp + fp - tp) > 0.01:
            raise ValueError(f"BoN T2 {period}: the label shift no longer holds "
                             f"(domestic% + row-51 value != total%) -- BoN may "
                             f"have corrected the table; revisit the layout")
        cov = "Central government loan guarantees"
        out.append(_rec("Domestic Guarantees", period, "stock", d, _UNIT, cov, "BoN T2"))
        out.append(_rec("Domestic Guarantees", period, "share_of_gdp", dp, "percent", cov, "BoN T2"))
        out.append(_rec("Total Guarantees", period, "share_of_gdp", tp, "percent", cov, "BoN T2"))
    return out


def parse(path: str, extras=None) -> pd.DataFrame:
    ws = openpyxl.load_workbook(path, data_only=True)[_SHEET]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    t1 = next(i for i, r in enumerate(rows) if _norm(r[1]).startswith("Table 1"))
    t2 = next(i for i, r in enumerate(rows) if _norm(r[1]).startswith("Table 2"))
    if "Central Government debt" not in _norm(rows[t1][1]) or \
            "loan guarantees" not in _norm(rows[t2][1]):
        raise ValueError(f"BoN: unexpected table titles {rows[t1][1]!r} / {rows[t2][1]!r}")
    df = pd.DataFrame(_table1(rows, t1, t2) + _table2(rows, t2, len(rows)))

    lv = df[(df.measure == "stock") & (df.coverage == "Central government debt")]
    p = lv.pivot_table(index="period", columns="component", values="value")
    gap = (p["Foreign debt stock"] + p["Domestic debt stock"]
           - p["Gross Central Government debt"]).abs()
    if (gap > 1.0).any():
        raise ValueError(f"BoN T1: foreign + domestic != gross in "
                         f"{list(gap[gap > 1.0].index)[:5]}")
    return df
