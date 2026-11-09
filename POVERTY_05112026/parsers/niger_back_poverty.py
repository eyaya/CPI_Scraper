"""Niger -- INS back-rounds, from INS's own files on stat-niger.org.

parse (ECVMA 2011) -- "Profil et déterminants de la pauvreté au Niger 2011"
    (wp-content/uploads/2020/06/Profil_Pauvrete_2011_ECVMA.pdf). National line
    182 635,2 FCFA per person per year (Niamey prices; zones deflated).
    Tableau 3 (milieu, 8 regions), 4 (household size, sex / age / education of
    the head), 5 (branch, CSP, institutional sector of the head); columns P0 |
    P1 | P2 | % of population | % of the poor. Survey "ECVMA 2011 (profil 2011)":
    the EHCVM 2021 profile's trend table republishes ECVMA 2011 by milieu
    under "ECVMA 2011" with one value that differs (urban population share
    17,0 there vs 17,3 here), so the two are kept apart.
parse_quibb -- "Profil de pauvreté" from QUIBB 2005 (Annuaire/QUIBB/
    Profil de pauvrete QUIBB.pdf, Wayback `id_` copy). Lines are MILIEU-
    SPECIFIC (144 750 FCFA urban, 105 827 rural) -- no single national line,
    so line_value is blank. Tableau 3.3 (regions P0 P1 P2), 3.4 (P0 by
    Niamey / Autres villes / Rural / Niger), 3.5 (HOUSEHOLD P0 by sex of the
    head), 3.6 (person P0 by sex of the head), 3.7 (P0 by household size);
    in 3.4-3.7 only the "Pauvres" column is read (the other is its complement).
    Zinder and Diffa form one stratum ("Zinder-Diffa"), as printed.

CROSS-CHECK (verbatim): 2011 48,2 / 13,1 / 4,9; Maradi 57,8; Niamey 10,2;
female head 40,3; Secondaire 2+ 1,7; QUIBB 2005 62,1; Maradi 79,7 / 35,1 /
19,0; Niamey 27,1; households headed by women 43,4.
"""
from __future__ import annotations
import re

import pandas as pd

from . import poverty_tables as T
from ._vocab import label_rows

_FIVE = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"},
         {"metric": "population_share"}, {"metric": "poor_share"}]


def _act(prefix, labels):
    rows = label_rows("employment_of_head", labels)
    for r in rows:
        r["characteristic"] = f"{prefix}: {r['characteristic']}"
    return rows


