"""Parser for INE Cabo Verde's "Quadros das Contas Nacionais Trimestrais"
workbook (xlsx, Portuguese; Base 2015, SCN 2008).

One workbook, ten tables, both approaches and both frequencies:

  Q1.1 / Q2.1  production approach, current prices, CVE million   (quarterly / annual)
  Q1.2 / Q2.2  production approach, chained volume, CVE million
  Q1.3 / Q2.3  production approach, chained-volume y/y % change
  Q1.4 / Q2.4  expenditure approach, current prices + y/y % change block
  Q1.5 / Q2.5  expenditure approach, chained volume + y/y % change block

Production: 17 activity branches, VALOR ACRESCENTADO, net taxes on products and
PIB. Expenditure: final consumption (private, public), investment, exports and
imports of goods and services, net exports and PIB. "PRODUTO INTERNO BRUTO" /
"PIB (1+2+3 - 4)" / "PIB" rows are the `aggregate`.

READ BY GRAMMAR, NOT BY POSITION. Each sheet has a period header row
("2007:I" ... "2026:II" quarterly, or 2007 ... "2025P" annual), a level block,
and -- in the expenditure tables -- a "Taxa de Variação (Homóloga)" block of
y/y % changes below it, which either repeats the period header (annual) or
reuses the main one (quarterly). The sheet TITLE sets the approach (ótica da
Produção / Despesa) and the price basis (preços correntes / volume encadeado);
"Taxas de variação" in the title makes the whole sheet a growth table.

"P" = provisório: 2024 and 2025 annual figures are, per the workbook's own note,
the sum of their quarters, not the final annual accounts; the period is the
year and base_period records "provisional (sum of quarters)".

Constant prices are CHAINED VOLUMES referenced to 2015 (the workbook's "Base
2015"); chained volumes are not additive, so identities are checked at CURRENT
prices only: every period, VALOR ACRESCENTADO + net taxes = PIB (production)
and consumption + investment + exports - imports = PIB (expenditure), each to
within 0.1% -- and production PIB = expenditure PIB.

NOT READ: the annual "Contas Nacionais Anuais definitivas" workbook (supply-use
and integrated economic accounts at a finer grain, 2015-2023) -- a different,
final vintage; the quarterly workbook's own annualised tables (Q2.x) are the
series INE publishes alongside the quarters.

CROSS-CHECK: PIB 2007 Q1 current 31 804.48 CVE million; 2026 Q2 current
79 292.61; 2025P current (expenditure) 299 131.49, real growth 2025P 8.15%
(current) / see Q2.3 for volume; 2026 Q2 volume growth 8.89%.
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}
_GDP = re.compile(r"^(PRODUTO INTERNO BRUTO|PIB)\b", re.I)
# PUBLISHED: three 2022 quarters where Q1.1 (production) and Q1.4
# (expenditure) print different current-price PIB, by 0.15-0.24% (2022-Q1
# 53 941.70 vs 54 031.81; Q2 56 263.46 vs 56 349.28; Q4 64 431.77 vs
# 64 275.36). The annual 2022 figures agree. Both are kept, each under its own
# table's series_code; any OTHER quarter disagreeing raises.
_KNOWN_APPROACH_GAPS = {"2022-Q1", "2022-Q2", "2022-Q4"}


def _period(v):
    """'2007:I' -> ('2007-Q1', 'quarterly', ''), 2007 / '2025P' -> annual."""
    if isinstance(v, int) and 1990 < v < 2100:
        return str(v), "annual", ""
    s = str(v or "").strip()
    # Q2.2 stores its years as TEXT ('2007'), the other annual sheets as
    # numbers -- reading only numbers kept just its two 'P' columns.
    if re.fullmatch(r"(19|20)\d{2}", s):
        return s, "annual", ""
    m = re.fullmatch(r"(\d{4}):(I{1,3}|IV)", s)
    if m:
        return f"{m.group(1)}-Q{_ROMAN[m.group(2)]}", "quarterly", ""
    m = re.fullmatch(r"(\d{4})P", s)
    if m:
        return m.group(1), "annual", "provisional (sum of quarters)"
    return None


def _header(ws, r):
    hdr = {c: _period(ws.cell(r, c).value) for c in range(2, ws.max_column + 1)}
    return {c: p for c, p in hdr.items() if p}


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _sheet(ws, rows):
    title = re.sub(r"\s+", " ", str(ws.cell(1, 1).value or "")).strip()
    approach = "production" if "Produção" in title else \
        "expenditure" if "Despesa" in title else None
    if approach is None:
        raise ValueError(f"INE CV {ws.title}: no approach in title {title!r}")
    basis = "constant" if "volume encadeado" in title.lower() else "current"
    growth_sheet = title.lower().startswith(("quadro 1.3", "quadro 2.3")) or \
        "taxas de variação" in title.lower()
    unit_level = "CVE million"
    base_level = "Chained volume, reference year 2015" if basis == "constant" else ""

    hdr = _header(ws, 2)
    if not hdr:
        raise ValueError(f"INE CV {ws.title}: no period header on row 2")
    measure = "growth_yoy" if growth_sheet else "level"
    levels = {}
    for r in range(3, ws.max_row + 1):
        lab = ws.cell(r, 1).value
        if not isinstance(lab, str) or not lab.strip():
            continue
        lab = re.sub(r"\s+", " ", lab).strip()
        if lab.startswith("Taxa de Variação"):
            measure = "growth_yoy"
            own = _header(ws, r)
            if own:
                hdr = own
            continue
        if lab.startswith(("Fonte", "P -", "Nota")):
            continue
        is_gdp = bool(_GDP.match(lab))
        for c, (period, freq, prov) in hdr.items():
            v = _num(ws.cell(r, c).value)
            if v is None:
                continue
            if measure == "level":
                levels.setdefault(period, {})[lab] = v
            rows.append({
                "approach": "aggregate" if is_gdp else approach, "category": lab,
                "category_group": title, "series_code": f"CNT {ws.title}",
                "geography": "National", "period": period, "frequency": freq,
                "price_basis": basis, "seasonal_adjustment": "nsa",
                "measure": measure, "value": v,
                "unit": unit_level if measure == "level" else "percent",
                "base_period": "; ".join(x for x in (
                    base_level if measure == "level" else "", prov) if x)})
    return approach, basis, levels


def _identity(ws_name, approach, levels):
    for p, d in levels.items():
        gdp = next((v for k, v in d.items() if _GDP.match(k)), None)
        if gdp is None:
            continue
        if approach == "production":
            parts = [d.get("VALOR ACRESCENTADO"),
                     d.get("Impostos líquidos de subsídios sobre produtos")]
        else:
            g = {k.split(". ", 1)[-1]: v for k, v in d.items()}
            parts = [g.get("Despesa de Consumo Final"), g.get("Investimento"),
                     g.get("Exportações"),
                     -g["Importações"] if g.get("Importações") is not None else None]
        if None in parts:
            continue
        if abs(sum(parts) - gdp) > 1e-3 * abs(gdp):
            raise ValueError(f"INE CV {ws_name} {p}: components {sum(parts):.2f} "
                             f"!= PIB {gdp:.2f}")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, data_only=True)
    want = ["Q1.1", "Q1.2", "Q1.3", "Q1.4", "Q1.5",
            "Q2.1", "Q2.2", "Q2.3", "Q2.4", "Q2.5"]
    missing = [s for s in want if s not in wb.sheetnames]
    if missing:
        raise ValueError(f"INE CV: sheets {missing} not in {wb.sheetnames}")
    rows: list[dict] = []
    current_gdp = {}
    for s in want:
        approach, basis, levels = _sheet(wb[s], rows)
        if basis == "current":
            _identity(s, approach, levels)
            for p, d in levels.items():
                g = next((v for k, v in d.items() if _GDP.match(k)), None)
                if g is not None:
                    current_gdp.setdefault(p, {})[approach] = g
    for p, d in current_gdp.items():
        if len(d) == 2 and abs(d["production"] - d["expenditure"]) > 1e-3 * abs(d["production"]):
            if p in _KNOWN_APPROACH_GAPS:
                continue
            raise ValueError(f"INE CV {p}: production PIB {d['production']} != "
                             f"expenditure PIB {d['expenditure']} -- a new gap; "
                             f"check the edition before pinning it")
    for p in _KNOWN_APPROACH_GAPS:
        d = current_gdp.get(p, {})
        if len(d) == 2 and abs(d["production"] - d["expenditure"]) <= 1e-3 * abs(d["production"]):
            raise ValueError(f"INE CV {p}: the production/expenditure gap is gone "
                             f"-- INE aligned it; remove it from _KNOWN_APPROACH_GAPS")
    wb.close()
    # Production and expenditure tables each print their own PIB; both are
    # kept, told apart by series_code (equal except the pinned 2022 gaps).
    return pd.DataFrame.from_records(rows)[_OUT_COLS]
