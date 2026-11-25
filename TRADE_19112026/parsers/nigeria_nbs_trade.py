"""Parser for NBS Nigeria "Foreign Trade in Goods Statistics" quarterly tables (Excel).

Input: the quarterly workbook ("Q2 2026 Foreign Trade in Goods Statistics
Tables.xlsx", or the NADA zip that carries it beside the PDF report), plus
older quarters as `extras`. Every workbook since Q3 2024 has the same sheets;
each carries the series back to 2020. All values are naira, as printed in the
table caption: N'million, except Table 8 (N'billion).

Read (one observation per table cell, as published):
  TABLE 1   imports, exports (fob), balance (signed), total trade; and the
            exports of crude oil / non-crude oil / non-oil products
            (national grouping) -- annual (Jan-Dec), quarterly, monthly.
  TABLE 8   domestic exports and re-exports (N'billion). Its imports, exports
            and balance repeat Table 1 at a coarser scale and are NOT read
            (its 2025 quarterly balances also disagree with exports - imports).
  TABLE 2/3 imports (cif) / exports (fob) by HS SECTION (22 sections; the
            schema has no section level, so classification "national" with the
            printed section number as commodity_code_nso) -- annual and the
            same quarter of each year.
  TABLE 4/5 imports / exports by region and major partner (Africa, ECOWAS,
            America, USA ...): annual, quarterly, monthly. A region's "Others"
            column is labelled "<Region> - Others" so the five stay distinct.
  TABLE 5B  exports / imports with each African country: annual + the
            report quarter.
  TABLE 6   imports by SITC section (no codes printed -> code blank).
  TABLE 7   imports by BEC category (code printed in the label).
Not read: shares (%), growth, HS10 product rankings, partner x product tables
(5C, 15-18), sector x region (14/14A), mode of transport, ports.
Partial-year columns ("2026 (Jan-Jun)", "Jan-Jun") are skipped; the section
tables' "Total" rows (which differ slightly from Table 1) are skipped, as is
the "Total" column of Tables 4/5/6 (it repeats Table 1).
Several workbooks overlap: rows are taken oldest issue first and the newest
issue's figure wins for a key (revisions replace provisional figures).
"""
from __future__ import annotations

import io
import os
import re
import zipfile

import openpyxl
import pandas as pd

from ._common import row
from ..schema import KEY

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
           "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_QSPAN = {"jan-mar": 1, "apr-jun": 2, "jul-sep": 3, "oct-dec": 4}


def _book(path: str):
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
            data = z.read(name)
        return openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True), name
    return openpyxl.load_workbook(path, read_only=True, data_only=True), os.path.basename(path)


def _rows(wb, sheet):
    return [list(r) for r in wb[sheet].iter_rows(values_only=True)]


def _txt(c) -> str:
    return re.sub(r"\s+", " ", str(c)).strip() if c is not None else ""


def _num(c):
    if c is None or isinstance(c, bool):
        return None
    if isinstance(c, (int, float)):
        return float(c)
    s = _txt(c).replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


class _Clock:
    """Turns the (year, period) label pairs of a time-series table into periods.
    The year is printed on the first row of each block only; a month list that
    restarts at January without a year belongs to the next year."""

    def __init__(self):
        self.year = None
        self.last_month = 0

    def period(self, ycell, pcell):
        y = _txt(ycell)
        if re.fullmatch(r"\d{4}(\.0)?", y):
            self.year, self.last_month = int(float(y)), 0
        p = _txt(pcell).lower()
        if self.year is None or not p:
            return None
        if p == "jan-dec":
            return str(self.year), "annual"
        m = re.fullmatch(r"q([1-4])", p)
        if m:
            return f"{self.year}-Q{m.group(1)}", "quarterly"
        mo = _MONTHS.get(p[:3]) if re.fullmatch(r"[a-z]+", p) else None
        if mo:
            if not re.fullmatch(r"\d{4}(\.0)?", y) and mo <= self.last_month:
                self.year += 1
            self.last_month = mo
            return f"{self.year}-{mo:02d}", "monthly"
        return None          # "Jan-Jun" and other partial-year totals


def _col_period(h):
    """A column header of the section / BEC / 5B tables -> (period, freq)."""
    s = _txt(h)
    if re.fullmatch(r"\d{4}(\.0)?", s):
        return str(int(float(s))), "annual"
    m = re.fullmatch(r"([A-Za-z]{3}-[A-Za-z]{3})\s+(\d{4})", s)
    if m and m.group(1).lower() in _QSPAN:
        return f"{m.group(2)}-Q{_QSPAN[m.group(1).lower()]}", "quarterly"
    m = re.fullmatch(r"Q([1-4]),?\s*(\d{4})", s)
    if m:
        return f"{m.group(2)}-Q{m.group(1)}", "quarterly"
    return None


