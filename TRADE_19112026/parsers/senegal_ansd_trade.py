"""Parsers for ANSD Senegal merchandise trade (Tier 2 Excel + Tier 3 PDF).

ANSD (Agence Nationale de la Statistique et de la Démographie) compiles
Senegal's merchandise trade statistics from customs declarations (Eurotrace),
general trade system; exports FOB ("FAB"), imports CIF ("CAF").

Sources (one function per source family):

* ``parse_partners_xlsx`` -- ``imports_exports_janv2010-fevr2026_MAJ.xlsx``:
  sheets ``Import_Partenaire`` / ``Export_Partenaire``, monthly customs value
  (VALDOUANE, in FCFA -- units; checked against BMSCE Tableau 1/2 which print
  "Valeur FAB (FCFA)") by partner ("001:FRANCE" -- ANSD's partner code, then
  the label) and the "Total" row (all partners). Codes 9xx are not countries
  (provisions de bord, consignation, origines mélangées, Air Afrique, USEX)
  -> partner_type "group".
* ``parse_hs2_xlsx`` -- ``Exportations/Importations des produits (valeur et
  volume), janv2010 - fevr2024.xlsx``: monthly HS chapters ("Code SH2"),
  value (VALDOUANE, FCFA) and net weight (POIDSNET, kg -- equal to BMSCE
  Tableau 1/2 "Poids Net (Kg)"), all partners (PARTENAIRE MONDE), and the
  "Total" row.
* ``parse_bmsce`` -- the monthly "Bulletin mensuel des statistiques du
  commerce extérieur" PDFs. Each issue prints five months (the month under
  review, the three before it and the same month a year earlier) in:
  Tableau 1/2 (all products, value FCFA and net weight kg), Tableau 19/20 and
  23/24 (HS chapters, value in millions of FCFA, weight in thousands of kg),
  Tableau 27/29 (partner countries and ANSD's regional groupings, millions of
  FCFA) and Tableau 31 (trade balance by partner, millions of FCFA, signed).
  The chapter tables print the chapter LABEL only; the HS2 code is taken from
  ANSD's own HS2 workbook where the label is identical (else left blank).
  Where several issues print the same month, the newest issue's figure is kept
  (revised replaces provisional). Cumulative columns and % columns are skipped.
"""
from __future__ import annotations

import datetime as dt
import os
import re

import pandas as pd

from ._common import month_period, row, scale_from_text, to_number

_FLOW_SHEET = {"import": "import", "export": "export"}


