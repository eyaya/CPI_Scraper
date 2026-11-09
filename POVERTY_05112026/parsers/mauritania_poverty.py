"""Mauritania -- monetary poverty from three ANSADE (ex-ONS) publications.

Three descriptors, one output file (merge-on-write):

* `mauritania_poverty` -- "Synthèse des résultats EPCV 2019-2020", the
  "Tableau synoptique" (p. 5): P0/P1/P2 national, urban, rural, for the
  overall AND the extreme line. Fieldwork Nov 2019 - Mar 2020 (2nd pass
  cancelled, Covid). The synoptic page is TWO COLUMNS of key figures; the
  poverty block is the right half, read with `half: right`, and the overall
  and extreme blocks print the same labels -- told apart in a bespoke pass.
  No line value is printed in the synthesis.

* `mauritania_2014_poverty` -- ONS "Profil de pauvreté de la Mauritanie 2014"
  (EPCV 2014). Line 169 445 UM per person per year (old ouguiya, MRO --
  before the 2018 redenomination), extreme line 126 035 UM (Annexe 3).
  Annex tables:
    A-1.1  P0 P1 P2 + contributions by milieu and sex of head (persons)
    A-1.2  13 wilayas, same (persons)
    A-1.3  by education, household type, socio-economic group and branch of
           the head (persons); branch rows carry "Branche: " in
           `characteristic` (they share the employment topic)
    A-1.4  extreme line, milieu + wilaya, HOUSEHOLDS (left block) and PERSONS
           (right block) -- order confirmed by the prose p. 30 (persons 16,6%,
           rural 25,1%; households rural 17,6%)
    A-1.6  wilayas + national for 2004 and 2008 (2014 columns repeat A-1.2)
    1-4    2008 milieu (Rural/Urbain) -- the 2008 columns only
    1-5    households: wilayas, milieu, sex of head
  2004 and 2008 rows carry their own survey and line (94 650 / 129 600 UM).

* `mauritania_annuaire_poverty` -- ANSADE "Annuaire socio-démographique
  2024", Tableau 6.12: P0 by wilaya and milieu, 2000/2004/2008/2014/2019.
  The 2004 and 2008 columns equal the 2014 profile's and are skipped. THE
  2014 COLUMN DIFFERS from the 2014 profile (national 30,9 vs 31,0; Hodh
  Chargui 29,4 vs 28,3), so it is kept under its own survey label, not merged
  over the profile's. 2019 national/urban/rural equal the synthesis.

CROSS-CHECK (verbatim): 2019 P0 28,2 / P1 7,6 / P2 3,1, urban 14,4, rural
41,2; extreme 12,8 / 3,2 / 1,3. 2014 P0 31,0 / 9,4 / 4,1; Guidimagha 49,1;
households 22,3; extreme persons 16,6, households 10,9. 2008 42,0 / 14,5 /
6,9; 2004 46,7. Annuaire 2000 national 51,0; Nouakchott 2019 14,3.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T
from ._vocab import label_rows
from .poverty_tables import make_parser

_FGT = ("headcount", "gap", "severity")
_CTR = ("poor_share", "gap_contribution", "severity_contribution")
_FGT_CTR = [{"metric": m} for m in _FGT + _CTR]

_URB = {"topic": "locality", "locality": "urban", "locality_label": "Urbain"}
_RUR = {"topic": "locality", "locality": "rural", "locality_label": "Rural"}

# ---------------------------------------------------------------- 2019 ----
LAYOUT = {
    "survey": "EPCV 2019-2020", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté", "period": "2019",
    "reference_period": "2019-2020", "tables": [],
}

_SYN = [  # (line regex, metric)
    (r"^(?:Pauvreté\s+)?Prévalence de la pauvreté \(P0\)\s*:", "headcount"),
    (r"^(?:Pauvreté\s+)?Profondeur de la pauvreté\s*:", "gap"),
    (r"^(?:Pauvreté\s+)?Sévérité de la pauvreté\s*:", "severity"),
]


def parse(path: str) -> pd.DataFrame:
    """The synoptic poverty block: two passes of P0/P1/P2 (overall, then
    extreme), each a national figure followed by Urbain and Rural lines."""
    pages = T._pages(path, halves=True)
    page = next((t for t in pages["right"] if "Prévalence de la pauvreté (P0)" in t), None)
    if page is None:
        raise ValueError(f"{path}: synoptic poverty block not found")
    rows, level, metric, seen_p0 = [], None, None, 0
    for line in (l.strip() for l in page.splitlines()):
        for pat, m in _SYN:
            if re.match(pat, line):
                if m == "headcount":
                    seen_p0 += 1
                    level = "overall" if seen_p0 == 1 else "extreme"
                metric = m
                rows.append(dict(metric=m, line_level=level, value=C.numbers_in(line, ",")[-1]))
                break
        else:
            mm = re.match(r"^(Urbain|Rural)\s+([\d,]+)%$", line)
            if mm and metric:
                rows.append(dict(metric=metric, line_level=level, value=C.to_number(mm.group(2), ","),
                                 **(_URB if mm.group(1) == "Urbain" else _RUR)))
            if line.startswith("Part des quintiles"):
                break
    if len(rows) != 18:
        raise ValueError(f"synoptic block gave {len(rows)} values, expected 18 "
                         f"(P0/P1/P2 x national/urban/rural x 2 lines)")
    out = []
    for r in rows:
        lvl = r.pop("line_level")
        out.append(C.row(
            survey=LAYOUT["survey"], welfare_aggregate="consumption",
            line_type="national", line_level=lvl,
            line_name="Seuil de pauvreté" if lvl == "overall" else "Seuil d'extrême pauvreté",
            period="2019", reference_period="2019-2020", frequency="ad_hoc",
            characteristic=r.get("locality_label", "Total"), **r))
    return pd.DataFrame(out)


# ---------------------------------------------------------------- 2014 ----
_W14 = {"label_ok": r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\-\.\/ ]+$"}
_EXT = {"line_level": "extreme", "line_name": "Seuil d'extrême pauvreté",
        "line_value": 126035, "line_unit": "MRO per person per year"}


def _yr(year, survey, line_value):
    return {"period": year, "survey": survey, "reference_period": year,
            "line_value": line_value, "line_unit": "MRO per person per year"}


_2004 = _yr("2004", "EPCV 2004", 94650)
_2008 = _yr("2008", "EPCV 2008", 129600)

LAYOUT_2014 = {
    "survey": "EPCV 2014", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté", "line_value": 169445,
    "line_unit": "MRO per person per year",
    "period": "2014", "reference_period": "2014",
    "tables": [
        {   # A-1.1 milieu, sex of head (persons)
            "page_contains": ["tableau-a-1.1", "tendances de la pauvreté suivant le milieu"],
            "start": r"^Tableau-A-1\.1\s*:", "end": r"^Tableau-A-1\.2", "exact_numbers": True,
            "columns": _FGT_CTR,
            "rows": [
                {"match": r"^Urbain(?=\s)", **_URB}, {"match": r"^Rural(?=\s)", **_RUR},
                {"match": r"^Homme(?=\s)", "topic": "sex_of_head", "characteristic": "Homme", "sex": "male"},
                {"match": r"^Femme(?=\s)", "topic": "sex_of_head", "characteristic": "Femme", "sex": "female"},
                {"match": r"^Ensemble(?=\s)"},
            ],
        },
        {   # A-1.2 wilayas (persons)
            "page_contains": ["tableau-a-1.2"], "start": r"^Tableau-A-1\.2\s*:", "end": r"^Page",
            "columns": _FGT_CTR,
            "row_scan": {"expect_rows": 13, "exclude_labels": ["Ensemble"], **_W14},
        },
        # A-1.3 characteristics of the head (persons)
        *[{"page_contains": ["tableau-a-1.3"], "start": start, "end": end, "exact_numbers": True,
           "columns": _FGT_CTR, "rows": label_rows(topic, labels)}
          for start, end, topic, labels in (
              (r"^Niveau d’instruction", r"^Typologie du ménage", "education_of_head",
               ["Primaire", "Secondaire général", "Secondaire technique et professionnel",
                "Supérieur", "Traditionnel", "Alphabétisation", "Aucun", "Ne sait pas"]),
              (r"^Typologie du ménage", r"^Groupes socio", "household_type",
               ["Ménage unipersonnel", "Couples sans enfant", "Couples avec enfants",
                "Monoparental nucléaire", "Monoparental élargi", "Famille élargie"]),
              (r"^Groupes socio-économiques", r"^Branches d", "employment_of_head",
               ["Salarié du secteur public", "Salarié du secteur privé", "Indépendant agricole",
                "Indépendant non agricole", "Aides familiaux et autre occupés", "Chômeurs",
                "Inactifs"]))],
        {   # A-1.3 branches of the head: prefixed, they share the employment topic
            "page_contains": ["tableau-a-1.3"], "start": r"^Branches d", "end": r"^Ensemble",
            "exact_numbers": True, "columns": _FGT_CTR,
            "rows": [dict(r, characteristic="Branche: " + r["characteristic"])
                     for r in label_rows("employment_of_head", [
                         "Agriculture", "Elevage", "Pêche", "Mines et extraction",
                         "Industrie alimentaire", "Industrie artisanales",
                         "Autres industries manufacturières", "BTP", "Transport",
                         "Communications", "Commerce/Vente", "Services divers", "Education",
                         "Santé", "Administration", "Autre activité", "ND/NC"])],
        },
        {   # A-1.4 extreme line: households (left 6) | persons (right 6)
            "page_contains": ["tableau-a-1.4"], "start": r"^Tableau-A-1\.4\s*:", "end": r"^Tableau-A-2",
            "columns": [dict(c, unit_of_analysis="household", **_EXT) for c in _FGT_CTR]
                       + [dict(c, unit_of_analysis="person", **_EXT) for c in _FGT_CTR],
            "row_scan": {"expect_rows": 16, **_W14,
                         "label_map": {"Ensemble": "Total country", "Hodh Charghy": "Hodh Chargui",
                                       "Hodh Gharby": "Hodh Gharbi", "D. Nouadhibou": "Nouadhibou"},
                         "row_attrs": {"Rural": {"geography": "Total country", **_RUR},
                                       "Urbain": {"geography": "Total country", **_URB}}},
        },
        {   # A-1.6 wilayas 2004 and 2008 (2014 columns repeat A-1.2)
            "page_contains": ["tableau-a-1.6"], "start": r"^Tableau-A-1\.6\s*:", "end": r"^Tableau-A-1\.7",
            "columns": [dict(metric=m, **_2004) for m in _FGT] + [dict(metric=m, **_2008) for m in _FGT]
                       + [{"skip": True}] * 3,
            "row_scan": {"expect_rows": 14, **_W14,
                         "label_map": {"National": "Total country", "Hodh El Chargui": "Hodh Chargui",
                                       "Hodh El Gharbi": "Hodh Gharbi", "D. Nouadhibou": "Nouadhibou",
                                       "Tiris Zemmour": "Tirs Zemmour"}},
        },
        {   # 1-4: the 2008 milieu columns
            "page_contains": ["tableau 1-4"], "start": r"^Tableau 1-4\s*:", "end": r"^En synthétisant",
            "exact_numbers": True,
            "columns": [{"skip": True}] * 3 + [dict(metric=m, **_2008) for m in _FGT] + [{"skip": True}] * 3,
            "rows": [{"match": r"^Rural(?=\s)", **_RUR}, {"match": r"^Urbain(?=\s)", **_URB}],
        },
        {   # 1-5: households, wilayas
            "page_contains": ["tableau 1-5"], "start": r"^Tableau 1-5\s*:", "end": r"^Milieu de résidence",
            "columns": [dict(c, unit_of_analysis="household") for c in _FGT_CTR],
            "row_scan": {"expect_rows": 13, **_W14,
                         "label_map": {"Hodh El Gharbi": "Hodh Gharbi"}},
        },
        {   # 1-5: households, milieu / sex / national
            "page_contains": ["tableau 1-5"], "start": r"^Milieu de résidence", "end": r"^1\.6\.",
            "exact_numbers": True,
            "columns": [dict(c, unit_of_analysis="household") for c in _FGT_CTR],
            "rows": [
                {"match": r"^Rural(?=\s)", **_RUR}, {"match": r"^Urbain(?=\s)", **_URB},
                {"match": r"^Homme(?=\s)", "topic": "sex_of_head", "characteristic": "Homme", "sex": "male"},
                {"match": r"^Femme(?=\s)", "topic": "sex_of_head", "characteristic": "Femme", "sex": "female"},
                {"match": r"^Ensemble(?=\s)"},
            ],
        },
    ],
}
_parse_2014_engine = make_parser(LAYOUT_2014)


def parse_2014(path: str) -> pd.DataFrame:
    """The engine over the profile, with ONE text repair: every Ensemble row
    ends its contributions with "100 100 100", which the French
    space-thousands rule reads as the single number 100100100 -- the row then
    has too few cells and is dropped. The exact run is rewritten "100,0 100,0
    100,0" (same values) before the tables are read."""
    real = T._pages

    def patched(p, halves=True):
        pages = real(p, halves)
        fix = lambda t: re.sub(r"(?<![\d,])100 100 100(?![\d,])", "100,0 100,0 100,0", t)  # noqa: E731
        return {k: [fix(t) for t in v] for k, v in pages.items()}

    T._pages = patched
    try:
        return _parse_2014_engine(path)
    finally:
        T._pages = real


