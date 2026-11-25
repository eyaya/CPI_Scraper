"""Parsers for Statistics Mauritius external merchandise trade (Excel).

`parse_historical` -- "External Merchandise Trade Statistics" historical series
  (By_Subject/External_Trade/HS_ExtTrade_<n>Qtr<yy>_<date>.xlsx):
    Table 1  imports and exports of goods, annual 1938- and quarterly from 1976
             (Rs million): exports of goods (excl. ship's stores), domestic
             exports, re-exports, ship's stores and bunkers, total exports
             (f.o.b), total imports (c.i.f), total trade, balance of visible trade.
    Table 4  exports by SITC section, quarterly + annual 2000-  (f.o.b, Rs million)
    Table 5  exports by country of destination, annual 1956-   (f.o.b, Rs million)
    Table 6  imports by SITC section, quarterly + annual 2000-  (c.i.f, Rs million)
    Table 7  imports by country of origin, annual 1956-        (c.i.f, Rs million)
  Tables 2-3 are price indices (not trade values) and are not read.

`parse_monthly` -- the monthly "Monthly External Merchandise Trade Statistics"
  workbook (Monthly/Trade/<year>/Trade_M_<Mon><yy>_<date>.xlsx): the summary
  (same month a year earlier, previous month, current month), imports and
  exports by SITC section, and the main trading partners of the month.

HOW SHIP'S STORES ARE KEPT. Mauritius' total exports (and so the balance and
total trade) INCLUDE ship's stores and bunkers; domestic exports + re-exports
equal "exports of goods" EXCLUDING them. So the all-products export row is the
printed total (A), ship's stores is a national product line, and domestic
exports, re-exports and the excl.-stores exports are filed under the national
product "Goods excluding ship's stores and bunkers" -- the only way both
printed identities (balance = A - B; exports of goods = domestic + re-exports)
hold. The SITC-section and partner tables exclude ship's stores (footnote), so
their "All sections" / "All countries" / "Total" lines (= excl.-stores
exports) are not emitted as the all-products total.

Partner tables print an "Other countries" line under every continent; it is
qualified with its continent ("Other countries (Europe)") since the same label
would otherwise carry five different figures. Footnote markers glued to a
label or year ("Hong Kong (S.A.R) 2", "2025 3") are removed.
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd

from ._common import row, to_number

_UNIT, _MULT = "MUR", 1e6
_EXCL = "Goods excluding ship's stores and bunkers"
_STORES = "Ship's stores and bunkers"
_QTR = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4}
_REGIONS = {"europe", "asia", "africa", "america", "oceania"}


def _s(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""


def _year(v) -> int | None:
    m = re.match(r"^\s*(\d{4})", _s(v))
    return int(m.group(1)) if m else None


def _num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return to_number(_s(v)) if v is not None else None


def _sheet(wb, prefix):
    for n in wb.sheetnames:
        if re.sub(r"\s+", " ", n).strip().lower() == prefix.lower():
            return wb[n]
    raise KeyError(prefix)


def _period_cols(rows, yr_i: int, q_i: int | None):
    """[(col, period, frequency)] from a year row (merged, carried forward)
    and an optional quarter row ('1st Qr' .. '4th Qr', 'Year')."""
    out, cur = [], None
    yr, qr = rows[yr_i], (rows[q_i] if q_i is not None else [])
    for j in range(1, len(yr)):
        y = _year(yr[j])
        if y:
            cur = y
        if cur is None:
            continue
        q = _s(qr[j]) if j < len(qr) else ""
        m = re.match(r"(1st|2nd|3rd|4th)\s*Q", q, re.I)
        if m:
            out.append((j, f"{cur}-Q{_QTR[m.group(1).lower()]}", "quarterly"))
        elif q.lower().startswith("year") or (not q and y):
            out.append((j, str(cur), "annual"))
    return out


def _table1(ws) -> list[dict]:
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    cols = _period_cols(rows, 2, 3)
    spec = (  # label regex -> (flow, commodity)
        (r"^exports of goods", ("export", _EXCL)),
        (r"^domestic exports", ("domestic_export", _EXCL)),
        (r"^re-?exports", ("re_export", _EXCL)),
        (r"^ship'?s stores", ("export", _STORES)),
        (r"^a\.\s*total exports", ("export", None)),
        (r"^b\.\s*total imports", ("import", None)),
        (r"^total value of trade", ("total", None)),
        (r"^balance of visible trade", ("balance", None)),
    )
    out = []
    for r in rows[4:]:
        lab = _s(r[0]).lower()
        hit = next((v for rx, v in spec if re.search(rx, lab)), None)
        if not hit:
            continue                  # "of which: Export Oriented Enterprises" is not read
        flow, com = hit
        basis = "cif" if flow == "import" else "fob" if flow in ("export", "domestic_export", "re_export") else ""
        for j, period, freq in cols:
            v = _num(r[j]) if j < len(r) else None
            if v is None:
                continue
            out.append(row(tradeflow=flow, period=period, frequency=freq, value=v, unit=_UNIT,
                           unit_multiplier=_MULT, commodity=com,
                           commodity_classification="national" if com else "",
                           price_basis=basis, trade_system="general", series_code="Table 1"))
    return out


def _sections(ws, flow: str, table: str) -> list[dict]:
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    cols = _period_cols(rows, 2, 3)
    out = []
    for r in rows[4:]:
        m = re.match(r"^\s*(\d)\s*-\s*(.+?)\s*$", _s(r[0]))
        if not m:
            continue                  # "All sections" (excl. stores) and the "of which" lines
        for j, period, freq in cols:
            v = _num(r[j]) if j < len(r) else None
            if v is None:
                continue
            out.append(row(tradeflow=flow, period=period, frequency=freq, value=v, unit=_UNIT,
                           unit_multiplier=_MULT, commodity=_s(r[0]), commodity_classification="sitc1",
                           commodity_code_nso=m.group(1), price_basis="fob" if flow == "export" else "cif",
                           trade_system="general", series_code=table))
    return out


def _clean_partner(lab: str) -> str:
    lab = re.sub(r"\s+\d$", "", _s(lab))          # footnote marker
    return re.sub(r"\s+", " ", lab).strip()


def _partners(ws, flow: str, table: str) -> list[dict]:
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    cols = _period_cols(rows, 2, None)
    out, region = [], None
    for r in rows[3:]:
        lab = _clean_partner(r[0])
        if not lab or not any(_num(c) is not None for c in r[1:]):
            continue
        low = lab.lower()
        if low.startswith("all countries"):
            continue                  # = exports excl. ship's stores; total from Table 1
        if low in _REGIONS:
            region, name, ptype = lab, lab, "group"
        elif low.startswith("other countries"):
            name, ptype = f"Other countries ({region})" if region else lab, "group"
        else:
            name, ptype = lab, "country"
        for j, period, freq in cols:
            v = _num(r[j]) if j < len(r) else None
            if v is None:
                continue
            out.append(row(tradeflow=flow, period=period, frequency=freq, value=v, unit=_UNIT,
                           unit_multiplier=_MULT, partner=name, partner_type=ptype,
                           price_basis="fob" if flow == "export" else "cif",
                           trade_system="general", series_code=table))
    return out


def parse_historical(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        out = _table1(_sheet(wb, "Table 1"))
        out += _sections(_sheet(wb, "Table 4"), "export", "Table 4")
        out += _partners(_sheet(wb, "Table 5"), "export", "Table 5")
        out += _sections(_sheet(wb, "Table 6"), "import", "Table 6")
        out += _partners(_sheet(wb, "Table 7"), "import", "Table 7")
    finally:
        wb.close()
    return pd.DataFrame(out)


# ------------------------------------------------------------------ monthly
_MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
                                         "sep", "oct", "nov", "dec"])}


def _month_cols(rows, i_year: int, i_mon: int, first_col: int, ncols: int, issue=None):
    """[(col, 'YYYY-MM')] for a block headed by a year row and a month row
    ('Aug 1' | 'Jul 2' | 'Aug 2': same month a year earlier, previous month,
    current month). With the issue's (year, month) known, each month label is
    dated from it -- the merged year cells sit over different columns in
    different issues (January 2026: '2026' spans December 2025 too)."""
    cand = []
    for j in range(first_col, first_col + ncols):
        mon = _s(rows[i_mon][j])[:3].lower() if j < len(rows[i_mon]) else ""
        if mon in _MON:
            cand.append((j, _MON[mon]))
    if issue:
        y, m = issue
        last_cur = max((j for j, mo in cand if mo == m), default=None)
        out = []
        for j, mo in cand:
            if mo == m:
                yy = y if j == last_cur else y - 1
            else:
                yy = y if mo < m else y - 1
            out.append((j, f"{yy}-{mo:02d}"))
        return out
    out, cur = [], None
    for j in range(first_col, first_col + ncols):
        yv = _year(rows[i_year][j]) if j < len(rows[i_year]) else None
        if yv:
            cur = yv
        mo = dict(cand).get(j)
        if cur and mo:
            out.append((j, f"{cur}-{mo:02d}"))
    return out


def _issue(rows):
    for r in rows[:6]:
        for c in r:
            m = re.search(r"statistics\s*[-–]\s*([A-Za-z]+)\s*,?\s*(\d{4})", _s(c), re.I)
            if m and m.group(1)[:3].lower() in _MON:
                return int(m.group(2)), _MON[m.group(1)[:3].lower()]
    return None


def _first_sheet_rows(path: str) -> list[list]:
    """Rows of the first worksheet; .xls (2016-2020 issues) via xlrd."""
    if path.lower().endswith(".xls"):
        import xlrd
        book = xlrd.open_workbook(path)
        try:
            sh = book.sheet_by_index(0)
            return [[None if c.ctype in (0, 6) else c.value for c in sh.row(i)] for i in range(sh.nrows)]
        finally:
            book.release_resources()
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        return [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    finally:
        wb.close()


def parse_monthly_rows(path: str) -> list[dict]:
    rows = _first_sheet_rows(path)
    issue = _issue(rows)
    out = []
    i = 0
    while i < len(rows):
        first = next((_s(c) for c in rows[i] if c is not None), "")
        low = first.lower()
        if low.startswith("summary of external merchandise trade"):
            hy = next(k for k in range(i + 1, i + 5) if sum(_year(c) is not None for c in rows[k]) >= 2)
            cols = _month_cols(rows, hy, hy + 1, 1, len(rows[hy]) - 1, issue)
            for r in rows[hy + 2: hy + 14]:
                lab = _s(r[0]).lower()
                spec = ((r"total exports", ("export", None)), (r"domestic exports", ("domestic_export", _EXCL)),
                        (r"re-?exports", ("re_export", _EXCL)), (r"ship'?s stores", ("export", _STORES)),
                        (r"total imports", ("import", None)), (r"total international trade", ("total", None)),
                        (r"trade (deficit|surplus|balance)", ("balance", None)))
                hit = next((v for rx, v in spec if re.search(rx, lab)), None)
                if not hit:
                    continue
                flow, com = hit
                basis = "cif" if flow == "import" else "fob" if flow != "total" and flow != "balance" else ""
                for j, period in cols:
                    v = _num(r[j])
                    if v is None:
                        continue
                    out.append(row(tradeflow=flow, period=period, frequency="monthly", value=v,
                                   unit=_UNIT, unit_multiplier=_MULT, commodity=com,
                                   commodity_classification="national" if com else "",
                                   price_basis=basis, trade_system="general",
                                   series_code="1. Summary"))
        elif re.match(r"^\d\.\s*total (imports|exports) of goods by s\.?i\.?t\.?c", low):
            flow = "import" if "imports" in low else "export"
            hy = next(k for k in range(i + 1, i + 5) if sum(_year(c) is not None for c in rows[k]) >= 2)
            cols = _month_cols(rows, hy, hy + 1, 1, len(rows[hy]) - 1, issue)
            for r in rows[hy + 2: hy + 20]:
                m = re.match(r"^\s*(\d)\s*-\s*(.+?)\s*$", _s(r[0]))
                if not m:
                    continue
                for j, period in cols:
                    v = _num(r[j])
                    if v is None:
                        continue
                    out.append(row(tradeflow=flow, period=period, frequency="monthly", value=v,
                                   unit=_UNIT, unit_multiplier=_MULT, commodity=_s(r[0]),
                                   commodity_classification="sitc1", commodity_code_nso=m.group(1),
                                   price_basis="fob" if flow == "export" else "cif",
                                   trade_system="general", series_code=f"Table {first[0]}"))
        elif re.match(r"^\d\.\s*main trading partners", low):
            hy = next(k for k in range(i + 1, i + 6) if sum(_year(c) is not None for c in rows[k]) >= 2)
            # two side-by-side blocks: Country | y | y ... || Country | y | y ...
            starts = [j for j, c in enumerate(rows[hy]) if _s(c).lower() == "country"]
            for b, j0 in enumerate(starts):
                flow = "export" if b == 0 else "import"
                end = starts[b + 1] if b + 1 < len(starts) else len(rows[hy])
                cols = _month_cols(rows, hy, hy + 1, j0 + 1, end - j0 - 1, issue)
                for r in rows[hy + 2: hy + 20]:
                    lab = _clean_partner(r[j0]) if j0 < len(r) else ""
                    if not lab or lab.lower() == "total" or lab.lower().startswith("1 "):
                        continue
                    ptype = "group" if lab.lower() in ("other", "others") else "country"
                    for j, period in cols:
                        v = _num(r[j]) if j < len(r) else None
                        if v is None:
                            continue
                        out.append(row(tradeflow=flow, period=period, frequency="monthly", value=v,
                                       unit=_UNIT, unit_multiplier=_MULT, partner=lab, partner_type=ptype,
                                       price_basis="fob" if flow == "export" else "cif",
                                       trade_system="general", series_code=f"Table {first[0]}"))
        i += 1
    return out


def parse_monthly(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """The latest monthly workbook plus back issues; a month printed by two
    issues (provisional, then revised) keeps the newer issue's figure."""
    from ..schema import KEY
    files = list(dict.fromkeys([*(extras or []), path]))
    frames = []
    for p in files:
        rows = parse_monthly_rows(p)
        if rows:
            df = pd.DataFrame(rows)
            frames.append((df["period"].max(), df))
    frames.sort(key=lambda t: t[0])
    df = pd.concat([f for _, f in frames], ignore_index=True)
    return df.drop_duplicates(KEY, keep="last").reset_index(drop=True)


parse = parse_historical
