"""Liberia -- Ministry of Finance and Development Planning (MFDP), Debt
Management Unit, "Quarterly Public Debt Management Report"
(mfdp.gov.lr; files under /edocman/).

PUBLISHER: the MFDP Debt Management Unit -- an accepted official national
compiler under this indicator's source policy.

COVERAGE: public and publicly guaranteed (PPG) debt of the Government of
Liberia, as the report titles it ("STOCK OF PUBLIC & PUBLICLY GUARANTEED (PPG)
DEBT"). SOE contingent liabilities, which the report lists separately, are not
part of the stock and are not read.

TABLE READ: "Public Debt Stock by Creditors/Holders (Millions USD)" -- four
quarters per report (e.g. Q2 2025 .. Q1 2026), US$ million. Rows are read
in their two sections and named with them ("Domestic: CBL", "External:
Multilateral") because a label alone can repeat. The table is hierarchical
and its sub-items are emitted as printed:
  Domestic = CBL + Commercial Banks + Other Institutions + Claims (Court &
             Non Court Debt); Commercial Banks = Promissory Note + Treasury
             Bills + Treasury Bonds;
  External = Multilateral + Bilateral + Commercial Debt (Bank Leumi);
  Total Debt Stock = Domestic + External.
The parser checks those identities (to rounding) and reports any break; a
break is the publisher's, and the figures are kept as printed. "-" is an
empty cell, never zero.

LETTER-SPACED DIGITS: some issues (Q4 2025) split a number after its first
digit ("1 ,076.70", "7 35.96"); since every value carries two decimals, such a
split is rejoined before reading.

PUBLISHED INCONSISTENCY KEPT: the Q2 2025 report's Total Debt Stock for
2025-Q2 (2,685.23) is not Domestic + External (2,683.22); later reports
revise that quarter (2,691.00), and the newest report's figures win.

DATING: the report's own column headers ("Q2 2025 Q3 2025 Q4 2025 Q1 2026");
the fiscal year is the calendar year since FY2025. Where reports overlap,
the NEWEST report's figure wins.

NOT READ: debt service, disbursements, contingent liabilities, risk
indicators (debt-to-GDP appears there in prose and in a risk table, not as a
stock table).

CROSS-CHECK (printed, Q1 2026 report): total debt stock US$2,833.48m
(Q1 2026), 2,824.36m (Q4 2025); external 1,649.99m; domestic 1,183.49m;
CBL 726.91m.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

SERIES = "MFDP DMU public debt stock by creditors/holders"
_NUM = r"\d[\d,]*\.\d+|-"
_SECTIONS = {"domestic": "Domestic", "external": "External"}


def _parse_one(path: str) -> list[dict]:
    where = os.path.basename(path)
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    caps = [m for m in re.finditer(r"Table\s*\d+\s*:\s*Public Debt Stock by Creditors\s*/?\s*Holders",
                                   text, re.I)]
    # The list of tables carries the caption too, followed by dot leaders.
    caps = [m for m in caps if not re.match(r"[^\n]*\.{4}", text[m.end():])]
    if not caps:
        print(f"[liberia_mfdp] {where}: no 'Public Debt Stock by Creditors/Holders' table -- skipped")
        return []
    body = text[caps[0].end():].split("Source", 1)[0]
    # Some issues letter-space their numbers ("1 ,076.70", "7 35.96", "2 7.95").
    # Every value here carries two decimals, so a lone digit followed by
    # digits-with-decimals is a split value, never two values: rejoin it.
    lines = [re.sub(r"(?<![\d.])(\d) (?=,?\d+\.\d{2}\b)", r"\1", ln.strip())
             for ln in body.splitlines() if ln.strip()]
    hdr = next((ln for ln in lines if re.search(r"Q[1-4]\s+20\d\d.*Q[1-4]\s+20\d\d", ln)), None)
    if hdr is None:
        raise ValueError(f"{where}: no quarter header in the stock table")
    quarters = [f"{y}-Q{q}" for q, y in re.findall(r"Q([1-4])\s+(20\d\d)", hdr)]

    recs, section = [], None
    for ln in lines:
        m = re.match(rf"^(.+?)((?:\s+(?:{_NUM})){{{len(quarters)}}})\s*$", ln)
        if not m:
            continue
        label = m.group(1).strip()
        vals = m.group(2).split()
        low = label.lower()
        if low in _SECTIONS:
            section = _SECTIONS[low]
            comp = section
        elif low.startswith("total debt stock"):
            comp, section = "Total Debt Stock", None
        else:
            if section is None:
                raise ValueError(f"{where}: row {label!r} outside any section")
            comp = f"{section}: {label}"
        for q, v in zip(quarters, vals):
            if v == "-":
                continue
            recs.append(dict(component=comp, period=q, frequency="quarterly",
                             measure="stock", value=float(v.replace(",", "")),
                             unit="USD million", series_code=SERIES))
    if not any(r["component"] == "Total Debt Stock" for r in recs):
        print(f"[liberia_mfdp] {where}: stock table read no Total Debt Stock row -- skipped")
        return []
    _check(recs, where)
    return recs


def _check(recs: list[dict], where: str) -> None:
    by = {}
    for r in recs:
        by.setdefault(r["period"], {})[r["component"]] = r["value"]
    for q, v in by.items():
        tests = [("Total Debt Stock", ["Domestic", "External"])]
        for tot, parts in tests:
            if tot in v and all(p in v for p in parts):
                if abs(v[tot] - sum(v[p] for p in parts)) > 0.05:
                    print(f"[liberia_mfdp] {where} {q}: {tot} {v[tot]} != "
                          f"sum of {parts} -- kept as published")


def _report_key(path: str) -> tuple:
    """Order reports by the last quarter their table covers (read from the
    file name): newest last, so it wins on overlap."""
    n = os.path.basename(path).lower()
    y = re.findall(r"(20\d\d)", n)
    q = re.search(r"(1st|2nd|3rd|4th|first|second|third|fourth)", n)
    qn = {"1st": 1, "first": 1, "2nd": 2, "second": 2, "3rd": 3, "third": 3,
          "4th": 4, "fourth": 4}.get(q.group(1) if q else "", 0)
    return (int(y[-1]) if y else 0, qn, n)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in sorted(extras or [], key=_report_key) + [path]:
        got = _parse_one(p)
        if p == path and not got:
            raise ValueError("liberia_mfdp: the current report has no stock table")
        rows += got
    df = pd.DataFrame(rows)
    key = ["component", "period", "frequency", "measure", "unit", "series_code"]
    return df.drop_duplicates(key, keep="last").reset_index(drop=True)
