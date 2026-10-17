"""Kenya — Central Bank of Kenya (CBK), Government Finance Statistics page:
the "Public Debt" and "Domestic Debt by Instrument" CSV downloads.

PUBLISHER: Central Bank of Kenya (an accepted official compiler under the
public-debt source policy; the National Treasury's annual and quarterly debt
reports carry the same aggregates).

TWO FILES, ONE PARSER -- each recognised by its own header line:

* "PUBLIC DEBT (shillings million)": Year | Month | Domestic Debt | External
  Debt | Total. Monthly from 1999-09 (quarterly-spaced until mid-2000, then
  every month). Components: Domestic debt, External debt, Total public debt.
* "Domestic Debt by Instrument (shillings million)": Treasury Bills (incl.
  Frozen Government Debt), Treasury Bonds, Government Stocks, Overdraft at
  Central Bank, Advances from Commercial Banks, Other Domestic Debt, Total
  Domestic Debt. Monthly from 1999-09.

COVERAGE: CBK labels the series "Public Debt" and "Domestic Debt" without
stating the perimeter -- recorded as such in the descriptors, not assumed.
Domestic debt is GROSS: from June 2023 it includes IMF funds on-lent by CBK to
Government (the file's own footnotes, carried in the docstring of the row
label below).

TRAPS:
* TWO DATE FORMATS IN ONE COLUMN. The instrument file labels months "Sep-99"
  up to 2023 and "24-Oct" (YY-Mon) after -- the second form read naively as
  day-month would date 2024 as the 24th of October. Both forms are parsed by
  shape, and every label must resolve or the parse raises.
* Numbers are quoted with thousands commas in the early rows and bare floats
  with full precision later ("7185210.646"); both are read as published.
* THE PAGE LINKS TWO "Domestic Debt by Instrument" FILES -- the current one
  (to 2026-08) and an older vintage (to 2026-06) whose "Other domestic debt"
  differs (94 507.6 vs 78 933.8 in 2026-04). Discovery takes the first link,
  which is the current file; merge-on-write means the newest file wins.

ONE NEGATIVE CELL, PINNED: "Other domestic debt" for 2006-08 prints
-575.961638. The line includes items in transit, so a negative net is
plausible as published -- but the schema refuses negative debt, so the cell is
NOT emitted (`_KNOWN_NEGATIVE`). It is re-checked every run: if CBK revises it
to a non-negative value the parse raises so the pin is removed deliberately,
and any OTHER negative cell raises too. The instrument sum check still uses it.

CHECKS: in the Public Debt file, Domestic + External = Total for every month
(to within 1 shilling-million: early rows are rounded); in the instrument file
the six instruments sum to the Total (within 1). A failure raises -- a parse
that cannot reproduce the publisher's own total is a misread.

CROSS-CHECK (KSh million): 1999-09 domestic 183 417.00, external 320 137.00,
total 503 554.00; 2026-06 total 13 097 471.11 (domestic 7 327 202.088);
2026-08 Treasury bonds 6 365 634.08, total domestic 7 676 024.025.
"""
from __future__ import annotations

import csv
import re

import pandas as pd

_UNIT = "KSh million"
_MON = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
     "nov", "dec"], 1)}


def _num(s: str) -> float | None:
    s = str(s).strip().replace(",", "")
    if not s or s in {"-", "–"}:
        return None
    return float(s)


def _month_label(lab: str) -> str:
    lab = lab.strip()
    m = re.fullmatch(r"([A-Za-z]{3})-(\d{2})", lab)          # Sep-99
    if m:
        mon, yy = _MON[m.group(1).lower()], int(m.group(2))
    else:
        m = re.fullmatch(r"(\d{2})-([A-Za-z]{3})", lab)      # 24-Oct
        if not m:
            raise ValueError(f"CBK: unreadable month label {lab!r}")
        mon, yy = _MON[m.group(2).lower()], int(m.group(1))
    year = 1900 + yy if yy >= 90 else 2000 + yy
    return f"{year}-{mon:02d}"


def _rows(path: str) -> list[list[str]]:
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        return list(csv.reader(f))


def _public_debt(rows) -> list[dict]:
    out = []
    for r in rows:
        if len(r) < 5 or not re.fullmatch(r"\d{4}", r[0].strip()):
            continue
        period = f"{int(r[0])}-{int(r[1]):02d}"
        dom, ext, tot = (_num(x) for x in r[2:5])
        if None in (dom, ext, tot):
            raise ValueError(f"CBK Public Debt {period}: missing cell {r}")
        if abs(dom + ext - tot) > 1:
            raise ValueError(f"CBK Public Debt {period}: {dom} + {ext} != {tot}")
        for comp, v in (("Domestic debt", dom), ("External debt", ext),
                        ("Total public debt", tot)):
            out.append({"component": comp, "period": period,
                        "frequency": "monthly", "measure": "stock",
                        "value": v, "unit": _UNIT,
                        "series_code": "CBK Public Debt"})
    return out


# (component, period) cells CBK prints negative; see the module docstring.
_KNOWN_NEGATIVE = {("Other domestic debt", "2006-08")}

_INSTR = ["Treasury bills (incl. frozen government debt)", "Treasury bonds",
          "Government stocks", "Overdraft at Central Bank",
          "Advances from commercial banks", "Other domestic debt",
          "Total domestic debt (gross)"]


def _domestic_by_instrument(rows) -> list[dict]:
    out = []
    for r in rows:
        if len(r) < 8 or not re.fullmatch(r"[A-Za-z]{3}-\d{2}|\d{2}-[A-Za-z]{3}",
                                          r[0].strip()):
            continue
        period = _month_label(r[0])
        vals = [_num(x) for x in r[1:8]]
        if None in vals:
            raise ValueError(f"CBK domestic by instrument {period}: {r}")
        if abs(sum(vals[:6]) - vals[6]) > 1:
            raise ValueError(f"CBK domestic by instrument {period}: instruments "
                             f"sum to {sum(vals[:6])}, total {vals[6]}")
        for comp, v in zip(_INSTR, vals):
            if (comp, period) in _KNOWN_NEGATIVE:
                if v >= 0:
                    raise ValueError(f"CBK {comp} {period} is now {v} -- remove "
                                     f"it from _KNOWN_NEGATIVE")
                continue
            if v < 0:
                raise ValueError(f"CBK {comp} {period}: new negative value {v}")
            out.append({"component": comp, "period": period,
                        "frequency": "monthly", "measure": "stock",
                        "value": v, "unit": _UNIT,
                        "series_code": "CBK Domestic Debt by Instrument"})
    return out


def _parse_one(path: str) -> list[dict]:
    rows = _rows(path)
    head = " ".join(",".join(r) for r in rows[:5]).lower()
    if "treasury bills" in head:
        got = _domestic_by_instrument(rows)
    elif "public debt" in head and "external debt" in head:
        got = _public_debt(rows)
    else:
        raise ValueError(f"CBK: unrecognised debt file {path!r}")
    if len(got) < 100:
        raise ValueError(f"CBK: only {len(got)} values read from {path!r}")
    return got


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        rows += _parse_one(p)
    return pd.DataFrame(rows)
