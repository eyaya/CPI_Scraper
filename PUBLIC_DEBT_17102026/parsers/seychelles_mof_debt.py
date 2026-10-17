"""Seychelles — Ministry of Finance, National Planning & Trade (Debt Management
Division), Quarterly Debt Bulletin, Q1 2021 - Q4 2024 (16 issues).

PUBLISHER and COVERAGE: the MoF's own bulletin, finance.gov.sc "Debt
Management" page. "Total Debt" is GOVERNMENT debt plus government-GUARANTEED
debt (Table 2 splits it exactly that way), domestic and external.

FIVE TABLES PER ISSUE, each printing the previous and the current quarter
(SCR million) and a "% Diff" column, which is a computed change and is NOT
collected:

* Table 1  by residency of creditor: Domestic / External, each "o.w.
           Government" and "o.w. Guarantees", and Total Debt -- plus the
           current quarter's % of GDP (measure share_of_gdp)
* Table 2  by guarantee status: Government / Guarantees (Total = Table 1's)
* Table 3  EXTERNAL debt by creditor category: Multilateral, Bilateral (o.w.
           Paris Club, Non-Paris Club), Commercial Banks, Private
* Table 4  EXTERNAL debt by instrument: Loans, Securities
* Table 5  DOMESTIC debt by instrument: Loans, Securities (of which T-bills,
           T-bonds, Deposits, Others), Other Debt Liabilities

Component labels carry their table's side ("External: Multilateral",
"Domestic: T-bills") because the same words recur across tables. Each
table's printed Total is checked against Table 1 (to rounding) and not
emitted twice.

TABLE 3 SITS BESIDE A PIE CHART whose legend ("Multilateral 82%", "Banks
2%") interleaves with the table's rows in the text layer; that page is read
CROPPED to its left 55%, where only the table is. "Commercial / Banks" wraps
around its numbers and is rejoined.

A QUARTER APPEARS IN TWO ISSUES (as "current" in one, "previous" in the
next). The NEWER issue's figure is kept -- the same rule merge-on-write
applies between runs -- and the parse counts how many such revisions there
were.

The page lists the bulletins alphabetically, not by date, so the descriptor
discovers the newest by the quarter in its file name (`wp_media_latest_quarter`)
and passes every earlier bulletin as an extra. From 2025 Table 3 no longer sits
beside a pie chart (the left-half crop is used only when the caption survives
it) and the bilateral parent row prints "o. w." -- both handled.

ONE PUBLISHED MISPRINT is pinned (`_KNOWN_BAD_TOTALS`): Q1 2024's Table 2
Total (17,873) against its own parts and Table 1 (17,918).

CROSS-CHECK: Q4 2024 total debt SCR 18,885m (60.8% of GDP), domestic 9,281,
external 9,604, multilateral 7,829; Q1 2021 total 20,024 (89.5% of GDP).
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

_UNIT = "SCR million"
_HDR = re.compile(r"Q([1-4])\s+(20\d\d)\s+Q([1-4])\s+(20\d\d)")
_ROW = re.compile(r"^(?P<label>[A-Za-z][A-Za-z .;,'’\-]*?)\s+(?P<a>\d[\d,]*)\s+"
                  r"(?P<b>\d[\d,]*)\s+(?P<d>-?\d+(?:\.\d+)?)(?:\s+(?P<g>\d+(?:\.\d+)?))?\s*$")
_NUMS = re.compile(r"^(?P<a>\d[\d,]*)\s+(?P<b>\d[\d,]*)\s+(?P<d>-?\d+(?:\.\d+)?)$")
# PUBLISHED MISPRINTS, pinned: (issue's current quarter, table) -> (printed
# total, the figure its own parts and Table 1 give). Q1 2024 Table 2 prints
# Total Debt 17,873; Government 17,206 + Guarantees 712 = 17,918 = Table 1.
# The components are consistent, so they are kept; only the printed total
# (never emitted anyway) is wrong. Any OTHER mismatch still raises.
_KNOWN_BAD_TOTALS = {("2024-Q1", "2"): (17873.0, 17918.0)}
_PREFIX = {"1": "", "2": "", "3": "External: ", "4": "External: ", "5": "Domestic: "}
# TABLES ARE FOUND BY CAPTION, NOT NUMBER: Q4 2021 inserts an extra table, so
# "External Debt by Instrument Type" is Table 5 there and Table 4 elsewhere.
# The keys "1".."5" below are this module's own names for the five tables.
_CAPS = {"1": r"Total Debt by residency", "2": r"by Guarantee Status",
         "3": r"by Creditor Category", "4": r"External Debt by Instrument",
         "5": r"Domestic Debt by Instrument"}


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _label(t: str, raw: str, side: str) -> str:
    lab = re.sub(r"\s+", " ", raw).strip()
    # A trailing "o.w." ("of which") flags a parent row; 2025+ bulletins
    # print it "o. w." -- both forms are stripped so the series stays one.
    lab = re.sub(r"\s*(o\.\s?w\.|of which;?)\s*$", "", lab, flags=re.I).strip()
    if t == "1" and lab.startswith("o.w."):
        return f"{side} {lab}"                       # "Domestic o.w. Government"
    if t == "2":
        return {"Government": "Government debt (domestic + external)",
                "Guarantees": "Government-guaranteed debt (domestic + external)"}.get(lab, lab)
    if t == "3" and lab in ("Paris Club", "Non-Paris Club"):
        return f"External: Bilateral - {lab}"
    return f"{_PREFIX[t]}{lab}"


def _caption(text: str, t: str):
    return re.search(rf"^Table \d+:.*{_CAPS[t]}.*$", text, re.M | re.I)


def _table(text: str, t: str):
    m = _caption(text, t)
    if not m:
        raise ValueError(f"Seychelles bulletin: table '{_CAPS[t]}' not found")
    body = text[m.end():]
    end = body.find("Source:")
    return body[:end if end >= 0 else None].splitlines()


def _parse_issue(path: str):
    with pdfplumber.open(path) as pdf:
        full = "\n".join(p.extract_text() or "" for p in pdf.pages)
        # Table 3 sat beside a pie chart whose legend interleaves with it, so
        # the page is cropped to its left 55%. From 2025 the table stands
        # alone and the crop would cut its caption and rows: the cropped text
        # is used only when the caption survives it.
        page3 = next(p for p in pdf.pages if _caption(p.extract_text() or "", "3"))
        cropped = page3.crop((0, 0, page3.width * 0.55, page3.height)).extract_text() or ""
        t3 = cropped if _caption(cropped, "3") else page3.extract_text()
    h = _HDR.search(full[_caption(full, "1").start():])
    prev, curr = f"{h.group(2)}-Q{h.group(1)}", f"{h.group(4)}-Q{h.group(3)}"
    rows, totals = {}, {}
    for t in "12345":
        side, pending = "", None
        for ln in _table(t3 if t == "3" else full, t):
            s = ln.strip()
            n = _NUMS.match(s)
            if n and pending:                         # "Commercial" / nums / "Banks"
                m, label = n, pending + " Banks"
                pending = None
            else:
                m = _ROW.match(s)
                if not m:
                    if t == "3" and s == "Commercial":
                        pending = "Commercial"
                    continue
                label = m.group("label")
            lab = re.sub(r"\s+", " ", label).strip()
            if t == "1" and lab in ("Domestic", "External"):
                side = lab
            a, b = _num(m.group("a")), _num(m.group("b"))
            if lab.lower().startswith("total"):
                totals[t] = b
                if t != "1":
                    continue
            comp = _label(t, lab, side)
            rows[(comp, prev, "stock")] = a
            rows[(comp, curr, "stock")] = b
            if t == "1" and m.group("g"):
                rows[(comp, curr, "share_of_gdp")] = float(m.group("g"))
    # Each breakdown's Total must equal Table 1's corresponding figure.
    t1 = {c: v for (c, p, ms), v in rows.items() if p == curr and ms == "stock"}
    for t, want in (("2", t1.get("Total Debt")), ("3", t1.get("External")),
                    ("4", t1.get("External")), ("5", t1.get("Domestic"))):
        if (curr, t) in _KNOWN_BAD_TOTALS:
            if (totals.get(t), want) != _KNOWN_BAD_TOTALS[(curr, t)]:
                raise ValueError(f"Seychelles {curr} Table {t}: the pinned misprint "
                                 f"changed -- re-check and update _KNOWN_BAD_TOTALS")
            continue
        if t in totals and want is not None and abs(totals[t] - want) > 2:
            raise ValueError(f"Seychelles {os.path.basename(path)}: Table {t} "
                             f"total {totals[t]} vs Table 1 {want}")
    if abs(t1["Domestic"] + t1["External"] - t1["Total Debt"]) > 2:
        raise ValueError(f"Seychelles {os.path.basename(path)}: Table 1 does not add up")
    return curr, rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    issues = sorted((_parse_issue(p) for p in [path, *(extras or [])]),
                    key=lambda x: x[0])
    merged, revised = {}, 0
    for _, rows in issues:                            # oldest first: newer issue wins
        for k, v in rows.items():
            if k in merged and merged[k] != v:
                revised += 1
            merged[k] = v
    out = [{"component": c, "period": p, "frequency": "quarterly", "measure": ms,
            "value": v, "unit": "percent" if ms == "share_of_gdp" else _UNIT,
            "series_code": "MoF Quarterly Debt Bulletin"}
           for (c, p, ms), v in merged.items()]
    if revised:
        print(f"[seychelles] {revised} figure(s) revised by a later bulletin -- newest kept")
    return pd.DataFrame(out)
