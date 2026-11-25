"""Parser for NBS Seychelles quarterly "Merchandise Trade" statistical bulletins (PDF, text layer).

One bulletin per quarter (2020-Q1 onward on www.nbs.gov.sc/downloads, category
"Merchandise Trade"), values in thousand rupees (R'000) unless a table says
"SR million". Read from the text layer, line by line:

  Table 1a  Summary of external trade: annual and quarterly imports (c.i.f),
            domestic exports (f.o.b), re-exports (f.o.b) and the balance of
            trade (= domestic exports + re-exports - imports, as printed).
            The column order is checked on every row against that printed
            identity; a bulletin whose rows break it is refused.
  Table 2a  Imports by "HS section and division", quarterly (the NSO's own
            grouping: section aggregates and HS chapters by name, no codes
            printed) -> national product list.
  Table 3   Imports by country of origin; Table 4b domestic exports by country of
            destination: only the full-year ("Jan - Dec") and first-quarter
            ("Jan-Mar") columns -- Jan-Jun / Jan-Sep are year-to-date, not a
            schema period. "Others" is a group.
  Table 5   Re-exports of petroleum products / other re-exports, annual and
            quarterly (national product list).
  Table 6   Imports / domestic exports by economic community (EU, IOC, COMESA,
            SADC, ASEAN), full-year and Jan-Mar columns only (groups).
Not read: Table 1b and 2b (Jan-<month> year-to-date in SR million), Table 4a
(major domestic export products by destination -- a product x partner matrix
with quantities), the charts. Totals are taken from Table 1a only. A row whose
number tokens do not match the table's column count (a figure split by a stray
space, "2 ,210,654") is dropped, never repaired.
"""
from __future__ import annotations

import re

import pandas as pd

from ._common import row

_NUM = re.compile(r"^\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?$|^-?\d+(?:\.\d+)?$")
_UNIT, _MULT = "SCR", 1e3


def _lines(path: str) -> list[str]:
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            out.append("<<PAGE>>")
            out.extend((pg.extract_text() or "").split("\n"))
    return out


def _split(line: str):
    """(label, [numeric tokens], [pct tokens]) of a table line."""
    toks = line.split()
    nums, pcts = [], []
    i = len(toks)
    while i > 0:
        t = toks[i - 1]
        if t.endswith("%") and _NUM.match(t[:-1].replace("-", "") or "x"):
            pcts.insert(0, t)
        elif _NUM.match(t):
            nums.insert(0, t)
        else:
            break
        i -= 1
    return " ".join(toks[:i]).strip(), nums, pcts


def _val(t: str) -> float:
    neg = t.startswith("(") or t.startswith("-")
    v = float(t.strip("()-").replace(",", ""))
    return -v if neg else v


def _find(lines, rx, start=0):
    # Case-sensitive: table titles are upper case; the contents page repeats
    # them in title case and must not match.
    r = re.compile(rx)
    return next((i for i in range(start, len(lines)) if r.search(lines[i])), None)


# ------------------------------------------------------------------ Table 1a
def _table1a(lines) -> list[dict]:
    i = _find(lines, r"SUMMARY OF EXTERNAL TRADE")
    if i is None:
        return []
    out, year = [], None
    for ln in lines[i + 1:]:
        if ln.startswith("Source") or ln == "<<PAGE>>":
            break
        lab, nums, _ = _split(ln)
        m_year = re.match(r"^(\d{4})\s*(\(\d\))?$", lab)
        m_q = re.match(r"^Q([1-4])$", lab)
        if not nums:
            if re.match(r"^\d{4}\s*(\(\d\))?$", ln.strip()):
                year = int(ln.strip()[:4])
            continue
        if len(nums) == 5 and re.match(r"^\d{4}$", nums[0]) and not lab:
            m_year, lab, nums = re.match(r"^(\d{4})$", nums[0]), nums[0], nums[1:]
        if len(nums) != 4:
            continue
        if m_year:
            period, freq = m_year.group(1), "annual"
        elif m_q and year:
            period, freq = f"{year}-Q{m_q.group(1)}", "quarterly"
        else:
            continue
        imp, dom, rex, bal = (_val(t) for t in nums)
        if abs((dom + rex - imp) - bal) > 2:
            raise ValueError(f"seychelles_nbs_trade: Table 1a row {ln!r} breaks "
                             f"balance = domestic exports + re-exports - imports")
        for flow, v, basis in (("import", imp, "cif"), ("domestic_export", dom, "fob"),
                               ("re_export", rex, "fob"), ("balance", bal, "")):
            out.append(row(tradeflow=flow, period=period, frequency=freq, value=v, unit=_UNIT,
                           unit_multiplier=_MULT, price_basis=basis, trade_system="general",
                           series_code="Table 1a"))
    return out


