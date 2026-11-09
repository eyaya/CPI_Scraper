"""DR Congo -- EGI-ODD 2020 (Enquête par Grappes à Indicateurs des ODD, OCDD
and INS), final report, chapters 2 and 5.

Two lines, both person-level P0/P1/P2:
  * NATIONAL line (Tableaux 5.1-5.4, 5.10) -- the report prints no amount;
  * the international "1,9$ par jour" line (Tableaux 2.1-2.2). The report never
    states its PPP base year, so the line name says so rather than inventing
    "2011 PPP" -- standardise then gives it its own ID instead of merging it
    with other offices' US$1.90 (2011 PPP) series.

Geography: the 26 provinces of the 2015 découpage. Province names are written
as Tableau 2.1 prints them; 5.2-5.3 spell three differently ("Tanganyka",
"Kasai ...") and are mapped to 2.1's spelling so one province is one place.

Collected: 2.1 (26 provinces + Autres urbains / Ens. urbain / Rural / RDC),
2.2 (sex, age, education, household size, formal/informal sector of the head),
5.1 (urban/rural), 5.2 (provinces), 5.3 (Autres urbains P0), 5.4 (marital
status of the head -- its sex/age/education rows are taken from 5.4 too),
5.10 (formality of the head's enterprise).
NOT collected:
  * 5.12 (2012 vs 2020): its 2012 column assigns the 1-2-3 2012 provincial
    values to the WRONG provinces (Bandundu's 74,6 printed under Bas-Congo,
    Equateur's 77,3 under Sud Kivu ...; the national/urban/rural cells do
    match), and its 2020 column regroups the 26 provinces into the 11 old ones
    under the same names as two new ones (Equateur 74,4 vs province Equateur
    67,2), so it would collide on geography. The 2012 round is collected from
    INS's own 1-2-3 report (dr_congo.yaml).
  * 5.9 (labour-market groups): it does not say whether the status is the
    person's or the head's.
  * 5.11 (self-employed heads only), non-monetary and subjective poverty,
    5.13-5.14 (cumulative poverty, not monetary).

CROSS-CHECK (verbatim): national 56,2 / 22,3 / 11,6; urban 45,2, rural 65,4;
Kinshasa 17,6; Kwango 87,6 / 42,5 / 25,2; $1,90 74,7 / 36,3 / 21,4; Sankuru
$1,90 94,9; Université 18,8; Marié(e) polygame 73,4.
"""
from __future__ import annotations

import re

from ._vocab import label_rows
from .poverty_tables import make_parser

_PROV = ["Kinshasa", "Kongo central", "Kwango", "Kwilu", "Mai-Ndombe", "Equateur",
         "Nord Ubangi", "Sud Ubangi", "Mongala", "Tshuapa", "Tshopo", "Bas Uele", "Haut Uele",
         "Ituri", "Nord Kivu", "Sud Kivu", "Maniema", "Haut Katanga", "Haut Lomami", "Lualaba",
         "Tanganyika", "Lomami", "Sankuru", "Kasaï Oriental", "Kasaï", "Kasaï Central"]
# 5.2/5.3 spellings -> 2.1 spellings
_ALIAS = {"Tanganyika": r"Tanganyi?ka", "Kasaï Oriental": r"Kasa[iï] Oriental",
          "Kasaï Central": r"Kasa[iï] Central", "Kasaï": r"Kasa[iï](?! (?:Oriental|Central))"}

_INT = {"line_type": "international", "line_level": "other",
        "line_name": "Seuil international de 1,9$ par jour (base PPA non précisée)"}
_FGT = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}]


def _prov_rows():
    return [{"match": r"^" + _ALIAS.get(p, re.escape(p)) + r"(?=\s+\d)", "geography": p} for p in _PROV]


def _t(contains, start, end, rows, columns=_FGT, **kw):
    return {"page_contains": contains, "start": start, "end": end, "columns": columns,
            "exact_numbers": True, "rows": rows, **kw}


