"""INS Tunisie national accounts (base 2015), from the server-rendered theme
pages www.ins.tn/statistiques/72, /73 and /75 -- the NSO's own figures, where
the BCT pages `tunisia_bct_gdp` reads give only current-price annual totals.

The pages are the same Drupal "statistiques par thèmes" markup `unemployment/`
and `labour/` already read for Tunisia: each series is a <table> whose first
rows are furniture (NoFilter / Unité / Source / the table's TITLE / blanks) and
whose columns are periods -- French ordinal quarters on /72
("troisième-trimestre 2024"), years on /73 and /75.

    /72  Comptes nationaux trimestriels -- 26 branches + taxes + PIB, quarterly:
         levels at 2015 prices, y/y and q/q at 2015 prices; levels, y/y and
         q/q at current prices (production approach).
    /73  Équilibre général annuel -- resources and uses (PIB, imports, final
         consumption public/private, GFCF, stocks, domestic demand, exports):
         levels and growth at current prices and at PREVIOUS-YEAR prices, and
         the price evolution (expenditure approach).
    /75  Valeurs ajoutées -- 26 branches, market / non-market subtotals, total
         VA, taxes, PIB: levels, growth and structure at current and at
         previous-year prices, annual (production approach).

PRICE BASES ARE RECORDED AS PRINTED. /72's constant series are "aux prix de
l'année 2015"; /73's and /75's are "aux prix de l'année précédente" -- a
previous-year-prices (chain) volume, NOT 2015 prices; `base_period` says which
on every constant row. The 2015-price quarterly levels are chain-linked and
not additive, so no identity is asserted on them.

IDENTITIES, per period, or the parse raises (0,05 per summed item, min 0,15):
  /72 current levels : 26 branches + taxes = PIB
  /75 levels (both)  : 26 branches = total VA = market + non-market subtotals;
                       total VA + taxes = PIB
  /73 levels (both)  : PIB + imports = total resources = domestic demand +
                       exports; public + private = final consumption; final
                       consumption + GFCF + stocks = domestic demand
  /73 vs /75         : the two pages' PIB agree, at current and previous-year
                       prices.

A ROLLING WINDOW. INS shows the latest 8 quarters and 6 years. GDP keeps no
merge keys, so each run's output is what the pages show that day: earlier
periods are NOT accumulated.

Values are TND million (levels), percent (growth, structure). The price
evolution table (/73, last) is a PRICE CHANGE in percent, filed as measure
`growth_yoy` with price basis `not_applicable` (the table title stays in
category_group); `deflator` is reserved for index levels. Labels are INS's own, French.
NOT READ: /74 (income, saving, external debt), /76 (GFCF by field).
"""
from __future__ import annotations

import io
import re

import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]
_ORD = {"premier": 1, "première": 1, "deuxième": 2, "troisième": 3, "quatrième": 4}
_PIB = re.compile(r"^Produit Int[ée]rieur Brut", re.I)
_TAX = re.compile(r"^Imp[ôo]ts nets de subventions", re.I)

# (page, table index) -> (title must contain, price, measure, unit, base)
_SPEC = {
    (72, 0): ("prix de l'année 2015 en million", "constant", "level", "TND million", "Prix de l'année 2015"),
    (72, 1): ("Glissement annuels (T/T-4) aux prix de l'année 2015", "constant", "growth_yoy", "percent", "Prix de l'année 2015"),
    (72, 2): ("Variations trimestrielles (T/T-1) aux prix de l'année 2015", "constant", "growth_qoq", "percent", "Prix de l'année 2015"),
    (72, 3): ("Aux prix courants en millions", "current", "level", "TND million", ""),
    (72, 4): ("Glissements annuels T/T-4 aux prix courants", "current", "growth_yoy", "percent", ""),
    (72, 5): ("Variations Trimestrielles T/T-1 aux prix courants", "current", "growth_qoq", "percent", ""),
    (73, 0): ("Ressources et emplois des biens et services aux prix courants", "current", "level", "TND million", ""),
    (73, 1): ("Evolution des ressources et emplois des biens et services aux prix courants", "current", "growth_yoy", "percent", ""),
    (73, 2): ("Ressources et emplois des biens et services aux prix de l'année préc", "constant", "level", "TND million", "Prix de l'année précédente"),
    (73, 3): ("Evolution des ressources et emplois des biens et services aux prix de l'année préc", "constant", "growth_yoy", "percent", "Prix de l'année précédente"),
    (73, 4): ("Evolution des prix des ressources et emplois", "not_applicable", "growth_yoy", "percent", ""),
    (75, 0): ("Valeurs ajoutées par secteur d'activité aux prix courants", "current", "level", "TND million", ""),
    (75, 1): ("Evolution des valeurs ajoutées par secteur d'activité aux prix courants", "current", "growth_yoy", "percent", ""),
    (75, 2): ("Structure de valeurs ajoutées par secteur d'activité aux prix courants", "current", "share", "percent", ""),
    (75, 3): ("Valeurs ajoutées par secteur d'activité aux prix de l'année préc", "constant", "level", "TND million", "Prix de l'année précédente"),
    (75, 4): ("Evolution des valeurs ajoutées par secteur d'activité aux prix de l'année préc", "constant", "growth_yoy", "percent", "Prix de l'année précédente"),
    (75, 5): ("Structure des Valeurs ajoutées par secteur d'activité aux prix de l'année préc", "constant", "share", "percent", "Prix de l'année précédente"),
}
_GROUP = {72: "Comptes nationaux trimestriels (Base 2015)",
          73: "Équilibre général annuel (Base 2015)",
          75: "Valeurs ajoutées (Base 2015)"}


