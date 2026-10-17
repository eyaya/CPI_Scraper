"""Sudan — Central Bank of Sudan (CBOS), 58th Annual Report 2018, chapter 10:
Table (10-7) "Sudan External Debt for 2017 and 2018" and Table (10-8)
"External Debt Sustainability Indicators".

PUBLISHER: CBOS, whose External Debt Unit compiles Sudan's external-debt
statistics (the source line of both tables). Sudan's statistics office
(cbs.gov.sd) no longer resolves; the Ministry of Finance publishes no debt
series online.

COVERAGE, as the report states it: "the total external obligations of Sudan
... including all sources of financing" -- Sudan's external debt by creditor
group (Paris Club, non-Paris Club, international and regional institutions,
foreign commercial banks, foreign suppliers' facilities). Domestic debt is not
tabulated as a stock. Figures exclude South Sudan (the report postdates 2011).

Rows (US$ billion as printed; one decimal):
* 2017 -- total by creditor group;
* 2018 -- by creditor group: principal, contractual interest, delay (penalty)
  interest and total, plus each group's weight in total debt (share, %);
* Table (10-8): total debt to GDP, 2017 and 2018 (share_of_gdp).
Checked: for every 2018 group, principal + contractual + delay interest =
total (to 0.15, one-decimal rounding); the groups sum to the printed Total in
both years; the weights sum to 100.

TRAPS. Two group labels wrap around their numbers ("International and
Regional" / numbers / "Institutions"); Foreign Suppliers' Facilities prints
only four numbers (2017 total, 2018 principal, 2018 total, weight -- no
interest), assigned by count and checked principal = total.

A PUBLISHED CONTRADICTION, NOT RESOLVED: the report's opening summary table
(chapter 1) prints external debt at 39.4% (2017) and 103.3% (2018) of GDP;
Table (10-8) prints 45 and 98.9. Only Table (10-8) is collected -- it is the
External Debt Unit's own table; the summary's are noted here.

CROSS-CHECK: total external debt 48.2 (2017) and 49.9 (2018) US$ billion;
2018 principal 19.7, contractual interest 4.8, delay interest 25.4; Paris
Club 15.7 (31.5%); debt to GDP 98.9% (2018).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_GROUPS = ["Non Paris Club countries", "Paris Club countries",
           "International and Regional Institutions",
           "Foreign international Commercial Banks",
           "Foreign Suppliers Facilities", "Total"]
_NUM = r"\d+(?:\.\d+)?"
_CODE = "CBOS Annual Report 2018, Table 10-7"


def _page_text(path: str, needle: str) -> str:
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[200:240]:
            t = page.extract_text() or ""
            if needle in t:
                return t
    raise ValueError(f"CBOS annual report: {needle!r} not found")


def _table_10_7(path: str) -> list[dict]:
    t = _page_text(path, "Table (10 - 7)")
    t = t[t.index("Table (10 - 7)"):t.index("Source: Central Bank of Sudan")]
    lines = [l.strip() for l in t.splitlines()]
    found, pending = {}, ""
    for l in lines:
        m = re.fullmatch(rf"(.*?)\s*((?:{_NUM}\s*){{4,6}})", l)
        if m and not l.startswith(("Year", "Total Debt")):
            label = (m.group(1) or pending).strip()
            nums = [float(x) for x in m.group(2).split()]
            pending = ""
            found[label] = nums
            continue
        if found and not m and l and not l.startswith(("Source", "(US")):
            # the wrapped tail of the previous label ("Institutions")
            last = list(found)[-1]
            if last + " " + l in _GROUPS:
                found[last + " " + l] = found.pop(last)
                continue
        if l and not l.startswith(("Table", "Sudan External", "(US", "Year",
                                   "Contractual", "Total Debt", "Source of")):
            pending = l
    rows, by = [], {}
    for g in _GROUPS:
        key = next((k for k in found if k == g or (k and g.startswith(k))
                    or (k and g.endswith(k))), None)
        if key is None:
            raise ValueError(f"CBOS 10-7: group {g!r} not read (got {list(found)})")
        by[g] = found.pop(key)
    for g, n in by.items():
        if len(n) == 6:
            y17, princ, contr, delay, tot, w = n
            if abs(princ + contr + delay - tot) > 0.15:
                raise ValueError(f"CBOS 10-7: {g} components != total")
            parts = {"Principal": princ, "Contractual interests": contr,
                     "Delay interests": delay}
        elif len(n) == 4:
            y17, princ, tot, w = n
            if princ != tot:
                raise ValueError(f"CBOS 10-7: {g} four-number row does not fit")
            parts = {"Principal": princ}
        else:
            raise ValueError(f"CBOS 10-7: {g} has {len(n)} numbers")
        base = dict(frequency="annual", unit="USD billion", series_code=_CODE)
        rows.append({**base, "component": g, "period": "2017", "measure": "stock", "value": y17})
        rows.append({**base, "component": g, "period": "2018", "measure": "stock", "value": tot})
        for p, v in parts.items():
            rows.append({**base, "component": f"{g} - {p}", "period": "2018",
                         "measure": "stock", "value": v})
        if g != "Total":
            rows.append({"component": g, "period": "2018", "frequency": "annual",
                         "measure": "share", "value": w, "unit": "percent",
                         "series_code": _CODE})
    for col, per in ((0, "2017"), (4, "2018")):
        s = sum(by[g][col if len(by[g]) == 6 else (0 if per == "2017" else 2)]
                for g in _GROUPS[:-1])
        tot = by["Total"][col]
        if abs(s - tot) > 0.25:
            raise ValueError(f"CBOS 10-7: groups sum to {s} vs Total {tot} ({per})")
    w = sum(by[g][-1] for g in _GROUPS[:-1])
    if abs(w - 100) > 0.3:
        raise ValueError(f"CBOS 10-7: weights sum to {w}")
    return rows


def _table_10_8(path: str) -> list[dict]:
    t = _page_text(path, "Total debt to GDP")
    m = re.search(rf"Total debt to GDP\s+({_NUM})\s+({_NUM})\s+({_NUM})", t)
    if not m:
        raise ValueError("CBOS 10-8: 'Total debt to GDP' row not read")
    # columns: standard (30), 2017, 2018 -- the standard is a benchmark, not data
    return [{"component": "Total", "period": p, "frequency": "annual",
             "measure": "share_of_gdp", "value": float(v), "unit": "percent",
             "series_code": "CBOS Annual Report 2018, Table 10-8"}
            for p, v in (("2017", m.group(2)), ("2018", m.group(3)))]


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    return pd.DataFrame(_table_10_7(path) + _table_10_8(path))