_MIL = lambda: [  # noqa: E731
    {"match": r"^Autres urbains(?=\s)", "topic": "locality", "locality": "other", "locality_label": "Autres urbains"},
    {"match": r"^Ens(?:\.|emble) urbain(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Ensemble urbain"},
    {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
    {"match": r"^RDC(?=\s)"}]

_HEAD = lambda: (  # noqa: E731
    [{"match": r"^Homme(?=\s)", "topic": "sex_of_head", "characteristic": "Homme", "sex": "male"},
     {"match": r"^Femme(?=\s)", "topic": "sex_of_head", "characteristic": "Femme", "sex": "female"},
     {"match": r"^15-29(?=\s)", "topic": "age_of_head", "characteristic": "15-29"},
     {"match": r"^30-49(?=\s)", "topic": "age_of_head", "characteristic": "30-49"},
     {"match": r"^50-64(?=\s)", "topic": "age_of_head", "characteristic": "50-64"},
     {"match": r"^65 \+(?=\s)", "topic": "age_of_head", "characteristic": "65 +"}]
    + label_rows("education_of_head", ["Non scolarisé", "Au-delà du primaire", "Université"]))

LAYOUT = {
    "survey": "EGI-ODD 2020", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ",", "line_type": "national", "line_level": "overall",
    "line_name": "Seuil national de pauvreté (EGI-ODD 2020)",
    "period": "2020", "reference_period": "2020",
    "tables": [
        # 2.1 -- $1,90 line, provinces and milieu
        _t(["tableau 2.1 : incidence de la pauvreté monétaire avec le seuil de 1,9$"], r"^Province$",
           r"^Milieu de résidence", _prov_rows(), defaults=_INT),
        _t(["tableau 2.1 : incidence de la pauvreté monétaire avec le seuil de 1,9$"],
           r"^Milieu de résidence", r"^Source", _MIL(), defaults=_INT),
        # 2.2 -- $1,90 line, characteristics of the head
        _t(["tableau 2.2 : incidence de la pauvreté monétaire avec le seuil de 1,9$"], r"^Sexe du CM",
           r"^\d+$", _HEAD() + label_rows("household_size", [
               "1 à 3 personnes", "4 à 5 personnes", "6 à 7 personnes", "8 à 9 personnes",
               "10 personnes et plus"]) + [
               {"match": r"^Formel(?=\s)", "topic": "employment_of_head", "characteristic": "Secteur: Formel"},
               {"match": r"^Informel(?=\s)", "topic": "employment_of_head", "characteristic": "Secteur: Informel"}],
           defaults=_INT),
        # 5.1 -- national line, urban/rural
        _t(["tableau 5.1 : différentes formes de pauvreté selon le milieu"], r"^Milieu de résidence",
           r"^Source", [
               {"match": r"^Urbain(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Urbain"},
               {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
               {"match": r"^RDC(?=\s)"}],
           columns=_FGT + [{"skip": True}, {"skip": True}]),
        # 5.2 -- national line, provinces
        _t(["tableau 5.2 : différentes formes de pauvreté par provinces"], r"^Provinces$", r"^RDC",
           _prov_rows(), columns=_FGT + [{"skip": True}, {"skip": True}]),
        # 5.3 -- the only new cell: other urban areas
        _t(["tableau 5.3 : incidence de la pauvreté monétaire évaluée selon le seuil national"],
           r"^Milieu de résidence", r"^Source", [
               {"match": r"^Autres urbains(?=\s)", "topic": "locality", "locality": "other",
                "locality_label": "Autres urbains"}], columns=[{"metric": "headcount"}]),
        # 5.4 -- national line P0, characteristics of the head
        _t(["tableau 5.4 : pauvreté monétaire évaluée selon le seuil national"], r"^Sexe du CM", r"^Source",
           _HEAD() + label_rows("marital_status_of_head", [
               "Célibataire", "Marié(e) monogame", "Marié(e) polygame", "Union libre",
               "Divorcé(e) / séparé(e)", "Veuf (veuve)"]), columns=[{"metric": "headcount"}]),
        # 5.10 -- national line, formality of the head's enterprise (point decimals here)
        _t(["formalité de l’entreprise du chef du ménage"], r"^Formalité de l", r"^RDC", [
            {"match": r"^Formel(?=\s)", "topic": "employment_of_head", "characteristic": "Entreprise: Formel"},
            {"match": r"^Informel(?=\s)", "topic": "employment_of_head", "characteristic": "Entreprise: Informel"}],
           columns=[{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}]),
    ],
}

_base = make_parser(LAYOUT)


def parse(path: str):
    """5.10 prints point decimals ("37.1") in a comma-decimal report; the
    engine's comma reader would take 37.1 as 371. Those page lines are
    rewritten to commas before reading -- 5.10's page only, and only numbers
    of the form d+.d (no thousands groups occur on it)."""
    from . import poverty_tables as T
    orig = T._pages

    def pages(p, halves=True):
        out = orig(p, halves)
        out["full"] = [re.sub(r"(?<=\d)\.(?=\d)", ",", t) if "Tableau 5.10" in t else t
                       for t in out["full"]]
        return out
    T._pages = pages
    try:
        return _base(path)
    finally:
        T._pages = orig
