"""Parser for ANSADE Mauritania foreign-trade publications (PDF, Direction Générale des
Douanes / SYDONIA data compiled and published by ANSADE).

Two publication families, both read through pdfplumber's table extraction
(the text layer joins thousands with spaces, "116 978", so cells are needed):

  * "Note trimestrielle du commerce extérieur" (recent layout, five quarter
    columns "2025T3 ... 2026T3"): the summary table (Exportations,
    Importations, Balance commerciale, Échanges commerciaux -- million MRU),
    and the value tables whose first line is "Total exportations" /
    "Total importations" equal to the summary's figures (the tonnage twins of
    each table print other totals and are not read): exports by product group
    (the table starting "Métaux et minéraux"), imports by product type (the
    table starting "produits pétroliers et leurs dérivés") and exports /
    imports by destination / origin (tables starting with a continent).
  * "Annuaire des statistiques du commerce extérieur" (five year columns):
    Tableau 1 (exports, imports, balance, milliards MRU), Tableau 3 (exports by
    product), Tableau 4 (exports by destination), Tableau 11 (imports by type),
    Tableau 12 (imports by origin), million MRU.
Shares ("Structure"), coverage rates and growth are not read. Partner lines:
continents, blocs and "Autres ..." are groups, the rest countries. Product
tables are national groupings; sub-items (e.g. "Poissons frais" under
"Produits de pêche") are kept with their printed labels. Across files the
newest (by period covered) wins.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

from ._common import row
from ..schema import KEY

_GROUP = re.compile(r"^(europe|asie|afrique|am[ée]rique|oc[ée]anie|uma|cedeao|union europ|moyen-orient|"
                    r"autres?\b|reste|maghreb|pays arabes)", re.I)
_CONT = re.compile(r"^(europe|asie|afrique|am[ée]rique)", re.I)


def _num(s):
    s = (s or "").replace("−", "-").replace("\xa0", " ").strip()
    if not re.fullmatch(r"-?\d{1,3}( \d{3})*(,\d+)?|-?\d+(,\d+)?", s):
        return None
    return float(s.replace(" ", "").replace(",", "."))


def _clean_rows(tab):
    """-> (label, [cells after the label]) per row: label = last non-empty
    text cell before the first numeric cell."""
    out = []
    for r in tab:
        cells = [(c or "").strip() for c in r]
        idx = next((i for i, c in enumerate(cells) if _num(c) is not None and i > 1), None)
        if idx is None:
            continue
        lab = next((c for c in reversed(cells[:idx]) if c and not re.fullmatch(r"\d+", c)), "")
        if lab.lower() in ("indicateur", "id", "produits"):
            continue
        # empty cells are layout columns of the extraction, not blank values
        # (ANSADE prints "-" for nil, which keeps its place)
        out.append((lab, [c for c in cells[idx:] if c != ""]))
    return out


def _periods(tab):
    for r in tab[:3]:
        cells = [(c or "").strip() for c in r]
        qs = [re.fullmatch(r"(20\d{2})T([1-4])", c) for c in cells]
        if sum(1 for q in qs if q) >= 3:
            return [(f"{q.group(1)}-Q{q.group(2)}", "quarterly") for q in qs if q]
        ys = [c for c in cells if re.fullmatch(r"20\d{2}", c)]
        if len(ys) >= 3:
            return [(y, "annual") for y in ys]
    return None


def _emit(rows_, pers, fl, kind, sc, mult, skip_total=True):
    out = []
    for lab, cells in rows_:
        if not lab or re.match(r"^total", lab, re.I) and skip_total:
            continue
        raw = cells[:len(pers)]
        vals = [_num(c) for c in raw]
        if len(vals) < len(pers) or any(v is None and c not in ("-", "–") for v, c in zip(vals, raw)):
            continue
        if kind == "partner":
            key = dict(partner=lab, partner_type="group" if _GROUP.match(lab) else "country")
        else:
            key = dict(commodity=lab[0].upper() + lab[1:], commodity_classification="national")
        for (p, f), v in zip(pers, vals):
            if v is not None:
                out.append(row(tradeflow=fl, period=p, frequency=f, value=v, unit="MRU",
                               unit_multiplier=mult, series_code=sc, **key))
    return out


def parse_file(path):
    base = os.path.basename(path)
    out, summary = [], {}
    with pdfplumber.open(path) as pdf:
        tables = []
        for pg in pdf.pages:
            text = pg.extract_text() or ""
            m = re.search(r"Tableau\s+(\d+(\.\d+)?)\s*(\(suite\))?\s*:", text)
            for t in pg.extract_tables():
                tables.append((m.group(1) if m else "", text, t))
    annuaire = "annuaire" in base.lower()
    # 1) summary / Tableau 1
    for tno, text, t in tables:
        pers = _periods(t)
        if not pers:
            continue
        rows_ = _clean_rows(t)
        labs = {lab.lower(): cells for lab, cells in rows_}
        if "exportations" in labs and "importations" in labs and "balance commerciale" in labs:
            if annuaire and "milliards" not in text.lower():
                continue
            mult = 1e9 if annuaire else 1e6
            for lab, fl in (("exportations", "export"), ("importations", "import"),
                            ("balance commerciale", "balance"), ("échanges commerciaux", "total")):
                cells = labs.get(lab)
                if not cells:
                    continue
                for (p, f), c in zip(pers, cells):
                    v = _num(c)
                    if v is not None:
                        out.append(row(tradeflow=fl, period=p, frequency=f, value=v, unit="MRU",
                                       unit_multiplier=mult, series_code=f"{base}:summary"))
                        if fl in ("export", "import"):
                            summary[(fl, p)] = v
            break
    # 2) value tables
    done = set()
    cont = None            # (flow, kind, sc, pers) of the note table being continued
    for tno, text, t in tables:
        pers = _periods(t)
        if not pers:
            continue
        rows_ = _clean_rows(t)
        if not rows_:
            continue
        first = rows_[0][0].lower()
        if not annuaire and cont and not first.startswith("total") and pers == cont[3]:
            out += _emit(rows_, pers, cont[0], cont[1], cont[2], 1e6)
            continue
        if first.startswith("total"):
            cont = None
        if not first.startswith(("total exportations", "total importations")):
            # continuation pages of an annuaire table carry no total line
            if annuaire and tno and tno.split(".")[0] in ("3", "4", "11", "12") and tno in done:
                fl = "export" if tno in ("3", "4") else "import"
                kind = "partner" if tno in ("4", "12") else "product"
                out += _emit(rows_, pers, fl, kind, f"{base}:Tableau {tno}", 1e6)
            continue
        fl = "export" if "export" in first else "import"
        tot = [_num(c) for c in rows_[0][1][:len(pers)]]
        if annuaire:
            if tno not in ("3", "4", "11", "12") or "million" not in text.lower():
                continue
            kind = "partner" if tno in ("4", "12") else "product"
            done.add(tno)
            sc = f"{base}:Tableau {tno}"
        else:
            # value table only if its total equals the summary's (tonnage twins differ)
            if not summary or any(summary.get((fl, p)) != v for (p, _), v in zip(pers, tot)):
                continue
            second = rows_[1][0] if len(rows_) > 1 else ""
            if _CONT.match(second):
                kind = "partner"
            elif re.match(r"^(métaux|produits pétroliers)", second, re.I):
                kind = "product"
            else:
                continue
            sig = (fl, kind)
            if sig in done:
                continue
            done.add(sig)
            sc = f"{base}:{fl}-{kind}"
            cont = (fl, kind, sc, pers)
        out += _emit(rows_, pers, fl, kind, sc, 1e6)
    return out


def _order(path):
    n = os.path.basename(path)
    m = re.search(r"(\d)T[-\s]?(20\d{2})", n)
    if m:
        return (int(m.group(2)), int(m.group(1)))
    m = re.search(r"(20\d{2})", n)
    return (int(m.group(1)), 5) if m else (0, 0)


def parse(path, extras=None):
    frames, seen = [], set()
    for f in sorted({path, *(extras or [])}, key=_order, reverse=True):
        df = pd.DataFrame(parse_file(f))
        if df.empty:
            continue
        df = df.loc[~df[KEY].astype(str).duplicated()]     # a table repeated on two pages
        k = df[KEY].astype(str).agg("|".join, axis=1)
        frames.append(df.loc[~k.isin(seen)])
        seen |= set(k)
    return pd.concat(frames, ignore_index=True)
