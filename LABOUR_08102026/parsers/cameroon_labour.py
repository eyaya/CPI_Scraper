"""Cameroon — INS EESI3 (Troisième Enquête sur l'Emploi et le Secteur Informel),
Phase 1 "Emploi", rapport principal, 2021.

THE MAIN REPORT, NOT THE DÉPLIANT. `unemployment/` reads the two-page dépliant,
whose composition titles ("par secteur d'activité", "par secteur
institutionnel", "par statut du travailleur") carry no values at all -- which
is why Cameroon was swept as empty here. The 173-page main report prints them
as tables (Uganda's lesson again: a key-findings note is not the report).
Phase 1 is the HOUSEHOLD employment survey; Phase 2 (the informal production
units) is a separate publication and is not used.

Four tables, each holding two stacked distributions under sub-headings, read
as separate blocks pinned to their own page (the same sub-headings recur in the
youth and child tables):

* Tableau 3.7  (14+)   secteur institutionnel | secteur d'activité, by milieu,
                       sex and age group;
* Tableau 3.8  (14+)   GSE | CSP, by milieu and sex;
* Tableau 3.15 (15-34) as 3.7, by milieu and sex (no age columns);
* Tableau 3.16 (15-34) as 3.8.

THE COLUMN ORDER OF 3.7 IS NOT THE ORDER ITS HEADER READS IN. The text layer
gives "Urbain Rural Masculin Féminin Ensemble" and then "14-34 35-64 65 ans ou
plus" -- but each data row carries eight values, and page geometry puts
Ensemble at the RIGHT (x 480-513), after the three age columns (x 379-461).
Confirmed by the rows themselves (Public: male 9,9 / female 6,1 / Ensemble 8,2
-- the overall figure lies between the sexes; it is not 6,4) and by the prose
("59,2% des personnes de 14-34 ans ... informel non agricole" = column 5).

TOPICS. "Secteur institutionnel" here is Public / Privé formel / Informel non
agricole / Informel agricole -- a production-unit split whose main axis is
formal vs informal, filed as `formality` like the unit-of-production tables of
Somalia, Eswatini and Liberia. "Secteur d'activité" (Primaire / Industrie /
Commerce / Services) is `industry`. The CSP (cadre, employé qualifié, manœuvre,
patron, compte propre, aide familial) partitions the employed and is filed as
`employment_status` -- a hybrid of status and skill level, hence National.

NOT COLLECTED: the GSE blocks of 3.8/3.16 (each group crosses institutional
sector with status -- "Salarié de l'informel non agricole" -- which one
category column cannot hold); Tableaux 3.18-3.20 (children 10-17, below the
survey's own 14+ working-age line); 3.6 (a single informal-share row by
region); chapter 5's youth tables 5.11/5.12 (a different youth universe
"jeunes de 15-34 ans" including non-employed); chapter 6's 2005/2010/2021
comparisons (rates). Graphiques 3.4/3.5 are charts.

NO NOMENCLATURE IS NAMED against any table (CITI, CITP, NAEMA, NACAM absent)
-> National. Base 14+, the survey's own definition.

PERIOD 2021: collection began 10 May 2021.

CROSS-CHECK (Ensemble, 14+): public 8,2; informel agricole 34,7; services
32,7; travailleur pour propre compte 55,5; employé qualifié 21,6. Youth:
informel non agricole 59,1; propre compte 48,5.
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser

_P = {"measure": "share", "unit": "percent"}
_URB = {"locality": "urban", "locality_label": "Urbain", **_P}
_RUR = {"locality": "rural", "locality_label": "Rural", **_P}
_M = {"sex": "male", **_P}
_F = {"sex": "female", **_P}

# Tableau 3.7: Urbain Rural Masculin Féminin | 14-34 35-64 65+ | Ensemble
_COLS_37 = [_URB, _RUR, _M, _F,
            {"age_group": "14-34 ans", **_P}, {"age_group": "35-64 ans", **_P},
            {"age_group": "65 ans ou plus", **_P}, _P]
# Tableaux 3.8, 3.15, 3.16: Urbain Rural Masculin Féminin Ensemble
_COLS_5 = [_URB, _RUR, _M, _F, _P]
_Y = {"age_group": "15-34 ans"}
_COLS_5_YOUTH = [{**c, **_Y} for c in _COLS_5]


def _block(table: str, heading: str, topic: str, classification: str,
           columns: list, rows: int) -> dict:
    return {
        "caption": rf"^{heading}$",
        # The same sub-headings recur in 3.15/3.16 and the child tables
        # 3.18-3.20: pin each block to the page carrying its own table's caption.
        "page_contains": [f"Tableau {table}:"],
        "topic": topic, "classification": classification,
        "columns": columns,
        "series_code": f"EESI3 T{table}",
        # Prose follows the Total row with no caption between.
        "end_after": r"^Total\s+100,0",
        "row_scan": {"expect_rows": rows},
    }


LAYOUT = {
    "survey": "Troisième Enquête sur l'Emploi et le Secteur Informel "
              "(EESI3), Phase 1",
    "frequency": "ad_hoc", "working_age_base": "14+",
    "period": "2021", "reference_period": "EESI3 2021",
    "decimal": ",",
    "tables": [
        _block("3.7", "Secteur institutionnel", "formality", "Not applicable",
               _COLS_37, 5),
        _block("3.7", "Secteur d.activité", "industry", "National",
               _COLS_37, 5),
        _block("3.8", "Catégorie socioprofessionnelle", "employment_status",
               "National", _COLS_5, 7),
        _block("3.15", "Secteur institutionnel", "formality", "Not applicable",
               _COLS_5_YOUTH, 5),
        _block("3.15", "Secteur d.activité", "industry", "National",
               _COLS_5_YOUTH, 5),
        _block("3.16", "Catégorie socioprofessionnelle", "employment_status",
               "National", _COLS_5_YOUTH, 7),
    ],
}

parse = make_parser(LAYOUT)