def _clean(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


# --------------------------------------------------------------------------- xlsx
def _header_months(r) -> dict[int, str]:
    out = {}
    for j, v in enumerate(r):
        if isinstance(v, (dt.datetime, dt.date)):
            out[j] = f"{v.year}-{v.month:02d}"
    return out


def parse_partners_xlsx(path: str) -> pd.DataFrame:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = []
    try:
        for ws in wb.worksheets:
            title = ws.title.strip().lower()
            flow = "import" if title.startswith("import") else "export" if title.startswith("export") else None
            if flow is None:
                continue
            basis = "cif" if flow == "import" else "fob"
            data = list(ws.iter_rows(values_only=True))
            hi = next(i for i, r in enumerate(data) if _clean(r[0]).upper() == "PARTENAIRE")
            months = _header_months(data[hi])
            # A label shared by two codes (620 and 660 are both "AFGANISTAN"): the code
            # whose cells are all blank or 0 is dropped, so the label names one series.
            seen: dict[str, list] = {}
            for r in data[hi + 1:]:
                m = re.match(r"^(\d{3})\s*:\s*(.+)$", _clean(r[0]))
                if m:
                    seen.setdefault(m.group(2).strip(), []).append(r)
            empty = {id(r) for rs in seen.values() if len(rs) > 1 for r in rs
                     if not any(v not in (None, "", 0) for v in r[1:])}
            for r in data[hi + 1:]:
                if id(r) in empty:
                    continue
                lab = _clean(r[0])
                if not lab:
                    continue
                if lab.lower() == "total":
                    partner, ptype, code = None, "world", ""
                else:
                    m = re.match(r"^(\d{3})\s*:\s*(.+)$", lab)
                    if not m:
                        raise ValueError(f"senegal partners: unexpected label {lab!r}")
                    code, partner = m.group(1), m.group(2).strip()
                    ptype = "group" if code.startswith("9") else "country"
                for j, per in months.items():
                    v = r[j] if j < len(r) else None
                    if v is None or (isinstance(v, str) and not v.strip()):
                        continue
                    rows.append(row(tradeflow=flow, period=per, frequency="monthly", value=float(v),
                                    unit="XOF", unit_multiplier=1, partner=partner, partner_type=ptype,
                                    price_basis=basis, trade_system="general",
                                    series_code=f"{ws.title.strip()}"))
    finally:
        wb.close()
    return pd.DataFrame(rows)


def _hs2_sheet(ws) -> list[dict]:
    data = list(ws.iter_rows(values_only=True))
    meta = " ".join(_clean(c) for r in data[:12] for c in r[:3] if c)
    flow = "export" if "EXPORTATION" in meta.upper() else "import" if re.search(r"\bI:", meta) else None
    if flow is None:
        raise ValueError(f"senegal hs2: flow not found in {ws.title!r}")
    if "VALDOUANE" in meta.upper():
        measure, unit = "value", "XOF"
    elif "POIDSNET" in meta.upper():
        measure, unit = "net_weight", "kg"
    else:
        raise ValueError(f"senegal hs2: indicator not found in {ws.title!r}")
    hi = next(i for i, r in enumerate(data) if _clean(r[0]) == "Code SH2")
    months = _header_months(data[hi])
    out = []
    for r in data[hi + 1:]:
        code = _clean(r[0])
        if not code:
            continue
        if code.lower() == "total":
            com, ccode = None, ""
        else:
            ccode = code.zfill(2) if code.isdigit() else code
            com = _clean(r[1])
        for j, per in months.items():
            v = r[j] if j < len(r) else None
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            out.append(row(tradeflow=flow, period=per, frequency="monthly", value=float(v), unit=unit,
                           unit_multiplier=1, measure=measure, commodity=com,
                           commodity_classification="hs2" if com else "", commodity_code_nso=ccode,
                           price_basis=("fob" if flow == "export" else "cif") if measure == "value" else "",
                           trade_system="general", series_code=ws.title.strip()))
    return out


def parse_hs2_xlsx(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    import openpyxl
    rows = []
    for p in [path] + list(extras or []):
        if not p.lower().endswith(".xlsx"):
            continue
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        try:
            for ws in wb.worksheets:
                rows += _hs2_sheet(ws)
        finally:
            wb.close()
    return pd.DataFrame(rows)


def hs2_label_codes(paths: list[str]) -> dict[str, str]:
    """ANSD's own label -> HS2 code table, from its HS2 workbooks."""
    import openpyxl
    out: dict[str, str] = {}
    for p in paths:
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        try:
            for ws in wb.worksheets:
                data = list(ws.iter_rows(values_only=True))
                hi = next(i for i, r in enumerate(data) if _clean(r[0]) == "Code SH2")
                for r in data[hi + 1:]:
                    c, lab = _clean(r[0]), _clean(r[1]).upper()
                    if c.isdigit() and lab:
                        out.setdefault(_key(lab), c.zfill(2))
        finally:
            wb.close()
    return out


def _key(label: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", label.upper())


# --------------------------------------------------------------------------- PDF
_TABLES = {   # tableau number -> (kind, flow, measure)
    1: ("head", "export", None), 2: ("head", "import", None),
    19: ("hs2", "export", "value"), 20: ("hs2", "export", "net_weight"),
    23: ("hs2", "import", "value"), 24: ("hs2", "import", "net_weight"),
    27: ("partner", "export", "value"), 29: ("partner", "import", "value"),
    31: ("partner", "balance", "value"),
}
_MONTH_RX = re.compile(r"^(janv|f[ée]vr|mars|avr|mai|juin|juil|ao[uû]t|sept|oct|nov|d[ée]c)[a-z]*\.?-\d{2}$", re.I)
_TAB_RX = re.compile(r"TABLEAU\s+(\d+)\s*:", re.I)


def _spans(page):
    d = page.get_text("dict")
    out = []
    for b in d["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                t = s["text"].strip()
                if t:
                    x0, y0, x1, y1 = s["bbox"]
                    out.append((x0, (y0 + y1) / 2, x1, t))
    return out


def _lines(spans, tol=2.5):
    spans = sorted(spans, key=lambda s: (s[1], s[0]))
    lines, cur, cy = [], [], None
    for s in spans:
        if cy is None or abs(s[1] - cy) <= tol:
            cur.append(s)
            cy = s[1] if cy is None else cy
        else:
            lines.append(sorted(cur))
            cur, cy = [s], s[1]
    if cur:
        lines.append(sorted(cur))
    return lines


def _group_label(lab: str) -> bool:
    u = lab.upper()
    return (u.startswith(("LES ", "UEMOA", "CEDEAO", "UNION ", "ZONE ", "RESTE", "DIVERS",
                          "PROVISION", "CONSIGNATION", "ORIGINES", "USEX", "AIR AFRIQUE", "COMMUNAUTE"))
            or "NON DETERMIN" in u or "NON SPECIF" in u)


_NUM_RX = re.compile(r"^-?\d{1,3}(?:[\s  ]\d{3})*(?:,\d+)?$|^-?\d+(?:,\d+)?$|^-$")


def _segments(doc):
    """(table state, ordered month periods, month header centres, data lines) per table x page."""
    segs, cur, seg = [], None, None
    for page in doc:
        seg = None
        for ln in _lines(_spans(page)):
            text = " ".join(s[3] for s in ln)
            m = _TAB_RX.search(text)
            if m:
                n = int(m.group(1))
                if n in _TABLES:
                    low = text.lower()
                    scale = 1e6 if "millions" in low else 1e3 if "milliers" in low else 1.0
                    cur = (n,) + _TABLES[n] + (scale,)
                else:
                    cur = None
                seg = None
                continue
            if cur is None:
                continue
            mon = [(s, month_period(s[3])) for s in ln if _MONTH_RX.match(s[3])]
            if len(mon) >= 3 and all(p for _, p in mon):
                seg = {"state": cur, "months": [p for _, p in mon],
                       "hx": [(s[0] + s[2]) / 2 for s, _ in mon], "lines": []}
                segs.append(seg)
                continue
            if text.lower().startswith("source"):
                cur, seg = None, None
                continue
            if seg is not None:
                seg["lines"].append(ln)
    return segs


def _columns(seg):
    """Right-aligned numbers share a right edge: cluster the right edges of every numeric
    cell of the segment; the first k clusters, left to right, are the k month columns."""
    left = min(seg["hx"]) - 0.75 * (min(b - a for a, b in zip(seg["hx"], seg["hx"][1:])))
    x1s = sorted(s[2] for ln in seg["lines"] for s in ln
                 if s[2] > left and _NUM_RX.match(s[3]))
    clusters = []
    for x in x1s:
        if clusters and x - clusters[-1][-1] <= 3:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    clusters = [c for c in clusters if len(c) >= 2]
    k = len(seg["months"])
    if len(clusters) < k:
        return left, None
    return left, [(min(c) - 1.5, max(c) + 1.5) for c in clusters[:k]]


def _parse_issue(path: str, codes: dict[str, str]) -> list[dict]:
    import fitz
    out = []
    doc = fitz.open(path)
    fname = os.path.basename(path)
    try:
        segs = _segments(doc)
    finally:
        doc.close()
    for seg in segs:
        n, kind, flow, measure, scale = seg["state"]
        left, cols = _columns(seg)
        if cols is None:
            continue
        for ln in seg["lines"]:
            lab = " ".join(s[3] for s in ln if s[0] < left and not _NUM_RX.match(s[3])).strip()
            if not lab:
                continue
            vals = {}
            for s in ln:
                for per, (lo, hi) in zip(seg["months"], cols):
                    if lo <= s[2] <= hi and _NUM_RX.match(s[3]):
                        vals[per] = s[3]
            if kind == "head":
                u = lab.upper()
                if u.startswith("VALEUR"):
                    meas, unit, mult = "value", "XOF", (1e6 if "MILLION" in u else 1.0)
                elif u.startswith("POIDS"):
                    meas, unit, mult = "net_weight", "kg", (1e3 if "MILLIER" in u else 1.0)
                else:
                    continue
                for per, txt in vals.items():
                    v = to_number(txt, decimal=",")
                    if v is None:
                        continue
                    out.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit=unit,
                                   unit_multiplier=mult, measure=meas,
                                   price_basis=("fob" if flow == "export" else "cif") if meas == "value" else "",
                                   trade_system="general", series_code=f"BMSCE Tableau {n}"))
                continue
            total = lab.upper().startswith("TOTAL") or lab.upper() in ("ENSEMBLE", "MONDE")
            unit = "XOF" if measure == "value" else "kg"
            basis = ""
            if measure == "value" and flow != "balance":
                basis = "fob" if flow == "export" else "cif"
            for per, txt in vals.items():
                v = to_number(txt, decimal=",")
                if v is None:
                    continue
                if kind == "hs2":
                    if total:
                        com, cls, cc = None, "", ""
                    else:
                        com, cls, cc = lab, "hs2", codes.get(_key(lab), "")
                    out.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit=unit,
                                   unit_multiplier=scale, measure=measure, commodity=com,
                                   commodity_classification=cls, commodity_code_nso=cc,
                                   price_basis=basis, trade_system="general",
                                   series_code=f"BMSCE Tableau {n}"))
                else:
                    if total:
                        par, pt = None, "world"
                    else:
                        par, pt = lab, ("group" if _group_label(lab) else "country")
                    out.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit=unit,
                                   unit_multiplier=scale, partner=par, partner_type=pt,
                                   price_basis=basis, trade_system="general",
                                   series_code=f"BMSCE Tableau {n}"))
    for r in out:
        r["_file"] = fname
    return out


