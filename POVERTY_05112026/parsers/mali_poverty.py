"""Mali -- monetary-poverty layout (INSTAT, "Profil et déterminants de la
pauvreté au Mali en 2021", EHCVM 2021-2022).

Fieldwork 23 Oct - 24 Dec 2021 and 11 Apr - 24 Jul 2022 -> period 2021,
reference "2021/2022". National line 277 173 FCFA per person per year (food
172 251); welfare = consumption per person.

Most tables print BOTH EHCVM rounds side by side:
    Incidence 2019 | 2021 | Profondeur 2019 | 2021 | Sévérité 2019 | 2021
"2019" is the EHCVM 2018/2019 round (fieldwork 2018-19; Tableau 2-4 labels
its line "2019", 269 485 FCFA). Filed as period 2018, reference
"2018/2019", like the other WAEMU countries' first round.

Collected: 3-3 (9 regions, Urbain / Rural / Ensemble), 3-4 (age, sex,
marital status of the head), 3-5 (household composition and size), 3-6
(literacy and education of the head), 3-11 (2021 only: P0/P1/P2 by branch,
institutional sector and socio-professional category of the head; the
distribution columns are skipped).
Not collected: 3-7..3-9 (health), 3-10 (disability: no topic; its Ensemble
row also prints "42,1 42,1 45,5 ..." -- shifted), 3-12..3-20 (housing, food
security, shocks, banking, Covid), 4-x (inequality), Ensemble rows of the
characteristic tables (repeat 3-3).

CROSS-CHECK (verbatim): 2021 P0 45,5 / P1 12,9 / P2 5,0; 2019 42,1 / 11,9 /
4,6; Mopti 57,5, Kidal 4,9, Bamako 15,8; rural 52,5, urban 21,3; female head
31,8; polygamous head 58,4; agriculture 60,9.
"""
from __future__ import annotations
import re

from ._vocab import label_rows
from .poverty_tables import make_parser

# The 2019 round AS REPUBLISHED here: re-estimated (Tombouctou P0 39,0 here vs
# 46,8 in the original 2018-2019 report, which mali_2018_2019_poverty reads).
_R18 = {"period": "2018", "survey": "EHCVM 2018/2019 (republié, profil 2021)",
        "reference_period": "2018/2019",
        "line_value": 269485}
_R21 = {"period": "2021"}
_SIX = [{"metric": "headcount", **_R18}, {"metric": "headcount", **_R21},
        {"metric": "gap", **_R18}, {"metric": "gap", **_R21},
        {"metric": "severity", **_R18}, {"metric": "severity", **_R21}]

_REGIONS = ["Kayes", "Koulikoro", "Sikasso", "Ségou", "Mopti", "Tombouctou", "Gao",
            "Kidal", "Bamako"]


def _t(caption, rows, **kw):
    return {"page_contains": caption, "exact_numbers": True, "columns": _SIX,
            "rows": rows, **kw}


_T34 = ["tableau 3-4", "situation matrimonial du"]
_T35 = ["tableau 3-5", "composition du ménage"]
_T36 = ["tableau 3-6", "statut d’alphabétisation"]
_T311 = ["caractéristiques de l'activité", "urbain (%) rural (%) total (%)"]
_THREE = [{"skip": True}] * 3 + [{"metric": "headcount"}, {"metric": "gap"},
                                 {"metric": "severity"}]


def _act(start, end, labels, prefix):
    rows = label_rows("employment_of_head", labels)
    for r in rows:
        r["characteristic"] = f"{prefix}: {r['characteristic']}"
    t = {"page_contains": _T311, "join_wrapped_labels": True, "exact_numbers": True,
         "columns": _THREE, "rows": rows}
    if start:
        t["start"] = start
    if end:
        t["end"] = end
    return t


