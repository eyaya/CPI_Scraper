"""Annual back series for INS Guinea GDP (a helper for guinea_ins_gdp, read as an extra).

'Note_analyse_des_comptes_nationaux_definitifs_et_rapides_2018_2024_VC.pdf' --
INS's note on the final and rapid annual accounts, 2018-2024 (2024 an
estimate; base year 2018). Its annex tables:

  Tableau 3  Agrégats macroéconomiques   GDP (million GNF and million US$), real
             growth, GDP per head, the GDP deflator, sector weights,
             sector growth and contributions to growth, demand ratios to GDP
  Tableau 4  value added by activity, current prices          (production)
  Tableau 5  GDP by expenditure, current prices               (expenditure)
  Tableau 6  value added by activity, previous-year prices    (production)
  Tableau 7  GDP by expenditure, previous-year prices         (expenditure)

Levels are million GNF as published. The published 'Deflateur du PIB' is the
year's current-price GDP over its previous-year-price GDP (2019: 188,309,424 /
173,350,728 = 108.6), i.e. an index with the PREVIOUS YEAR = 100 -- filed so,
not as a 2018-based index. A table that runs onto the next page
continues under its caption. Rows printed '-' are empty. Everything as
published; nothing derived. The quarterly note (the primary) prints only
quarters, so these annual rows never share an identity with it.
"""
from __future__ import annotations
import os
import re
import pdfplumber

_GROUP = "INS comptes nationaux annuels 2018-2024 (définitifs et rapides; 2024 estimation)"
_CAP_RE = re.compile(r"Tableau\s*(\d+)\s*:")
_TABLES = {
    4: ("production", "current", "level"),
    5: ("expenditure", "current", "level"),
    6: ("production", "constant", "level"),
    7: ("expenditure", "constant", "level"),
}
_PREV = "previous year prices"


def _num(s):
    s = re.sub(r"\s+", "", str(s or "")).replace(",", ".")
    return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _years(row):
    out = {}
    for i, c in enumerate(row):
        m = re.match(r"^(20\d\d)", re.sub(r"\s", "", str(c or "")))
        if m and i > 0:
            out[i] = m.group(1)
    return out


def _row(approach, label, year, basis, measure, value, unit, base=""):
    return {"approach": approach, "category": label, "category_group": _GROUP,
            "series_code": "", "geography": "National", "period": year,
            "frequency": "annual", "price_basis": basis,
            "seasonal_adjustment": "nsa", "measure": measure, "value": value,
            "unit": unit, "base_period": base}


def _aggregate_spec(label: str):
    """Tableau 3 row -> (approach, price_basis, measure, unit, base) or None."""
    low = label.lower()
    if low.startswith("pib (en millions gnf)"):
        return "aggregate", "current", "level", "million GNF", ""
    if low.startswith("pib (en millions de $"):
        return "aggregate", "current", "level", "USD million", ""
    if low.startswith("taux de croissance"):
        return "aggregate", "constant", "growth_yoy", "percent", _PREV
    if low.startswith("pib par tête (en millions"):
        return "aggregate", "current", "per_capita", "million GNF", ""
    if low.startswith("pib par tête (en $"):
        return "aggregate", "current", "per_capita", "USD", ""
    if low.startswith("deflateur du pib"):
        return "aggregate", "not_applicable", "deflator", "index", "previous year = 100"
    if low.startswith("poids du secteur"):
        return "production", "current", "share", "percent", ""
    if low.startswith("croissance du secteur"):
        return "production", "constant", "growth_yoy", "percent", _PREV
    if low.startswith("contribution"):
        return "production", "constant", "contribution", "percentage points", _PREV
    if "/ pib" in low or "/pib" in low:
        if "pression fiscale" in low or "recettes" in low or "ouverture" in low:
            return None
        return "expenditure", "current", "share", "percent", ""
    return None


def parse_note(path: str) -> list[dict]:
    rows = []
    cap = None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            caps = [int(m.group(1)) for m in _CAP_RE.finditer(page.extract_text() or "")]
            tables = [t for t in page.extract_tables() if t and _years(t[0])]
            # tables before the page's first caption continue the previous one
            lead = len(tables) - len(caps)
            for i, tb in enumerate(tables):
                if i >= lead:
                    cap = caps[i - lead] if i - lead < len(caps) else cap
                if cap not in _TABLES and cap != 3:
                    continue
                ycols = _years(tb[0])
                for r in tb[1:]:
                    label = _norm(r[0])
                    if not label:
                        continue
                    if cap == 3:
                        spec = _aggregate_spec(label)
                        if spec is None:
                            continue
                        approach, basis, measure, unit, base = spec
                    else:
                        approach, basis, measure = _TABLES[cap]
                        unit, base = "million GNF", (_PREV if basis == "constant" else "")
                        if label == "PIB" and approach == "production":
                            approach = "aggregate"
                    for c, y in ycols.items():
                        v = _num(r[c]) if c < len(r) else None
                        if v is not None:
                            rows.append(_row(approach, label, y, basis, measure, v, unit, base))
    return rows


def read(extras: list[str] | None) -> list[dict]:
    rows = []
    for x in extras or []:
        n = os.path.basename(x).lower()
        if n.startswith("note_analyse_des_comptes_nationaux") and n.endswith(".pdf"):
            rows += parse_note(x)
    return rows
