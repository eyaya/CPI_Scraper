"""Cameroon -- INS "Note d'analyse de l'Indice des Prix à la Production
Industrielle (IPPI)", quarterly, base 2016 = 100, NAEMA rév.1 sections B-E.

One descriptor reads EVERY retained note (the newest as the primary file, the
rest as extras) and keeps, for each branch x quarter x measure, the value
from the NEWEST note -- INS revises back quarters (T1-19 is 115,0 in the
2019 note, 111 in the 2023 history table).

TWO TABLE LAYOUTS, both text (no OCR):
  * "INDICE DES PRIX DE PRODUCTION DANS L'INDUSTRIE BASE 100 EN 2016" -- 20
    branch rows (the same list, the same order, in every note since 2019) x
    8-10 quarter columns + "Glissement annuel" [+ "trimestriel"]. Read by
    WORD POSITION: each value column is matched to the header label above it.
    INS's header is unreliable and is never trusted alone:
      - it repeats a label (2024-26 notes print "T3-24 T3-24": the second is
        T4-24) -- a repeated label is resolved ONLY when its neighbours prove
        the one quarter missing between them (T3-24, ?, T1-25 -> T4-24);
      - it omits labels (the 1T2026 note: 10 value columns under 8 labels; the
        9th repeats T4-25, the 10th is T1-26) -- an unlabelled LAST column is
        the note's own quarter only if the printed glissements of ENSEMBLE
        INDUSTRIE agree with it; any other unlabelled column is dropped.
    Which glissement is annual and which quarterly is decided by ENSEMBLE
    INDUSTRIE's arithmetic, not by the header (the 2019 note prints annual
    first under a header reading "Trimestriel ... Annuel").
  * "TABLEAU DES INDICES" (2T-2023 and 3T-2023 notes) -- quarters as rows
    (2019 Q1 ...) x 17 abbreviated branch columns (EXTRACTIVES ... ENSEMBLE),
    filed under the full branch names of the other layout (same branches,
    same order; the header must match exactly).

THE 2019 NOTE'S CAPTION says "BASE 100 EN 2006"; its own methodology (p. 9:
"avec 2016 comme année de base", "la moyenne de l'année de base (2016)") and
every later note say 2016 -- filed as 2016 = 100.

NOT READ: the 2020-2022 notes (IPPI-2T-2020, IPPI-3T-2020, IPPI-2020-1111,
1T-2021, 2T/4T-2022, 1T-2023, IPPI-2022-annuelle): their table page is
ROTATED 90 degrees and extract_text() returns the cells reversed and
unordered. Every quarter they cover is in the 2023 history tables and later
notes; only the annual averages 2017-2022 of IPPI-2022-annuelle are lost.
"""
from __future__ import annotations

import os
import re
import unicodedata

import pandas as pd
import pdfplumber

from . import _common as C

INDEX_NAME = "Indice des prix à la production industrielle (IPPI)"
BASE = "2016=100"

