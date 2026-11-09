"""Chad -- ECOSIT3 2011 poverty profile (INSEED, "Rapport principal sur la
pauvreté, Tchad 2011, version publiée"), with ECOSIT2 2003 as it republishes it.

Wayback `id_` copy of inseed.td's own file (inseed.td is gone; the new
inseed.ssn-tchad.td API lists only ECOSIT4). National line 237 942 FCFA per
person per year in 2011 (N'Djaména's, Tableau 2.2); ECOSIT2's 144 570 (Tableau
4.9). Consumption per capita, person level. INSEED states ECOSIT2 and ECOSIT3
were run "dans les mêmes conditions" (method, coverage, collection period), so
the 2003 values are comparable with 2011 -- but NOT with ECOSIT4 2018.

Survey/line labels match the chad_poverty module's ECOSIT3 rows (read from the
ECOSIT4 recap), so the national/urban/rural/sex-of-head rows both print merge
on one key; the values are identical.

Collected (columns Incidence | Profondeur | Sévérité | Contribution, the last
being each group's share of the poor, footnote 11):
  4.6  2011: Autres milieux urbains, Urbain, Rural, 20 regions, Tchad
  4.7  2011: sex, marital status, age, household size of the head
  4.8  2011: education, activity status, status in employment, socio-economic
       category and branch of the head. THE TEXT LAYER SPLITS SOME ROWS: the
       Profondeur and Sévérité cells sit on the line ABOVE the label, which
       carries Incidence and Contribution ("27,6 17,0" / "Sans instruction
       48,5 62,9"). `_repair` rebuilds "Sans instruction 48,5 27,6 17,0 62,9";
       the prose confirms the incidence and contribution of every such row
       checked (48,5 / 62,9; Chômeur BIT 54,1; Apprenti 61,0) and P0>=P1>=P2
       holds for all of them.
  4.9  2003: national P0, P1, P2 (ECOSIT2)
  4.10 2003: P0 by sex, household size, education and socio-economic
       category of the head
  4.11 2003: P0 for N'Djaména, other urban centres and rural areas.
NOT collected: 4.11's 2003 REGION rows -- their values repeat across groups
of today's regions (Kanem = Lac = Barh El Gazel 54,1; Mayo Kebbi Est = Ouest
71,7; Mandoul = Moyen Chari 69,3 ...), i.e. they are the coarser 2003 strata
copied onto successor regions, and filing them as each region's own rate
would misstate them. Also not: 4.8's employed-heads "Ensemble/Tchad" rows
(49,4 -- a sub-population total), Tableau 2.2 (regional lines, no metric),
variation/écart columns.

CROSS-CHECK (verbatim): 2011 46,7 / 26,3 / 15,9; 2003 55,0 / 21,6 / 10,8;
Mandoul 70,9; N'Djaména 11,0; Plus de 10 personnes 56,5; Salarié du public
11,6; 2003 Primaire 64,1. Regional contributions sum to 100,2.
"""
from __future__ import annotations

import re

import pandas as pd

from ._vocab import label_rows
from . import poverty_tables as T

_L11 = {"survey": "ECOSIT3", "line_name": "Seuil global de pauvreté (ECOSIT3)",
        "line_value": 237942, "line_unit": "XOF per person per year",
        "period": "2011", "reference_period": "2011"}
_L03 = {"survey": "ECOSIT2", "line_name": "Seuil de pauvreté (ECOSIT2)",
        "line_value": 144570, "line_unit": "XOF per person per year",
        "period": "2003", "reference_period": "2003"}
_FGT = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"},
        {"metric": "poor_share"}]
_P0_2003 = [{"metric": "headcount", **_L03}, {"skip": True}, {"skip": True}]

_REGIONS = ["Barh El Gazel", "Batha", "Borkou-Ennedi-Tibesti", "Chari Baguirmi", "Guéra",
            "Hadjer Lamis", "Kanem", "Lac", "Logone Occidental", "Logone Oriental", "Mandoul",
            "Mayo Kebbi Est", "Mayo Kebbi Ouest", "Moyen Chari", "N'Djaména", "Ouaddai",
            "Salamat", "Sila", "Tandjilé", "Wadi Fira"]


