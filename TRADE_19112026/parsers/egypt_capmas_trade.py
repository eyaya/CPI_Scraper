"""Parser for CAPMAS Egypt "Foreign Trade (Monthly Bulletin)" workbooks (publication 22).

One workbook per month (Excel since January 2021; earlier issues are PDF only --
scanned before 2019, reversed-Arabic text in 2019-2020 -- and are not read).
Bilingual (Arabic/English) sheets; the column order changes between issues
(2021: imports before exports in Table 9; 2026: exports first, plus Jan/<month>
cumulative blocks; LNG split out of petroleum from 2022), so every column is
located from its printed header, never by position.

Read, per workbook:
  Table 1   trade balance by general trade system (US$ million): the current
            month and the same month a year earlier ("*" validated data) --
            exports / imports by petroleum breakdown (national product list),
            total exports, total imports, trade volume (total), trade balance.
  Table 6-A/6-B  exports / imports by Broad Economic Categories (US$ million),
            the current month (and, in a December issue, the January/December
            cumulative = the calendar year).
  Table 9-A/9-B  exports / imports by region and country (US$ thousand), the
            current month and the same month a year earlier (and Jan/Dec in a
            December issue). Regions, blocs and subtotals are partner_type
            "group".
Skipped: the "amount of change" and % columns, Jan/<month> cumulative blocks
other than December (year-to-date is not a schema period), ports (Table 2),
the product lists of Tables 3-5 and 7-8 (Table 8 is a partner x product
matrix), and Table h (repeats Table 1 with the previous month).

The all-partner/all-product totals are taken from Table 1 ONLY: the totals
printed atop Tables 6 and 9 sometimes differ from Table 1 by a rounding
thousand (2020-01 imports: 6,568.598 million in Table 1 vs 6,569,598 thousand
in Table 9-A).
"""
from __future__ import annotations

import datetime as dt
import re

import openpyxl

from ._common import row

_AR_MONTHS = {"يناير": 1, "فبراير": 2, "مارس": 3, "ابريل": 4, "أبريل": 4, "إبريل": 4, "مايو": 5,
              "يونيو": 6, "يونيه": 6, "يوليو": 7, "يوليه": 7, "اغسطس": 8, "أغسطس": 8, "سبتمبر": 9,
              "اكتوبر": 10, "أكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12}
_EN_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
              "september", "october", "november", "december"]


