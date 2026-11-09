"""Burkina Faso -- monetary-poverty layout (INSD, "Diagnostic de la pauvreté",
EHCVM 2021).

National line 247 806 FCFA per person per year (food part 142 009); welfare =
consumption per person (no equivalence scale, as the report stresses).

THREE LINES ARE PRINTED, kept apart by line_level / line_name:
  overall   P0 vs the total line                         (2-3, 3-2, 3-6..3-8, 2-10)
  extreme   TOTAL consumption vs the FOOD line            (2-8, 3-4)
  other     "pauvreté alimentaire": FOOD consumption vs the food line (2-7, 3-3)
            -- a different welfare measure, hence its own line name.

Every table has the columns P0 | contribution | P1 | P2 | consumption per head
(the last skipped). Collected: 2-1 (number of poor, overall and extreme), 2-3
milieu (Urbain, Ouaga+Bobo, Autres urbain, Rural, national), 2-7 / 2-8 the same
for the food and extreme lines, 2-10 HOUSEHOLD-level rates by milieu, sex of
head and household size, 3-2 / 3-3 / 3-4 the 13 regions on the three lines,
3-6 sex / household size / marital status / age of the head, 3-7 literacy,
education and diploma of the head, 3-8 five employment cuts of the head.
Not collected: 2-2's P1/P0 ratio, 2-4 / 3-1 (consumption), 2-5 / 3-5 / 2-6
(inequality, deciles), 2-9 (decomposition), the region tables' national rows
(they repeat 2-3 / 2-7 / 2-8), 3-7's DEUG / Maîtrise rows (printed "-"), and the
socio-professional block's "Inactif" row, which runs onto the next page
without its block heading (it repeats the "Inactifs" of the block above).

CROSS-CHECK (verbatim): P0 43,2 / P1 13,0 / P2 5,4; 9 292 224 poor; extreme
11,9 (2 568 949); food poverty 53,3; rural 52,7, urban 16,6; Sahel 76,1, Centre
8,0; households 35,0; female head 47,5; chômeur 69,1.
"""
from __future__ import annotations
import re

from ._vocab import label_rows

_FIVE = [{"metric": "headcount"}, {"metric": "poor_share"}, {"metric": "gap"},
         {"metric": "severity"}, {"skip": True}]
_EXT = {"line_level": "extreme", "line_name": "Seuil alimentaire (extrême pauvreté)",
        "line_value": 142009, "line_unit": "XOF per person per year"}
_FOOD = {"line_level": "other",
         "line_name": "Seuil alimentaire, consommation alimentaire (pauvreté alimentaire)",
         "line_value": 142009, "line_unit": "XOF per person per year"}
_HH = {"unit_of_analysis": "household"}

_REGIONS = [("Boucle du Mouhoun", r"^Boucle du\s+Mouhoun"), ("Cascades", r"^Cascades"),
            ("Centre", r"^Centre(?=\s+\d)"), ("Centre-Est", r"^Centre-Est"),
            ("Centre-Nord", r"^Centre-Nord"), ("Centre-Ouest", r"^Centre-Ouest"),
            ("Centre-Sud", r"^Centre-Sud"), ("Est", r"^Est(?=\s+\d)"),
            ("Hauts-Bassins", r"^Hauts\s+Bassins"), ("Nord", r"^Nord(?=\s+\d)"),
            ("Plateau-Central", r"^Plateau-\s?Central"), ("Sahel", r"^Sahel"),
            ("Sud-Ouest", r"^Sud-Ouest")]


def _milieu(ouaga="Ouaga+Bobo"):
    # "Burkina Faso" / numbers / "Milieu de résidence": the wrap rejoin folds the
    # heading into the label, so match the start only (numbers follow the match).
    return [{"match": r"^Burkina Faso\b"},
            {"match": r"^Urbain(?=\s+\d)", "topic": "locality", "locality": "urban",
             "locality_label": "Urbain"},
            {"match": r"^" + re.escape(ouaga) + r"(?=\s+\d)", "topic": "locality",
             "locality": "other", "locality_label": "Ouaga+Bobo"},
            {"match": r"^Autres urbain(?=\s+\d)", "topic": "locality", "locality": "other",
             "locality_label": "Autres urbain"},
            {"match": r"^Rural(?=\s+\d)", "topic": "locality", "locality": "rural",
             "locality_label": "Rural"}]


