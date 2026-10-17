"""Mauritius — Ministry of Finance, Quarterly Public Sector Debt Statistics
(QPSDS) workbook, Table 1 "Public Sector Debt".

PUBLISHER: Ministry of Finance (Public Debt Management Unit), mof.govmu.org
"Debt Data" page; one workbook per quarter (QPSDS <Mon><YYYY>.xlsx), each
carrying the whole history back to June 2003.

SEVERAL PERIMETERS, SIDE BY SIDE, IN ONE TABLE -- the reason `coverage` is set
PER ROW here. Table 1 builds the public sector up in layers, as the Public Debt
Management Act defines it:

    Budgetary Central Government (BCG)        domestic + external
    + Extra Budgetary Units                   -> Central Government
    + Local Government (+ Rodrigues)          -> General Government
    + Public Corporations                     -> Public Sector

Each row's `coverage` is the layer it belongs to, and `component` keeps the
printed label (footnote markers like "Treasury Notes2" stripped of their
trailing digit). The "As percent of GDP" rows name no series of their own, so
each takes the component of the total it follows ("Budgetary Central
Government External Debt", ...) -- stated in `_ROWS`, never inferred.

RATIOS ARE STORED AS FRACTIONS under a "0.0%" cell format (0.6253 displays as
62.5%). They are emitted as the PERCENT the publisher displays (value x 100),
unit "percent", measure share_of_gdp -- the convention the GDP indicator uses
for Eswatini and Burkina Faso's percent-formatted cells.

PERIODS. Columns are end-of-period stocks: end-June only for 2003-2007, then
quarterly from June 2008 (headers mix "Jun 2003" text, "Sept 2015" and real
dates). Every column is dated to its quarter (YYYY-Qn), frequency quarterly.
The newest columns are flagged "Provisional" in row 4; a later issue's
revision replaces them through merge-on-write.

NOT COLLECTED: the consolidation-adjustment row (a negative adjustment, not a
debt stock), "Less Cash and Cash Equivalents & Equity" (an asset deduction),
the GDP memo row (not debt), and every "Note 6" / "Note 8" placeholder cell --
net debt was not computed before Sept 2015 and is no longer computed from
Sept 2025 (PDM Act s.6(1A) repealed). Tables 1a-20 (corporation-level detail,
external debt of the whole economy, debt service, maturity and currency
breakdowns) are not read yet.

CROSS-CHECK (Jun 2026, Rs million): public sector debt after consolidation
669,635.86 (86.2% of GDP); BCG total debt and Public Corporations rows hold to
their printed sums; Jun 2003 BCG total 96,121 (62.5% of GDP).
"""
from __future__ import annotations

import datetime as dt
import re

import openpyxl
import pandas as pd

_SHEET = "Tab 1"
_UNIT = "Rs million"
BCG, EBU, CG = "Budgetary Central Government", "Extra Budgetary Units", "Central Government"
LG, RRA, GG = "Local Government", "Rodrigues Regional Assembly", "General Government"
PC, PS = "Public Corporations", "Public Sector"