LAYOUT = {
    "survey": "EHCVM 2021-2022", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil national de pauvreté", "line_value": 277173,
    "line_unit": "XOF per person per year",
    "period": "2021", "reference_period": "2021/2022",
    "tables": [
        _t(["tableau 3-3", "selon la région et le milieu de résidence"],
           [{"match": r"^" + re.escape(r) + r"(?=\s+\d)", "geography": r} for r in _REGIONS]
           + [{"match": r"^Urbain(?=\s+\d)", "topic": "locality", "locality": "urban",
               "locality_label": "Urbain"},
              {"match": r"^Rural(?=\s+\d)", "topic": "locality", "locality": "rural",
               "locality_label": "Rural"},
              {"match": r"^Ensemble(?=\s+\d)"}]),
        _t(_T34, label_rows("age_of_head", ["15 à 24 ans", "25 à 34 ans", "35 à 54 ans",
                                            "55 à 62 ans", "63 ans et plus"])
           + [{"match": r"^Homme(?=\s+\d)", "topic": "sex_of_head", "characteristic": "Homme",
               "sex": "male"},
              {"match": r"^Femme(?=\s+\d)", "topic": "sex_of_head", "characteristic": "Femme",
               "sex": "female"}]
           + label_rows("marital_status_of_head", ["Célibataire", "Marie monogame",
                                                   "Marie polygame", "Veuf (vé)", "Divorce",
                                                   "Sépare"])),
        _t(_T35, [{"match": r"^Unipersonnel(?=\s+\d)", "topic": "household_type",
                   "characteristic": "Unipersonnel"},
                  {"match": r"^Couples sans enfant\b", "topic": "household_type",
                   "characteristic": "Couples sans enfant (Nucléaire sans enfant)"},
                  {"match": r"^Couples avec enfants\b", "topic": "household_type",
                   "characteristic": "Couples avec enfants (Nucléaire avec enfant)"},
                  {"match": r"^Nucléaire Monoparental\b", "topic": "household_type",
                   "characteristic": "Nucléaire Monoparental"},
                  {"match": r"^Monoparental élargi(?=\s+\d)", "topic": "household_type",
                   "characteristic": "Monoparental élargi"},
                  {"match": r"^Elargi(?=\s+\d)", "topic": "household_type",
                   "characteristic": "Elargi"}]
           # "1 à 2 personnes ..." begins with a digit, so the wrap rejoin
           # glues the heading "Tailles du ménage" in front of it.
           + [dict(r, match=r["match"].replace("^", "(?:^|ménage )", 1))
              for r in label_rows("household_size", ["1 à 2 personnes", "3 à 4 personnes",
                                                     "5 à 6 personnes", "7 à 8 personnes",
                                                     "9 personnes ou plus"])],
           join_wrapped_labels=True),
        _t(_T36, label_rows("literacy_of_head", ["Oui", "Non"]),
           start=r"^Statut d'alphabétisation", end=r"^Niveau d'instruction"),
        _t(_T36, label_rows("education_of_head", ["Aucun", "Primaire", "Secondaire",
                                                  "Supérieur"]),
           start=r"^Niveau d'instruction du CM"),
        # 3-11 -- 2021 only; the CSP block continues on the next page under a
        # repeated header, so it is not bounded by its heading.
        _act(r"^Branche activité du CM", r"^Secteur institutionnel",
             ["Agriculture", "Elevage/pèche", "Industrie /extraction", "Autres Industrie", "BTP",
              "Commerce", "Restaurant/Hôtel", "Transport/Commun", "Education/Sante",
              "Services personnels.", "Autres services"], "Branche d'activité"),
        _act(r"^Secteur institutionnel du CM", r"^Catégorie socioprofessionnelle",
             ["Etat/Collectivité locale", "Entreprise publique/ parapublique", "Entreprise Privé",
              "Entreprise associative", "Ménage comme employeur de personnel domestique",
              "Organisme international"], "Secteur institutionnel"),
        _act(None, None,
             ["Cadre supérieur", "Cadre moyen/agent de maitrise",
              "Ouvrier ou employé non qualifié", "Manœuvre, aide-ménagère",
              "Stagiaire ou Apprenti rémunère", "Stagiaire ou Apprenti non rémunère",
              "Aide familial", "Travailleur pour compte propre", "Patron"],
             "Catégorie socioprofessionnelle"),
    ],
}

parse = make_parser(LAYOUT)
