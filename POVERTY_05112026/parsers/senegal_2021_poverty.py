"""Senegal -- ANSD, "EHCVM II (2021/2022) au Sénégal : Rapport final"
(Rapport_Final_EHCVM_2021-2022_VF.pdf, ansd.sn 2024-07).

Lines (Principaux indicateurs, p.9): 369 666 FCFA per person per year
(overall), 196 233 (extreme = total consumption below the food line).
Period 2021, reference 2021/2022, like the other WAEMU second rounds.

Collected:
  II-1  P0 and absolute contribution by stratum (Dakar urbain / Autres urbains
        / Rural / Total), 2021/22 columns only -- the 2018/19 columns equal the
        2018/19 report's own values (senegal.yaml) and are not read twice.
  II-2  number of poor by stratum, 2021/22.
  II-3  extreme P0 and absolute contribution by stratum, 2021/22.
  III-1 milieu (Urbain / Rural / Total): population share, P0, P1, P2, C0.
  III-2 14 regions: same columns.
  III-4 household size: P0, P1, P2, C0, and urban / rural P0.
  III-5 / III-6 age / education of the head x Homme / Femme / National, on
        both lines (the share columns are not read).
  III-7 marital status, III-8 occupation status, III-9 institutional sector
        and status in employment, III-10 branch of the head: population share,
        P0, P1, P2 and (8-10) the distribution of the poor.
Not collected: consumption means, Gini (inequality), II-4 to II-6 (Gini,
panel transitions), III-3 (spending shares).

CROSS-CHECK (verbatim): 37,5 / 10,2 / 4,0; extreme 5,6; 6 553 429 poor;
rural 53,3; urban 20,0; Kédougou 65,7; Dakar 9,3; female head aged 60+ 21,7;
"20 personnes ou plus" 66,4.
"""
from __future__ import annotations
import re

import pandas as pd

from . import poverty_tables as T
from ._vocab import label_rows

