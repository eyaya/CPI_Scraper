"""Eswatini -- Central Bank of Eswatini, Quarterly Review, section 6.3
"Total Public Debt": Table 4 "Public Debt Portfolio by Proportion
(E'Billion)" and Table 5 "Public Domestic Debt Portfolio (E'Million)".

PUBLISHER: Central Bank of Eswatini. Table 4's source line reads "Central
Bank of Eswatini, Ministry of Finance & MAC DSA IMF & World Bank" -- the debt
STOCKS are CBE/MoF figures; the DSA thresholds printed beside them (the
"Critical Ratios" 50 and 10) and "Gross Financing Needs % of GDP" come from
the IMF-World Bank framework and are NOT collected (aggregator-derived, and
not debt stocks). Table 5 is sourced to CBE alone. COVERAGE: "Total public
debt" (domestic + external) as Table 4 states it; Table 5 is the domestic
portfolio of that total.

EACH ISSUE PRINTS THREE POINTS (e.g. Jun'25, Mar'26, Jun'26) at quarter
ends, dated to their calendar quarters. The current issue plus earlier issues
as extras build the series; where two issues print the same quarter the
NEWEST wins (CBE revises: March 2026 total debt is 40.6% of GDP in the March
issue, 40.7% in June's).

COLLECTED, as printed:
  * Table 4: total, domestic and external debt -> `stock` ("SZL billion"),
    and each "% to GDP" -> `share_of_gdp`;
  * Table 5: treasury bonds, treasury bills, CBE advance, domestic loans and
    total domestic debt -> `stock` ("SZL million"); each instrument's percent
    -> `share`, named for its denominator ("... (share of total domestic
    debt)"); "As % GDP" -> `share_of_gdp` of Total Domestic Debt.

A PUBLISHED INCONSISTENCY, KEPT: Table 4's "Domestic debt % to GDP" and
Table 5's "As % GDP" disagree within one issue (March 2026: 22.3 vs 20.42).
They are different printed rows and stay apart as different components
("Domestic debt" vs "Total Domestic Debt").

NOT COLLECTED: the external-debt annex (Table 7.6, "Total Public External
Debt (E'000)") is printed ROTATED and its text layer comes out
character-reversed with an interleaved row order that does not reconcile
under any reading this parser could verify (central government + parastatal
does not equal the printed total) -- refused rather than guessed.

Each issue is checked: domestic + external = total (to E0.15 billion, the
table's own rounding) -- except June 2025, pinned: 20.6 + 17.9 = 38.5 against
a printed 38.2, and Table 5's instruments sum to its total (to E2
million).

CROSS-CHECK (June 2026 issue): total public debt Jun'26 42.5 (E bn), 40.8% of
GDP; domestic 22.0, external 20.5; Table 5 total domestic 21 677, treasury
bonds 13 869 (64.0%).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_Q = {"mar": 1, "jun": 2, "sep": 3, "dec": 4}
_T4_ROWS = {
    "total public debt e' billion": ("Total public debt", "stock", "SZL billion"),
    "domestic debt e' billion": ("Domestic debt", "stock", "SZL billion"),
    "external debt e' billion": ("External debt", "stock", "SZL billion"),
    "total public debt % to gdp": ("Total public debt", "share_of_gdp", "percent"),
    "domestic debt % to gdp": ("Domestic debt", "share_of_gdp", "percent"),
    "external debt % to gdp": ("External debt", "share_of_gdp", "percent"),
}
# Quarters whose printed domestic + external does not reach the printed total,
# kept as published. June 2025 (June 2026 issue): 20.6 + 17.9 = 38.5 against
# a total of 38.2. Listed so a correction is noticed.
_KNOWN_T4_GAP = {"2025-Q2"}
_T5_ITEMS = ["Treasury Bonds", "Treasury Bills", "CBE Advance", "Domestic Loans",
             "Total Domestic Debt"]


def _clean(s: str) -> str:
    # The June 2026 issue sets text with '.' as word spacing ("Domestic.Loans").
    return re.sub(r"(?<=[A-Za-z])\.(?=[A-Za-z])", " ", s).replace("’", "'").strip()


def _periods(line: str):
    """Quarter-end headers: "Jun'25 Mar'26 Jun'26" or "Mar 2025 Dec 2025 Mar 2026"."""
    out = []
    for mon, yr in re.findall(r"\b(Mar|Jun|Sep|Dec)[a-z]*\s*'?\s*(\d{4}|\d{2})\b", line):
        y = int(yr) + (2000 if len(yr) == 2 else 0)
        out.append(f"{y}-Q{_Q[mon.lower()]}")
    return out


def _issue(path: str):
    with pdfplumber.open(path) as pdf:
        text = next((p.extract_text() or "" for p in pdf.pages
                     if "PUBLIC DEBT PORTFOLIO BY PROPORTION" in (p.extract_text() or "")
                     and "Total Public Debt E" in (p.extract_text() or "")), None)
    if text is None:
        raise ValueError(f"CBE: no Table 4 in {path}")
    lines = [_clean(ln) for ln in text.splitlines()]
    recs = []

    # ---- Table 4
    i4 = next(i for i, ln in enumerate(lines) if ln.startswith("Category"))
    p4 = _periods(lines[i4])
    if len(p4) != 3:
        raise ValueError(f"CBE T4: header {lines[i4]!r}")
    for ln in lines[i4 + 1:]:
        if ln.lower().startswith("source"):
            break
        m = re.match(r"^(.*?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(?:\s+\d+)?$", ln)
        if not m:
            continue
        key = re.sub(r"\s+", " ", m.group(1)).lower()
        if key not in _T4_ROWS:
            continue                       # gross financing needs, thresholds
        comp, meas, unit = _T4_ROWS[key]
        for p, v in zip(p4, m.group(2, 3, 4)):
            recs.append((comp, p, meas, float(v), unit, "CBE QR T4"))

    # ---- Table 5
    i5 = next(i for i, ln in enumerate(lines) if ln.startswith("Type of Debt"))
    p5 = _periods(lines[i5])
    if len(p5) != 3:
        raise ValueError(f"CBE T5: header {lines[i5]!r}")
    for ln in lines[i5 + 1:]:
        if ln.lower().startswith("source"):
            break
        m = re.match(r"^(As % GDP)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)$", ln)
        if m:
            for p, v in zip(p5, m.group(2, 3, 4)):
                recs.append(("Total Domestic Debt", p, "share_of_gdp", float(v),
                             "percent", "CBE QR T5"))
            continue
        m = re.match(r"^(.*?)\s+((?:[\d,]+\s+[\d.]+%\s*){3})$", ln)
        if not m or m.group(1) not in _T5_ITEMS:
            continue
        pairs = re.findall(r"([\d,]+)\s+([\d.]+)%", m.group(2))
        for p, (lvl, pct) in zip(p5, pairs):
            recs.append((m.group(1), p, "stock", float(lvl.replace(",", "")),
                         "SZL million", "CBE QR T5"))
            if m.group(1) != "Total Domestic Debt":
                recs.append((f"{m.group(1)} (share of total domestic debt)", p,
                             "share", float(pct), "percent", "CBE QR T5"))
    latest = max(p4 + p5)
    return latest, recs


def parse(path: str, extras=None) -> pd.DataFrame:
    # The primary issue must parse; a BACK ISSUE whose tables differ (Dec 2025
    # and Q4 2022 carry no matching Table 4; Jun 2025's layout differs) is
    # skipped with a message, never misread.
    got = [_issue(path)]
    for p in extras or []:
        try:
            got.append(_issue(p))
        except (ValueError, IndexError, KeyError) as e:
            print(f"  [eswatini] back issue skipped ({p.replace(chr(92), '/').rsplit('/', 1)[-1]}): {type(e).__name__} {e}")
    issues = sorted(got, key=lambda t: t[0])
    best = {}
    for latest, recs in issues:                       # newer issues overwrite
        for comp, p, meas, v, unit, code in recs:
            best[(comp, p, meas, unit, code)] = v
    df = pd.DataFrame([{"component": c, "period": p, "frequency": "quarterly",
                        "measure": m, "value": v, "unit": u, "series_code": code}
                       for (c, p, m, u, code), v in best.items()])

    s4 = df[(df.series_code == "CBE QR T4") & (df.measure == "stock")].pivot_table(
        index="period", columns="component", values="value")
    gap = (s4["Domestic debt"] + s4["External debt"] - s4["Total public debt"]).abs()
    bad = set(gap[gap > 0.15].index)
    if bad - _KNOWN_T4_GAP:
        raise ValueError(f"CBE T4: domestic + external != total in {sorted(bad - _KNOWN_T4_GAP)}")
    healed = {p for p in _KNOWN_T4_GAP if p in gap.index and p not in bad}
    if healed:
        raise ValueError(f"CBE T4: pinned gap in {sorted(healed)} now adds up -- "
                         f"CBE revised it; drop it from _KNOWN_T4_GAP")
    s5 = df[(df.series_code == "CBE QR T5") & (df.measure == "stock")].pivot_table(
        index="period", columns="component", values="value")
    parts = s5[[c for c in _T5_ITEMS if c != "Total Domestic Debt"]].sum(axis=1)
    gap5 = (parts - s5["Total Domestic Debt"]).abs()
    if (gap5 > 2).any():
        raise ValueError(f"CBE T5: instruments != total in {list(gap5[gap5 > 2].index)}")
    return df