def _regions(caption, line):
    return {"page_contains": caption, "join_wrapped_labels": True, "exact_numbers": True,
            "start": r"^Selon les régions administratives", "columns": _FIVE,
            "defaults": line,
            "rows": [{"match": pat + r"(?=\s+\d)" if "(?=" not in pat else pat, "geography": g}
                     for g, pat in _REGIONS]}


def _block(start, end, topic, labels, prefix="", **extra):
    rows = label_rows(topic, labels, **extra)
    for r in rows:
        if prefix:
            r["characteristic"] = f"{prefix}: {r['characteristic']}"
    t = {"page_contains": ["tableau 3- 8", "emploi du chef de ménage"], "start": start,
         "join_wrapped_labels": True, "exact_numbers": True, "columns": _FIVE, "rows": rows}
    if end:
        t["end"] = end
    return t


_T37 = ["tableau 3- 7", "niveau d’instruction du ménage"]
_T36 = ["tableau 3- 6", "caractéristiques démographiques du ménage"]

LAYOUT = {
    "survey": "EHCVM 2021/2022", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté", "line_value": 247806,
    "line_unit": "XOF per person per year",
    "period": "2021", "reference_period": "2021/2022",
    "tables": [
        {   # 2-1: extreme P0 | P0 | extreme poor | poor | population | sample
            "page_contains": ["tableau 2- 1", "indicateurs de pauvreté au burkina faso en 2021"],
            "exact_numbers": True,
            "columns": [{"skip": True}, {"skip": True},
                        {"metric": "poor_count", **_EXT}, {"metric": "poor_count"},
                        {"skip": True}, {"skip": True}],
            "rows": [{"match": r"^Indicateur(?=\s+\d)"}]},
        {"page_contains": ["tableau 2- 3", "par milieu 2021"], "join_wrapped_labels": True,
         "exact_numbers": True, "columns": _FIVE, "rows": _milieu()},
        {"page_contains": ["tableau 2- 7", "pauvreté alimentaire par milieu"],
         "exact_numbers": True, "columns": _FIVE, "defaults": _FOOD, "rows": _milieu()},
        {"page_contains": ["tableau 2- 8", "extrême pauvreté par milieu"],
         "exact_numbers": True, "columns": _FIVE, "defaults": _EXT,
         "rows": _milieu("Ouaga et Bobo")},
        {"page_contains": ["tableau 2- 10", "pauvreté au niveau des ménages"],
         "join_wrapped_labels": True, "exact_numbers": True, "columns": _FIVE, "defaults": _HH,
         "rows": [r for r in _milieu() if "Ouaga" not in r["match"] and "Autres" not in r["match"]]
         + [{"match": r"^Homme(?=\s+\d)", "topic": "sex_of_head", "characteristic": "Homme",
             "sex": "male"},
            {"match": r"^Femme(?=\s+\d)", "topic": "sex_of_head", "characteristic": "Femme",
             "sex": "female"}]
         # Unanchored: once joined, "1 à 4 personnes 16,7 ..." starts with a
         # digit and the wrap rejoin prefixes the heading "Selon la taille du
         # ménage" to it.
         + [dict(r, match=r["match"].replace("^", "(?:^|ménage )", 1))
            for r in label_rows("household_size", ["1 à 4 personnes", "5 à 6 personnes",
                                                   "7 à 8 personnes", "9 à 11 personnes",
                                                   "12 personnes et +"])]},
        _regions(["tableau 3- 2", "selon la région de résidence"], {}),
        _regions(["tableau 3- 3", "pauvreté alimentaire selon les régions"], _FOOD),
        _regions(["tableau 3- 4", "extrême pauvreté selon les régions"], _EXT),
        # 3-6 -- demographics of the head
        {"page_contains": _T36, "start": r"^Sexe du chef de ménage", "end": r"^Nombre de personnes",
         "exact_numbers": True, "columns": _FIVE,
         "rows": [{"match": r"^Masculin(?=\s+\d)", "topic": "sex_of_head",
                   "characteristic": "Masculin", "sex": "male"},
                  {"match": r"^Féminin(?=\s+\d)", "topic": "sex_of_head",
                   "characteristic": "Féminin", "sex": "female"}]},
        {"page_contains": _T36, "start": r"^Nombre de personnes", "end": r"^Selon le statut",
         "exact_numbers": True, "columns": _FIVE,
         "rows": label_rows("household_size", ["1-4 pers", "5-6 pers", "7-8 pers", "9-11 pers",
                                               "12 pers et +"])},
        {"page_contains": _T36, "start": r"^Selon le statut matrimonial", "end": r"^Selon l'âge",
         "exact_numbers": True, "columns": _FIVE,
         "rows": label_rows("marital_status_of_head", ["Célibataire", "Marié monogame",
                                                       "Marié polygame", "Union libre",
                                                       "Veuf (ve)", "Divorcé/séparé"])},
        {"page_contains": _T36, "start": r"^Selon l'âge du chef", "exact_numbers": True,
         "columns": _FIVE,
         "rows": label_rows("age_of_head", ["Moins de 24 ans", "25-34 ans", "35-44 ans",
                                            "45-54 ans", "55-64 ans", "65 ans et +"])},
        # 3-7 -- human capital of the head
        {"page_contains": _T37, "start": r"^Statut d'alphabétisation", "end": r"^Niveau d'instruction",
         "exact_numbers": True, "columns": _FIVE,
         "rows": label_rows("literacy_of_head", ["Analphabète", "Alphabète"])},
        {"page_contains": _T37, "start": r"^Niveau d'instruction du chef", "end": r"^Diplôme",
         "exact_numbers": True, "columns": _FIVE,
         "rows": label_rows("education_of_head", ["Aucun", "Primaire", "Post primaire",
                                                  "Secondaire", "Supérieur"])},
        {"page_contains": _T37, "start": r"^Diplôme le plus élevé", "exact_numbers": True,
         "columns": _FIVE,
         "rows": [dict(r, characteristic="Diplôme: " + r["characteristic"])
                  for r in label_rows("education_of_head", ["Aucun", "CEP", "BEPC-CAP-BT-BAC"])]},
        # 3-8 -- employment of the head, five blocks
        _block(r"^Selon le statut d'activité", r"^Selon l'activité principal", "employment_of_head",
               ["Occupé", "Travailleur familial cherchant emploi",
                "Travailleur familial ne cherchant emploi", "Chômeur", "Inactifs"],
               "Statut d'activité"),
        _block(r"^Selon l'activité principal", r"^Selon le type d'emploi", "employment_of_head",
               ["Occupé", "Travailleur familial", "Non occupé"], "Activité principale (12 mois)"),
        _block(r"^Selon le type d'emploi", r"^Selon la catégorie", "employment_of_head",
               ["Salarié", "Non salarié", "Inactifs"], "Type d'emploi"),
        _block(r"^Selon la catégorie socioprofessionnelle", None, "employment_of_head",
               ["Cadre supérieur et moyen", "Ouvrier", "Manoeuvre, stagiaire, aide familial",
                "Travailleur compte propre", "Patron"], "Catégorie socioprofessionnelle"),
        dict(_block(r"^Selon la branche d’activité", None, "employment_of_head",
                    ["Agriculture", "Elevage/pêche", "Indust. extr.", "Autr. indust.", "BTP",
                     "Commerce", "Restaurant/Hotel", "Trans./Comm.", "Education/Sante",
                     "Services perso.", "Autre. services", "Inactif"], "Branche d'activité"),
             page_contains=["selon la branche d’activité du chef de ménage", "agriculture"]),
    ],
}

_PAGE_FIXES = [
    # 2-10 prints "1 à 4 personnes" on its own line above its numbers; the
    # engine's wrap rejoin only takes digit-free labels, so join these here.
    (re.compile(r"^((?:\d+ à \d+|12) personnes(?: et \+)?)\n(?=\d)", re.M), r"\1 "),
]


def parse(path: str):
    """`make_parser`, with the page fixes above applied first."""
    import pandas as pd
    from . import poverty_tables as T
    pages = T._pages(path, halves=False)
    for pat, rep in _PAGE_FIXES:
        pages["full"] = [pat.sub(rep, p) for p in pages["full"]]
    period, ref = T._resolve_period(pages["full"], LAYOUT)
    rows, misses = [], []
    for i, tbl in enumerate(LAYOUT["tables"]):
        got, matched = T._parse_table(pages, LAYOUT, tbl, period, ref)
        rows += got
        misses += [f"table[{i}].{r['match']!r}" for j, r in enumerate(tbl.get("rows", []))
                   if j not in matched]
    if misses:
        raise ValueError(f"Burkina Faso: {len(misses)} row spec(s) matched nothing: {misses}")
    return pd.DataFrame.from_records(rows)