def _pre(prefix, labels):
    return [{"match": r"^" + re.escape(lab) + r"(?=\s+[-\d])", "topic": "employment_of_head",
             "characteristic": f"{prefix}: {lab}" if prefix else lab} for lab in labels]


def _t(contains, start, end, rows, columns=_FGT, **kw):
    return {"page_contains": contains, "start": start, "end": end, "columns": columns,
            "exact_numbers": True, "rows": rows, **kw}


LAYOUT = {
    **_L11, "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ",", "line_type": "national", "line_level": "overall",
    "tables": [
        # 4.6 -- milieu and regions, 2011
        _t(["tableau 4.6: indicateurs de pauvreté par région"], r"^Lieu de résidence", r"^Région de résidence", [
            {"match": r"^Autres milieux urbains(?=\s)", "topic": "locality", "locality": "other",
             "locality_label": "Autres milieux urbains"}]),
        _t(["tableau 4.6: indicateurs de pauvreté par région"], r"^Milieu de résidence", r"^Région de résidence", [
            {"match": r"^Urbain(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Urbain"},
            {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"}]),
        _t(["tableau 4.6: indicateurs de pauvreté par région"], r"^Région de résidence", r"^11 Le poids",
           [{"match": r"^" + re.escape(r) + r"(?=\s+\d)", "geography": r} for r in _REGIONS]
           + [{"match": r"^Tchad(?=\s)"}]),
        # 4.7 -- characteristics of the head, 2011
        _t(["tableau 4.7: indicateurs de pauvreté selon certaines"], r"^Sexe$", r"^Statut matrimonial", [
            {"match": r"^Masculin(?=\s)", "topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"},
            {"match": r"^Féminin(?=\s)", "topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}]),
        _t(["tableau 4.7: indicateurs de pauvreté selon certaines"], r"^Statut matrimonial", r"^Ensemble",
           label_rows("marital_status_of_head", ["Marié", "Union libre", "Célibataire", "Veuf",
                                                 "Séparé", "Divorcé"])),
        _t(["tableau 4.7: indicateurs de pauvreté selon certaines"], r"^Grand groupe d'âge", r"^Profil de",
           label_rows("age_of_head", ["Moins de 25 ans", "25 à 44 ans", "44 à 64 ans", "65 ans et plus"])),
        _t(["tableau 4.7: indicateurs de pauvreté selon certaines"], r"^Taille du ménage", r"^Ensemble",
           label_rows("household_size", ["1 personne", "2 à 3 personnes", "4 à 6 personnes",
                                         "7 à 10 personnes", "Plus de 10 personnes"])),
        # 4.8 -- socio-economic characteristics of the head, 2011 (split rows repaired)
        _t(["tableau 4.8: indicateurs de pauvreté par caractéristiques"], r"^Niveau d'instruction",
           r"^Situation d'activité",
           label_rows("education_of_head", ["Sans instruction", "Ecole coranique", "Primaire",
                                            "Secondaire", "Professionnel", "Supérieur"])),
        _t(["tableau 4.8: indicateurs de pauvreté par caractéristiques"], r"^Situation d'activité",
           r"^Ensemble", _pre("Situation d'activité", ["Actif occupé", "Chômeur au sens du BIT",
                                                        "Chômeur découragé", "Inactif"])),
        _t(["tableau 4.8: indicateurs de pauvreté par caractéristiques"], r"^Statut dans la profession",
           r"^Ensemble", _pre("Statut dans la profession", ["Patron, compte propre", "Salarié",
                                                             "Apprenti, aide familial"])),
        _t(["tableau 4.8: indicateurs de pauvreté par caractéristiques"], r"^Catégorie socio-économique",
           r"^Branche d'activité", _pre("", ["Indépendant non agricole", "Indépendant agricole",
                                              "Salarié du public", "Salarié du privé",
                                              "Autres catégories"])),
        _t(["tableau 4.8: indicateurs de pauvreté par caractéristiques"], r"^Branche d'activité",
           r"^Ensemble", _pre("Branche", [
               "Agriculture, sylviculture et cueillette", "Elevage et chasse", "Pêche",
               "Activités extractives", "Fabrication de produits alimentaires, boissons et tabac",
               "Autres industries", "Bâtiments et travaux publics", "Commerce et réparation engins",
               "Transport et entreposage", "Hébergement et restauration", "Autres services"]),
           join_wrapped_labels=True),
        # 4.9 -- ECOSIT2 national
        _t(["tableau 4. 9 : evolution de la pauvreté entre 2003 et 2011"], r"^Indicateurs de pauvreté",
           r"^4\.3\.1", [
               {"match": r"^Taux de pauvreté \(%\)", "columns": _P0_2003},
               {"match": r"^Profondeur de la pauvreté \(%\)",
                "columns": [{"metric": "gap", **_L03}, {"skip": True}, {"skip": True}]},
               {"match": r"^Sévérité de la pauvreté \(%\)",
                "columns": [{"metric": "severity", **_L03}, {"skip": True}, {"skip": True}]}]),
        # 4.10 -- ECOSIT2 by characteristics of the head
        _t(["tableau 4.10 : evolution de la pauvreté"], r"^Sexe du chef de ménage", r"^Taille du ménage", [
            {"match": r"^Masculin(?=\s)", "topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"},
            {"match": r"^Féminin(?=\s)", "topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}],
           columns=_P0_2003),
        _t(["tableau 4.10 : evolution de la pauvreté"], r"^Taille du ménage", r"^Niveau d'instruction",
           label_rows("household_size", ["1 personne", "2 à 3 personnes", "4 à 6 personnes",
                                         "7 à 10 personnes", "11 personnes ou plus"]), columns=_P0_2003),
        _t(["tableau 4.10 : evolution de la pauvreté"], r"^Niveau d'instruction du CM", r"^Catégorie",
           label_rows("education_of_head", ["Sans instruction", "Ecole coranique", "Primaire",
                                            "Secondaire", "Professionnel", "Supérieur"]), columns=_P0_2003),
        _t(["tableau 4.10 : evolution de la pauvreté"], r"^Catégorie socioéconomique", r"^TCHAD",
           _pre("", ["Indépendant non agricole", "Indépendant agricole", "Salarié du public",
                     "Salarié du privé", "Autres catégories"]), columns=_P0_2003),
        # 4.11 -- ECOSIT2 milieu (region rows deliberately NOT read)
        _t(["tableau 4.11 : evolution de la pauvreté"], r"^Milieu de résidence", r"^Région de résidence", [
            {"match": r"^N'Djaména(?=\s)", "geography": "N'Djaména"},
            {"match": r"^Autres centre urbains(?=\s)", "topic": "locality", "locality": "other",
             "locality_label": "Autres centres urbains"},
            {"match": r"^Milieu rural(?=\s)", "topic": "locality", "locality": "rural",
             "locality_label": "Milieu rural"}], columns=_P0_2003),
    ],
}

_NUM = r"-?\d+,\d+|-?\d+"
_TWO = re.compile(rf"^\s*({_NUM})\s+({_NUM})\s*$")
_LAB2 = re.compile(rf"^(\D+?)\s+({_NUM})\s+({_NUM})\s*$")


def _repair(text: str) -> str:
    """Rejoin 4.8's split rows: "P1 P2" alone above "Label P0 Contribution"."""
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        a = _TWO.match(lines[i])
        b = _LAB2.match(lines[i + 1]) if (a and i + 1 < len(lines)) else None
        if a and b:
            out.append(f"{b.group(1)} {b.group(2)} {a.group(1)} {a.group(2)} {b.group(3)}")
            i += 2
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def parse(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)
    pages["full"] = [_repair(t) if "Tableau 4.8:" in t else t for t in pages["full"]]
    period, ref = T._resolve_period(pages["full"], LAYOUT)
    rows = []
    for tbl in LAYOUT["tables"]:
        got, matched = T._parse_table(pages, LAYOUT, tbl, period, ref)
        miss = [r["match"] for k, r in enumerate(tbl["rows"]) if k not in matched]
        if miss:
            print(f"[chad_ecosit3] no match: {miss}")
        rows.extend(got)
    return pd.DataFrame.from_records(rows)
