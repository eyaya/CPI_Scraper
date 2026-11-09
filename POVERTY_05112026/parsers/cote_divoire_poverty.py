"""Côte d'Ivoire -- monetary-poverty layout (ANStat, Profil de pauvreté 2021).

EHCVM 2021 (collected Nov 2021 - Jul 2022), chapter 3. National line 369 516
FCFA per person per year (1 012 FCFA a day); welfare = consumption per capita.

THE TEXT-LAYER TRAP: every other page carries the previous page's content
placed OFF-PAGE (negative x). The engine reads only inside the page box --
without that, Tableau 3-3's regions interleave with Tableau 3-2's.

Collected:
  3-1  milieu (Abidjan urbain / Autre urbain / Rural / Total): P0, P1, P2, the
       contribution of each to all three, population share
  3-2  33 regions: population share only (their P0 is read from 3-3 with P1/P2)
  3-3  regions + Rural/Urbain/Total, P0 P1 P2 for 2018 AND 2021. The 2018
       columns are the EHCVM 2018/19 estimates as this report republishes them.
  3-4..3-7  P0 and population share by household size, household type, sex /
       literacy / education / marital status / age of the head, and literacy
       and education of individuals 15+, each for Rural, Urbain and Total.
Not collected: Totals of the characteristic tables (they repeat 3-1), the
Variation columns (derived), counts of population, Tableau 3-8 onwards
(enrolment, health -- not poverty measures).

CROSS-CHECK (verbatim): P0 37,5 / P1 10,4 / P2 4,1 (2021); 39,4 / 11,6 / 4,7
(2018); rural 54,4, urban 22,2; Bounkani 71,6, Abidjan 6,8; female-headed 32,4.
"""
from __future__ import annotations

from ._vocab import label_rows, loc3_p0_pop_part
from .poverty_tables import make_parser

_P0P1P2 = lambda year, survey, ref: [  # noqa: E731
    {"metric": m, "period": year, "survey": survey, "reference_period": ref}
    for m in ("headcount", "gap", "severity")]
_2018 = _P0P1P2("2018", "EHCVM 2018/19", "2018/19")
_2021 = _P0P1P2("2021", "EHCVM 2021", "2021")
_VAR = [{"skip": True}] * 3

def _block(start, topic, labels, **extra):
    return {"page_contains": ["tableau 3-6", "caractéristiques sociodémographiques du chef"],
            "start": start, "end": r"^Total\b", "columns": loc3_p0_pop_part(),
            "rows": label_rows(topic, labels, **extra)}


