"""Mauritius -- Statistics Mauritius "Historical Series on Labour", 1990-2025.

The workbook HS_Labour_Yr90-Yr25_<ddmmyy>.xls, linked from the Labour subject
page. It is the BACK-SERIES of employment composition: employment by industry
and sex for every year 1990-2025, and by broad sector.

A DIFFERENT SERIES FROM THE CMPHS QUARTERLY ROWS (parsers/mauritius_labour.py).
These are Statistics Mauritius's RECONCILED employment estimates -- the
workbook's own note: "worked out in order to give a set of comparable
employment estimates obtained from different sources": CMPHS for employed
Mauritians, the March Survey of Employment and Earnings for large
establishments (10+ persons, foreign workers included), and a reconciliation
of CMPHS, SEE and administrative sources for the rest. They INCLUDE FOREIGN
WORKERS; the CMPHS quarterly figures do not. `survey` names the series, and the
periods are annual (the CMPHS rows are quarterly), so the two never share a key.

Read:
* Tables 1.2(a)-(f), employment by industrial group and sex ('000), one sheet
  per classification era -- each era keeps ITS OWN labels and classification,
  never mapped onto another's:
      1990-1994  ISIC Rev.2 (sheet note: "Revision 2 of 1968")
      1995-2006  NSIC, "an adaptation of ... ISIC Rev. 3"     -> National
      2007-2025  NSIC Rev 2, "an adaptation of ... ISIC Rev. 4" -> National
  (NSIC is filed as National, as the CMPHS rows file it.)
* Table 1.4, employment by sex and sector (Primary / Secondary / Tertiary, the
  sheet's own grouping), counts. Its Total column repeats Table 1.2's Total for
  the same year and sex; it is CHECKED equal and not filed twice.
* Table 1.5, the sector percentages of total employment. Its count columns
  repeat Table 1.4 and are not re-filed.

SUB-ROWS. The industry tables print sub-items under their parent (Sugarcane /
Other under agriculture; Sugar, EPZ, Food, Textiles, Other under manufacturing;
central / local government under community services). The same printed label
("Other") sits under two parents, so a sub-item is filed as
"<parent> - <label as printed>". Nothing is summed or re-derived.

WORKING-AGE BASE. Table 1.4 note 3: "Employment figures refer to population
aged 16 years & over for years 2000 onwards"; Table 1.3(a) note (c) gives
"population aged 12 years and above" for the early years. So 1990-1999 rows
carry 12+ and 2000 onwards 16+ -- as stated, not harmonised.

AS DISPLAYED. Several cells hold unrounded reconciliation output
(15.35504750593824) under a 0.0 number format; the published figure is the
displayed one, so values are rounded to their cell's format.

PERIOD MARKERS. Year headers carry footnote digits ("2022 1" = revised to the
2022 Census population, "2025 2" = provisional); they go to reference_period.

NOT READ: Tables 1.3(a)-(f), employment by industry and SIZE OF ESTABLISHMENT
(large / other) -- the schema has no establishment-size dimension, and filing
"large establishments" as an industry category would bend it.
"""
from __future__ import annotations
import re

import pandas as pd
import xlrd

from . import _common as C

SURVEY = ("Historical Series on Labour -- reconciled employment estimates "
          "(CMPHS, SEE and administrative sources; incl. foreign workers)")
UNIT = "thousand_persons"

_SEX = {"male": "male", "female": "female", "b. sexes": "total",
        "both sexes": "total", "total": "total"}

# era sheets: (sheet-name prefix, classification, series code)
_INDUSTRY_SHEETS = [
    ("T1.2(a)", "ISIC Rev.2", "HS T1.2(a)"),
    ("T1.2(b)", "National", "HS T1.2(b)"),
    ("T1.2(c)", "National", "HS T1.2(c)"),
    ("T1.2(d)", "National", "HS T1.2(d)"),
    ("T1.2(e)", "National", "HS T1.2(e)"),
    ("T1.2(f)", "National", "HS T1.2(f)"),
]

# Printed sub-item labels (lower-cased, whitespace-collapsed) -> they belong to
# the most recent top-level row above them.
_CHILDREN = {
    "of which sugar cane", "sugar cane", "sugarcane", "agriculture(non-sugar)",
    "non sugar", "other", "of which sugar", "sugar", "epz",
    "manufacturing(non-epz & non-sugar)", "non-epz & non-sugar", "food",
    "textiles", "food (including sugar)", "of which : central government",
    "local government",
}

