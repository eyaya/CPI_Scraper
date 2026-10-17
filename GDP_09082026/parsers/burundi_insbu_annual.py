"""Annual back series for INSBU Burundi GDP (a helper for burundi_insbu_gdp, read as an extra).

The 'Comptes économiques' chapter of INSBU's ANNUAIRE STATISTIQUE DU BURUNDI
(édition 2024; 2016-2023), billion BIF ('milliards de Fbu'):

  Tableau 17.01  GDP by the production approach: output, intermediate
                 consumption, value added (each with its informal part), taxes,
                 GDP -- at current prices and at previous-year prices
  Tableau 17.02  value added by sector as a percent of GDP (current prices)
  Tableau 17.03-17.05  value added of the primary / secondary / tertiary
                 activities, current and previous-year prices
  Tableau 17.06  GDP by expenditure, current prices

The chapter is text, not a table grid, so each line is read as label + numbers
(French or dotted decimals, space-grouped thousands, 'ND' = not available). A
line is kept only when its number count matches the block's year columns (a
previous-year-price block prints one year fewer: it starts in 2017); a line
whose numbers cannot be told apart (e.g. '748 863 896,1' -- three values or one?)
is skipped rather than guessed. 'dont informelle' rows carry their parent in the
label. Each table is its own category_group (the sector tables each end in a
'Total VA'). Everything as published; nothing derived.
"""
from __future__ import annotations
import os
import re
import pdfplumber

_TAG = "INSBU Annuaire statistique 2024, ch. 17 Comptes économiques"
_TOK = re.compile(r"(?:(?<=\s)|^)(?:ND|-?\d{1,3}(?: \d{3})*(?:[.,]\d+)?)(?=\s|$)")
_CAP = re.compile(r"Tableau\s*17\.\s*(\d\d)\.")
_PREV = "previous year prices"


def _val(tok):
    if tok == "ND":
        return None
    return float(tok.replace(" ", "").replace(",", "."))


def parse_annuaire(path: str) -> list[dict]:
    rows = []
    table, years, basis, parent = None, [], None, ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "17." not in text and table is None:
                continue
            for line in text.split("\n"):
                line = line.strip()
                m = _CAP.search(line)
                if m:
                    table = m.group(1) if m.group(1) in ("01", "02", "03", "04", "05", "06") else None
                    years, basis, parent = [], "current", ""
                    continue
                if table is None:
                    continue
                if line.startswith("Libellés"):
                    years = re.findall(r"\b(20\d\d)\b", line)
                    continue
                low = line.lower()
                if re.match(r"^(en valeur courante|a prix courant)", low):
                    basis = "current"
                    continue
                if re.match(r"^(en volume|a prix constant)", low):
                    basis = "constant"
                    continue
                if low.startswith(("source", "comptes économiques")) or not years:
                    continue
                toks = _TOK.findall(line)
                if not toks:
                    continue
                first = _TOK.search(line)
                label = re.sub(r"\s+", " ", line[:first.start()]).strip()
                if len(label) < 3:
                    continue
                if len(toks) == len(years):
                    ys = years
                elif len(toks) == len(years) - 1 and basis == "constant":
                    ys = years[1:]
                else:
                    continue                       # cannot tell the numbers apart
                if label.lower().startswith("dont informelle"):
                    label = f"{parent} -- {label}"
                else:
                    parent = label
                is_pib = label.upper().startswith("PIB")
                if table == "06":
                    approach = "expenditure"
                else:
                    approach = "aggregate" if is_pib and table in ("01",) else "production"
                measure = "share" if table == "02" else "level"
                for y, t in zip(ys, toks):
                    v = _val(t)
                    if v is None:
                        continue
                    rows.append({
                        "approach": approach, "category": label,
                        "category_group": f"{_TAG}, Tableau 17.{table}",
                        "series_code": "", "geography": "National", "period": y,
                        "frequency": "annual", "price_basis": basis,
                        "seasonal_adjustment": "nsa", "measure": measure, "value": v,
                        "unit": "percent" if measure == "share" else "BIF billion",
                        "base_period": _PREV if basis == "constant" else "",
                    })
    return rows


def read(extras: list[str] | None) -> list[dict]:
    rows = []
    for x in extras or []:
        if "annuaire" in os.path.basename(x).lower() and x.lower().endswith(".pdf"):
            rows += parse_annuaire(x)
    return rows
