"""Parser for LISGIS Liberia external-trade workbooks (uploads/archive/trade-statistics/).

LISGIS publishes its trade workbooks as Excel files in its Trade Statistics
archive (also exposed cell-by-cell as JSON datasets on /api/datasets). Four
workbooks, each read by its own function (dispatched on the file name):

  External Trade <YYYY> Q<n> REPORT TABLES.xlsx  (2026 Q1)
      LIB TRADE SUMMARY: exports FOB, imports CIF, total trade (TT), balance
      (BOT) by month + the quarter's grand total; TRADE BY SITC (SITC
      sections, no codes printed); EXPORT BY HS / IMPORT BY HS (HS chapters);
      TRADE BY PARTNE(R) EXPORT & IMPORT (every partner) -- for the quarter.
      Top-10 and HS6 detail sheets are not read (HS2 exists).
  EXTERNAL TRADE TABLES 2024 N0V - 2025 NOV.xlsx
      Tables 1 / 2: monthly exports (FOB) / imports (CIF), Nov 2024 - Nov 2025.
      Months outside the stated window print 0 and are skipped. The partner
      and product tables give "2024" (= Nov-Dec) and "2025" (= Jan-Nov)
      partial-year columns -- not a standard period, so not read.
  External_Trade_2021_data.xlsx
      Monthly + "TOTAL 2021" exports (FOB), imports (CIF), balance, total trade.
  bop2004-2007nov202008.xlsx  (historical BoP & trade workbook)
      Exports by HS chapter 2006-2007 (+2008-Q1, Jan-Mar 2008), monthly,
      quarterly, annual; imports by HS chapter, monthly 2007 + year; imports
      by country of supply, 2007 monthly / quarterly / annual. Thousands of US
      dollars, c.i.f. as printed (the export tables say "c.i.f. values" too).
      World totals = "TOTAL EXPORTS" / "TOTAL IMPORTS" (incl. tax-exempt
      trade); the "TOTAL" line excluding tax-exempt trade is not read (the
      partner table sums to it, a different coverage). HS sections (roman
      numerals) and sub-items are not read. BoP sheets are not trade tables.
All values in US dollars, as printed. "-" cells are skipped.
"""
from __future__ import annotations

import datetime as dt
import os
import re

import openpyxl
import pandas as pd

from ._common import row
from ..schema import KEY

_MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
                                         "sep", "oct", "nov", "dec"])}


def _t(c) -> str:
    return re.sub(r"\s+", " ", str(c)).strip() if c is not None else ""


def _n(c):
    if isinstance(c, bool) or c is None:
        return None
    if isinstance(c, (int, float)):
        return float(c)
    s = _t(c).replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _rows(wb, name):
    return [list(r) for r in wb[name].iter_rows(values_only=True)]


def _sheet(wb, *frags):
    for n in wb.sheetnames:
        if all(f.lower() in n.lower() for f in frags):
            return n
    raise KeyError(frags)