# ------------------------------------------------------------------ Table 2a
def _quarter_cols(year_line: str, q_line: str):
    years = [int(y) for y in re.findall(r"\b(20\d\d)\b", year_line)]
    qs = [int(q) for q in re.findall(r"\bQ([1-4])\b", q_line)]
    out, yi, prev = [], 0, 0
    for q in qs:
        if q <= prev:
            yi += 1
        prev = q
        if yi >= len(years):
            return []
        out.append(f"{years[yi]}-Q{q}")
    return out


def _table2a(lines) -> list[dict]:
    out = []
    i = _find(lines, r"VALUE OF IMPORTS BY HS SECTION")
    if i is None:
        return out
    cols, buf = [], []
    for k in range(i + 1, len(lines)):
        ln = lines[k].strip()
        if re.search(r"^Table 2b|VALUE OF IMPORTS BY MAJOR SECTIONS", ln, re.I):
            break
        if ln == "<<PAGE>>" or ln.startswith("Table 2a") or ln.startswith("Source") \
                or ln.startswith("Notes"):
            buf = []
            continue
        if ln.startswith("HS Section and Division"):
            nxt = lines[k + 1] if k + 1 < len(lines) else ""
            c = _quarter_cols(ln, nxt)
            if c:
                cols = c
            buf = []
            continue
        if re.match(r"^(Q[1-4]\s*)+$", ln) or ln.startswith("(Reserved"):
            buf = []
            continue
        lab, nums, _ = _split(ln)
        if not nums:
            buf.append(ln)
            continue
        label = re.sub(r"\s+", " ", " ".join(buf + [lab])).strip().rstrip(".")
        buf = []
        if not label or label.upper() == "TOTAL" or not cols or len(nums) != len(cols):
            continue
        for period, t in zip(cols, nums):
            out.append(row(tradeflow="import", period=period, frequency="quarterly", value=_val(t),
                           unit=_UNIT, unit_multiplier=_MULT, commodity=label,
                           commodity_classification="national", price_basis="cif",
                           trade_system="general", series_code="Table 2a"))
    return out


# ------------------------------------------------------------------ Tables 3, 4b, 6
def _ytd_period(lab: str, year: int):
    t = re.sub(r"\s+", "", lab).lower()
    if t in ("jan-dec", "january-december"):
        return str(year), "annual"
    if t in ("jan-mar", "january-march"):
        return f"{year}-Q1", "quarterly"
    return None


def _period_header(year_line: str, per_line: str):
    years = [int(y) for y in re.findall(r"\b(20\d\d)\b", year_line)]
    pers = re.findall(r"Jan\s*-\s*[A-Za-z]{3}", per_line)
    if not years or len(pers) % len(years):
        return None
    reps = len(pers) // len(years)
    years = [y for y in years for _ in range(1)] * reps if reps > 1 else years
    return [_ytd_period(p, y) for p, y in zip(pers, years)]