_EXT = {"line_level": "extreme", "line_name": "Seuil de l'extrême pauvreté", "line_value": 196233}
_P = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}]
_S = {"skip": True}
_STRATA = [
    {"match": r"^Dakar Urbain(?=\s)", "topic": "locality", "locality": "other", "locality_label": "Dakar urbain"},
    {"match": r"^Autres Urbains(?=\s)", "topic": "locality", "locality": "other", "locality_label": "Autres urbains"},
    {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
    {"match": r"^Total(?=\s)"},
]
_REG = {"DAKAR": "Dakar", "ZIGUINCHOR": "Ziguinchor", "DIOURBEL": "Diourbel", "SAINT-LOUIS": "Saint-Louis",
        "TAMBACOUNDA": "Tambacounda", "KAOLACK": "Kaolack", "THIES": "Thiès", "LOUGA": "Louga",
        "FATICK": "Fatick", "KOLDA": "Kolda", "MATAM": "Matam", "KAFFRINE": "Kaffrine",
        "KEDOUGOU": "Kédougou", "SEDHIOU": "Sédhiou"}
_SEX3 = [("male", "Homme"), ("female", "Femme"), ("total", "National")]


def _sexcols(ext_too=True):
    cols = [{"metric": "headcount", "sex": s} for s, _ in _SEX3]
    if ext_too:
        cols += [{"metric": "headcount", "sex": s, **_EXT} for s, _ in _SEX3]
    return cols + [_S]


def _act(prefix, labels):
    rows = label_rows("employment_of_head", labels)
    for r in rows:
        r["characteristic"] = f"{prefix}: {r['characteristic']}"
    return rows


def _t(cap, **kw):
    return {"page_contains": [cap], "page_excludes": ["...."], "exact_numbers": True, **kw}


LAYOUT = {
    "survey": "EHCVM 2021/2022", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ",", "percent_cells": True,
    "line_type": "national", "line_level": "overall", "line_name": "Seuil de pauvreté",
    "line_value": 369666, "line_unit": "XOF per person per year",
    "period": "2021", "reference_period": "2021/2022",
    "tables": [
        _t("tableau ii-1 :", join_wrapped_labels=True,
           columns=[_S, {"metric": "headcount"}, _S, _S, {"metric": "absolute_contribution"}, _S],
           rows=_STRATA),
        _t("tableau ii-2 :", join_wrapped_labels=True,
           columns=[_S, {"metric": "poor_count"}, _S, _S, _S, _S], rows=_STRATA),
        _t("tableau ii-3 :", columns=[_S, {"metric": "headcount"}, _S, _S, {"metric": "absolute_contribution"}, _S],
           defaults=_EXT, rows=_STRATA),
        _t("tableau iii-1 :", columns=[{"metric": "population_share"}, _S] + _P + [{"metric": "poor_share"}, _S],
           rows=[{"match": r"^Urbain(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Urbain"},
                 {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
                 {"match": r"^Total(?=\s)"}]),
        _t("tableau iii-2 :", columns=[{"metric": "population_share"}, _S] + _P + [{"metric": "poor_share"}, _S],
           rows=[{"match": rf"^{k}(?=\s)", "geography": v} for k, v in _REG.items()]),
        _t("tableau iii-4 :", columns=_P + [{"metric": "poor_share"},
                                            {"metric": "headcount", "locality": "urban", "locality_label": "Urbain"},
                                            {"metric": "headcount", "locality": "rural", "locality_label": "Rural"}, _S],
           rows=label_rows("household_size", ["1-4 personnes", "5-9 personnes", "10-14 personnes",
                                              "15-19 personnes", "20 personnes ou plus"])),
        _t("tableau iii-5 :", columns=_sexcols(), rows=label_rows(
            "age_of_head", ["Moins de 24 ans", "25 à 39 ans", "40 à 49 ans", "50 à 59 ans", "60 ans ou plus"])),
        _t("tableau iii-6 :", columns=_sexcols(), start=r"^Tableau III-6", end=r"^Tableau III-7",
           rows=label_rows("education_of_head", ["Aucun niveau", "Primaire", "Secondaire", "Supérieur"])),
        _t("tableau iii-7 :", columns=[{"metric": "population_share"}] + _P, rows=label_rows(
            "marital_status_of_head", ["Jamais marié", "Marié monogame", "Marié polygame", "Divorcé ou veuf"])),
        _t("tableau iii-8 :", columns=[{"metric": "population_share"}] + _P + [{"metric": "poor_share"}],
           rows=_act("Statut d'occupation", ["Occupés", "Travailleurs familiaux", "Non occupés"])),
        _t("tableau iii-9 :", columns=[{"metric": "population_share"}] + _P + [{"metric": "poor_share"}],
           join_wrapped_labels=True,
           rows=_act("Secteur institutionnel", [])
           + [{"match": r"^Administration, entreprise publique,", "topic": "employment_of_head",
               "characteristic": "Secteur institutionnel: Administration, entreprise publique, organisme international"},
              {"match": r"^Entreprise privée/ONG(?=\s)", "topic": "employment_of_head",
               "characteristic": "Secteur institutionnel: Entreprise privée/ONG"},
              {"match": r"^Ménage \(employeur de personnel", "topic": "employment_of_head",
               "characteristic": "Secteur institutionnel: Ménage (employeur de personnel domestique)"}]
           + _act("Statut dans la profession", ["Salarié", "Tâcheron/aide familial et autres", "Compte propre"])),
        _t("tableau iii-10 :", columns=[{"metric": "population_share"}] + _P + [{"metric": "poor_share"}],
           join_wrapped_labels=True,
           rows=_act("Branche d'activité", ["Agriculture", "Industries extractives", "Autres industries", "BTP",
                                            "Commerce", "Restaurant/Hôtel", "Education/Sante",
                                            "Services personnels,", "Autres services"])
           + [{"match": r"^Elevage/sylviculture/p[eè]ch", "topic": "employment_of_head",
               "characteristic": "Branche d'activité: Elevage/sylviculture/pèche"},
              {"match": r"^Transport/", "topic": "employment_of_head",
               "characteristic": "Branche d'activité: Transport/Communication"}]),
    ],
}

# The wrap re-join folds a label fragment printed on the line after the
# numbers ("Autres / 29,9 ... / Urbains") into its row; III-9's and III-10's
# multi-line labels are matched on their first words.


def parse(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)
    # II-2: "Dakar Urbain 308 867 340 533 ..." -- two six-digit counts side by
    # side fuse into one space-grouped number. Split narrowly; the strata then
    # sum exactly to the printed Total (340 533 + 1 321 631 + 4 891 265 =
    # 6 553 429), checked below.
    pages["full"] = [t.replace("Dakar Urbain 308 867 340 533", "Dakar Urbain 308 867 | 340 533")
                     for t in pages["full"]]
    rows, misses = [], []
    for i, tbl in enumerate(LAYOUT["tables"]):
        got, matched = T._parse_table(pages, LAYOUT, tbl, "2021", "2021/2022")
        rows.extend(got)
        misses += [f"t{i}:{r['match']}" for j, r in enumerate(tbl["rows"]) if j not in matched]
    if misses:
        raise ValueError(f"{len(misses)} row spec(s) matched nothing: {misses}")
    df = pd.DataFrame.from_records(rows)
    # Rural and Total P0 are printed in both II-1 and III-1: kept once, and
    # only if the two tables agree.
    key = [c for c in df.columns if c != "value"]
    dup = df[df.duplicated(key, keep=False)]
    if dup.groupby(key)["value"].nunique().gt(1).any():
        raise ValueError(f"II-1 and III-1 disagree: {dup.to_dict('records')}")
    df = df.drop_duplicates(key)
    cnt = df[df.metric == "poor_count"]
    strata = cnt[cnt.topic == "locality"]["value"].sum()
    total = cnt[cnt.topic == "total"]["value"].sum()
    if abs(strata - total) > 2:
        raise ValueError(f"II-2: strata sum {strata} != printed total {total}")
    return df