# printed label (stripped) -> (coverage, component, measure); None = not collected
_ROWS = {
    "Budgetary Central Government (BCG) Domestic Debt": (BCG, "Budgetary Central Government (BCG) Domestic Debt", "stock"),
    "Government securities issued for meeting borrowing requirements": (BCG, "Government securities issued for meeting borrowing requirements", "stock"),
    "- Treasury Bills and other short term borrowings": (BCG, "Treasury Bills and other short term borrowings", "stock"),
    "- Treasury Notes2": (BCG, "Treasury Notes", "stock"),
    "- Five year & Seven year GoM Bonds": (BCG, "Five year & Seven year GoM Bonds", "stock"),
    "- Other Long Term Bonds": (BCG, "Other Long Term Bonds", "stock"),
    "Government securities issued for mopping up excess liquidity": (BCG, "Government securities issued for mopping up excess liquidity", "stock"),
    "BCG Domestic Debt as percent of GDP": (BCG, "Budgetary Central Government (BCG) Domestic Debt", "share_of_gdp"),
    "Budgetary Central Government External Debt": (BCG, "Budgetary Central Government External Debt", "stock"),
    "- Short Term3": (BCG, "External debt - Short Term", "stock"),
    "- Medium & Long Term4": (BCG, "External debt - Medium & Long Term", "stock"),
    "- Long term debt liability - IMF SDR Allocations5": (BCG, "External debt - Long term debt liability - IMF SDR Allocations", "stock"),
    "Budgetary Central Government Total Debt": (BCG, "Budgetary Central Government Total Debt", "stock"),
    "Total- Extra Budgetary Units": (EBU, "Total- Extra Budgetary Units", "stock"),
    "Central Government Total Debt": (CG, "Central Government Total Debt", "stock"),
    "Local Government Debt": (LG, "Local Government Debt", "stock"),
    "Rodrigues Regional Assembly": (RRA, "Rodrigues Regional Assembly", "stock"),
    "General Government Total Debt": (GG, "General Government Total Debt", "stock"),
    "General Government Total Debt as % of GDP": (GG, "General Government Total Debt", "share_of_gdp"),
    "Public Corporations Total Debt6": (PC, "Public Corporations Total Debt", "stock"),
    "Public Corporations debt as % of GDP": (PC, "Public Corporations Total Debt", "share_of_gdp"),
    "Public Sector Domestic Debt": (PS, "Public Sector Domestic Debt", "stock"),
    "Public Sector Domestic Debt as % of GDP": (PS, "Public Sector Domestic Debt", "share_of_gdp"),
    "Public Sector External Debt": (PS, "Public Sector External Debt", "stock"),
    "Public Sector External Debt as % of GDP": (PS, "Public Sector External Debt", "share_of_gdp"),
    "Public Sector Debt (Gross prior to consolidation adjustment)": (PS, "Public Sector Debt (Gross prior to consolidation adjustment)", "stock"),
    "Public Sector Debt (Gross prior to consolidation adjustment) as % of GDP": (PS, "Public Sector Debt (Gross prior to consolidation adjustment)", "share_of_gdp"),
    "Consolidation adjustment (iro Govt Securities held by non-financial public sector entities)7": None,
    "Public Sector Debt (Gross) after consolidation adjustment": (PS, "Public Sector Debt (Gross) after consolidation adjustment", "stock"),
    "Public Sector Debt as % of GDP (after consolidation adjustment)": (PS, "Public Sector Debt (Gross) after consolidation adjustment", "share_of_gdp"),
    "Less Cash and Cash Equivalents & Equity (Net of Rs 500M)8": None,
    "Public Sector Net Debt": (PS, "Public Sector Net Debt", "stock"),
    "Public Sector Net Debt as % of GDP": (PS, "Public Sector Net Debt", "share_of_gdp"),
    "GDP (Source - Statistics Mauritius)": None,
}
# Repeated sub-rows ("Domestic-Guaranteed", "As percent of GDP") take their
# coverage from the block they sit in, which these headers open.
_BLOCK_OPENERS = {
    "Budgetary Central Government External Debt": (BCG, "Budgetary Central Government External Debt"),
    "Budgetary Central Government Total Debt": (BCG, "Budgetary Central Government Total Debt"),
    "Total- Extra Budgetary Units": (EBU, "Total- Extra Budgetary Units"),
    "Central Government Total Debt": (CG, "Central Government Total Debt"),
    "Local Government Debt": (LG, "Local Government Debt"),
    "Public Corporations Total Debt6": (PC, "Public Corporations Total Debt"),
}
_SUBROWS = {  # normalised sub-label -> printed component (within its block)
    "domestic-guaranteed": "Domestic-Guaranteed",
    "domestic-non guaranteed": "Domestic-Non Guaranteed",
    "domestic-non-guaranteed": "Domestic-Non Guaranteed",
    "external-guaranteed": "External-Guaranteed",
    "external-non guaranteed": "External-Non Guaranteed",
    "external-non-guaranteed": "External-Non Guaranteed",
    "external-guaranteed and non guaranteed": "External-Guaranteed and non guaranteed",
}
_MON = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
        "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}


def _clean(label) -> str:
    return re.sub(r"\s+", " ", str(label).replace("​", "")).strip()


def _quarter(h) -> str:
    if isinstance(h, (dt.datetime, dt.date)):
        y, m = h.year, h.month
    else:
        mm = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{4})", _clean(h))
        if not mm or mm.group(1).lower() not in _MON:
            raise ValueError(f"Mauritius QPSDS: unreadable period header {h!r}")
        y, m = int(mm.group(2)), _MON[mm.group(1).lower()]
    if m not in (3, 6, 9, 12):
        raise ValueError(f"Mauritius QPSDS: {h!r} is not a quarter end")
    return f"{y}-Q{m // 3}"


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    ws = openpyxl.load_workbook(path, data_only=True)[_SHEET]
    cols = [(c, _quarter(ws.cell(3, c).value))
            for c in range(2, ws.max_column + 1) if ws.cell(3, c).value is not None]
    if len({p for _, p in cols}) != len(cols):
        raise ValueError("Mauritius QPSDS: two columns date to the same quarter")

    rows, block, seen = [], None, set()
    for r in range(5, ws.max_row + 1):
        raw = ws.cell(r, 1).value
        if raw is None:
            continue
        label = _clean(raw)
        if label.startswith(("*", "(")):
            break                                        # footnotes
        if label in _BLOCK_OPENERS:
            block = _BLOCK_OPENERS[label]
        if label in _ROWS:
            spec = _ROWS[label]
            seen.add(label)
            if spec is None:
                continue
            coverage, component, measure = spec
        else:
            key = re.sub(r"\s*-\s*", "-", label).lower()
            if label == "As percent of GDP":
                if block is None:
                    raise ValueError(f"Mauritius QPSDS row {r}: ratio outside a block")
                coverage, component, measure = block[0], block[1], "share_of_gdp"
            elif key in _SUBROWS and block is not None:
                coverage, component, measure = block[0], _SUBROWS[key], "stock"
            else:
                raise ValueError(f"Mauritius QPSDS row {r}: unknown label {label!r} "
                                 f"-- the table's layout has changed")
        for c, period in cols:
            v = ws.cell(r, c).value
            if not isinstance(v, (int, float)):
                continue                                 # "Note 6" / "Note 8" placeholders
            if measure == "share_of_gdp":
                v, unit = round(float(v) * 100, 6), "percent"
            else:
                v, unit = float(v), _UNIT
            rows.append({"coverage": coverage, "component": component,
                         "period": period, "frequency": "quarterly",
                         "measure": measure, "value": v, "unit": unit,
                         "series_code": "QPSDS Table 1"})
    missing = [k for k in _ROWS if k not in seen]
    if missing:
        raise ValueError(f"Mauritius QPSDS: rows not found {missing[:3]}")
    df = pd.DataFrame(rows)
    key = ["coverage", "component", "period", "measure"]
    if df.duplicated(key).any():
        raise ValueError("Mauritius QPSDS: two rows share a key")
    return df