# ---------------------------------------------------------------- 2026 Q1 report tables
def _quarter_report(wb, year, q, sc):
    out, qp = [], f"{year}-Q{q}"
    rows = _rows(wb, _sheet(wb, "TRADE SUMMARY"))
    hi = next(i for i, r in enumerate(rows) if "MONTH" in [_t(c).upper() for c in r])
    hdr = [_t(c).upper() for c in rows[hi]]
    cols = {hdr.index("FOB"): ("export", "fob"), hdr.index("CIF"): ("import", "cif"),
            hdr.index("TT"): ("total", ""), hdr.index("BOT"): ("balance", "")}
    mc = hdr.index("MONTH")
    for r in rows[hi + 1:]:
        lab = _t(r[mc]).lower()
        if lab == "grand total":
            per, freq = qp, "quarterly"
        elif lab[:3] in _MON:
            per, freq = f"{year}-{_MON[lab[:3]]:02d}", "monthly"
        else:
            continue
        for j, (fl, pb) in cols.items():
            v = _n(r[j])
            if v is not None:
                out.append(row(tradeflow=fl, period=per, frequency=freq, value=v, unit="USD",
                               price_basis=pb, series_code=f"{sc}:LIB TRADE SUMMARY"))
    # SITC
    rows = _rows(wb, _sheet(wb, "SITC"))
    hi = next(i for i, r in enumerate(rows) if "SITC" in [_t(c).upper() for c in r])
    hdr = [_t(c).upper() for c in rows[hi]]
    lc, fc, cc = hdr.index("SITC"), hdr.index("FOB"), hdr.index("CIF")
    for r in rows[hi + 1:]:
        lab = _t(r[lc])
        if not lab or lab.lower() == "grand total":
            continue
        for j, fl, pb in ((fc, "export", "fob"), (cc, "import", "cif")):
            v = _n(r[j])
            if v is not None:
                out.append(row(tradeflow=fl, period=qp, frequency="quarterly", value=v, unit="USD",
                               commodity=lab, commodity_classification="sitc1", price_basis=pb,
                               series_code=f"{sc}:TRADE BY SITC"))
    # HS chapters
    for frag, fl, pb in (("EXPORT BY HS", "export", "fob"), ("IMPORT BY HS", "import", "cif")):
        name = next(n for n in wb.sheetnames if n.strip().upper() == frag)
        rows = _rows(wb, name)
        hi = next(i for i, r in enumerate(rows) if "HS2" in [_t(c).upper() for c in r])
        hdr = [_t(c).upper() for c in rows[hi]]
        kc, lc = hdr.index("HS2"), hdr.index("HS2 LABEL")
        vc = next(j for j, h in enumerate(hdr) if h in ("FOB", "CIF"))
        for r in rows[hi + 1:]:
            code = _t(r[kc])
            if not re.fullmatch(r"\d{1,2}", code):
                continue
            v = _n(r[vc])
            if v is not None:
                out.append(row(tradeflow=fl, period=qp, frequency="quarterly", value=v, unit="USD",
                               commodity=_t(r[lc]), commodity_classification="hs2",
                               commodity_code_nso=code.zfill(2), price_basis=pb,
                               series_code=f"{sc}:{frag}"))
    # partners
    rows = _rows(wb, _sheet(wb, "TRADE BY PARTNE"))
    hi = next(i for i, r in enumerate(rows) if "COUNTRY" in [_t(c).upper() for c in r])
    hdr = [_t(c).upper() for c in rows[hi]]
    lc, fc, cc = hdr.index("COUNTRY"), hdr.index("FOB"), hdr.index("CIF")
    for r in rows[hi + 1:]:
        lab = _t(r[lc])
        if not lab or lab.lower() == "grand total":
            continue
        pt = "group" if re.search(r"unknown|not specified|\bother|\bn\.?e\.?s\b", lab, re.I) else "country"
        for j, fl, pb in ((fc, "export", "fob"), (cc, "import", "cif")):
            v = _n(r[j]) if j < len(r) else None
            if v is not None:
                out.append(row(tradeflow=fl, period=qp, frequency="quarterly", value=v, unit="USD",
                               partner=lab, partner_type=pt, price_basis=pb,
                               series_code=f"{sc}:TRADE BY PARTNER"))
    return out


# ---------------------------------------------------------------- Nov 2024 - Nov 2025 tables
def _window_tables(wb, sc):
    rows = _rows(wb, "TRADE TABLES")
    out = []
    lo, hi = (2024, 11), (2025, 11)            # the window stated in the table titles
    for i, r in enumerate(rows):
        for j, c in enumerate(r):
            m = re.match(r"TABLE\s*:\s*([12])$", _t(c), re.I)
            if not m:
                continue
            fl, pb = ("export", "fob") if m.group(1) == "1" else ("import", "cif")
            hr = next(k for k in range(i + 1, i + 6) if "month" in [_t(x).lower() for x in rows[k]])
            hdr = [_t(x) if j <= k < j + 5 else "" for k, x in enumerate(rows[hr])]   # this block only
            mc = [x.lower() for x in hdr].index("month")
            ycols = {k: int(h) for k, h in enumerate(hdr) if re.fullmatch(r"\d{4}", h)}
            for rr in rows[hr + 1: hr + 18]:
                lab = _t(rr[mc]).lower()[:3]
                if lab not in _MON:
                    continue
                for k, y in ycols.items():
                    if not lo <= (y, _MON[lab]) <= hi:
                        continue
                    v = _n(rr[k])
                    if v is not None:
                        out.append(row(tradeflow=fl, period=f"{y}-{_MON[lab]:02d}", frequency="monthly",
                                       value=v, unit="USD", price_basis=pb,
                                       series_code=f"{sc}:Table {m.group(1)}"))
    return out


# ---------------------------------------------------------------- 2021 workbook
def _annual_2021(wb, sc):
    rows = _rows(wb, wb.sheetnames[0])
    hdr = [_t(c).upper() for c in rows[0]]
    cols = {}
    for j, h in enumerate(hdr):
        if h.startswith("EXPORT VALUE"):
            cols[j] = ("export", "fob")
        elif h.startswith("IMPORT VALUE"):
            cols[j] = ("import", "cif")
        elif h == "BALANCE OF TRADE":
            cols[j] = ("balance", "")
        elif h == "TOTAL TRADE":
            cols[j] = ("total", "")
    out = []
    for r in rows[1:]:
        lab = _t(r[0]) if r else ""
        m = re.match(r"TOTAL\s+(\d{4})", lab, re.I)
        if m:
            per, freq = m.group(1), "annual"
        elif lab[:3].lower() in _MON and re.fullmatch(r"[A-Za-z]+", lab):
            per, freq = f"2021-{_MON[lab[:3].lower()]:02d}", "monthly"
        else:
            continue
        for j, (fl, pb) in cols.items():
            v = _n(r[j])
            if v is not None:
                out.append(row(tradeflow=fl, period=per, frequency=freq, value=v, unit="USD",
                               price_basis=pb, series_code=f"{sc}:externalTrade2021"))
    return out