LAYOUT = {
    "survey": "EHCVM 2021", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "percent_cells": True,
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil national de pauvreté 2021",
    "line_value": 369516, "line_unit": "XOF per person per year",
    "period": "2021", "reference_period": "2021",
    "tables": [
        {   # Tableau 3-1 -- milieu de résidence
            "page_contains": ["tableau 3-1", "indices et contributions de pauvreté"],
            "exact_numbers": True,
            "columns": [{"metric": "headcount"}, {"metric": "poor_share"},
                        {"metric": "gap"}, {"metric": "gap_contribution"},
                        {"metric": "severity"}, {"metric": "severity_contribution"},
                        {"skip": True}, {"metric": "population_share"}],
            "rows": [
                {"match": r"^Abidjan urbain\b", "topic": "locality",
                 "locality": "other", "locality_label": "Abidjan urbain"},
                {"match": r"^Autre urbain\b", "topic": "locality",
                 "locality": "other", "locality_label": "Autre urbain"},
                {"match": r"^Rural\b", "topic": "locality",
                 "locality": "rural", "locality_label": "Rural"},
                {"match": r"^Total\b"},
            ],
        },
        {   # Tableau 3-2 -- regions: population share of the total
            "page_contains": ["tableau 3-2", "incidence de la pauvreté par région"],
            "columns": [{"skip": True}] * 6 + [{"metric": "population_share"}],
            "row_scan": {"expect_rows": 33, "exclude_labels": ["Total"]},
        },
        {   # Tableau 3-3 -- regions, P0 P1 P2 in 2018 and 2021
            "page_contains": ["tableau 3-3", "dynamique de la pauvreté"],
            "columns": _2018 + _2021 + _VAR,
            "row_scan": {"expect_rows": 33,
                         "exclude_labels": ["Rural", "Urbain", "Total"],
                         "label_map": {"AUTONOME D’ABIDJAN": "ABIDJAN"}},
        },
        {   # Tableau 3-3 -- the national rows. 2021 Rural and Total are already
            # in 3-1, so only Urbain (the two urban strata together) is new.
            "page_contains": ["tableau 3-3", "dynamique de la pauvreté"],
            "columns": _2018 + _2021 + _VAR,
            "rows": [
                {"match": r"^Rural\b", "topic": "locality", "locality": "rural",
                 "locality_label": "Rural", "columns": _2018 + [{"skip": True}] * 6},
                {"match": r"^Urbain\b", "topic": "locality", "locality": "urban",
                 "locality_label": "Urbain"},
                {"match": r"^Total\b", "columns": _2018 + [{"skip": True}] * 6},
            ],
        },
        {   # Tableau 3-4 -- household size
            "page_contains": ["tableau 3-4", "taille du ménage et pauvreté"],
            "join_wrapped_labels": True,
            "columns": loc3_p0_pop_part(),
            "rows": label_rows("household_size", [
                "Une personne", "Deux personnes", "Trois personnes",
                "Quatre personnes", "Cinq personnes", "Six personnes",
                "Sept personnes", "Huit personnes", "Neuf personnes",
                "Dix personnes", "Onze personnes", "Douze personnes",
                "Treize personnes", "Quatorze personnes et plus"]),
        },
        {   # Tableau 3-5 -- household type
            "page_contains": ["tableau 3-5", "typologie du ménage et pauvreté"],
            "columns": loc3_p0_pop_part(),
            "rows": label_rows("household_type", [
                "Ménage unipersonnel", "Couple monogamique sans enfants",
                "Couple monogamique avec enfants", "Couple polygamique sans enfants",
                "Couple polygamique avec enfants", "Ménage monoparental élargi",
                "Ménage monoparental nucléaire", "Ménage monogamique élargie",
                "Ménage polygamique élargie", "Autre ménage élargi"]),
        },
        # Tableau 3-6 -- characteristics of the household head, five blocks
        _block(r"^Sexe du CM", "sex_of_head", []) | {"rows": [
            {"match": r"^Féminin(?=\s)", "topic": "sex_of_head",
             "characteristic": "Féminin", "sex": "female"},
            {"match": r"^Masculin(?=\s)", "topic": "sex_of_head",
             "characteristic": "Masculin", "sex": "male"}]},
        _block(r"^Alphabétisation du CM", "literacy_of_head", ["Non", "Oui"]),
        _block(r"^Niveau d’instruction du CM", "education_of_head",
               ["Aucun", "Primaire", "Secondaire 1", "Secondaire 2", "Supérieur"]),
        _block(r"^Situation matrimoniale du CM", "marital_status_of_head",
               ["Marié", "Non marié"]),
        _block(r"^Tranche d’âge du CM", "age_of_head", [
            "Moins de 25 ans", "26 à 30 ans", "31 à 35 ans", "36 à 40 ans",
            "41 à 45 ans", "46 à 50 ans", "51 à 60 ans", "61 à 70 ans",
            "Plus de 70 ans"]),
        # Tableau 3-7 -- individuals aged 15 and over
        {"page_contains": ["tableau 3-7", "alphabétisation et le niveau d’instruction des individus"],
         "start": r"^Alphabétisation des individus", "end": r"^Total\b",
         "columns": loc3_p0_pop_part(),
         "rows": label_rows("literacy", ["Non", "Oui"], age_group="15 ans et plus")},
        {"page_contains": ["tableau 3-7", "alphabétisation et le niveau d’instruction des individus"],
         "start": r"^Niveau d’instruction des individus", "end": r"^Total\b",
         "join_wrapped_labels": True,
         "columns": loc3_p0_pop_part(),
         "rows": label_rows("education", [
             "Aucun", "Primaire", "Secondaire 1", "Secondaire 2",
             "Supérieure/Post secondaire"], age_group="15 ans et plus")},
    ],
}

parse = make_parser(LAYOUT)
