"""Annual back series for Kenya: KNBS Statistical Abstract, National Accounts
chapter, published as a workbook (`National-Accounts.xlsx`, Statistical Abstract
2024, years 2014-2023, constant prices referenced to 2016).

Not a registry parser: `kenya_knbs_gdp.parse` hands it any `.xlsx` extra.

Each sheet is one table: a caption row ('Table 2.2: ...'), a unit line ('Current
Prices - KSh Million', 'Per cent', ...), a header row of years ('2021+' revised,
'2023*' provisional -- the marks are dropped, the year kept), then labelled rows.
The table caption is kept as `category_group`; labels are kept as printed apart
from the dot/leader filler the workbook carries after some of them.

Tables read: 2.1 production accounts by industry (output, intermediate
consumption, value added, compensation, operating surplus), 2.2-2.5 GDP by
activity (current level, share, constant 2016 level, real growth), 2.6a-d
expenditure on GDP, 2.7a-d gross fixed capital formation by purpose, 2.8 GDP
and GNI (incl. per-capita), 2.9 national disposable income and saving.
Everything as published; nothing derived.
"""
from __future__ import annotations
import re
import openpyxl

UNIT = "KES million"
BASE = "constant 2016 prices"
_YEAR = re.compile(r"^\s*((?:19|20)\d\d)\s*[+*]?\s*$")


def _label(v) -> str:
    s = str(v or "")
    s = re.sub(r"[�…]+", " ", s)       # leader filler
    s = re.sub(r"[\s.]+$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _is_aggregate(label: str) -> bool:
    l = label.lower()
    return ("gdp at market" in l or "gross domestic product" in l
            or "gross national" in l or l.startswith("gdp"))


def _sheet_spec(caption: str, unitline: str):
    """(measure, price_basis, unit, approach) from the caption + unit line."""
    c, u = caption.lower(), unitline.lower()
    approach = "expenditure" if ("expenditure" in c or "capital formation" in c) \
        else "production"
    if "growth" in c or "percentage change" in u:
        return "growth_yoy", "constant", "percent", approach
    if "contribution" in c or "share" in c or "per cent" in u or "percentage" in u:
        return "share", "current", "percent", approach
    if "constant" in u:
        return "level", "constant", UNIT, approach
    return "level", "current", UNIT, approach


def _years(row):
    out = {}
    for j, v in enumerate(row):
        if v is None:
            continue
        m = _YEAR.match(str(v).replace(".0", ""))
        if m:
            out[j] = m.group(1)
    return out


def _row(approach, category, group, period, basis, measure, value, unit):
    return {"approach": approach, "category": category, "category_group": group,
            "series_code": "", "geography": "National", "period": period,
            "frequency": "annual", "price_basis": basis,
            "seasonal_adjustment": "not_applicable", "measure": measure,
            "value": float(value), "unit": unit,
            "base_period": BASE if basis == "constant"
            and measure in ("level", "per_capita") else ""}


def parse_workbook(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    rows = []
    for ws in wb.worksheets:
        grid = [list(r) for r in ws.iter_rows(values_only=True)]
        cells = [str(c) for r in grid[:3] for c in r if c is not None]
        cap = next((c for c in cells if c.lower().startswith("table")), "")
        if not cap:
            continue
        # The edition is part of the group: older editions (other bases,
        # other vintages) print different figures for the same years.
        group = "Statistical Abstract 2024, " + re.sub(
            r",\s*(19|20)\d\d\s*-\s*(19|20)\d\d.*$", "", cap).strip()
        unitline = " ".join(c for c in cells[1:] if not c.lower().startswith("table")
                            and not _YEAR.match(c) and not c.lower().startswith(
                                ("industry", "expenditure", "purpose")))
        measure, basis, unit, approach = _sheet_spec(cap, unitline)
        tnum = re.match(r"Table\s*([\d.]+\w?)", cap.replace("(", "").replace(")", ""))
        tnum = tnum.group(1) if tnum else ""
        years = {}
        parent = ""
        section_basis = basis
        labels = [_label(r[0]) if r else "" for r in grid]
        for i, r in enumerate(grid):
            yr = _years(r)
            if len(yr) >= 4:
                years = yr
                continue
            label = _label(r[0])
            if not label or not years:
                continue
            nums = {j: r[j] for j in years if j < len(r) and isinstance(r[j], (int, float))}
            if not nums:
                low = label.lower()
                if low.startswith(("*", "+", "1 ", "npish", "table")):
                    continue
                if tnum == "2.8" and "constant prices" in low:
                    section_basis = "constant"
                if tnum == "2.1":
                    # An industry heading is followed by its accounts; an item
                    # printed without figures ('Less: Subsidies') is not one.
                    nxt = next((l for l in labels[i + 1:] if l), "").lower()
                    if not nxt.startswith(("output", "intermediate")):
                        continue
                parent = label                       # a heading row
                continue
            if label.lower().startswith(("* provisional", "+ revised")):
                continue
            cat, appr, meas, b, un = label, approach, measure, section_basis, unit
            if tnum == "2.1":
                cat = f"{parent}: {label}"
                if label.lower().startswith(("compensation", "gross operating")):
                    appr = "income"
            elif tnum in ("2.8", "2.9"):
                appr = "income"
                if tnum == "2.9" and parent:
                    cat = f"{parent}: {label}"
                elif label.lower().startswith(("receivable", "payable")):
                    cat = f"{parent}: {label}"
                low = label.lower()
                if "percentage change" in low:
                    meas, un = "growth_yoy", "percent"
                elif "per capita" in low:
                    meas, un = "per_capita", "KES"
            if _is_aggregate(label) and tnum != "2.1":
                appr = "aggregate"
            for j, v in nums.items():
                rows.append(_row(appr, cat, group, years[j], b, meas, v, un))
    if not rows:
        raise ValueError(f"no national-accounts rows read from {path}")
    return rows
