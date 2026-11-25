"""Parsers for INSD Burkina Faso merchandise trade (Tier 3 PDF).

INSD (Institut National de la Statistique et de la Démographie) compiles
Burkina Faso's merchandise trade statistics from customs (SYDONIA) records;
exports FOB, imports CIF, values in FCFA (XOF).

* ``parse_annuaire`` -- "Annuaire du commerce extérieur" (annual). Read:
  Tableau 1.1 (imports, exports, trade balance, billions of FCFA, every year
  since 1995), Tableaux 3.x (by HS chapter: value in millions of FCFA, net
  weight in tonnes, all partners, with the chapter code "CH"), 9.1-9.6 (by
  partner country and INSD's regional lines: exports, imports, balance,
  millions of FCFA) and 9.7-9.12 (by economic zone: CEDEAO, UEMOA, UE27 ...).
* ``parse_sce`` -- the quarterly note "Statistiques du commerce extérieur"
  (SCE): Tableau 1.1 / 1.4 / 1.7 (quarterly exports, imports in billions of
  FCFA and thousands of tonnes; the balance) and Tableaux 1.3 / 1.6 (exports
  / imports by partner country, billions of FCFA).

Cells: thousands are separated by a narrow no-break space, cells by runs of
ordinary spaces, so one text span may hold several cells; a span is split only
when it covers several header columns and yields exactly that many pieces, a
row is kept only when every year column is accounted for (else dropped, never
guessed). "-" is an empty cell; a "-" padded before a number inside ONE column
is the accounting-format minus sign.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import quarter_period, row, to_number

_TITLE = re.compile(r"Tableau\s*n?°?\s*(\d+)\.(\d+)\s*:\s*(.+)", re.I)
_NUMCELL = re.compile(r"^-?\s*\d{1,3}(?:[   ]\d{3})*(?:,\d+)?$|^-$")


def _spans(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
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


def _cells(ln, cols, label_right):
    """Map the numeric spans of a line onto header columns -> {col_index: text}."""
    out = {}
    centres = [c for c in cols]
    gap = min((b - a for a, b in zip(centres, centres[1:])), default=80)
    for x0, _, x1, t in ln:
        if x1 <= label_right:
            continue
        inside = [i for i, c in enumerate(centres) if x0 - 2 <= c <= x1 + 2]
        if len(inside) >= 2:
            pieces = [p for p in re.split(r" {2,}", t.strip()) if p]
            if len(pieces) != len(inside) or not all(_NUMCELL.match(p) for p in pieces):
                return None
            for i, p in zip(inside, pieces):
                out[i] = p
        else:
            if not _NUMCELL.match(t.strip()):
                continue
            c = (x0 + x1) / 2
            i = min(range(len(centres)), key=lambda k: abs(centres[k] - c))
            if abs(centres[i] - c) > gap * 0.75:
                continue            # a column outside the header (e.g. "Taux de couverture")
            if i in out:
                return None
            out[i] = t.strip()
    return out


def _num(t):
    if t is None:
        return None
    t = t.strip()
    if t == "-":
        return None
    neg = t.startswith("-")
    v = to_number(re.sub(r"^-\s*", "", t), decimal=",")
    if v is None:
        return None
    return -v if neg else v


_GROUP_WORDS = ("union", "autres", "autre ", "divers", "non ", "total", "ensemble", "cedeao", "uemoa",
                "autres pays", "zone", "reste", "moyen", "proche", "extrême", "extreme", "ue27", "ue 27")
_REGIONS = {"afrique", "amérique", "amerique", "asie", "europe", "océanie", "oceanie"}


def _partner_type(lab: str) -> str:
    low = lab.lower()
    if any(w in low for w in _GROUP_WORDS):
        return "group"
    first = low.split()[0] if low.split() else ""
    if first in _REGIONS and not re.search(r"\bdu sud\b", low):
        return "group"
    return "country"


def _annuaire_tables(doc):
    """Yield (major, minor, title, years/cols, rows) for every annex table page."""
    cur, prev = None, None
    for page in doc:
        lines = _lines(_spans(page))
        for k, ln in enumerate(lines):
            text = " ".join(s[3] for s in ln)
            m = _TITLE.match(text.strip())
            if cur is None and not m and prev is not None:
                # a continuation page without a repeated title: same year header as before
                yrs = [s[3] for s in ln if re.fullmatch(r"(19|20)\d{2}", s[3])]
                if len(yrs) >= 3 and yrs == prev["labels"]:
                    cur = {**prev, "lines": [], "cols": None}
            if m:
                if cur and cur["cols"]:
                    yield cur
                cur = {"major": int(m.group(1)), "minor": int(m.group(2)), "title": m.group(3),
                       "cols": None, "labels": None, "lines": [], "label_right": None}
                continue
            if cur is None:
                continue
            if cur["cols"] is None:
                yrs = [s for s in ln if re.fullmatch(r"(19|20)\d{2}", s[3])]
                if len(yrs) >= 3:
                    cur["cols"] = [(s[0] + s[2]) / 2 for s in yrs]
                    cur["labels"] = [s[3] for s in yrs]
                    cur["label_right"] = min(s[0] for s in yrs) - 25
                    continue
                words = [s for s in ln if s[3] in ("Importations", "Exportations")]
                if len(words) == 2:
                    cur["hdr_words"] = [(s[3], (s[0] + s[2]) / 2) for s in words]
                elif "hdr_words" in cur and any(s[3] == "commerciale" for s in ln):
                    bal = [s for s in ln if s[3] == "commerciale"][0]
                    hw = cur["hdr_words"] + [("Balance", (bal[0] + bal[2]) / 2)]
                    cur["cols"] = [c for _, c in hw]
                    cur["labels"] = [w for w, _ in hw]
                    cur["label_right"] = min(cur["cols"]) - 45
                continue
            cur["lines"].append(ln)
        # a table continues on the next page only under its own repeated title
        if cur and cur["cols"]:
            yield cur
            prev = {k: v for k, v in cur.items() if k != "lines"}
        else:
            prev = None
        cur = None


def _chapter_rows(tab):
    """Chapter rows: a 2-digit code span at the left; label pieces on the code line or on
    label-only lines, each given to the nearest code line."""
    code_lines, label_lines = [], []
    for ln in tab["lines"]:
        left = [s for s in ln if s[2] <= tab["label_right"]]
        if left and re.fullmatch(r"\d{2}", left[0][3]):
            code_lines.append(ln)
        elif left and not any(s[2] > tab["label_right"] for s in ln):
            label_lines.append(ln)
    labels = {id(ln): [" ".join(s[3] for s in ln if s[2] <= tab["label_right"])[2:].strip()]
              for ln in code_lines}
    for ln in label_lines:
        if not code_lines:
            break
        y = ln[0][1]
        near = min(code_lines, key=lambda c: abs(c[0][1] - y))
        if abs(near[0][1] - y) < 20:
            labels[id(near)].append((y, " ".join(s[3] for s in ln)))
    out = []
    for ln in code_lines:
        y0 = ln[0][1]
        own = labels[id(ln)][0]
        pieces = [(y0, own)] + [p for p in labels[id(ln)][1:]]
        lab = " ".join(t for _, t in sorted(pieces, key=lambda p: p[0]) if t).strip()
        out.append((ln[0][3], re.sub(r"\s+", " ", lab), ln))
    return out


def parse_annuaire(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    import fitz
    files = [p for p in [path] + list(extras or []) if p.lower().endswith(".pdf")]

    def edition(p):
        m = re.findall(r"(19|20)(\d{2})", os.path.basename(p))
        return int("".join(m[-1])) if m else 0
    files.sort(key=edition)
    frames = []
    for p in files:
        doc = fitz.open(p)
        try:
            rows = _parse_annuaire_doc(doc)
        finally:
            doc.close()
        df = pd.DataFrame(rows)
        if not df.empty:
            df["_ed"] = edition(p)
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    # one figure per chapter CODE (labels are reworded between editions), partner, year
    df["_ck"] = df["commodity_code_nso"].where(df["commodity_code_nso"] != "", df["commodity"])
    key = ["tradeflow", "_ck", "partner", "measure", "period"]
    df = df.sort_values("_ed", kind="stable").drop_duplicates(key, keep="last")
    return df.drop(columns=["_ed", "_ck"]).reset_index(drop=True)


def _parse_annuaire_doc(doc) -> list[dict]:
    out = []
    for tab in _annuaire_tables(doc):
        maj, mnr, title = tab["major"], tab["minor"], tab["title"].lower()
        sc = f"Annuaire Tableau {maj}.{mnr}"
        if maj == 1 and mnr == 1 and "milliards" in title:
            if tab["labels"][:3] != ["Importations", "Exportations", "Balance"]:
                continue
            for ln in tab["lines"]:
                y = ln[0][3]
                if not re.fullmatch(r"(19|20)\d{2}", y):
                    continue
                cells = _cells(ln, tab["cols"], tab["label_right"])
                if cells is None:
                    continue
                for i, flow in enumerate(("import", "export", "balance")):
                    v = _num(cells.get(i))
                    if v is None:
                        continue
                    out.append(row(tradeflow=flow, period=y, frequency="annual", value=v, unit="XOF",
                                   unit_multiplier=1e9,
                                   price_basis={"import": "cif", "export": "fob"}.get(flow, ""),
                                   series_code=sc))
            continue
        flow = "export" if "exportations" in title else "import" if "importations" in title else \
            "balance" if "balance" in title else None
        if flow is None:
            continue
        if "en millions" in title:
            meas, unit, mult = "value", "XOF", 1e6
        elif "en milliards" in title:
            meas, unit, mult = "value", "XOF", 1e9
        elif re.search(r"en tonnes\b", title):
            meas, unit, mult = "net_weight", "tonnes", 1.0
        elif "milliers de tonnes" in title:
            meas, unit, mult = "net_weight", "tonnes", 1e3
        else:
            continue
        basis = {"export": "fob", "import": "cif"}.get(flow, "") if meas == "value" else ""
        years = tab["labels"]
        if maj == 3 and "chapitre sh" in title:
            for code, lab, ln in _chapter_rows(tab):
                cells = _cells(ln, tab["cols"], tab["label_right"])
                if cells is None or len(cells) != len(years):
                    continue
                for i, y in enumerate(years):
                    v = _num(cells.get(i))
                    if v is None:
                        continue
                    out.append(row(tradeflow=flow, period=y, frequency="annual", value=v, unit=unit,
                                   unit_multiplier=mult, measure=meas, commodity=lab or code,
                                   commodity_classification="hs2", commodity_code_nso=code,
                                   price_basis=basis, series_code=sc))
            # the chapter tables' TOTAL line
            for ln in tab["lines"]:
                lab = " ".join(s[3] for s in ln if s[2] <= tab["label_right"]).strip()
                if lab.upper().startswith(("TOTAL", "ENSEMBLE")):
                    cells = _cells(ln, tab["cols"], tab["label_right"])
                    if cells is None or len(cells) != len(years):
                        continue
                    for i, y in enumerate(years):
                        v = _num(cells.get(i))
                        if v is not None:
                            out.append(row(tradeflow=flow, period=y, frequency="annual", value=v,
                                           unit=unit, unit_multiplier=mult, measure=meas,
                                           price_basis=basis, series_code=sc))
            continue
        if maj == 9 and ("par pays" in title or "zone" in title) and meas == "value":
            zone = "zone" in title
            for ln in tab["lines"]:
                lab = " ".join(s[3] for s in ln if s[2] <= tab["label_right"]).strip()
                if not lab or lab.lower() == "dont":
                    continue
                cells = _cells(ln, tab["cols"], tab["label_right"])
                if not cells:
                    continue
                if len(cells) != len(years):
                    continue
                total = lab.upper().startswith(("TOTAL", "ENSEMBLE")) or lab.lower() == "monde"
                for i, y in enumerate(years):
                    v = _num(cells.get(i))
                    if v is None:
                        continue
                    if total:
                        par, pt = None, "world"
                    else:
                        par, pt = lab, ("group" if zone else _partner_type(lab))
                    out.append(row(tradeflow=flow, period=y, frequency="annual", value=v, unit=unit,
                                   unit_multiplier=mult, partner=par, partner_type=pt,
                                   price_basis=basis, series_code=sc))
    return out


# --------------------------------------------------------------------------- quarterly note
_SCE_TITLE = re.compile(r"Tableau\s*0?1?\.?0?(\d+)\s*:\s*(.+)", re.I)
_QLAB = re.compile(r"^([1-4])\s*T\s*(\d{2})$")


def _sce_kind(title: str):
    low = title.lower()
    if "balance commerciale" in low or re.search(r"evolution du commerce ext", low):
        return "balance"
    if "exportations par pays" in low:
        return "export_partner"
    if "importations par pays" in low:
        return "import_partner"
    return None


def _sce_tables(doc):
    cur = None
    for page in doc:
        lines = _lines(_spans(page))
        if cur is not None and cur["cols"] is not None:
            cur = None          # a table whose header was found ends with its page
        for ln in lines:
            text = " ".join(s[3] for s in ln).strip()
            m = _SCE_TITLE.match(text)
            if m and "...." not in text:
                kind = _sce_kind(m.group(2))
                if cur and cur["cols"]:
                    yield cur
                cur = {"kind": kind, "title": m.group(2), "cols": None, "lines": []} if kind else None
                continue
            if cur is None:
                continue
            if cur["cols"] is None:
                q = [s for s in ln if _QLAB.match(s[3].strip())]
                if len(q) >= 5:
                    q = q[:5]
                    cur["cols"] = [(s[0] + s[2]) / 2 for s in q]
                    cur["qlabels"] = [s[3] for s in q]
                    cur["label_right"] = min(s[0] for s in q) - 10
                else:
                    cur["title"] += " " + text        # the caption wraps onto a second line
                continue
            if text.lower().startswith(("source", "graphique")):
                yield cur
                cur = None
                continue
            cur["lines"].append(ln)
        if cur and cur["cols"]:
            yield cur
            cur = None


def _quarters(labels):
    """'2 T 18' -> '2018-Q2'. A label that breaks the run of consecutive quarters (the
    3T2021 note prints '1 T 20' for 1T21) is dropped (None), never corrected."""
    qs = []
    for t in labels:
        m = _QLAB.match(t.strip())
        qs.append((2000 + int(m.group(2)), int(m.group(1))))
    idx = [y * 4 + q - 1 for y, q in qs]
    out = []
    for i, (y, q) in enumerate(qs):
        ok = any(0 <= j < len(idx) and j != i and idx[j] - idx[i] == j - i for j in (i - 1, i + 1))
        out.append(f"{y}-Q{q}" if ok else None)
    return out


def _labelled_rows(tab):
    """(label, line) for value lines; a value line without a label takes the label-only
    lines just above and below it ('CHINE (REPUBLIQUE POPULAIRE' / values / 'DE)')."""
    lr = tab["label_right"]
    kinds = []
    for ln in tab["lines"]:
        lab = " ".join(s[3] for s in ln if s[2] <= lr).strip()
        has_val = any(s[0] > lr for s in ln)
        kinds.append((lab, has_val, ln))
    vals = [i for i, k in enumerate(kinds) if k[1]]
    extra: dict = {i: [] for i in vals}
    for j, (lab, has_val, ln) in enumerate(kinds):
        if has_val or not lab or not vals:
            continue
        i = min(vals, key=lambda v: abs(kinds[v][2][0][1] - ln[0][1]))
        if abs(kinds[i][2][0][1] - ln[0][1]) < 12:
            extra[i].append((ln[0][1], lab))
    out = []
    for i in vals:
        lab, _, ln = kinds[i]
        pieces = sorted(extra[i] + ([(ln[0][1], lab)] if lab else []))
        lab = " ".join(p for _, p in pieces).strip()
        if re.search(r"[A-Za-zÀ-ÿ]", lab):     # a stray ")" is not a label
            out.append((re.sub(r"\s+", " ", lab), ln))
    return out


def parse_sce(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """Quarterly notes (SCE, and the 2018 'ICE' issues in the same layout): Tableau 7
    (exports FOB, imports CIF, trade balance BC, billions of FCFA) and Tableaux 3 / 6 (the
    main partner countries, exports FOB / imports CIF, billions of FCFA). Five quarters per
    issue; the newest issue wins per quarter."""
    import fitz
    frames = []
    for p in [path] + list(extras or []):
        if not p.lower().endswith(".pdf"):
            continue
        doc = fitz.open(p)
        rows = []
        try:
            for tab in _sce_tables(doc):
                if "milliards" not in tab["title"].lower():
                    continue
                pers = _quarters(tab["qlabels"])
                for lab, ln in _labelled_rows(tab):
                    cells = _cells(ln, tab["cols"], tab["label_right"])
                    if not cells:
                        continue
                    if tab["kind"] == "balance":
                        u = lab.upper()
                        flow = "export" if u.startswith("EXPORT") else "import" if u.startswith("IMPORT") \
                            else "balance" if u in ("BC", "BALANCE COMMERCIALE") else None
                        if flow is None:
                            continue
                        par, pt = None, "world"
                    else:
                        flow = "export" if tab["kind"] == "export_partner" else "import"
                        if lab.upper().startswith(("TOTAL", "ENSEMBLE")):
                            par, pt = None, "world"
                        elif lab.upper().startswith("AUTRES"):
                            par, pt = lab, "group"
                        else:
                            par, pt = lab, _partner_type(lab)
                    for i, per in enumerate(pers):
                        if per is None:
                            continue
                        v = _num(cells.get(i))
                        if v is None:
                            continue
                        rows.append(row(tradeflow=flow, period=per, frequency="quarterly", value=v,
                                        unit="XOF", unit_multiplier=1e9, partner=par, partner_type=pt,
                                        price_basis={"export": "fob", "import": "cif"}.get(flow, ""),
                                        series_code=f"SCE {tab['kind']}"))
        finally:
            doc.close()
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        df["_vintage"] = df["period"].max()
        df["_file"] = os.path.basename(p)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    key = ["tradeflow", "partner", "period"]
    df = df.sort_values(["_vintage", "_file"], kind="stable").drop_duplicates(key, keep="last")
    return df.drop(columns=["_vintage", "_file"]).reset_index(drop=True)