BRANCHES = [  # (label as INS prints it in 2026, keyword that must appear in the row label)
    ("INDUSTRIES EXTRACTIVES", "EXTRACTIVES"),
    ("EXTRACTION D'HYDROCARBURES", "HYDROCARBURES"),
    ("INDUSTRIES MANUFACTURIÈRES", "MANUFACTURI"),
    ("AGRO ALIMENTAIRE", "ALIMENTAIRE"),
    ("INDUSTRIES TEXTILES", "TEXTILES"),
    ("TRAVAIL DU CUIR ; FABRICATION D'ARTICLES DE VOYAGE ET DE CHAUSSURES", "CUIR"),
    ("TRAVAIL DU BOIS ET FABRICATION D'ARTICLES EN BOIS HORS MEUBLES", "BOIS"),
    ("FABRICATION DU PAPIER ET DU CARTON, IMPRIMERIE", "PAPIER"),
    ("RAFFINAGE PÉTROLIER, COKEFACTION", "RAFFINAGE"),
    ("FABRICATION DE PRODUITS CHIMIQUES, PHARMACEUTIQUES ET PLASTIQUES", "CHIMIQUES"),
    ("FABRICATION DE MATERIAUX MINERAUX", "MINERAUX"),
    ("MÉTALLURGIE ET FABRICATION D'OUVRAGES EN MÉTAUX", "METALLURGIE"),
    ("FABRICATION DE MACHINES ET D'EQUIPEMENTS N.C.A.", "MACHINES"),
    ("CONSTRUCTION DE VÉHICULES AUTOMOBILES ET D'AUTRES MATERIELS DE TRANSPORT", "VEHICULES"),
    ("FABRICATION DE MEUBLES ET AUTRES INDUSTRIES MANUFACTURIERES NCA", "MEUBLES"),
    # the group reads "[INDUSTRIES DE] PRODUCTION ET DE DISTRIBUTION ...", its one
    # item "PRODUCTION ET DISTRIBUTION D'ÉLECTRICITÉ ET DE GAZ"
    ("INDUSTRIES DE PRODUCTION ET DE DISTRIBUTION D'ELECTRICITE, DE GAZ", "PRODUCTION ET DE"),
    ("PRODUCTION ET DISTRIBUTION D'ÉLECTRICITÉ ET DE GAZ", "PRODUCTION ET DISTRIBUTION"),
    ("INDUSTRIES ENVIRONEMENTALES", "ENVIRON"),
    ("CAPTAGE, TRAITEMENT ET DISTRIBUTION D'EAU, COLLECTE, TRAITEMENT ET ELIMINATION DES DECHETS ; RECUPERATION", "CAPTAGE"),
    ("ENSEMBLE INDUSTRIE", "ENSEMBLE"),
]
TOTAL = "ENSEMBLE INDUSTRIE"
# "TABLEAU DES INDICES" columns -> BRANCHES index.
HIST_HEADER = ("EXTRACTIVES MANUFACTURE ALIMENTAIRE TEXTILES CUIR BOIS IMPRIMERIE RAFFINAGE CHIMIQUES "
               "MINERAUX METALLURGIE MACHINES VEHICULES MEUBLES ELECTRICITE ENVIRONEMENTALES ENSEMBLE")
HIST_COLS = [0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 19]

_ORD = {"premier": 1, "1er": 1, "deuxieme": 2, "2e": 2, "2eme": 2, "troisieme": 3, "3e": 3,
        "3eme": 3, "quatrieme": 4, "4e": 4, "4eme": 4}
_REF = re.compile(r"(premier|1er|deuxieme|2e|2eme|troisieme|3e|3eme|quatrieme|4e|4eme)\s+trimestre\s+(20\d\d)")
_TLAB = re.compile(r"^T([1-4])-(\d\d)$")
_NUM = re.compile(r"^-?\d+(?:[.,]\d+)?\*?%?$")


def _fold(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().upper()


def _qi(period: str) -> int:
    return int(period[:4]) * 4 + int(period[-1]) - 1


def _qp(i: int) -> str:
    return f"{i // 4}-Q{i % 4 + 1}"


def _ref_quarter(pdf) -> str | None:
    t = " ".join((pdf.pages[i].extract_text() or "") for i in range(min(2, len(pdf.pages))))
    m = _REF.search(_fold(t).lower().replace("\n", " "))
    return f"{m.group(2)}-Q{_ORD[m.group(1)]}" if m else None


def _num(tok: str) -> float | None:
    return C.to_number(tok.rstrip("%").rstrip("*"), decimal=",")


def _lines(words):
    """Words grouped into lines: a word within 2.5 pt of a line's first word joins it
    (rounding tops into fixed buckets split rows that straddle a bucket edge)."""
    out = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if out and w["top"] - out[-1][0]["top"] <= 2.5:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(l, key=lambda w: w["x0"]) for l in out]


def _changes(idx_last, idx_prev_q, idx_prev_y, printed):
    """Which printed change is annual / quarterly, proved on ENSEMBLE INDUSTRIE."""
    yoy = (idx_last / idx_prev_y - 1) * 100 if idx_prev_y else None
    qoq = (idx_last / idx_prev_q - 1) * 100 if idx_prev_q else None
    out = {}
    for j, v in enumerate(printed):
        fy = yoy is not None and abs(v - yoy) <= 0.15
        fq = qoq is not None and abs(v - qoq) <= 0.15
        if fy and not fq:
            out[j] = "inflation_yoy"
        elif fq and not fy:
            out[j] = "inflation_qoq"
    if len(set(out.values())) != len(out):
        return {}
    return out