def _table1(rows, sc):
    hdr_i = next(i for i, r in enumerate(rows) if any(_txt(c).lower() == "balance" for c in r))
    hdr = [_txt(c).lower() for c in rows[hdr_i]]
    cols = {}
    for j, h in enumerate(hdr):
        if h == "imports":
            cols[j] = dict(tradeflow="import")
        elif h.startswith("exports") and "%" not in h and "/" not in h:
            cols[j] = dict(tradeflow="export", price_basis="fob" if "fob" in h else "")
        elif h == "balance":
            cols[j] = dict(tradeflow="balance")
        elif h == "total trade":
            cols[j] = dict(tradeflow="total")
        elif h == "crude oil exports":
            cols[j] = dict(tradeflow="export", commodity="Crude Oil", commodity_classification="national")
        elif h.replace("_", "-") == "non-crude oil exports":
            cols[j] = dict(tradeflow="export", commodity="Non-Crude Oil", commodity_classification="national")
        elif h == "non oils exports":
            cols[j] = dict(tradeflow="export", commodity="Non-Oil", commodity_classification="national")
    yc = next(j for j, h in enumerate(hdr) if h == "imports") - 2
    out, clk = [], _Clock()
    for r in rows[hdr_i + 1:]:
        per = clk.period(r[yc], r[yc + 1])
        if not per:
            continue
        for j, kw in cols.items():
            v = _num(r[j])
            if v is not None:
                out.append(row(period=per[0], frequency=per[1], value=v, unit="NGN",
                               unit_multiplier=1e6, series_code=f"{sc}:Table 1", **kw))
    return out


def _table8(rows, sc):
    hdr_i = next(i for i, r in enumerate(rows) if any(_txt(c).upper() == "RE-EXPORTS" for c in r))
    hdr = [_txt(c).upper() for c in rows[hdr_i]]
    cols = {hdr.index("DOMESTIC EXPORT"): "domestic_export", hdr.index("RE-EXPORTS"): "re_export"}
    yc = hdr.index("YEAR")
    out, clk = [], _Clock()
    for r in rows[hdr_i + 1:]:
        per = clk.period(r[yc], r[yc + 1])
        if not per:
            continue
        for j, fl in cols.items():
            v = _num(r[j])
            if v is not None:
                out.append(row(tradeflow=fl, period=per[0], frequency=per[1], value=v, unit="NGN",
                               unit_multiplier=1e9, series_code=f"{sc}:Table 8"))
    return out


def _sections(rows, sc, flow, basis, tab):
    hdr_i = next(i for i, r in enumerate(rows) if any("value (" in _txt(c).lower() for c in r))
    pers = {j: _col_period(h) for j, h in enumerate(rows[hdr_i])}
    pers = {j: p for j, p in pers.items() if p}
    out = []
    for r in rows[hdr_i + 1:]:
        if any("proportion" in _txt(c).lower() or "share" in _txt(c).lower() for c in r[:3]):
            break
        code = _txt(r[0])
        if not re.fullmatch(r"\d{1,2}(\.0)?", code):
            continue
        code, label = str(int(float(code))), _txt(r[1])
        for j, (p, f) in pers.items():
            v = _num(r[j])
            if v is not None:
                out.append(row(tradeflow=flow, period=p, frequency=f, value=v, unit="NGN",
                               unit_multiplier=1e6, commodity=label, commodity_classification="national",
                               commodity_code_nso=code, price_basis=basis, series_code=f"{sc}:{tab}"))
    return out


def _regions(rows, sc, flow, tab):
    r1_i = next(i for i, r in enumerate(rows) if any(_txt(c) == "Africa" for c in r))
    r1, r2 = rows[r1_i], rows[r1_i + 1]
    region, cols = None, {}
    for j in range(len(r1)):
        if _txt(r1[j]):
            region = _txt(r1[j])
        sub = _txt(r2[j]) if j < len(r2) else ""
        if region is None or region.lower() == "total":
            continue
        if not sub:
            if _txt(r1[j]):          # a one-column region (Oceania)
                cols[j] = (region, "group")
            continue
        if sub.lower() == "total":
            cols[j] = (region, "group")
        elif sub.lower() == "others":
            cols[j] = (f"{region} - Others", "group")
        elif sub.upper() == "ECOWAS":
            cols[j] = (sub, "group")
        else:
            cols[j] = (sub, "country")
    out, clk = [], _Clock()
    for r in rows[r1_i + 2:]:
        per = clk.period(r[0], r[1])
        if not per:
            continue
        for j, (lab, pt) in cols.items():
            v = _num(r[j]) if j < len(r) else None
            if v is not None:
                out.append(row(tradeflow=flow, period=per[0], frequency=per[1], value=v, unit="NGN",
                               unit_multiplier=1e6, partner=lab, partner_type=pt,
                               series_code=f"{sc}:{tab}"))
    return out