def _country_table(lines, title_rx: str, flow: str, table: str) -> list[dict]:
    i = _find(lines, title_rx)
    if i is None:
        return []
    hdr = _find(lines, r"^Country\b", i)
    if hdr is None or hdr > i + 6:
        return []
    cols = _period_header(lines[hdr], lines[hdr + 1])
    if not cols:
        return []
    out = []
    for ln in lines[hdr + 2:]:
        if ln.startswith("Source") or ln == "<<PAGE>>":
            break
        lab, nums, pcts = _split(ln)
        lab = re.sub(r"[”\"]\d$", "", lab).strip()
        if not lab or lab.lower() == "total" or len(nums) != len(cols):
            continue
        ptype = "group" if lab.lower() in ("others", "other") else "country"
        for per, t in zip(cols, nums):
            if per is None:
                continue
            out.append(row(tradeflow=flow, period=per[0], frequency=per[1], value=_val(t), unit=_UNIT,
                           unit_multiplier=_MULT, partner=lab, partner_type=ptype,
                           price_basis="cif" if flow == "import" else "fob",
                           trade_system="general", series_code=table))
    return out


def _table6(lines) -> list[dict]:
    i = _find(lines, r"TRADE WITH SELECTED ECONOMIC COMMUNITIES")
    if i is None:
        return []
    yl = _find(lines, r"^\s*20\d\d", i)
    if yl is None or yl > i + 5:
        return []
    years = [int(y) for y in re.findall(r"\b(20\d\d)\b", lines[yl])]
    pers = re.findall(r"Jan\s*-\s*[A-Za-z]{3}", lines[yl + 1])
    if len(years) != len(pers) or len(years) % 2:
        return []
    half = len(years) // 2
    cols = []
    for j, (y, p) in enumerate(zip(years, pers)):
        cols.append((("import" if j < half else "domestic_export"), _ytd_period(p, y)))
    out = []
    for ln in lines[yl + 2:]:
        if ln.startswith("Percentage") or ln.startswith("Source") or ln == "<<PAGE>>":
            break
        lab, nums, _ = _split(ln)
        if not lab or re.search(r"total", lab, re.I) or len(nums) != len(cols):
            continue
        for (flow, per), t in zip(cols, nums):
            if per is None:
                continue
            out.append(row(tradeflow=flow, period=per[0], frequency=per[1], value=_val(t), unit=_UNIT,
                           unit_multiplier=_MULT, partner=lab, partner_type="group",
                           price_basis="cif" if flow == "import" else "fob",
                           trade_system="general", series_code="Table 6"))
    return out


# ------------------------------------------------------------------ Table 5
def _table5(lines) -> list[dict]:
    i = _find(lines, r"VALUE OF RE.?EXPORTS")
    if i is None:
        return []
    hl = _find(lines, r"^\s*20\d\d", i)
    if hl is None or hl > i + 5:
        return []
    cols = []
    for m in re.finditer(r"(20\d\d)(?:\s*\(\d\))?(?:\s+Q([1-4]))?", lines[hl]):
        cols.append((f"{m.group(1)}-Q{m.group(2)}", "quarterly") if m.group(2) else (m.group(1), "annual"))
    out = []
    for ln in lines[hl + 1:]:
        if ln.startswith("Source") or ln == "<<PAGE>>" or ln.startswith("TRADE WITH"):
            break
        lab, nums, _ = _split(ln)
        if not lab or lab.lower() == "total" or len(nums) != len(cols):
            continue
        lab = re.sub(r"\s*-\s*", "-", lab)
        for (per, freq), t in zip(cols, nums):
            out.append(row(tradeflow="re_export", period=per, frequency=freq, value=_val(t), unit=_UNIT,
                           unit_multiplier=_MULT, commodity=lab, commodity_classification="national",
                           price_basis="fob", trade_system="general", series_code="Table 5"))
    return out


def parse_rows(path: str) -> list[dict]:
    lines = _lines(path)
    out = _table1a(lines)
    if not out:
        raise ValueError(f"seychelles_nbs_trade: no Table 1a in {path}")
    out += _table2a(lines)
    out += _country_table(lines, r"VALUE OF IMPORTS\s*\(?(?:cif|CIF)\)? BY COUNTRY", "import", "Table 3")
    out += _country_table(lines, r"VALUE OF DOMESTIC EXPORTS.*BY COUNTRY", "domestic_export", "Table 4b")
    out += _table5(lines)
    out += _table6(lines)
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """Latest bulletin plus back issues, oldest first; where two bulletins print
    one figure (provisional, then revised) the newer bulletin's value is kept."""
    from ..schema import KEY
    frames = []
    for p in dict.fromkeys([*(extras or []), path]):
        df = pd.DataFrame(parse_rows(p))
        q = df.loc[df["frequency"] == "quarterly", "period"]
        frames.append((q.max() if len(q) else df["period"].max(), df))
    frames.sort(key=lambda t: t[0])
    df = pd.concat([f for _, f in frames], ignore_index=True)
    return df.drop_duplicates(KEY, keep="last").reset_index(drop=True)