# ------------------------------------------------------------ annuaire ----
# Wilaya names are normalised to the 2014 profile's spellings (the annuaire
# prints "D. Nouadhibou", "Tiris Zemmour", "Hodh El Gharbi", "lnchiri" with a
# lower-case L) so one wilaya is one geography across the three sources.
def _ann(year, survey):
    return {"metric": "headcount", "period": year, "survey": survey, "reference_period": year}


LAYOUT_ANNUAIRE = {
    "survey": "EPCV (Annuaire socio-démographique 2024)", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall", "line_name": "Seuil de pauvreté",
    "period": "2019", "reference_period": "2019-2020",
    "tables": [{
        "page_contains": ["tableau 6.12", "pauvreté monétaire, 2000-2019"],
        "columns": [_ann("2000", "EPCV 2000"), {"skip": True}, {"skip": True},
                    _ann("2014", "EPCV 2014 (série de l'Annuaire 2024)"),
                    dict(_ann("2019", "EPCV 2019-2020"), reference_period="2019-2020")],
        "row_scan": {"expect_rows": 16, **_W14,
                     "label_map": {"National": "Total country", "lnchiri": "Inchiri",
                                   "D. Nouadhibou": "Nouadhibou", "Tiris Zemmour": "Tirs Zemmour",
                                   "Hodh El Gharbi": "Hodh Gharbi", "Guidimakha": "Guidimagha"},
                     "row_attrs": {"Urbain": {"geography": "Total country", **_URB},
                                   "Rural": {"geography": "Total country", **_RUR}}},
    }],
}
parse_annuaire = make_parser(LAYOUT_ANNUAIRE)
