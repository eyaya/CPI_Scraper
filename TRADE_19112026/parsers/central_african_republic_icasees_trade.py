"""Parser for ICASEES (Central African Republic) "Annuaire statistique 2018-2021",
chapter III-7 Commerce extérieur.

Four tables of one consistent family are read (their "Total" lines agree
with each other), annual 2018-2021, values in millions (FCFA, the national
currency; the captions print the scale as "en million(s) FOB / de CAF"):

  Tableau 172  exports (FOB) by main product   -> national commodity list
  Tableau 173  exports by destination continent -> groups ("PNDA" = pays non
               déterminés ailleurs, a group)
  Tableau 175  imports (CAF) by main product    -> national commodity list
  Tableau 176  imports by continent of origin   -> groups
"Total" lines are the all-products / all-partners figures. "ND" (2018) is not
available and skipped; the two variation columns (%) are not read.
The continent tables' "Total" lines are not emitted (Tableau 173 prints 49 698
for 2020 where Tableau 172 prints 49 696; the product table's total is kept).
Not read: Tableau 171 (its 2018-2021 header has only three value columns, so
the years cannot be matched), Tableaux 174 and 177 (product groups whose
values disagree with Tableaux 172 / 175 for the same year and label, and
quantities in mixed units).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from ._common import row, to_number, _fold

YEARS = ["2018", "2019", "2020", "2021"]
_TABLES = {"172": ("export", "commodity", "fob"), "173": ("export", "partner", "fob"),
           "175": ("import", "commodity", "cif"), "176": ("import", "partner", "cif")}
_TOK = r"(ND|-?\d{1,3}(?: \d{3})+|-?\d+(?:,\d+)?|#DIV/0!)"


def parse(path: str, extras=None) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        lines = []
        for page in pdf.pages[140:170]:
            lines += (page.extract_text() or "").split("\n")
    out, cur, pending = [], None, ""
    for ln in lines:
        ln = ln.strip()
        m = re.match(r"^Tableau\s*(\d+)\s*:", ln)
        if m:
            cur = _TABLES.get(m.group(1))
            tab = m.group(1)
            pending = ""
            continue
        if cur is None:
            continue
        if ln.startswith("Source"):
            cur = None
            continue
        mm = re.match(rf"^(.*?)\s+{_TOK}\s+{_TOK}\s+{_TOK}\s+{_TOK}\s+{_TOK}\s+{_TOK}$", ln)
        if not mm:
            # a wrapped label ("Gommes" / "arabiques ND ND") -- skip such rows
            continue
        label = mm.group(1).strip()
        if not label or _fold(label) in ("pays", "produits", "flux", "nd"):
            continue
        flow, kind, basis = cur
        vals = [mm.group(i) for i in range(2, 6)]
        if _fold(label) == "total":
            if kind == "partner":
                continue      # the product table's total is kept (173 prints 49 698 for 172's 49 696)
            kw = dict(commodity=None, partner=None)
        elif kind == "commodity":
            kw = dict(commodity=label, commodity_classification="national")
        else:
            kw = dict(partner=label, partner_type="group")
        for y, v in zip(YEARS, vals):
            if v in ("ND", "#DIV/0!"):
                continue
            x = to_number(v.replace(" ", ""), decimal=",")
            if x is None or x < 0:
                continue
            out.append(row(tradeflow=flow, period=y, frequency="annual", value=x, unit="XAF",
                           unit_multiplier=1e6, price_basis=basis, series_code=f"T{tab}", **kw))
    return pd.DataFrame.from_records(out)
