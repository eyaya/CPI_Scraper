"""Mauritius -- Statistics Mauritius producer price indices (PPI-M, PPI-A).

Two indices, each published as a "Historical Series" workbook on the
By_Subject/Indices page and as a quarterly Economic and Social Indicator (ESI)
workbook:

parse_ppim_hs  HS_PPIM_<q>_<date>.xlsx -- Producer Price Index - Manufacturing.
    T1  1993-2000, base 1993=100 (food, beverages & tobacco only -- the first PPI)
    T2  1998-2005, base 1998    T3 2003-2009, base 2003    T4 2007-2011, base 2007 (NSIC1)
    T5  2007-2015, base 2007 (NSIC2)   T6 2013-2021, base 2013   T7 2018-, base 2018
        -- rows = industry groups (NSIC code, label, weight per mille), columns =
        year x (Jan Feb Mar 1st Qr. Apr ... 4th Qr. Average year).
    T8  1998-2015 quarterly total, base 2007; T9 1998-2021, base 2013; T10 2003-, base 2018
        -- Statistics Mauritius' own back-casts of the total to the newer base.
    T11-T18 monthly + quarterly + yearly average + "Annual change (%)" for the total
        (T11/T12), food & beverages (T13/T14), chemicals (T15/T16), rubber & plastic
        (T17/T18), bases 2013 and 2018, back to 2007 / 2013.
    Where two tables print the SAME cell (T7 and T12 both carry total manufacturing
    2018-), it is emitted once; the run fails if the two printings differ.
parse_ppia_hs  HS_PPIA_<q>_<date>.xls -- Producer Price Index - Agriculture.
    T1/T4  2026 monthly / quarterly by commodity, reference January-December 2025=100
    T2/T5  2018-2025 monthly / quarterly + yearly by commodity, base 2018=100
    T3/T6  the same months re-referenced to 2025=100 by Statistics Mauritius
    T7     quarterly total 1993-, each row with its own reference period column
    T8     monthly total 2000-, reference 2025=100 (the NSO's linked series)
parse_ppim_esi PPIM_<q>_<date>.xlsx (ESI) -- the % changes the historical series
    does not carry: Tab 1(a-c) month-on-month (last three months), Tab 3(a-c)
    quarter-on-quarter and year-on-year (last four quarters), by industry group.
parse_ppia_esi PPIA_<q>_<date>.xlsx (ESI) -- Tab 1 month-on-month and Tab 2
    quarter-on-quarter % changes by commodity.

VALUES AS DISPLAYED. The workbooks hold some cells unrounded (the PPI-A linked
series is stored as 29.83256534177552); each value is rounded to the decimals of
the cell's own number format ("0.0" -> 1), i.e. the figure the NSO publishes. A
trailing footnote marker ("90.5 1" = provisional) is dropped. Weights are per
mille as printed (each table's weights sum to 1000).

CROSS-CHECK (verbatim): PPI-M total May 2026 176.6, April 2026 174.4, May 2025
163.8 (monthly release 29 June 2026); total Jan 2015 93.8 (base 2018, T12);
food 1993 Jan 95.6 (T1); PPI-A Q1 1993 98.5 (1993=100, T7).
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

PPIM = "Producer Price Index - Manufacturing (PPI-M)"
PPIA = "Producer Price Index - Agriculture (PPI-A)"
_MON = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_QTR = re.compile(r"(?i)^\s*(?:average\s+)?([1-4])\s*(?:st|nd|rd|th)\s*(?:qr|quarter)")
_QTR2 = re.compile(r"(?i)^\s*qr\.?\s*([1-4])\s*$")


# ------------------------------------------------------------------ cells ---
def _ndp(fmt: str):
    f = (fmt or "General").split(";")[0]
    if f == "General" or not re.search(r"0", f):
        return None
    m = re.search(r"0\.(0+)", f)
    return len(m.group(1)) if m else 0


def _num(v, fmt=""):
    """The value as displayed; None for blanks/dashes. '90.5 1' -> 90.5."""
    if v is None or v == "":
        return None
    if isinstance(v, str):
        m = re.fullmatch(r"\s*([+-]?\s*\d+(?:\.\d+)?)\s*(?:\d)?\s*", v.replace(" ", " "))
        if not m:
            return None
        v = float(m.group(1).replace(" ", ""))
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    n = _ndp(fmt)
    return round(float(v), n) if n is not None else round(float(v), 10)


def _sheets_xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    out = {}
    for ws in wb:
        out[ws.title] = [[(c.value, c.number_format) for c in r] for r in ws.iter_rows()]
    wb.close()
    return out


def _sheets_xls(path):
    import xlrd
    b = xlrd.open_workbook(path, formatting_info=True)
    out = {}
    for sh in b.sheets():
        g = []
        for i in range(sh.nrows):
            row = []
            for j in range(sh.ncols):
                xf = b.xf_list[sh.cell_xf_index(i, j)]
                fmt = b.format_map[xf.format_key].format_str
                v = sh.cell_value(i, j)
                row.append((v, fmt))
            g.append(row)
        out[sh.name] = g
    b.release_resources()
    return out


def _text(c):
    return str(c[0]).strip() if c and c[0] is not None else ""


def _year(c):
    v = c[0]
    if isinstance(v, (int, float)) and 1980 <= v <= 2100:
        return int(v)
    m = re.fullmatch(r"\s*((?:19|20)\d{2})(?:\.0)?\s*\d?\s*", str(v or ""))
    return int(m.group(1)) if m else None


def _title(g):
    for r in g[:5]:
        for c in r:
            t = _text(c)
            if t.lower().startswith("table"):
                return t
    return ""


def _base(text: str) -> str:
    m = re.search(r"(?i)(?:base (?:period|year)\s*:?\s*(?:year)?\s*((?:19|20)\d{2})\s*=\s*100)", text)
    if m:
        return f"{m.group(1)}=100"
    m = re.search(r"(?i)index reference period\s*:?\s*(January (?:20\d{2} )?to December (20\d{2}))\s*=\s*100", text)
    if m:
        return f"January to December {m.group(2)}=100"
    return ""


def _sheet_base(g) -> str:
    for r in g[:6]:
        for c in r:
            b = _base(_text(c))
            if b:
                return b
    return ""


# ------------------------------------------------------- column decoding ---
def _col_period(label: str, year: int):
    """(frequency, period) for a header cell under `year`."""
    t = label.strip().lower().rstrip(".")
    if t[:3] in _MON and (len(t) <= 4 or t in ("january", "february", "march", "april", "june",
                                                "july", "august", "september", "october",
                                                "november", "december")):
        return "monthly", f"{year}-{_MON[t[:3]]:02d}"
    m = _QTR.match(label) or _QTR2.match(label)
    if m:
        return "quarterly", f"{year}-Q{m.group(1)}"
    if re.match(r"(?i)^(average year|yearly|year)", t):
        return "annual", str(year)
    return None


def _wide(g, index_name, variant, base, label_col=1, code_col=0, weight_col=2, start_col=3):
    """Rows = industries, columns = year groups x (months, quarters, year)."""
    hdr = next(i for i, r in enumerate(g) if any(
        _text(c).lower().rstrip(".") in ("jan", "january") or _QTR.match(_text(c))
        for c in r[start_col:start_col + 2]))
    yr_row = next(i for i in (hdr, hdr - 1, hdr - 2) if any(_year(c) for c in g[i][start_col:]))
    cols, year = {}, None
    for j in range(start_col, len(g[hdr])):
        y = _year(g[yr_row][j]) if j < len(g[yr_row]) else None
        year = y or year
        lab = _text(g[hdr][j])
        if year and lab:
            cp = _col_period(lab, year)
            if cp:
                cols[j] = cp
    # The weights' reference year: printed above the weight column (PPI-A
    # 2025=100 carries 2023 weights), else the base year.
    wyear = next((str(_year(g[i][weight_col])) for i in (hdr, hdr - 1)
                  if weight_col is not None and weight_col < len(g[i]) and _year(g[i][weight_col])),
                 (re.search(r"(?:19|20)\d{2}", base) or re.search(r"", "")).group(0))
    rows = []
    for r in g[hdr + 1:]:
        if len(r) <= label_col:
            continue
        label = re.sub(r"\s+", " ", _text(r[label_col])).strip()
        code = _text(r[code_col]).replace(".0", "") if code_col is not None else ""
        if not label or re.match(r"(?i)^(note|source|\d\s|provisional|back to)", label) or len(label) > 200:
            continue
        got = False
        for j, (freq, per) in cols.items():
            if j >= len(r):
                continue
            v = _num(*r[j])
            if v is None:
                continue
            rows.append(C.row(index_name=index_name, index_variant=variant, industry=label,
                              industry_code_nso=code, period=per, frequency=freq,
                              measure="index", value=v, base_period=base))
            got = True
        if got and weight_col is not None and weight_col < len(r):
            w = _num(*r[weight_col])
            if w is not None:
                rows.append(C.row(index_name=index_name, index_variant=variant, industry=label,
                                  industry_code_nso=code, period=wyear, frequency="annual",
                                  measure="weight", value=w, unit="per_mille", base_period=base))
    return rows


def _by_year(g, index_name, variant, base, industry, code=""):
    """Rows = months / quarter averages / yearly average / annual change, columns = years."""
    hdr = next(i for i, r in enumerate(g) if r and _text(r[0]).lower() in ("month", "quarter", "year"))
    years = {j: _year(c) for j, c in enumerate(g[hdr]) if j > 0 and _year(c)}
    rows = []
    for r in g[hdr + 1:]:
        lab = _text(r[0]) if r else ""
        if not lab:
            continue
        low = lab.lower()
        for j, y in years.items():
            if j >= len(r):
                continue
            v = _num(*r[j])
            if v is None:
                continue
            if low.startswith("annual change"):
                rows.append(C.row(index_name=index_name, index_variant=variant, industry=industry,
                                  industry_code_nso=code, period=str(y), frequency="annual",
                                  measure="inflation_avg", value=v, base_period=base))
                continue
            cp = _col_period(re.sub(r"(?i)^average\s+", "", lab).strip(), y) or (
                ("annual", str(y)) if re.match(r"(?i)^yearly", lab) else None)
            if cp is None and low.startswith("average"):
                cp = _col_period(lab, y)
            if cp is None:
                continue
            rows.append(C.row(index_name=index_name, index_variant=variant, industry=industry,
                              industry_code_nso=code, period=cp[1], frequency=cp[0],
                              measure="index", value=v, base_period=base))
    return rows


DISAGREEMENTS: list = []   # filled by _dedupe; read by the build to write the notes


def _dedupe(rows):
    """Keep one row per key: the FIRST printing, i.e. the industry-detail
    table (T1-T7) over the summary tables (T8-T18). A second printing that
    differs is recorded in DISAGREEMENTS (the NSO's own inconsistency, e.g. T7
    vs T12 for January 2018); more than 2% disagreeing means a misread."""
    seen, out, bad, dup = {}, [], [], 0
    for r in rows:
        k = (r["index_name"], r["industry"], r["frequency"], r["measure"], r["base_period"], r["period"])
        if k in seen:
            dup += 1
            if abs(seen[k] - r["value"]) > 0.051:
                bad.append((k, seen[k], r["value"]))
            continue
        seen[k] = r["value"]
        out.append(r)
    DISAGREEMENTS.extend(bad)
    if dup and len(bad) > 0.02 * dup:
        raise ValueError(f"{len(bad)}/{dup} repeated cell(s) differ, e.g. {bad[:3]}")
    return out


# ------------------------------------------------------------ PPI-M ---
_PPIM_BY_YEAR = {11: ("Total manufacturing", "10-33"), 12: ("Total manufacturing", "10-33"),
                 13: ("Food products and beverages", "10/11"), 14: ("Food products and beverages", "10/11"),
                 15: ("Chemicals and chemical products", "20"), 16: ("Chemicals and chemical products", "20"),
                 17: ("Rubber and plastic products", "22"), 18: ("Rubber and plastic products", "22")}


def _tno(name: str):
    m = re.match(r"\s*T(\d+)", name)
    return int(m.group(1)) if m else None


def parse_ppim_hs(path: str) -> pd.DataFrame:
    sheets = _sheets_xlsx(path)
    rows = []
    for name, g in sheets.items():
        n = _tno(name)
        if n is None:
            continue
        base = _base(_title(g)) or _sheet_base(g) or _base(name.replace("(", " ").replace(")", " "))
        if not base:
            m = re.search(r"Base\s*((?:19|20)\d{2})\s*=\s*100", name)
            base = f"{m.group(1)}=100" if m else ""
        if not base:
            raise ValueError(f"{name}: no base period")
        if n <= 7:
            rows += _wide(g, PPIM, "output", base)
        elif n <= 10:
            rows += _by_year(g, PPIM, "output", base, "Total manufacturing", "10-33")
        else:
            ind, code = _PPIM_BY_YEAR[n]
            rows += _by_year(g, PPIM, "output", base, ind, code)
    rows = _dedupe(rows)
    if len(rows) < 8000:
        raise ValueError(f"only {len(rows)} PPI-M rows from {path}")
    return pd.DataFrame(rows)


# ------------------------------------------------------------ PPI-A ---
def parse_ppia_hs(path: str) -> pd.DataFrame:
    sheets = _sheets_xls(path)
    rows = []
    for name, g in sheets.items():
        m = re.match(r"\s*Table\s*(\d+)", name)
        if not m:
            continue
        n = int(m.group(1))
        base = _sheet_base(g)
        if n in (1, 2, 3, 4, 5, 6):
            if not base:
                raise ValueError(f"{name}: no base")
            # Tables 3/6 carry a linking factor, not a weight, in column 2.
            rows += _wide(g, PPIA, "agriculture", base, label_col=0, code_col=None,
                          weight_col=None if n in (3, 6) else 1, start_col=2)
        elif n == 7:
            hdr = next(i for i, r in enumerate(g) if r and _text(r[0]).lower() == "year")
            for r in g[hdr + 1:]:
                y = _year(r[0]) if r else None
                ref = _text(r[1]) if len(r) > 1 else ""
                if not y or not re.search(r"=\s*100", ref):
                    continue
                ref = re.sub(r"\s*=\s*100", "=100", ref)
                for q in range(1, 5):
                    v = _num(*r[1 + q]) if 1 + q < len(r) else None
                    if v is not None:
                        rows.append(C.row(index_name=PPIA, index_variant="agriculture",
                                          industry="Total", period=f"{y}-Q{q}",
                                          frequency="quarterly", measure="index", value=v,
                                          base_period=ref))
        elif n == 8:
            rows += _by_year(g, PPIA, "agriculture", base, "Total")
    rows = _dedupe(rows)
    if len(rows) < 3000:
        raise ValueError(f"only {len(rows)} PPI-A rows from {path}")
    return pd.DataFrame(rows)


# ------------------------------------------------------------ ESI % changes ---
_CHG = re.compile(r"(?i)([a-z]{3})\w*\s*(\d{2})?\s*to\s*([a-z]{3})\w*\s*(\d{2,4})")
_QCHG = re.compile(r"(?i)([1-4])\s*(?:st|nd|rd|th)\s*qr\s*(\d{2,4})?\s*to\s*([1-4])\s*(?:st|nd|rd|th)\s*qr\s*(\d{2,4})")


def _y(t, default=None):
    if not t:
        return default
    t = int(t)
    return t + 2000 if t < 100 else t


def _changes(g, index_name, variant, base, label_col, code_col, first_col):
    """% change columns, named by their own header ('Mar 26 to Apr 26',
    '2nd Qr 25 to 3rd Qr 25', '1st Qr to 2nd Qr 2026')."""
    out = []
    for i, r in enumerate(g[:10]):
        for j, c in enumerate(r):
            t = re.sub(r"\s+", " ", _text(c))
            m = _CHG.search(t)
            if m and m.group(1).lower() in _MON and m.group(3).lower() in _MON:
                y2 = _y(m.group(4))
                y1 = _y(m.group(2), y2 if _MON[m.group(1).lower()] < _MON[m.group(3).lower()] else y2 - 1)
                k1 = y1 * 12 + _MON[m.group(1).lower()]
                k2 = y2 * 12 + _MON[m.group(3).lower()]
                meas = {1: "inflation_mom", 12: "inflation_yoy"}.get(k2 - k1)
                if meas:
                    out.append((i, j, "monthly", f"{y2}-{_MON[m.group(3).lower()]:02d}", meas))
                continue
            m = _QCHG.search(t)
            if m:
                y2 = _y(m.group(4))
                y1 = _y(m.group(2), y2 if int(m.group(1)) < int(m.group(3)) else y2 - 1)
                lag = (y2 * 4 + int(m.group(3))) - (y1 * 4 + int(m.group(1)))
                meas = {1: "inflation_qoq", 4: "inflation_yoy"}.get(lag)
                if meas:
                    out.append((i, j, "quarterly", f"{y2}-Q{m.group(3)}", meas))
    if not out:
        return []
    # Columns under a "Net contributions" group are not % changes.
    cut = min([j for r in g[:10] for j, c in enumerate(r) if "contribution" in _text(c).lower()
               and not _text(c).lower().startswith("table")] or [10 ** 6])
    out = [o for o in out if o[1] < cut]
    hdr = max(i for i, *_ in out)
    rows = []
    for r in g[hdr + 1:]:
        if len(r) <= label_col:
            continue
        label = re.sub(r"\s+", " ", _text(r[label_col])).strip()
        if not label or re.match(r"(?i)^(note|source|\d\s|provisional|back to)", label):
            continue
        code = _text(r[code_col]).replace(".0", "") if code_col is not None else ""
        for _i, j, freq, per, meas in out:
            if j < len(r):
                v = _num(*r[j])
                if v is not None:
                    rows.append(C.row(index_name=index_name, index_variant=variant, industry=label,
                                      industry_code_nso=code, period=per, frequency=freq,
                                      measure=meas, value=v, base_period=base))
    return rows


def parse_ppim_esi(path: str) -> pd.DataFrame:
    rows = []
    for name, g in _sheets_xlsx(path).items():
        if re.match(r"Tab [13]\(", name):
            rows += _changes(g, PPIM, "output", _sheet_base(g) or "2018=100", 1, 0, 3)
    rows = _dedupe(rows)   # a % change carries its index's base ("Base period: Year 2018=100")
    if len(rows) < 100:
        raise ValueError(f"only {len(rows)} PPI-M change rows from {path}")
    return pd.DataFrame(rows)


def parse_ppia_esi(path: str) -> pd.DataFrame:
    rows = []
    for name, g in _sheets_xlsx(path).items():
        if name.strip() in ("Tab 1", "Tab 2"):
            rows += _changes(g, PPIA, "agriculture", _sheet_base(g), 0, None, 2)   # the sheet's base
    rows = _dedupe(rows)
    if len(rows) < 100:
        raise ValueError(f"only {len(rows)} PPI-A change rows from {path}")
    return pd.DataFrame(rows)


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse_ppia_esi = carry_base(parse_ppia_esi)
parse_ppia_hs = carry_base(parse_ppia_hs)
parse_ppim_esi = carry_base(parse_ppim_esi)
parse_ppim_hs = carry_base(parse_ppim_hs)