# ---------------------------------------------------------------- 2004-2007 workbook
def _period_of(h):
    if isinstance(h, (int, float)) and 1990 < h < 2100:
        return str(int(h)), "annual"
    if isinstance(h, (dt.datetime, dt.date)):
        return f"{h.year}-{h.month:02d}", "monthly"
    s = _t(h)
    m = re.fullmatch(r"(\d{4})-Q([1-4])", s)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}", "quarterly"
    m = re.fullmatch(r"([A-Za-z]{3})-(\d{2})", s)
    if m and m.group(1).lower() in _MON:
        return f"20{m.group(2)}-{_MON[m.group(1).lower()]:02d}", "monthly"
    return None


def _hist(wb, sc):
    out = []
    specs = [("Tab 4.1", "export"), ("Monthly Export", "export"), ("Monthly Import", "import")]
    for frag, fl in specs:
        name = _sheet(wb, frag)
        rows = _rows(wb, name)
        if "thousands of us dollars" not in _t(rows[1][0]).lower():
            continue
        pers = {j: _period_of(h) for j, h in enumerate(rows[2])}
        pers = {j: p for j, p in pers.items() if p}
        for r in rows[3:]:
            c0, c1 = _t(r[0]), _t(r[1]) if len(r) > 1 else ""
            label = code = None
            m = re.match(r"^(\d{2})\s+(.+)$", c0)
            if m:                                           # export sheets: "03   Fish ..."
                code, label = m.group(1), m.group(2)
            elif re.fullmatch(r"\d{1,2}", c0) and c1:      # import sheet: code | label
                code, label = c0.zfill(2), re.sub(r"^\d{1,2}\s+", "", c1)
            elif c0.upper() == "TOTAL EXPORTS" or c1.upper() == "TOTAL IMPORTS":
                code = ""
            if code is None or (label and "discrepancy" in label.lower()):
                continue                        # not a chapter (a "99 Statistical Discrepancy" line)
            for j, (p, f) in pers.items():
                v = _n(r[j]) if j < len(r) else None
                if v is None:
                    continue
                out.append(row(tradeflow=fl, period=p, frequency=f, value=v, unit="USD",
                               unit_multiplier=1e3, price_basis="cif",
                               commodity=label.strip() if label else None,
                               commodity_classification="hs2" if label else "", commodity_code_nso=code,
                               series_code=f"{sc}:{name.strip()}"))
    for frag in ("Imports by Country", "Mon-Imports"):
        name = _sheet(wb, frag)
        rows = _rows(wb, name)
        pers = {j: _period_of(h) for j, h in enumerate(rows[2])}
        pers = {j: p for j, p in pers.items() if p}
        for r in rows[3:]:
            lab = _t(r[1])
            if not lab or lab.upper() == "TOTAL":
                continue
            pt = "group" if _t(r[2]).upper() == "ZZ" else "country"
            for j, (p, f) in pers.items():
                v = _n(r[j]) if j < len(r) else None
                if v is not None:
                    out.append(row(tradeflow="import", period=p, frequency=f, value=v, unit="USD",
                                   unit_multiplier=1e3, price_basis="cif", partner=lab, partner_type=pt,
                                   series_code=f"{sc}:{name.strip()}"))
    return out


def parse_file(path: str) -> list[dict]:
    base = os.path.basename(path)
    sc = os.path.splitext(base)[0]
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        m = re.search(r"(\d{4})\s*Q([1-4])\s*REPORT", base, re.I)
        if m:
            return _quarter_report(wb, int(m.group(1)), int(m.group(2)), sc)
        if "TRADE TABLES" in base.upper():
            return _window_tables(wb, sc)
        if "2021" in base:
            return _annual_2021(wb, sc)
        if base.lower().startswith("bop2004"):
            return _hist(wb, sc)
        raise ValueError(f"liberia_lisgis_trade: unknown workbook {base}")
    finally:
        wb.close()


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for f in [path, *(extras or [])]:
        rows += parse_file(f)
    df = pd.DataFrame(rows)
    return df.loc[~df[KEY].astype(str).duplicated(keep="first")].reset_index(drop=True)
