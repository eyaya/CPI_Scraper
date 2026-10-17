"""Zimbabwe -- ZPDMO Annual Public Debt Bulletin (end-December), the
back-issue companion to `zimbabwe_pdmo_debt` (which reads the 2023 Public Debt
Report). The bulletins are Ministry of Finance (Zimbabwe Public Debt
Management Office) documents, fetched as Wayback id_ copies of
zimtreasury.gov.zw, which no longer serves them.

TWO TABLES ARE READ, in ZWL$ millions as printed:

* Table 1 "Stock of total PPG Debt (Including RBZ External Debt) - December
  <year>": only rows that print ALL SEVEN cells (Non-Guaranteed DOD / Arrears /
  Total, Guaranteed DOD / Arrears / Total, Grand Total; "-" is a nil cell and
  is not emitted). Rows printing fewer cells (the RBZ facilities, the domestic
  instruments) cannot be placed in their columns and are not read here -- the
  domestic instruments come from Table 2 instead.
* Table 2 "Stock of Domestic Debt end December <y-1> and <y>": each instrument
  for both years, the unlabelled total row, and "as a per cent of GDP"
  (share_of_gdp). A "-*" cell (Compensation of Former Farm Owners, not counted
  in 2020) is nil and not emitted.

CHECKS: in Table 1, Non-Guaranteed Total + Guaranteed Total = Grand Total, and
Total Public Debt = External Debt + Domestic Debt (Grand Total); in Table 2,
the instruments sum to the printed total for each year.

DATING: end-December stocks, period "YYYY-12", frequency monthly -- the same
point-in-time convention as the 2023 report's "2023-09".
"""
from __future__ import annotations

import re

import pdfplumber

_COLS = ["Non-guaranteed DOD", "Non-guaranteed arrears", "Non-guaranteed total",
         "Guaranteed DOD", "Guaranteed arrears", "Guaranteed total", "Grand total"]
_TOK = r"(?:-\*?|\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+)"
_ROW7 = re.compile(rf"^((?:\d\.\s*)?\D.*?)\s+({_TOK})\s+({_TOK})\s+({_TOK})\s+({_TOK})\s+"
                   rf"({_TOK})\s+({_TOK})\s+({_TOK})$")
_ROW2 = re.compile(rf"^(\D.*?)\s+({_TOK})\s+({_TOK})$")
_CAP1 = re.compile(r"^Table 1: Stock of total PPG Debt.*December (\d{4})", re.M)
_CAP2 = re.compile(r"^Table 2: Stock of Domestic Debt end December (\d{4}) and (\d{4})", re.M)
_UNIT = "ZWL million"


def _v(tok: str):
    return None if tok.startswith("-") else float(tok.replace(",", ""))


def _page(pages, rx):
    # The caption also sits in the list of tables (with dot leaders).
    for t in pages:
        for m in rx.finditer(t):
            line = t[m.start():t.find("\n", m.start())]
            if "...." not in line:
                return t, m
    raise ValueError(f"ZPDMO bulletin: {rx.pattern[:40]!r} not found")


def parse_bulletin(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages[:30]]
    out = []

    text, m = _page(pages, _CAP1)
    year = m.group(1)
    code = f"ZPDMO Annual Public Debt Bulletin {year} Table 1"
    rows = {}
    for ln in text[m.end():].splitlines():
        if ln.startswith("Source"):
            break
        r = _ROW7.match(ln.strip())
        if r:
            rows[r.group(1).strip()] = [_v(x) for x in r.groups()[1:]]
    tot = next((v for k, v in rows.items() if k.startswith("Total Public Debt")), None)
    ext = next((v for k, v in rows.items() if k.startswith("1. External Debt")), None)
    if tot is None or ext is None:
        raise ValueError(f"ZPDMO {year} Table 1: headline rows not read ({list(rows)[:4]})")
    for k, v in rows.items():
        if v[2] is not None and v[5] is not None and v[6] is not None \
                and abs(v[2] + v[5] - v[6]) > 2:
            raise ValueError(f"ZPDMO {year} Table 1 {k!r}: {v[2]} + {v[5]} != {v[6]}")
        for col, val in zip(_COLS, v):
            if val is not None:
                out.append({"component": f"{k} [{col}]", "period": f"{year}-12",
                            "frequency": "monthly", "measure": "stock",
                            "value": val, "unit": _UNIT, "series_code": code})

    text, m = _page(pages, _CAP2)
    years = [m.group(1), m.group(2)]
    code = f"ZPDMO Annual Public Debt Bulletin {year} Table 2"
    items, total, pct = {}, None, None
    for ln in text[m.end():].splitlines()[1:]:
        s = ln.strip()
        if s.startswith(("*", "Source", "Nominal")):
            break
        r = _ROW2.match(s)
        if r:
            lab = r.group(1).strip()
            vals = [_v(r.group(2)), _v(r.group(3))]
            if lab.lower().startswith("as a per cent of gdp"):
                pct = vals
            else:
                items[lab] = vals
        elif re.fullmatch(rf"({_TOK})\s+({_TOK})", s):
            total = [_v(x) for x in s.split()]
    if total is None or not items:
        raise ValueError(f"ZPDMO {year} Table 2: total or items not read")
    for j, y in enumerate(years):
        s = sum(v[j] or 0 for v in items.values())
        if abs(s - (total[j] or 0)) > 2:
            raise ValueError(f"ZPDMO {year} Table 2 {y}: instruments {s} != {total[j]}")
    for lab, vals in [*items.items(), ("Total domestic debt", total)]:
        for y, val in zip(years, vals):
            if val is not None:
                out.append({"component": f"Domestic debt: {lab}", "period": f"{y}-12",
                            "frequency": "monthly", "measure": "stock",
                            "value": val, "unit": _UNIT, "series_code": code})
    if pct:
        for y, val in zip(years, pct):
            if val is not None:
                out.append({"component": "Domestic debt", "period": f"{y}-12",
                            "frequency": "monthly", "measure": "share_of_gdp",
                            "value": val, "unit": "percent", "series_code": code})
    return out
