"""Parsers for INS Guinée merchandise trade (Tier 3 PDF).

INS (Institut National de la Statistique, Guinée) compiles the merchandise
trade statistics from customs records; values in Guinean francs (GNF).

* ``parse_notes`` -- the monthly "Note (d'analyse) sur le commerce extérieur"
  (NOTE_<MOIS>_<ANNEE>.pdf), annex Tableau 1/2 "Principaux produits exportés /
  importés en <mois> <année>" (the 20 leading products, HS-heading labels without
  codes, value in billions of GNF and net weight in tonnes, plus "Total général")
  and Tableau 4/5 "Principaux pays clients / fournisseurs" (the 20 leading
  partners, "Autres pays" and "Total général", billions of GNF). The food-imports
  Tableau 3 (a subset) and the shares are not collected. The products' residual line
  ("Autres produits" / "Autres pays") is not a commodity and is skipped; the
  partners' residual "Autres pays" is kept as partner_type group.
* ``parse_annual`` -- the annual "Annuaire statistique du commerce extérieur" /
  "Note d'analyse statistique du commerce extérieur": the annex tables that print
  one cell per text line, by label: "Evolution générale du commerce extérieur"
  (exports / imports), exports / imports by HS chapter (label only), by SITC
  ("CTCI") section/division, by zone, by continent and by CEDEAO partner, in
  billions of GNF. A row whose label is followed by more or fewer figures than the
  table has years is dropped (labels wrap, and a few rows print no label).
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import month_period, row, to_number

_NUM = r"-?\d{1,3}(?:[   ]\d{3})*(?:[,.]\d+)?"
_CELL = re.compile(rf"^(?:{_NUM}|-?\d+(?:[,.]\d+)?)$")
_MONTHS = r"janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre"
_NOTE_TAB = re.compile(rf"Tableau\s*(\d)\s*:\s*Principaux\s+(produits|pays)\s+(export[ée]s|import[ée]s|clients|fournisseurs|alimentaires)[^\n]*?\b(?:en|du mois d[e'’]\s*)\s*({_MONTHS})\s*(\d{{4}})", re.I)
_ISSUE = re.compile(rf"Note\s+du\s+mois\s+d[e'’]?\s*({_MONTHS})\s*(\d{{4}})", re.I)


def _num(cell: str):
    """A printed figure: decimal comma, or (in some 2025 notes) a decimal point."""
    c = cell.strip()
    if "," not in c and re.search(r"\.\d+$", c):
        return to_number(c.replace(".", ","), decimal=",")
    return to_number(c, decimal=",")


def _split_cells(line: str) -> list[str] | None:
    """One text line -> its numeric cells. Cells set apart by runs of spaces split there;
    two figures run together by ONE space split only where both end in a decimal
    ("5 736,1 15 069 218,8"); anything else is not a row of figures."""
    s = line.strip()
    parts = [x for x in re.split(r"\s{2,}", s) if x]
    if parts and all(_CELL.match(x) for x in parts):
        if len(parts) == 1:
            m = re.match(rf"^({_NUM}[,.]\d)\s+({_NUM}[,.]\d)$", s)
            if m and not _CELL.match(s):
                return [m.group(1), m.group(2)]
        return parts
    m = re.match(rf"^({_NUM}[,.]\d)\s+({_NUM}[,.]\d)$", s)
    if m:
        return [m.group(1), m.group(2)]
    return None


def _note_tables(text: str):
    """Yield (tableau no, kind, flow, period, body text)."""
    hits = list(_NOTE_TAB.finditer(text))
    for i, m in enumerate(hits):
        body = text[m.end(): hits[i + 1].start() if i + 1 < len(hits) else len(text)]
        end = re.search(r"\n\s*Source", body)
        body = body[:end.start()] if end else body
        kind = "partner" if m.group(2).lower() == "pays" else "product"
        w = m.group(3).lower()
        if w.startswith("alim"):
            continue
        flow = "export" if w.startswith(("export", "client")) else "import"
        yield int(m.group(1)), kind, flow, month_period(f"{m.group(4)} {m.group(5)}"), body


def _note_rows(body: str, kind: str):
    """(label, [cells]) per ranked row, 'Autres ...' and 'Total ...' rows."""
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    start = None
    for i, ln in enumerate(lines):
        if re.match(r"^1(\s+\D.*)?$", ln):
            start = i
            break
    if start is None:
        return []
    out, lab, cells = [], None, []

    def flush():
        if lab:
            out.append((re.sub(r"\s+", " ", lab).strip(), cells))
    for ln in lines[start:]:
        rk = re.match(r"^(\d{1,2})(?:\s+(\D.*))?$", ln)
        if rk and (lab is None or cells or lab == ""):
            if lab is None or cells:
                flush()
                lab, cells = (rk.group(2) or ""), []
                continue
        c = _split_cells(ln)
        if c is not None and lab:
            cells = cells + c
            continue
        if re.match(r"^(Autres|Total)", ln, re.I) and lab != "":
            flush()
            lab, cells = ln, []
            continue
        if lab is not None and not cells:
            lab = f"{lab} {ln}".strip()
        else:
            flush()
            lab, cells = None, []
    flush()
    return out


def _parse_note(path: str) -> list[dict]:
    import fitz
    doc = fitz.open(path)
    try:
        text = "\n".join(p.get_text() for p in doc)
    finally:
        doc.close()
    # the note's own month: from its file name (NOTE_MARS_2024.pdf), else its running header
    stem = re.sub(r"[_\-]+", " ", os.path.splitext(os.path.basename(path))[0])
    fm = re.search(rf"({_MONTHS}|jan|fev|sept|oct|nov|dec|jullet)\w*\s+(20\d\d)", stem, re.I)
    issue = None
    if fm:
        mon = {"jan": "janvier", "fev": "fevrier", "sept": "septembre", "oct": "octobre", "nov": "novembre",
               "dec": "decembre", "jullet": "juillet"}.get(fm.group(1).lower(), fm.group(1))
        issue = month_period(f"{mon} {fm.group(2)}")
    if issue is None:
        im = _ISSUE.search(text)
        issue = month_period(f"{im.group(1)} {im.group(2)}") if im else None
    out = []
    for n, kind, flow, period, body in _note_tables(text):
        # a table titled with another month than the note's own (INS copies a title
        # from an earlier note, e.g. "Mars 2023" in the December 2023 note) is dropped
        if not period or (issue and period != issue):
            continue
        head = body[:400].lower()
        if "milliards" not in head or "gnf" not in head:
            continue                       # the value column must say billions of GNF
        for lab, cells in _note_rows(body, kind):
            low = lab.lower()
            total = low.startswith("total")
            other = low.startswith("autres")
            need = 3 if kind == "product" else 2          # value, (weight,) share
            if len(cells) != need:
                continue
            val = _num(cells[0])
            if val is None:
                continue
            sc = f"NOTE Tableau {n}"
            if kind == "product":
                if other:
                    continue
                # Net weights are NOT collected: the column says "(en tonne)" but some
                # notes print thousands of tonnes under it (bauxite "15 987" in April
                # 2025 against "15 069 218,8" in August 2026) -- the scale cannot be read.
                out.append(row(tradeflow=flow, period=period, frequency="monthly", value=val, unit="GNF",
                               unit_multiplier=1e9, commodity=None if total else lab,
                               commodity_classification="" if total else "hs4", series_code=sc))
            else:
                par = None if total else lab
                pt = "world" if total else ("group" if other else "country")
                out.append(row(tradeflow=flow, period=period, frequency="monthly", value=val, unit="GNF",
                               unit_multiplier=1e9, partner=par, partner_type=pt, series_code=sc))
    return out


def parse_notes(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = []
    for p in [path] + list(extras or []):
        if not p.lower().endswith(".pdf"):
            continue
        rs = _parse_note(p)
        if rs:
            df = pd.DataFrame(rs)
            df["_issue"] = df["period"].max()
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    key = ["tradeflow", "commodity", "partner", "partner_type", "measure", "period", "unit"]
    df = df.sort_values("_issue", kind="stable").drop_duplicates(key, keep="last")
    return df.drop(columns="_issue").reset_index(drop=True)


# --------------------------------------------------------------------------- annual reports
_TITLE = re.compile(r"Tableau\s*(?:n°\s*)?([\d.]+)\s*:\s*([^\n]+)", re.I)
_YEAR = re.compile(r"^(?:(?:19|20)\d{2}|[12] \d{3})$")
_ZONE = re.compile(r"^(Afrique de l.?ouest|Afrique du Nord|Afrique Centrale|Afrique de l.Est|Autres|Am[ée]rique du Nord|"
                   r"Am[ée]rique|Proche|Union Europ|Europe|Asie|Oc[ée]anie|Non class|Reste|AFRIQUE (?!DU SUD)|AMERIQUE|"
                   r"ASIE|EUROPE|OCEANIE|Afrique$)", re.I)
_PAGE_HDR = re.compile(r"^(Statistiques du commerce ext|Annuaire statistique du Commerce|Note d.Analyse|Annexe$)", re.I)


def _kind(title: str):
    """title -> (kind, flow, scale, classification) or None."""
    low = title.lower()
    sc = 1e9 if "milliard" in low else None
    if re.search(r"tonne|%|pourcentage|indice|termes de l|taux de change|principaux produits|par pays,? en milliers|"
                 r"selon les chapitres", low):
        return None
    flow = "export" if re.match(r"\s*export", low) else "import" if re.match(r"\s*import", low) else None
    if re.search(r"evolution (g[ée]n[ée]rale du commerce|des [ée]changes)", low):
        return ("head", None, sc, "")
    if low.startswith("balance commerciale"):
        if "chapitre" in low:
            return ("hs2", "balance", sc, "hs2")
        if "cedeao" in low or "pays" in low or "zone" in low or "partenaire" in low:
            return ("partner", "balance", sc, "")
        return None
    if flow is None:
        if re.search(r"pays (clients|fournisseurs)", low):
            return ("partner", "export" if "clients" in low else "import", sc, "")
        return None
    if "ctci" in low:
        return ("sitc", flow, sc, "sitc2")
    if re.search(r"en valeurs?\b.*milliards|chapitres?.*milliards", low) and "zone" not in low and "pays" not in low:
        return ("hs2", flow, sc, "hs2")
    if re.search(r"zone g[ée]ographique|continent|cedeao|par pays", low):
        return ("partner", flow, sc, "")
    return None


_FIGS_ONLY = re.compile(r"^-?[\d][\d  ,.\-]*\d$")
_TOK = re.compile(r"^-?\d{1,3}(?:[   ]\d{3})*(?:[,.]\d+)?$|^-?\d+(?:[,.]\d+)?$")


def _unique_split(line: str, need: int):
    """The cells of a fused line when exactly one way of cutting it at spaces into
    `need` printed figures exists, else None."""
    parts = line.split()
    found = []

    def rec(i, acc):
        if len(found) > 1 or len(acc) > need:
            return
        if i == len(parts):
            if len(acc) == need:
                found.append(list(acc))
            return
        for j in range(i + 1, len(parts) + 1):
            tok = " ".join(parts[i:j])
            if _TOK.match(tok):
                rec(j, acc + [tok])
    rec(0, [])
    return found[0] if len(found) == 1 else None


def _annual_tables(text: str):
    hits = list(_TITLE.finditer(text))
    for i, m in enumerate(hits):
        title = m.group(2).strip()
        if re.search(r"\.{5,}|-{5,}", title):
            continue                                    # a table of contents line
        body = text[m.end(): hits[i + 1].start() if i + 1 < len(hits) else len(text)]
        end = re.search(r"\n\s*Source", body)
        body = body[:end.start()] if end else body
        lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
        years, j = [], 0
        while j < len(lines) and len(years) < 12:
            if _YEAR.match(lines[j]):
                years.append(int(lines[j].replace(" ", "")))
            elif years:
                break
            j += 1
        if len(years) < 2 or years != list(range(years[0], years[0] + len(years))):
            continue
        ytxt = [str(y) for y in years]
        rows, lab, cells, k = [], None, [], j
        while k < len(lines):
            ln = lines[k]
            if _PAGE_HDR.match(ln):
                k += 1
                continue
            if [x.replace(" ", "") for x in lines[k:k + len(years)]] == ytxt:
                if lab is not None and not cells:
                    lab = None                       # the column-header word before repeated years
                k += len(years)
                continue
            if re.match(r"^\d{1,3}$", ln) and k + 1 < len(lines) and _PAGE_HDR.match(lines[k + 1]):
                k += 1
                continue                             # page number
            c = ln if (_CELL.match(ln) or ln in ("-", "–")) else None
            if c is None and _FIGS_ONLY.match(ln):
                # Several cells fused on one text line ("-7 983 -12 087", "5 172,8 4 043,7").
                # They are split only when exactly ONE split gives the cells the open row
                # still needs; otherwise the row is dropped. Either way the line is never
                # taken for a label (it became "-7 983 -12 087 Pologne"). Repaired 2026-11-12.
                need = len(years) - len(cells)
                sp = _unique_split(ln, need) if lab is not None and need > 0 else None
                if sp:
                    cells.extend(sp)
                else:
                    lab, cells = None, []
                k += 1
                continue
            if c is not None and lab is not None:
                cells.append(c)
            elif c is None:
                if lab is not None and cells:
                    rows.append((re.sub(r"\s+", " ", lab).strip(), cells))
                    lab, cells = ln, []
                elif lab is not None and not cells:
                    lab = f"{lab} {ln}"
                else:
                    lab, cells = ln, []
            k += 1
        if lab is not None and cells:
            rows.append((re.sub(r"\s+", " ", lab).strip(), cells))
        yield m.group(1), title, years, rows


def _annual_report(path: str) -> list[dict]:
    import fitz
    doc = fitz.open(path)
    try:
        text = "\n".join(p.get_text() for p in doc)
    finally:
        doc.close()
    out, pending = [], []
    zone_vals = {}                                   # (flow, label, year) -> value, from the zone tables
    tables = list(_annual_tables(text))
    # the report's headline exports / imports by year (the "Evolution générale" table)
    headline = {}
    for tno, title, years, rows in tables:
        spec = _kind(title)
        if spec and spec[0] == "head":
            for lab, cells in rows:
                f = "import" if lab.lower().startswith("import") else "export" if lab.lower().startswith("export") else None
                if f and len(cells) == len(years):
                    for y, c in zip(years, cells):
                        v = _num(c) if c not in ("-", "–") else None
                        if v is not None:
                            headline.setdefault((f, y), v)
    for tno, title, years, rows in tables:
        spec = _kind(title)
        if spec is None:
            continue
        kind, flow, scale, cls = spec
        # TWO TABLES UNDER ONE TITLE. When a title's body holds more than one "Total"
        # row, the next table's title was not recognised and its rows ran on (2024
        # note, "Importation des produits CTCI en valeurs": a block totalling
        # 78 925 356 in 2020, then the value block totalling 31 350). A block is kept
        # only when its total row equals the report's headline flow for every year;
        # otherwise it is dropped. (Repaired 2026-11-12.)
        tot_idx = [i for i, (lab, _) in enumerate(rows) if lab.lower().startswith(("total", "ensemble"))
                   and not lab.lower().startswith("total des sections")]
        if len(tot_idx) >= 2 and flow in ("import", "export"):
            keep, start = [], 0
            for i in tot_idx:
                block, start = rows[start:i + 1], i + 1
                cells = rows[i][1]
                ok = len(cells) == len(years) and all(
                    (flow, y) in headline and _num(c) is not None and abs(_num(c) - headline[(flow, y)]) <= 1
                    for y, c in zip(years, cells))
                if ok:
                    keep += block
            rows = keep
        sc_code = f"{os.path.splitext(os.path.basename(path))[0][:40]} T{tno}"
        recs = []
        for lab, cells in rows:
            if len(cells) != len(years):
                continue                               # wrapped / missing label: never guessed
            low = lab.lower()
            if re.match(r"^(dont|total des sections)", low):
                continue
            total = low.startswith(("total", "ensemble"))
            for y, c in zip(years, cells):
                v = None if c in ("-", "–") else _num(c)
                if v is None:
                    continue
                if kind == "head":
                    f = ("import" if low.startswith("import") else "export" if low.startswith("export")
                         else "balance" if low.startswith("balance") else None)
                    if f is None:
                        continue
                    recs.append(dict(tradeflow=f, period=str(y), value=v))
                elif kind in ("hs2", "sitc"):
                    if re.match(r"^[IVXL]+\s", lab):
                        continue                       # an HS section subtotal (not in the schema)
                    m = re.match(r"^(\d{2})\s*[-:]\s*(.+)$", lab)
                    code, name = (m.group(1), m.group(2)) if (m and kind == "hs2") else ("", lab)
                    recs.append(dict(tradeflow=flow, period=str(y), value=v,
                                     commodity=None if total else name,
                                     commodity_classification="" if total else cls, commodity_code_nso=code))
                else:
                    if low.startswith("balance commerciale"):
                        continue                       # the CEDEAO subtotal of the balance table
                    if total and "cedeao" in title.lower():
                        continue                       # "Total general" of a CEDEAO table is the CEDEAO total, not the world
                    pt = "world" if total else ("group" if _ZONE.match(lab) else "country")
                    recs.append(dict(tradeflow=flow, period=str(y), value=v,
                                     partner=None if total else lab, partner_type=pt))
                    if "zone" in title.lower() and "milliard" in title.lower() and pt == "group":
                        zone_vals[(flow, lab.lower(), str(y))] = v
        if scale is None:
            pending.append((sc_code, kind, flow, title, recs))
            continue
        out += [_mk(r, scale, sc_code) for r in recs]
    # "Pays clients / fournisseurs par zone (valeurs GNF)": no scale printed. Taken in billions
    # only where every zone subtotal equals the billions-of-GNF zone table of the same report.
    for sc_code, kind, flow, title, recs in pending:
        chk = [(r, zone_vals.get((r["tradeflow"], str(r.get("partner", "")).lower(), r["period"])))
               for r in recs if r.get("partner_type") == "group"]
        chk = [(r, z) for r, z in chk if z is not None]
        if len(chk) >= 3 and all(abs(r["value"] - z) <= 0.5 for r, z in chk):
            out += [_mk(r, 1e9, sc_code + " (scale = zone table)") for r in recs]
    return out


def _mk(r: dict, scale: float, sc: str) -> dict:
    return row(tradeflow=r["tradeflow"], period=r["period"], frequency="annual", value=r["value"], unit="GNF",
               unit_multiplier=scale, commodity=r.get("commodity"),
               commodity_classification=r.get("commodity_classification", ""),
               commodity_code_nso=r.get("commodity_code_nso", ""), partner=r.get("partner"),
               partner_type=r.get("partner_type", "world"), series_code=sc)


def parse_annual(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = []
    for p in [path] + list(extras or []):
        if not p.lower().endswith(".pdf"):
            continue
        rs = _annual_report(p)
        if rs:
            df = pd.DataFrame(rs)
            df["_ed"] = df["period"].max()
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    key = ["tradeflow", "commodity", "commodity_classification", "commodity_code_nso", "partner", "partner_type",
           "period"]
    df = df.sort_values("_ed", kind="stable").drop_duplicates(key, keep="last")
    return df.drop(columns="_ed").reset_index(drop=True)