def _parse_window(page, ref: str) -> list[dict]:
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
    cap = [w for w in words if w["text"].upper() == "BASE"]
    if not cap:
        return []
    labels = [w for w in words if _TLAB.match(w["text"])]
    gl = [w["x0"] for w in words if _fold(w["text"]).startswith("GLISSEMENT")]
    head_bottom = max(w["bottom"] for w in labels + [w for w in words if _fold(w["text"]).startswith("GLISSEMENT")])
    body = [w for w in words if w["top"] > head_bottom + 2]
    # Build rows: accumulate lines until a full row of numbers is reached, in BRANCHES order.
    lines = _lines(body)
    # Column positions from the fullest numeric line (ENSEMBLE's label can sit on its own line).
    nums_total = max(([w for w in l if _NUM.match(w["text"])] for l in lines), key=len)
    xcut = (min(gl) - 15) if gl else 1e9
    idx_x = [w["x0"] for w in nums_total if not w["text"].endswith("%") and w["x0"] < xcut]
    n_idx, n_all = len(idx_x), len(nums_total)
    # Column -> period, from the header label above each column.
    lab = []
    for x in idx_x:
        near = [w for w in labels if abs(w["x0"] - x) < 14]
        m = _TLAB.match(near[0]["text"]) if near else None
        lab.append(_qi(f"20{m.group(2)}-Q{m.group(1)}") if m else None)
    for i in range(1, len(lab) - 1):     # a repeated label proved by its neighbours
        if lab[i] is not None and lab[i] == lab[i - 1] and lab[i + 1] is not None and lab[i + 1] == lab[i - 1] + 2:
            lab[i] = lab[i - 1] + 1
    seen = [l for l in lab if l is not None]
    orig = list(lab)
    if len(seen) != len(set(seen)):      # a duplicate that could not be resolved: drop both
        dup = {l for l in seen if seen.count(l) > 1}
        lab = [None if l in dup else l for l in lab]
    rq = _qi(ref)
    rows_out = []
    cur_text, cur_nums, k = [], [], 0
    parsed = []
    for line in lines:
        for w in line:
            if _NUM.match(w["text"]):
                cur_nums.append(w)
            else:
                cur_text.append(w["text"])
        if len(cur_nums) >= n_all:
            if len(cur_nums) > n_all:
                raise ValueError(f"row {k + 1}: {len(cur_nums)} numbers, expected {n_all}")
            # The next branch IN ORDER whose keyword the row carries (a note may omit
            # a branch -- 4T-2023 has no separate hydrocarbons row).
            label = _fold(" ".join(cur_text))
            hit = next((j for j in range(k, len(BRANCHES)) if BRANCHES[j][1] in label), None)
            if hit is None:
                raise ValueError(f"row {' '.join(cur_text)!r} matches no remaining branch")
            # Values by POSITION: a wrapped row can print its last value on the label line.
            parsed.append((BRANCHES[hit][0], sorted(cur_nums, key=lambda w: w["x0"])))
            k = hit + 1
            cur_text, cur_nums = [], []
            if BRANCHES[hit][0] == TOTAL:
                break
    if not parsed or parsed[-1][0] != TOTAL or len(parsed) < 15:
        raise ValueError(f"{len(parsed)} branch rows read, ending {parsed[-1][0] if parsed else None!r}")
    # The unlabelled last column is the note's quarter only if ENSEMBLE's glissements say so.
    tot = dict(parsed)[TOTAL]
    tvals = [_num(w["text"]) for w in tot]
    chg_printed = tvals[n_idx:]
    if lab[-1] is None and rq not in lab:
        trial = lab[:-1] + [rq]
        pos = {q: j for j, q in enumerate(trial) if q is not None}
        cm = _changes(tvals[n_idx - 1], tvals[pos[rq - 1]] if rq - 1 in pos else None,
                      tvals[pos[rq - 4]] if rq - 4 in pos else None, chg_printed)
        if cm:
            lab = trial
            # A label dropped as a duplicate of the (mis-labelled) last column is unique again.
            for i in range(len(lab) - 1):
                if lab[i] is None and orig[i] is not None and orig[i] not in lab:
                    lab[i] = orig[i]
    pos = {q: j for j, q in enumerate(lab) if q is not None}
    if lab[-1] != rq:
        raise ValueError(f"last column is {lab[-1]}, the note's quarter is {ref}")
    if sorted(pos) != list(pos):
        raise ValueError(f"quarter columns out of order: {lab}")
    cmap = _changes(tvals[pos[rq]], tvals[pos[rq - 1]] if rq - 1 in pos else None,
                    tvals[pos[rq - 4]] if rq - 4 in pos else None, chg_printed)
    for name, ws in parsed:
        vals = [_num(w["text"]) for w in ws]
        for j, q in enumerate(lab):
            if q is not None and vals[j] is not None:
                rows_out.append(C.row(index_name=INDEX_NAME, industry=name, period=_qp(q),
                                      frequency="quarterly", measure="index", value=vals[j],
                                      base_period=BASE))
        for j, meas in cmap.items():
            v = vals[n_idx + j]
            if v is not None:
                rows_out.append(C.row(index_name=INDEX_NAME, industry=name, period=ref,
                                      frequency="quarterly", measure=meas, value=v))
    return rows_out