LAYOUT = {
    "survey": "ECVMA 2011 (profil 2011)", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall", "line_name": "Seuil global de pauvreté",
    "line_value": 182635.2, "line_unit": "XOF per person per year",
    "period": "2011", "reference_period": "2011",
    "tables": [
        {"page_contains": ["tableau 3. indicateurs de pauvreté selon la région"], "exact_numbers": True,
         "start": r"^Tableau 3\.", "end": r"^Source", "columns": _FIVE,
         "rows": [{"match": r"^Urbain(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Urbain"},
                  {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
                  {"match": r"^Ensemble(?=\s)"}]
         + [{"match": rf"^{g}(?=\s)", "geography": g} for g in
            ("Agadez", "Diffa", "Dosso", "Maradi", "Tahoua", "Tillabéry", "Zinder", "Niamey")]},
        {"page_contains": ["tableau 4. indicateurs de pauvreté selon les caractéristiques socio"],
         "exact_numbers": True, "start": r"^Taille du ménage", "end": r"^Genre du chef", "columns": _FIVE,
         "rows": label_rows("household_size", ["Une personne", "2 personnes", "3 à 5 personnes",
                                               "6 à 9 personnes", "10 à 14 personnes", "15 pers, et +"])},
        {"page_contains": ["tableau 4. indicateurs de pauvreté selon les caractéristiques socio"],
         "exact_numbers": True, "start": r"^Genre du chef", "end": r"^Age du chef", "columns": _FIVE,
         "rows": [{"match": r"^Masculin(?=\s)", "topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"},
                  {"match": r"^Féminin(?=\s)", "topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}]},
        {"page_contains": ["tableau 4. indicateurs de pauvreté selon les caractéristiques socio"],
         "exact_numbers": True, "start": r"^Age du chef", "end": r"^Education du chef", "columns": _FIVE,
         "rows": label_rows("age_of_head", ["Moins de 25 ans", "25-34 ans", "35-44 ans", "45-54 ans",
                                            "55-64 ans", "65 ans et +"])},
        # Education runs onto the next page under a repeated header.
        {"page_contains": ["incidence de la profondeur sévérité de % de la % de"], "exact_numbers": True,
         "columns": _FIVE,
         "rows": label_rows("education_of_head", ["Sans instruction", "Primaire", "Secondaire 1",
                                                  "Secondaire 2+"])},
        {"page_contains": ["tableau 5. indicateurs de pauvreté selon les caractéristiques du marché"],
         "exact_numbers": True, "start": r"^Branche du chef", "end": r"^CSP du chef", "columns": _FIVE,
         "rows": _act("Branche d'activité", ["Agriculture", "Elevage/Sylv,/pêche", "Industrie",
                                             "Commerce", "Services", "Sans-emploi"])},
        {"page_contains": ["tableau 5. indicateurs de pauvreté selon les caractéristiques du marché"],
         "exact_numbers": True, "start": r"^CSP du chef", "end": r"^Secteur institutionnel", "columns": _FIVE,
         "rows": _act("Catégorie socioprofessionnelle", ["Cadre", "Autres salariés", "Patron",
                                                         "Travailleur pour CP", "Autres dépendants",
                                                         "Sans-emploi"])},
        {"page_contains": ["tableau 5. indicateurs de pauvreté selon les caractéristiques du marché"],
         "exact_numbers": True, "start": r"^Secteur institutionnel", "end": r"^Ensemble", "columns": _FIVE,
         "rows": _act("Secteur institutionnel", ["Secteur public", "Grande entreprise",
                                                 "Entreprise individuelle", "Ménage", "Sans-emploi"])},
    ],
}


def _run(path, cfg, per, ref, fixes=()):
    pages = T._pages(path, halves=False)
    for pat, rep in fixes:
        pages["full"] = [re.sub(pat, rep, t) for t in pages["full"]]
    rows, misses = [], []
    for i, tbl in enumerate(cfg["tables"]):
        got, matched = T._parse_table(pages, cfg, tbl, per, ref)
        rows.extend(got)
        misses += [f"t{i}:{r['match']}" for j, r in enumerate(tbl.get("rows", [])) if j not in matched]
    if misses:
        raise ValueError(f"{path}: {len(misses)} row spec(s) matched nothing: {misses}")
    return pd.DataFrame.from_records(rows)


def parse(path: str) -> pd.DataFrame:
    return _run(path, LAYOUT, "2011", "2011")


_POOR2 = [{"skip": True}, {"metric": "headcount"}]          # Non pauvres | Pauvres
LAYOUT_QUIBB = {
    "survey": "QUIBB 2005", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ",", "line_type": "national", "line_level": "overall",
    "line_name": "Seuils de pauvreté par milieu (QUIBB 2005)", "period": "2005", "reference_period": "2005",
    "tables": [
        {"page_contains": ["tableau 3.3: indices de pauvreté selon les régions"], "exact_numbers": True,
         "start": r"^Tableau 3\.3", "end": r"^Il ressort",
         "columns": [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}],
         "rows": [{"match": rf"^{g}(?=\s)", "geography": g.replace("Tillabéri", "Tillabéry")}
                  for g in ("Agadez", "Dosso", "Maradi", "Tahoua", "Tillabéri", "Zinder-Diffa", "Niamey")]},
        {"page_contains": ["tableau 3.4 : répartition de la population selon le statut de pauvreté et le milieu"],
         "exact_numbers": True, "start": r"^Tableau 3\.4", "end": r"^Ce tableau",
         "columns": [{"skip": True}, {"metric": "headcount"}, {"skip": True}],
         "rows": [{"match": r"^Niamey(?=\s)", "topic": "locality", "locality": "other", "locality_label": "Niamey"},
                  {"match": r"^Autres Villes(?=\s)", "topic": "locality", "locality": "other",
                   "locality_label": "Autres villes"},
                  {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
                  {"match": r"^Niger(?=\s)"}]},
        {"page_contains": ["tableau 3.5 : répartition des ménages selon le statut de pauvreté et le sexe"],
         "exact_numbers": True, "start": r"^Tableau 3\.5", "end": r"^Cela peut", "columns": _POOR2,
         "defaults": {"unit_of_analysis": "household"},
         "rows": [{"match": r"^Masculin(?=\s)", "topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"},
                  {"match": r"^Féminin(?=\s)", "topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}]},
        {"page_contains": ["tableau 3.6 : répartition de la population selon le statut de pauvreté et le sexe"],
         "exact_numbers": True, "start": r"^Tableau 3\.6", "end": r"^Le tableau", "columns": _POOR2,
         "rows": [{"match": r"^Masculin(?=\s)", "topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"},
                  {"match": r"^Féminin(?=\s)", "topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}]},
        {"page_contains": ["tableau 3.7 : répartition de la population selon statut de pauvreté selon la taille"],
         "exact_numbers": True, "start": r"^Tableau 3\.7", "end": r"^Ensemble", "columns": _POOR2,
         "rows": label_rows("household_size", ["1 à 2 personnes", "3 à 4 personnes", "5 à 6 personnes",
                                               "7 à 9 personnes", "10 à 12 personnes", "13 à 15 personnes",
                                               "16 personnes et plus"])},
    ],
}


def parse_quibb(path: str) -> pd.DataFrame:
    return _run(path, LAYOUT_QUIBB, "2005", "2005")


# --- ENBC 2007/08 ---------------------------------------------------------
# "Tendances de la pauvreté au Niger" (TendancesPauvreteNiger.pdf, Wayback
# `id_` copy of INS's file). DECIMAL POINT in this report.
#   Tableau 3.1 -- ENBC 2007/08: P0 P1 P2 | population weight | contribution
#     (column order settled by arithmetic: Maradi, P0 above the national 59.5,
#     has 26.5 > 21.5 in the last two columns, Agadez the reverse -- the
#     contribution is the LAST column; both columns sum to 100) by region,
#     milieu, sex / age / education of the head, household size and the
#     head's socio-economic group. Lines 150 933 (urban) / 110 348 (rural).
#     PUBLISHED ERROR: "Homme 60.1 19.8 84.5" -- a severity of 84.5 above its
#     own incidence; the row is dropped (the validator's P0 >= P2 law).
#   Tableau 2.2 -- its 2005 columns: QUIBB 2005 as recomputed for this
#     comparison, with Zinder and Diffa SEPARATE (the QUIBB report pools them)
#     and Agadez P2 8.1 against the report's 8.8 -> survey "QUIBB 2005
#     (républié, Tendances 2005-2007/08)". Its 2007/08 columns repeat 3.1.
# CROSS-CHECK: 59.5 / 19.6 / 8.4; Maradi 73.4; Agadez 16.1; urban 36.7;
# 2005 (republished) 62.1 / 24.1 / 12.3, Diffa 18.8, Zinder 71.0.
_FIVE_E = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"},
           {"metric": "population_share"}, {"metric": "poor_share"}]
_R05 = {"period": "2005", "survey": "QUIBB 2005 (républié, Tendances 2005-2007/08)",
        "reference_period": "2005"}
_SIX05 = [dict(m, **_R05) for m in ({"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"})] \
    + [{"skip": True}] * 3
_REG_E = [("Agadez", "Agadez"), ("Diffa", "Diffa"), ("Dosso", "Dosso"), ("Maradi", "Maradi"),
          ("Tahoua", "Tahoua"), ("Tillabéri", "Tillabéry"), ("Zinder", "Zinder"), ("CUN", "Niamey")]
_GSE = ["Salarié public", "Salarié privé", "Indépendant agricole", "Indépendant non agricole", "Sans emploi"]


def _geo_rows():
    return [{"match": rf"^{a}(?=\s)", "geography": b} for a, b in _REG_E] + [
        {"match": r"^Urbain(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Urbain"},
        {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"}]


def _gse():
    rows = label_rows("employment_of_head", _GSE)
    for r in rows:
        r["characteristic"] = "Groupe socio-économique: " + r["characteristic"]
    return rows


LAYOUT_ENBC = {
    "survey": "ENBC 2007/08", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ".", "line_type": "national", "line_level": "overall",
    "line_name": "Seuils de pauvreté par milieu (ENBC 2007/08)", "period": "2007",
    "reference_period": "2007/08",
    "tables": [
        {"page_contains": ["tableau 3.1. indicateurs de pauvreté en 2007-2008"], "exact_numbers": True,
         "start": r"^Tableau 3\.1", "end": r"^Source", "columns": _FIVE_E, "join_wrapped_labels": True,
         "rows": _geo_rows()
         + [{"match": r"^Femme(?=\s)", "topic": "sex_of_head", "characteristic": "Femme", "sex": "female"}]
         + label_rows("age_of_head", ["Moins de 30 ans", "30-39 ans", "40-49 ans", "50-59 ans", "60 ans et plus"])
         + label_rows("education_of_head", ["Sans instruction", "Coranique", "Alphabétisé", "Primaire",
                                            "Secondaire", "Professionnel/Technique", "Supérieur"])
         + label_rows("household_size", ["1 personne", "2 personnes", "3 à 5 personnes", "6 à 9 personnes",
                                         "10 personnes et plus"])
         + _gse() + [{"match": r"^Ensemble(?=\s)"}]},
        {"page_contains": ["tableau 2.2. evolution des indicateurs de pauvreté"], "exact_numbers": True,
         "start": r"^Tableau 2\.2", "end": r"^Source", "columns": _SIX05, "join_wrapped_labels": True,
         "rows": _geo_rows() + _gse() + [{"match": r"^Ensemble(?=\s)"}]},
    ],
}


# Tableau 2.2 wraps "Indépendant / agricole 69.0 ..." BEFORE its numbers;
# the generic re-join would hand "Indépendant" to the row above instead.
_FIX_ENBC = [(r"(?m)^Indépendant\n(agricole)", r"Indépendant \1"),
             (r"(?m)^Indépendant non\n(agricole)", r"Indépendant non \1"),
             (r"(?m)^Taille du ménage\n", "")]


def parse_enbc(path: str) -> pd.DataFrame:
    return _run(path, LAYOUT_ENBC, "2007", "2007/08", fixes=_FIX_ENBC)
