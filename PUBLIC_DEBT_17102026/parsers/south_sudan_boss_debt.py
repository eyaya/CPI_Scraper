"""South Sudan — Bank of South Sudan "Macroeconomic Review Report", Table 6
"South Sudan Outstanding Public Debt" (source: Ministry of Petroleum and
Ministry of Finance and Planning).

The central bank republishes the ministries' external-debt figures, credited
under the table -- the sanctioned central-bank route. Collected: external debt
by creditor (World Bank, IMF, AfDB, other creditors) and the total, USD
million, for the quarter the table is dated (2024-Q3 in the Q1-2025 review).

NOT COLLECTED: Table 5 "Composition of Net Claim on Central Government" --
monetary-survey claims net of government deposits, not a debt stock.

CHECK: the creditor rows must sum to the printed total (104 + 227 + 19 +
2 082 = 2 432).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_CAPTION = re.compile(r"Table \d+: South Sudan Outstanding Public Debt")
_TOTAL = "Total External Debt in USD"


def parse(path: str, extras=None) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        text = next((p.extract_text() or "" for p in pdf.pages
                     if _CAPTION.search(p.extract_text() or "")
                     and _TOTAL in (p.extract_text() or "")), None)
    if text is None:
        raise ValueError("BoSS: Table 'South Sudan Outstanding Public Debt' not found")
    lines = text[_CAPTION.search(text).end():].splitlines()
    head = next(ln for ln in lines if ln.strip().startswith("Million USD"))
    m = re.search(r"(20\d\d)Q([1-4])", head)
    if not m:
        raise ValueError(f"BoSS: undated header {head!r}")
    period = f"{m.group(1)}-Q{m.group(2)}"

    rows = []
    for ln in lines[lines.index(head) + 1:]:
        ln = ln.strip()
        if ln.startswith("Source"):
            break
        r = re.fullmatch(r"(.+?)\s+([\d,]+(?:\.\d+)?)", ln)
        if r:
            rows.append((r.group(1), float(r.group(2).replace(",", ""))))
    labels = [r[0] for r in rows]
    if not rows or labels[-1] != _TOTAL:
        raise ValueError(f"BoSS: rows {labels}")
    *parts, (_, total) = rows
    if abs(sum(v for _, v in parts) - total) > 0.5:
        raise ValueError(f"BoSS: creditors sum to {sum(v for _, v in parts)}, "
                         f"total {total}")
    return pd.DataFrame([{"component": lab, "period": period,
                          "frequency": "quarterly", "measure": "stock",
                          "value": v, "unit": "USD million",
                          "series_code": "BoSS MER Table 6"} for lab, v in rows])
