"""Zambia — ZamStats (Zambia Statistics Agency) national accounts workbooks.

Two workbooks, both from ZamStats's WordPress media library:

* QGDP_Q<n>_<YYYY>_Zambia.xlsx (primary, the newest quarterly release) --
  production approach, QUARTERLY from 2010 Q1, levels at current and constant
  prices (ZMW million): gross value added, taxes less subsidies on products,
  GDP at market prices, and value added for 30 activities coded AA..S (ZamStats'
  own ISIC-based codes, kept as `series_code`).
* Final-Annual_GDP_<YYYY>_Zambia.xlsx (extra) -- ANNUAL from 2010: production
  approach at current prices (output, intermediate consumption, GVA, taxes and
  subsidies on products, the same 30 activities) and constant prices; the
  EXPENDITURE approach at current prices; and the INCOME approach (compensation
  of employees, gross operating surplus, gross mixed income, net taxes).

CONSTANT PRICES ARE 2010 PRICES. The workbooks say only "Constant prices", but
ZamStats' GDP Benchmark Estimates Summary Report (2023) states the rebased
series is "in current and constant 2010 prices" with 2010 as the base year --
and every activity's 2010 constant value equals its 2010 current value.

NOTHING IS DERIVED: no growth rates, shares or deflators are computed; ZamStats
publishes none in these files. `*` and `**` against the two latest quarters
(2026 Q1*, Q2**) are ZamStats' own unexplained revision marks; they are
stripped from the period and the values kept.

IDENTITIES CHECKED every run (to 0.5 ZMW million): activities sum to GVA; GVA
plus taxes less subsidies equals GDP; final consumption + gross capital
formation + net exports + errors and omissions equals the expenditure total;
compensation + operating surplus + mixed income equals GVA.

PUBLISHED INCONSISTENCY KEPT: the expenditure table's 2025 GDP (785,900.7) is
not the production/income GDP for 2025 (797,706.8), while every earlier year
agrees. It is internally consistent (its own errors-and-omissions balances
it), so it is an older vintage of the 2025 expenditure estimate. Both are
kept, under their own approach; the gap is pinned (`_KNOWN_GAPS`) and the
parser raises if it changes, so a realignment by ZamStats is noticed.

PUBLISHED DEFECT KEPT: 2022 GDP on the production sheet (493,964.3) is 183.8
below the expenditure total and the income sheet's GDP (494,148.1), which
agree with each other; the production sheet's own GVA + net taxes adds up to
its figure. Both kept (production GDP as `aggregate`, the expenditure total
under `expenditure`, and the income sheet's own GDP and GVA under `income`,
since in 2022 they are a different estimate). Pinned.

PUBLISHED DEFECT KEPT: 2019 "Final Consumption Expenditures" is printed
215.6 above the sum of its own components (households, government, NPISH);
the expenditure total agrees with the components. Kept as printed, pinned.

NOT EMITTED TWICE: the income sheet repeats taxes and subsidies on products
from the production sheet -- checked equal, emitted once (production).

CROSS-CHECK: GDP 2025 current 797,706.8 / constant 177,485.7 ZMW million;
2026 Q2 GDP constant 47,744.3; 2010 GDP 97,215.9 (current = constant); 2025
compensation of employees 140,180.5.
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd

_UNIT = "ZMW million"
_BASE = "Constant 2010 prices"
_TOL = 0.5
# (year, what) -> published gap that is pinned rather than raised.
_KNOWN_GAPS = {("2025", "expenditure total vs production GDP"): 11806.1,
               # 2022: the PRODUCTION sheet's GDP is 183.8 below both the
               # expenditure total and the income sheet's GDP, which agree.
               ("2022", "expenditure total vs production GDP"): -183.8,
               ("2022", "income GDP vs production GDP"): 183.8,
               ("2022", "income GVA vs production GVA"): 183.8,
               # 2019 "Final Consumption Expenditures" is printed 215.6 above
               # households + government + NPISH; the expenditure total agrees
               # with the components, not with the printed subtotal.
               ("2019", "final consumption vs its components"): 215.6}


def _year(v):
    s = str(v).strip() if v is not None else ""
    return s if re.fullmatch(r"(19|20)\d\d", s) else None


def _rows(ws):
    return [list(r) for r in ws.iter_rows(values_only=True)]


def _read_block(rows, header_idx, quarter_idx=None):
    """Yield (code, label, {period: value}) for every data row under a header."""
    hdr = rows[header_idx]
    cols = {}
    year = None
    for j, v in enumerate(hdr):
        y = _year(v)
        if y:
            year = y
        if quarter_idx is not None:
            q = rows[quarter_idx][j] if j < len(rows[quarter_idx]) else None
            m = re.match(r"Q([1-4])", str(q or "").strip())
            if m and year:
                cols[j] = f"{year}-Q{m.group(1)}"
        elif y:
            cols[j] = y
    first = min(cols)
    start = (quarter_idx if quarter_idx is not None else header_idx) + 1
    for r in rows[start:]:
        texts = [(j, v) for j, v in enumerate(r[:first])
                 if isinstance(v, str) and v.strip()]
        vals = {p: r[j] for j, p in cols.items()
                if j < len(r) and isinstance(r[j], (int, float))}
        if not texts or not vals:
            continue
        label = re.sub(r"\s+", " ", texts[-1][1]).strip()
        code = texts[0][1].strip() if len(texts) > 1 else ""
        yield code, label, vals


def _check(cond, msg):
    if not cond:
        raise ValueError(f"ZamStats GDP: {msg}")


def _production(rows_iter, frequency, basis, sheet):
    out, agg, inds = [], {}, {}
    for code, label, vals in rows_iter:
        low = label.lower()
        if code and code != "GDP":
            inds[code] = vals
        else:
            agg[low] = vals
        approach = "aggregate" if low.startswith("gdp at market") else "production"
        for p, v in vals.items():
            out.append(dict(approach=approach, category=label,
                            category_group=sheet, series_code="" if code == "GDP" else code,
                            period=p, frequency=frequency, price_basis=basis,
                            measure="level", value=float(v), unit=_UNIT,
                            base_period=_BASE if basis == "constant" else ""))
    gva = agg.get("gross value added", {})
    gdp = agg.get("gdp at market prices", {})
    _check(gva and gdp and len(inds) >= 28, f"{sheet}: aggregates/activities missing")
    net = agg.get("taxes minus subsidies on products")
    for p in gdp:
        s = sum(v.get(p, 0) for v in inds.values())
        _check(abs(s - gva[p]) <= _TOL * 4, f"{sheet} {p}: activities {s:.1f} != GVA {gva[p]:.1f}")
        if net is not None:
            t = net[p]
        else:
            t = agg["taxes on products"][p] + agg["subsidies on products"][p]
        _check(abs(gva[p] + t - gdp[p]) <= _TOL, f"{sheet} {p}: GVA + net taxes != GDP")
    return out, gdp


def _expenditure(rows, gdp_prod):
    out, d = [], {}
    for _, label, vals in _read_block(rows, 0):
        d[label.lower()] = vals
        is_total = label.lower().startswith("gdp at purchasers")
        for p, v in vals.items():
            out.append(dict(approach="expenditure", category=label,
                            category_group="Expenditure (current prices)",
                            series_code="", period=p, frequency="annual",
                            price_basis="current", measure="level",
                            value=float(v), unit=_UNIT, base_period=""))
    tot = d["gdp at purchasers prices by final expeniture categories"]
    g = lambda k, p: d[k].get(p, 0)
    for p, t in tot.items():
        fce_parts = (g("households", p) + g("government", p)
                     + g("non-profit insitutions serving households", p))
        gap = round(g("final consumption expenditures", p) - fce_parts, 1)
        known = _KNOWN_GAPS.get((p, "final consumption vs its components"), 0.0)
        _check(abs(gap - known) <= 0.2, f"expenditure {p}: final consumption is "
                                        f"{gap} off its components (pinned {known})")
        _check(abs(g("gross fixed capital formation, incl. valuables", p)
                   + g("changes in inventories", p) - g("gross capital formation", p)) <= _TOL
               and abs(g("exports of goods and services", p) - g("import of goods and services", p)
                       - g("net export of goods and services", p)) <= _TOL,
               f"expenditure {p}: capital formation or net exports off their parts")
        s = (fce_parts + g("gross capital formation", p)
             + g("net export of goods and services", p) + g("errors and omissions", p))
        _check(abs(s - t) <= _TOL, f"expenditure {p}: components {s:.1f} != total {t:.1f}")
        gap = round(gdp_prod[p] - t, 1)
        known = _KNOWN_GAPS.get((p, "expenditure total vs production GDP"))
        if known is not None:
            _check(abs(gap - known) <= 0.2, f"expenditure {p}: pinned gap {known} is now {gap} "
                                            f"-- ZamStats revised it; update _KNOWN_GAPS")
        else:
            _check(abs(gap) <= _TOL, f"expenditure {p}: total {t:.1f} != production GDP "
                                     f"{gdp_prod[p]:.1f}")
    return out


def _income(rows, gdp_prod, gva_prod):
    out, d = [], {}
    # Taxes and subsidies on products repeat the production sheet exactly and
    # are emitted once (there). GDP and GVA are the income approach's own
    # totals -- they differ from the production sheet in 2022 -- so they stay.
    dup = {"taxes on products", "subsidies on products"}
    for _, label, vals in _read_block(rows, 0):
        low = label.lower().strip()
        d[low] = vals
        if low in dup:
            continue
        for p, v in vals.items():
            out.append(dict(approach="income", category=label,
                            category_group="Income components (current prices)",
                            series_code="", period=p, frequency="annual",
                            price_basis="current", measure="level",
                            value=float(v), unit=_UNIT, base_period=""))
    for p, g in d["gross value added"].items():
        gap = round(d["gdp"][p] - gdp_prod[p], 1)
        known = _KNOWN_GAPS.get((p, "income GDP vs production GDP"), 0.0)
        _check(abs(gap - known) <= 0.2, f"income {p}: GDP {gap} off the production "
                                        f"sheet (pinned {known})")
        gap = round(g - gva_prod[p], 1)
        known = _KNOWN_GAPS.get((p, "income GVA vs production GVA"), 0.0)
        _check(abs(gap - known) <= 0.2, f"income {p}: GVA {gap} off the production "
                                        f"sheet (pinned {known})")
        s = (d["compensation of employees"][p] + d["operating surplus, gross"][p]
             + d["mixed income, gross"][p])
        _check(abs(s - g) <= _TOL, f"income {p}: components {s:.1f} != GVA {g:.1f}")
    return out


def _quarterly(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    out = []
    for sheet, basis in (("Current Price", "current"), ("Constant Price", "constant")):
        rows = _rows(wb[sheet])
        o, _ = _production(_read_block(rows, 0, quarter_idx=1), "quarterly", basis, sheet)
        out += o
    return out


def _annual(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    out = []
    cur, gdp_cur = _production(_read_block(_rows(wb["GDP_Annual_Current"]), 0),
                               "annual", "current", "GDP_Annual_Current")
    con, _ = _production(_read_block(_rows(wb["GDP_Annual_Constant"]), 0),
                         "annual", "constant", "GDP_Annual_Constant")
    gva_cur = {r["period"]: r["value"] for r in cur
               if r["category"] == "Gross value added"}
    out += cur + con
    out += _expenditure(_rows(wb["Expenditure"]), gdp_cur)
    out += _income(_rows(wb["Income"]), gdp_cur, gva_cur)
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = _quarterly(path)
    for ex in extras or []:
        if "annual" in ex.lower():
            rows += _annual(ex)
    df = pd.DataFrame(rows)
    df["geography"] = "National"
    df["seasonal_adjustment"] = "nsa"
    return df
