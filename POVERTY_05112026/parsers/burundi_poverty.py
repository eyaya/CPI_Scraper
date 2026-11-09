"""Burundi -- monetary poverty (ISTEEBU / INSBU).

PRIMARY: EICVMB 2019-2020, module "Profil et déterminants de la pauvreté".
  Tableau 14: P0/P1/P2 for 18 provinces, Urbain/Rural and Ensemble, each at
  HOUSEHOLD and at POPULATION level (columns P0 ménage | P0 population | P1
  ménage | P1 population | P2 ménage | P2 population). Line 576 753 FBU per
  adult equivalent per year (1 580 FBU a day), 2 250 kcal.
  Tableau 20: the national 2020 "enquête témoin" run on the 2014 METHODOLOGY
  for comparability (P0 62,8 / 25,8 / 14,6) -- its own survey, not EICVMB.
EXTRA: ECVMB 2013/2014 "Profil et déterminants de la pauvreté" (Feb 2015).
  Tableau 9: P0/P1/P2 + contributions (CTR) by milieu and 17 provinces, at
  household and population level. Line 636 510 FBU / adult eq. / year.
  Tableau 10: P0/P1/P2 by age, sex, household size, education and branch of
  the head (population level; its non-monetary column is not collected; the
  "Secondaire et +" row prints no values).
  Tableau 16: the 2006 (QUIBB 2006) columns by province -- 2014 repeats T9.
  Line 2006: 475 594 FBU (Tableau 6; the prose says 475 595).

THE 2013/2014 REPORT MIXES DECIMAL MARKS: "Pays 58.3 100,0 21.8 100,0 ...",
and Tableau 10 is almost all points. Read with a comma decimal, "58.3" would
be 583. Its pages are repaired narrowly -- a point BETWEEN TWO DIGITS becomes
a comma -- which is safe because no number in these tables is grouped with a
point (counts use spaces: "636 510").

Province spellings differ between the two reports and are kept as printed:
2014 "Bujumbura. rural" is mapped to "Bujumbura rural" (Tableau 16's
spelling of the same province); "Bujumbura- Mairie" to "Bujumbura-Mairie".
The 2020 "Bujumbura" is the province renamed from Bujumbura Rural (2015
reform) and is NOT merged with it -- an editorial call left to the user.
"""
from __future__ import annotations
import os
import re

import pandas as pd

from ._vocab import label_rows
from . import poverty_tables as T

_PROV20 = ["Bubanza", "Bujumbura", "Bururi", "Cankuzo", "Cibitoke", "Gitega", "Karusi",
           "Kayanza", "Kirundo", "Makamba", "Muramvya", "Muyinga", "Mwaro", "Ngozi",
           "Rutana", "Ruyigi", "Rumonge"]
_PROV14 = ["Bubanza", "Bururi", "Cankuzo", "Cibitoke", "Gitega", "Karusi", "Kayanza",
           "Kirundo", "Makamba", "Muramvya", "Muyinga", "Mwaro", "Ngozi", "Rutana", "Ruyigi"]

_HH = {"unit_of_analysis": "household"}
_PP = {"unit_of_analysis": "person"}


def _rowspec(label, match=None, **attrs):
    return {"match": match or (r"^" + re.escape(label) + r"(?=\s+\d)"), **attrs}


_MIL = lambda: [  # noqa: E731
    _rowspec("Urbain", topic="locality", locality="urban", locality_label="Urbain"),
    _rowspec("Rural", topic="locality", locality="rural", locality_label="Rural")]

# ---------------------------------------------------------------- EICVMB 2020
_E20 = {"survey": "EICVMB 2019-2020", "line_name": "Seuil de pauvreté EICVMB 2019-2020",
        "line_value": 576753, "line_unit": "BIF per adult equivalent per year"}
LAYOUT = {
    **_E20, "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ",", "line_type": "national",
    "line_level": "overall", "period": "2020", "reference_period": "2019-2020",
    "tables": [
        {"page_contains": ["tableau 14", "profil de pauvreté monétaire"],
         "join_wrapped_labels": True, "exact_numbers": True,
         "columns": [{"metric": "headcount", **_HH}, {"metric": "headcount", **_PP},
                     {"metric": "gap", **_HH}, {"metric": "gap", **_PP},
                     {"metric": "severity", **_HH}, {"metric": "severity", **_PP}],
         # The engine's wrapped-label join appends the section heading that
         # follows Rumonge ("Milieu de résidence") to Rumonge's own row.
         "rows": [_rowspec(p, geography=p) for p in _PROV20 if p != "Rumonge"]
                 + [_rowspec("Rumonge", r"^Rumonge(?: Milieu de résidence)?(?=\s+\d)", geography="Rumonge")]
                 + [_rowspec("Bujumbura Mairie", geography="Bujumbura Mairie")]
                 + _MIL() + [_rowspec("Ensemble")]},
        {"page_contains": ["tableau 20", "tendances des indicateurs de pauvreté"],
         "exact_numbers": True,
         "columns": [{"skip": True}, {"metric": "headcount"}, {"skip": True},
                     {"skip": True}, {"metric": "gap"}, {"skip": True},
                     {"skip": True}, {"metric": "severity"}, {"skip": True}],
         "defaults": {"survey": "Enquête témoin 2020 (méthodologie ECVMB 2013/2014)",
                      "line_name": "Seuil de pauvreté (méthodologie ECVMB 2013/2014)",
                      "line_value": "", "line_unit": ""},
         "rows": [_rowspec("National")]},
    ],
}

