"""Madagascar — INSTAT: ENEMPSI 2012 (Tome 1 workbook) and RGPH-3 2018
("Caractéristiques économiques de la population", thematic report, Oct 2021).

TWO SOURCES, TWO UNIVERSES, NEVER CHAINED. They differ in instrument, year and
working-age base, and each row says which through `survey`, `period` and
`working_age_base`:

    ENEMPSI 2012   household employment survey     employed aged 5 and over
    RGPH-3 2018    census                          employed aged 15-59

ENEMPSI (Enquête Nationale sur l'Emploi et le Secteur Informel), Tome 1, sheet
"structure emplois", Tableaux 20-44. ENEMPSI is ERI-ESI-shaped: Tome 1 is the
HOUSEHOLD employment phase; the informal production-unit (UPI) results are a
separate tome and are not read. Only the tables whose rows each sum to 100 over
the categories -- a composition of one population -- are taken:

* secteur institutionnel (Administration publique / Entreprises formelles /
  Entreprises informelles hors agriculture / Entreprises informelles agricoles
  / Entreprises associatives) -> `formality`, as Cameroon's "secteur
  institutionnel" is: its main axis is formal vs informal production units.
  By milieu (T20), sex (T22), region (T23), age (T24, T25).
* catégorie socio-professionnelle (Cadre / Ouvrier qualifié / Ouvrier non
  qualifié / Travailleur indépendant / Aide familiale) -> `employment_status`,
  National. By milieu (T28), region (T30), sex (T31), age (T33, T34).
* branche d'activités (12 national branches) -> `industry`, National. By
  milieu (T37), region (T39), sex (T40), age (T41, T42).

NOT TAKEN from ENEMPSI: T21, T29, T32, T38 are ROW percentages (the sex or
milieu split WITHIN a category); T26, T27, T35, T36, T43, T44 cross two
category dimensions, which one category column cannot hold. T43/T44 also print
an "Ensemble" branch distribution that disagrees with T37-T42's (Commerce 4,1
against 6,975; Autres services 5,7 against 2,772) -- another reason not to mix
them in.

THE BASE IS 5+, read from the tables themselves: T24/T33/T41 have a "5 à 9
ans" employed row, and every distribution's Ensemble is that population.
Comparing these shares with a 15+ series is a real error.

VALUES ARE COLLECTED AS THE CELLS HOLD THEM: the Ensemble rows are
unrounded weighted estimates (75.1719..., displayed 75.172) while the others
carry two decimals. Each row's printed "Total" (99.99, 100.01 -- a rounded
sum, sometimes over 100) is used as the sum check and NOT emitted: it is not a
category, and a share of 100.01 is not one the schema accepts.

THE ENSEMBLE ROW REPEATS in every table of a block (T20, T22, T23, T24, T25
all print 2.532 / 3.827 / 17.864 / 75.172 / 0.604) and would collide on the
merge key. It is emitted once, and the parser raises if a repeat differs.

RGPH-3 2018, two tables, columns Urbain (H F E) | Rural (H F E) | Ensemble
(H F E):

* Tableau 5.7 branche d'activités, 21 branches -> `industry`. PRINTED ROTATED
  90 degrees: pdfplumber reads each token backwards ("5,37" for 73,5), so the
  page is read from PyMuPDF words, whose order is the content stream's, with
  each table row rebuilt from the words sharing an x position. The branches
  are NOMAC -- "Pour le RGPH-3, la nomenclature NOMAC adoptée par Madagascar
  en 2012 est choisie ... En 1993, la nomenclature utilisée ... (CITI)" -- so
  National, not ISIC: CITI names the 1993 census's scheme, not this one.
  Its "Effectif" row is NOT collected: the urban total prints "709 676" where
  Tableaux 5.6 and 5.9 print 1 709 676 for the same population.
* Tableau 5.8 situation dans l'occupation, 8 categories -> `employment_status`,
  National (salariés split public/privé, plus "travailleur à la tâche").
  ITS CAPTION IS WRONG, AND THE TABLE SAYS SO: it reads "(15-19 ans)", but its
  own count row gives 9 644 559 valid + 94 332 missing = 9 738 891, exactly the
  employed 15-59 of Tableaux 5.6, 5.9 and 5.10; and the prose above it cites
  its figures (indépendants 80,5 %, salariés 12,8 %) for all workers. Base
  15-59, as the numbers show. Shares are of the VALID count (the table's note).

CROSS-CHECK. ENEMPSI 2012: informel agricole 75.172, administration publique
2.532; aide familiale 45.946, cadre 1.014; secteur primaire 75.682, commerce
6.975; Analamanga informel hors agriculture 40.87. RGPH-3 2018 (15-59):
agriculture 73,5 (urbain 22,4, rural 84,3); commerce 4,5; indépendant 80,5;
salarié privé 7,4; employed 9 738 891.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber

from . import _common as C

_SHEET = "structure emplois"
_ENEMPSI = {"survey": "Enquête Nationale sur l'Emploi et le Secteur Informel "
                      "(ENEMPSI) 2012",
            "period": "2012", "reference_period": "ENEMPSI 2012",
            "frequency": "ad_hoc", "working_age_base": "5+"}
_RGPH = {"survey": "Troisième Recensement Général de la Population et de "
                   "l'Habitation (RGPH-3)",
         "period": "2018", "reference_period": "RGPH-3 2018",
         "frequency": "ad_hoc", "working_age_base": "15-59"}
_P = {"measure": "share", "unit": "percent"}

# Tableau -> (topic, classification, what the row label is)
_ENEMPSI_TABLES = {
    20: ("formality", "Not applicable", "milieu"),
    22: ("formality", "Not applicable", "sexe"),
    23: ("formality", "Not applicable", "region"),
    24: ("formality", "Not applicable", "age"),
    25: ("formality", "Not applicable", "age"),
    28: ("employment_status", "National", "milieu"),
    30: ("employment_status", "National", "region"),
    31: ("employment_status", "National", "sexe"),
    33: ("employment_status", "National", "age"),
    34: ("employment_status", "National", "age"),
    37: ("industry", "National", "milieu"),
    39: ("industry", "National", "region"),
    40: ("industry", "National", "sexe"),
    41: ("industry", "National", "age"),
    42: ("industry", "National", "age"),
}
# Row count per table INCLUDING its Ensemble row; the guard for a sheet edit.
_ENEMPSI_ROWS = {20: 3, 22: 3, 23: 23, 24: 6, 25: 4, 28: 3, 30: 23, 31: 3,
                 33: 6, 34: 4, 37: 3, 39: 23, 40: 3, 41: 6, 42: 4}
_CATEGORIES = {"formality": 5, "employment_status": 5, "industry": 12}


def _dims(kind: str, label: str) -> dict:
    """What a row label of this table means, in schema columns."""
    if label == "Ensemble":
        return {}
    if kind == "milieu":
        return {"locality": C.normalise_locality(label), "locality_label": label}
    if kind == "sexe":
        return {"sex": C.normalise_sex(label)}
    if kind == "region":
        return {"geography": label}
    return {"age_group": label}


def _enempsi(path: str) -> list[dict]:
    raw = pd.read_excel(path, sheet_name=_SHEET, header=None)
    starts = {}
    for i, v in raw[0].items():
        m = re.match(r"Tableau (\d+) :", str(v))
        if m:
            starts[int(m.group(1))] = i
    out, ensemble = [], {}
    for tab, (topic, scheme, kind) in _ENEMPSI_TABLES.items():
        if tab not in starts:
            raise ValueError(f"ENEMPSI: Tableau {tab} not found on {_SHEET!r}")
        block = raw.iloc[starts[tab] + 1:]
        # The header row is the first whose last filled cell is "Total".
        hdr = next(i for i, r in block.iterrows()
                   if str(r.dropna().iloc[-1] if r.notna().any() else "") == "Total")
        cats = [str(c).strip() for c in raw.loc[hdr].dropna().iloc[1:]]
        if len(cats) != _CATEGORIES[topic] + 1:
            raise ValueError(f"ENEMPSI T{tab}: header {cats}")
        rows = []
        for i in range(hdr + 1, len(raw)):
            r = raw.loc[i]
            if r.isna().all():
                break
            rows.append((str(r[0]).strip(), list(r[1:len(cats) + 1])))
        if len(rows) != _ENEMPSI_ROWS[tab] or rows[-1][0] != "Ensemble":
            raise ValueError(f"ENEMPSI T{tab}: read {[r[0] for r in rows]}")
        for label, vals in rows:
            if label == "Ensemble":
                prev = ensemble.setdefault(topic, vals)
                if prev != vals:
                    raise ValueError(f"ENEMPSI T{tab}: Ensemble differs from "
                                     f"the block's earlier tables")
                if prev is not vals:
                    continue       # already emitted from an earlier table
            if abs(sum(vals[:-1]) - vals[-1]) > 0.05:
                raise ValueError(f"ENEMPSI T{tab} {label}: categories do not "
                                 f"sum to the printed Total")
            # The printed "Total" is each row's rounded sum (99.99, 100.01):
            # it is the check above, not a category, and is not emitted.
            for cat, val in zip(cats[:-1], vals[:-1]):
                out.append(C.row(
                    topic=topic, classification=scheme, characteristic=cat,
                    value=val, series_code=f"ENEMPSI2012 T{tab}",
                    **_ENEMPSI, **_P, **_dims(kind, label)))
    return out


# RGPH-3 columns: Urbain H F E | Rural H F E | Ensemble H F E
_RGPH_COLS = [dict(locality=loc, locality_label=lab, sex=sex)
              for loc, lab in (("urban", "Urbain"), ("rural", "Rural"),
                               ("all", "Total"))
              for sex in ("male", "female", "total")]
_NUM = r"\d+(?:,\d)?"
_ROW = re.compile(rf"^(.*?)\s*((?:{_NUM}\s+){{8}}{_NUM})$")


def _nine(nums: str) -> list[float]:
    return [float(n.replace(",", ".")) for n in nums.split()]


def _rgph_rows(lines: list[str], where: str) -> list[tuple[str, list[float]]]:
    """Label + nine values per row; a label may wrap around its numbers
    ("Travailleur à la" / numbers / "tâche"), or sit whole on the number line."""
    rows, pending, i = [], [], 0
    while i < len(lines):
        s = lines[i].strip()
        m = _ROW.match(s)
        if m:
            label = " ".join(pending + [m.group(1)]).strip()
            vals = _nine(m.group(2))
            if not m.group(1) and i + 1 < len(lines) \
                    and not _ROW.match(lines[i + 1].strip()) \
                    and not re.search(r"\d", lines[i + 1]):
                label = f"{label} {lines[i + 1].strip()}"   # wrapped tail
                i += 1
            rows.append((label, vals))
            pending = []
            if label == "ENSEMBLE":
                break
        elif s:
            pending.append(s)
        i += 1
    if not rows or rows[-1][0] != "ENSEMBLE":
        raise ValueError(f"{where}: no ENSEMBLE row")
    for c in range(9):
        tot = sum(v[c] for _, v in rows[:-1])
        if abs(tot - 100) > 0.6:
            raise ValueError(f"{where}: column {c} sums to {tot:.1f}")
    return rows


def _rgph_emit(rows, topic: str, code: str) -> list[dict]:
    out = []
    for label, vals in rows:
        lab = "Total" if label == "ENSEMBLE" else label
        for col, val in zip(_RGPH_COLS, vals):
            out.append(C.row(topic=topic, characteristic=lab,
                             classification="National", value=val,
                             series_code=code, **_RGPH, **_P, **col))
    return out


def _t57(path: str) -> list[dict]:
    """Tableau 5.7, printed rotated: rebuild each row from the PyMuPDF words
    sharing an x position, read in descending y (the rotated reading order)."""
    doc = fitz.open(path)
    page = next(p for p in doc
                if re.search(r"Tableau\s+5\.7\.\s+Distribution", p.get_text())
                and "Effectif" in p.get_text())
    by_x = defaultdict(list)
    for w in page.get_text("words"):
        if w[0] >= 60 and 50 < w[1] < 800:
            by_x[round(w[0])].append(w)
    lines = [" ".join(w[4] for w in sorted(by_x[x], key=lambda w: -w[1]))
             for x in sorted(by_x)]
    start = next(i for i, ln in enumerate(lines)
                 if ln.startswith("Homme Femme Ensemble")) + 1
    rows = _rgph_rows(lines[start:], "RGPH-3 T5.7")
    if len(rows) != 22:
        raise ValueError(f"RGPH-3 T5.7: read {[r[0] for r in rows]}")
    return _rgph_emit(rows, "industry", "RGPH3 T5.7")


def _t58(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        # The caption also opens a line of the list of tables (page 12);
        # only the table's own page carries its count row.
        text = next(t for t in (p.extract_text() or "" for p in pdf.pages)
                    if re.search(r"^Tableau 5\.8\. Distribution", t, re.M)
                    and "Effectif (valides)" in t)
    lines = text[re.search(r"^Tableau 5\.8\.", text, re.M).start():].splitlines()
    start = next(i for i, ln in enumerate(lines)
                 if ln.startswith("Homme Femme Ensemble")) + 1
    rows = _rgph_rows(lines[start:], "RGPH-3 T5.8")
    want = ["Indépendant", "Employeur", "Salarié public", "Salarié privé",
            "Travailleur à la tâche", "Apprenti", "Travailleur familial",
            "Autre", "ENSEMBLE"]
    if [r[0] for r in rows] != want:
        raise ValueError(f"RGPH-3 T5.8: read {[r[0] for r in rows]}")
    return _rgph_emit(rows, "employment_status", "RGPH3 T5.8")


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for path in [local_path] + list(extras or []):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".xls":
            rows += _enempsi(path)
        elif ext == ".pdf":
            rows += _t57(path) + _t58(path)
        else:
            raise ValueError(f"{path}: not a Madagascar source this parser knows")
    return pd.DataFrame(rows)