def _period(col: str) -> tuple[str, str]:
    col = str(col).strip()
    m = re.fullmatch(r"(\w+)-trimestre\s+(\d{4})", col)
    if m and m.group(1) in _ORD:
        return f"{m.group(2)}-Q{_ORD[m.group(1)]}", "quarterly"
    if re.fullmatch(r"\d{4}", col):
        return col, "annual"
    raise ValueError(f"INS Tunisie: unreadable period header {col!r}")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).replace("’", "'")).strip()


def _read_page(path: str, page: int) -> dict[int, tuple[str, list, list]]:
    html = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for i, t in enumerate(pd.read_html(io.StringIO(html))):
        title = _norm(t.iloc[3, 0])
        cols = [c for c in t.columns[1:]]
        body = []
        for _, r in t.iloc[4:].iterrows():
            lab = r.iloc[0]
            if pd.isna(lab):
                continue
            # "--" is INS's missing cell -- never 0.
            vals = [None if pd.isna(v) or str(v).strip() in ("--", "-", "")
                    else float(v) for v in r.iloc[1:]]
            if all(v is None for v in vals):
                continue
            body.append((_norm(lab), vals))
        out[i] = (title, cols, body)
    return out


def _approach(page: int, label: str) -> str:
    if _PIB.match(label):
        return "aggregate"
    return "expenditure" if page == 73 else "production"


def _close(got, want, items, what):
    if abs(got - want) > max(0.15, 0.05 * items):
        raise ValueError(f"INS Tunisie {what}: {got:,.1f} vs printed {want:,.1f}")


def _check_levels(page: int, idx: int, cols, body):
    rows = dict(body)
    labs = [l for l, _ in body]
    for j, c in enumerate(cols):
        v = {l: rows[l][j] for l in labs if rows[l][j] is not None}
        tag = f"/{page} table {idx} {c}"
        if page in (72, 75):
            pib = next(l for l in labs if _PIB.match(l))
            tax = next(l for l in labs if _TAX.match(l))
            # Subtotals read "Sous total. Activités marchandes" on /75 and
            # plain "Activités marchandes" on /72.
            sub = lambda l: re.match(r"^(Sous total\. )?Activités (non )?marchandes$", l)
            stop = next((l for l in labs if sub(l) or l.startswith("Total des")), tax)
            branches = labs[:labs.index(stop)]
            tot = next((l for l in labs if l.startswith("Total des valeurs")), None)
            if tot:
                subs = [l for l in labs if sub(l)]
                if len(subs) != 2:
                    raise ValueError(f"INS Tunisie {tag}: subtotals {subs}")
                _close(sum(v[b] for b in branches), v[tot], len(branches), tag + " branches")
                _close(sum(v[s] for s in subs), v[tot], 2, tag + " subtotals")
                _close(v[tot] + v[tax], v[pib], 2, tag + " VA + taxes")
            else:
                _close(sum(v[b] for b in branches) + v[tax], v[pib],
                       len(branches) + 1, tag + " branches + taxes")
        else:   # /73
            g = lambda k: v[next(l for l in labs if l.startswith(k))]
            pib, imp = g("Produit Int"), g("Importations")
            tot, cf = g("Total Ressources"), g("Consommation finale")
            pub, prv = g("Consommation Publique"), g("Consommation priv")
            fbcf, stk = g("Formation Brute"), g("Variations de stocks")
            di, exp = g("Demande Int"), g("Exportations")
            _close(pib + imp, tot, 2, tag + " resources")
            _close(pub + prv, cf, 2, tag + " final consumption")
            _close(cf + fbcf + stk, di, 3, tag + " domestic demand")
            _close(di + exp, tot, 2, tag + " uses")


def parse_pages(paths: dict[int, str]) -> pd.DataFrame:
    """`paths` maps page number (72, 73, 75) -> saved HTML file."""
    rows, pib = [], {}
    for page in (72, 73, 75):
        if page not in paths:
            raise ValueError(f"INS Tunisie: page /{page} not supplied")
        tables = _read_page(paths[page], page)
        for (pg, idx), (must, price, measure, unit, base) in _SPEC.items():
            if pg != page:
                continue
            if idx not in tables:
                raise ValueError(f"INS Tunisie /{page}: table {idx} missing")
            title, cols, body = tables[idx]
            if must.lower() not in title.lower():
                raise ValueError(f"INS Tunisie /{page} table {idx}: title "
                                 f"{title!r} is not {must!r}")
            if len(body) < 9:
                raise ValueError(f"INS Tunisie /{page} table {idx}: {len(body)} rows")
            periods = [_period(c) for c in cols]
            if measure == "level" and not (page == 72 and price == "constant"):
                _check_levels(page, idx, cols, body)
            for lab, vals in body:
                for (per, freq), v in zip(periods, vals):
                    if v is None:
                        continue
                    if measure == "level" and _PIB.match(lab) and page in (73, 75):
                        pib.setdefault((price, per), {})[page] = v
                    rows.append({
                        "approach": _approach(page, lab), "category": lab,
                        "category_group": _GROUP[page],
                        "series_code": f"INS-TN-{page}-{idx}",
                        "geography": "National", "period": per, "frequency": freq,
                        "price_basis": price, "seasonal_adjustment": "nsa",
                        "measure": measure, "value": v, "unit": unit,
                        "base_period": base})
    for (price, per), d in pib.items():
        if len(d) == 2 and abs(d[73] - d[75]) > 0.15:
            raise ValueError(f"INS Tunisie {per} {price}: PIB /73 {d[73]} vs /75 {d[75]}")
    df = pd.DataFrame.from_records(rows)[_OUT_COLS]
    key = ["series_code", "category", "period"]
    if df.duplicated(key).any():
        raise ValueError(f"INS Tunisie: duplicate rows {df[df.duplicated(key)].head(3)}")
    return df
