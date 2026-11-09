"""Gabon -- EGEP 2005 poverty, as tabulated in the DGS Annuaire statistique 2014.

Source: chapter "Population active, revenus, conditions de vie des ménages et
pauvreté" of DGS's Annuaire statistique du Gabon 2014 (Wayback `id_` copy of
dgstat.ga's own file). Its Tableau III.5.1.3 "Caractéristiques
sociodémographiques de la Pauvreté des Ménages, en 2005" (EGEP 2005, sources
"EGEP 2005 et DSCRP") prints, in ONE column order:

    Incidence | Profondeur | Sévérité | Répartition de la population | Répartition des pauvres

with a point decimal. The national line is 429 336 FCFA per person per year
(Libreville's line, p. 31-32). Person level: the Total (32,7) is the EGEP 2005
headcount the chapter's prose rounds to "33% de Gabonais".

Collected: milieu, the six survey regions (Libreville, Port-Gentil, Nord, Sud,
Est, Ouest -- filed as locality "other" strata, the convention the EGEP 2 2017
module uses for its strata), sex, age, education and socio-economic group of
the head, and the head's pluri-activity (filed under employment_of_head with a
"Pluri-activité:" prefix so its "Sans emploi" can never collide with a GSE
label).
NOT collected: nationality of the head and number of earners (no topic);
Tableau III.5.1.1-2 (the same figures, letter-spaced text layer); III.5.1.4
(EDML 2003 Libreville income structure, a different survey and quantity).

CROSS-CHECK (verbatim): Total 32.7 / 10.0 / 4.3; Urbain 29.8, Rural 44.6;
Libreville 22.8 / 5.8 / 2.3; Sud 53.9; Femme 36.9; Supérieur 11.3; Cadre 10.3.
Population shares of regions sum to 99.9; shares of the poor to 100.1.
"""
from __future__ import annotations

from ._vocab import label_rows
from .poverty_tables import make_parser

_COLS = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"},
         {"metric": "population_share"}, {"metric": "poor_share"}]


def _block(start, end, rows):
    return {"page_contains": ["tableau iii.5.1.3"], "start": start, "end": end,
            "exact_numbers": True, "columns": _COLS, "rows": rows}


def _strata(labels):
    out = []
    for lab, printed in labels:
        out.append({"match": r"^" + printed + r"(?=\s+\d)", "topic": "locality",
                    "locality": "other", "locality_label": lab})
    return out


LAYOUT = {
    "survey": "EGEP 2005", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall",
    "line_name": "Ligne nationale de pauvreté EGEP 2005",
    "line_value": 429336, "line_unit": "XAF per person per year",
    "period": "2005", "reference_period": "2005",
    "tables": [
        _block(r"^Milieu de résidence", r"^Région de résidence", [
            {"match": r"^Urbain(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Urbain"},
            {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"}]),
        _block(r"^Région de résidence", r"^Sexe du chef", _strata([
            ("Libreville", "Libreville"), ("Port-Gentil", r"Port-\s?Gentil"), ("Nord", "Nord"),
            ("Sud", "Sud"), ("Est", "Est"), ("Ouest", "Ouest")])),
        _block(r"^Sexe du chef", r"^Nationalité du chef", [
            {"match": r"^Homme(?=\s)", "topic": "sex_of_head", "characteristic": "Homme", "sex": "male"},
            {"match": r"^Femme(?=\s)", "topic": "sex_of_head", "characteristic": "Femme", "sex": "female"}]),
        _block(r"^Age du chef", r"^Instruction du chef", [
            {"match": r"^Moins de 30 ans(?=\s)", "topic": "age_of_head", "characteristic": "Moins de 30 ans"},
            {"match": r"^30 à 39 ans(?=\s)", "topic": "age_of_head", "characteristic": "30 à 39 ans"},
            {"match": r"^40\s?à 49 ans(?=\s)", "topic": "age_of_head", "characteristic": "40 à 49 ans"},
            {"match": r"^50 à 59 ans(?=\s)", "topic": "age_of_head", "characteristic": "50 à 59 ans"},
            {"match": r"^60 et plus(?=\s)", "topic": "age_of_head", "characteristic": "60 et plus"}]),
        _block(r"^Instruction du chef", r"^GSE du chef",
               label_rows("education_of_head", ["Aucun", "Primaire", "Secondaire 1",
                                                "Secondaire 2", "Supérieur"])),
        _block(r"^GSE du chef", r"^Pluri-activité du chef",
               label_rows("employment_of_head", ["Cadre", "Employés/ouvriers", "Autres salariés",
                                                 "Independant agricole", "Independant non agricole",
                                                 "Chomeurs", "Inactifs"])),
        _block(r"^Pluri-activité du chef", r"^Nombre d'actifs", [
            {"match": r"^" + lab + r"(?=\s+\d)", "topic": "employment_of_head",
             "characteristic": "Pluri-activité: " + lab}
            for lab in ("Sans emploi", "Activité unique", "Pluri-actif")]),
        _block(r"^Trois actifs et plus", r"^Sources", [{"match": r"^Total(?=\s)"}]),
    ],
}

parse = make_parser(LAYOUT)
