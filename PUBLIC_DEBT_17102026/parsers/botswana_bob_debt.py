"""Botswana -- Bank of Botswana, "Botswana Economic and Financial Statistics"
(BEFS) monthly workbook, Table 7.5 "PUBLIC DEBT OUTSTANDING (P million)".

PUBLISHER: Bank of Botswana; the table's source line is "Ministry of Finance
and Bank of Botswana".

THREE SECTIONS, `coverage` set per row:
  * A "Medium and Long Term External Debt" and B "Domestic Debt", summing to
    "TOTAL GOVERNMENT DEBT" -> coverage "Central government debt";
  * C "Government Guaranteed Debt" (domestic, external, total) -> coverage
    "Government guaranteed debt";
  * "TOTAL GOVERNMENT AND GOVERNMENT GUARANTEED DEBT" -> coverage
    "Central government and government guaranteed debt".
Creditor and instrument rows are qualified by their parent ("Loans from
Organisations: African Development Fund/Bank", "Other Loans: BPOPF").
Two-line names are rejoined ("International Bank for Reconstruction and
Development").

PERIODS. Columns 2014/15 .. 2022/23 are FISCAL YEARS (footnote 1: "Fiscal year
runs from 1st April to 31st March"); each is a stock at the year's end and is
dated to the year in which the fiscal year ENDS (2014/15 -> "2015", annual).
From 2023/24 the table prints quarter ends Jun / Sep / Dec / Mar of each
fiscal year; each is dated to its calendar quarter (Jun of 2023/24 ->
2023-Q2, Mar of 2023/24 -> 2024-Q1).

"…" (not available) and "-" (nil) are skipped, not read as 0; most creditor
detail is printed for the March quarter only. Values carry float residue
(31.76470542986425); kept as stored. Every column with all three is checked:
total external + total domestic = total government debt (to P 0.2 million).

CROSS-CHECK: 2014/15 total government debt 25 449.4 (external 17 981.3,
domestic 7 468.1); guaranteed 7 680.6; 2025/26 Mar (2026-Q1) total 83 937.9;
2026/27 Jun (2026-Q2) 86 325.85.
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd

_UNIT = "BWP million"
_SHEET = "7.5"
_MONTH_Q = {"jun": (0, 2), "sep": (0, 3), "dec": (0, 4), "mar": (1, 1)}
_PARENTS = {"loans from governments", "loans from organisations", "other loans"}


def _norm(v) -> str:
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()


def _num(v):
    s = _norm(v).replace(" ", "")
    if s in ("", "…", "...", "-", "–"):
        return None
    return float(s)


def _columns(rows):
    hdr_i = next(i for i, r in enumerate(rows) if _norm(r[0]).startswith("Period"))
    fy_row, m_row = rows[hdr_i - 1], rows[hdr_i]
    cols, fy = {}, None
    for j in range(1, len(fy_row)):
        m = re.fullmatch(r"(\d{4})/(\d{2})", _norm(fy_row[j]))
        if m:
            fy = int(m.group(1))
        mon = _norm(m_row[j]).lower()[:3] if j < len(m_row) else ""
        if mon in _MONTH_Q and fy is not None:
            off, q = _MONTH_Q[mon]
            cols[j] = (f"{fy + off}-Q{q}", "quarterly")
        elif m:                                   # an annual fiscal-year column
            cols[j] = (str(fy + 1), "annual")
    return hdr_i, cols


def parse(path: str, extras=None) -> pd.DataFrame:
    ws = openpyxl.load_workbook(path, data_only=True)[_SHEET]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    if not any("PUBLIC DEBT OUTSTANDING" in _norm(r[0]).upper() for r in rows[:4]):
        raise ValueError("BoB 7.5: title changed")
    if "(P million)" not in _norm(rows[2][0]):
        raise ValueError(f"BoB 7.5: unit line changed: {rows[2][0]!r}")
    hdr_i, cols = _columns(rows)

    out, section, parent, pending = [], "", None, ""
    for r in rows[hdr_i + 1:]:
        raw = _norm(r[0])
        if not raw or raw.startswith("Source") or re.match(r"^\d\.", raw):
            continue
        label = re.sub(r"\d$", "", raw).strip()        # footnote digit: "Japan3"
        vals = {j: _num(r[j]) for j in cols if j < len(r)}
        if re.match(r"^[ABC]:", label):
            section, parent, pending = label[0], None, ""
            continue
        if all(v is None for v in vals.values()) and not any(
                _norm(r[j]) for j in cols if j < len(r)):
            if label.lower() in _PARENTS:
                parent = label
            else:
                pending = label                         # first line of a wrapped name
            continue
        if pending:
            label, pending = f"{pending} {label}", ""
        low = label.lower()
        if low in _PARENTS:
            parent, comp = label, label
        elif str(r[0]).startswith(" ") and parent:
            comp = f"{parent}: {label}"
        else:
            comp = label
            if low.startswith("total"):
                parent = None
        if section == "C":
            cov = "Government guaranteed debt"
            if low in ("domestic", "external"):
                comp = f"Guaranteed {low} debt"
        else:
            cov = "Central government debt"
        if low.startswith("total government and government guaranteed"):
            cov = "Central government and government guaranteed debt"
        for j, (period, freq) in cols.items():
            v = vals.get(j)
            if v is not None:
                out.append({"coverage": cov, "component": comp, "period": period,
                            "frequency": freq, "measure": "stock", "value": v,
                            "unit": _UNIT, "series_code": "BoB BEFS T7.5"})
    df = pd.DataFrame(out)
    p = df[df.coverage == "Central government debt"].pivot_table(
        index=["period", "frequency"], columns="component", values="value")
    need = ["Total External Debt", "Total Domestic Debt", "TOTAL GOVERNMENT DEBT"]
    ok = p[need].dropna()
    gap = (ok[need[0]] + ok[need[1]] - ok[need[2]]).abs()
    if len(ok) < 10 or (gap > 0.2).any():
        raise ValueError(f"BoB 7.5: external + domestic != total in "
                         f"{list(gap[gap > 0.2].index)}")
    return df
