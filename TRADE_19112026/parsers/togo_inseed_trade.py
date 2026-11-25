"""Parser for INSEED Togo quarterly bulletins of international merchandise trade (Tier 3 PDF).

INSEED (Institut National de la Statistique et des Etudes Economiques et Démographiques)
publishes the "Bulletin (trimestriel) statistique du Commerce international des
marchandises" (customs data, Eurotrace). Each issue prints the five latest quarters in:

* Tableau 1 -- exports f.o.b., imports c.a.f., trade balance (millions of FCFA) and the
  quantities exported / imported (tonnes), all products, all partners;
* "... par section de la CTCI" / "... par division de la CTCI" (SITC rev.4 sections ->
  sitc1, divisions -> sitc2), value (millions of FCFA) and quantity (tonnes);
* "... selon les pays et territoires" (partner countries, ISO alpha-2 code + name);
* "... selon la zone géographique" / "... selon les zones économiques" (blocs: CEDEAO,
  UEMOA, UE ...; partner_type group);
* from 2023 or so also Tableaux 87/88/89 "Valeur des exportations / importations / Solde
  commercial par période (milliards de FCFA)": every month, quarter and year since 2008
  (semesters are skipped -- no schema frequency).

Not read: HS-section tables (no schema classification for HS sections; SITC is read),
shares, growth rates, customs-regime tables, top-ten tables.

Columns are located on the page: each figure is given to the period header whose right
edge is nearest (within half a column). Row labels that wrap over several text lines are
re-joined by vertical position. Newest issue wins per observation.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import row, to_number

_Q_RX = re.compile(r"^(\d{4})\s*T\s*([1-4])$")
_Y_RX = re.compile(r"^(19|20)\d{2}$")
_NUM_RX = re.compile(r"^-?\d{1,3}(?:[\s  ]\d{3})*(?:,\d+)?$|^-?\d+(?:,\d+)?$")
_TAB_RX = re.compile(r"^Tableau\s*\d+\s*:", re.I)
_MONTHS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre",
           "octobre", "novembre", "decembre"]
_NOT_COUNTRY = {"XX", "QU", "QZ", "ZZ", "QS", "QR", "QW", "XZ", "ND"}


def _fold(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


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


def _kind(title: str):
    """(kind, flow, measure, multiplier, classification) from a table title, or None."""
    t = _fold(title)
    if any(w in t for w in ("structure", "part relative", "parts relatives", "variation", "glissement",
                            "dix premiers", "regime douanier")):
        return None
    if "exportation et importation en valeur et quantite" in t:
        return ("head", None, None, None, "")
    m = re.search(r"valeur des (exportations|importations) par periode|solde commercial par periode", t)
    if m:
        flow = "balance" if "solde" in t else ("export" if "export" in t else "import")
        return ("period", flow, "value", 1e9 if "milliards" in t else None, "")
    flow = "export" if "des exportations" in t else "import" if "des importations" in t else None
    if flow is None:
        return None
    if t.startswith("valeur") or "valeur f.o.b" in t or "valeur c.a.f" in t:
        measure = "value"
        mult = 1e6 if "million" in t else 1e9 if "milliard" in t else None
    elif "quantite" in t:
        measure = "net_weight"
        mult = 1.0 if "tonne" in t else None
    else:
        return None
    if mult is None:
        return None
    if "division de la ctci" in t or "divisions de la ctci" in t:
        return ("sitc2", flow, measure, mult, "sitc2")
    if "section de la ctci" in t or "sections de la ctci" in t:
        return ("sitc1", flow, measure, mult, "sitc1")
    if "pays et territoires" in t:
        return ("country", flow, measure, mult, "")
    if "zone geographique" in t or "zones geographiques" in t or "zones economiques" in t:
        return ("zone", flow, measure, mult, "")
    return None


def _consecutive(hdr):
    """Quarter columns are consecutive quarters. The 2022-T3 issue prints "2022T3 2021T2
    2021T1 2021T4 2021T3" (for 2022T2 and 2022T1), so its 2022 figures were filed under
    2021. The columns whose label does not fit the run of consecutive quarters that most
    labels fit are dropped -- never relabelled. (Repaired 2026-11-12.)"""
    cols = sorted(hdr, key=lambda h: h[0][2])
    ords = [int(p[:4]) * 4 + int(p[-1]) - 1 for _, p in cols]
    best = []
    for j in range(len(ords)):
        for d in (1, -1):
            keep = [c for i, c in enumerate(cols) if ords[i] == ords[j] + d * (i - j)]
            if len(keep) > len(best):
                best = keep
    return best if len(best) >= 3 else None


def _segments(doc):
    segs, cur, seg = [], None, None
    for page in doc:
        seg = None
        for ln in _lines(_spans(page)):
            text = " ".join(s[3] for s in ln)
            if _TAB_RX.match(text):
                if "----" in text or "...." in text:
                    cur = None
                    continue
                cur = (_kind(text), text)
                seg = None
                continue
            if cur is None or cur[0] is None:
                continue
            qs = [(s, _Q_RX.match(s[3].replace(" ", ""))) for s in ln]
            qs = [(s, f"{m.group(1)}-Q{m.group(2)}") for s, m in qs if m]
            ys = [(s, s[3]) for s in ln if _Y_RX.match(s[3])]
            hdr = qs if len(qs) >= 3 else (ys if cur[0][0] == "period" and len(ys) >= 3 else None)
            if hdr and hdr is qs:
                hdr = _consecutive(hdr)
            if hdr:
                seg = {"kind": cur[0], "title": cur[1], "cols": [(p, s[2]) for s, p in hdr], "lines": []}
                segs.append(seg)
                continue
            if seg is not None:
                seg["lines"].append(ln)
    return segs


_MULTI_RX = re.compile(r"^-?\d{1,3}(?:[\s  ]\d{3})*,\d+(?:\s+-?\d{1,3}(?:[\s  ]\d{3})*,\d+)+$")
_CODE_RX = re.compile(r"^[A-Z0-9][A-Z0-9+\-]{0,9}$")


def _values(seg, ln):
    cols = seg["cols"]
    xs = sorted(x for _, x in cols)
    half = min((b - a for a, b in zip(xs, xs[1:])), default=60) / 2
    vals = {}
    for s in ln:
        if s[2] < xs[0] - half:
            continue
        if not _NUM_RX.match(s[3]):
            # Several figures in ONE span ("202 673,1 179 323,6 197 620,1 ...") were
            # not read, so the row's text was glued onto a neighbour's label. Every
            # figure ends in a decimal, so the span cuts after each ",d"; its figures
            # are kept only when they are exactly as many as the period columns whose
            # right edge falls inside the span. (Repaired 2026-11-12.)
            t = s[3].strip()
            if not _MULTI_RX.match(t):
                continue
            toks = re.split(r"(?<=,\d)\s+|(?<=,\d\d)\s+|(?<=,\d\d\d)\s+", t)
            inside = sorted((c for c in cols if s[0] - 2 <= c[1] <= s[2] + 2), key=lambda c: c[1])
            if len(inside) != len(toks):
                continue
            for (p, _), tok in zip(inside, toks):
                if p not in vals:
                    vals[p] = tok
            continue
        p, x = min(cols, key=lambda c: abs(c[1] - s[2]))
        if abs(x - s[2]) <= half and p not in vals:
            vals[p] = s[3]
    return vals


def _rows_of(seg):
    """[(label, {period: text})]. A row's code and figures stand on one line; a long
    name is printed over several lines, above, around or below that line depending on
    the issue ("Antilles neerlandaises (Bonnaire;" / "Curaçao; Saba et St-Eustache; St-"
    / "AN Martin Méridional) 0,0 ...", or "AN Antilles ... (Bonnaire; 0,8 ..." followed by
    the two other lines). The text lines between two figure lines form one block that
    belongs to ONE of them: the one without a name of its own, else the one whose
    brackets the block closes; only when brackets do not decide, each line goes to the
    nearest row within 14 pt (the old rule, which made "Albanie Antilles neerlandaises"
    and "Martin Méridional) Angola"). The code (ISO code, bloc acronym) is kept in front
    of the name, also when printed on a line of its own ("Alliance ... ALBA-TCP Amérique
    ..." became "ALBA-TCP Alliance ... Amérique ..."). (Repaired 2026-11-12.)"""
    left = min(x for _, x in seg["cols"]) - 60
    data, texts = [], []
    for ln in seg["lines"]:
        vals = _values(seg, ln)
        words = [s for s in ln if s[0] < left and not (_NUM_RX.match(s[3]) and s[0] > left)]
        if vals:
            data.append((ln[0][1], words, vals))
        else:
            txt = [s for s in ln if s[0] < left + 40]
            if txt:
                texts.append((ln[0][1], txt))

    def split_code(words):
        if words and _CODE_RX.match(words[0][3].strip()):
            return words[0][3].strip(), words[1:]
        return "", words

    def own(i):
        return " ".join(s[3] for s in split_code(data[i][1])[1]).strip()

    def bal(t):
        return t.count("(") == t.count(")")

    ys = [d[0] for d in data]
    extra = {i: [] for i in range(len(data))}
    codes = {}
    blocks = {}                         # (above, below) -> [(y, txt)]
    for y, txt in texts:
        t = " ".join(s[3] for s in txt).strip()
        if t.isdigit() or re.search(r"\d\s?,\s?\d", t) or _fold(t).startswith(("monde", "total", "ensemble")):
            continue                    # a page number, figures not read, a total's label: never a name
        if len(txt) == 1 and _CODE_RX.match(t):
            near = [k for k in range(len(ys)) if abs(ys[k] - y) <= 8 and not split_code(data[k][1])[0]]
            if near:
                codes.setdefault(min(near, key=lambda k: abs(ys[k] - y)), t)
                continue
        above = max((k for k in range(len(ys)) if ys[k] < y), key=lambda k: ys[k], default=None)
        below = min((k for k in range(len(ys)) if ys[k] > y), key=lambda k: ys[k], default=None)
        blocks.setdefault((above, below), []).append((y, txt))
    for (a, b), lines in blocks.items():
        btxt = " ".join(" ".join(s[3] for s in t) for _, t in sorted(lines))
        y0, y1 = min(y for y, _ in lines), max(y for y, _ in lines)
        okA = a is not None and y1 - ys[a] <= 24
        okB = b is not None and ys[b] - y0 <= 24
        owner = None
        if okA and okB and not own(a) and not own(b):
            for y, t in lines:          # two rows without names: each line to the nearer one
                extra[min((a, b), key=lambda k: abs(ys[k] - y))].append((y, t))
            continue
        if okB and not own(b):
            owner = b
        elif okA and not own(a):
            owner = a
        else:
            toA = okA and bal(own(a) + btxt) and (b is None or bal(own(b)))
            toB = okB and bal(btxt + own(b)) and (a is None or bal(own(a)))
            if toA != toB:
                owner = a if toA else b
            elif toA and toB and okB and own(b)[:1].islower():
                owner = b               # the row's own name is a continuation ("commerciales entre ...")
            elif toA and toB and okA and (btxt[:1].islower() or btxt[:1] in ":;,-–"):
                owner = a               # a name continued below its figure line ("... de" / "l'Ouest")
            elif toA and toB:
                for y, t in lines:      # nothing decides: nearest row, as before
                    near = [k for k in (a, b) if k is not None and abs(ys[k] - y) <= 14]
                    if near:
                        extra[min(near, key=lambda k: abs(ys[k] - y))].append((y, t))
                continue
        if owner is not None:
            extra[owner] += lines
    out = []
    for i, (y, words, vals) in enumerate(data):
        code, rest = split_code(words)
        code = code or codes.get(i, "")
        pieces = [(yy, " ".join(s[3] for s in t)) for yy, t in extra[i]] + [(y, " ".join(s[3] for s in rest))]
        name = " ".join(p for _, p in sorted(pieces) if p).strip()
        out.append(((code + " " + name).strip(), vals))
    return out


def _period_row(label: str):
    f = _fold(label).strip()
    if f in _MONTHS:
        return ("monthly", _MONTHS.index(f) + 1)
    m = re.match(r"^(1er|2eme|3eme|4eme|premier|deuxieme|troisieme|quatrieme)\s+trimestre", f)
    if m:
        q = {"1er": 1, "premier": 1, "2eme": 2, "deuxieme": 2, "3eme": 3, "troisieme": 3,
             "4eme": 4, "quatrieme": 4}[m.group(1)]
        return ("quarterly", q)
    if f.startswith("annee"):
        return ("annual", None)
    return None


def _glossary(doc) -> dict:
    """Acronym -> name, from the bulletin's list of abbreviations ("CEDEAO  COMMUNAUTÉ
    ÉCONOMIQUE DES ÉTATS DE L'AFRIQUE DE L'OUEST"), first pages only."""
    out = {}
    for page in list(doc)[:10]:
        for ln in _lines(_spans(page)):
            if len(ln) == 2 and _CODE_RX.match(ln[0][3].strip()) and ln[1][3].upper() == ln[1][3] \
                    and len(ln[1][3]) > 8:
                out[ln[0][3].strip()] = _key(ln[1][3])
    return out


def _key(name: str) -> str:
    return re.sub(r"[^a-z]", "", _fold(name))[:14]


def _zone_misaligned(rows, gloss) -> bool:
    """True when a bloc table prints acronyms against other blocs' names (2016-T4..2017-T3
    bulletin, Tableau 59: "CARICOM Conseil de coopération des États arabes du Golfe",
    "CEAP Communauté économique des États de l'Afrique de l'Ouest" -- from CAN down the
    name column is one row off the acronym column). The figures then cannot be given to a
    bloc with certainty, so the table is not read. (Repaired 2026-11-12.)"""
    for label, _ in rows:
        m = re.match(r"^(\S+)\s+(.+)$", label.strip())
        if m and m.group(1) in gloss and len(gloss[m.group(1)]) >= 8:
            k = _key(m.group(2))
            n = min(len(k), len(gloss[m.group(1)]))
            if n >= 8 and k[:n] != gloss[m.group(1)][:n]:
                return True
    return False


def _parse_issue(path: str) -> list[dict]:
    import fitz
    doc = fitz.open(path)
    try:
        segs = _segments(doc)
        gloss = _glossary(doc)
    finally:
        doc.close()
    out = []
    for n_seg, seg in enumerate(segs):
        n_out = len(out)
        kind, flow, measure, mult, cls = seg["kind"]
        sc = seg["title"].split(":")[0].strip()
        if kind == "head":
            # rows in print order: exports, imports, balance (values, millions), then exports,
            # imports (quantities, tonnes) -- the k-th export / import row decides the measure.
            seen = {"export": 0, "import": 0}
            for label, vals in _rows_of(seg):
                f = _fold(label)
                fl = "balance" if "solde" in f else "import" if "importation" in f else                     "export" if "exportation" in f else None
                if fl is None:
                    continue
                if fl == "balance":
                    meas = "value"
                else:
                    meas = "value" if seen[fl] == 0 else "net_weight"
                    seen[fl] += 1
                    if seen[fl] > 2:
                        continue
                for p, t in vals.items():
                    v = to_number(t, decimal=",")
                    if v is None:
                        continue
                    out.append(row(tradeflow=fl, period=p, frequency="quarterly", value=v,
                                   unit="XOF" if meas == "value" else "tonnes",
                                   unit_multiplier=1e6 if meas == "value" else 1, measure=meas,
                                   price_basis={"export": "fob", "import": "cif"}.get(fl, "") if meas == "value" else "",
                                   series_code=sc))
            continue
        if kind == "period":
            for label, vals in _rows_of(seg):
                pr = _period_row(label)
                if pr is None:
                    continue
                freq, k = pr
                for y, t in vals.items():
                    v = to_number(t, decimal=",")
                    if v is None:
                        continue
                    per = y if freq == "annual" else (f"{y}-{k:02d}" if freq == "monthly" else f"{y}-Q{k}")
                    out.append(row(tradeflow=flow, period=per, frequency=freq, value=v, unit="XOF",
                                   unit_multiplier=mult,
                                   price_basis={"export": "fob", "import": "cif"}.get(flow, ""),
                                   series_code=sc))
            continue
        basis = ("fob" if flow == "export" else "cif") if measure == "value" else ""
        unit = "XOF" if measure == "value" else "tonnes"
        rows_ = _rows_of(seg)
        if kind == "zone" and _zone_misaligned(rows_, gloss):
            continue
        for label, vals in rows_:
            lab = re.sub(r"\s+", " ", label).strip()
            total = _fold(lab).startswith(("total", "ensemble"))
            code = ""
            if kind in ("sitc1", "sitc2") and not total:
                m = re.match(r"^(\d{1,2})\s+(.*)$", lab)
                if not m:
                    continue
                code, lab = m.group(1), m.group(2).strip()
                if (kind == "sitc2") != (len(code) == 2):
                    continue
            ptype, partner = "world", None
            if kind in ("country", "zone") and not total:
                m = re.match(r"^([A-Z]{2})\s+(.*)$", lab) if kind == "country" else None
                if kind == "country":
                    if not m:
                        continue
                    code, partner = m.group(1), m.group(2).strip()
                    ptype = "group" if code in _NOT_COUNTRY or "non " in _fold(partner) else "country"
                else:
                    if not lab.strip():
                        continue                 # no label (a page number or an orphaned row): dropped
                    partner, ptype = lab, "group"
            for p, t in vals.items():
                v = to_number(t, decimal=",")
                if v is None:
                    continue
                if kind in ("sitc1", "sitc2"):
                    out.append(row(tradeflow=flow, period=p, frequency="quarterly", value=v, unit=unit,
                                   unit_multiplier=mult, measure=measure,
                                   commodity=None if total else lab,
                                   commodity_classification="" if total else cls,
                                   commodity_code_nso="" if total else code,
                                   price_basis=basis, series_code=sc))
                else:
                    out.append(row(tradeflow=flow, period=p, frequency="quarterly", value=v, unit=unit,
                                   unit_multiplier=mult, measure=measure, partner=partner,
                                   partner_type=ptype, price_basis=basis, series_code=sc))
                    if kind == "country":
                        out[-1]["_pcode"] = code      # checked against the other issues in parse()
        for r in out[n_out:]:
            r["_seg"] = n_seg
    # A TABLE'S TOTAL AGAINST TABLEAU 1. Every commodity / partner table prints its total;
    # when that total is not Tableau 1's figure for the same flow, measure and quarter, the
    # table was misread (2022-T4 issue, Tableau 24: a total printed as a truncated "1 057"
    # against 1 057 897,7 t) and all its rows are dropped. (Repaired 2026-11-12.)
    head = {(r["tradeflow"], r["measure"], r["period"]): r["value"] for r in out
            if r["series_code"] == "Tableau 1"}
    badseg = set()
    for r in out:
        if "_seg" in r and r["partner"] == "All partners" and r["commodity"] == "All products":
            h = head.get((r["tradeflow"], r["measure"], r["period"]))
            if h is not None and abs(h - r["value"]) > 0.15:
                badseg.add(r["_seg"])
    out = [r for r in out if r.get("_seg") not in badseg]
    for r in out:
        r.pop("_seg", None)
    # Cells for a period after the issue's own latest quarter are table errors (the
    # 2026 T2 issue prints a 2026 "4eme Trimestre" balance) -- dropped.
    qs = [r["period"] for r in out if r["frequency"] == "quarterly" and "Tableau 8" not in r["series_code"]]
    last = max(qs) if qs else None
    if last:
        ly, lq = int(last[:4]), int(last[-1])
        def after(r):
            p, f = r["period"], r["frequency"]
            if f == "quarterly":
                return p > last
            if f == "monthly":
                return (int(p[:4]), (int(p[5:]) - 1) // 3 + 1) > (ly, lq)
            return int(p) > ly
        out = [r for r in out if not after(r)]
    # A "par periode" balance that is not exports - imports of the same table and period
    # (within rounding) is a sign misprint (2026 T2 issue: 2024 4eme Trimestre "284,5" for
    # exports 205,5 - imports 490,0): dropped, never corrected.
    per = {}
    for r in out:
        if r["series_code"].startswith("Tableau 8") and r["unit_multiplier"] == 1e9:
            per[(r["tradeflow"], r["frequency"], r["period"])] = r["value"]
    def bad(r):
        if r["tradeflow"] != "balance" or r["unit_multiplier"] != 1e9:
            return False
        e = per.get(("export", r["frequency"], r["period"]))
        i = per.get(("import", r["frequency"], r["period"]))
        return e is not None and i is not None and abs(e - i - r["value"]) > 0.25
    return [r for r in out if not bad(r)]


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = []
    for p in [path] + list(extras or []):
        if not p.lower().endswith(".pdf"):
            continue
        rs = _parse_issue(p)
        if not rs:
            continue
        df = pd.DataFrame(rs)
        q = df.loc[df["frequency"] == "quarterly", "period"]
        df["_vintage"] = q.max() if len(q) else ""
        df["_mult"] = -df["unit_multiplier"]
        frames.append(df)
    for i, f in enumerate(frames):
        f["_issue"] = i
    df = pd.concat(frames, ignore_index=True)
    # CODES AGAINST NAMES. A country table whose ISO-code column is shifted against its
    # name column (2021 Q1 issue, Tableaux 71-74: "BD Belgique", "BE Burkina Faso", "BF
    # Bulgarie" ...) cannot say whose figures it prints, so it is dropped: a table is
    # kept only when nearly every code carries the name that code carries in most
    # issues. (Repaired 2026-11-12.)
    if "_pcode" in df.columns:
        c = df["_pcode"].notna()
        nk = df.loc[c, "partner"].map(_key)
        major = nk.groupby(df.loc[c, "_pcode"]).agg(lambda s: s.value_counts().index[0])
        off = nk != df.loc[c, "_pcode"].map(major)
        share = off.groupby([df.loc[c, "_issue"], df.loc[c, "series_code"]]).mean()
        bad = set(share[share > 0.05].index)
        drop = c & pd.Series([(i, s) in bad for i, s in zip(df["_issue"], df["series_code"])], index=df.index)
        df = df[~drop].drop(columns=["_pcode"])
    df = df.drop(columns=["_issue"])
    key = ["tradeflow", "commodity", "commodity_classification", "commodity_code_nso", "partner",
           "partner_type", "measure", "period", "frequency", "unit", "price_basis"]
    df = df.sort_values(["_vintage", "_mult"], kind="stable").drop_duplicates(key, keep="last")
    return df.drop(columns=["_vintage", "_mult"]).reset_index(drop=True)
