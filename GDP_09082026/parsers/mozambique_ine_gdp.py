"""Parser for INE Moçambique's Anuário Estatístico (Statistical Yearbook) PDF,
chapter 5 "Agregados Macroeconómicos / Produto Interno Bruto" -- tables sourced
to "INE Direcção de Contas Nacionais e Indicadores Globais".

WHY THE YEARBOOK. INE's own "PIB > Trimestrais/Anuais" document folders hold
only 2013-14 notes, and the quarterly GDP figures appear elsewhere only in
prose (Síntese de Conjuntura) or a two-line flash bulletin. The yearbook is the
NSO's current tabulated national-accounts release: five years per edition.

Read (Anuário 2025, years 2021-2025):

  Quadro 5.5.1  GDP by EXPENDITURE: total / private / public consumption,
                gross capital formation, exports, imports and PIB (pm), at
                current prices AND constant 2019 prices, 10^6 MT  -> level
  Quadro 5.5.3  volume % change of the same components            -> growth_yoy
  Quadro 5.4.1  PIBpm per capita in MT and in US$                 -> per_capita
                (its PIBpm levels and volume growth repeat 5.5.1/5.5.3 and are
                checked equal, not emitted twice)

NOT READ: Quadro 5.5.2 (growth of the implicit deflators -- a percent change of
a deflator, for which the schema has no measure); the fiscal, external and
exchange-rate ratios in 5.4.1 (not national-accounts aggregates); the tourism
satellite table 3.10.6. No production-approach table is printed.

READ BY TOKENS, NOT LINES. PyMuPDF returns one table cell per line, so a
space-grouped number ("1 058 442") arrives whole -- the reason this is not read
with pdfplumber, whose line text fuses adjacent cells. A row is its label text
(the Portuguese half, before "/"; wrapped labels rejoined) followed by exactly
the number of values the header announces; anything else raises.

Identity checked every year at current prices: consumption + capital
formation + exports - imports = PIB (to 1 million MT of rounding). Each table's
PIB must equal 5.4.1's headline.

Constant prices are "preços constantes de 2019" (base_period).

CROSS-CHECK (Anuário 2025): PIBpm current 2021 1 058 442 / 2025 1 508 475;
constant 2019 prices 2025 1 101 792; volume growth 2023 5.48%, 2025 -0.17%;
per capita 2025 44 249 MT / US$ 692.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]
_NUM = re.compile(r"^-?\d{1,3}(?: \d{3})*(?:,\d+)?%?$")


def _num(tok: str) -> float:
    return float(tok.replace(" ", "").replace("%", "").replace(",", "."))


def _lines(doc, caption):
    for page in doc:
        text = page.get_text()
        i = text.find(caption)
        # The list of tables repeats captions; the table itself is followed by
        # a "Descrição" header.
        if i >= 0 and "Descrição" in text[i:i + 400]:
            body = text[i:]
            end = body.find("Fonte:")
            return [ln.strip() for ln in body[:end].splitlines() if ln.strip()]
    raise ValueError(f"INE MZ yearbook: {caption!r} not found")


def _rows(lines, n_values):
    """Yield (label, [values]) -- label text, then exactly n numeric tokens."""
    label, vals, out = [], [], []
    for ln in lines:
        if _NUM.match(ln):
            vals.append(_num(ln))
            if len(vals) == n_values:
                out.append((" ".join(label), vals))
                label, vals = [], []
            continue
        if vals:
            raise ValueError(f"INE MZ: {label} has {len(vals)} values, "
                             f"expected {n_values}")
        label.append(ln)
    return [(re.split(r"\s*/\s*", lab, 1)[0].strip(), v) for lab, v in out]


def _years(lines):
    # Only after the "Descrição" header: captions wrap ("..., 2021-" / "2025")
    # and the wrapped year is not a column.
    start = next(i for i, ln in enumerate(lines) if ln.startswith("Descrição"))
    return [ln for ln in lines[start:] if re.fullmatch(r"20\d\d", ln)]


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    doc = fitz.open(path)
    rows: list[dict] = []

    def add(approach, cat, group, code, period, basis, measure, value, unit, base=""):
        rows.append({"approach": approach, "category": cat, "category_group": group,
                     "series_code": code, "geography": "National", "period": period,
                     "frequency": "annual", "price_basis": basis,
                     "seasonal_adjustment": "nsa", "measure": measure,
                     "value": value, "unit": unit, "base_period": base})

    # --- Quadro 5.5.1: expenditure, current then constant 2019 prices -------
    L = _lines(doc, "Quadro 5.5.1 Produto Interno Bruto (PIB) na óptica da despesa")
    years = _years(L)
    if len(years) != 10 or years[:5] != years[5:]:
        raise ValueError(f"INE MZ 5.5.1: header years {years}")
    years = years[:5]
    body = L[max(i for i, ln in enumerate(L) if ln == years[-1]) + 1:]
    t551 = _rows(body, 10)
    labels = [lab for lab, _ in t551]
    if not labels or not labels[-1].startswith("PIB") or len(labels) != 7:
        raise ValueError(f"INE MZ 5.5.1: rows {labels}")
    cur = {lab: dict(zip(years, v[:5])) for lab, v in t551}
    for lab, v in t551:
        approach = "aggregate" if lab.startswith("PIB") else "expenditure"
        for y, cv, kv in zip(years, v[:5], v[5:]):
            add(approach, lab, "Quadro 5.5.1 PIB na óptica da despesa",
                "Anuário Q5.5.1", y, "current", "level", cv, "MZN million")
            add(approach, lab, "Quadro 5.5.1 PIB na óptica da despesa",
                "Anuário Q5.5.1", y, "constant", "level", kv, "MZN million",
                "Constant 2019 prices")
    gdp = cur[labels[-1]]
    for y in years:
        c = cur["Consumo Total"][y] + cur["Formação Bruta de Capital"][y] + \
            cur["Exportações de Bens e Serviços"][y] - \
            cur["Importações de Bens e Serviços"][y]
        if abs(c - gdp[y]) > 2:
            raise ValueError(f"INE MZ 5.5.1 {y}: C+I+X-M {c} != PIB {gdp[y]}")

    # --- Quadro 5.5.3: volume % change ----------------------------------------
    L = _lines(doc, "Quadro 5.5.3 Variação percentual em volume")
    ys = _years(L)
    if ys != years:
        raise ValueError(f"INE MZ 5.5.3: years {ys} != {years}")
    body = L[max(i for i, ln in enumerate(L) if ln == ys[-1]) + 1:]
    t553 = _rows(body, 5)
    if [lab for lab, _ in t553] != labels:
        raise ValueError(f"INE MZ 5.5.3: rows {[lab for lab, _ in t553]}")
    growth = {}
    for lab, v in t553:
        for y, g in zip(years, v):
            add("aggregate" if lab.startswith("PIB") else "expenditure", lab,
                "Quadro 5.5.3 Variação percentual em volume", "Anuário Q5.5.3",
                y, "constant", "growth_yoy", g, "percent")
        if lab.startswith("PIB"):
            growth = dict(zip(years, v))

    # --- Quadro 5.4.1: per capita; its PIB rows are checked against 5.5.x ----
    L = _lines(doc, "Quadro 5.4.1 Indicadores macroeconómicos")
    ys = _years(L)[:5]
    if ys != years:
        raise ValueError(f"INE MZ 5.4.1: years {ys} != {years}")
    text = "\n".join(L)

    def row541(start, unit_tok):
        i = next(k for k, ln in enumerate(L) if ln.startswith(start)
                 and L[k + 1] == unit_tok)
        return [_num(t) for t in L[i + 2:i + 7]]

    if row541("PIBpm (preços correntes)", "106 MT") != [gdp[y] for y in years]:
        raise ValueError("INE MZ 5.4.1: current PIB differs from Quadro 5.5.1")
    g541 = row541("Taxa de crescimento em Volume", "%")
    if any(abs(a - round(growth[y], 1)) > 0.051 for a, y in zip(g541, years)):
        raise ValueError(f"INE MZ 5.4.1: volume growth {g541} vs 5.5.3 {growth}")
    for unit_tok, unit in (("MT", "MZN"), ("US$", "USD")):
        i = next(k for k, ln in enumerate(L) if ln.startswith("PIBpm per capita")
                 and L[k + 1] == unit_tok)
        for y, tok in zip(years, L[i + 2:i + 7]):
            # Two rows share the label and differ only by unit, which is not
            # in the key -- the unit goes into the category, as printed.
            add("aggregate", f"PIBpm per capita ({unit_tok})",
                "Quadro 5.4.1 Indicadores macroeconómicos",
                "Anuário Q5.4.1", y, "current", "per_capita", _num(tok), unit)
    doc.close()
    return pd.DataFrame.from_records(rows)[_OUT_COLS]
