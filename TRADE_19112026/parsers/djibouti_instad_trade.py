"""Parser for Djibouti INSTAD (ex-DISED) Annuaire statistique, chapter 5.1
"Commerce extérieur" (Tier 3 PDF).

Collected from every edition on INSTAD's Firebase bucket (2017, 2018, 2022-2025):
  Tableau 5.1.1 "Importations par grands groupes en Valeur et en Volume":
      17 groups + "Transactions spéciales" + "Total importations spéciales";
      Valeur CAF in millions of FDJ (-> value, DJF, cif, trade_system special)
      and Volume in tonnes (-> measure quantity, unit tonnes: the table does not
      say net or gross weight). Each edition prints 4-5 years.
  Tableau 5.1.2 "Flux du commerce selon le régime douanier": the
      "Réexportations" row only (value, millions FDJ; quantity, tonnes) -- the
      one export-side flow INSTAD prints. Column order is Valeur, Volume here
      (Volume, Valeur in 5.1.1).
  Tableau 5.1.6 "Importations par pays en valeur et en volume" (2017 and 2018
      editions: 2016 and 2017): every origin country, VALEUR EN FDJ (units)
      and POIDS EN KG (-> net_weight kg is not claimed either: measure
      quantity, unit kg). Partner = the French label as printed.
Not collected: Tableau 5.1.3 (imports by tax regime), 5.1.4 (product x origin,
volume) and 5.1.5 (a mixed list of HS sections, chapters and headings, not a
complete chapter table).

Figures use a space as thousands separator, which the PDF stores as separate
words ("173 851"); a digit group is re-joined to the number before it only
when the gap between them is a word space (< 5 pt) -- column gaps are > 9 pt.
A row is kept only if it then has exactly the expected number of figures.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import row, to_number
from .tanzania_nbs_trade import _lines, _newest_wins

_NUMTOK = re.compile(r"^-?[\d   ]+(,\d+)?$")


def _merge_numbers(ln):
    """Words of a line with space-separated digit groups re-joined."""
    out = []
    for w in ln:
        t = w[4]
        if out and re.fullmatch(r"\d{3}", t) and _NUMTOK.match(out[-1][4]) and (w[0] - out[-1][2]) < 5:
            p = out[-1]
            out[-1] = (p[0], p[1], w[2], w[3], p[4] + " " + t)
        else:
            out.append(tuple(w[:5]))
    return out


def _split(ln, n):
    toks = _merge_numbers(ln)
    vals = []
    while toks and (_NUMTOK.match(toks[-1][4]) or toks[-1][4] in ("-", "–")):
        vals.insert(0, toks.pop()[4])
    label = " ".join(t[4] for t in toks).strip()
    if len(vals) == n + 1 and re.fullmatch(r"\d{1,2}", vals[0]) and not label:
        vals = vals[1:]                       # a row number printed alone before the figures
    label = re.sub(r"^\d{1,2}\s+(?=[A-Za-zÀ-ÿ])", "", label)   # leading row number
    return label, vals


def _edition(path):
    m = re.findall(r"(20\d{2})", os.path.basename(path))
    return int(m[-1]) if m else 0


def _years_from(text):
    ys = re.findall(r"\b(20\d{2})\b", text)
    return ys


def parse_one(path):
    import fitz
    ed = _edition(path)
    doc = fitz.open(path)
    out = []
    try:
        for pno in range(doc.page_count):
            raw = doc[pno].get_text()
            if "Tableau 5.1" not in raw:
                continue
            lines = _lines(doc[pno])
            texts = [" ".join(w[4] for w in ln) for ln in lines]
            for i, t in enumerate(texts):
                m = re.match(r"^Tableau\s*5\.1\.([126])\s*[:\-]", t)
                if not m or re.search(r"\.{6,}", t) or "(suite" in t.lower() or "suite" in t.lower():
                    if not (m and m.group(1) == "6"):
                        continue
                kind = m.group(1)
                ser = f"Annuaire {ed} Tableau 5.1.{kind} p{pno + 1}"
                j = next((k for k in range(i + 1, len(texts)) if re.match(r"^(Source|Annuaire|Tableau)", texts[k])),
                         len(texts))
                if kind in ("1", "2"):
                    unit_line = " ".join(texts[i:i + 3])
                    has_vol = bool(re.search(r"tonnes", unit_line))
                    if not re.search(r"millions de FDJ", unit_line, re.I) or (kind == "1" and not has_vol):
                        continue
                    k = next((k for k in range(i + 1, min(i + 6, j)) if len(set(_years_from(texts[k]))) >= 3
                              and not texts[k].startswith("Unit")), None)
                    if k is None:
                        continue
                    years = _years_from(texts[k])
                    n = (2 if has_vol else 1) * len(years)
                    pending = ""
                    for ln in lines[k + 1:j]:
                        label, vals = _split(ln, n)
                        if len(vals) != n:
                            if not vals and label and not re.match(r"^(Volume|Valeur|GRAND|R[ée]gime|Dont)", label, re.I):
                                pending = label if not pending or label[:1].isupper() else pending + " " + label
                            continue
                        if not label and pending:
                            label, pending = pending, ""
                        elif pending and label[:1].islower():
                            label, pending = pending + " " + label, ""
                        else:
                            pending = ""
                        if not label:
                            continue
                        if kind == "2" and not re.match(r"^R[ée]exportations?$", label, re.I):
                            continue
                        # 2018 edition: the wrapped word "verre" lands inside the label
                        if label == "Ouvrages verre en pierre, ciment, céramique,":
                            label = "Ouvrages en pierre, ciment, céramique, verre"
                        total = re.match(r"^total\s+importations", label, re.I)
                        for c, y in enumerate(years):
                            if has_vol:
                                a, b = vals[2 * c], vals[2 * c + 1]
                                vol, val = (a, b) if kind == "1" else (b, a)
                            else:
                                vol, val = None, vals[c]
                            for tok, measure, unit, mult in ((val, "value", "DJF", 1e6), (vol, "quantity", "tonnes", 1.0)):
                                v = to_number(tok) if tok is not None else None
                                if v is None:
                                    continue
                                if kind == "2":
                                    out.append(row(tradeflow="re_export", period=y, frequency="annual", value=v,
                                                   unit=unit, unit_multiplier=mult, measure=measure, series_code=ser))
                                else:
                                    out.append(row(tradeflow="import", period=y, frequency="annual", value=v,
                                                   unit=unit, unit_multiplier=mult, measure=measure,
                                                   price_basis="cif" if measure == "value" else "",
                                                   trade_system="special",
                                                   commodity=None if total else label,
                                                   commodity_classification="" if total else "national",
                                                   series_code=ser))
                else:   # 5.1.6 imports by country, one year
                    ys = _years_from(t)
                    if not ys:
                        continue
                    y = ys[-1]
                    if not re.search(r"VALEUR EN FDJ", " ".join(texts[i:i + 3])):
                        # continuation pages repeat the caption; header may sit on the next line
                        pass
                    for ln in lines[i + 1:j]:
                        label, vals = _split(ln, 2)
                        if len(vals) != 2:
                            continue
                        mm = re.match(r"^([A-Z]{2})\s+(.+)$", label)
                        if not mm:
                            continue
                        name = mm.group(2).strip()
                        if re.match(r"^total", name, re.I):
                            continue
                        for tok, measure, unit in ((vals[0], "value", "DJF"), (vals[1], "quantity", "kg")):
                            v = to_number(tok)
                            if v is None:
                                continue
                            out.append(row(tradeflow="import", period=y, frequency="annual", value=v, unit=unit,
                                           measure=measure, price_basis="", partner=name, partner_type="country",
                                           series_code=ser))
    finally:
        doc.close()
    return out


def parse(path, extras=None):
    files = sorted([path] + list(extras or []), key=_edition)
    return _newest_wins([parse_one(f) for f in files])
