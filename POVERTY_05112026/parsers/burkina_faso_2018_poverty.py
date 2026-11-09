"""Burkina Faso -- monetary-poverty layout for INSD's "EHCVM-2018 : Diagnostic
de la pauvreté" (EHCVM_2018_Diagnostic de la Pauvrete.pdf, 2022-05 upload).

EHCVM 2018/19 (period 2018, like every WAEMU first round). National line
194 629 FCFA per person per year (food line 102 686); welfare = consumption
per person. Three measures, as in the 2021 module (burkina_faso_poverty):
  overall   total consumption vs 194 629
  extreme   total consumption vs the FOOD line (4-5, 4-6)
  other     food consumption vs the food line, "pauvreté alimentaire" (4-3, 4-4)
plus the US$1,90 / US$3,20 (2011 PPP) rates of Tableau 4-3 (sic: numbered
4-3 on p.39, a second "4-3" follows on p.48).

THE EMC SERIES, republished in Tableau 3-4: EMC 2014 and EMC 2018 P0/P1/P2
and contribution by Urbain / Rural / national (lines 153 530 and 164 955
FCFA). The EMC is a different survey and method (EMC 2018 = 36,2% against
EHCVM 2018 = 41,4% for the same year), so each round is its own survey.

Most tables print P0 | contribution | P1 | P2 | consumption per person (the
last skipped). Collected: 3-1 (poor counts), 3-4 (EMC), 3-7 (HOUSEHOLD-level
by milieu and size), 4-1..4-6 (milieu and 13 regions on the three lines),
4-3 international, 5-1..5-4 (household size, sex, marital status, age of the
head), 6-1 / 6-2 (literacy, education of the head), 8-2 (activity status of
the head over 7 days and 12 months), 8-3 (type of employment), 8-6 (socio-
professional category), 8-7 (branch). Not collected: 6-3 (diploma: its "Aucun"
would collide with 6-2's under one topic), 8-5 (transfers: no topic), the
Ensemble rows of characteristic tables (repeat 4-1), 8-2's 12-month "Non
occupé" (truncated in the text layer, "360 0").

TEXT REPAIRS (narrow): a decimal POINT in this comma report ("1.1", "94.8"
-> "1,1", "94,8"); Tableau 4-2's "Centre-Sud 26,1 2,7 5,8 2 297 553" fuses
P2 = 2 with the consumption 297 553 and is split.

CROSS-CHECK (verbatim): 41,4 / 12,3 / 5,0; extreme 8,2; food 50,7; 8 375 686
poor; Nord 70,9; Centre 5,3; Centre-Sud P2 2; EMC 40,1 (2014) / 36,2 (2018);
households 31,5; female head 32,8; US$1,9 31,9.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T
from ._vocab import label_rows

_EXT = {"line_level": "extreme", "line_name": "Seuil alimentaire (extrême pauvreté)",
        "line_value": 102686}
_FOOD = {"line_level": "other",
         "line_name": "Seuil alimentaire, consommation alimentaire (pauvreté alimentaire)",
         "line_value": 102686}
_FIVE = [{"metric": "headcount"}, {"metric": "poor_share"}, {"metric": "gap"},
         {"metric": "severity"}, {"skip": True}]
_HH6 = _FIVE[:4] + [{"skip": True}, {"skip": True}]
_REGIONS = ["Boucle du Mouhoun", "Cascades", "Centre", "Centre-Est", "Centre-Nord", "Centre-Ouest",
            "Centre-Sud", "Est", "Hauts-Bassins", "Hauts Bassins", "Nord", "Plateau-Central",
            "Sahel", "Sud-Ouest"]

LAYOUT = {
    "survey": "EHCVM 2018/2019", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil national de pauvreté", "line_value": 194629,
    "line_unit": "XOF per person per year",
    "period": "2018", "reference_period": "2018/2019",
    "tables": [],
}


def _fix(t: str) -> str:
    t = re.sub(r"(?<![\d.,])(\d{1,3})\.(\d)(?![\d.])", r"\1,\2", t)
    return t.replace("Centre-Sud 26,1 2,7 5,8 2 297 553", "Centre-Sud 26,1 2,7 5,8 2 | 297 553")


def _virtual(pages, caption):
    """A table's text: from its caption to the next caption, section heading
    or page footer. The ToC repeats every caption with dot leaders: skipped."""
    for t in pages:
        if "...." in t:
            continue
        m = re.search(caption, t)
        if not m:
            continue
        body = t[m.end():]
        k = re.search(r"^(?:Tableau \d|Carte \d|\d+(?:\.\d+)+\s|EHCVM-2018 :|\d+\s+EHCVM-2018)", body, re.M)
        return [body[:k.start()] if k else body]
    return []


def _region_rows():
    rows = []
    for r in _REGIONS:
        geo = "Hauts-Bassins" if r == "Hauts Bassins" else r
        rows.append({"match": r"^" + re.escape(r) + r"(?=\s+[\d,])", "geography": geo})
    return rows


_MILIEU = [
    {"match": r"^(?:Burkina Faso|Ensemble)(?=\s+[\d,])"},
    {"match": r"^(?:Milieu )?Urbain(?=\s+[\d,])", "topic": "locality", "locality": "urban",
     "locality_label": "Urbain"},
    # "Ouaga+Bobo ..." is followed by a lone "Dont" line, which the wrap
    # rejoin folds into its label.
    {"match": r"^Ouaga\+Bobo(?: Dont)?(?=\s+[\d,])", "topic": "locality", "locality": "other",
     "locality_label": "Ouaga+Bobo"},
    {"match": r"^(?:Dont\s+)?Autres? (?:villes|urbain)(?=\s+[\d,])", "topic": "locality",
     "locality": "other", "locality_label": "Autres villes"},
    {"match": r"^(?:Milieu r|R)ural(?=\s+[\d,])", "topic": "locality", "locality": "rural",
     "locality_label": "Rural"},
]


def _act(prefix, rows):
    for r in rows:
        r["characteristic"] = f"{prefix}: {r['characteristic']}"
    return rows


def _specs():
    S = []

    def add(caption, rows, columns=_FIVE, **kw):
        S.append((caption, {"exact_numbers": True, "join_wrapped_labels": True,
                            "columns": columns, "rows": rows, **kw}))

    add(r"Tableau 4- 1: Indicateurs de la pauvret. mon.taire selon le milieu", _MILIEU)
    add(r"Tableau 4- 2: Indicateurs de pauvret. mon.taire par r.gion", _region_rows())
    add(r"Tableau 4- 3: Indicateurs de pauvret. alimentaire par milieu", _MILIEU, defaults=_FOOD)
    add(r"Tableau 4- 4: Indicateurs de pauvret. alimentaire par r.gion", _region_rows(), defaults=_FOOD)
    add(r"Tableau 4- 5: Indicateurs d.extr.me pauvret. par milieu", _MILIEU, defaults=_EXT)
    add(r"Tableau 4- 6: Indicateurs d.extr.me pauvret. par r.gion", _region_rows(), defaults=_EXT)
    # International lines: nominal | normalised consumption | US$1,9 | US$3,2 | Gini
    intl = [{"skip": True}, {"skip": True},
            {"metric": "headcount", "line_type": "international", "line_level": "extreme",
             "line_name": "US$1,90 par jour (PPA 2011)", "line_value": 159116},
            {"metric": "headcount", "line_type": "international", "line_level": "other",
             "line_name": "US$3,20 par jour (PPA 2011)", "line_value": 267985},
            {"skip": True}]
    # Its two consumption columns ("315 549 299 562") fuse into one
    # space-grouped number; `_sub` splits a pair of 6-digit groups.
    add(r"Tableau 4- 3: Indicateurs de pauvret. sur la base des seuils internationaux",
        _MILIEU, columns=intl, _sub=(r"(\d{3} \d{3}) (\d{3} \d{3})", r"\1 | \2"))
    # Households (3-7): P0 | contribution | P1 | P2 | size | consumption
    add(r"Tableau 3- 7: Indicateurs de pauvret. des m.nages par milieu", [
        {"match": r"^Burkina Faso(?=\s)"},
        {"match": r"^Urbain(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Urbain"},
        {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"}]
        # "1-4 personnes ..." starts with a digit, so the wrap rejoin glues the
        # heading "Nombre de personnes dans le ménage" in front of it.
        + [dict(r, match=r["match"].replace("^", "(?:^|ménage )", 1))
           for r in label_rows("household_size", ["1-4 personnes", "5-6 personnes", "7-8 personnes",
                                                  "9-11 personnes", "12 personnes et +"])],
        columns=_HH6, defaults={"unit_of_analysis": "household"})
    add(r"Tableau 5- 1: Indicateurs de la pauvret. selon la taille", label_rows(
        "household_size", ["1-4 personnes", "5-6 personnes", "7-8 personnes", "9-11 personnes",
                           "12 personnes ou plus"]))
    add(r"Tableau 5- 2: Indicateurs de la pauvret. mon.taire selon le sexe", [
        {"match": r"^Masculin(?=\s)", "topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"},
        {"match": r"^Féminin(?=\s)", "topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}])
    add(r"Tableau 5- 3: Incidence de la pauvret. selon le statut matrimonial", label_rows(
        "marital_status_of_head", ["Marié polygame", "Divorcé/séparé", "Marié monogame", "Veuf (ve)",
                                   "Union libre", "Célibataire"]))
    add(r"Tableau 5- 4: Indicateurs de la pauvret. selon l.âge", label_rows(
        "age_of_head", ["Moins de 24 ans", "25-34 ans", "35-44 ans", "45-54 ans", "55-64 ans",
                        "65 ans et +"]))
    add(r"Tableau 6- 1: Indicateur de pauvret. selon le statut d.alphab", label_rows(
        "literacy_of_head", ["Analphabète", "Alphabète"]))
    add(r"Tableau 6- 2: Indicateurs de pauvret. selon le niveau d.instruction", label_rows(
        "education_of_head", ["Aucun", "Primaire", "Post primaire", "Secondaire", "Supérieur"]))
    add(r"Tableau 8- 2: Indicateurs de pauvret. selon la branche d.activit.s du chef", _act(
        "Statut d'activité (7 derniers jours)", label_rows("employment_of_head", [
            "Occupé", "Chômeur", "Travailleur familial cherchant un emploi", "Inactifs"])
        # a 4-word label tail is not rejoined: match the head it keeps
        + [{"match": r"^Travailleur familial ne(?: cherchant pas un emploi)?(?=\s+[\d,])",
            "topic": "employment_of_head",
            "characteristic": "Travailleur familial ne cherchant pas un emploi"}]),
        start=r"^Selon le statut d.activit", end=r"^Selon l.activit")
    add(r"Tableau 8- 2: Indicateurs de pauvret. selon la branche d.activit.s du chef", _act(
        "Activité principale (12 derniers mois)", label_rows("employment_of_head", [
            "Occupé", "Travailleur familial"])), start=r"^Selon l.activit")
    add(r"Tableau 8- 3: Indicateurs de pauvret. selon le type d.emploi", _act(
        "Type d'emploi", label_rows("employment_of_head", ["Salarié", "Non salarié", "Inactifs"])))
    add(r"Tableau 8- 6: Indicateurs de pauvret. selon la cat.gorie socioprofessionnelle", _act(
        "Catégorie socioprofessionnelle", [
            {"match": r"^(?:Cadre )?supérieur ou moyen(?=\s)", "topic": "employment_of_head",
             "characteristic": "Cadre supérieur ou moyen"},
            {"match": r"^Ouvrier(?=\s)", "topic": "employment_of_head", "characteristic": "Ouvrier"},
            {"match": r"^(?:Manoeuvre, )?stagiaire, aide familial(?=\s)", "topic": "employment_of_head",
             "characteristic": "Manoeuvre, stagiaire, aide familial"},
            {"match": r"^Travailleur compte propre(?=\s)", "topic": "employment_of_head",
             "characteristic": "Travailleur compte propre"},
            {"match": r"^Patron(?=\s)", "topic": "employment_of_head", "characteristic": "Patron"}]))
    add(r"Tableau 8- 7: Indicateurs de pauvret. selon la branche d.activit. du chef", _act(
        "Branche d'activité", label_rows("employment_of_head", [
            "Agriculture", "Elevage/peche", "Indust. extr.", "Autr. indust.", "BTP", "Commerce",
            "Restaurant/Hotel", "Trans./Comm.", "Education/Sante", "Services perso.", "Aut. services"])))
    return S


def _emc(pages) -> list[dict]:
    """Tableau 3-4: six data lines in printed order Urbain 2014/2018, Rural
    2014/2018, Burkina Faso 2014/2018 -- the stratum label sits on a line of
    its own or before the year, so rows are read by ORDER and checked."""
    body = _virtual(pages, r"Tableau 3- 4: Indicateurs de pauvret. selon le milieu de r.sidence")
    if not body:
        return []
    hits = re.findall(r"(2014|2018) (\d+,\d) (\d+,\d) (\d+,\d) (\d+,\d) \d{3} \d{3}", body[0])
    if len(hits) != 6 or [h[0] for h in hits] != ["2014", "2018"] * 3:
        raise ValueError(f"Tableau 3-4 (EMC): expected 6 rows in year order, got {hits}")
    order = [("urban", "Urbain", "locality"), ("rural", "Rural", "locality"), ("all", "Total", "total")]
    lines = {"2014": 153530, "2018": 164955}
    out = []
    for i, (yr, p0, ctr, p1, p2) in enumerate(hits):
        loc, lab, topic = order[i // 2]
        for metric, v in (("headcount", p0), ("poor_share", ctr), ("gap", p1), ("severity", p2)):
            out.append(C.row(metric=metric, value=C.to_number(v, ","),
                             survey=f"EMC {yr} (républié, diagnostic EHCVM 2018)",
                             welfare_aggregate="consumption", line_type="national",
                             line_level="overall", line_name="Seuil de pauvreté (EMC)",
                             line_value=lines[yr], line_unit="XOF per person per year",
                             period=yr, reference_period=yr, frequency="ad_hoc", topic=topic,
                             characteristic=lab if topic == "locality" else "Total",
                             locality=loc, locality_label=lab))
    nat = [r["value"] for r in out if r["topic"] == "total" and r["metric"] == "headcount"]
    if nat != [40.1, 36.2]:
        raise ValueError(f"Tableau 3-4 national P0 {nat}, the prose says 40,1 / 36,2")
    return out


def _counts(pages) -> list[dict]:
    """Tableau 3-1: extreme %, poverty %, extremely poor, poor, population, sample."""
    body = _virtual(pages, r"Tableau 3- 1: Indicateurs de pauvret. au Burkina Faso en 2018")
    m = re.search(r"^Indicateur\s+(.*)$", body[0], re.M) if body else None
    nums = C.numbers_in(m.group(1), decimal=",") if m else []
    if len(nums) != 6:
        return []
    base = dict(survey=LAYOUT["survey"], welfare_aggregate="consumption", line_type="national",
                line_unit=LAYOUT["line_unit"], period="2018", reference_period="2018/2019",
                frequency="ad_hoc")
    return [C.row(metric="poor_count", value=nums[3], line_level="overall",
                  line_name=LAYOUT["line_name"], line_value=194629, **base),
            C.row(metric="poor_count", value=nums[2], **_EXT, **base)]


def parse(path: str) -> pd.DataFrame:
    full = [_fix(t) for t in T._pages(path, halves=False)["full"]]
    rows: list[dict] = []
    misses = []
    for cap, tbl in _specs():
        sub = tbl.pop("_sub", None)
        body = _virtual(full, cap)
        if sub:
            body = [re.sub(sub[0], sub[1], b) for b in body]
        got, matched = T._parse_table({"full": body}, LAYOUT, tbl, "2018", "2018/2019")
        rows.extend(got)
        misses += [f"{cap[:30]}..{r['match']}" for i, r in enumerate(tbl["rows"]) if i not in matched]
    if misses:
        print(f"[burkina_2018] no match for {len(misses)} row spec(s): {misses}")
    rows += _emc(full) + _counts(full)
    return pd.DataFrame.from_records(rows)