def _s(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""


def _num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _sheet(wb, *needles):
    for name in wb.sheetnames:
        flat = re.sub(r"\s+", " ", name)
        if all(n in flat for n in needles):
            return wb[name]
    return None


def _rows(ws):
    return [list(r) for r in ws.iter_rows(values_only=True)]


def _issue_period(wb) -> tuple[int, int]:
    """Month and year of the issue, from Table 1's English title ('... during August 2026')."""
    ws = _sheet(wb, "Table 1")
    for r in _rows(ws)[:6]:
        for c in r:
            m = re.search(r"during\s+([A-Za-z]+)\s*,?\s*(\d{4})", _s(c), re.I)
            if m and m.group(1).lower() in _EN_MONTHS:
                return int(m.group(2)), _EN_MONTHS.index(m.group(1).lower()) + 1
    raise ValueError("egypt_capmas_trade: issue month not found in Table 1 title")


def _row_period(cells) -> tuple[int, int, bool] | None:
    """(year, month, cumulative) of a Table 1 data row from its Arabic period
    label; "يناير/أغسطس 2026" (January/August) is a cumulative row."""
    for c in cells:
        if isinstance(c, dt.datetime):
            continue
        t = _s(c).replace("*", " ")
        m = re.search(r"([؀-ۿ]+)\s*(\d{4})", t)
        if m and m.group(1) in _AR_MONTHS:
            return int(m.group(2)), _AR_MONTHS[m.group(1)], "/" in t
    # Some issues print the current month as an Excel date (January 2024).
    if cells and isinstance(cells[0], dt.datetime):
        return cells[0].year, cells[0].month, False
    return None


# ---------------------------------------------------------------- Table 1
_T1_COLS = (  # English header (folded) -> (flow, commodity label or None)
    ("non petroleum", None),           # resolved by side: non-petroleum exports / imports
    ("except crude oil", None),
    ("crude oil", "Crude oil"),
    ("liquefied natural gas", "Liquefied natural gas"),
    ("products petroleum", "Petroleum products"),
    ("total exports", "TOTAL"),
    ("total imports", "TOTAL"),
    ("trade valume", "VOLUME"),
    ("trade volume", "VOLUME"),
    ("trade balance", "BALANCE"),
)


def _table1(wb, src: str) -> list[dict]:
    ws = _sheet(wb, "Table 1")
    rows = _rows(ws)
    hdr = None
    for i, r in enumerate(rows[:12]):
        low = [_s(c).lower().replace("-", " ") for c in r]
        if any("total exports" in c for c in low) and any("total imports" in c for c in low):
            hdr = i
            break
    if hdr is None:
        raise ValueError("egypt_capmas_trade: Table 1 header not found")
    low = [re.sub(r"\s+", " ", _s(c).lower().replace("-", " ")) for c in rows[hdr]]
    # Trade volume / balance may sit in the row above (merged two-row header).
    above = [re.sub(r"\s+", " ", _s(c).lower()) for c in rows[hdr - 1]] if hdr else []
    cols: dict[int, tuple[str, str | None]] = {}
    exp_total = next(j for j, c in enumerate(low) if "total exports" in c)
    for j in range(max(len(low), len(above))):
        txt = low[j] if j < len(low) else ""
        if not txt and j < len(above):
            txt = above[j]
        for key, lab in _T1_COLS:
            if key in txt:
                side = "export" if j <= exp_total else "import"
                if lab == "TOTAL":
                    cols[j] = (side, None)
                elif lab == "VOLUME":
                    cols[j] = ("total", None)
                elif lab == "BALANCE":
                    cols[j] = ("balance", None)
                else:                 # product line: the English header as printed
                    cols[j] = (side, re.sub(r"\s+", " ", _s(rows[hdr][j])))
                break
    if not any(v == ("balance", None) for v in cols.values()):
        raise ValueError("egypt_capmas_trade: Table 1 balance column not found")
    out = []
    for r in rows[hdr + 1: hdr + 12]:
        ym = _row_period(r)
        if ym is None:
            continue
        if ym[2]:                     # cumulative January/<month> row
            if ym[1] != 12:
                continue
            period, freq = str(ym[0]), "annual"
        else:
            period, freq = f"{ym[0]}-{ym[1]:02d}", "monthly"
        for j, (flow, com) in cols.items():
            v = _num(r[j]) if j < len(r) else None
            if v is None:
                continue
            out.append(row(tradeflow=flow, period=period, frequency=freq, value=v, unit="USD",
                           unit_multiplier=1e6, commodity=com,
                           commodity_classification="national" if com else "",
                           trade_system="general", series_code="Table 1"))
    if not out:
        raise ValueError(f"egypt_capmas_trade: no Table 1 rows in {src}")
    return out


# ---------------------------------------------------------------- Table 6 (BEC)
def _table6(wb, sheet_letter: str, flow: str, year: int, month: int) -> list[dict]:
    ws = _sheet(wb, "Table", sheet_letter, "6")
    if ws is None:
        return []
    rows = _rows(ws)
    hdr = next((i for i, r in enumerate(rows[:12]) if any(_s(c) == "الكود" for c in r)), None)
    if hdr is None:
        return []
    # Value columns: header cells between the Arabic label and the English label.
    h = [_s(c) for c in rows[hdr]]
    nxt = [_s(c) for c in rows[hdr + 1]] if hdr + 1 < len(rows) else []
    code_j = h.index("الكود")
    vals = []
    for j in range(code_j + 2, len(h)):
        t = (h[j] + " " + (nxt[j] if j < len(nxt) else "")).strip()
        if not t or re.search(r"commodity|code", t, re.I):
            continue
        vals.append((j, "/" in t))
    out = []
    for r in rows[hdr + 1:]:
        code = r[code_j]
        if not isinstance(code, (int, float)) and not _s(code).isdigit():
            continue
        code = str(int(float(code)))
        en = next((_s(c) for c in r[code_j + 2:] if isinstance(c, str) and re.search(r"[A-Za-z]", c)), "")
        label = re.sub(r"^[\sـ-]+", "", en) or re.sub(r"^[\sـ-]+", "", _s(r[code_j + 1]))
        for j, cumulative in vals:
            v = _num(r[j]) if j < len(r) else None
            if v is None:
                continue
            if cumulative and month != 12:
                continue
            period, freq = (str(year), "annual") if cumulative else (f"{year}-{month:02d}", "monthly")
            out.append(row(tradeflow=flow, period=period, frequency=freq, value=v, unit="USD",
                           unit_multiplier=1e6, commodity=label, commodity_classification="bec",
                           commodity_code_nso=code, trade_system="general",
                           series_code=f"Table 6-{sheet_letter}"))
    return out


# ---------------------------------------------------------------- Table 9 (partners)
_GROUP_RX = re.compile(r"total|countr|includ|:|\bother|union|\bunity\b|market|council|"
                       r"^europe|^asia|^africa|^america|^australia and|^oceania|^eastern|^western|"
                       r"^north america|^south america|^latin|^free zone|unknown|not specified", re.I)
_GROUP_AR = re.compile(r"جمل|اجمال|أجمال|إجمال|دول|باقى|باقي|أخرى|اخرى|:")


def _table9(wb, sheet_letter: str, year: int, month: int) -> list[dict]:
    ws = _sheet(wb, "Table", sheet_letter, "9")
    if ws is None:
        return []
    rows = _rows(ws)
    fl_i = next((i for i, r in enumerate(rows[:10])
                 if sum(bool(re.search(r"\b(Exports|Imports)\b", _s(c))) for c in r) >= 2), None)
    if fl_i is None:
        return []
    yr_i = next(i for i in range(fl_i + 1, fl_i + 5)
                if sum(isinstance(c, (int, float)) and 1990 < c < 2100 for c in rows[i]) >= 2)
    per_i = [i for i in range(fl_i, yr_i)]
    blocks = []                       # (start col, flow, cumulative)
    for j, c in enumerate(rows[fl_i]):
        t = _s(c)
        if re.search(r"\bExports\b", t):
            fl = "export"
        elif re.search(r"\bImports\b", t):
            fl = "import"
        else:
            continue
        cum = any("/" in _s(rows[i][j]) for i in per_i if j < len(rows[i]))
        blocks.append((j, fl, cum))
    cols = []                         # (col, flow, period, freq)
    yr_row = rows[yr_i]
    for j0, fl, cum in blocks:
        if cum and month != 12:
            continue
        for j in range(j0, min(j0 + 3, len(yr_row))):
            y = yr_row[j]
            if isinstance(y, (int, float)) and 1990 < y < 2100:
                y = int(y)
                if cum:
                    cols.append((j, fl, str(y), "annual"))
                else:
                    cols.append((j, fl, f"{y}-{month:02d}", "monthly"))
    out = []
    for r in rows[yr_i + 1:]:
        en = ""
        for c in reversed(r):
            if isinstance(c, str) and re.search(r"[A-Za-z]", c):
                en = _s(c)
                break
        ar = next((_s(c) for c in r if isinstance(c, str) and re.search(r"[؀-ۿ]", c)), "")
        if not en and not ar:
            continue
        label = re.sub(r"\s+", " ", re.sub(r"[()×]", " ", en or ar)).strip(" ,:")
        low = label.lower()
        if "%" in (en + ar) or "relative importance" in low:
            continue
        if re.search(r"total (world|trade exchange)|^total$", low):
            continue                  # the world total: taken from Table 1
        if re.match(r"^\s*(source|note|\*)", low) or "data" in low and "validated" in low:
            continue
        is_group = bool(_GROUP_RX.search(label)) or bool(_GROUP_AR.search(ar) and not en) \
            or bool(re.search(r"جمل|اجمال|أجمال|إجمال|وأهمها|:", ar))
        ptype = "group" if is_group else "country"
        for j, fl, period, freq in cols:
            v = _num(r[j]) if j < len(r) else None
            if v is None:
                continue
            out.append(row(tradeflow=fl, period=period, frequency=freq, value=v, unit="USD",
                           unit_multiplier=1e3, partner=label, partner_type=ptype,
                           trade_system="general", series_code=f"Table 9-{sheet_letter}"))
    return out


def parse_rows(path: str) -> tuple[tuple[int, int], list[dict]]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=False)
    try:
        year, month = _issue_period(wb)
        out = _table1(wb, path)
        out += _table6(wb, "A", "export", year, month)
        out += _table6(wb, "B", "import", year, month)
        p9 = _table9(wb, "A", year, month) + _table9(wb, "B", year, month)
        # A partner printed in both 9-A (regions) and 9-B (Arab countries) is
        # one observation; keep the first printing.
        seen = set()
        for r in p9:
            k = (r["tradeflow"], r["partner"], r["period"])
            if k in seen:
                continue
            seen.add(k)
            out.append(r)
        return (year, month), out
    finally:
        wb.close()


def parse(path: str, extras: list[str] | None = None):
    """The primary (latest) workbook plus back issues. Each issue reprints the
    same month of the previous year as validated data, so one key can come
    from two issues: the NEWER issue's figure is kept (a revision replaces the
    provisional figure), which is the rule the standardised layer applies
    across files."""
    import pandas as pd
    from ..schema import KEY
    issues = []
    for p in dict.fromkeys([*(extras or []), path]):
        ym, rows = parse_rows(p)
        issues.append((ym, rows))
    issues.sort(key=lambda t: t[0])
    df = pd.DataFrame([r for _, rows in issues for r in rows])
    return df.drop_duplicates(KEY, keep="last").reset_index(drop=True)
