"""Gabon -- DGS Annuaire statistique du Gabon 2001-2007 (the edition before the
2004-2008 one `gabon_dgs_gdp` reads), chapter V.1 'Comptes nationaux', CURRENT
PRICES ONLY. Not a registry parser: `gabon_dgs_gdp.parse` hands it the PDF as
an extra (Wayback `id_` copy of stat-gabon.org's own file).

Read: V.1.1.1 resources and uses at current prices (credit DGSEE et DGE) and
V.1.2.1 value added by branch at current prices (DGS). 2001-2007, milliard
FCFA.

REFUSED: V.1.3.2 'par habitant'. Its "PIB 1000 FCFA" row prints, for
2002-2007, the national GDP total in milliard FCFA (3 438,6 ... 5 476,2 --
V.1.1.1's GDP to the decimal) under a per-head unit; a per-head GDP of 3.4
million FCFA in 2002 would be 4.7 thousand USD, not the 4 691 USD the next row
prints for the same year only by coincidence of the exchange rate. The row
cannot be both; it is not collected. Rows whose labels the PDF font garbles
('(cid:..)' glyph codes) are refused too.

NOT read, as `gabon_dgs_gdp` already decided for this edition: the constant-
price table V.1.1.2 (2001 at 1989 prices, 2002-2007 the DGE's on a 1991 base;
the Annuaire itself says 2001 is not comparable) and the contributions table
built on it; the institutional-sector tables. This edition is its own vintage
(its 2004-2007 figures differ from the 2004-2008 edition's): `category_group`
and `series_code` name the edition, nothing is spliced.

Same number rules as the 2004-2008 reader: space thousands + comma decimal,
'..' missing, a row must give one value per year or it is refused (rows
printed for 2001 only, and one row whose label the PDF font garbles, are
refused that way).
"""
from __future__ import annotations
import re
import pdfplumber

from .gabon_dgs_gdp import _TOK, _val

_YEARS = ["2001", "2002", "2003", "2004", "2005", "2006", "2007"]
_TABLES = {
    "V.1.1.1": ("current", "level", "milliard FCFA", "DGSEE et DGE"),
    "V.1.2.1": ("current", "level", "milliard FCFA", "DGS"),
}
_CAP = re.compile(r"Tableau (V\.1\.[123]\.[123])\s*:\s*(.+)$")
_SUB = ("Biens", "Services", "Correction territoriale", "Pétrole",
        "Produits miniers", "Bois et ouvrages en bois", "Autres biens")


def parse_annuaire(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        lines = []
        for p in pdf.pages:
            t = p.extract_text() or ""
            if "Tableau V.1" in t or "V.1.2" in t:
                lines += t.splitlines()
    tables, cur, section = {}, None, ""
    for ln in lines:
        ln = ln.strip()
        m = _CAP.search(ln)
        if m:
            cur = m.group(1) if m.group(1) in _TABLES else None
            if cur:
                tables[cur] = {"title": m.group(2).strip(), "rows": []}
                section = ""
            continue
        if cur is None:
            continue
        if ln.startswith(("Source", "Unité")) or ln in ("RESSOURCES", "EMPLOIS"):
            section = ln if ln in ("RESSOURCES", "EMPLOIS") else section
            continue
        toks = list(_TOK.finditer(ln))
        if not toks:
            continue
        label = ln[:toks[0].start()].strip()
        if not label or re.fullmatch(r"[\d ]+", label) or "(cid:" in label:
            continue
        if cur == "V.1.3.2":
            label = re.sub(r"\s+(1000 FCFA|USD)$", r" (\1)", label)
        vals = [_val(t.group(0)) for t in toks]
        if len(vals) != len(_YEARS):
            continue                                    # refused, never shifted
        tables[cur]["rows"].append((section, re.sub(r"\s+\d$", "", label), vals))
    missing = [t for t in _TABLES if t not in tables or not tables[t]["rows"]]
    if missing:
        raise ValueError(f"DGS Annuaire 2001-2007: tables not read {missing}")

    out = []
    for tid, (pb, measure, unit, credit) in _TABLES.items():
        t, side = tables[tid], ""
        for section, lab, vals in t["rows"]:
            if tid == "V.1.3.2" and not lab.startswith("PIB"):
                continue
            cat, u = lab, unit
            if lab.startswith("Importations"):
                side = "Importations"
            elif lab.startswith("Exportations"):
                side = "Exportations"
            if tid == "V.1.1.1" and side and lab in _SUB:
                cat = f"{side}: {lab}"
            if tid == "V.1.1.1":
                appr = "aggregate" if lab.startswith("Produit intérieur brut") \
                    else "expenditure"
            elif tid == "V.1.2.1":
                appr = "aggregate" if lab == "Produit intérieur brut" else "production"
            else:
                appr = "aggregate"
                u = "thousand FCFA" if "1000 FCFA" in lab else "USD"
            for y, v in zip(_YEARS, vals):
                if v is None:
                    continue
                out.append({
                    "approach": appr, "category": cat,
                    "category_group": f"Annuaire 2001-2007, {tid} {t['title']} "
                                      f"(source: {credit})",
                    "series_code": f"DGS Annuaire 2001-2007 {tid}",
                    "geography": "Total country", "period": y,
                    "frequency": "annual", "price_basis": pb,
                    "seasonal_adjustment": "nsa", "measure": measure,
                    "value": v, "unit": u, "base_period": ""})
    return out
