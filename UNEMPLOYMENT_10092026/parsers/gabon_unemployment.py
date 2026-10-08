"""Gabon — INSTAT, RGPL-2013 (Recensement Général de la Population et des
Logements), "Résultats globaux" (December 2015), chapter V "L'activité
économique de la population".

THE SAME VOLUME `labour/` READS (its Tableaux 71-72, composition); this module
reads the headline tables that come before them. A census, so the population is
everyone in ordinary households; the working-age population is the LEGAL
working age, 16-65 ("L'âge légal du travail au Gabon est compris entre 16 et 65
ans"), and travels on every row.

* Tableau 61  actifs / inactifs / total (16-65), counts, by milieu x sex
              -> labour_force, outside_labour_force, working_age_population;
* Tableau 62  the same three by province, for men and for women;
* Tableau 63  taux brut d'activité (TBA) by province x milieu x sex
              -> labour_force_participation_rate;
* Tableau 64  taux de chômage of the actifs 16-65, same cut -> unemployment_rate;
* Tableau 67  occupés by sex -> employed.

"NON DÉCLARÉ" IS NOT IN ANY TOPIC. 41 939 of the 1 031 521 aged 16-65 (4%)
have no declared activity status. They are inside the working-age total
(Tableau 61's "Total") but in neither the actifs nor the inactifs, and the TBA
leaves them out of its denominator: 577 242 / (1 031 521 - 41 939) = 58,3, the
published national TBA, where actifs / total would give 56,0. The rate is
collected as published; a user deriving it from these counts must know that.

DEFINITION `not_applicable`. The census classes the actifs as occupés,
chômeurs (who have worked before) and demandeurs d'un premier emploi; its
unemployment rate counts both kinds of job-seeker (16,5 = (66 030 + 29 284) /
577 242). It is self-declared status with no ILO search-and-availability test,
and INSTAT gives it no strict / broad label of its own.

The two kinds of job-seeker are NOT collected as `unemployed` counts: they are
the census's two components, not its unemployed total, and adding them would be
computing. Tableau 65's counts (actifs by type, by milieu) print with every
number broken over two lines in the text layer and are left out; its shares
repeat Tableau 64's arithmetic.

COUNTS USE SPACE THOUSANDS ("1 031 521") and PyMuPDF sometimes runs two cells
onto one line ("498 630 1 031 521"). Each count is read greedily as one
space-grouped number and the reading is held to the tables' own arithmetic:
men + women = ensemble, urbain + rural = Gabon, actifs + inactifs + non
déclaré = total, and the provinces sum to the national row. A mis-split
cannot pass all of them.

The rows are found by their labels in printed order (`_take`), so the wrapped
"Ogooué-" / "Maritime" and "Non" / "déclaré" labels are matched whole.

PERIOD 2013 (census year).

CROSS-CHECK: TBA 58,3 (hommes 70,4, femmes 45,5; urbain 57,7, rural 63,6);
chômage 16,5 (hommes 13,1, femmes 22,1; Ogooué-Ivindo 30,0); actifs 577 242;
inactifs 412 340; population 16-65 1 031 521; occupés 481 928.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd

from . import _common as C

_SURVEY = "Recensement Général de la Population et des Logements (RGPL-2013)"
_BASE, _PERIOD, _REF = "16-65", "2013", "RGPL-2013"
_COUNT = r"\d{1,3}(?: \d{3})+|\d+"
_RATE = r"\d{1,3},\d"

_PROVINCES = ["Estuaire", "Haut-Ogooué", "Moyen-Ogooué", "Ngounié", "Nyanga",
              "Ogooué-Ivindo", "Ogooué-Lolo", "Ogooué-Maritime", "Woleu-Ntem"]
# The 9 columns of 61, 63, 64: (Urbain | Rural | Gabon) x (H, F, Ensemble).
_COLS9 = [dict(loc, **sex)
          for loc in ({"locality": "urban", "locality_label": "Urbain"},
                      {"locality": "rural", "locality_label": "Rural"}, {})
          for sex in ({"sex": "male"}, {"sex": "female"}, {})]


def _label_re(label: str) -> str:
    # "Ogooué-Maritime" prints "Ogooué-\nMaritime"; "Non déclaré" wraps too.
    return r"\s*".join(re.escape(p) for p in re.split(r"(?<=-)|\s+", label) if p)


def _region(text: str, caption: str) -> str:
    ms = list(re.finditer(caption, text))
    if not ms:
        raise ValueError(f"RGPL: {caption!r} not found")
    body = text[ms[-1].end():]                     # the list of tables precedes
    end = re.search(r"\n\s*Tableau \d+ :|\n\s*\d\.\d\.\d? ", body)
    return body[:end.start()] if end else body


def _take(region: str, labels: list[str], n: int, num: str, where: str):
    out, pos = [], 0
    for lab in labels:
        m = re.compile(rf"(?:^|\n)\s*{_label_re(lab)}\s*(?:\n|$)").search(region, pos)
        if not m:
            raise ValueError(f"{where}: row {lab!r} not found")
        vals = re.findall(num, region[m.end():])[:n]
        if len(vals) != n:
            raise ValueError(f"{where}: {lab!r} has {len(vals)} values")
        out.append((lab, [float(v.replace(" ", "").replace(",", ".")) for v in vals]))
        # advance past this row's values
        pos = m.end()
        for _ in range(n):
            pos = re.compile(num).search(region, pos).end()
    return out


def _row(topic, value, label, code, **ctx):
    return C.row(topic=topic, definition="not_applicable", value=value,
                 series_label=label, survey=_SURVEY, period=_PERIOD,
                 reference_period=_REF, frequency="ad_hoc",
                 working_age_base=_BASE, series_code=code, **ctx)


def _check_sexes(vals, where):
    for k in range(0, len(vals), 3):
        if vals[k] + vals[k + 1] != vals[k + 2]:
            raise ValueError(f"{where}: {vals[k]} + {vals[k + 1]} != {vals[k + 2]}")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    with fitz.open(path) as doc:
        text = "\n".join(doc[i].get_text() for i in range(105, 125))
    rows = []

    # --- Tableau 61: counts by milieu x sex ------------------------------
    r = dict(_take(_region(text, r"Tableau 61 : R.partition \(effectif\)"),
                   ["Actifs", "Inactifs", "Non déclaré", "Total"], 9, _COUNT, "T61"))
    for lab, v in r.items():
        _check_sexes(v, f"T61 {lab}")
        for k in range(3):
            if v[k] + v[3 + k] != v[6 + k]:
                raise ValueError(f"T61 {lab}: urbain + rural != Gabon")
    for k in range(9):
        if r["Actifs"][k] + r["Inactifs"][k] + r["Non déclaré"][k] != r["Total"][k]:
            raise ValueError("T61: actifs + inactifs + non déclaré != total")
    for lab, topic, sl in (("Actifs", "labour_force", "Actifs (16-65 ans)"),
                           ("Inactifs", "outside_labour_force", "Inactifs (16-65 ans)"),
                           ("Total", "working_age_population",
                            "Population en âge de travailler (16-65 ans)")):
        for ctx, v in zip(_COLS9, r[lab]):
            rows.append(_row(topic, v, sl, "RGPL-2013 T61", **ctx))

    # --- Tableau 62: counts by province, men then women -------------------
    t62 = _take(_region(text, r"Tableau 62 : R.partition \(effectif\)"),
                _PROVINCES + ["Gabon"], 8, _COUNT, "T62")
    for lab, v in t62:
        for half in (v[:4], v[4:]):
            if half[0] + half[1] + half[2] != half[3]:
                raise ValueError(f"T62 {lab}: actif + inactif + non déclaré != ensemble")
    for k in range(8):
        if sum(v[k] for _, v in t62[:-1]) != t62[-1][1][k]:
            raise ValueError(f"T62: provinces do not sum to Gabon (column {k})")
    nat61 = r["Actifs"][6:8] + r["Inactifs"][6:8]
    if [t62[-1][1][i] for i in (0, 4, 1, 5)] != [nat61[0], nat61[1], nat61[2], nat61[3]]:
        raise ValueError("T62's Gabon row disagrees with T61")
    for lab, v in t62[:-1]:                     # Gabon row = T61's, not repeated
        for sex, half in (("male", v[:4]), ("female", v[4:])):
            for topic, sl, val in (
                    ("labour_force", "Actifs (16-65 ans)", half[0]),
                    ("outside_labour_force", "Inactifs (16-65 ans)", half[1]),
                    ("working_age_population",
                     "Population en âge de travailler (16-65 ans)", half[3])):
                rows.append(_row(topic, val, sl, "RGPL-2013 T62",
                                 geography=lab, sex=sex))

    # --- Tableaux 63 / 64: rates by province x milieu x sex ---------------
    for caption, topic, sl, code in (
            (r"Tableau 63 : Taux brut d.activit", "labour_force_participation_rate",
             "Taux brut d'activité (16-65 ans)", "RGPL-2013 T63"),
            (r"Tableau 64 : Taux de ch.mage \(%\) des actifs",
             "unemployment_rate", "Taux de chômage des actifs de 16-65 ans",
             "RGPL-2013 T64")):
        t = _take(_region(text, caption), _PROVINCES + ["Gabon"], 9, _RATE, code)
        for lab, v in t:
            geo = {} if lab == "Gabon" else {"geography": lab}
            for ctx, val in zip(_COLS9, v):
                rows.append(_row(topic, val, sl, code, **geo, **ctx))

    # --- Tableau 67: occupés by sex ----------------------------------------
    t67 = _take(_region(text, r"Tableau 67 : R.partition par sexe"),
                ["Hommes", "Femmes", "Ensemble"], 1, _COUNT, "T67")
    occ = {lab: v[0] for lab, v in t67}
    if occ["Hommes"] + occ["Femmes"] != occ["Ensemble"]:
        raise ValueError("T67: occupés hommes + femmes != ensemble")
    for lab, sex in (("Hommes", "male"), ("Femmes", "female"), ("Ensemble", "total")):
        rows.append(_row("employed", occ[lab], "Occupés (16-65 ans)",
                         "RGPL-2013 T67", sex=sex))

    # The national TBA and chômage must be the published headline figures.
    nat = {(x["topic"]): x["value"] for x in rows
           if x["geography"] == "Total country" and x["sex"] == "total"
           and x["locality"] == "all" and x["measure"] == "rate"}
    if nat != {"labour_force_participation_rate": 58.3, "unemployment_rate": 16.5}:
        raise ValueError(f"RGPL: national rates read {nat}")
    return pd.DataFrame(rows)
