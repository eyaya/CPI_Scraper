"""Parser for INSEED Chad "Statistiques du Commerce Extérieur" (annual reports).

INSEED publishes one report per year (2010 ... 2025 on its publications API,
customs data DGDDI/SYDONIA). The tables are read from WORD POSITIONS (see
_pdfwords): every table has a title line "Tableau <n> : ...", a header line
holding "Poids" and "Valeur" (any case), and data lines whose numbers are
assigned to the nearest of those two header columns. Labels wrapped onto the
following lines are appended to their row. Only these tables are read
(classified by their title, never by page or number):

  * "... importations / exportations par section de SH2" and the 2024-2025
    annexes "Liste des produits importés / exportés au niveau SH2": HS
    chapters (hs2, code as printed) with weight and value; the "Total" line is
    the all-products figure.
  * "... importations / exportations par pays partenaire", "Principaux
    partenaires du Tchad à l'importation / l'exportation", "principaux
    fournisseurs / clients du Tchad": partner countries (the 2-letter code
    column is not part of the label), "Autres partenaires" (group), "Total"
    (all partners). Tables limited to non-oil exports ("hors pétrole") and
    partner x product tables ("en provenance de la Chine par section ...",
    "... et leurs 5 principaux produits") are not read.
  * "... par continent et sous-continent": continents and sub-continents
    (groups), first Poids/Valeur pair only (the "avec pétrole" columns).

Period: the report year (file name / title); the two-year 2017-2018 report,
whose tables carry both years, is not read by this parser. Scale: read from
the title or header ("valeur en million de F CFA", "poids en tonne"; the
2024-2025 annexes print values in F CFA and weights in kg -- only when that
is stated on the page); a table whose value scale cannot be read is dropped.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

from ._common import row, _fold
from . import _pdfwords as W

_CODE2 = re.compile(r"^[A-Z]{2}$")


def _flow(t: str):
    i = max(t.rfind("import"), t.rfind("fournisseur"))
    e = max(t.rfind("export"), t.rfind("client"))
    if i < 0 and e < 0:
        return None
    return "import" if i > e else "export"


def _kind(t: str):
    if "baril" in t or "exportation du petrole" in t:
        return None                                 # crude-oil table (barrels)
    if "hors petrole" in t or "provenance de l" in t and "section" in t and "pays" not in t:
        return None
    if re.search(r"provenance (de la|du|des|de) (?!l'afrique|l'amerique|l'asie|l'europe|l'oceanie)", t) \
            or " vers l" in t or " vers le" in t or "principaux produits" in t or "top 5" in t:
        return None
    if "sh2" in t and ("section" in t or "niveau" in t) and "provenance" not in t and "vers" not in t:
        return "hs2"
    if "continent" in t:
        return "continent"
    if "pays partenaire" in t or "principaux partenaires" in t or re.search(r"principaux (fournisseurs|clients) du tchad", t):
        return "partner"
    return None


def _scales(text: str):
    t = _fold(text)
    v = 1e6 if re.search(r"millions?\s+de\s+f\s*\.?\s*cfa|million\s+de\s+fcfa", t) else None
    if v is None and re.search(r"milliards?\s+de\s+f\s*\.?\s*cfa", t):
        v = 1e9
    if v is None and re.search(r"(valeur|valeurs)\s*(\(|en)\s*(en\s+)?f\s*\.?\s*cfa\b", t):
        v = 1.0
    q = ("tonnes", 1.0) if re.search(r"poids\s*\(?\s*en\s*tonnes?|poids\s+en\s*tonne|entonne", t) else None
    if q is None and re.search(r"poids\s*\(?\s*en\s*(kg|kilogrammes?)", t):
        q = ("kg", 1.0)
    return v, q


def parse_report(path: str) -> pd.DataFrame:
    year = re.findall(r"(20\d\d)", os.path.basename(path))
    if len(year) != 1:
        return pd.DataFrame()
    year = year[0]
    out = []
    cur = None                       # the open table
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            lns = W.lines(page)
            pagetext = " ".join(W.text(l) for l in lns)
            for ln in lns:
                txt = W.text(ln)
                ft = _fold(txt)
                # running header / footer ("STATISTIQUES DU COMMERCE EXTERIEUR, 2022", page numbers)
                if re.search(r"(rapport sur les )?statistiques du commerce exterieur,?\s*\d{4}", ft) and txt.upper() == txt                         or re.fullmatch(r"(p\.\s*)?\d{1,3}", ft.strip()) or "commerce exterieur, 20" in ft:
                    continue
                if re.match(r"^tableau\s*[a-z]?\s*\d+", ft):
                    out += _close(cur, year)
                    cur = {"title": txt, "cols": None, "rows": [], "page": pno, "pagetext": pagetext}
                    continue
                if cur is None:
                    continue
                if cur["cols"] is None:
                    pw = [w for w in ln if _fold(w["text"]).startswith("poids")]
                    vw = [w for w in ln if _fold(w["text"]).startswith("valeur")]
                    if pw and vw:
                        cur["cols"] = {"q": (pw[0]["x0"] + pw[0]["x1"]) / 2, "v": (vw[0]["x0"] + vw[0]["x1"]) / 2,
                                       "zone": min(pw[0]["x0"], vw[0]["x0"]) - 45, "head": txt,
                                       "heads": sorted([("q", w["x0"]) for w in pw] + [("v", w["x0"]) for w in vw]
                                                       + [("-", w["x0"]) for w in ln if re.match(
                                                           r"(pourcentage|part)\b", _fold(w["text"]))],
                                                       key=lambda h: h[1])}
                        cur["title"] += " " + txt
                    elif len(cur["title"]) < 400:
                        cur["title"] += " " + txt
                    continue
                if ft.startswith("source") or ft.startswith("note"):
                    out += _close(cur, year)
                    cur = None
                    continue
                numw = [w for w in ln if W._NUM.match(w["text"]) and w["x1"] >= cur["cols"]["zone"]]
                # A dash in the Poids / Valeur zone is an EMPTY CELL, not label text
                # ("Costa Rica -"): it is dropped from the label, and a line holding
                # only dashes is still a data row (so the next wrapped label line is
                # not glued onto the row above). Row split repaired 2026-11-12.
                dash = [w for w in ln if re.fullmatch(r"[-–—]+", w["text"]) and w["x1"] >= cur["cols"]["zone"]]
                other = [w for w in ln if w not in numw and w not in dash]
                nums = W.numbers(numw)
                if nums or (dash and other):
                    cur["rows"].append({"words": other, "nums": nums, "top": ln[0]["top"], "page": pno})
                    lab = _fold(W.text(other)).strip()
                    if lab.startswith("total") and not lab.startswith("total top"):
                        out += _close(cur, year)          # the table ends at its total line
                        cur = None
                elif other and cur["rows"] and cur["rows"][-1]["page"] == pno \
                        and ln[0]["top"] - cur["rows"][-1]["top"] < 40:
                    cur["rows"][-1]["words"] = cur["rows"][-1]["words"] + other
                    cur["rows"][-1]["top"] = ln[0]["top"]
            # a table runs on to the next page only while no new title appears
    if cur is not None:
        out += _close(cur, year)
    df = pd.DataFrame.from_records(out)
    if df.empty:
        return df
    # One total printed in two tables that disagree by a rounding slip (2021:
    # imports 615 458,87 in the SH2 table, 615 456,83 in the partner table):
    # the first table read (the SH2 / product table) is kept.
    from ..schema import KEY
    return df.drop_duplicates([k for k in KEY if k in df.columns], keep="first").reset_index(drop=True)


DROPPED: list = []   # (page, title, clusters, headers) of tables whose columns could not be told apart


def _close(t, year) -> list[dict]:
    if not t or not t["cols"] or not t["rows"]:
        return []
    title = _fold(t["title"])
    kind, flow = _kind(title), _flow(title.split("(")[0] if "(" in title else title)
    if kind is None or flow is None:
        return []
    vmult, q = _scales(t["title"])
    if vmult is None:
        vmult, q2 = _scales(t["pagetext"]) if kind == "hs2" and "niveau" in title else (None, None)
        q = q or q2
    if vmult is None:
        return []
    cols = t["cols"]
    # COLUMNS FROM THE FIGURES' RIGHT EDGES. The figures are right-aligned well to
    # the right of their header words, so the old nearest-header-centre rule (45 pt)
    # dropped short weights and filed short values ("Minerais 2,16 9,90") under
    # Poids. The right edges form one tight cluster per column; the k-th cluster
    # is the k-th Poids/Valeur header from the left. A table whose clusters do not
    # match its headers one-to-one is dropped. (Repaired 2026-11-12.)
    edges = sorted(x1 for r in t["rows"] for tok, _, x1 in r["nums"] if not tok.endswith("%"))
    clusters = []
    for e in edges:
        if clusters and e - clusters[-1][-1] <= 12:
            clusters[-1].append(e)
        else:
            clusters.append([e])
    # A column is a cluster carrying figures on >= 3 lines; a stray figure (a line of
    # the commentary printed beside the 2025 tables) is not a column, and its line is
    # not read. The share column ("Pourcentage" / "Part") counts as a column when its
    # figures print without "%" (2022 Tableau A9), else it is absent.
    clusters = [c for c in clusters if len(c) >= 3]
    heads = cols.get("heads") or []
    share_right = bool(heads) and heads[-1][0] == "-"     # a share column printed last
    if len(clusters) != len(heads):
        heads = [h for h in heads if h[0] != "-"]
    if heads and len(clusters) == len(heads) + 1:
        # a share column whose header is not on the Poids / Valeur line (2022 Tableau
        # A9): accepted only when every figure of the rightmost cluster is <= 100
        lo, hi = clusters[-1][0] - 0.5, clusters[-1][-1] + 0.5
        right = [W.value(tok) for r in t["rows"] for tok, _, x1 in r["nums"]
                 if lo <= x1 <= hi and not tok.endswith("%")]
        if right and all(v is not None and 0 <= v <= 100 for v in right):
            heads = heads + [("-", hi)]
            share_right = True
    if not heads or len(clusters) != len(heads) or any(c[-1] - c[0] > 12 for c in clusters):
        DROPPED.append((t["page"], t["title"][:60], len(clusters), len(heads)))
        return []
    first_pair = {}
    for (kind_, _), c in zip(heads, clusters):
        if kind_ not in first_pair:
            first_pair[kind_] = (c[0] - 0.5, c[-1] + 0.5)

    def colmap(x1):
        for k_, (lo, hi) in first_pair.items():
            if lo <= x1 <= hi:
                return k_
        for c in clusters:
            if c[0] - 0.5 <= x1 <= c[-1] + 0.5:
                return "-"              # a later column pair (e.g. "hors pétrole"): not read
        if share_right and clusters and x1 > clusters[-1][-1] + 0.5:
            return "-"                  # the share column, right of every figure column
        return None
    out = []
    seen = set()
    series = f"p{t['page']}:{kind}"
    for r in t["rows"]:
        ws = r["words"]
        label = W.text(ws).strip()
        code = ""
        if kind == "hs2":
            m = re.match(r"^(\d{2})\s+(.*)$", label)
            if m:
                code, label = m.group(1), m.group(2).strip()
        elif kind == "partner" and ws and _CODE2.match(ws[0]["text"]) and len(ws) > 1:
            label = W.text(ws[1:]).strip()
        fl = _fold(label)
        if not label or fl.startswith("total top") or "%" in label:
            continue
        cells = {}
        for tok, x0, x1 in r["nums"]:
            if tok.endswith("%"):
                continue                # the "Pourcentage" column (a share) is not read
            k = colmap(x1)
            if k is None or k in cells:
                cells = None            # a figure outside the columns, or two in one column
                break
            if k == "-":
                continue
            v = W.value(tok)
            if v is not None:
                cells[k] = v
        if cells is None:
            continue
        if kind != "hs2" and len(label.split()) > 6:
            continue                    # a sentence of the commentary, not a partner row
        if fl.startswith("total"):
            kw = dict(commodity=None, partner=None)
        elif kind == "hs2":
            if not code:
                continue
            kw = dict(commodity=label.rstrip(" ."), commodity_classification="hs2", commodity_code_nso=code)
        elif kind == "partner":
            # a label printed twice in one table (2022: "TC Turquie", Turks and
            # Caicos, under Turkey's name) keeps its first, largest line only
            if label in seen:
                continue
            seen.add(label)
            ptype = "group" if fl.startswith(("autres", "reste", "divers", "non ")) else "country"
            kw = dict(partner=label, partner_type=ptype)
        else:
            kw = dict(partner=label, partner_type="group")
        if "v" in cells:
            out.append(row(tradeflow=flow, period=year, frequency="annual", value=cells["v"], unit="XAF",
                           unit_multiplier=vmult, series_code=series, **kw))
        if "q" in cells and q:
            out.append(row(tradeflow=flow, period=year, frequency="annual", value=cells["q"], unit=q[0],
                           unit_multiplier=q[1], measure="net_weight", series_code=series, **kw))
    # The caption's scale must fit the figures: the 2023 report's Tableau A1
    # says "valeur en million de F CFA" over figures printed in F CFA (a total of
    # 835 584 6.. million million). Such a table is dropped, never rescaled.
    if any(r["measure"] == "value" and r["value"] * r["unit_multiplier"] > 1e14 for r in out):
        return []
    return out


def parse(path: str, extras=None) -> pd.DataFrame:
    frames = [parse_report(f) for f in [path, *(extras or [])]]
    return pd.concat([f for f in frames if not f.empty], ignore_index=True)
