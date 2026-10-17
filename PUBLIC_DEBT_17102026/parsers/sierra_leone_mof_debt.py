"""Sierra Leone -- Ministry of Finance, Public Debt Management Division (PDMD),
"Updated Public Debt Stock and New Debt" workbook (mof.gov.sl, WordPress
upload; latest seen: ..._June-2026.xlsx).

PUBLISHER: the Ministry of Finance (PDMD) -- an accepted official national
compiler under this indicator's source policy.

TWO SHEETS ARE READ:

* "Public_Debt_Stock" -- end-year domestic debt, external debt (NLe million
  and US$ million) and total public debt, 2021 onward. ONLY THE COLUMNS
  FLAGGED "Actual" ARE TAKEN; the ministry's own projections (2026-2029 in
  the June 2026 edition) are not data. The flag row is read, not assumed: the
  sheet's two blocks disagree on whether 2025 is "Actual" or "Projection"
  (first block Actual, second block Projection); the FIRST block is read and
  a 2025 column is taken only where that block calls it Actual.
* "Domestic Debt FY<year>" -- stock of domestic debt by HOLDER (Bank of
  Sierra Leone, commercial banks, non-bank public) and instrument (treasury
  bills by tenor, treasury bonds by tenor) plus domestic arrears, for the two
  year-ends the sheet prints, NLe million, with each line's percent of total
  for the latest year. The table states it EXCLUDES zero-coupon bonds and Ways
  and Means advances; its rows carry that perimeter as their `coverage`.
  The table's total (31,736.48 at end-2025) plus zero-coupon bonds (1,096.18)
  and Ways and Means (600.66) equals Public_Debt_Stock's domestic debt
  (33,433.31) -- the two sheets reconcile.

* "Public Debt Stock <year>" (ANNEX 15, added 2026-10-14) -- the BACK
  SERIES ONLY: columns 2007, 2010, 2012, FY2016-FY2019 and FY2020 (FY2021
  onward is read from Public_Debt_Stock above). Its title says "In Million
  New Leones", but the columns up to FY2019 are in OLD leones: every row
  breaks by a factor of about 1,000 between FY2019 and FY2020 (total
  25,411,235.63 -> 30,263.88; 5-year bond 939,595.49 -> 810.98) -- the 2022
  redenomination (1 NLe = 1,000 old Le) applied from FY2020 on. The unit is
  therefore set PER COLUMN: "SLL million (pre-2022 leone)" to FY2019, "NLe
  million" for FY2020, never converted; the break is checked on every row
  that prints both years, so a sheet revised to one unit raises rather than
  being mislabelled. Rows: total domestic debt and its instruments, total
  external debt and its creditor groups, total debt stock; series code
  "PDMD Annex 15" keeps them apart from the Public_Debt_Stock rows.

NOT READ: Annex 15's FY2021+ columns (two unlabelled FY2022/FY2023 columns,
end-June vs end-December) and its share / % change columns; the
external-debt-by-creditor sheet (a two-row header whose quarter labels do not
line up with its values); the GDP-ratio rows of Public_Debt_Stock (7 values
under 9 year columns -- not alignable); the "flow / new borrowing" column;
loan terms.

CROSS-CHECK (printed): total public debt end-2021 34,618.84, end-2024
69,866.75 NLe million; external debt end-2024 US$1,829.76 million; domestic
debt end-2025 by holder: commercial banks 18,614.43 (58.65%).
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd

SERIES = "PDMD public debt stock"


def _stock_sheet(wb) -> list[dict]:
    ws = wb["Public_Debt_Stock"]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    yr_i = next(i for i, r in enumerate(rows)
                if any(isinstance(v, str) and re.match(r"End[\s-]*20\d\d", v) for v in r))
    years = rows[yr_i]
    flags = rows[yr_i + 1]
    cols = []
    for j, v in enumerate(years):
        if isinstance(v, str) and (m := re.match(r"End[\s-]*(20\d\d)", v)):
            if str(flags[j] or "").strip().lower() == "actual":
                cols.append((j, m.group(1)))
    if not cols:
        raise ValueError("SL Public_Debt_Stock: no Actual columns")
    want = {
        "Domestic Debts (A)": ("Domestic debt", "NLe million"),
        "External Debts (B)": ("External debt", "NLe million"),
        "External Debts (in millions of US$)": ("External debt", "USD million"),
        "Total Public Debt": ("Total public debt", "NLe million"),
    }
    out, seen = [], set()
    for r in rows[yr_i + 2:]:
        lab = next((str(v).strip() for v in r if isinstance(v, str) and v.strip()), "")
        if lab.startswith("Source"):
            break                          # the first block ends at its source line
        if lab not in want or lab in seen:
            continue
        seen.add(lab)
        comp, unit = want[lab]
        for j, y in cols:
            v = r[j]
            if isinstance(v, (int, float)):
                out.append(dict(component=comp, period=y, frequency="annual",
                                measure="stock", value=float(v), unit=unit,
                                series_code=SERIES))
    if seen != set(want):
        raise ValueError(f"SL Public_Debt_Stock: rows missing {set(want) - seen}")
    return out


def _domestic_sheet(wb) -> list[dict]:
    name = next((n for n in wb.sheetnames if n.lower().startswith("domestic debt")), None)
    if name is None:
        raise ValueError("SL: no 'Domestic Debt FY...' sheet")
    ws = wb[name]
    rows = [list(r) for r in ws.iter_rows(values_only=True)
            if any(v not in (None, "") for v in r)]
    # Drop leading empty columns so the label sits in column 0.
    lead = min(next(j for j, v in enumerate(r) if v not in (None, "")) for r in rows)
    rows = [r[lead:] for r in rows]
    title = next(str(v) for v in rows[0] if isinstance(v, str))
    if "excluding zero-coupon bonds and ways and means" not in " ".join(title.lower().split()):
        raise ValueError(f"SL {name}: perimeter note changed: {title!r}")
    coverage = ("Central government domestic debt, excluding zero-coupon bonds "
                "and Ways and Means advances (PDMD table)")
    hdr = rows[1]
    dates = [(j, v.year) for j, v in enumerate(hdr) if hasattr(v, "year")]
    pct_j = next(j for j, v in enumerate(hdr) if isinstance(v, str) and "percent of total" in v.lower())
    pct_year = re.search(r"(20\d\d)", hdr[pct_j]).group(1)
    out, holder, instr = [], "", ""
    for r in rows[2:]:
        lab = str(r[0] or "").strip()
        if not lab:
            continue
        lab = re.sub(r"\s+", " ", lab)
        if lab.lower().startswith("total"):
            comp = "Total domestic debt"
            end = True
        else:
            end = False
            if lab.lower().startswith("net claims on government"):
                holder, instr = lab, ""
                comp = holder
            elif lab in ("Treasury Bills", "Treasury Bonds"):
                instr = lab
                comp = f"{holder}: {instr}"
            elif lab == "Domestic Arrears":
                holder, instr = "", ""
                comp = lab
            else:
                comp = f"{holder}: {instr}: {lab}" if instr else f"{holder}: {lab}"
        for j, y in dates:
            v = r[j] if j < len(r) else None
            if isinstance(v, (int, float)):
                out.append(dict(component=comp, period=str(y), frequency="annual",
                                measure="stock", value=float(v), unit="NLe million",
                                series_code=SERIES + " (domestic, by holder)",
                                coverage=coverage))
        v = r[pct_j] if pct_j < len(r) else None
        if isinstance(v, (int, float)) and not end:
            out.append(dict(component=comp, period=pct_year, frequency="annual",
                            measure="share", value=float(v), unit="percent",
                            series_code=SERIES + " (domestic, by holder)",
                            coverage=coverage))
        if end:
            break                          # the summary block below regroups the same debt
    return out


_OLD_UNIT, _NEW_UNIT = "SLL million (pre-2022 leone)", "NLe million"
_ANNEX_COLS = {"2007": "2007", "2010": "2010", "2012": "2012", "FY2016": "2016",
               "FY2017": "2017", "FY2018": "2018", "FY2019": "2019",
               "FY2020": "2020"}


def _annex_sheet(wb) -> list[dict]:
    name = next((n for n in wb.sheetnames
                 if re.fullmatch(r"Public Debt Stock \d{4}", n.strip())), None)
    if name is None:
        raise ValueError("SL: no 'Public Debt Stock <year>' (Annex 15) sheet")
    rows = [list(r) for r in wb[name].iter_rows(values_only=True)]
    hdr_i = next(i for i, r in enumerate(rows)
                 if any(str(c).strip() == "Debt Type" for c in r if c is not None))
    cols = {}
    for j, c in enumerate(rows[hdr_i]):
        k = str(c).strip() if c is not None else ""
        if k in _ANNEX_COLS and k not in cols:
            cols[k] = j
    if set(cols) != set(_ANNEX_COLS):
        raise ValueError(f"SL Annex 15: year columns {sorted(cols)}")
    section, table, out = None, {}, []
    for r in rows[hdr_i + 1:]:
        lab = str(r[1]).strip() if len(r) > 1 and r[1] is not None else ""
        if not lab or lab.startswith("Source"):
            if lab.startswith("Source"):
                break
            continue
        if lab == "Total Domestic Debt":
            section, comp = "Domestic", lab
        elif lab.startswith("Total External Debt"):
            section, comp = "External", lab
        elif lab == "Total Debt Stock":
            section, comp = None, lab
        elif section:
            comp = f"{section}: {lab}"
        else:
            continue
        vals = {k: r[j] for k, j in cols.items()
                if isinstance(r[j], (int, float))}
        table[comp] = vals
        o, n = vals.get("FY2019"), vals.get("FY2020")
        if o and n and not 200 < o / n < 5000:
            raise ValueError(f"SL Annex 15 {comp}: FY2019/FY2020 = {o}/{n} -- "
                             f"not the old/new leone break")
        for k, v in vals.items():
            out.append({"component": comp, "period": _ANNEX_COLS[k],
                        "frequency": "annual", "measure": "stock",
                        "value": float(v),
                        "unit": _NEW_UNIT if k == "FY2020" else _OLD_UNIT,
                        "series_code": "PDMD Annex 15 public debt stock"})
    dom, ext = table.get("Total Domestic Debt"), next(
        (v for k, v in table.items() if k.startswith("Total External Debt")), None)
    tot = table.get("Total Debt Stock")
    if not (dom and ext and tot):
        raise ValueError("SL Annex 15: total rows not read")
    for k in _ANNEX_COLS:
        tol = 1.0 if k == "FY2020" else 1000.0
        if abs(dom[k] + ext[k] - tot[k]) > tol:
            raise ValueError(f"SL Annex 15 {k}: domestic + external != total")
        for sec, total in (("Domestic", dom), ("External", ext)):
            parts = sum(v.get(k, 0) for c, v in table.items()
                        if c.startswith(sec + ": "))
            if abs(parts - total[k]) > tol:
                raise ValueError(f"SL Annex 15 {k}: {sec} parts {parts} != {total[k]}")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, data_only=True)
    df = pd.DataFrame(_stock_sheet(wb) + _domestic_sheet(wb) + _annex_sheet(wb))
    # Sheets carry negative-zero-looking rounding residue as tiny negatives
    # nowhere in the stock rows; a negative here is a parse error.
    if (df["value"] < 0).any():
        raise ValueError("SL: negative stock value read")
    return df
