"""Parser for INSBU Burundi "Bulletin du Commerce Extérieur de Marchandises"
(quarterly, 2020 Q1 on, from INSBU's publications API; OBR customs data).

All values in millions of BIF ("en millions de BIF", "millions de Fbu" in each
title). Tables are read from WORD POSITIONS (see _pdfwords), classified by
their title:

  Tableau 1 "Balance commerciale": one row per quarter of a ~5-year window plus
    a "Total" row per year (annual), columns Importations (1), Exportations (2)
    définitives, Exportations temporaires (not read), Re-Exportations (3),
    Total des exportations (2)+(3), Total des échanges (1)+(2)+(3), Balance
    commerciale, Taux de couverture (not read) -> import / domestic_export /
    re_export / export / total / balance. The year label is printed once per
    year group (vertically centred), so a group runs to its "Total" line.
  Matrix tables: rows x (year x quarter) columns ("1er trim" ... "4e trim",
    "Total annuel" under a year label):
      "importations / exportations / réexportations par grands groupes de
       produits"  -> HS chapters (hs2, code as printed)
      "... par continent"  -> continents and the blocs/countries printed under
       them (UE, COMESA, EAC, "dont: France" -> France); "Total" = all partners
      "... à partir des / vers les pays du COMESA / de l'EAC / ..." -> member
       countries; that table's "Total" is the bloc itself.
    A "Total annuel" is emitted only when the row prints all four quarters of
    that year (the current year's column is a year-to-date sum).
The side-by-side top-20 partner tables and temporary exports are not read.
Several bulletins at once: the newest bulletin wins a key.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

from ._common import row, _fold
from . import _pdfwords as W
from ..schema import KEY

UNIT, MULT = "BIF", 1e6
_GROUPS = {"europe", "ue", "union europeenne", "afrique", "comesa", "eac", "ceeac", "cepgl", "sadc",
           "amerique", "asie", "oceanie", "autres", "autres pays", "reste du monde", "non specifie",
           "zone euro", "moyen orient"}
_ZONES = (("comesa", "COMESA"), ("l'eac", "EAC"), ("ceeac", "CEEAC"), ("cepgl", "CEPGL"),
          ("sadc", "SADC"), ("l' ue", "UE"), ("l'ue", "UE"), ("ue (", "UE"))
_QTXT = re.compile(r"^(1er|2e|2eme|2ème|3e|3eme|3ème|4e|4eme|4ème)$", re.I)


def _qnum(s: str):
    m = re.match(r"(\d)", s)
    return int(m.group(1)) if m else None


def _group_lines(items, numidx_fn):
    pass


_GLYPH = re.compile(r"\(cid:\d+\)")
_DASH = re.compile(r"^[-–—]+$")


def _clean(lns):
    """Words of each line as printed: unmapped glyphs ("CEPGL (cid:3)") removed, and
    pieces of ONE word that touch or overlap (gap <= 0.9 pt) joined. Several bulletins (2021 Q3 ...)
    set every digit as its own word, so "18 640,0" came out as "1" "8" "640,0" and the
    first piece, "1", was read as the cell; "56,2" as "5" "6" ",2"; "dont:" as "d"
    "ont:"; "COMESA" as "C" "OMESA". (Repaired 2026-11-12.)"""
    out = []
    for ln in lns:
        ws = []
        for w in ln:
            t = _GLYPH.sub("", w["text"]).strip()
            if not t:
                continue
            w = dict(w, text=t)
            if ws and -2 <= w["x0"] - ws[-1]["x1"] <= 0.9 and abs(w["top"] - ws[-1]["top"]) <= 3:
                ws[-1] = dict(ws[-1], text=ws[-1]["text"] + t, x1=w["x1"])
            else:
                ws.append(w)
        if ws:
            out.append(ws)
    return out


def _rows(lns, start, stop, zone_x):
    """[(label_words, nums, top)] figure lines with wrapped label lines joined. A dash in
    the figure zone is an EMPTY CELL: it is not label text ("Angola - -"), and a line of
    a name and dashes only is still a row (so the next wrapped name is not glued onto the
    row above: "Sel; soufre; ... ciments. 26 Minerais, scories et cendres. - - -").
    (Repaired 2026-11-12.)"""
    items = []
    for ln in lns[start:stop]:
        numw = [w for w in ln if W._NUM.match(w["text"]) and w["x1"] >= zone_x]
        dash = [w for w in ln if _DASH.match(w["text"]) and w["x1"] >= zone_x]
        other = [w for w in ln if w not in numw and w not in dash]
        items.append((ln[0]["top"], other, W.numbers(numw), bool(numw or dash)))
    numidx = [i for i, it in enumerate(items) if it[3]]
    labs = {i: list(items[i][1]) for i in numidx}
    for i, (t, other, nums, cells) in enumerate(items):
        if cells or not other or not numidx:
            continue
        if _fold(W.text(other)).startswith("dont"):
            # "dont: Emirats" / "Arabes Unis 135 721,7 ...": an "of which" item begins
            # here and its name ends on the figure line BELOW (it was glued to "Asie")
            below = [k for k in numidx if 0 < items[k][0] - t <= 14]
            if below:
                labs[min(below, key=lambda k: items[k][0])] += other
                continue
        j = min(numidx, key=lambda k: (abs(items[k][0] - t), -items[k][0]))
        if abs(items[j][0] - t) <= 12:
            labs[j] += other
    return [(sorted(labs[i], key=lambda w: (round(w["top"]), w["x0"])), items[i][2], items[i][0])
            for i in numidx]


def _balance(lns, ti, stop, series):
    head = [w for ln in lns[ti + 1:ti + 6] for w in ln]
    def cx(pred):
        ws = [w for w in head if pred(w["text"])]
        return (ws[0]["x0"] + ws[0]["x1"]) / 2 if ws else None
    cols = {"import": cx(lambda t: t.startswith("Importations")),
            "domestic_export": cx(lambda t: t == "définitives"),
            "_temp": cx(lambda t: t == "temporaires"),
            "re_export": cx(lambda t: t.startswith("Re-Exportations") or t == "(3)"),
            "export": cx(lambda t: t == "(2)+(3)"),
            "total": cx(lambda t: t == "(1)+(2)+(3)"),
            "balance": cx(lambda t: t == "commerciale"),
            "_rate": cx(lambda t: t == "couverture")}
    cols = {k: v for k, v in cols.items() if v is not None}
    if not {"import", "balance"} <= set(cols):
        return []
    hdr_end = max(i for i in range(ti + 1, min(ti + 7, stop)) if any(
        w["text"] in ("(1)+(2)+(3)", "couverture", "commerciale") for w in lns[i])) + 1
    zone = min(cols.values()) - 45
    rows_ = _rows(lns, hdr_end, stop, zone)
    out, group = [], []
    def flush(group):
        yrs = [y for g in group for y in g["years"]]
        if len(set(yrs)) != 1:
            return []
        y = yrs[0]
        res = []
        for g in group:
            if g["q"]:
                per, freq = f"{y}-Q{g['q']}", "quarterly"
            else:
                per, freq = y, "annual"
            for fl, v in g["cells"].items():
                res.append(row(tradeflow=fl, period=per, frequency=freq, value=v, unit=UNIT,
                               unit_multiplier=MULT, series_code=series))
        return res
    for ws, nums, _ in rows_:
        txt = W.text(ws)
        years = re.findall(r"\b(20\d\d)\b", txt)
        q = None
        m = re.search(r"\b(\d)\s*(?:er|e|ème|eme)\b", txt)
        is_total = "Total" in txt
        if m and not is_total:
            q = int(m.group(1))
        elif not is_total:
            continue
        cells = {}
        for tok, x0, x1 in nums:
            v = W.value(tok)
            if v is None:
                continue
            xc = (x0 + x1) / 2
            k = min(cols, key=lambda c: abs(cols[c] - xc))
            if abs(cols[k] - xc) <= 45 and not k.startswith("_") and k not in cells:
                cells[k] = v
        group.append({"years": years, "q": q, "cells": cells})
        if is_total:
            out += flush(group)
            group = []
    if group:
        out += flush(group)
    # Column check: where a layout differs (2021 Q1/Q2, 2024 Q2 bulletins) the
    # columns cannot be told apart reliably; if exports - imports does not give
    # the printed balance for most rows, the table is dropped, not guessed.
    cells = {}
    for r in out:
        cells.setdefault(r["period"], {})[r["tradeflow"]] = r["value"]
    chk = [c for c in cells.values() if {"import", "export", "balance"} <= set(c)]
    bad = [c for c in chk if abs(c["export"] - c["import"] - c["balance"]) > 1.0]
    if not chk or len(bad) > len(chk) / 4:
        return []
    # a single period whose printed balance is not exports - imports (the 2025 Q1
    # bulletin's 2024 total uses another export figure) keeps its flows, not its
    # balance / total-trade cells
    badp = {p for p, c in cells.items() if {"import", "export", "balance"} <= set(c)
            and abs(c["export"] - c["import"] - c["balance"]) > 1.0}
    badp |= {p for p, c in cells.items() if {"import", "export", "total"} <= set(c)
             and abs(c["export"] + c["import"] - c["total"]) > 1.0}
    if len(badp) > len(cells) / 4:
        return []                     # columns not reliably told apart: drop the table
    out = [r for r in out if not (r["period"] in badp and r["tradeflow"] in ("balance", "total"))]
    # "Total des exportations (2)+(3)" in fact includes temporary exports (2026 Q2
    # bulletin, 2021 Q3: 39 276,3 + 4 169,9 + 4 289,9 = 47 736,1), so it is not
    # domestic + re-exports; where domestic exports are printed the total-exports
    # column is not emitted (it would break export = domestic + re-exports). Bulletins
    # whose table has a single export column keep it as "export".
    if any(r["tradeflow"] == "domestic_export" for r in out):
        out = [r for r in out if r["tradeflow"] != "export"]
    return out


DROPPED: list = []


def _matrix(lns, ti, stop, title, series, state):
    t = _fold(title)
    if "temporaire" in t:
        return []
    flow = "re_export" if "reexport" in t or "re-export" in t else \
        "import" if "importation" in t else "export" if "exportation" in t else None
    if flow is None:
        return []
    if "groupes de produits" in t or "sh2" in t or "chapitre" in t:
        kind = "hs2"
    elif "continent" in t:
        kind = "continent"
    elif any(z in t for z, _ in _ZONES):
        kind = "zone"
    else:
        return []
    zone_name = next((n for z, n in _ZONES if z in t), None)
    # header: a line with >= 4 quarter labels, the year labels just above it
    qi = next((i for i in range(ti + 1, min(ti + 8, stop))
               if sum(_fold(w["text"]) == "trim" for w in lns[i]) >= 3), None)
    if qi is None:
        return []
    qline = lns[qi]
    cols = []
    for k, w in enumerate(qline):
        if _fold(w["text"]) == "trim" and k > 0 and _QTXT.match(qline[k - 1]["text"]):
            cols.append([(qline[k - 1]["x0"] + w["x1"]) / 2, _qnum(qline[k - 1]["text"])])
        elif _fold(w["text"]) == "total" and k + 1 < len(qline) and _fold(qline[k + 1]["text"]) == "annuel":
            cols.append([(w["x0"] + qline[k + 1]["x1"]) / 2, 0])
        elif _fold(w["text"]) == "annuel" and not (k > 0 and _fold(qline[k - 1]["text"]) == "total"):
            cols.append([(w["x0"] + w["x1"]) / 2, 0])
    ylabs = [(float((w["x0"] + w["x1"]) / 2), w["text"]) for i in range(max(ti, qi - 3), qi)
             for w in lns[i] if re.fullmatch(r"20\d\d", w["text"])]
    if not ylabs or not cols:
        return []
    # Each run of columns ending in "Total annuel" belongs to ONE year label, in order:
    # the k-th run to the k-th year from the left. Given to the NEAREST year label (a
    # label centred over its run is nearer the next run's first columns), the 2024 Q1
    # bulletin filed figures under "2024-Q4" and others one year off. A table whose runs
    # and year labels do not pair up, or whose run does not count 1er, 2e, ... trim, is
    # dropped. (Repaired 2026-11-12.)
    cols.sort(key=lambda c: c[0])
    runs, cur = [], []
    for c in cols:
        cur.append(c)
        if c[1] == 0:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    years = []
    for _, y in sorted(ylabs):
        if y not in years:
            years.append(y)
    if len(runs) != len(years):
        DROPPED.append((series, "runs/years", len(runs), len(years)))
        return []
    for run, y in zip(runs, years):
        qs = [c[1] for c in run if c[1]]
        ok = qs == list(range(1, len(qs) + 1))
        if not ok:
            DROPPED.append((series, "run " + y, qs))
        for c in run:
            # a run not in printed order keeps its columns (so its figures are not
            # taken by a neighbouring column) but they are not read
            c.append(y if ok else None)
    if all(c[2] is None for c in cols):
        return []
    centres = [c[0] for c in cols]
    zone = min(centres) - 40
    out = []
    for ws, nums, _ in _rows(lns, qi + 1, stop, zone):
        cells = {}
        for tok, x0, x1 in nums:
            v = W.value(tok)
            k = W.nearest((x0 + x1) / 2, centres, tol=32)
            if v is not None and k is not None and k not in cells:
                cells[k] = v
        label = W.text(ws).strip()
        code = ""
        if kind == "hs2":
            m = re.match(r"^(\d{2})\s+(.*)$", label) or re.match(r"^(.*?)\s*\b(\d{2})\s+(.*)$", label)
            if m and len(m.groups()) == 2:
                code, label = m.group(1), m.group(2)
            elif m:
                code, label = m.group(2), (m.group(1) + " " + m.group(3)).strip()
        fl = _fold(label)
        if not label:
            continue
        if fl.startswith("total"):
            kw = dict(commodity=None, partner=None) if kind != "zone" else \
                dict(partner=zone_name, partner_type="group") if zone_name else None
            if kw is None:
                continue
        elif kind == "hs2":
            if not code:
                continue
            kw = dict(commodity=label.rstrip(". "), commodity_classification="hs2", commodity_code_nso=code)
        else:
            name = re.sub(r"^dont\s*:\s*", "", label, flags=re.I).strip()
            ptype = "group" if _fold(name) in _GROUPS else "country"
            kw = dict(partner=name, partner_type=ptype)
        years_full = {}
        for k, v in cells.items():
            if cols[k][1]:
                years_full.setdefault(cols[k][2], set()).add(cols[k][1])
        for k, v in cells.items():
            _, q, y = cols[k]
            if y is None:
                continue
            if q:
                per, freq = f"{y}-Q{q}", "quarterly"
            else:
                if years_full.get(y) != {1, 2, 3, 4}:
                    continue
                per, freq = y, "annual"
            out.append(row(tradeflow=flow, period=per, frequency=freq, value=v, unit=UNIT,
                           unit_multiplier=MULT, series_code=series, **kw))
    return out


def parse_bulletin(path: str) -> pd.DataFrame:
    out = []
    with pdfplumber.open(path) as pdf:
        pages = [_clean(W.lines(p)) for p in pdf.pages]
    # flatten with page breaks; a table runs until the next "Tableau" title,
    # a "Source" line, or the end of its page (headers repeat on continuation pages)
    last_title = None
    for pno, lns in enumerate(pages, 1):
        titles = [i for i, ln in enumerate(lns) if re.match(r"^tableau\s*\d+\s*:", _fold(W.text(ln)))]
        hdrs = [i for i, ln in enumerate(lns) if sum(_fold(w["text"]) == "trim" for w in ln) >= 3]
        first_t = titles[0] if titles else len(lns)
        if last_title and hdrs and hdrs[0] < first_t:
            # continuation page: the header repeats without the title
            stop = first_t
            for j in range(hdrs[0], stop):
                if _fold(W.text(lns[j])).startswith("source"):
                    stop = j
                    break
            out += _matrix(lns, max(0, hdrs[0] - 3), stop, last_title, f"p{pno}c", {})
        for n, ti in enumerate(titles):
            stop = titles[n + 1] if n + 1 < len(titles) else len(lns)
            for j in range(ti + 1, stop):
                if _fold(W.text(lns[j])).startswith("source"):
                    stop = j
                    break
            title = W.text(lns[ti]) + " " + W.text(lns[ti + 1]) if ti + 1 < len(lns) else W.text(lns[ti])
            ft = _fold(title)
            if not re.search(r"millions?\s+de\s+(bif|fbu)", ft):
                continue
            series = f"p{pno}"
            last_title = None if "balance commerciale" in ft else title
            if "balance commerciale" in ft:
                out += _balance(lns, ti, stop, series)
            else:
                out += _matrix(lns, ti, stop, title, series, {})
        # continuation page of a matrix table: no title, but a quarter header
        if not titles and out:
            pass
    df = pd.DataFrame.from_records(out)
    if df.empty:
        return df
    # A table holding a period after the bulletin's own quarter was misread: dropped whole.
    m = re.search(r"(\d{4})Q(\d)", os.path.basename(path))
    if m:
        by, bq = int(m.group(1)), int(m.group(2))
        def late(p):
            return (int(p[:4]), int(p[-1])) > (by, bq) if "-Q" in p else int(p) > by
        bad = set(df.loc[df["period"].map(late), "series_code"])
        df = df[~df["series_code"].isin(bad)]
        if df.empty:
            return df
    # One cell printed in two tables of a bulletin: a rounding difference is
    # one observation (first kept); a real disagreement (2026 Q2 bulletin: RDC
    # imports 2025-Q4 85 910,5 in the COMESA table, 28 993,7 in the CEEAC and
    # CEPGL tables) is ambiguous, so every copy of that key is dropped.
    k = [c for c in KEY if c in df.columns]
    full = df["value"] * df["unit_multiplier"]
    g = full.groupby([df[c].astype(str) for c in k]).transform(lambda s: s.max() - s.min())
    df = df[g <= 0.5 * df["unit_multiplier"] + 1e-9]
    return df.drop_duplicates(k, keep="first").reset_index(drop=True)


def bulletin_key(path: str) -> str:
    m = re.search(r"(\d{4})Q(\d)", os.path.basename(path))
    return f"{m.group(1)}-Q{m.group(2)}" if m else os.path.basename(path)


def parse(path: str, extras=None) -> pd.DataFrame:
    files = sorted({path, *(extras or [])}, key=bulletin_key)
    df = pd.concat([parse_bulletin(f) for f in files], ignore_index=True)
    return df.drop_duplicates([k for k in KEY if k in df.columns], keep="last").reset_index(drop=True)
