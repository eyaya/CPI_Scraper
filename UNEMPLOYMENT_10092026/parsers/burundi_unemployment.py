"""Burundi — INSBU, EICVMB 2019-2020 (Enquête Intégrée sur les Conditions de
Vie des Ménages au Burundi), "Module : Emploi".

A HOUSEHOLD survey on the ICLS-19 framework (the report cites the 19th CIST's
"main-d'œuvre potentielle" in footnote 3), working-age population 15+. NOT the
Annuaire statistique that `labour/` reads for its status table: the yearbook's
employment chapter carries no rates, and its other tables are INSS and civil-
service registers (administrative, never collected here).

Tables taken (all national-population rates are as printed, never recomputed):

* Tableau 3  taux d'activité STRICT and ÉTENDU by milieu, sex, age band and
             education -> labour_force_participation_rate (strict / broad);
* Tableau 4  the same two rates by province;
* Tableau 5  taux d'emploi (ratio emploi/population) by milieu, sex, education,
             age band -> employment_to_population_ratio;
* Tableau 6  the same by province;
* Tableau 9  taux de chômage STRICT and the "taux cumulé de chômage et de la
             population active potentielle" by milieu, sex, education, age ->
             unemployment_rate (strict) and labour_underutilisation_rate (broad
             -- the LU3 concept, filed as Liberia's LU3 is);
* Tableau A1 working-age population (15+) by province and sex -> counts;
* Tableau A2 population hors main-d'oeuvre and population active, counts, by
             province, milieu, sex, age and education.

"Strict" and "broad" come from INSBU's own labels: "taux d'activité strict" /
"étendue" (Tableau 4's caption says "élargie"), "taux de chômage strict" /
"cumulé ... au sens large" (p.31).

NOT COLLECTED: A2's percentage columns (they repeat Tableaux 3/4 to the digit);
A3's extended-labour-force COUNTS (labour force + potential labour force -- no
topic holds that sum, and differencing it against A2 would be computing);
Tableau 7 (taux d'emploi by institutional sector -- a composition, `labour/`'s
territory, and its denominator is ambiguous); Tableau 8 and A4/A5 (distributions
of the employed and of the inactive by reason); the youth (15-35) and
time-related-underemployment figures, which the report gives only as Figures
9-13 whose data labels are scrambled in the text layer.

TRAP: INSBU drops the leading zero -- Rural strict unemployment prints ",4"
(0,4) and 36-64 ",4". A number pattern that requires a digit before the comma
reads those rows one value short, so `_NUM` accepts ",4" deliberately.

ORDER, NOT NAMES, PLACES THE PROVINCES: "Bujumbura" (the province) and
"Bujumbura Mairie" (the capital) both open with "Bujumbura", and the capital's
"Mairie" wraps onto the next line in Tableau 4. Rows are taken in printed order
against the stated list, each checked to begin with its expected first word.

PERIOD 2020, reference "EICVMB 2019-2020" (end-year convention).

CROSS-CHECK: activité strict 76,4 / étendue 77,8; taux d'emploi 75,6
(Bujumbura Mairie 48,7); chômage strict 1,1 (urbain 7,3, rural 0,4), cumulé
2,8 (urbain 17,2); working-age population 6 460 883; hors main-d'oeuvre
1 525 630; actifs 4 935 253.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = "Enquête Intégrée sur les Conditions de Vie des Ménages (EICVMB) 2019-2020"
_BASE, _PERIOD, _REF = "15+", "2020", "EICVMB 2019-2020"
_NUM = r"(?<![\d,])(\d*,\d+|\d+)(?![\d,])"

_PROVINCES = ["Bubanza", "Bujumbura", "Bururi", "Cankuzo", "Cibitoke", "Gitega",
              "Karusi", "Kayanza", "Kirundo", "Makamba", "Muramvya", "Muyinga",
              "Mwaro", "Ngozi", "Rutana", "Ruyigi", "Bujumbura Mairie", "Rumonge"]
_MILIEU = [("Urbain", {"locality": "urban", "locality_label": "Urbain"}),
           ("Rural", {"locality": "rural", "locality_label": "Rural"})]
_SEXE = [("Masculin", {"sex": "male"}), ("Féminin", {"sex": "female"})]
_AGE = [(a, {"age_group": a}) for a in
        ("15 à 24 ans", "25 à 35 ans", "36 à 64 ans", "65 ans et plus")]
_EDU = [(e, {"education": e}) for e in
        ("Aucun", "Primaire", "Secondaire", "Superieur", "NSP")]
_PROV = [(p, {"geography": p}) for p in _PROVINCES]
_NAT = [("National", {})]


def _num(tok: str) -> float:
    return float(("0" + tok if tok.startswith(",") else tok).replace(",", "."))


def _region(text: str, caption: str) -> list[str]:
    """From the table's caption to the next Tableau/Figure caption.

    THE LIST OF TABLES REPEATS EVERY CAPTION, and wraps it before its dot
    leaders, so a dot-leader test on the caption line does not exclude it --
    a region opened there scanned Tableau 3's rows for Tableau 9's (and read
    "540" as a rate). The body caption is the LAST occurrence."""
    ms = list(re.finditer(caption, text))
    if not ms:
        raise ValueError(f"EICVMB: {caption!r} not found")
    out = []
    for ln in text[ms[-1].end():].splitlines():
        if re.match(r"\s*(Tableau|Figure)\s", ln):
            break
        out.append(ln.strip())
    return out


def _seq(lines: list[str], groups: list[tuple[str, dict]], ncols: int,
         where: str, total_label: str = "National") -> list[tuple[dict, list]]:
    """Rows in printed order: a line whose last `ncols` tokens are numbers and
    whose label opens with the expected group's first word."""
    out, i = [], 0
    for ln in lines:
        if i == len(groups):
            break
        nums = list(re.finditer(_NUM, ln))
        if len(nums) < ncols:
            continue
        tail = nums[-ncols:]
        if ln[tail[-1].end():].strip().rstrip("%"):
            continue
        label = ln[:tail[0].start()]
        want = groups[i][0]
        if want == "National" and total_label != "National":
            want = total_label
        if not re.search(rf"\b{re.escape(want.split()[0])}", label):
            continue
        out.append((groups[i][1], [_num(t.group(1)) for t in tail]))
        i += 1
    if i != len(groups):
        raise ValueError(f"{where}: read {i} of {len(groups)} rows "
                         f"(stopped before {groups[i][0]!r})")
    return out


