"""Eswatini — Central Statistical Office (CSO) national accounts.

THE CSO'S OWN FILES, REACHED THROUGH THE WAYBACK MACHINE. The CSO publishes on
gov.sz (/images/planningministry/...), which times out from here, and
eswatinistats.org.sz never answers. The Wayback Machine holds `id_` captures --
the original bytes -- of two CSO files, which is the route DR Congo, Congo,
Benin and Sudan already use. Switch the descriptor back to gov.sz once it
answers.

* QGDP Tables 2013Q1-2025Q4.xls (primary; captured 2026-05-17, saved by CSO
  staff April 2026) -- PRODUCTION approach, QUARTERLY 2013 Q1 to 2025 Q4:
  levels at current and constant prices (E million) for 29 activities, the
  primary / secondary / tertiary sector subtotals, "Total: All industries",
  taxes on products and GDP, plus SEASONALLY ADJUSTED GDP; shares of GDP,
  year-on-year growth and contributions to growth.
* Eswatini Rebased GDP Report 2023 (extra) -- ANNUAL 2013-2023, Annexures 1
  and 2: production (A1.1-A1.5) and EXPENDITURE (A2.1-A2.5) approaches, levels
  at current and constant 2019 prices, shares, growth, contributions (A1.5)
  and implicit deflators (A2.5).

CONSTANT PRICES ARE 2019 PRICES. The rebased report: "real gross domestic
product (GDP) is now measured at constant 2019 prices from 2011 prices". The
workbook says only "constant prices"; it is the rebased series (its quarters
are the report's base, and 2019 current = constant in the report's annual
tables).

PERCENT CELLS. The workbook stores shares, growth and contributions as
fractions under a % number format (`0.0%`, `0.00%`); the published figure is
the percent, so the value is the cell x 100 -- the same convention as
`burkina_insd_gdp` / `rwanda_nisr_gdp`, a unit of display, not a computation.
The report prints them as "8.4%"; its deflators are index numbers (2019=100).

TRAP -- A2.4's HEADER LISTS ELEVEN YEARS (2013-2023) OVER TEN VALUES. The
values are 2014-2023 (growth needs a prior year, and A1.4 heads the same ten
years). The parser takes the LAST n header years for a row of n values and
proves the alignment every run against the report's own levels: final
consumption 2014 at constant prices, 48 242 / 50 177 - 1 = -3,9% printed.

LABELS. "Goods" and "Services" appear under both exports and imports, so
they are qualified ("Exports of goods and services: Goods"). Everything else
is the CSO's wording as printed, including spellings that differ between
tables ("Public administration and defence; social security" in A1.1,
"...; compulsory social security" elsewhere) -- they are separate tables and
`price_basis` keeps them apart. Negative values print in parentheses.

IDENTITIES checked every run (to the table's rounding): in every level table
the sector subtotals equal the sum of their activities, the three sectors sum
to "Total: All industries", and total + taxes on products = GDP; in the
expenditure tables consumption + capital formation + net exports = GDP by
expenditure, and that plus the published discrepancy = GDP by economic
activity. The quarterly workbook's GDP for each year is NOT compared with the
report's annual GDP: they are different vintages (2026 vs 2025).

NOT COLLECTED: the A2.3 shares row for the discrepancy (a balancing item, not
a share of expenditure); blank growth/deflator cells of the discrepancy row.

CROSS-CHECK (as printed): quarterly GDP 2025 Q4 current 25 170.0 E million,
SA 23 565.9; annual GDP 2023 current 84 964, constant 70 126; GDP growth 2023
3.4%; manufacturing share 2023 29.4%; GDP-by-expenditure deflator 2023 118.96.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber
import xlrd

_C = {"geography": "Total country"}
_SECTORS = {
    "Primary sector": ["Agriculture and forestry", "Mining and quarrying"],
    "Secondary sector": ["Manufacturing", "Electricity supply",
                         "Water and sewerage; waste collection", "Construction"],
}
_SUBACTIVITIES = {  # children printed under a parent activity
    "Agriculture and forestry": ["Growing of crops", "Animal production",
                                 "Support activities to agriculture", "Forestry"],
    "Financial and insurance activities": [
        "Financial service activities, except insurance",
        "Insurance and pension funding",
        "Activities auxiliary to financial services"],
    "Real estate activities": ["Real estate activities, market",
                               "Owner-occupied dwellings"],
}
_CHILDREN = {c for v in _SUBACTIVITIES.values() for c in v}


def _row(**kw) -> dict:
    base = {"category_group": "", "series_code": "", "geography": "Total country",
            "seasonal_adjustment": "nsa", "base_period": ""}
    base.update(kw)
    return base


# ---------------------------------------------------------------- quarterly

_SHEETS = {  # sheet -> (price_basis, measure, unit)
    "Current prices": ("current", "level", "E million"),
    "Constant prices": ("constant", "level", "E million"),
    "Shares to GDP": ("current", "share", "percent"),
    "Growth rates": ("constant", "growth_yoy", "percent"),
    "Contribution to growth": ("constant", "contribution", "percentage points"),
}


def _check_levels(vals: dict[str, float], where: str, tol: float) -> None:
    """Sector subtotals, all industries and GDP, for one period column."""
    tertiary = [k for k in vals if k not in _CHILDREN and k not in _SECTORS
                and k not in sum(_SECTORS.values(), [])
                and k not in ("Tertiary sector", "Total: All industries",
                              "Taxes on products", "GDP by economic activity",
                              "Seasonal adjusted")]
    groups = {**_SECTORS, "Tertiary sector": tertiary}
    for parent, kids in {**groups, **_SUBACTIVITIES}.items():
        if parent in vals and all(k in vals for k in kids):
            s = sum(vals[k] for k in kids)
            if abs(s - vals[parent]) > tol:
                raise ValueError(f"CSO {where}: {parent} {vals[parent]} != sum {s}")
    tot = sum(vals[k] for k in groups)
    if abs(tot - vals["Total: All industries"]) > tol:
        raise ValueError(f"CSO {where}: sectors {tot} != all industries")
    if abs(vals["Total: All industries"] + vals["Taxes on products"]
           - vals["GDP by economic activity"]) > tol:
        raise ValueError(f"CSO {where}: industries + taxes != GDP")


def _quarterly(path: str) -> list[dict]:
    book = xlrd.open_workbook(path)
    out = []
    for sheet, (pb, measure, unit) in _SHEETS.items():
        sh = book.sheet_by_name(sheet)
        title = str(sh.cell_value(0, 0)).strip()
        hdr = sh.row_values(1)
        if str(hdr[0]).strip() != "Description":
            raise ValueError(f"CSO QGDP {sheet}: unexpected header {hdr[:3]}")
        periods = []
        for h in hdr[1:]:
            m = re.fullmatch(r"(\d{4}) Q([1-4])", str(h).strip())
            periods.append(f"{m.group(1)}-Q{m.group(2)}" if m else None)
        if None in periods:
            raise ValueError(f"CSO QGDP {sheet}: unreadable period header")
        rows = {}
        for r in range(2, sh.nrows):
            lab = str(sh.cell_value(r, 0)).strip()
            if not lab:
                continue
            vals = sh.row_values(r)[1:1 + len(periods)]
            rows[lab] = vals
        if "GDP by economic activity" not in rows:
            raise ValueError(f"CSO QGDP {sheet}: no GDP row")
        if measure == "level":
            for j, per in enumerate(periods):
                col = {k: v[j] for k, v in rows.items()
                       if k != "Seasonal adjusted" and v[j] != ""}
                _check_levels(col, f"QGDP {sheet} {per}", tol=0.5)
        for lab, vals in rows.items():
            sa = lab == "Seasonal adjusted"
            for per, v in zip(periods, vals):
                if v == "" or v is None:
                    continue
                v = float(v) * (100 if unit == "percent" else 1)
                out.append(_row(
                    approach="aggregate" if lab in ("GDP by economic activity",
                                                    "Seasonal adjusted",
                                                    "Total: All industries",
                                                    "Taxes on products")
                    else "production",
                    category="GDP by economic activity" if sa else lab,
                    category_group=title, series_code=f"CSO QGDP {sheet}",
                    period=per, frequency="quarterly", price_basis=pb,
                    seasonal_adjustment="saa" if sa else "nsa",
                    measure=measure, value=v, unit=unit,
                    base_period="Constant 2019 prices"
                    if (measure == "level" and pb == "constant") else ""))
    return out


# ------------------------------------------------------------------- annual

_TABLES = {  # caption id -> (approach, price_basis, measure, unit)
    "A1.1": ("production", "current", "level", "E million"),
    "A1.2": ("production", "constant", "level", "E million"),
    "A1.3": ("production", "current", "share", "percent"),
    "A1.4": ("production", "constant", "growth_yoy", "percent"),
    "A1.5": ("production", "constant", "contribution", "percentage points"),
    "A2.1": ("expenditure", "current", "level", "E million"),
    "A2.2": ("expenditure", "constant", "level", "E million"),
    "A2.3": ("expenditure", "current", "share", "percent"),
    "A2.4": ("expenditure", "constant", "growth_yoy", "percent"),
    "A2.5": ("expenditure", "not_applicable", "deflator", "index"),
}
_NUM = r"\(?-?[\d,]+(?:\.\d+)?\)?%?"
_CAP = re.compile(r"^(A[12]\.[1-5]) (.+)$")


def _num(tok: str) -> float:
    neg = tok.startswith("(")
    v = float(tok.strip("()%").replace(",", ""))
    return -v if neg else v


def _annual(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        lines = []
        for p in pdf.pages[30:]:
            lines += (p.extract_text() or "").splitlines()
    tables, cur = {}, None
    for ln in lines:
        ln = ln.strip()
        m = _CAP.match(ln)
        if m and m.group(1) in _TABLES and "....." not in ln:
            cur = m.group(1)
            tables[cur] = {"title": m.group(2), "years": None, "rows": []}
            continue
        if cur is None:
            continue
        if ln.startswith("Description"):
            tables[cur]["years"] = re.findall(r"\b(20\d\d)\b", ln)
            continue
        mm = re.match(rf"^(.*?[A-Za-z.)])\s+((?:{_NUM}\s*)+)$", ln)
        if mm and tables[cur]["years"]:
            tables[cur]["rows"].append((mm.group(1).strip(),
                                        [_num(t) for t in mm.group(2).split()]))
        elif re.match(r"^Discrepancy incl\. Changes in invent", ln):
            continue
    missing = [t for t in _TABLES if t not in tables or not tables[t]["rows"]]
    if missing:
        raise ValueError(f"CSO rebased report: tables not read {missing}")

    out = []
    for tid, (appr, pb, measure, unit) in _TABLES.items():
        t = tables[tid]
        seen_exports = False
        lab_rows = []
        for lab, vals in t["rows"]:
            if lab.startswith("Exports of goods"):
                seen_exports, side = True, "Exports of goods and services"
            elif lab.startswith("Imports of goods"):
                side = "Imports of goods and services"
            if lab in ("Goods", "Services"):
                lab = f"{side}: {lab}"
            years = t["years"][-len(vals):]     # A2.4: 11 years over 10 values
            lab_rows.append((lab, dict(zip(years, vals))))
        if measure == "level" and appr == "production":
            for y in t["years"]:
                _check_levels({k: v[y] for k, v in lab_rows if y in v},
                              f"{tid} {y}", tol=3)
        if measure == "level" and appr == "expenditure":
            d = dict(lab_rows)
            for y in t["years"]:
                s = (d["Final consumption expenditures"][y]
                     + d["Gross capital formation"][y]
                     + d["Net exports of goods and services"][y])
                if abs(s - d["GDP by expenditure"][y]) > 3:
                    raise ValueError(f"CSO {tid} {y}: components != GDP by expenditure")
                g = d["GDP by expenditure"][y] + d["Discrepancy incl. Changes in inventories"][y]
                if abs(g - d["GDP by economic activity"][y]) > 3:
                    raise ValueError(f"CSO {tid} {y}: expenditure + discrepancy != GDP")
        for lab, byyear in lab_rows:
            if tid == "A2.3" and lab.startswith("Discrepancy"):
                continue
            for y, v in byyear.items():
                out.append(_row(
                    approach="aggregate" if lab in ("GDP by economic activity",
                                                    "Total: All industries",
                                                    "Taxes on products")
                    else appr,
                    category=lab, category_group=f"{tid} {t['title']}",
                    series_code=f"CSO Rebased GDP Report 2023 {tid}",
                    period=y, frequency="annual", price_basis=pb,
                    measure=measure, value=v, unit=unit,
                    base_period="Constant 2019 prices"
                    if (measure == "level" and pb == "constant") else ""))
    # A2.4's alignment, proved from the report's own levels.
    lv = {r["period"]: r["value"] for r in out
          if r["series_code"].endswith("A2.2")
          and r["category"] == "Final consumption expenditures"}
    g14 = next(r["value"] for r in out if r["series_code"].endswith("A2.4")
               and r["category"] == "Final consumption expenditures"
               and r["period"] == "2014")
    if abs((lv["2014"] / lv["2013"] - 1) * 100 - g14) > 0.15:
        raise ValueError("CSO A2.4: growth values are not aligned to 2014-2023")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        if p.lower().endswith(".xls"):
            rows += _quarterly(p)
        elif p.lower().endswith(".pdf"):
            rows += _annual(p)
    df = pd.DataFrame(rows)
    # Deflators are an index; the corpus convention is unit "index" with the
    # reference year in base_period, not in the unit string.
    df.loc[df["measure"] == "deflator", "base_period"] = "2019=100"
    return df
