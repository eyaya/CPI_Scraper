"""South Sudan — Ministry of Finance and Planning, "Debt Policy and
Medium-Term Debt Strategy" report (2025), Table 3 "Domestic Debt Outstanding
as at December 31, 2022".

DOMESTIC ONLY, AND WHY. The same report's Table 2 (external debt by creditor)
contradicts itself: the commercial creditors sum to 1 095,49 against a printed
subtotal of 2 050,21, the subtotals sum to 2 526,91 against a grand total of
2 059,21, and the prose gives commercial debt as 1 700,48. It is refused.
Table 3 is a printed statistical table that adds up exactly, so it is taken:

    Advances from BSS                      424 997 799 745,75   99,55 %
    Borrowing from BSS in USD                               0
    BSS's Capital Restoration (AX1-AX27)     1 917 373 479,74    0,45 %
    Overdrafts from BSS (SSP & USD)                         0
    TOTAL                                  426 915 173 225,49  100,00 %

Values are SSP (units, as printed), stock and share of total. The prose above
the table gives advances as "SSP424,997.74 million"; the table's own figure is
the one collected.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_CAPTION = re.compile(r"Table 3: Domestic Debt Outstanding as at (\w+) (\d+), (20\d\d)")
_LABELS = ["Advances from BSS", "Borrowing from BSS in USD",
           "BSS's Capital Restoration (Series AX1-AX27)",
           "Overdrafts from BSS (SSP & USD)", "TOTAL"]


def _num(s: str) -> float:
    return float(s.replace(" ", "").replace(",", ""))


def parse(path: str, extras=None) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        text = next((p.extract_text() or "" for p in pdf.pages
                     if _CAPTION.search(p.extract_text() or "")), None)
    if text is None:
        raise ValueError("MoFP South Sudan: Table 3 not found")
    cap = _CAPTION.search(text)
    # A year-end stock ("as at December 31, 2022") is filed as the annual
    # observation, as other countries' end-year stocks are.
    if cap.group(1) != "December" or cap.group(2) != "31":
        raise ValueError(f"MoFP South Sudan: not a year-end stock ({cap.group(0)})")
    period = cap.group(3)
    body = text[cap.end():text.find("Source:", cap.end())]
    # Values print as "424, 997,799,745.75" (a stray space) and labels wrap
    # ("...(Series" / "AX1-AX27)"); read amount + optional percent per row.
    found = re.findall(r"([\d][\d, ]*\.\d{2}|(?<![\d.])0(?![\d.]))\s*(\d+\.\d{2}%|0)?",
                       body.replace("%", "% "))
    amounts = [(_num(a), p) for a, p in found]
    if len(amounts) != len(_LABELS):
        raise ValueError(f"MoFP South Sudan: {len(amounts)} values for "
                         f"{len(_LABELS)} rows: {amounts}")
    *parts, (total, _) = amounts
    if abs(sum(a for a, _ in parts) - total) > 0.05:
        raise ValueError("MoFP South Sudan: rows do not sum to the TOTAL")
    rows = []
    for lab, (amt, pct) in zip(_LABELS, amounts):
        lab = "Total domestic debt" if lab == "TOTAL" else lab
        rows.append({"component": lab, "period": period, "frequency": "annual",
                     "measure": "stock", "value": amt, "unit": "SSP",
                     "series_code": "MoFP MTDS 2025 Table 3"})
        if pct and pct != "0":
            rows.append({"component": lab, "period": period, "frequency": "annual",
                         "measure": "share", "value": float(pct.rstrip("%")),
                         "unit": "percent", "series_code": "MoFP MTDS 2025 Table 3"})
    return pd.DataFrame(rows)
