"""Back series for Mozambique: INE Anuário Estatístico 2019, chapter 5.4
'Agregados macroeconómicos' (sourced to INE Direcção de Contas Nacionais e
Indicadores Globais). Not a registry parser: `mozambique_ine_gdp.parse` hands
it the 2019 yearbook as an extra.

This edition predates the 2019 rebasing: its constant prices are 2014 prices
(the 2025 edition the caller reads uses 2019 prices). The two are never
chained; `category_group` / `series_code` name the edition and table, and the
constant levels carry 'Constant 2014 prices'.

Read:
  Q 5.4.1  PIBpm at current and at constant 2014 prices, real growth, and PIBpm
           per capita (MT and US$), 2015-2019
  Q 5.4.2  GDP by expenditure at current and constant 2014 prices, 2018-2019
  Q 5.4.4  volume % change of GDP by activity (production), 2015-2019

Not read: Q 5.4.3 deflator growth (as the caller decides for the 2025
edition), the fiscal / external / wage ratios of Q 5.4.1.

PyMuPDF returns one cell per line; labels are bilingual ('Portuguese/English')
and the Portuguese half is kept, as in the caller. A row must carry exactly
the expected number of values or the table raises. Q 5.4.2's identity
(consumption + GFCF + exports - imports = PIB) is checked at both price bases.
"""
from __future__ import annotations
import re
import fitz

_NUM = re.compile(r"^-?\s*\d{1,3}(?:\s\d{3})*(?:,\d+)?$")
_BASE = "Constant 2014 prices"
_ED = "Anuário 2019"


def _f(t: str) -> float:
    return float(re.sub(r"\s+", "", t).replace(",", "."))


def _pt(label: str) -> str:
    return re.sub(r"\s+", " ", label.split("/")[0]).strip(" '")


def _cells(doc, start: str, stop: str = "Fonte"):
    for page in doc:
        cells = [c.strip() for c in page.get_text().splitlines() if c.strip()]
        idx = [i for i, c in enumerate(cells) if c.startswith(start)]
        if idx:
            i = idx[0]
            j = next((k for k in range(i, len(cells)) if cells[k].startswith(stop)),
                     len(cells))
            return cells[i:j]
    raise ValueError(f"INE MZ 2019: '{start}' not found")


def _rows(cells, n):
    out, label, nums = [], [], []
    for c in cells:
        if _NUM.match(c):
            nums.append(_f(c))
            if len(nums) == n:
                out.append((" ".join(label), nums))
                label, nums = [], []
        else:
            if nums:
                raise ValueError(f"INE MZ 2019: row {' '.join(label)!r} cut short {nums}")
            label.append(c)
    return out


def _rec(approach, cat, group, code, y, basis, measure, v, unit, base=""):
    return {"approach": approach, "category": cat, "category_group": group,
            "series_code": code, "geography": "National", "period": y,
            "frequency": "annual", "price_basis": basis,
            "seasonal_adjustment": "nsa", "measure": measure, "value": v,
            "unit": unit, "base_period": base}


def parse_anuario(path: str) -> list[dict]:
    doc = fitz.open(path)
    out = []
    years5 = ["2015", "2016", "2017", "2018", "2019"]

    # Q 5.4.1 -- the page opens with '5.4 Agregados macroeconómicos'
    c = _cells(doc, "5.4 Agregados macroecon", "Taxa de crescimento da Popula")
    g, code = f"{_ED}, Quadro 5.4.1 Indicadores macroeconómicos", f"{_ED} Q5.4.1"
    want = {
        "PIBpm (preços correntes)": ("current", "level", "MZN million", ""),
        "PIBpm (preços constantes de 2014)": ("constant", "level", "MZN million", _BASE),
        "Taxa de crescimento em Volume": ("constant", "growth_yoy", "percent", ""),
    }
    seen_pc = 0
    for i, cell in enumerate(c):
        lab = _pt(cell)
        unit = c[i + 1] if i + 1 < len(c) else ""
        vals = c[i + 2:i + 7]
        if len(vals) != 5 or not all(_NUM.match(v) for v in vals):
            continue
        nums = [_f(v) for v in vals]
        if lab in want:
            b, m, u, base = want[lab]
            cat = "PIB (pm)" if m == "level" or m == "growth_yoy" else lab
            for y, v in zip(years5, nums):
                out.append(_rec("aggregate", cat, g, code, y, b, m, v, u, base))
        elif lab == "PIBpm per capita":
            u = "USD" if "US" in unit else "MZN"
            seen_pc += 1
            for y, v in zip(years5, nums):
                out.append(_rec("aggregate", f"PIBpm per capita ({'US$' if u == 'USD' else 'MT'})",
                                g, code, y, "current", "per_capita", v, u))
    if len(out) != 25 or seen_pc != 2:
        raise ValueError(f"INE MZ 2019 Q5.4.1: {len(out)} values read")

    # Q 5.4.2 -- expenditure, 2018-2019, current then constant 2014
    c = _cells(doc, "Consumo Total/Total Consumption")
    rows = _rows(c, 4)
    if len(rows) != 7 or not _pt(rows[-1][0]).startswith("PIB"):
        raise ValueError(f"INE MZ 2019 Q5.4.2: rows {[r[0] for r in rows]}")
    g, code = f"{_ED}, Quadro 5.4.2 PIB por tipo de despesa", f"{_ED} Q5.4.2"
    vals = {_pt(l): v for l, v in rows}
    imp = vals["Importações de Bens e Serviços"]
    for j in (2, 3):
        tot = (vals["Consumo Total"][j] + vals["Formação Bruta de Capital fixo"][j]
               + vals["Exportações de Bens e Serviços"][j] - imp[j])
        if abs(tot - vals["PIB (pm)"][j]) > 2:
            raise ValueError(f"INE MZ 2019 Q5.4.2: constant identity fails ({j})")
    # PUBLISHED ERROR, REFUSED: the current-price imports cells repeat the
    # constant-price figures (497 001 / 497 104), and with them the current-
    # price identity misses PIB by ~240 000 million MT. Those two cells are
    # not collected; pinned so a corrected reprint is noticed.
    if imp[:2] != imp[2:]:
        raise ValueError("INE MZ 2019 Q5.4.2: current imports no longer repeat "
                         "the constant ones -- review the refusal")
    for lab, v in vals.items():
        appr = "aggregate" if lab.startswith("PIB") else "expenditure"
        for j, y in enumerate(("2018", "2019")):
            if not lab.startswith("Importações"):
                out.append(_rec(appr, lab, g, code, y, "current", "level", v[j],
                                "MZN million"))
            out.append(_rec(appr, lab, g, code, y, "constant", "level", v[j + 2],
                            "MZN million", _BASE))

    # Q 5.4.4 -- production, volume % change 2015-2019
    c = _cells(doc, "Agricultura, produção animal")
    rows = _rows(c, 5)
    if len(rows) < 15 or not _pt(rows[-1][0]).startswith("Produto Interno Bruto"):
        raise ValueError(f"INE MZ 2019 Q5.4.4: rows {[r[0] for r in rows]}")
    g, code = f"{_ED}, Quadro 5.4.4 PIB óptica de produção, variação em volume", \
        f"{_ED} Q5.4.4"
    for lab, v in rows:
        lab = _pt(lab)
        appr = "aggregate" if lab.startswith("Produto Interno Bruto") else "production"
        for y, x in zip(years5, v):
            out.append(_rec(appr, lab, g, code, y, "constant", "growth_yoy", x, "percent"))
    return out
