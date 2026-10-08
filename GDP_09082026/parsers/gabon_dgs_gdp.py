"""Gabon — Direction Générale de la Statistique (DGS, now INSTAT), Annuaire
statistique du Gabon 2004-2008, chapter V.1 "Comptes nationaux".

THE ONLY TEXT-LAYER NATIONAL ACCOUNTS THE NSO HAS PUT ONLINE. INSTAT's
"Comptes nationaux" page has read "en attente de contenu" since at least March
2025; its annual-publications page is in maintenance; the Annuaires 2020/2022
carry no accounts tables; and the DGS "Comptes rapides" 2006-2010 PDFs are
IMAGE-only (no OCR here). The 2004-2008 Annuaire, captured by the Wayback
Machine from the DGS's old host stat-gabon.org (`id_`, original bytes), prints
the accounts as text. Old (2004-2008), but the NSO's own.

Tables read (milliard FCFA unless stated):

* V.1.1.1  Ressources et emplois aux prix courants -- expenditure approach
           (+ imports and exports by product where printed)
* V.1.1.2  Ressources et emplois aux prix constants -- base 2001 (the
           chapter's methodology: "la DGS utilise maintenant les prix de
           l'année 2001 comme prix de base")
* V.1.1.3  Contributions à la croissance du PIB (%) + real GDP growth
* V.1.2.1  Valeur ajoutée par branche en francs courants -- production
* V.1.3.2  PIB par habitant (1000 FCFA and USD) -- the two PIB rows only

CREDITS ARE RECORDED, NOT SMOOTHED. V.1.1.1 is credited "DGSEE et DGE" (the
NSO with the Ministry's Direction Générale de l'Économie); V.1.1.2, V.1.2.1
and V.1.3.2 "DGS"; V.1.1.3 "DGSEE". The credit line is carried in
`category_group` on every row.

PUBLISHED INCONSISTENCY KEPT: V.1.2.1's GDP for 2004 and 2005 (3 868,1 /
4 715,8) is not V.1.1.1's (4 097,5 / 4 989,3); 2006-2008 agree. The chapter
says 2004-2005 are definitive and 2005-2008 provisional, and the two tables
carry different credits -- two estimates, both published. Both are kept (they
differ by series_code); the gap is pinned in `_KNOWN_GAPS` and re-checked
every run.

NUMBERS have space thousands AND a comma decimal ("1 128,9"), so each value
is one token ending in ",d"; ".." is missing and skipped. A row must yield one
cell per year column or it is refused, never shifted. The contributions table
heads its years "2 004" (a print glitch) -- read as 2004.

IDENTITIES checked every run: V.1.1.1 total resources = GDP + imports = total
uses = consumption + FBCF + stock change + exports (to 0.3 -- the table's own
footnote warns of rounding); V.1.2.1 sector subtotals = their branches,
primary + secondary + tertiary = total market value added, + non-market
services = GDP.

NOT COLLECTED: V.1.3.1 institutional-sector accounts (sector production,
operating surplus, saving -- no approach in this schema holds a sector
account); V.1.3.3 ratios (derived); the 2001-2007 Annuaire (an older edition
of the same tables, whose 2002-2007 constant-price series is the DGE's on a
1991 base, which the Annuaire itself says is not comparable).

CROSS-CHECK (as printed): GDP current 2008 7 032,8; real GDP 2008 4 087,1;
real growth 2005 23,4% (as printed); pétrole brut VA 2008 3 728,0; GDP per
head 2008 4 878,5 thousand FCFA / 9 805 USD.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_TOK = re.compile(r"-?\d+(?: \d{3})*,\d|\.\.")
_YEARS = ["2004", "2005", "2006", "2007", "2008"]
_TABLES = {  # caption id -> (price_basis, default measure, unit, credit)
    "V.1.1.1": ("current", "level", "milliard FCFA", "DGSEE et DGE"),
    "V.1.1.2": ("constant", "level", "milliard FCFA", "DGS"),
    "V.1.1.3": ("constant", "contribution", "percentage points", "DGSEE"),
    "V.1.2.1": ("current", "level", "milliard FCFA", "DGS"),
    "V.1.3.2": ("current", "per_capita", "", "DGS"),
}
_CAP = re.compile(r"^Tableau (V\.1\.[123]\.[123])\s*:\s*(.+)$")
_KNOWN_GAPS = {"2004": (4097.5, 3868.1), "2005": (4989.3, 4715.8)}
_PRODUCTION = {
    "PRIMAIRE": ["Agriculture, élevage, pêche", "Exploitation forestière",
                 "Pétrole brut", "Mines"],
    "SECONDAIRE": ["Industries agroalimentaires", "Industries du bois",
                   "Autres industries", "Raffinage", "Electricité, eau",
                   "Bâtiment et travaux publics", "Recherche, services pétroliers"],
    "TERTIAIRE": ["Transports", "Services", "Commerce",
                  "Droits et taxes à l'importation + TVA nette",
                  "Services bancaires, assurances"],
}


def _val(tok: str) -> float | None:
    return None if tok == ".." else float(tok.replace(" ", "").replace(",", "."))


def _read(path: str) -> dict:
    with pdfplumber.open(path) as pdf:
        lines = []
        for p in pdf.pages[145:156]:
            lines += (p.extract_text() or "").splitlines()
    tables, cur, section = {}, None, ""
    for ln in lines:
        ln = ln.strip()
        m = _CAP.match(ln)
        if m:
            cur = m.group(1) if m.group(1) in _TABLES else None
            if cur:
                tables[cur] = {"title": m.group(2).strip(), "rows": []}
                section = ""
            continue
        if cur is None:
            continue
        if ln.startswith(("Source", "Unité")) or re.fullmatch(r"\d{1,3}", ln):
            continue
        if ln in ("RESSOURCES", "EMPLOIS"):
            section = ln
            continue
        toks = list(_TOK.finditer(ln))
        if not toks:
            continue
        label = ln[:toks[0].start()].strip()
        if not label or re.fullmatch(r"[\d ]+", label):     # header years
            continue
        if cur == "V.1.3.2":                                 # "PIB 1000 FCFA ..."
            label = re.sub(r"\s+(1000 FCFA|USD|Milliards FCFA)$", r" (\1)", label)
        vals = [_val(t.group(0)) for t in toks]
        if len(vals) != len(_YEARS):
            continue                                        # refused, never shifted
        tables[cur]["rows"].append((section, re.sub(r"\s+\d$", "", label), vals))
    missing = [t for t in _TABLES if t not in tables or not tables[t]["rows"]]
    if missing:
        raise ValueError(f"DGS Annuaire 2004-2008: tables not read {missing}")
    return tables


def _check(tables: dict) -> None:
    def col(tid, lab, j, section=None):
        for s, l, v in tables[tid]["rows"]:
            if l == lab and (section is None or s == section):
                return v[j]
        raise ValueError(f"DGS {tid}: row {lab!r} not read")

    for j, y in enumerate(_YEARS):
        gdp = col("V.1.1.1", "Produit intérieur brut", j)
        res = col("V.1.1.1", "Total ressources", j)
        if abs(gdp + col("V.1.1.1", "Importations", j) - res) > 0.3:
            raise ValueError(f"DGS V.1.1.1 {y}: GDP + imports != resources")
        uses = sum(col("V.1.1.1", k, j) for k in (
            "Consommation finale", "Formation brute de capital fixe",
            "Variation de stocks", "Exportations"))
        if abs(uses - col("V.1.1.1", "Total emplois", j)) > 0.3:
            raise ValueError(f"DGS V.1.1.1 {y}: uses do not sum")
        tot = 0.0
        for parent, kids in _PRODUCTION.items():
            s = sum(col("V.1.2.1", k, j) for k in kids)
            if abs(s - col("V.1.2.1", parent, j)) > 0.3:
                raise ValueError(f"DGS V.1.2.1 {y}: {parent} != its branches")
            tot += col("V.1.2.1", parent, j)
        mkt = col("V.1.2.1", "Total des valeurs ajoutées marchandes", j)
        if abs(tot - mkt) > 0.3:
            raise ValueError(f"DGS V.1.2.1 {y}: sectors != market value added")
        pib = col("V.1.2.1", "Produit intérieur brut", j)
        if abs(mkt + col("V.1.2.1", "Services non marchands", j) - pib) > 0.3:
            raise ValueError(f"DGS V.1.2.1 {y}: GDP identity fails")
        if y in _KNOWN_GAPS:
            if (gdp, pib) != _KNOWN_GAPS[y]:
                raise ValueError(f"DGS {y}: the V.1.1.1 / V.1.2.1 GDP gap changed "
                                 f"({gdp} / {pib}) -- update _KNOWN_GAPS")
        elif abs(gdp - pib) > 0.05:
            raise ValueError(f"DGS {y}: new GDP gap between V.1.1.1 and V.1.2.1")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    tables = _read(path)
    _check(tables)
    out = []
    for tid, (pb, measure, unit, credit) in _TABLES.items():
        t = tables[tid]
        side = ""
        for section, lab, vals in t["rows"]:
            if tid == "V.1.3.2" and not lab.startswith("PIB"):
                continue                       # household per-head rows: no home
            cat, appr, meas, u, p = lab, None, measure, unit, pb
            if lab.startswith("Importations"):
                side = "Importations"
            elif lab.startswith("Exportations"):
                side = "Exportations"
            # Only the resources-and-uses tables nest these under imports /
            # exports; in V.1.2.1 "Services" is a branch of its own.
            if tid in ("V.1.1.1", "V.1.1.2") and side and lab in (
                    "Biens", "Services", "Correction territoriale", "Pétrole",
                    "Produits miniers", "Bois et ouvrages en bois", "Autres biens"):
                cat = f"{side}: {lab}"
            if tid in ("V.1.1.1", "V.1.1.2"):
                appr = "aggregate" if lab.startswith("Produit intérieur brut") \
                    else "expenditure"
            elif tid == "V.1.1.3":
                if lab.startswith("Taux de croissance"):
                    # growth rows share the contributions table, but a growth
                    # rate is percent, not percentage points
                    appr, meas, u = "aggregate", "growth_yoy", "percent"
                else:
                    appr = "expenditure"
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
                    "category_group": f"{tid} {t['title']} (source: {credit})",
                    "series_code": f"DGS Annuaire 2004-2008 {tid}",
                    "geography": "Total country", "period": y,
                    "frequency": "annual", "price_basis": p,
                    "seasonal_adjustment": "nsa", "measure": meas,
                    "value": v, "unit": u,
                    "base_period": "Constant 2001 prices"
                    if (tid == "V.1.1.2") else "",
                })
    return pd.DataFrame(out)
