"""Central African Republic — ICASEES (ex-DGSEE/BCR), RGPH03 (Recensement
Général de la Population et de l'Habitation, December 2003), thematic report
"Caractéristiques économiques" (June 2005), chapter 3.2.

A CENSUS, so the universe is the resident population of ordinary households.
THE BASE IS 6+, NOT 15+: the report "ramène l'âge de début d'activité à 6 ans"
and defines the employed as the population aged 6 and over who worked in the
seven days before the interview. Carried exactly; comparing these shares with
a 15+ series without saying so would be a real error.

Five tables, all column-% distributions of the employed:

* Eco 11  occupation (8 groups) by sex                 -> occupation
* Eco 12  occupation by urban / rural / ensemble        -> occupation
* Eco 13  occupation by the six administrative regions and Bangui -> occupation
* Eco 15  branch of activity (11) by ensemble / urban / rural -> industry
* Eco 17  status in the profession (6) by sex, within Ensemble RCA / Urbain /
          Rural blocks                                  -> employment_status

EVERY "RAPPORT DE FÉMINITÉ" COLUMN IS DROPPED -- a sex ratio, not a share. In
Eco 17 that column is also misaligned (the Urbain block opens with 87,9, the
national Total's ratio); the share columns beside it are not: each of the nine
columns sums to 100 and every Ensemble lies between its Masculin and Féminin.

EO 11'S TEXT LAYER IS SPLIT, NOT LOST. For seven of its eight rows the
Ensemble and sex-ratio cells land on the line ABOVE the label line that holds
Homme / Femme ("8,5 57,4" then "Scientifique, Technique ou Libéral 10,0 6,9").
The pairing is proved on every run rather than assumed: each Ensemble must lie
between its row's Homme and Femme values and must equal Eco 12's Ensemble
column; only Homme / Femme are emitted (the Ensemble comes from Eco 12, once).

EO 13 PRINTS REGION 3 AND REGION 4 AS THE SAME COLUMN -- identical in all nine
rows (1,1 / 0,1 / 0,2 / 4,2 / 0,8 / 92,7 / 1,0 / 0,0 / 100,0) -- although the
two regions differ everywhere else in the report (Eco 16: 27,7% vs 18,8% of
agriculture). One is a copy and nothing in the table says which, so NEITHER is
collected. The parser checks the copy on every run and collects both columns
if the two ever differ.

ONE LABEL PER CATEGORY. The three occupation tables spell the same eight
groups with different punctuation ("Trav.Spec,/Man*", "Trav,Spec/Man*",
"Personnel administratif, Assimilé"); each table's printed words are checked
in order, and the rows are emitted under one label per group (Eco 12's), so a
group is not split across spellings. "Trav.Spec/Man" is the report's own
abbreviation: travailleurs spécialisés dans les services, travailleurs non
qualifiés ou manœuvres (footnote).

NOT COLLECTED: Eco 14 (1988 vs 2003, excluding the military -- its 2003
column is a different universe from Eco 12's and would collide with it);
Eco 16 (row percentages: each branch spread across regions); Eco 18 (branch
WITHIN each status, a two-dimension cross-tab); Eco 19-20 (children 6-14);
Eco 1-10 and 21-39 (activity rates, education, unemployment, inactivity).

DATA-QUALITY CAVEAT, THE REPORT'S OWN (§1.5.2): branch and occupation were the
questions census agents found hardest, and coding them raised "problèmes de
nomenclature et de correspondance". No nomenclature is named -> National.

CROSS-CHECK (ensemble): agriculteurs, éleveurs ou forestiers 73,8 (urban 40,4,
rural 86,1; men 66,8, women 80,8); agriculture branch 78,6; indépendants 80,1;
salariés 7,9 (urban men 30,1); Bangui commerce 37,5.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = ("Recensement Général de la Population et de l'Habitation "
           "(RGPH03), décembre 2003")
_BASE = dict(survey=_SURVEY, period="2003", reference_period="RGPH03 (décembre 2003)",
             frequency="ad_hoc", measure="share", unit="percent",
             working_age_base="6+")
_NUM = r"\d+(?:[,.]\d+)?"

_OCC = ["Scientifique, Technique ou Libéral", "Cadres supérieurs",
        "Personnel administrative ou assimilé", "Personnel commercial ou Vendeurs",
        "Trav.Spec/Man", "Agriculteurs, Eleveurs ou Forestiers",
        "Ouvriers, Artisans", "Militaires", "Total"]
# Each table's own printed words for the same nine rows, checked in order.
_OCC_11 = ["Scientifique, Technique ou Libéral", "Cadres supérieurs",
           "Personnel administrative ou assimilé",
           "Personnel commercial ou Vendeurs", "Trav.Spec,/Man",
           "Agriculteurs, Eleveurs ou Forestiers", "Ouvriers, Artisans",
           "Militaires", "Total"]
_OCC_13 = ["Scientifique, Technique, ou libéral", "Cadres supérieurs",
           "Personnel administratif, Assimilé", "Personnel commercial, Vendeurs",
           "Trav,Spec,/Man", "Agriculteurs, Eleveurs, Forestiers",
           "Ouvriers, Artisans", "Militaires", "Total"]
_BRANCH = ["Agriculture, Elevage, chasse, Pêche", "Activités d’extraction",
           "Activités manufacturières", "Electricité, Gaz et Eau",
           "Bâtiments et Travaux Publics",
           "Commerce, Restauration/Hôtellerie, Services aux entreprises",
           "Transports et Communication", "Activités financières",
           "Activités d'administration", "Activité des ménages",
           "Activité des organisation extraterritoriale", "Total"]
_STATUS = ["Salariés", "Indépendants", "Employeurs", "Aide familial",
           "Apprenti", "Autres", "Total"]
_REGIONS = ["Région 1", "Région 2", "Région 3", "Région 4", "Région 5",
            "Région 6", "Bangui"]
_URB = {"locality": "urban", "locality_label": "Milieu urbain"}
_RUR = {"locality": "rural", "locality_label": "Milieu rural"}


def _f(tok: str) -> float:
    return float(tok.replace(",", "."))


def _words(s: str) -> list[str]:
    return re.findall(r"\w+", s.lower())


def _tail(line: str) -> tuple[str, list[float]]:
    """Split a line into its label and the run of numbers that ends it."""
    m = re.search(rf"((?:\s|^)(?:{_NUM}))+\s*$", line)
    if not m:
        return line.strip(), []
    return line[:m.start()].strip(), [_f(t) for t in m.group(0).split()]


def _region(lines: list[str], caption: str, where: str,
            n_totals: int = 1) -> list[str]:
    start = next((i for i, ln in enumerate(lines) if re.search(caption, ln)), None)
    if start is None:
        raise ValueError(f"{where}: caption not found")
    out, seen = [], 0
    for ln in lines[start + 1:]:
        out.append(ln)
        if ln.startswith("Total"):
            seen += 1
            if seen == n_totals:
                return out
    raise ValueError(f"{where}: no closing Total row")


def _rows(region: list[str], ncols: int, labels: list[str], where: str):
    """Rows whose line ends in exactly `ncols` numbers, in order, with every
    stated label's words present in order in the region's text."""
    rows, text = [], []
    for ln in region:
        lab, nums = _tail(ln)
        if len(nums) == ncols:
            rows.append(nums)
        text.append(lab if len(nums) == ncols else ln)
    if len(rows) != len(labels):
        raise ValueError(f"{where}: {len(rows)} value rows for {len(labels)} labels")
    flat, pos = _words(" ".join(text)), 0
    for lab in labels:
        for w in _words(lab):
            try:
                pos = flat.index(w, pos) + 1
            except ValueError:
                raise ValueError(f"{where}: label {lab!r} not found in order")
    return rows


def _check_columns(rows, cols, where, tol=0.35):
    for j in cols:
        s = sum(r[j] for r in rows[:-1])
        if abs(s - 100) > tol or abs(rows[-1][j] - 100) > 1e-9:
            raise ValueError(f"{where}: column {j} sums to {s:.1f}")


def _between(val, a, b, where):
    if not (min(a, b) - 0.1 <= val <= max(a, b) + 0.1):
        raise ValueError(f"{where}: ensemble {val} outside {a} / {b}")


def _emit(topic, labels, rows, cols, code):
    out = []
    for lab, vals in zip(labels, rows):
        for j, ctx in cols:
            out.append(C.row(topic=topic, characteristic=lab,
                             classification="National", value=vals[j],
                             series_code=code, **_BASE, **ctx))
    return out


def _lines(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        text = []
        for page in pdf.pages[30:42]:           # chapter 3.2, printed pp. 19-29
            text += (page.extract_text() or "").splitlines()
    return [ln.strip() for ln in text if ln.strip()]


def _eco_11(lines, eco12_ensemble):
    region = _region(lines, r"^Tableau Eco 11\s*:", "Eco 11")
    rows, text, pending = [], [], None
    for ln in region:
        lab, nums = _tail(ln)
        if not lab and len(nums) == 2:          # "8,5 57,4": ensemble, ratio
            pending = nums
            continue
        if len(nums) == 4:                      # all four on one line
            rows.append((nums[0], nums[1], nums[2]))
        elif len(nums) == 2 and lab and pending:
            rows.append((nums[0], nums[1], pending[0]))
            pending = None
        text.append(lab or ln)
    _rows_check = [list(r) for r in rows]
    if len(rows) != 9:
        raise ValueError(f"Eco 11: {len(rows)} rows")
    flat, pos = _words(" ".join(text)), 0
    for lab in _OCC_11:
        for w in _words(lab):
            pos = flat.index(w, pos) + 1
    _check_columns(_rows_check, (0, 1), "Eco 11")
    for (h, f, e), ens in zip(rows[:-1], eco12_ensemble[:-1]):
        _between(e, h, f, "Eco 11")
        if e != ens:
            raise ValueError(f"Eco 11: ensemble {e} is not Eco 12's {ens}")
    return _emit("occupation", _OCC, _rows_check,
                 [(0, {"sex": "male"}), (1, {"sex": "female"})], "RGPH03 Eco 11")


def parse(path: str) -> pd.DataFrame:
    lines = _lines(path)
    out = []

    # Eco 12: Milieu urbain | Milieu rural | Ensemble
    r12 = _rows(_region(lines, r"^Tableau Eco 12\s*:", "Eco 12"), 3, _OCC, "Eco 12")
    _check_columns(r12, (0, 1, 2), "Eco 12")
    for u, r, e in r12[:-1]:
        _between(e, u, r, "Eco 12")
    out += _emit("occupation", _OCC, r12, [(0, _URB), (1, _RUR), (2, {})],
                 "RGPH03 Eco 12")
    out += _eco_11(lines, [row[2] for row in r12])

    # Eco 13: Région 1..6 | Bangui
    r13 = _rows(_region(lines, r"^Tableau Eco 13\s*:", "Eco 13"), 7, _OCC_13, "Eco 13")
    _check_columns(r13, range(7), "Eco 13")
    copied = all(row[2] == row[3] for row in r13)
    cols13 = [(j, {"geography": g}) for j, g in enumerate(_REGIONS)
              if not (copied and j in (2, 3))]
    out += _emit("occupation", _OCC, r13, cols13, "RGPH03 Eco 13")

    # Eco 15: Ensemble | Urbain | Rural | rapport de féminité (dropped)
    r15 = _rows(_region(lines, r"^Tableau Eco 15\s*:", "Eco 15"), 4, _BRANCH, "Eco 15")
    _check_columns(r15, (0, 1, 2), "Eco 15")
    for e, u, r, _ in r15[:-1]:
        _between(e, u, r, "Eco 15")
    out += _emit("industry", _BRANCH, r15, [(0, {}), (1, _URB), (2, _RUR)],
                 "RGPH03 Eco 15")

    # Eco 17: three blocks of seven rows; Masculin | Féminin | Ensemble | ratio
    r17 = _rows(_region(lines, r"^Tableau Eco 17\s*:", "Eco 17", n_totals=3),
                4, _STATUS * 3, "Eco 17")
    for b, loc in enumerate(({}, _URB, _RUR)):
        block = r17[7 * b:7 * b + 7]
        _check_columns(block, (0, 1, 2), f"Eco 17 block {b}", tol=0.25)
        for m, f, e, _ in block[:-1]:
            _between(e, m, f, f"Eco 17 block {b}")
        out += _emit("employment_status", _STATUS, block,
                     [(0, {"sex": "male", **loc}), (1, {"sex": "female", **loc}),
                      (2, dict(loc))], "RGPH03 Eco 17")
    return pd.DataFrame(out)
