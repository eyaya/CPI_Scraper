"""Lesotho -- Central Bank of Lesotho, Quarterly Economic Review, table
"Public Debt Stock (Million Maloti)" (Table 17 in the Q4 2025 issue, Table 16
in Q4 2024 -- found by its title, not its number).

PUBLISHER: Central Bank of Lesotho; the table's source line is "Central Bank
of Lesotho and Ministry of Finance". COVERAGE: "Total Public Debt" as the
table states it, external + domestic, with a footnote in the review: "All
categories are on net terms. The stock of public external debt is converted
using an end-of-period exchange rate."

EACH ISSUE PRINTS FIVE QUARTERS (the latest and the four before), so the
current issue plus earlier issues as extras build the series, and history
accumulates on merge. Where two issues print the same quarter the NEWEST
issue wins -- CBL revises: 2023-Q4 total public debt is 24 387.00 in the Q4
2023 issue and 23 117.53 in the Q4 2024 one.

COLLECTED, as printed:
  * every level row for each of the five quarters -> `stock`, "LSL million"
    (maloti). Repeated child labels are qualified by their parent:
    "Multilateral Loans: Concessional", "Banks: Short-term (T-bills)",
    "Banks: Long-term: Treasury bonds";
  * the "Debt / GDP" column -> `share_of_gdp`, for the LATEST quarter only
    (that is all it covers);
  * DEBT INDICATORS: "Total Debt-to-GDP" -> `share_of_gdp` of Total Public
    Debt; "External Debt-to-Total Debt" -> `share` of External Debt;
    "Concessional Debt-to-External Debt" -> `share` named for its own
    denominator.
NOT COLLECTED: the Q-to-Q and Y-on-Y % columns (growth rates, which this
schema does not hold) and the external-debt-service ratios (flows).

LABEL TYPOGRAPHY ONLY is normalised -- "EXTERNAL DEBT" -> "External Debt",
"(t-bills)" -> "(T-bills)" -- because CBL capitalises the same heading
differently between issues and a series must not split on case. No label is
otherwise changed.

Each quarter is checked: external + domestic = total (to LSL 0.5 million).

CROSS-CHECK (Q4 2025 issue): total public debt 2025-Q4 22 480.80, external
17 881.43, domestic 4 599.37; total debt-to-GDP 52.9; multilateral
concessional 11 361.26.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_UNIT = "LSL million"
_TITLE = re.compile(r"Table \d+:\s*Public Debt Stock \(Million Maloti\)")
_NUM = r"-?\d+(?:\.\d+)?"
_L2 = {"external debt", "domestic debt"}
_L3 = {"bilateral loans", "multilateral loans", "financial institutions",
       "suppliers' credit", "banks", "non-bank"}
_UNDER_LONG = ("treasury bonds", "central bank")


def _typo(label: str) -> str:
    if label.isupper():
        label = label.title()
    return label.replace("(t-bills)", "(T-bills)").replace("(t-bonds)", "(T-bonds)")


def _quarters(lines):
    """The five column periods, from the years line and the Q1..Q4 line."""
    yi = next(i for i, ln in enumerate(lines) if re.match(r"^\s*20\d\d\s+20\d\d", ln))
    years = [int(y) for y in re.findall(r"20\d\d", lines[yi])]
    qs = [int(q) for q in re.findall(r"\bQ([1-4])\b", lines[yi + 1])][:5]
    if len(qs) != 5:
        raise ValueError(f"CBL: quarter header not read: {lines[yi + 1]!r}")
    year, out = years[0], []
    for k, q in enumerate(qs):
        if k and q < qs[k - 1]:
            year += 1
        out.append(f"{year}-Q{q}")
    if year != years[-1]:
        raise ValueError(f"CBL: quarters {out} do not end in {years[-1]}")
    return out, yi + 2


def _issue(path: str):
    with pdfplumber.open(path) as pdf:
        text = next((p.extract_text() or "" for p in pdf.pages
                     if _TITLE.search(p.extract_text() or "")
                     and "Total Public Debt" in (p.extract_text() or "")), None)
    if text is None:
        raise ValueError(f"CBL: no Public Debt Stock table in {path}")
    lines = text[_TITLE.search(text).end():].splitlines()
    periods, i0 = _quarters(lines)
    latest = periods[-1]
    recs, l3, l4, indicators = [], None, None, False
    for ln in lines[i0:]:
        s = ln.strip()
        if s.startswith("Source"):
            break
        if s.upper() == "DEBT INDICATORS":
            indicators = True
            continue
        m = re.match(rf"^(.*?[A-Za-z)'])\s+((?:{_NUM}\s+){{4}}{_NUM})(?:\s+(.*))?$", s)
        if not m:
            continue
        label, five = _typo(m.group(1).strip()), [float(v) for v in m.group(2).split()]
        tail = (m.group(3) or "").split()
        low = label.lower()
        if indicators:
            if low == "total debt-to-gdp":
                comp, meas = "Total Public Debt", "share_of_gdp"
            elif low == "external debt-to-total debt":
                comp, meas = "External Debt", "share"
            elif low == "concessional debt-to-external debt":
                comp, meas = "Concessional debt (share of external debt)", "share"
            else:
                continue                        # debt-service ratios: flows
            recs += [(comp, p, meas, v, "percent") for p, v in zip(periods, five)]
            continue
        if low == "total public debt" or low in _L2:
            comp, l3, l4 = label, None, None
        elif low in _L3:
            comp, l3, l4 = label, label, None
        elif l3 and low.startswith(_UNDER_LONG) and l4 and l4.lower().startswith("long-term"):
            comp = f"{l3}: {l4}: {label}"
        elif l3:
            comp, l4 = f"{l3}: {label}", label
        else:
            raise ValueError(f"CBL: row {label!r} has no parent")
        recs += [(comp, p, "stock", v, _UNIT) for p, v in zip(periods, five)]
        if len(tail) == 3 and re.fullmatch(_NUM, tail[2]):
            recs.append((comp, latest, "share_of_gdp", float(tail[2]), "percent"))
    return latest, recs


def parse(path: str, extras=None) -> pd.DataFrame:
    # The primary issue must parse; a BACK ISSUE whose table header differs
    # (the Q2 2024 review prints "Q-to- Y-on-Y Debt /" where the quarter row
    # should be) is skipped with a message, never misread.
    got = [_issue(path)]
    for p in extras or []:
        try:
            got.append(_issue(p))
        except ValueError as e:
            print(f"  [lesotho] back issue skipped ({p.replace(chr(92), '/').rsplit('/', 1)[-1]}): {e}")
    issues = sorted(got, key=lambda t: t[0])            # oldest first
    best = {}
    for latest, recs in issues:                          # newer issues overwrite
        mine = {}
        for comp, period, meas, val, unit in recs:
            k = (comp, period, meas, unit)
            # Within ONE issue a cell may be printed twice (total debt-to-GDP
            # in the Debt/GDP column and in the indicators block): it must
            # agree with itself.
            if k in mine and abs(mine[k] - val) > 0.05:
                raise ValueError(f"CBL {latest} issue prints {k} twice: "
                                 f"{mine[k]} vs {val}")
            mine[k] = val
        best.update(mine)
    df = pd.DataFrame([{"component": c, "period": p, "frequency": "quarterly",
                        "measure": m, "value": v, "unit": u,
                        "series_code": "CBL QER Public Debt Stock"}
                       for (c, p, m, u), v in best.items()])
    lv = df[df.measure == "stock"].pivot_table(index="period", columns="component",
                                               values="value")
    gap = (lv["External Debt"] + lv["Domestic Debt"] - lv["Total Public Debt"]).abs()
    if (gap > 0.5).any():
        raise ValueError(f"CBL: external + domestic != total in "
                         f"{list(gap[gap > 0.5].index)}")
    return df
