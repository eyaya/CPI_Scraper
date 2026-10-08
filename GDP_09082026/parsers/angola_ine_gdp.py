"""Parser for INE Angola's national-accounts workbooks (xlsx, Portuguese).

PRIMARY -- "CONTAS_NACIONAIS_TRIMESTRAIS" (Contas Nacionais Trimestrais 2002-
2025), production approach by 16 activities + taxes on products, subsidies (-)
and GDP, quarterly with an annual "Total" row per year:

  Q2  chained volume measures, seasonally adjusted, Kz million   level / constant / saa
  Q3  q/q % change, seasonally adjusted                           growth_qoq / constant / saa
  Q4  contribution to SA q/q GDP growth                           contribution / constant / saa
  Q5  chained volume measures, not adjusted, Kz million           level / constant / nsa
  Q6  y/y % change of Q5                                          growth_yoy / constant / nsa
  Q7  contribution to y/y GDP growth (not adjusted)               contribution / constant / nsa
  Q12 current prices, Kz million                                  level / current / nsa
  Q13 y/y % change at current prices                              growth_yoy / current / nsa
  Q14 share of nominal GDP                                        share / current / nsa

NOT READ: Q8-Q11 (year-to-date and rolling-four-quarter accumulations -- no
measure in this schema), Q1 and Q15 (oil / non-oil and sector regroupings of
the same activities).

OPTIONAL EXTRA -- "CONTAS NACIONAIS ANUAIS" (Contas Nacionais Anuais 2002-2025):
Q1.1 GDP at current prices and at previous-year prices (levels) with real
annual growth; Q1.3 GDP by the production, expenditure AND income approaches at
current prices. Recognised by its sheet names. It sits in a different INE folder
("Anual") from the primary, and INE files download only by POST, which
`extra_urls` cannot send -- see the descriptor for the one-line harness change
that would fetch it. Q1.1's "Deflator implícito, variação anual" is a percent
change of a deflator, which this schema has no measure for, and is not read.

TRAP -- THE ANNUAL "Total" ROW SITS ABOVE ITS YEAR. Every quarterly sheet prints
"Total" on the line BEFORE that year's "I TRIM" row (the year label is on the
I TRIM row): in Q5 the first Total, 6 423 975.18, is the sum of the four 2002
quarters, and in Q13 the Total printed after 2002's empty quarters is 2003's
annual nominal growth (116.23 agriculture). Each Total is therefore dated to the
year of the quarter row BELOW it, and on the level sheets (Q2, Q5, Q12) the
parser asserts that every Total equals the sum of that year's four quarters --
read the other way, that check fails in every year.

SUBSIDIES' GROWTH RATES ARE LEFT OUT (levels and contributions kept): the
line nears zero in some quarters and INE's growth off it reaches 1.5e7 %.

PLACEHOLDER ZEROS: growth and contribution sheets print 0 for every activity in
quarters with no prior period (2002 for y/y, 2002 Q1 for q/q). A period whose
every cell is exactly 0 is a placeholder, not a measured zero, and is skipped.

Constant prices are CHAINED VOLUME MEASURES in Kz million; INE states no
reference year in the workbook, so base_period says exactly that. Quarters for
which INE has not yet published (the 2025 tail) are empty and skipped.

Identity checked every run on Q12 and Q5 (current and chained levels): the 16
activities + taxes - |subsidies| reproduce GDP to within 0.5% at current prices
(chained volumes are not additive, so only current prices are held to it).

CROSS-CHECK: current GDP 2002 = 753 573.72 Kz million (= annual Q1.1);
2002 Q1 chained volume, not adjusted, 1 540 753.94; agriculture share 2002
8.47%; real GDP growth 2024 5.0% (Q1.1).
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]
_CHAIN = "Chained volume measures (reference year not stated)"
_QSHEETS = {
    "Q2": ("level", "constant", "saa", "Kz million", _CHAIN),
    "Q3": ("growth_qoq", "constant", "saa", "percent", ""),
    "Q4": ("contribution", "constant", "saa", "percentage points", ""),
    "Q5": ("level", "constant", "nsa", "Kz million", _CHAIN),
    "Q6": ("growth_yoy", "constant", "nsa", "percent", ""),
    "Q7": ("contribution", "constant", "nsa", "percentage points", ""),
    "Q12": ("level", "current", "nsa", "Kz million", ""),
    "Q13": ("growth_yoy", "current", "nsa", "percent", ""),
    "Q14": ("share", "current", "nsa", "percent", ""),
}
_QUARTER = {"I TRIM": 1, "II TRIM": 2, "III TRIM": 3, "IV TRIM": 4}


def _clean(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def _approach(label: str) -> str:
    return "aggregate" if "PRODU" in label.upper() and "BRUTO" in label.upper() \
        else "production"


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _quarterly_sheet(ws, spec, rows):
    measure, basis, sa, unit, base = spec
    title = _clean(ws.cell(1, 3).value or ws.cell(1, 2).value)
    cols = {c: _clean(ws.cell(2, c).value) for c in range(4, ws.max_column + 1)
            if ws.cell(2, c).value is not None}
    if not any("BRUTO" in v.upper() for v in cols.values()):
        raise ValueError(f"INE AO {ws.title}: no GDP column in the header")
    # Pass 1: rows with their (year, quarter|None); a Total takes the year of
    # the next quarter row.
    seq, year = [], None
    for r in range(3, ws.max_row + 1):
        y, q = ws.cell(r, 2).value, _clean(ws.cell(r, 3).value or "")
        if isinstance(y, int):
            year = y
        if q in _QUARTER:
            seq.append([r, year, _QUARTER[q]])
        elif q == "Total":
            seq.append([r, None, None])
    for i, item in enumerate(seq):
        if item[2] is None:
            nxt = next((s for s in seq[i + 1:] if s[2] is not None), None)
            item[1] = nxt[1] if nxt and nxt[2] == 1 else None
    # A YEAR STILL IN PROGRESS has a "Total" over the quarters published so far
    # (2026 over Q1-Q2 in the 2026 edition). That is a year-to-date figure, not
    # an annual one, so a Total is kept only when its year has all four quarter
    # rows filled in this sheet.
    def _filled(r):
        return any(_num(ws.cell(r, c).value) is not None for c in cols)
    full = {y for y in {s[1] for s in seq if s[2]}
            if sum(1 for r, yy, q in seq if q and yy == y and _filled(r)) == 4}
    seq = [s for s in seq if s[2] is not None or s[1] in full]
    # Pass 2: values.
    per = {}
    for r, y, q in seq:
        if y is None:
            continue
        vals = {c: _num(ws.cell(r, c).value) for c in cols}
        if all(v is None for v in vals.values()):
            continue
        if measure != "level" and all((v or 0) == 0 for v in vals.values()):
            continue                                    # placeholder zeros
        period = f"{y}-Q{q}" if q else str(y)
        per[period] = vals
        for c, v in vals.items():
            if v is None:
                continue
            # SUBSIDIES' GROWTH RATES ARE NOT COLLECTED: the line falls to near
            # zero in some quarters, and INE's growth off that base reaches
            # 1.5e7 % (Q6 2020-Q1) -- past the schema's deliberately loose
            # bound. Cutting the series at a threshold would be arbitrary, so
            # the whole growth series of this one line is left out; its levels
            # and contributions are kept.
            if measure.startswith("growth") and cols[c].startswith("Subs"):
                continue
            rows.append({
                "approach": _approach(cols[c]), "category": cols[c],
                "category_group": title, "series_code": f"CNT {ws.title}",
                "geography": "National", "period": period,
                "frequency": "quarterly" if q else "annual",
                "price_basis": basis, "seasonal_adjustment": sa,
                "measure": measure, "value": v, "unit": unit,
                "base_period": base})
    if measure == "level":
        gdp_c = next(c for c, v in cols.items() if "BRUTO" in v.upper())
        for p, vals in per.items():
            if "-Q" in p or vals.get(gdp_c) is None:
                continue
            qs = [per.get(f"{p}-Q{i}", {}).get(gdp_c) for i in range(1, 5)]
            if None in qs:
                continue
            if abs(sum(qs) - vals[gdp_c]) > max(1.0, 1e-5 * abs(vals[gdp_c])):
                raise ValueError(f"INE AO {ws.title}: Total {p} ({vals[gdp_c]}) is "
                                 f"not the sum of {p}'s quarters ({sum(qs)}) -- "
                                 f"the Total-above-its-year convention has changed")
        if basis == "current":
            for p, vals in per.items():
                parts = [v for c, v in vals.items() if c != gdp_c and v is not None]
                if vals.get(gdp_c) and parts:
                    s = sum(v if v >= 0 else v for v in parts)
                    if abs(s - vals[gdp_c]) > 0.005 * abs(vals[gdp_c]):
                        raise ValueError(f"INE AO {ws.title} {p}: components "
                                         f"{s:.1f} vs GDP {vals[gdp_c]:.1f}")


def _annual_workbook(wb, rows):
    # Q1.1: year | current | previous-year prices | real growth | deflator var.
    ws = wb["Q1.1"]
    for r in range(5, ws.max_row + 1):
        y = ws.cell(r, 2).value
        m = re.fullmatch(r"(\d{4})\*?", str(y or "").strip())
        if not m:
            continue
        p = m.group(1)
        for c, measure, basis, unit, base in (
                (3, "level", "current", "Kz million", ""),
                (4, "level", "constant", "Kz million", "Previous year's prices"),
                (5, "growth_yoy", "constant", "percent", "")):
            v = _num(ws.cell(r, c).value)
            if v is None:
                continue
            rows.append({"approach": "aggregate", "category": "Produto Interno Bruto",
                         "category_group": "Quadro 1.1- Produto Interno Bruto",
                         "series_code": "CNA Q1.1", "geography": "National",
                         "period": p, "frequency": "annual", "price_basis": basis,
                         "seasonal_adjustment": "nsa", "measure": measure,
                         "value": v, "unit": unit, "base_period": base})
    # Q1.3: three approaches, current prices, years across.
    ws = wb["Q1.3"]
    years = {c: re.fullmatch(r"(\d{4})\*?", str(ws.cell(2, c).value or "").strip())
             for c in range(3, ws.max_column + 1)}
    years = {c: m.group(1) for c, m in years.items() if m}
    approach, seen = None, set()
    for r in range(3, ws.max_row + 1):
        lab = ws.cell(r, 2).value
        if lab is None:
            continue
        lab = _clean(lab)
        hdr = re.match(r"([ABC]) - Óptica d[ao] (produção|despesa|rendimento)", lab)
        if hdr:
            approach = {"produção": "production", "despesa": "expenditure",
                        "rendimento": "income"}[hdr.group(2)]
            continue
        if approach is None:
            continue
        is_gdp = lab == "Produto Interno Bruto"
        if is_gdp and "gdp" in seen:
            continue                     # the same GDP repeated under B and C
        if is_gdp:
            seen.add("gdp")
        for c, p in years.items():
            v = _num(ws.cell(r, c).value)
            if v is None:
                continue
            rows.append({"approach": "aggregate" if is_gdp else approach,
                         "category": lab, "category_group": f"Óptica ({approach})",
                         "series_code": "CNA Q1.3", "geography": "National",
                         "period": p, "frequency": "annual", "price_basis": "current",
                         "seasonal_adjustment": "nsa", "measure": "level",
                         "value": v, "unit": "Kz million", "base_period": ""})
    if "gdp" not in seen:
        raise ValueError("INE AO Q1.3: no GDP row read")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows: list[dict] = []
    for p in [path, *(extras or [])]:
        wb = openpyxl.load_workbook(p, data_only=True)
        if all(s in wb.sheetnames for s in _QSHEETS):
            for s, spec in _QSHEETS.items():
                _quarterly_sheet(wb[s], spec, rows)
        elif {"Q1.1", "Q1.3"} <= set(wb.sheetnames):
            _annual_workbook(wb, rows)
        else:
            raise ValueError(f"INE AO: unrecognised workbook {p} {wb.sheetnames[:6]}")
        wb.close()
    if not rows:
        raise ValueError("no GDP rows parsed from INE Angola workbooks")
    return pd.DataFrame.from_records(rows)[_OUT_COLS]
