"""Congo -- INS "Indices des prix à la production industrielle" (IPPI), quarterly
note, base 2019 = 100, NAEMA divisions 05-38.

Each note's annex carries two tables, both read here:
  Tableau 1 -- by TYPE of industry (Indice Global IPPI + 10 groups, printed
               with NAEMA division spans "05-09" in 2022),
  Tableau 2 -- by BRANCH (NAEMA division: 06 hydrocarbures ... 38 déchets).
Columns: Pondérations | Base 2019=100 | the quarters (2 to 6) | change on the
previous quarter | change on the same quarter a year earlier.

READ BY WORD POSITION. Wrapped labels push a row's middle values onto the
line above ("Industries pétrolières, chimiques et caoutchouc," / "83,6 100,2
102,1" / "plastiques 659,6 100,0 89,7 2,0 2,1"), so a row's numbers are
gathered until the row is complete and ordered by x. Rows are matched IN
ORDER to the branch list by keyword (a note may omit a branch: the 2020
notes have no "32 AUTRES INDUSTRIES MANUFACTURIERES"); labels are filed
under one canonical spelling (the 2022 note's) with its NAEMA code, so a
branch is one series across notes. "Indice Global IPPI" is taken from
Tableau 1 only (Tableau 2 repeats it).

NOT TAKEN: the "Base 2019=100" column (100,0 everywhere -- the base, not a
period). The Pondérations are printed per ten thousand (sum 10000,0) and are
kept on that scale (unit per_ten_thousand, filed under the base year).
The y/y header of the T2-2020 Tableau 1 reads "T2-2020 / T1-2019" (Tableau 2
and the text: "En variation annuelle ... 43,1") -- filed as y/y. The q/q
change is checked on Indice Global IPPI against the indices; a note whose
global q/q does not match is not given changes.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd
import pdfplumber

from . import _common as C

INDEX_NAME = "Indice des prix à la production industrielle (IPPI)"
BASE = "2019=100"

T1 = [("Indice Global IPPI", "", "GLOBAL"),
      ("Industries extractives", "05-09", "EXTRACTIVES"),
      ("Industries agro-alimentaires et tabac", "10-12", "AGRO"),
      ("Industries du bois", "16", "BOIS"),
      ("Industries du papier, carton et édition, imprimerie", "17-18", "PAPIER"),
      ("Industries pétrolières, chimiques et caoutchouc, plastiques", "19-22", "PETROLIERES"),
      ("Industrie de la céramique et des matériaux de construction", "23", "CERAMIQUE"),
      ("Industries métalliques", "24-30", "METALLIQUES"),
      ("Autres industries manufacturières", "31-32", "AUTRES INDUSTRIES"),
      ("Industries de production de l’énergie", "35-36", "ENERGIE"),
      ("Industries environnementales", "38", "ENVIRONNEMENTALES")]
T2 = [("Indice Global IPPI", "", "GLOBAL"),
      ("EXTRACTION D'HYDROCARBURES", "06", "HYDROCARBURES"),
      ("EXTRACTION DE MINERAIS METALLIQUES", "07", "MINERAIS"),
      ("AUTRES ACTIVITES EXTRACTIVES", "08", "AUTRES ACTIVITES"),
      ("FABRICATION DE PRODUITS ALIMENTAIRES", "10", "ALIMENTAIRES"),
      ("FABRICATION DE BOISSONS", "11", "BOISSONS"),
      ("FABRICATION DE PRODUITS A BASE DE TABAC", "12", "TABAC"),
      ("TRAVAIL DU BOIS ET FABRICATION D'ARTICLES EN BOIS (à l'exception des meubles)", "16", "BOIS"),
      ("FABRICATION DE PAPIER, CARTONS ET D’ARTICLES EN PAPIER OU EN CARTON", "17", "PAPIER"),
      ("IMPRIMERIE ET REPRODUCTION D'ENREGISTREMENTS", "18", "IMPRIMERIE"),
      ("PRODUITS DU RAFFINAGE ET DE LA COKÉFACTION", "19", "RAFFINAGE"),
      ("FABRICATION DE PRODUITS CHIMIQUES", "20", "CHIMIQUES"),
      ("TRAVAIL DU CAOUTCHOUC ET DU PLASTIQUE", "22", "CAOUTCHOUC"),
      ("FABRICATION DE MATERIAUX MINERAUX", "23", "MATERIAUX MINERAUX"),
      ("METALLURGIE", "24", "METALLURGIE"),
      ("FABRICATION D'OUVRAGES EN METAUX", "25", "OUVRAGES"),
      ("FABRICATION DES MEUBLES ET MATELAS", "31", "MEUBLES"),
      ("AUTRES INDUSTRIES MANUFACTURIERES", "32", "AUTRES INDUSTRIES"),
      ("PRODUCTION ET DISTRIBUTION D'ELECTRICITE, DE GAZ", "35", "ELECTRICITE"),
      ("CAPTAGE, TRAITEMENT ET DISTRIBUTION D'EAU", "36", "CAPTAGE"),
      ("COLLECTE, TRAITEMENT ET ELIMINATION DES DECHETS; RECUPERATION", "38", "DECHETS")]

_Q = re.compile(r"^T([1-4])-(20\d\d)/?$")
_NUM = re.compile(r"^(?:-?\d[\d ]*(?:,\d+)?|-)$")


def _fold(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().upper()


def _lines(words):
    out = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if out and w["top"] - out[-1][0]["top"] <= 2.5:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(l, key=lambda w: w["x0"]) for l in out]


def _qi(y: int, q: int) -> int:
    return y * 4 + q - 1


def _table(words, canon, take_global: bool):
    """One annex table (its words only) -> rows."""
    hdr = next((w for w in words if _fold(w["text"]).startswith("PONDERATION")), None)
    if hdr is None:
        raise ValueError("no 'Pondérations' header")
    xnum = hdr["x0"] - 12
    # The data start at the first "Indice Global IPPI" row; everything above is header.
    g = min((w for w in words if _fold(w["text"]) == "GLOBAL"), key=lambda w: w["top"])
    head = [w for w in words if w["top"] < g["top"] - 2]
    qtok = [w for w in head if _Q.match(w["text"]) and abs(w["top"] - hdr["top"]) < 3]
    # A label stacked over two lines ("T1-" above "2021", 2022 Tableau 2) is one label;
    # only LEFT of the one-line labels (the change headers on the right stack too).
    first_x = min((v["x0"] for v in qtok), default=1e9)
    for w in head:
        if re.fullmatch(r"T[1-4]-", w["text"]):
            below = [v for v in head if re.fullmatch(r"20\d\d", v["text"])
                     and abs(v["x0"] - w["x0"]) < 4 and 0 < v["top"] - w["top"] < 25]
            if below and abs(w["top"] - hdr["top"]) < 25 and w["x0"] < first_x:
                qtok.append({**w, "text": w["text"] + min(below, key=lambda v: v["top"])["text"]})
    qtok = sorted(qtok, key=lambda w: w["x0"])
    body = [w for w in words if w["top"] >= g["top"] - 2]
    lines = _lines(body)
    ncol = max(len([w for w in l if w["x0"] >= xnum and _NUM.match(w["text"])]) for l in lines)
    nq = ncol - 4                                  # weight, base, quarters..., q/q, y/y
    if nq < 1 or len(qtok) < nq:
        raise ValueError(f"{ncol} numeric columns, {len(qtok)} quarter labels")
    quarters = [_qi(int(_Q.match(w["text"]).group(2)), int(_Q.match(w["text"]).group(1))) for w in qtok[:nq]]
    if quarters != list(range(quarters[0], quarters[0] + nq)):
        raise ValueError(f"quarter labels not consecutive: {[w['text'] for w in qtok[:nq]]}")
    rows, k, text, nums = [], 0, [], []
    for line in lines:
        for w in line:
            if w["x0"] >= xnum and _NUM.match(w["text"]):
                nums.append(w)
            else:
                text.append(w["text"])
        if len(nums) >= ncol:
            if len(nums) > ncol:
                raise ValueError(f"row {' '.join(text)!r}: {len(nums)} numbers, expected {ncol}")
            lab = _fold(" ".join(text))
            hit = next((j for j in range(k, len(canon)) if canon[j][2] in lab), None)
            if hit is None:
                raise ValueError(f"row {' '.join(text)!r} matches no remaining branch")
            vals = [C.to_number(w["text"].replace(" ", ""), decimal=",")
                    for w in sorted(nums, key=lambda w: w["x0"])]
            rows.append((canon[hit], vals))
            k, text, nums = hit + 1, [], []
            if k == len(canon):
                break
    if not rows or rows[0][0][2] != "GLOBAL":
        raise ValueError("table does not start with Indice Global IPPI")
    return quarters, [(c, v) for c, v in rows if take_global or c[2] != "GLOBAL"]


def parse_note(path: str) -> list[dict]:
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if "BASE 100 EN 2019" not in t or "Tableau" not in t:
                continue
            words = page.extract_words()
            caps = sorted([w for w in words if w["text"] == "Tableau"], key=lambda w: w["top"])
            for i, cap in enumerate(caps):
                bottom = caps[i + 1]["top"] - 1 if i + 1 < len(caps) else page.height
                nxt = [w for w in words if w["top"] > cap["bottom"] and w["top"] < bottom]
                which = next((ww["text"] for ww in words if abs(ww["top"] - cap["top"]) < 2 and ww["x0"] > cap["x0"]), "")
                canon = T1 if which.startswith("1") else T2
                quarters, rows = _table(nxt, canon, take_global=(canon is T1))
                out.append((quarters, rows))
    if not out:
        return []
    recs = []
    for quarters, rows in out:
        nq = len(quarters)
        last = quarters[-1]
        glob = next((v for c, v in rows if c[2] == "GLOBAL"), None)
        ok_qoq = True
        if glob is not None and nq >= 2 and glob[2 + nq - 2] and glob[2 + nq - 1]:
            implied = (glob[2 + nq - 1] / glob[2 + nq - 2] - 1) * 100
            ok_qoq = abs(implied - glob[2 + nq]) <= 0.15
        for (name, code, _kw), vals in rows:
            if vals[0] is not None:               # weight, per ten thousand as printed
                recs.append(C.row(index_name=INDEX_NAME, industry=name, industry_code_nso=code,
                                  period=re.search(r"\d{4}", BASE).group(0), frequency="annual",
                                  measure="weight", value=vals[0], unit="per_ten_thousand",
                                  base_period=BASE))
            for j, q in enumerate(quarters):
                v = vals[2 + j]
                if v is not None:
                    recs.append(C.row(index_name=INDEX_NAME, industry=name, industry_code_nso=code,
                                      period=f"{q // 4}-Q{q % 4 + 1}", frequency="quarterly",
                                      measure="index", value=v, base_period=BASE))
            if ok_qoq:
                for v, meas in ((vals[2 + nq], "inflation_qoq"), (vals[3 + nq], "inflation_yoy")):
                    if v is not None:
                        recs.append(C.row(index_name=INDEX_NAME, industry=name, industry_code_nso=code,
                                          period=f"{last // 4}-Q{last % 4 + 1}", frequency="quarterly",
                                          measure=meas, value=v, base_period=BASE))
    return recs, max(q for qs, _ in out for q in qs)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    best = {}
    for f in [path] + list(extras or []):
        got = parse_note(f)
        if not got:
            continue
        recs, ref = got
        for r in recs:
            key = (r["industry"], r["period"], r["measure"])
            if key not in best or ref > best[key][0]:
                best[key] = (ref, r)
    if not best:
        raise ValueError("no IPPI annex table read")
    return pd.DataFrame([r for _, r in best.values()])