def _rows(read, specs, series, **fixed) -> list[dict]:
    out = []
    for ctx, vals in read:
        for (topic, definition, label, measure), v in zip(specs, vals):
            if topic is None:
                continue
            out.append(C.row(topic=topic, definition=definition, value=v,
                             series_label=label, survey=_SURVEY, period=_PERIOD,
                             reference_period=_REF, frequency="ad_hoc",
                             working_age_base=_BASE, series_code=series,
                             measure=measure, **{**fixed, **ctx}))
    return out


_ACT = [("labour_force_participation_rate", "strict", "Taux d'activité strict", None),
        ("labour_force_participation_rate", "broad", "Taux d'activité étendue", None)]
_EMP = [("employment_to_population_ratio", "not_applicable",
         "Taux d'emploi de la main d'oeuvre ou ratio emploi/population", None)]
_CHO = [("unemployment_rate", "strict", "Taux de chômage strict", None),
        ("labour_underutilisation_rate", "broad",
         "Taux cumulé de chômage et de la population active potentielle", None)]


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    cap = lambda s: rf"(?m)^{s}[^\n]*\n"   # noqa: E731

    rows = []
    t3 = _region(text, cap(r"Tableau 3 : Taux d.activité par le milieu"))
    r3 = _seq(t3, _MILIEU + _SEXE + _AGE + _EDU + _NAT, 2, "T3")
    rows += _rows(r3, _ACT, "EICVMB T3")
    # The province tables repeat the national row; it must agree with the
    # demographic table's, and is emitted once (the merge key has no table).
    t4 = _region(text, cap(r"Tableau 4 : Taux d.activité strict et élargie"))
    r4 = _seq(t4, _PROV + _NAT, 2, "T4")
    if r4[-1][1] != r3[-1][1]:
        raise ValueError(f"EICVMB: T4 national {r4[-1][1]} != T3 {r3[-1][1]}")
    rows += _rows(r4[:-1], _ACT, "EICVMB T4")
    t5 = _region(text, cap(r"Tableau 5: Taux d'emploi de la main"))
    r5 = _seq(t5, _MILIEU + _SEXE + _EDU[:4] + _AGE + _NAT, 1, "T5")
    rows += _rows(r5, _EMP, "EICVMB T5")
    t6 = _region(text, cap(r"Tableau 6 : Taux d'emploi de la main"))
    r6 = _seq(t6, _PROV + _NAT, 1, "T6")
    if r6[-1][1] != r5[-1][1]:
        raise ValueError(f"EICVMB: T6 national {r6[-1][1]} != T5 {r5[-1][1]}")
    rows += _rows(r6[:-1], _EMP, "EICVMB T6")
    t9 = _region(text, cap(r"Tableau 9 : Taux de chômage strict et cumulé"))
    rows += _rows(_seq(t9, _MILIEU + _SEXE + _EDU + _AGE + _NAT, 2, "T9"),
                  _CHO, "EICVMB T9")

    # Annex counts. A1: Masculin N, %, Féminin N, %, Total N, % (6 numbers).
    a1 = _region(text, cap(r"Tableau A 1: Répartition de la population en âge"))
    read = _seq(a1, _PROV + _NAT, 6, "A1")
    # Weighted counts, each rounded on its own: male + female misses the
    # printed Total by one person in some provinces (Bururi 119 792 + 147 621
    # = 267 413 against 267 412). Kept as printed; more than one is a misread.
    for ctx, (m, _, f, _, t, _) in read:
        if abs(m + f - t) > 1:
            raise ValueError(f"EICVMB A1 {ctx}: {m} + {f} != {t}")
    wap = [("working_age_population", "not_applicable",
            "Population en âge de travailler (15 ans et plus)", "count")]
    for sex, idx in (("male", 0), ("female", 2), ("total", 4)):
        rows += _rows([(ctx, [v[idx]]) for ctx, v in read], wap, "EICVMB A1",
                      sex=sex)
    # A2: hors main-d'oeuvre N, %, actifs N, % (4 numbers); total row "Total".
    a2 = _region(text, cap(r"Tableau A2: Taux de participation de la main"))
    read = _seq(a2, _PROV + _MILIEU + _SEXE + _AGE + _EDU + _NAT, 4, "A2",
                total_label="Total")
    nat = read[-1][1]
    if abs(nat[0] + nat[2] - 6460883) > 1:
        raise ValueError("EICVMB A2: actifs + hors main-d'oeuvre != A1's 6 460 883")
    rows += _rows([(ctx, [v[0], v[2]]) for ctx, v in read],
                  [("outside_labour_force", "not_applicable",
                    "Population hors main d'oeuvre", "count"),
                   ("labour_force", "not_applicable",
                    "Population active (taux d'activité)", "count")],
                  "EICVMB A2")
    return pd.DataFrame(rows)