# ---------------------------------------------------------------- ECVMB 2014
_E14 = {"survey": "ECVMB 2013/2014", "line_name": "Seuil de pauvreté ECVMB 2013/2014",
        "line_value": 636510, "line_unit": "BIF per adult equivalent per year",
        "period": "2014", "reference_period": "2013/2014"}
_CTR6 = lambda u: [{"metric": "headcount", **u}, {"metric": "poor_share", **u},  # noqa: E731
                   {"metric": "gap", **u}, {"metric": "gap_contribution", **u},
                   {"metric": "severity", **u}, {"metric": "severity_contribution", **u}]
_P012 = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}, {"skip": True}]


def _t10(start, end, topic, labels, **attrs):
    return {"page_contains": ["tableau 10", "caractéristiques du chef de ménage"],
            "half": "right", "start": start, "end": end, "exact_numbers": True,
            "columns": _P012, "rows": label_rows(topic, labels, **attrs)}


_L14 = {
    **{k: v for k, v in LAYOUT.items() if k != "tables"}, **_E14,
    "tables": [
        {"page_contains": ["tableau 9", "profil de pauvreté monétaire selon les provinces"],
         "exact_numbers": True, "columns": _CTR6(_HH) + _CTR6(_PP),
         "rows": _MIL() + [_rowspec(p, geography=p) for p in _PROV14]
                 + [_rowspec("Bujumbura rural", r"^Bujumbura\. rural(?=\s+\d)", geography="Bujumbura rural"),
                    _rowspec("Bujumbura-Mairie", r"^Bujumbura- Mairie(?=\s+\d)", geography="Bujumbura-Mairie"),
                    _rowspec("Pays")]},
        _t10(r"^Age du Chef", r"^Sexe du Chef", "age_of_head",
             ["moins 20 ans", "20-24 ans", "25-34 ans", "35-54 ans", "55 ans et +"]),
        {**_t10(r"^Sexe du Chef", r"^Taille du", "sex_of_head", []), "rows": [
            _rowspec("Homme", topic="sex_of_head", characteristic="Homme", sex="male"),
            _rowspec("Femme", topic="sex_of_head", characteristic="Femme", sex="female")]},
        _t10(r"^Taille du", r"^Niveau d", "household_size",
             ["1 personne", "2", "3", "4", "5", "6 pers. et plus"]),
        _t10(r"^Niveau d", r"^Branches", "education_of_head", ["Aucun", "Primaire"]),
        _t10(r"^Branches", r"Pays", "employment_of_head",
             ["Primaire", "Industrie", "Commerce", "Services", "Non préciser"]),
        {"page_contains": ["tableau 16", "tendances des indicateurs de pauvreté"],
         # The table sits beside a prose column whose lines share its rows
         # ("baissé de 2,5 points de Bujumbura rural 63,0 ..."), so labels are
         # matched ANYWHERE on the line and only the numbers after them read.
         "exact_numbers": True,
         "columns": [{"metric": "headcount"}, {"skip": True}, {"skip": True},
                     {"metric": "gap"}, {"skip": True}, {"skip": True},
                     {"metric": "severity"}, {"skip": True}, {"skip": True}],
         "defaults": {"survey": "QUIBB 2006", "period": "2006", "reference_period": "2006",
                      "line_name": "Seuil de pauvreté QUIBB 2006", "line_value": 475594},
         "rows": [_rowspec(p, r"(?<![\w-])" + p + r"(?=\s+\d)", geography=p) for p in _PROV14]
                 + [_rowspec("Bujumbura rural", r"(?<![\w-])Bujumbura rural(?=\s+\d)", geography="Bujumbura rural"),
                    _rowspec("Bujumbura-Mairie", r"(?<![\w-])Bujumbura-Mairie(?=\s+\d)", geography="Bujumbura-Mairie"),
                    _rowspec("Pays", r"(?<![\w-])Pays(?=\s+\d)")]},
    ],
}

_POINT = re.compile(r"(?<=\d)\.(?=\d)")


def _run(cfg: dict, pages: dict) -> pd.DataFrame:
    """make_parser's loop over pages already extracted (and repaired)."""
    period, reference = T._resolve_period(pages["full"], cfg)
    rows, misses = [], []
    for t, tbl in enumerate(cfg["tables"]):
        got, matched = T._parse_table(pages, cfg, tbl, period, reference)
        rows += got
        misses += [f"table[{t}].{r['match']!r}" for i, r in enumerate(tbl.get("rows", []))
                   if i not in matched]
    if misses:
        raise ValueError(f"{len(misses)} row spec(s) matched nothing: {misses[:6]}")
    return pd.DataFrame(rows)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = [_run(LAYOUT, T._pages(path, halves=False) | {"left": [], "right": []})]
    for ex in extras or []:
        if os.path.basename(ex).startswith("ECVMB_2013-2014"):
            pages = T._pages(ex, halves=True)
            pages = {k: [_POINT.sub(",", t) for t in v] for k, v in pages.items()}
            frames.append(_run(_L14, pages))
    return pd.concat(frames, ignore_index=True)