def _table5b(rows, sc):
    hdr_i = next(i for i, r in enumerate(rows) if sum(_txt(c) == "COUNTRY" for c in r) == 2)
    hdr = rows[hdr_i]
    cidx = [j for j, c in enumerate(hdr) if _txt(c) == "COUNTRY"]
    out = []
    for flow, cj in zip(("export", "import"), cidx):
        pers = {}
        for j in range(cj + 1, len(hdr)):
            p = _col_period(hdr[j])
            if not p:
                break
            pers[j] = p
        for r in rows[hdr_i + 1:]:
            lab = _txt(r[cj]).rstrip("* ").strip() if cj < len(r) else ""   # footnote star
            if not lab:
                continue
            pt = "group" if "nes" in lab.lower().split() else "country"
            for j, (p, f) in pers.items():
                v = _num(r[j])
                if v is not None:
                    out.append(row(tradeflow=flow, period=p, frequency=f, value=v, unit="NGN",
                                   unit_multiplier=1e6, partner=lab, partner_type=pt,
                                   series_code=f"{sc}:Table 5B"))
    return out


def _table6(rows, sc):
    hdr_i = next(i for i, r in enumerate(rows) if any("food" in _txt(c).lower() for c in r))
    hdr = rows[hdr_i]
    cols = {j: _txt(c) for j, c in enumerate(hdr) if _txt(c) and _txt(c).lower() != "total"}
    out, clk = [], _Clock()
    for r in rows[hdr_i + 1:]:
        per = clk.period(r[0], r[1])
        if not per:
            continue
        for j, lab in cols.items():
            v = _num(r[j])
            if v is not None:
                out.append(row(tradeflow="import", period=per[0], frequency=per[1], value=v, unit="NGN",
                               unit_multiplier=1e6, commodity=lab, commodity_classification="sitc1",
                               series_code=f"{sc}:Table 6"))
    return out


def _table7(rows, sc):
    hdr_i = next(i for i, r in enumerate(rows) if sum(_col_period(c) is not None for c in r) >= 3)
    pers = {j: _col_period(h) for j, h in enumerate(rows[hdr_i])}
    pers = {j: p for j, p in pers.items() if p}
    out, started = [], False
    for r in rows[hdr_i + 1:]:
        lab = _txt(r[0])
        if re.match(r"^a\.?\s", lab.lower()):
            started = True
            continue
        if re.match(r"^b\.?\s", lab.lower()):
            break
        m = re.match(r"^(\d{1,3})\s+(.+)$", lab)
        if not started or not m:
            continue
        for j, (p, f) in pers.items():
            v = _num(r[j])
            if v is not None:
                out.append(row(tradeflow="import", period=p, frequency=f, value=v, unit="NGN",
                               unit_multiplier=1e6, commodity=m.group(2).strip(),
                               commodity_classification="bec", commodity_code_nso=m.group(1),
                               series_code=f"{sc}:Table 7"))
    return out


def parse_workbook(path: str) -> list[dict]:
    wb, name = _book(path)
    try:
        m = re.search(r"Q([1-4])[ _]*(\d{4})", name)
        sc = f"NBS FTS {m.group(2)}-Q{m.group(1)}" if m else "NBS FTS"
        out = []
        out += _table1(_rows(wb, "TABLE 1"), sc)
        out += _table8(_rows(wb, "TABLE 8"), sc)
        out += _sections(_rows(wb, "TABLE 2"), sc, "import", "cif", "Table 2")
        out += _sections(_rows(wb, "TABLE 3"), sc, "export", "fob", "Table 3")
        out += _regions(_rows(wb, "TABLE 4"), sc, "import", "Table 4")
        out += _regions(_rows(wb, "TABLE 5"), sc, "export", "Table 5")
        out += _table5b(_rows(wb, "TABLE 5B"), sc)
        out += _table6(_rows(wb, "TABLE 6"), sc)
        out += _table7(_rows(wb, "TABLE 7"), sc)
    finally:
        wb.close()
    return out


def _issue_key(path: str):
    m = re.search(r"Q([1-4])[ _]*(\d{4})", os.path.basename(path))
    return (int(m.group(2)), int(m.group(1))) if m else (0, 0)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = sorted({path, *(extras or [])}, key=_issue_key)
    frames = [pd.DataFrame(parse_workbook(f)) for f in files]
    df = pd.concat(frames, ignore_index=True)
    # Newest issue wins within this run (files are oldest first).
    norm = df[KEY].astype(str)
    return df.loc[~norm.duplicated(keep="last")].reset_index(drop=True)
