"""Egypt — Central Bank of Egypt (CBE), Time Series: "External Debt by Debtor"
(quarterly) and "Gross Domestic Debt" (quarterly).

PUBLISHER: the Central Bank of Egypt, which compiles Egypt's external-debt
statistics and publishes the domestic-debt table (its source line: "Central
Bank of Egypt - Ministry of Finance - National Investment Bank").

TWO WORKBOOKS, TWO PERIMETERS -- `coverage` is set per row:

* EXTERNAL DEBT BY DEBTOR (primary; US$ million; one sheet per fiscal year,
  2004/2005 .. current). The table is the WHOLE ECONOMY's gross external debt
  (government, central bank, banks, other sectors). Only the GOVERNMENT debtor
  block is public debt in this indicator's sense, so only it is collected:
  "Government external debt (CBE, external debt by debtor)". The central-bank,
  bank and other-sector blocks, and the economy-wide total, are NOT collected.
* GROSS DOMESTIC DEBT (extra; LE million; sheets 2004/2005 .. 2019/2020 --
  CBE has not extended it since June 2020): "Gross domestic debt: government,
  public economic authorities and NIB, net of intra-debt" -- the CBE's own
  definition, (1+2+3-4) in its header.

FISCAL QUARTERS, MAPPED TO CALENDAR QUARTERS. Egypt's fiscal year runs July
to June; the external sheets head their columns Q1..Q4 under "2025/2026".
Fiscal Q1 = July-September = calendar Q3 of the first year; Q2 = Q4 of the
first year; Q3 = Q1 of the second; Q4 = Q2 of the second -- the same
relabelling the GDP collector applies to CBE data (a relabel of the same
quarter-end, not a recomputation). The domestic sheets name the quarter-end
month itself ("Sept.2019", " March 2020"), which is read directly and checked
against the fiscal-quarter position.

LABELS. Sub-items repeat ("Loans", "Debt securities", "US$", "LE") under
different parents, so each label carries its parent heading ("Government -
Long-term Debt - Loans"; "Treasury Bills : - LE"). Values are kept as stored,
rounded to 6 decimals only to drop float residue (163911.09999999998).

NOT COLLECTED: the signed NETTING rows of the domestic table ("Net Government
Balances with the Banking System", "Net Balances of Public Economic
Authorities ...", deposits) -- they are offsets, negative in most periods,
not debt stocks; "..", blank and zero-only placeholder cells are skipped as
"no value", never read as 0 where printed "..".

CROSS-CHECK: Government external debt end-March 2026 (FY2025/26 Q3) 82 841,7
US$ mn; end-Sept 2025 80 760,7; end-June 2005 (FY2004/05 Q4) 18 231,0. Gross
domestic debt end-June 2020 4 742 107 LE mn; end-Sept 2004 443 892.
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd

_TOP = {"central bank", "banks", "other sectors", "monetary authorities", "monetary authority",
        "deposit-taking corporations"}
_MONTH_Q = {"sept": 3, "sep": 3, "dec": 4, "march": 1, "mar": 1, "june": 2,
            "jun": 2}
_FISCAL_TO_CAL = {1: (0, 3), 2: (0, 4), 3: (1, 1), 4: (1, 2)}  # (year offset, quarter)


def _clean(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _num(v):
    if isinstance(v, (int, float)):
        return round(float(v), 6)
    return None


def _external(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    rows = []
    for ws in wb.worksheets:
        cells = [r for r in ws.iter_rows(values_only=True)]
        fy = next((m for r in cells[:6] for c in r
                   if (m := re.search(r"(20\d\d)\s*/\s*(20\d\d)", str(c or "")))), None)
        if not fy:
            raise ValueError(f"Egypt CBE external: no fiscal year on sheet {ws.title!r}")
        y0 = int(fy.group(1))
        qrow = next(r for r in cells[:8] if "Q1" in [_clean(c) for c in r])
        qcols = {i: int(_clean(c)[1]) for i, c in enumerate(qrow)
                 if re.fullmatch(r"Q[1-4]", _clean(c))}
        in_gov, level2 = False, ""
        for r in cells:
            lab = _clean(r[1] if len(r) > 1 else "")
            low = lab.lower().rstrip("*").strip()
            if low == "government":
                in_gov, comp = True, "Government"
            elif in_gov and low.rstrip(" *") in _TOP:
                break
            elif in_gov and lab:
                # a maturity heading ("Long-term Debt", "Medium- and Long-Term",
                # "Short-term Debt (Loans)") opens a new sub-block
                if re.match(r"(?i)(short|long|medium)", lab):
                    level2 = lab.rstrip(" *")
                    comp = f"Government - {level2}"
                else:
                    comp = f"Government - {level2} - {lab.rstrip(' *')}" if level2 \
                        else f"Government - {lab.rstrip(' *')}"
            else:
                continue
            for i, fq in qcols.items():
                v = _num(r[i]) if i < len(r) else None
                if v is None:
                    continue
                off, cq = _FISCAL_TO_CAL[fq]
                rows.append({"coverage": "Government external debt (CBE, external debt by debtor)",
                             "component": comp, "period": f"{y0 + off}-Q{cq}",
                             "frequency": "quarterly", "measure": "stock",
                             "value": v, "unit": "USD million",
                             "series_code": "CBE external debt by debtor"})
        if not in_gov:
            raise ValueError(f"Egypt CBE external: no Government block on {ws.title!r}")
    return rows


def _domestic(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    rows = []
    for ws in wb.worksheets:
        cells = [r for r in ws.iter_rows(values_only=True)]
        hdr = next(i for i, r in enumerate(cells)
                   if any(re.search(r"(?i)(sept|dec|march|june)\.?\s*20\d\d", _clean(c))
                          for c in r))
        cols = {}
        for i, c in enumerate(cells[hdr]):
            m = re.search(r"(?i)(sept|sep|dec|march|mar|june|jun)\.?\s*(20\d\d)", _clean(c))
            if m:
                cols[i] = f"{m.group(2)}-Q{_MONTH_Q[m.group(1).lower()]}"
        if len(cols) != 4:
            raise ValueError(f"Egypt CBE domestic: {len(cols)} quarter columns on {ws.title!r}")
        parent = ""
        for r in cells[hdr + 1:]:
            lab = _clean(r[1] if len(r) > 1 else "")
            if not lab or lab.lower().startswith("source"):
                if lab.lower().startswith("source"):
                    break
                continue
            vals = {p: _num(r[i]) for i, p in cols.items() if i < len(r)}
            if lab.endswith(":"):
                parent = lab
            comp = f"{parent} - {lab}" if (parent and lab in ("US$", "LE", "Euro")) else lab
            if re.search(r"(?i)^(net |deposits of|e- net)", lab) or "Net Balances" in lab \
                    or "Net Government Balances" in lab:
                continue           # signed netting offsets, not debt stocks
            for p, v in vals.items():
                if v is None:
                    continue
                if v < 0:
                    raise ValueError(f"Egypt CBE domestic: negative stock {lab!r} {p}")
                rows.append({"coverage": "Gross domestic debt: government, public economic "
                                         "authorities and NIB, net of intra-debt (CBE)",
                             "component": comp, "period": p, "frequency": "quarterly",
                             "measure": "stock", "value": v, "unit": "LE million",
                             "series_code": "CBE gross domestic debt"})
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        wb_names = openpyxl.load_workbook(p, read_only=True).sheetnames
        ws0 = openpyxl.load_workbook(p, read_only=True)[wb_names[0]]
        title = " ".join(_clean(c) for r in ws0.iter_rows(max_row=6, values_only=True)
                         for c in r if c)
        if "External Debt by Debtor" in title:
            rows += _external(p)
        elif "Gross Domestic Debt" in title:
            rows += _domestic(p)
        else:
            raise ValueError(f"Egypt CBE: unrecognised workbook {p}")
    df = pd.DataFrame(rows)
    key = ["coverage", "component", "period", "frequency", "measure", "unit"]
    dup = df[df.duplicated(key, keep=False)]
    if len(dup):
        raise ValueError(f"Egypt CBE: duplicate keys, e.g. "
                         f"{dup.iloc[0][['component', 'period']].tolist()}")
    return df