def _parse_history(text: str, ref: str) -> list[dict]:
    lines = text.splitlines()
    try:
        h = next(i for i, l in enumerate(lines) if l.startswith("Trimestre "))
    except StopIteration:
        return []
    if lines[h][len("Trimestre "):].strip() != HIST_HEADER:
        raise ValueError(f"history header changed: {lines[h]!r}")
    out, last = [], None
    for l in lines[h + 1:]:
        m = re.match(r"^((?:19|20)\d\d) Q([1-4]) (.*)$", l)
        if not m:
            continue
        vals = [_num(t) for t in m.group(3).split()]
        if len(vals) != len(HIST_COLS):
            raise ValueError(f"history row {l!r}: {len(vals)} values")
        q = f"{m.group(1)}-Q{m.group(2)}"
        last = (q, vals)
        for col, v in zip(HIST_COLS, vals):
            if v is not None:
                out.append(C.row(index_name=INDEX_NAME, industry=BRANCHES[col][0], period=q,
                                 frequency="quarterly", measure="index", value=v, base_period=BASE))
    if last is None or last[0] != ref:
        raise ValueError(f"history ends at {last and last[0]}, the note's quarter is {ref}")
    # Glissement lines: "annuel" then "trimestriel", for the last quarter -- checked on ENSEMBLE.
    blob = " ".join(lines[h:])
    ga = re.search(r"Glissement annuel ((?:-?\d+,\d%\s*){17})", blob)
    gt = re.search(r"Glissement trimestriel ((?:-?\d+,\d%\s*){17})", blob)
    byq = {}
    for r in out:
        if r["industry"] == TOTAL:
            byq[r["period"]] = r["value"]
    rq = _qi(ref)
    for mm, meas, lag in ((ga, "inflation_yoy", 4), (gt, "inflation_qoq", 1)):
        if not mm:
            continue
        vals = [_num(t) for t in mm.group(1).split()]
        prev = byq.get(_qp(rq - lag))
        if prev is None or abs((byq[ref] / prev - 1) * 100 - vals[-1]) > 0.15:
            continue                     # not proved on ENSEMBLE: not taken
        for col, v in zip(HIST_COLS, vals):
            out.append(C.row(index_name=INDEX_NAME, industry=BRANCHES[col][0], period=ref,
                             frequency="quarterly", measure=meas, value=v))
    return out


def parse_note(path: str) -> tuple[str | None, list[dict]]:
    with pdfplumber.open(path) as pdf:
        ref = _ref_quarter(pdf)
        if ref is None:
            return None, []
        for page in pdf.pages:
            t = page.extract_text() or ""
            if "TABLEAU DES INDICES" in t:
                return ref, _parse_history(t, ref)
            if re.search(r"BASE 100 EN 20[01]6", t) and "ENSEMBLE INDUSTRIE" in t:
                return ref, _parse_window(page, ref)
    return ref, []


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = [path] + list(extras or [])
    best: dict[tuple, tuple] = {}
    used = 0
    for f in files:
        if not os.path.exists(f):
            continue
        ref, rows = parse_note(f)
        if not rows:
            continue
        used += 1
        for r in rows:
            key = (r["industry"], r["period"], r["measure"])
            if key not in best or _qi(ref) > best[key][0]:
                best[key] = (_qi(ref), r)
    if not best:
        raise ValueError("no IPPI table read")
    return pd.DataFrame([r for _, r in best.values()])


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse = carry_base(parse)
