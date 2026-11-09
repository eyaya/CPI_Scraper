"""Mali -- monetary-poverty layout for the ORIGINAL EHCVM 2018/2019 report
(INSTAT, "Profil et déterminants de la pauvreté au Mali", profil-det-pauv-
2018-2019_pub.pdf). Line 269 485 FCFA per person per year (food 166 443).

WHY A SEPARATE SERIES: the 2021 profile republishes the 2019 round
RE-ESTIMATED -- Tombouctou P0 39,0 there against 46,8 here, P1 10,0 vs 12,20,
Gao 42,5 vs 42,7. Both are published; this report's values carry survey
"EHCVM 2018/2019" and the 2021 report's columns carry "EHCVM 2018/2019
(republié, profil 2021)", so neither overwrites the other.

Every table prints Urbain | Rural | Total (the category's share of each
milieu) then P0 | P1 | P2. Only P0/P1/P2 are read: the shares' universe
(households or persons) is not stated. Milieu rows print 4 numbers (share,
P0, P1, P2).

Collected: 3-3 (9 regions, Urbain, Rural, Ensemble), 3-4 (age, sex, marital
status of the head), 3-5 (household type and size; migrant transfers have no
topic and are skipped), 3-6 (literacy and education of the head), 3-11
(branch, institutional sector and socio-professional category of the head).
Not collected: 3-7..3-10, 3-12..3-17 (health, housing, food security, shocks,
banking), Ensemble rows other than 3-3's (3-11's prints P1 11,68 against
3-3's 11,86 -- a published inconsistency).

CROSS-CHECK (verbatim): 42,1 / 11,86 / 4,62; Kidal 4,5 / 0,47 / 0,08;
Tombouctou 46,8; urban 18,2, rural 50,5; female head 27,6; "9 personnes et
plus" 55,6; Supérieur 2,8; Aide familial 80,6.
"""
from __future__ import annotations
import re

from ._vocab import label_rows
from .poverty_tables import make_parser

_P = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}]
_SIX = [{"skip": True}] * 3 + _P
_FOUR = [{"skip": True}] + _P
_REGIONS = ["Kayes", "Koulikoro", "Sikasso", "Ségou", "Mopti", "Tombouctou", "Gao",
            "Kidal", "Bamako"]


def _t(caption, rows, **kw):
    return {"page_contains": caption, "page_excludes": ["...."], "exact_numbers": True,
            "columns": _SIX, "rows": rows, **kw}


def _act(start, end, labels, prefix):
    rows = label_rows("employment_of_head", labels)
    for r in rows:
        r["characteristic"] = f"{prefix}: {r['characteristic']}"
    return _t(["tableau 3-11", "caractéristiques de l'activité"], rows,
              join_wrapped_labels=True, start=start, end=end)


LAYOUT = {
    "survey": "EHCVM 2018/2019", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil national de pauvreté", "line_value": 269485,
    "line_unit": "XOF per person per year",
    "period": "2018", "reference_period": "2018/2019",
    "tables": [
        _t(["tableau 3-3", "selon la région et le milieu de résidence"],
           [{"match": r"^" + re.escape(r) + r"(?=\s+\d)", "geography": r} for r in _REGIONS]
           + [{"match": r"^Urbain(?=\s+\d)", "topic": "locality", "locality": "urban",
               "locality_label": "Urbain", "columns": _FOUR},
              {"match": r"^Rural(?=\s+\d)", "topic": "locality", "locality": "rural",
               "locality_label": "Rural", "columns": _FOUR},
              # "Ensemble 100 100 100 42,1 11,86 4,62": the three 100s fuse
              # into one space-grouped number (100100100), skipped as the share.
              {"match": r"^Ensemble(?=\s+\d)", "columns": _FOUR}]),
        _t(["tableau 3-4", "situation matrimonial du chef"],
           label_rows("age_of_head", ["15 à 24 ans", "25 à 34 ans", "35 à 54 ans",
                                      "55 à 62 ans", "63 ans et plus"])
           + [{"match": r"^Masculin(?=\s+\d)", "topic": "sex_of_head",
               "characteristic": "Masculin", "sex": "male"},
              {"match": r"^Féminin(?=\s+\d)", "topic": "sex_of_head",
               "characteristic": "Féminin", "sex": "female"}]
           + label_rows("marital_status_of_head", ["Célibataire", "Marie monogame",
                                                   "Marie polygame", "Veuf (ve)", "Divorce",
                                                   "Sépare"])),
        _t(["tableau 3-5", "composition du ménage et les transferts"],
           label_rows("household_type", ["Unipersonnel", "Couples sans enfant",
                                         "Couples avec enfants", "Nucléaire Monoparental",
                                         "Monoparental élargi", "Elargi"])
           + label_rows("household_size", ["1 à 2 personnes", "3 à 4 personnes",
                                           "5 à 6 personnes", "7 à 8 personnes",
                                           "9 personnes et plus"])),
        _t(["tableau 3-6", "statut d’alphabétisation"],
           label_rows("literacy_of_head", ["Oui", "Non"]),
           start=r"^Statut d'alphabétisation", end=r"^Niveau d'instruction"),
        _t(["tableau 3-6", "statut d’alphabétisation"],
           label_rows("education_of_head", ["Aucun", "Primaire", "Secondaire", "Supérieur"]),
           start=r"^Niveau d'instruction", end=r"^Ensemble"),
        _act(r"^Branche activité du CM", r"^Secteur institutionnel",
             ["Agriculture", "Elevage ou pêche", "Industrie ou extraction", "Autre Industrie",
              "BTP", "Commerce", "Restaurant ou Hôtel", "Transport ou Communication",
              "Education ou Santé", "Services personnels.", "Autres services"],
             "Branche d'activité"),
        _act(r"^Secteur institutionnel du CM", r"^Catégorie Socioprofessionnelle",
             ["Etat ou Collectivité locale", "Entreprise publique/ parapublique",
              "Entreprise Privé", "Entreprise associative",
              "Ménage comme employeur de personnel domestique",
              "Organisme international /Ambassade"], "Secteur institutionnel"),
        _act(r"^Catégorie Socioprofessionnelles du CM", r"^Ensemble",
             ["Cadre supérieur", "Cadre moyen/agent de maitrise", "Ouvrier ou employé qualifié",
              "Ouvrier ou employé non qualifié", "Manœuvre, aide-ménagère",
              "Stagiaire ou Apprenti rémunéré", "Stagiaire ou Apprenti non rémunéré",
              "Aide familial", "Travailleur pour compte propre", "Patron"],
             "Catégorie socioprofessionnelle"),
    ],
}

parse = make_parser(LAYOUT)
