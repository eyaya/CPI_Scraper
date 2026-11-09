"""DR Congo -- monetary-poverty layout (INS, Enquête 1-2-3 2012, Rapport global).

Part II chapter 1 ("Pauvreté et conditions de vie des ménages"), pp. 100-106.
Welfare = consumption per ADULT EQUIVALENT. The line (Tableau II.7.1) is a
pair of milieu lines -- 869 210,3 FC urban and 579 248,5 FC rural per adult
equivalent per year -- because INS reports the 2005-comparable method (one
urban line incl. Kinshasa); its Kinshasa-specific line (1 072 133,6 FC) is
printed but not used for any published rate. The line amount is therefore
carried only on the Urbain / Rural rows of 2012.

Every 2012 table gives each measure TWICE: over HOUSEHOLDS ("Ménages", % of
households poor) and over PERSONS ("Individus"). They are different
quantities (54,2 vs 63,4 nationally) and are told apart by `unit_of_analysis`.

Collected:
  II.1.1  P0 of persons in 2005 (Enquête 1-2-3 2005) by milieu and province.
          Its 2012 column repeats II.1.2 and is not read twice.
  II.1.2  P0/P1/P2, households and persons, Urbain / Rural / 11 provinces / Ensemble.
  II.1.3  P0 by sex of head, households and persons -- national (p.102) and by
          zone (pp.103-104). The zone table prints the zone name on the
          FÉMININ line only ("Masculin 51,5 60,9" / "Urbain Féminin 48,5 58,2"
          / "Total 50,8 60,4") and runs across a page break without its
          caption, so it is read by `_sex_by_zone` below, not by the engine.
          Its Total rows repeat II.1.2 and are skipped; its RDC block repeats
          the national table and is skipped. KASAÏ OCCIDENTAL IS NOT IN THIS
          TABLE -- the report omits its block (12 zones printed).
  II.1.5-9 P0/P1/P2, households and persons, by education, family type,
          marital status, age and socio-professional category of the head.
Not collected: II.1.10-19 (non-monetary "conditions de vie" poverty) and
II.1.20-26 (subjective poverty) -- different concepts, not FGT money-metric
measures; II.2.x (opinions); Ensemble rows of the characteristic tables
(repeat II.1.2).

PUBLISHED QUIRKS KEPT, NOT FIXED:
  * II.1.6's Individus header reads "Incidence Sévérité Profondeur", but the
    values are in P0 P1 P2 order: its Ensemble row is 63,4 26,5 14,5, which is
    II.1.2's P0 / P1 / P2, and every row has the second value above the third.
    Read as P0 P1 P2.
  * Rural persons' P0 is 65,2 in II.1.2 and II.1.1 but 65,3 in II.1.3's zone
    table (that Total row is not collected).
  * II.1.1 prints the 2005 national P0 as 71,3; the text says 71,34.

CROSS-CHECK (verbatim): persons P0 63,4 / P1 26,5 / P2 14,5 (2012), P0 71,3
(2005); households 54,2 / 21,6 / 11,5; Kinshasa persons 36,8, Kasaï Oriental
78,6; female-headed households 49,0%, persons 60,3%.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C
from ._vocab import label_rows
from .poverty_tables import make_parser

_LINE_UNIT = "CDF per adult equivalent per year"
_HH_IND = [{"metric": m, "unit_of_analysis": u}
           for u in ("household", "person") for m in ("headcount", "gap", "severity")]
_HH_IND_P0 = [{"metric": "headcount", "unit_of_analysis": u} for u in ("household", "person")]

# Province names as spelled in II.1.2; the other tables' spellings map onto them.
_PROVINCES = ["Kinshasa", "Bandundu", "Bas-Congo", "Katanga", "Kasaï Oriental",
              "Kasaï occidental", "Equateur", "Nord-Kivu", "Sud-Kivu", "Maniema",
              "Province Orientale"]
_ALIAS = {"Kasaï Orientale": "Kasaï Oriental", "Kasaï occidentale": "Kasaï occidental",
          "Kasai oriental": "Kasaï Oriental", "Kasai occidental": "Kasaï occidental",
          "Nord Kivu": "Nord-Kivu", "Sud Kivu": "Sud-Kivu",
          "Province orientale": "Province Orientale"}

_URB = {"topic": "locality", "locality": "urban", "locality_label": "Urbain"}
_RUR = {"topic": "locality", "locality": "rural", "locality_label": "Rural"}


def _geo_rows(provinces, national_label, national=True, lines=False):
    rows = [dict({"match": r"^Urbain(?=\s+[-\d,])"}, **_URB,
                 **({"line_value": 869210.3, "line_unit": _LINE_UNIT} if lines else {})),
            dict({"match": r"^Rural(?=\s+[-\d,])"}, **_RUR,
                 **({"line_value": 579248.5, "line_unit": _LINE_UNIT} if lines else {}))]
    for p in provinces:
        rows.append({"match": r"^" + re.escape(p) + r"(?=\s+[-\d,])",
                     "geography": _ALIAS.get(p, p)})
    if national:
        rows.append({"match": r"^" + national_label + r"(?=\s+[-\d,])"})
    return rows


def _char_table(caption, topic, labels):
    return {"page_contains": [caption.lower()],
            "start": re.escape(caption), "end": r"^Source",
            "columns": _HH_IND, "rows": label_rows(topic, labels)}


LAYOUT = {
    "survey": "Enquête 1-2-3 2012", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "percent_cells": True,
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté monétaire urbain/rural 2012",
    "period": "2012", "reference_period": "2012",
    "tables": [
        {   # II.1.1 -- the 2005 column only
            "page_contains": ["incidence de la pauvreté de 2005 et de 2012 selon le milieu"],
            "start": r"^Tableau II\.1\.1\.", "end": r"^Source",
            "columns": [{"metric": "headcount", "period": "2005", "reference_period": "2005",
                         "survey": "Enquête 1-2-3 2005",
                         "line_name": "Seuil de pauvreté monétaire urbain/rural 2005"},
                        {"skip": True}, {"skip": True}],
            "rows": _geo_rows(["Kinshasa", "Bandundu", "Bas-Congo", "Katanga",
                               "Kasaï Orientale", "Kasaï occidentale", "Equateur",
                               "Nord-Kivu", "Sud-Kivu", "Maniema", "Province Orientale"],
                              "RDC"),
        },
        {   # II.1.2 -- households and persons, P0 P1 P2
            "page_contains": ["pauvreté monétaire des ménages et des individus en 2012"],
            "start": r"^Tableau\. II\.1\.2\.", "end": r"^Source",
            "columns": _HH_IND,
            "rows": _geo_rows(_PROVINCES, "Ensemble", lines=True),
        },
        {   # II.1.3 (p.102) -- national, by sex of head
            "page_contains": ["incidence de pauvreté monétaire des ménages et des individus selon le sexe"],
            "start": r"^Tableau II\.1\.3\. Incidence", "end": r"^Source",
            "columns": _HH_IND_P0,
            "rows": [{"match": r"^Masculin(?=\s)", "topic": "sex_of_head",
                      "characteristic": "Masculin", "sex": "male"},
                     {"match": r"^Féminin(?=\s)", "topic": "sex_of_head",
                      "characteristic": "Féminin", "sex": "female"}],
        },
        _char_table("Tableau II.1.5. Pauvreté monétaire selon le niveau d’instruction du chef de ménage",
                    "education_of_head", ["Non scolarisé", "Primaire", "Programme non formel",
                                          "Secondaire", "Supérieur", "Professionnel(INPP)"]),
        _char_table("Tableau II.1.6. Pauvreté monétaire selon le type de famille",
                    "household_type", ["Personne seule", "Couple sans enfants",
                                       "Couple avec enfants", "Famille monoparentale",
                                       "Famille élargie"]),
        _char_table("Tableau II.1.7. Pauvreté monétaire selon la situation matrimoniale du chef de ménage",
                    "marital_status_of_head", ["Célibataire", "Marié(e) monogame",
                                               "Marié(e) polygame", "Union libre",
                                               "Divorcée", "Veuf / veuve"]),
        _char_table("Tableau II.1.8. Pauvreté monétaire selon la tranche d’âge du chef de ménage",
                    "age_of_head", ["15-24", "25-34", "35-44", "45-54", "55-64",
                                    "65-74", "75-84", "85&+"]),
        _char_table("Tableau II.1.9. Pauvreté monétaire selon la catégorie socio-professionnelle du chef de ménage",
                    "employment_of_head", ["Cadre", "Employé qualifié", "Manœuvre", "Patron",
                                           "Travailleur pour propre compte",
                                           "Aide familial/apprenti/Autre"]),
    ],
}

_engine = make_parser(LAYOUT)

_ZONE_CAPTION = "Tableau II.1.3. Pauvreté des ménages par sexe et zone géographique"


def _sex_by_zone(path: str) -> list[dict]:
    """II.1.3 by zone: triplets Masculin / <Zone> Féminin / Total, across a
    page break. The zone name is read from the Féminin line and applied to the
    Masculin line just above it."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:   # whole-page text only (cheaper than _pages)
        full = [pg.crop((0, 0, pg.width, pg.height)).extract_text() or "" for pg in pdf.pages]
    lines: list[str] = []
    for i, text in enumerate(full):
        src = text.splitlines()
        # The caption on a line of its own -- the List of Tables (p.12) prints
        # it too, followed by its page number.
        at = [k for k, l in enumerate(src) if l.strip() == _ZONE_CAPTION]
        if at:
            src = src[at[0] + 1:]
            nxt = full[i + 1].splitlines() if i + 1 < len(full) else []
            for l in src + nxt:
                if l.startswith("Source"):
                    break
                lines.append(l.strip())
            break
    if not lines:
        raise ValueError("II.1.3 (sexe x zone) caption not found")
    rows, pending_m = [], None
    for l in lines:
        m = re.match(r"^Masculin\s+(\d+,\d)\s+(\d+,\d)$", l)
        f = re.match(r"^(.+?)\s+Féminin\s+(\d+,\d)\s+(\d+,\d)$", l)
        if m:
            pending_m = (float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", ".")))
            continue
        if f:
            zone = f.group(1).strip()
            if pending_m is None:
                raise ValueError(f"II.1.3: Féminin line for {zone!r} without its Masculin line")
            if zone == "RDC":            # repeats the national table on p.102
                pending_m = None
                continue
            if zone == "Urbain":
                place = {"geography": "Total country", "locality": "urban", "locality_label": "Urbain"}
            elif zone == "Rural":
                place = {"geography": "Total country", "locality": "rural", "locality_label": "Rural"}
            else:
                geo = _ALIAS.get(zone, zone)
                if geo not in _PROVINCES:
                    raise ValueError(f"II.1.3: unknown zone {zone!r}")
                place = {"geography": geo}
            fv = (float(f.group(2).replace(",", ".")), float(f.group(3).replace(",", ".")))
            for sex, char, vals in (("male", "Masculin", pending_m), ("female", "Féminin", fv)):
                for unit, v in zip(("household", "person"), vals):
                    rows.append(C.row(
                        metric="headcount", value=v, survey=LAYOUT["survey"],
                        welfare_aggregate="consumption", unit_of_analysis=unit,
                        line_type="national", line_level="overall",
                        line_name=LAYOUT["line_name"], period="2012",
                        reference_period="2012", frequency="ad_hoc",
                        topic="sex_of_head", characteristic=char, sex=sex, **place))
            pending_m = None
    # 12 zones, not 13: the report's table goes Kasai oriental -> Equateur and
    # prints NO Kasaï occidental block at all (pp.103-104). Not reconstructed.
    if len(rows) != 12 * 4:
        raise ValueError(f"II.1.3 (sexe x zone): {len(rows)} values, expected 48 "
                         f"(12 zones x 2 sexes x 2 units) -- re-read the PDF")
    return rows


def parse(path: str) -> pd.DataFrame:
    return pd.concat([_engine(path), pd.DataFrame(_sex_by_zone(path))], ignore_index=True)