# PUBLISHED, PINNED (never corrected): Table 1.4's employment totals for
# 2003-2004 differ from Table 1.2(c)'s. Table 1.4 agrees with Table 1.1
# (2003: 490.2 = 326.8 + 163.4); the industry table prints 491.7. Only Table
# 1.2's total is filed (as the industry Total); Table 1.4's is not re-filed.
# Table 1.2(c)'s own 2003 industries sum 1.5 below its printed Total (female
# 1.7) -- i.e. to Table 1.4's figure: the printed 1.2(c) Total is the odd one.
# (year, sex, Table 1.4, Table 1.2)
_KNOWN_TOTAL_GAPS = {
    ("2003", "male", 326.8, 326.6), ("2003", "female", 163.4, 165.1),
    ("2003", "total", 490.2, 491.7), ("2004", "male", 329.3, 329.4),
    ("2004", "female", 163.5, 163.4),
}

_MARKERS = {"1": "revised estimate (2022 Population Census basis)",
            "2": "provisional"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def _sheet(book, prefix: str):
    for sh in book.sheets():
        if sh.name.replace(" ", "").startswith(prefix.replace(" ", "")):
            return sh
    raise ValueError(f"mauritius_hs_labour: no sheet starting {prefix!r}; "
                     f"the workbook holds {book.sheet_names()}")


def _decimals(book, cell) -> int | None:
    fmt = book.format_map[book.xf_list[cell.xf_index].format_key].format_str
    m = re.search(r"0\.(0+)", fmt)
    if m:
        return len(m.group(1))
    if re.search(r"(^|[^.])0(?!\.)", fmt) and "." not in fmt:
        return 0
    return None


def _num(book, sh, r, c):
    """The DISPLAYED number in a cell, or None (blank, '...', 'Napp')."""
    if r >= sh.nrows or c >= sh.ncols:
        return None
    cell = sh.cell(r, c)
    if cell.ctype != xlrd.XL_CELL_NUMBER:
        return None
    d = _decimals(book, cell)
    return round(cell.value, d) if d is not None else float(cell.value)


def _year(v) -> tuple[str, str] | None:
    """'2022 1' -> ('2022', '2022 (revised ...)'); 1990.0 -> ('1990', '1990')."""
    if isinstance(v, float):
        if v.is_integer() and 1980 <= v <= 2100:
            return str(int(v)), str(int(v))
        return None
    m = re.match(r"^\s*((?:19|20)\d\d)(?:\s+(\d))?\s*$", str(v))
    if not m:
        return None
    y, mark = m.group(1), m.group(2)
    if mark:
        if mark not in _MARKERS:
            raise ValueError(f"mauritius_hs_labour: unknown year marker {v!r}")
        return y, f"{y} ({_MARKERS[mark]})"
    return y, y


def _base(year: str) -> str:
    return "12+" if int(year) < 2000 else "16+"


def _industry(book, prefix, classification, code) -> tuple[list[dict], dict]:
    sh = _sheet(book, prefix)
    # Header: the row whose first cell names the industry column; years on it,
    # sexes on the next row.
    hdr = next(r for r in range(sh.nrows)
               if "industr" in str(sh.cell_value(r, 0)).lower()
               and str(sh.cell_value(r, 0)).lower().strip() != ""
               and not str(sh.cell_value(r, 0)).lower().startswith("table"))
    # Columns come in Male / Female / Both-sexes groups, one per year. The
    # year label is printed over the FIRST column of its group on most sheets
    # but over the MIDDLE one on 1990-94, so a group is delimited by its
    # "Male" column and takes whichever year its header cells carry.
    groups: list[list[tuple[int, str]]] = []
    for c in range(1, sh.ncols):
        sex = _SEX.get(_norm(sh.cell_value(hdr + 1, c)).lower())
        if not sex:
            continue
        if sex == "male" or not groups:
            groups.append([])
        groups[-1].append((c, sex))
    cols: dict[int, tuple[str, str, str]] = {}
    for g in groups:
        ys = [y for c, _ in g if sh.cell_value(hdr, c) != ""
              for y in [_year(sh.cell_value(hdr, c))] if y]
        if len(ys) != 1 or len(g) != 3:
            raise ValueError(f"mauritius_hs_labour: {sh.name}: column group "
                             f"{[c for c, _ in g]} has years {ys}")
        for c, sex in g:
            cols[c] = (ys[0][0], ys[0][1], sex)
    if not cols:
        raise ValueError(f"mauritius_hs_labour: {sh.name}: no year/sex columns")

    rows, totals = [], {}
    parent = None
    pending = ""            # a label wrapped onto the next line (1990-94)
    for r in range(hdr + 2, sh.nrows):
        raw = sh.cell_value(r, 0)
        label = _norm(raw) if isinstance(raw, str) else ""
        vals = {c: _num(book, sh, r, c) for c in cols}
        have = any(v is not None for v in vals.values())
        if not have:
            if label and not label.lower().startswith(("note", "1 ", "(")):
                pending = (pending + " " + label).strip()
            continue
        if not label and not pending:
            continue
        label = _norm((pending + " " + label).strip()) if pending else label
        pending = ""
        low = label.lower()
        if low == "total":
            char = "Total"
        elif low in _CHILDREN and parent:
            char = f"{parent} - {label}"
        else:
            parent, char = label, label
        for c, (y, ref, sex) in cols.items():
            v = vals[c]
            if v is None:
                continue
            if char == "Total":
                totals[(y, sex)] = v
            rows.append(C.row(
                topic="industry", characteristic=char,
                classification=classification, value=v, survey=SURVEY,
                period=y, reference_period=ref, frequency="annual",
                measure="count", unit=UNIT, sex=sex,
                working_age_base=_base(y), series_code=code))
    if not totals:
        raise ValueError(f"mauritius_hs_labour: {sh.name}: no Total row")
    return rows, totals


def _sector_counts(book, totals) -> list[dict]:
    """Table 1.4: a year row, then Male / Female / Both Sexes rows."""
    sh = _sheet(book, "T1.4")
    hdr = next(r for r in range(sh.nrows)
               if _norm(sh.cell_value(r, 3)).lower() == "primary")
    names = {c: _norm(sh.cell_value(hdr, c)) for c in range(3, sh.ncols)
             if _norm(sh.cell_value(hdr, c))}
    rows, year, gaps = [], None, set()
    for r in range(hdr + 1, sh.nrows):
        y = _year(sh.cell_value(r, 0)) if sh.cell_value(r, 0) != "" else None
        if y:
            year = y
            continue
        sex = _SEX.get(_norm(sh.cell_value(r, 2)).lower())
        if not (year and sex):
            continue
        for c, name in names.items():
            v = _num(book, sh, r, c)
            if v is None:
                continue
            if name.lower() == "total":
                want = totals.get((year[0], sex))
                if want is None or abs(want - v) > 0.05:
                    gaps.add((year[0], sex, v, want))
                continue
            rows.append(C.row(
                topic="industry", characteristic=name, classification="National",
                value=v, survey=SURVEY, period=year[0], reference_period=year[1],
                frequency="annual", measure="count", unit=UNIT, sex=sex,
                working_age_base=_base(year[0]), series_code="HS T1.4"))
    if gaps != _KNOWN_TOTAL_GAPS:
        raise ValueError(f"mauritius_hs_labour: Table 1.4 vs 1.2 totals changed: "
                         f"new {sorted(gaps - _KNOWN_TOTAL_GAPS)}, gone "
                         f"{sorted(_KNOWN_TOTAL_GAPS - gaps)}")
    return rows


def _sector_shares(book) -> list[dict]:
    """Table 1.5: per sector an Employment ('000) and a Percentage column."""
    sh = _sheet(book, "T1.5")
    hdr = next(r for r in range(sh.nrows)
               if _norm(sh.cell_value(r, 1)).lower() == "primary")
    pct_cols = {}
    for c in range(1, sh.ncols):
        if _norm(sh.cell_value(hdr + 1, c)).lower() == "percentage":
            pct_cols[c] = _norm(sh.cell_value(hdr, c - 1))
    if set(pct_cols.values()) != {"Primary", "Secondary", "Tertiary"}:
        raise ValueError(f"mauritius_hs_labour: Table 1.5 columns {pct_cols}")
    rows = []
    for r in range(hdr + 2, sh.nrows):
        y = _year(sh.cell_value(r, 0)) if sh.cell_value(r, 0) != "" else None
        if not y:
            continue
        for c, name in pct_cols.items():
            v = _num(book, sh, r, c)
            if v is None:
                continue
            rows.append(C.row(
                topic="industry", characteristic=name, classification="National",
                value=v, survey=SURVEY, period=y[0], reference_period=y[1],
                frequency="annual", measure="share", unit="percent",
                sex="total", working_age_base=_base(y[0]),
                series_code="HS T1.5"))
    return rows


def parse(local_path: str) -> pd.DataFrame:
    book = xlrd.open_workbook(local_path, formatting_info=True)
    rows, totals = [], {}
    for prefix, cls, code in _INDUSTRY_SHEETS:
        got, tot = _industry(book, prefix, cls, code)
        overlap = set(tot) & set(totals)
        if overlap:
            raise ValueError(f"mauritius_hs_labour: {prefix} repeats years "
                             f"{sorted(overlap)[:3]} of another era sheet")
        rows += got
        totals.update(tot)
    years = sorted({y for y, _ in totals})
    if years[0] != "1990" or len(years) != int(years[-1]) - 1989:
        raise ValueError(f"mauritius_hs_labour: industry years {years[0]}.."
                         f"{years[-1]} ({len(years)}) are not a 1990.. run")
    rows += _sector_counts(book, totals)
    rows += _sector_shares(book)
    return pd.DataFrame.from_records(rows)