# ------------------------------------------------------------------ time series workbook
_SERIES_SHEETS = {"imports": ("import", "cif"), "exports": ("domestic_export", "fob"),
                  "re-exports": ("re_export", "fob")}


def parse_series(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """NBS "Merchandise Trade Statistics Series" workbook (.xls): monthly values
    (thousand rupees) from January 2009, one sheet per flow -- Imports (c.i.f),
    Exports (= domestic exports, f.o.b; the sheet title says "VALUE OF DOMESTICS
    EXPORTS"), Re-Exports (f.o.b) -- by HS section (the NSO's grouped sections,
    no code printed -> national) and HS chapter (two-digit code -> hs2), plus
    the TOTAL (all products). A label wrapped onto a second row carries the
    figures on that second row. Other sheets (scratch copies of one month) are
    not read."""
    import xlrd
    book = xlrd.open_workbook(path)
    out = []
    try:
        for sh in book.sheets():
            spec = _SERIES_SHEETS.get(sh.name.strip().lower())
            if not spec:
                continue
            flow, basis = spec
            cols = None
            pend = None               # (kind, code, label) awaiting its figures
            for i in range(sh.nrows):
                r = sh.row_values(i)
                dates = [(j, v) for j, v in enumerate(r) if isinstance(v, float) and 30000 < v < 60000 and j >= 2]
                if len(dates) >= 6 and not any(isinstance(v, str) and v.strip() for v in r[:2]):
                    c = [(j, "%04d-%02d" % xlrd.xldate_as_tuple(v, book.datemode)[:2]) for j, v in dates]
                    if cols is None:
                        cols = c
                    elif c != cols:
                        # The header is repeated at every page break; a column
                        # dated differently by two copies (Exports: the last two
                        # columns read Apr/May 2025 in one, May/Jun in another)
                        # cannot be dated, so it is dropped.
                        other = dict(c)
                        cols = [(j, per) for j, per in cols if other.get(j) == per]
                    pend = None
                    continue
                if cols is None:
                    continue
                code, label = r[0], str(r[1]).strip() if len(r) > 1 else ""
                vals = [(per, r[j]) for j, per in cols if j < len(r) and isinstance(r[j], float)]
                if isinstance(code, str) and re.fullmatch(r"\d{2}", code.strip()):
                    kind, code = "hs2", code.strip()
                elif isinstance(code, float) and code >= 10:
                    kind, code = "hs2", str(int(code))      # chapters 32 and 55 are stored as numbers
                elif isinstance(code, float):
                    kind, code = "section", ""              # sections are numbered 0-9
                elif label.upper() == "TOTAL":
                    kind, code = "total", ""
                elif label and not code and pend:
                    kind, code, label = pend[0], pend[1], (pend[2] + " " + label)
                else:
                    pend = None
                    continue
                if not vals:
                    pend = (kind, code, label)
                    continue
                pend = None
                label = re.sub(r"\s+", " ", label).strip().rstrip(".")
                for per, v in vals:
                    kw = dict(tradeflow=flow, period=per, frequency="monthly", value=v, unit=_UNIT,
                              unit_multiplier=_MULT, price_basis=basis, trade_system="general",
                              series_code=f"Series: {sh.name.strip()}")
                    if kind == "total":
                        out.append(row(**kw))
                    elif kind == "hs2":
                        out.append(row(**kw, commodity=label, commodity_classification="hs2",
                                       commodity_code_nso=code))
                    else:
                        out.append(row(**kw, commodity=label, commodity_classification="national"))
    finally:
        book.release_resources()
    return pd.DataFrame(out)