def parse_bmsce(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    wbs = [p for p in (extras or []) if p.lower().endswith(".xlsx") and "produits" in p.lower()]
    codes = hs2_label_codes(wbs)
    frames = []
    for p in [path] + list(extras or []):
        if not p.lower().endswith(".pdf"):
            continue
        rs = _parse_issue(p, codes)
        if not rs:
            continue
        df = pd.DataFrame(rs)
        df["_vintage"] = df["period"].max()
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    key = ["tradeflow", "commodity", "commodity_code_nso", "partner", "partner_type", "measure", "period",
           "unit", "price_basis"]
    # newest issue wins; within one issue the finer print (Tableau 1/2 in FCFA over the
    # chapter table's millions) wins.
    df["_neg_mult"] = -df["unit_multiplier"]
    df = df.sort_values(["_vintage", "_neg_mult"], kind="stable").drop_duplicates(key, keep="last")
    df = df.drop(columns=["_neg_mult"])
    return df.drop(columns=["_file", "_vintage"]).reset_index(drop=True)


# --------------------------------------------------------------------------- NACE (annual)
_NACE_TITLE = re.compile(r"Tableau\s*-?\s*\d+\s*:\s*Evolution g[ée]n[ée]rale du commerce ext[ée]rieur", re.I)
_YEAR_LINE = re.compile(r"^(?:(19|20)\d{2}|[12]\s\d{3})$")
_CELL = re.compile(r"^-?\d{1,3}(?:[   ]\d{3})*(?:,\d+)?$|^-?\d+(?:,\d+)?$")


def _nace_table(doc) -> list[tuple[int, list[str]]]:
    """The 'Evolution générale du commerce extérieur' annex table: one (year, cells) per row,
    one text line per cell; a row whose cells do not split cleanly is dropped."""
    for page in doc:
        text = page.get_text()
        m = _NACE_TITLE.search(text)
        if not m or "...." in text[m.start():m.start() + 200] or "----" in text[m.start():m.start() + 200]:
            continue
        lines = [ln.strip() for ln in text[m.end():].split("\n")]
        lines = [ln for ln in lines if ln]
        rows, year, cells = [], None, []
        for ln in lines:
            # a year line is the next year in sequence ("1 458" thousand tonnes is not a year)
            yv = int(ln.replace(" ", "")) if _YEAR_LINE.match(ln) else None
            if yv is not None and (year is None or yv == year + 1):
                if year is not None:
                    rows.append((year, cells))
                year, cells = yv, []
            elif year is not None:
                if _CELL.match(ln):
                    cells.append(ln)
                elif ln.lower().startswith(("source", "(a)", "b.c", "t.c", "note")):
                    break
                else:
                    cells.append(None)       # unreadable / merged cell -> poisons the row
        if year is not None:
            rows.append((year, cells))
        return rows
    return []


def parse_nace(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """Annual headline from the NACE annex 'Evolution générale du commerce extérieur':
    exports FOB and imports CIF in billions of FCFA, net weights in thousands of tonnes
    ("en Mt"), the trade balance (B.C., billions, signed). Editions are read oldest first and
    a later edition's figure replaces an earlier one's (revisions)."""
    import fitz
    files = [p for p in [path] + list(extras or []) if p.lower().endswith(".pdf")]

    def edition(p):
        m = re.search(r"NACE_(?:EDITION_)?(\d{4})", os.path.basename(p))
        return int(m.group(1)) if m else 0
    files.sort(key=edition)
    best: dict = {}
    for p in files:
        doc = fitz.open(p)
        try:
            rows = _nace_table(doc)
        finally:
            doc.close()
        for year, cells in rows:
            if any(c is None for c in cells):
                continue
            if len(cells) == 10:
                idx = {"ev": 0, "ew": 2, "iv": 4, "iw": 6, "bc": 8}
            elif len(cells) == 6:          # the first year of a table prints no variation
                idx = {"ev": 0, "ew": 1, "iv": 2, "iw": 3, "bc": 4}
            else:
                continue
            vals = {k: to_number(cells[i], decimal=",") for k, i in idx.items()}
            if None not in (vals["ev"], vals["iv"], vals["bc"]) and                     abs(vals["ev"] - vals["iv"] - vals["bc"]) > 1.5:
                # ANSD misprint: the 2022-2024 editions print the balance column shifted by
                # three years (2022 "-2 327" is 2019's). A balance that is not exports - imports
                # (within rounding) is dropped, never corrected.
                vals["bc"] = None
            for k, (flow, meas) in {"ev": ("export", "value"), "ew": ("export", "net_weight"),
                                    "iv": ("import", "value"), "iw": ("import", "net_weight"),
                                    "bc": ("balance", "value")}.items():
                v = vals[k]
                if v is None:
                    continue
                best[(flow, meas, str(year))] = (v, os.path.basename(p), edition(p))
    out = []
    for (flow, meas, year), (v, fname, ed) in best.items():
        out.append(row(tradeflow=flow, period=year, frequency="annual", value=v,
                       unit="XOF" if meas == "value" else "tonnes",
                       unit_multiplier=1e9 if meas == "value" else 1e3, measure=meas,
                       price_basis={"export": "fob", "import": "cif"}.get(flow, "") if meas == "value" else "",
                       trade_system="general", series_code=f"NACE {ed} Evolution generale"))
    return pd.DataFrame(out)


_REGION_TITLE = re.compile(r"Tableau\s*-?\s*\d+\s*:\s*(Exportations?|Importations?)\s+par\s+(r[ée]gion|continent)\s+en\s+valeur[^\n]*", re.I)


def _nace_regions(doc, edition: int) -> list[dict]:
    out = []
    for page in doc:
        text = page.get_text()
        for m in _REGION_TITLE.finditer(text):
            title = m.group(0)
            if "...." in title or "----" in title:
                continue
            scale, cur = scale_from_text(title, "SEN")
            if scale is None:
                continue
            flow = "export" if m.group(1).lower().startswith("export") else "import"
            body = text[m.end():]
            end = re.search(r"\n\s*(?:Source|Tableau)", body)
            body = body[:end.start()] if end else body[:4000]
            lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
            # header years: "2 021", "2021" ...; stop at the first label
            years, i = [], 0
            while i < len(lines):
                toks = [t for t in re.split(r"\s{2,}|\|", lines[i]) if t.strip()]
                ys = []
                for t in toks:
                    for y in re.findall(r"(?<!\d)(?:(?:19|20)\d{2}|[12] \d{3})(?!\d)", t):
                        ys.append(int(y.replace(" ", "")))
                if ys and all(1990 <= y <= 2030 for y in ys):
                    years += ys
                    i += 1
                    continue
                if years and not re.search(r"[A-Za-z]", lines[i]):
                    i += 1
                    continue
                if years:
                    break
                i += 1
            if not years or years != list(range(years[0], years[0] + len(years))):
                continue
            lab, vals, table, done = None, [], [], False
            for ln in lines[i:]:
                if done:
                    break
                if re.search(r"[A-Za-z]", ln) and not _CELL.match(ln):
                    piece = re.sub(r"\s+", " ", ln).strip()
                    # a label wrapped over two lines ("LES PAYS DE" / "L'AFRIQUE CENTRALE")
                    lab = f"{lab} {piece}" if (lab is not None and not vals) else piece
                    vals = []
                    continue
                if lab is None:
                    continue
                vals += [t.strip() for t in re.split(r"\s{2,}|\|", ln) if t.strip()]
                if len(vals) == len(years):
                    if all(_CELL.match(v) for v in vals):
                        total = lab.upper().startswith("TOTAL")
                        for y, v in zip(years, vals):
                            x = to_number(v, decimal=",")
                            if x is None:
                                continue
                            table.append(row(tradeflow=flow, period=str(y), frequency="annual", value=x,
                                           unit=cur, unit_multiplier=scale,
                                           partner=None if total else lab,
                                           partner_type="world" if total else "group",
                                           price_basis="fob" if flow == "export" else "cif",
                                           trade_system="general",
                                           series_code=f"NACE {edition} {m.group(1)} par {m.group(2)}"))
                        done = total
                    lab, vals = None, []
                elif len(vals) > len(years):
                    lab, vals = None, []
            # keep a table only when it ends in its TOTAL row (checked against the headline
            # by parse_nace_all) -- a table that runs into the next one is dropped.
            if done and table:
                out += table
    return out


def parse_nace_all(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """parse_nace (annual headline) + the annex tables of exports / imports by region and by
    continent (millions of FCFA, all products; ANSD's groupings -> partner_type group, TOTAL ->
    all partners). Newest edition wins per key."""
    import fitz
    head = parse_nace(path, extras)
    files = [p for p in [path] + list(extras or []) if p.lower().endswith(".pdf")]
    rows = []
    for p in files:
        m = re.search(r"NACE_(?:EDITION_)?(\d{4})", os.path.basename(p))
        ed = int(m.group(1)) if m else 0
        doc = fitz.open(p)
        try:
            rs = _nace_regions(doc, ed)
        finally:
            doc.close()
        for r in rs:
            r["_ed"] = ed
        rows += rs
    reg = pd.DataFrame(rows)
    if not reg.empty:
        # The regions (continents) + DIVERS partition the world: a table whose rows do not
        # add up to its own TOTAL in every year (within 0.5 %) ran into another table or was
        # misread -- drop the whole table. (A CHECK; the sum is never emitted.)
        bad = set()
        for sc, g in reg.groupby("series_code"):
            for per, gp in g.groupby("period"):
                tot = gp.loc[gp["partner"] == "All partners", "value"]
                parts = gp.loc[gp["partner"] != "All partners", "value"].sum()
                if tot.empty or abs(parts - tot.iloc[0]) > 0.005 * abs(tot.iloc[0]) + len(gp):
                    bad.add(sc)
        reg = reg[~reg["series_code"].isin(bad)]
        key = ["tradeflow", "partner", "period"]
        reg = reg.sort_values("_ed", kind="stable").drop_duplicates(key, keep="last").drop(columns="_ed")
        # The regional TOTAL repeats the headline (often from another edition): the headline
        # table's figure is kept, so exports, imports and the balance of a year come from one
        # table; a regional TOTAL is kept only for a year the headline table does not print.
        have = {(r.tradeflow, r.period) for r in head.itertuples() if r.measure == "value"}
        reg = reg[~((reg["partner"] == "All partners")
                    & pd.Series([(f, p) in have for f, p in zip(reg["tradeflow"], reg["period"])], index=reg.index))]
    return pd.concat([head, reg], ignore_index=True)
