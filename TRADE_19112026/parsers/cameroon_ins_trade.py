"""Parser for INS Cameroun "Note sur le commerce extérieur" (annual / quarterly notes).

INS publishes one note per year (and some quarterly / half-year notes), built
from DGD/MINFI customs data. Every note is a text PDF whose tables carry ruling
lines, so pdfplumber's table finder returns clean cells. Three table shapes
are read (classified by their content, never by page number):

AGGREGATES ("Évolution des échanges avec l'extérieur", "Évolution de la
  balance commerciale"): rows Exportations / Importations / Balance commerciale
  / Echanges globaux, plus the NSO's own groupings (Pétrole brut, Gaz,
  Carburants et lubrifiants, Hydrocarbures, "hors pétrole brut" ...), with
  Q (milliers de tonnes) and V (milliards de FCFA) columns for several years
  ("2017" ... "janv-déc 2025 (b)") or quarters ("trim 1 2018"). A grouping
  label loses its flow word ("Exportations hors pétrole brut" -> commodity
  "hors pétrole brut", classification national) so the balance and the flows
  of one grouping share a commodity. "Taux de couverture" (a ratio),
  variations and shares are not read; cumulative windows (janv-juin,
  janvier-septembre) have no frequency in the schema and are skipped.
PARTNERS ("Principaux clients / fournisseurs du Cameroun en <year>",
  "Exportations vers / importations en provenance des pays frontaliers"):
  Pays / Quantité / Valeur / Poids, one year (read from the table title).
PRODUCTS ("Évolution des (principaux produits d') importations / exportations"):
  only the rows whose printed code is an HS chapter (two digits) are kept
  (hs2); headings, sub-headings and tariff lines ("18.01", "2713",
  "03.06.13.00") and "section N" totals are finer or coarser than HS2 and are
  not read. Tables without printed codes (the 2025 note) are not read.

Scale and currency are read from the table title / caption ("en milliards de
FCFA", "valeurs en millions de FCFA", "Quantité en milliers de tonnes"); a
table whose value scale cannot be read is dropped. Values are as printed
(space thousands separators, decimal comma).
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

from ._common import row, to_number, _fold
from . import _pdfwords as W

ISO3 = "CMR"
_FLOW_WORDS = (("exportations", "export"), ("importations", "import"),
               ("balance commerciale", "balance"), ("echanges globaux", "total"))


def _c(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""


def _num(s: str):
    s = _c(s)
    if not s or "%" in s or not re.search(r"\d", s):
        return None
    if not re.fullmatch(r"-?[\d   ]+(,\d+)?", s):
        return None
    return to_number(s, decimal=",")


def _value_scale(text: str):
    t = _fold(text)
    if re.search(r"milliards?\s+de\s+f\.?\s*cfa", t):
        return 1e9
    if re.search(r"millions?\s+de\s+f\.?\s*cfa", t):
        return 1e6
    return None


def _qty_scale(text: str):
    t = _fold(text)
    if re.search(r"milliers?\s+de\s+tonnes", t):
        return 1e3
    if re.search(r"en\s+tonnes?\b|quantite\s*\(en\s+tonnes?\)", t):
        return 1.0
    return None


_MONTHS_FULLYEAR = re.compile(r"janv\w*\.?\s*-\s*d[eé]c\w*")
_MONTHS_PARTIAL = re.compile(r"janv\w*\.?\s*-\s*(f[eé]v|mars|avr|mai|juin|juil|ao[uû]|sept|oct|nov)", re.I)


def _period(label: str):
    lab = re.sub(r"\b(periodes?|libell\w*|agregats|q|v)\b", " ", _fold(label))
    lab = re.sub(r"\s+", " ", lab).strip()
    if not lab or any(w in lab for w in ("absolue", "relative", "variation", "poids", "part", "%")):
        return None
    y = re.findall(r"(?<!\d)(20\d\d|19\d\d)(?!\d)", lab)
    if len(y) != 1:
        return None
    year = y[0]
    m = re.search(r"trim\w*\s*(\d)|(\d)\s*(?:er|e|eme|ème)?\s*trim", lab)
    if m:
        return f"{year}-Q{m.group(1) or m.group(2)}", "quarterly"
    if _MONTHS_PARTIAL.search(lab) or "semestre" in lab or "septembre" in lab:
        return None
    if _MONTHS_FULLYEAR.search(lab) or re.fullmatch(r"(janv\w*\s*-\s*d\w*\s*)?(19|20)\d\d\s*(\([a-z0-9]\))?", lab.strip()):
        return year, "annual"
    return None


def _strip_flow(label: str):
    low = _fold(label)
    for w, fl in _FLOW_WORDS:
        if low.startswith(w):
            rest = label[len(w):].strip(" :-")
            return fl, (rest or None)
    return None, None


def _grid_tables(page, pno: int, state: dict) -> list[dict]:
    """Aggregate and product tables read from word positions (see _pdfwords)."""
    out = []
    lns = W.lines(page)
    qv_idx = [i for i, ln in enumerate(lns) if sum(w["text"] in ("Q", "V") for w in ln) >= 4]
    for n, qi in enumerate(qv_idx):
        qv = [w for w in lns[qi] if w["text"] in ("Q", "V")]
        cols = [((w["x0"] + w["x1"]) / 2, w["text"]) for w in qv]
        centres = [c for c, _ in cols]
        pairs = []                       # (Q index, V index, centre) -- one period each
        for k, (c, m) in enumerate(cols):
            if m == "Q" and k + 1 < len(cols) and cols[k + 1][1] == "V":
                pairs.append((k, k + 1, (c + cols[k + 1][0]) / 2))
        if not pairs:
            continue
        top = lns[qi][0]["top"]
        band = [w for ln in lns if top - 48 <= ln[0]["top"] < top - 0.5 for w in ln]
        labs = {k: [] for k in range(len(pairs))}
        for w in band:
            xc = (w["x0"] + w["x1"]) / 2
            k = min(range(len(pairs)), key=lambda i: abs(pairs[i][2] - xc))
            if abs(pairs[k][2] - xc) <= 45:
                labs[k].append(w)
        colper = {}
        for k, (iq, iv, _) in enumerate(pairs):
            txt = " ".join(w["text"] for w in sorted(labs[k], key=lambda w: (round(w["top"]), w["x0"])))
            p = _period(txt)
            if p:
                colper[iq] = ("Q", *p)
                colper[iv] = ("V", *p)
        if not colper:
            continue
        above = " ".join(W.text(ln) for ln in lns if top - 130 <= ln[0]["top"] < top)
        head = W.text(lns[qi])
        is_product = bool(re.search(r"\bProduit|\bCode", head))
        fa = _fold(above)
        if is_product:
            if "importations" in fa or "exportations" in fa:
                state["flow"] = "import" if fa.rfind("importations") > fa.rfind("exportations") else "export"
            vm = _value_scale(above)
            if vm:
                state["pv"] = vm
                state["pq"] = 1.0 if re.search(r"q\.?\s*=?\s*(quantit\w*)?\s*en\s+tonnes|quantit\w*\s+en\s+tonnes", fa) else None
            flow, vmult, qmult = state.get("flow"), state.get("pv"), state.get("pq")
        else:
            vm = _value_scale(above)
            if vm:
                state["av"], state["aq"] = vm, _qty_scale(above)
            vmult, qmult, flow = state.get("av"), state.get("aq"), None
        if vmult is None or (is_product and flow is None):
            continue
        # value zone: right-aligned numbers start a little left of their Q/V header
        vz = min(w["x0"] for w in qv) - 15
        lib = next((w for w in lns[qi] if _fold(w["text"]).startswith(("libell", "agreg"))), None)
        code_x = lib["x0"] - 2 if lib else 0
        stop = qv_idx[n + 1] if n + 1 < len(qv_idx) else len(lns)
        items = []
        for ln in lns[qi + 1:stop]:
            if _fold(W.text(ln)).startswith(("source", "(*)", "**", "* ")) or "expression" in _fold(W.text(ln)):
                break
            numw = [w for w in ln if W._NUM.match(w["text"]) and w["x1"] >= vz]
            items.append((ln[0]["top"], [w for w in ln if w not in numw], W.numbers(numw)))
        # A wrapped label is printed above / below its numbers line (the cell
        # is vertically centred): each label-only line joins the NEAREST numbers
        # line within 10 pt (a tie goes to the line below).
        numidx = [i for i, it in enumerate(items) if it[2]]
        lab_of = {i: list(items[i][1]) for i in numidx}
        for i, (t, other, nums) in enumerate(items):
            if nums or not other or not numidx:
                continue
            cand = numidx
            if _strip_flow(W.text(other))[0]:       # "Balance commerciale hors" starts a label
                cand = [k for k in numidx if items[k][0] > t] or numidx
            j = min(cand, key=lambda k: (abs(items[k][0] - t), -items[k][0]))
            if abs(items[j][0] - t) <= 10:
                lab_of[j] += other
        cur_flow = None
        series = f"p{pno}{'P' if is_product else 'A'}"
        for i in numidx:
            nums = items[i][2]
            ws = sorted(lab_of[i], key=lambda w: (round(w["top"]), w["x0"]))
            code = ""
            if is_product:
                cw = [w for w in ws if w["x1"] <= code_x]
                code = " ".join(w["text"] for w in cw)
                ws = [w for w in ws if w not in cw]
            label = W.text(ws).strip()
            low = label.lower()
            cells = {}
            for t, x0, x1 in nums:
                k = W.nearest((x0 + x1) / 2, centres, tol=22)
                if k is not None and k in colper and k not in cells:
                    v = W.value(t)
                    if v is not None:
                        cells[k] = v
            if is_product:
                last = {"code": code, "label": label, "cells": cells, "colper": colper,
                        "flow": flow, "vmult": vmult, "qmult": qmult, "series": series}
                state.setdefault("prod", []).append(last)
                continue
            fl, rest = _strip_flow(label)
            if fl:
                cur_flow, commodity = fl, rest
            elif cur_flow in ("export", "import") and label and not low.startswith("taux"):
                commodity = re.sub(r"^dont\s+", "", label).strip()
                fl = cur_flow
            else:
                continue
            com = dict(commodity=commodity, commodity_classification="national" if commodity else "")
            for k, v in cells.items():
                m_, per, freq = colper[k]
                if m_ == "V":
                    out.append(row(tradeflow=fl, period=per, frequency=freq, value=v, unit="XAF",
                                   unit_multiplier=vmult, series_code=series, **com))
                elif qmult and fl in ("export", "import"):
                    out.append(row(tradeflow=fl, period=per, frequency=freq, value=v, unit="tonnes",
                                   unit_multiplier=qmult, measure="net_weight", series_code=series, **com))
    return out


def _emit_products(state) -> list[dict]:
    out = []
    for rec in state.get("prod", []):
        code = rec["code"].strip(".")
        if not re.fullmatch(r"\d{2}", code):
            continue
        lab = rec["label"].strip()
        com = dict(commodity=lab, commodity_classification="hs2", commodity_code_nso=code)
        for k, v in rec["cells"].items():
            m_, per, freq = rec["colper"][k]
            if m_ == "V":
                out.append(row(tradeflow=rec["flow"], period=per, frequency=freq, value=v, unit="XAF",
                               unit_multiplier=rec["vmult"], series_code=rec["series"], **com))
            elif rec["qmult"] and "*" not in lab and "*" not in rec["code"]:
                out.append(row(tradeflow=rec["flow"], period=per, frequency=freq, value=v, unit="tonnes",
                               unit_multiplier=rec["qmult"], measure="net_weight",
                               series_code=rec["series"], **com))
    return out


_NOT_PARTNER_CUT = ("riz", "cacao", "carburant", "produit", "bois", "ciment")


def _partner(rows, title, series):
    """Pays / Quantité / Valeur / Poids, one year. Cells are matched by ORDER
    (name, then the numbers in header order): the grid of these tables does
    not line up the header and data columns."""
    t = _fold(title)
    if "tableau" in t:                              # the caption, not the body text above it
        t = t[t.rindex("tableau"):]
    if any(w in t for w in _NOT_PARTNER_CUT):
        return []                                   # a partner x product table
    if "client" in t or "exportations vers" in t or "exportations a destination" in t:
        flow = "export"
    elif "fournisseur" in t or "importations en provenance" in t:
        flow = "import"
    else:
        return []
    years = re.findall(r"\ben\s+((?:19|20)\d\d)\b", t) or re.findall(r"\b((?:19|20)\d\d)\b", t)
    if not years:
        return []
    year = years[-1]
    nhead = 0
    for r in rows[:5]:
        if any(_num(c) is not None for c in r):
            break
        nhead += 1
    headtxt = _fold(" ".join(_c(c) for r in rows[:nhead] for c in r) + " " + title)
    order = [k for k in ("quantit", "valeur", "poids") if k in headtxt]
    order.sort(key=lambda k: headtxt.index(k))
    if "valeur" not in order:
        return []
    vmult = 1e9 if "milliard" in headtxt else 1e6 if "million" in headtxt else None
    qmult = 1e3 if "milliers" in headtxt else 1.0 if "tonne" in headtxt else None
    if vmult is None:
        return []
    out = []
    for r in rows[nhead:]:
        cells = [_c(c) for c in r if _c(c)]
        if not cells:
            continue
        name = cells[0]
        if _num(name) is not None or _fold(name).startswith(("total", "source", "pays")):
            continue
        vals = [c for c in cells[1:]]
        if len(vals) != len(order):
            continue
        ptype = "group" if _fold(name).startswith(("autres", "reste", "cemac", "union", "afrique",
                                                    "europe", "asie", "amerique")) else "country"
        for k, c in zip(order, vals):
            v = _num(c)
            if v is None:
                continue
            if k == "valeur":
                out.append(row(tradeflow=flow, period=year, frequency="annual", value=v, unit="XAF",
                               unit_multiplier=vmult, partner=name, partner_type=ptype, series_code=series))
            elif k == "quantit" and qmult:
                out.append(row(tradeflow=flow, period=year, frequency="annual", value=v, unit="tonnes",
                               unit_multiplier=qmult, measure="net_weight", partner=name,
                               partner_type=ptype, series_code=series))
    return out


def parse(path: str, extras=None) -> pd.DataFrame:
    files = [path, *(extras or [])]
    frames = [parse_note(f) for f in files]
    return pd.concat([f for f in frames if not f.empty], ignore_index=True)


def parse_note(path: str) -> pd.DataFrame:
    out, state = [], {}
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            out += _grid_tables(page, pno, state)
            tables = sorted(page.find_tables(), key=lambda t: (t.bbox[1], t.bbox[0]))
            for k, t in enumerate(tables):
                x0, top, x1, _ = t.bbox
                rows = [list(r) for r in t.extract() if any(_c(c) for c in r)]
                if len(rows) < 3:
                    continue
                headtxt = " ".join(_fold(_c(c)) for r in rows[:3] for c in r)
                if not ("pays" in headtxt and "valeur" in headtxt):
                    continue
                above = [u for u in tables[:k] if u.bbox[3] <= top + 1 and u.bbox[0] < x1 and u.bbox[2] > x0]
                ceil = max([u.bbox[3] for u in above] + [top - 140, 0])
                title = page.crop((max(0, x0 - 5), ceil, min(page.width, x1 + 5), top)).extract_text() or ""
                n0 = len(out)
                out += _partner(rows, title, f"p{pno}t{k + 1}")
                if os.environ.get("CMR_DEBUG"):
                    print(f"p{pno}t{k+1} partner ->", len(out) - n0, "| T:", title.replace(chr(10), " ")[-160:])
    out += _emit_products(state)
    return pd.DataFrame.from_records(out)
