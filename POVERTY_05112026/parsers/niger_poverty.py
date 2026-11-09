"""Niger -- monetary-poverty layout (INS, "Rapport sur le profil de pauvreté",
EHCVM 2021/2022).

Fieldwork 17 Nov 2021 - 13 Feb 2022 and 3 Jun - 31 Aug 2022 -> period 2021,
reference "2021/2022". National line 195 760 FCFA per person per year
(Tableau 2, "Seuil global", Niger); welfare = consumption per capita.

Collected:
  Tableau 3   trend by milieu, 2011 and 2014 (ECVMA), 2018 (EHCVM 2018/19) and
              2021: P0, P1, P2, population share, share of the poor, number of
              poor. Read by `_trend` below: the YEAR is printed only on each
              triplet's Rural line, so Urbain/National are dated by position.
              The report prints the 2014 national P0 as "45, 4" -- rejoined on
              that table only (the count of numbers then matches exactly).
  Tableau 5   8 regions: P0, number of poor, P1, P2, share of the poor,
              population share (mean consumption skipped). Its Urbain line
              prints "3,2 1 503 005" -- P2 = 1 run into the consumption 503 005
              -- so the milieu rows are NOT read here; Tableau 3's 2021 rows
              carry the same milieu values.
  Tableau 6   sex / age / marital status of the head: P0, number of poor, P1, P2
  Tableau 7   education, literacy, occupation status, institutional sector and
              socio-professional category of the head: P0, share of the poor,
              P1, P2 (block heading kept in `characteristic` for the
              employment blocks: "Inactif/non occupe" appears in two of them)
  Tableau 8   P0/P1/P2 of WOMEN by region and milieu (topic sex)
  Tableau 10  P0/P1/P2 of CHILDREN (< 18) by region and milieu (topic age)
  Tableau 11  quintile block, national columns only
  Tableau 12  children by age group
Not collected: Tableau 4 / 23 (transition matrices), 9 and 11's other blocks
(women / children CROSSED with a characteristic of the head -- the schema has
one sex column, used by the head in those topics), situation de handicap (no
topic), mean consumption, Gini (inequality), Tableaux 13+ (non-monetary).

CROSS-CHECK (verbatim): 2021 P0 41,2 / P1 9,9 / P2 3,4, 9 932 800 poor;
2018 40,8 / 11,2 / 4,3; 2011 48,2; urban 2021 15,2; Tillabéri 52,7 (P2 5,2);
Niamey 4,9; female-headed 36,4; women 40,6; children 45,8; line 195 760.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T
from ._vocab import label_rows

_SURVEY = "EHCVM 2021/2022"
_REGIONS = ["Agadez", "Diffa", "Dosso", "Maradi", "Tahoua", "Tillabéri", "Zinder", "Niamey"]


def _cols4(second):
    return [{"metric": "headcount"}, second, {"metric": "gap"}, {"metric": "severity"}]


_COUNT = {"metric": "poor_count"}
_SHARE = {"metric": "poor_share"}


def _t7(start, end, topic, labels, prefix=""):
    rows = label_rows(topic, labels)
    if prefix:
        for r in rows:
            r["characteristic"] = f"{prefix}: {r['characteristic']}"
    return {"page_contains": ["tableau 7", "capital humain"], "start": start, "end": end,
            "columns": _cols4(_SHARE), "exact_numbers": True, "rows": rows}


def _women_children(page_kw, which, extra):
    # National | group pairs for P0, P1, P2: keep the group's column.
    cols = []
    for m in ("headcount", "gap", "severity"):
        cols += [{"skip": True}, {"metric": m, **extra}]
    rows = [{"match": r"^" + re.escape(r) + r"(?=\s+\d)", "geography": g}
            for r, g in [(x, x) for x in _REGIONS[:5]] + [("Tillaberi", "Tillabéri"),
                                                         ("Zinder", "Zinder"), ("Niamey", "Niamey")]]
    rows += [{"match": r"^Urbain(?=\s+\d)", "locality": "urban", "locality_label": "Urbain"},
             {"match": r"^Rural(?=\s+\d)", "locality": "rural", "locality_label": "Rural"},
             {"match": r"^National(?=\s+\d)"}]
    return {"page_contains": page_kw, "exact_numbers": True, "columns": cols, "rows": rows}


_WOMEN = {"topic": "sex", "characteristic": "Femmes", "sex": "female"}
_CHILD = {"topic": "age", "characteristic": "Enfants (moins de 18 ans)",
          "age_group": "Moins de 18 ans"}

LAYOUT = {
    "survey": _SURVEY, "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil global de pauvreté",
    "line_value": 195760, "line_unit": "XOF per person per year",
    "period": "2021", "reference_period": "2021/2022",
    "tables": [
        {   # Tableau 5 -- regions
            "page_contains": ["tableau 5", "selon le milieu de résidence et la région"],
            "exact_numbers": True,
            "columns": [{"metric": "headcount"}, _COUNT, {"metric": "gap"},
                        {"metric": "severity"}, {"skip": True}, _SHARE,
                        {"metric": "population_share"}],
            "rows": [{"match": r"^" + re.escape(r) + r"(?=\s+\d)", "geography": r} for r in _REGIONS],
        },
        # Tableau 6 -- head: sex, age, marital status
        {"page_contains": ["tableau 6", "caractéristiques socio démographiques du chef"],
         "exact_numbers": True, "columns": _cols4(_COUNT),
         "rows": [{"match": r"^Masculin(?=\s+\d)", "topic": "sex_of_head",
                   "characteristic": "Masculin", "sex": "male"},
                  {"match": r"^Féminin(?=\s+\d)", "topic": "sex_of_head",
                   "characteristic": "Féminin", "sex": "female"}]
         + label_rows("age_of_head", ["Moins de 25 ans", "25-34 ans", "35-44 ans",
                                      "45-54 ans", "55-64 ans", "65 ans et plus"])
         + label_rows("marital_status_of_head", ["Célibataire", "Marié(e) monogame",
                                                 "Marié(e) polygame", "Veuf(ve)",
                                                 "Divorcé(e)", "Séparé(e)"])},
        # Tableau 7 -- human capital of the head, one block each
        _t7(r"^Education du CM", r"^Alphabétisation du CM", "education_of_head",
            ["Aucun", "Primaire", "Secondaire général 1", "Secondaire technique 1",
             "Secondaire général 2", "Secondaire technique 2", "Post-secondaire", "Supérieur"]),
        _t7(r"^Alphabétisation du CM", r"^Statut d'occupation", "literacy_of_head", ["Non", "Oui"]),
        _t7(r"^Statut d'occupation", r"^Secteur institutionnel", "employment_of_head",
            ["Occupe", "Non occupe"], "Statut d'occupation"),
        _t7(r"^Secteur institutionnel", r"^Catégorie Socioprofessionnelle", "employment_of_head",
            ["Inactif/non occupe", "Etat/Collectivités locales", "Entreprise publique/parapublique",
             "Entreprise Privée", "Entreprise associative", "Ménage comme employeur de personnel",
             "Organisme international/Ambassade"], "Secteur institutionnel"),
        _t7(r"^Catégorie Socioprofessionnelle", r"^Situation de handicap", "employment_of_head",
            ["Inactif/non occupe", "Cadre supérieur", "Cadre moyen/agent de maîtrise",
             "Ouvrier ou employé qualifié", "Ouvrier ou employé non qualifié",
             "Manœuvre, aide-ménagère", "Stagiaire ou Apprenti rémunéré",
             "Stagiaire ou Apprenti non rémunéré", "Travailleur pour compte propre", "Patron"],
            "Catégorie socioprofessionnelle"),
        # Tableaux 8 and 10 -- women, children
        _women_children(["tableau 8", "des femmes selon le milieu"], "women", _WOMEN),
        _women_children(["tableau 10", "des enfants selon les régions"], "children", _CHILD),
        # Tableau 11 -- quintiles, national columns
        {"page_contains": ["tableau 11", "des enfants selon la situation"],
         "start": r"^Quintile", "exact_numbers": True,
         "columns": [{"metric": "headcount"}, {"skip": True}, {"metric": "gap"},
                     {"skip": True}, {"metric": "severity"}, {"skip": True}],
         "rows": [{"match": rf"^Q{q}(?=\s+\d)", "topic": "quintile",
                   "characteristic": f"Q{q}"} for q in range(1, 6)]},
        # Tableau 12 -- children by age group
        {"page_contains": ["tableau 12", "selon la classe d’âge"], "exact_numbers": True,
         "columns": [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}],
         "rows": label_rows("age", ["Mois de 5 ans", "De 5 à 9 ans", "De 10 à 14 ans",
                                    "De 15 à 17 ans"])},
    ],
}

# Tableau 3's surveys, by the year printed on each triplet.
_TREND_SURVEY = {"2011": ("ECVMA 2011", "2011"), "2014": ("ECVMA 2014", "2014"),
                 "2018": ("EHCVM 2018/2019", "2018/2019"), "2021": (_SURVEY, "2021/2022")}
_TREND_COLS = ["headcount", "gap", "severity", "population_share", "poor_share", "poor_count"]
_LOC = {"Urbain": ("urban", "Urbain", "locality"), "Rural": ("rural", "Rural", "locality"),
        "National": ("all", "Total", "total")}


def _trend(pages: list[str]) -> list[dict]:
    """Tableau 3: triplets Urbain / <year> Rural / National."""
    page = next((p for p in pages if "Tableau 3: Tendance des indicateurs" in p
                 and "Urbain 17,9" in p), None)
    if page is None:
        raise ValueError("Niger Tableau 3 (trend) not found")
    out, pending, year = [], [], None
    for line in page.splitlines():
        m = re.match(r"^(?:(20\d\d)\s+)?(Urbain|Rural|National)\s+(.*)$", line.strip())
        if not m:
            continue
        # The five percentages are single tokens (none reaches 1 000, so none
        # has a thousands space); the space-grouped COUNT is everything after
        # them. Read generically, "100 100 7 963 631" fuses into 100100 and
        # 7963631. "45, 4" (2014 national P0) is rejoined first.
        cells = re.sub(r"(\d), (\d)", r"\1,\2", m.group(3)).split()
        nums = [C.to_number(c, decimal=",") for c in cells[:5]]
        nums.append(C.to_number("".join(cells[5:]), decimal=","))
        if len(cells) < 6 or any(v is None for v in nums):
            raise ValueError(f"Niger Tableau 3: {line!r} gives {len(nums)} numbers, want 6")
        pending.append((m.group(2), nums))
        if m.group(1):
            year = m.group(1)
        if m.group(2) == "National":
            if year not in _TREND_SURVEY or len(pending) != 3:
                raise ValueError(f"Niger Tableau 3: bad triplet before {line!r}")
            survey, ref = _TREND_SURVEY[year]
            for lab, vals in pending:
                loc, llab, topic = _LOC[lab]
                for metric, v in zip(_TREND_COLS, vals):
                    out.append(C.row(
                        metric=metric, value=v, survey=survey,
                        welfare_aggregate="consumption", line_type="national",
                        line_level="overall", line_name="Seuil global de pauvreté",
                        line_value=195760 if year == "2021" else "",
                        line_unit="XOF per person per year" if year == "2021" else "",
                        period=year, reference_period=ref, frequency="ad_hoc",
                        topic=topic, characteristic=llab if topic == "locality" else "Total",
                        locality=loc, locality_label=llab))
            pending, year = [], None
    years = {r["period"] for r in out}
    if years != set(_TREND_SURVEY):
        raise ValueError(f"Niger Tableau 3: years {sorted(years)}")
    return out


_tables = T.make_parser(LAYOUT)


def parse(path: str) -> pd.DataFrame:
    df = _tables(path)
    pages = T._pages(path, halves=False)["full"]
    return pd.concat([pd.DataFrame(_trend(pages)), df], ignore_index=True)
