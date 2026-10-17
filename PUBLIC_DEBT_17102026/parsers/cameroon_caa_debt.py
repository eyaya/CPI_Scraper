"""Cameroon — Caisse Autonome d'Amortissement (CAA), "Conjoncture Mensuelle de
la Dette Publique du Cameroun", Tableau 1 "Encours de la dette du secteur
public".

PUBLISHER: the CAA, Cameroon's public-debt management agency under the
Ministry of Finance (with the Comité National de la Dette Publique, CNDP). An
official national compiler, accepted under the 2026-10-08 source policy.

WHAT IS READ. Tableau 1 is the headline debt table: END-OF-MONTH
columns (eight in the 2026 issues; five or nine in others) -- the same month a year earlier, the previous December, and the six
months of the current half -- for 29 rows, in MILLIARDS DE FCFA as printed.
Each issue therefore carries the year-earlier month too, and merge-on-write
accumulates every month any retained issue prints. The newest issue wins on
revisions (the columns are flagged provisoire / semi-définitif / définitif).

COVERAGE IS PER ROW -- the table spans several debt perimeters, and a total is
only meaningful with its perimeter:

  * rows 1-3   "Administration centrale" (direct central-government debt:
               external by creditor class, domestic by instrument, arrears over
               3 months, floating debt)
  * row  4     "Entreprises et établissements publics" (SOE debt, excluding
               debt on-lent by the State, and -- the CAA notes -- excluding
               SONATREL/SOCADEL, still being valued)
  * row  5     "Collectivités territoriales décentralisées"
  * row  6     "Passifs conditionnels explicites de l'Etat" (guarantees, PPPs)
  * row  7     "Secteur public (non consolidé, hors passifs conditionnels)",
               the CAA's total public debt = 3 + 4 + 5

THE NUMBERS ARE LETTER-SPACED in the text layer ("1 3 388", "5 0 4 9" for
13 388 and 50 / 49), so line text cannot be split into cells. Rows are rebuilt
from WORD POSITIONS: inside a cell the gap between digit groups is at most a
few points, between cells it is over twenty, so a row splits on gaps above 10
pt and must yield exactly eight cells. Labels are STATED (`_ROWS`), as
printed, and checked word by word against the table's own label text in order.

CHECKS (every run, every column, +-2 for rounding of printed milliards):
external = multilateral + bilateral + commercial; central government direct =
external + domestic; SOE debt = its three components; total = 3 + 4 + 5.

"-" (nil) and "N/D" (not available -- the CTDs' direct external debt) are
missing cells, never zero.

PRINTED LABEL KEPT: "Collectivitées" (sic). The two "dont appuis budgétaires"
rows are qualified by their parent (multilateral / bilateral) so the two
series stay distinct.

CROSS-CHECK (juin 2026): total public debt 15 607; central government 14 659;
external 9 453 (multilateral 5 540); domestic 5 206; SOE 923; PPP 4 895.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_CAPTION = re.compile(r"Tableau 1 : Encours de la dette du secteur public")
_MONTHS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
           "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
           "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
           "decembre": 12}

_CG = "Administration centrale"
_SOE = "Entreprises et établissements publics"
_CTD = "Collectivités territoriales décentralisées"
_CL = "Passifs conditionnels explicites de l'Etat"
_PS = "Secteur public (non consolidé, hors passifs conditionnels)"

# (component as printed, coverage, words that must appear in the label text)
_ROWS = [
    ("1. Dette extérieure", _CG, "1. Dette extérieure"),
    ("Multilatérale", _CG, "Multilatérale"),
    ("Multilatérale: dont appuis budgétaires", _CG, "dont appuis budgétaires"),
    ("Bilatérale", _CG, "Bilatérale"),
    ("Bilatérale: dont appuis budgétaires", _CG, "dont appuis budgétaires"),
    ("Commerciale", _CG, "Commerciale"),
    ("2. Dette intérieure", _CG, "2. Dette intérieure"),
    ("2.1. Dette intérieure (hors Restes à Payer et dette flottante)", _CG,
     "2.1. Dette intérieure (hors Restes à Payer et dette flottante)"),
    ("Titres publics", _CG, "Titres publics"),
    ("Emprunt consolidé BEAC", _CG, "Emprunt consolidé BEAC"),
    ("Allocation de DTS (FMI-BEAC)", _CG, "Allocation de DTS"),
    ("Dette structurée", _CG, "Dette structurée"),
    ("Dette non structurée", _CG, "Dette non structurée"),
    ("2.2. Restes à payer de plus de 3 mois", _CG, "2.2. Restes à payer"),
    ("2.4. Dette flottante de l'Administration Centrale", _CG,
     "Dette flottante de l'Administration"),     # numbered 2.3. before 2026
    ("3. Dette Directe de l'Administration Centrale", _CG,
     "3. Dette Directe de l'Administration Centrale"),
    ("dont appui budgétaire total", _CG, "dont appui budgétaire total"),
    ("4. Dette des Entreprises et Etablissements publics", _SOE,
     "4. Dette des Entreprises"),
    ("Dette extérieure directe des Entreprises et Etablissements publics", _SOE,
     "Dette extérieure directe des"),
    ("Dette intérieure auprès du système bancaire", _SOE,
     "Dette intérieure auprès du système bancaire"),
    ("Dette flottante des Entreprises et Etablissements publics", _SOE,
     "Dette flottante des Entreprises"),
    ("5. Dette des Collectivitées Territoriales Décentralisées", _CTD,
     "5. Dette des Collectivitées"),
    ("Dette extérieure directe des CTD's", _CTD, "Dette extérieure directe des CTD's"),
    ("Dette intérieure directe des CTD's", _CTD, "Dette intérieure directe des CTD's"),
    ("Dette flottante des CTD's", _CTD, "Dette flottante des CTD's"),
    ("6. Passifs conditionnels explicites de l'Etat", _CL,
     "6. Passifs conditionnels"),
    ("Dette avalisée", _CL, "Dette avalisée"),
    ("Partenariats Publics Privés", _CL, "Partenariats Publics Privés"),
    ("7. Total Dette Publique (non consolidée) (Secteur Public - hors passifs "
     "conditionnels) (3+4+5)", _PS, "7. Total Dette Publique"),
]
_X_SPLIT = 222          # labels sit left of this x, values right of it
_CELL_GAP = 10          # a gap wider than this (pt) starts a new cell


def _lines(words, top0, top1):
    """Words between two y positions, grouped into visual lines (top +-3)."""
    out = []
    for w in sorted((w for w in words if top0 < w["top"] < top1),
                    key=lambda w: (w["top"], w["x0"])):
        if out and abs(w["top"] - out[-1][0]) <= 3:
            out[-1][1].append(w)
        else:
            out.append([w["top"], [w]])
    return [sorted(ws, key=lambda w: w["x0"]) for _, ws in out]


def _cells(ws):
    cells, cur, last = [], [], None
    for w in ws:
        if last is not None and w["x0"] - last > _CELL_GAP:
            cells.append(cur)
            cur = []
        cur.append(w)
        last = w["x1"]
    if cur:
        cells.append(cur)
    return cells


def _value(cell):
    txt = "".join(w["text"] for w in cell)
    if txt in ("-", "N/D"):
        return None
    if not re.fullmatch(r"\d+(?:[.,]\d+)?", txt):
        raise ValueError(f"CAA Tableau 1: unreadable cell {txt!r}")
    return float(txt.replace(",", "."))


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        rows += _parse_one(p)
    df = pd.DataFrame(rows)
    # Several issues print the same month; the newest issue (the primary,
    # read first) wins.
    return df.drop_duplicates(["coverage", "component", "period"], keep="first")


def _parse_one(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        page = next((p for p in pdf.pages
                     if _CAPTION.search(p.extract_text() or "")), None)
        if page is None:
            raise ValueError(f"CAA: Tableau 1 not found in {path}")
        words = page.extract_words()
    cap = next(w for w in words if w["text"] == "Tableau")["top"]
    end = next(w["top"] for w in words
               if w["text"] == "Source" and w["top"] > cap)
    lines = _lines(words, cap + 5, end)

    # header: every line above the first row ("1. Dette extérieure")
    first = next(i for i, ln in enumerate(lines)
                 if ln and ln[0]["text"] == "1." and ln[0]["x1"] <= _X_SPLIT)
    head, body = lines[:first], lines[first:]
    # LABEL / VALUE BOUNDARY. 2026 issues: x = _X_SPLIT. Older issues start
    # the first value column further left (inside 222 pt), so the boundary is
    # taken from the rows themselves: just left of the leftmost FIRST figure
    # of any row (figures are right-aligned, so a wide one -- "12 133" --
    # starts furthest left).
    firsts = []
    for ln in body:
        # the first word from which EVERY remaining word is a figure ("de 3
        # mois" keeps its 3 in the label)
        fig = [bool(re.fullmatch(r"\d+(?:[.,]\d+)?|-|N/D", w["text"])) for w in ln]
        k = next((i for i in range(1, len(ln) - 1) if all(fig[i:])), None)
        if k is not None:
            firsts.append(ln[k]["x0"])
    split = min([_X_SPLIT] + [x - 1 for x in firsts])

    num_rows, label_text, ncol = [], [], None
    for ln in body:
        if any("données" in w["text"] for w in ln):
            continue                    # the footnote line
        val = [w for w in ln if w["x0"] > split]
        # A wrapped label's tail can fall right of the boundary ("publics",
        # "dette", "Public-"): words before the first figure are label text.
        fig = [bool(re.fullmatch(r"\d+(?:[.,]\d+)?|-|N/D", w["text"])) for w in val]
        # at least two trailing figures: every table row has 5+ cells, and a
        # label ending in a lone "-" ("(Secteur Public -") is not a cell
        k = next((i for i in range(len(val) - 1) if all(fig[i:])), len(val))
        lab = [w for w in ln if w["x0"] <= split] + val[:k]
        val = val[k:]
        if any(not re.fullmatch(r"\d+(?:[.,]\d+)?|-|N/D", w["text"]) for w in val):
            raise ValueError(f"CAA Tableau 1: text among figures "
                             f"({' '.join(w['text'] for w in val)})")
        if lab:
            label_text.append(" ".join(w["text"] for w in lab))
        if val:
            cells = _cells(val)
            # The column count varies by issue (5, 8, 9, 11); every row of
            # one issue must carry the same number.
            ncol = ncol or len(cells)
            if len(cells) != ncol:
                raise ValueError(f"CAA Tableau 1: {len(cells)} cells in a row "
                                 f"of {ncol} ({' '.join(w['text'] for w in val)})")
            num_rows.append(cells)
    # ROWS PRESENT, in order. Older issues print fewer rows (no "dont appui
    # budgétaire total", or no CTD detail); a stated row is present when its
    # words are found in order in the label text. The present rows must
    # number exactly the value rows; the sum checks below then confirm the
    # alignment (a shifted row cannot pass them).
    # Two labels are letter-spaced (and scrambled) in the March 2025 issue.
    flat = (" ".join(label_text)
            .replace("d o n t a p p u si b u d g é at eri s", "dont appuis budgétaires")
            .replace("d o n t a p p u i b u d g é at eri ot at l", "dont appui budgétaire total"))
    present, pos = [], 0
    for row in _ROWS:
        q, ok = pos, True
        for word in row[2].split():
            k = flat.find(word, q)
            if k < 0 or (word == row[2].split()[0] and k - pos > 400):
                ok = False
                break
            q = k + len(word)
        if ok:
            present.append(row)
            pos = q
    if len(num_rows) != len(present):
        raise ValueError(f"CAA Tableau 1: {len(num_rows)} value rows for "
                         f"{len(present)} labels found ({len(_ROWS)} stated)")

    # column dates from the header: each column's month and year sit above
    # its cells, so assign header words to the nearest column centre.
    centres = [(c[0]["x0"] + c[-1]["x1"]) / 2 for c in num_rows[-1]]
    split_h = split
    months, years = [None] * ncol, [None] * ncol
    for ln in head:
        for w in ln:
            if w["x1"] <= split_h:
                continue
            j = min(range(ncol), key=lambda i: abs(centres[i] - (w["x0"] + w["x1"]) / 2))
            t = w["text"].lower()
            if t in _MONTHS:
                months[j] = _MONTHS[t]
            elif re.fullmatch(r"20\d\d\**", t):     # "2025***" = provisional
                years[j] = int(t[:4])
    if None in months or None in years:
        raise ValueError(f"CAA Tableau 1: header unread {months} {years}")
    periods = [f"{y}-{m:02d}" for y, m in zip(years, months)]

    vals = [[_value(c) for c in r] for r in num_rows]
    by = {comp: v for (comp, _, _), v in zip(present, vals)}

    def chk(total, parts):
        if total not in by or any(p not in by for p in parts):
            raise ValueError(f"CAA Tableau 1: check rows missing for {total}")
        for j in range(ncol):
            t = by[total][j]
            ps = [by[p][j] for p in parts]
            if t is None or any(v is None for v in ps):
                continue
            if abs(t - sum(ps)) > 2:
                raise ValueError(f"CAA Tableau 1 {periods[j]}: {total} = {t}, "
                                 f"parts sum to {sum(ps)}")
    chk("1. Dette extérieure", ["Multilatérale", "Bilatérale", "Commerciale"])
    chk("3. Dette Directe de l'Administration Centrale",
        ["1. Dette extérieure", "2. Dette intérieure"])
    chk("4. Dette des Entreprises et Etablissements publics",
        ["Dette extérieure directe des Entreprises et Etablissements publics",
         "Dette intérieure auprès du système bancaire",
         "Dette flottante des Entreprises et Etablissements publics"])
    chk(_ROWS[-1][0], ["3. Dette Directe de l'Administration Centrale",
                       "4. Dette des Entreprises et Etablissements publics",
                       "5. Dette des Collectivitées Territoriales Décentralisées"])

    out = []
    for (comp, cov, _), v in zip(present, vals):
        for per, x in zip(periods, v):
            if x is None:
                continue
            out.append({"coverage": cov, "component": comp, "period": per,
                        "frequency": "monthly", "measure": "stock", "value": x,
                        "unit": "FCFA milliards", "series_code": "CAA T1"})
    return out
