"""Madagascar -- monetary-poverty layout (INSTAT, Rapport EPM 2021-2022, ch. 18).

EPM 2021-2022, fieldwork November 2021 - June 2022 (report §18.2.2: "une
période de huit mois de novembre 2021 à juin 2022"), published March 2024.
Welfare = real consumption per capita (household aggregate divided by
household SIZE, temporal and spatial deflators). Lines (Tableau 18.1, Ariary
per person per year): overall 1 453 987; extreme = the food component 986 047.

NOT COMPARABLE with ENSOMD 2012 or the EPM 1993-2010 series (§18.2.4: new
questionnaire, new line method, new deflators) -- so no back-series is taken.

Collected (PDF pages 365-377; report pages 331-343):
  18.2  milieu (Capitale / Autre Urbain / Rural / Ensemble): P0, poor share, population share
  18.3  same, extreme line
  18.4  milieu: P1, P2 and their contributions
  18.6  Urbain only (the two urban strata together): population share, P0,
        poor share, P1, P1 contribution. Its Rural and Total rows repeat 18.2/18.4.
        Its printed header says "Intensité | Sévérité" over P0 | P1 -- the values
        prove the columns are P0/contribution/P1/contribution (Rural 83,3 87,3
        37,6 89,7 = 18.2's and 18.4's rural values).
  18.7  23 regions: population share, P0 (ensemble / urbain / rural), poor
        share, P1, P1 contribution. The Ensemble row repeats national values.
  18.8  sex of head: share of households, P0 and extreme P0 of PERSONS and
        their poor share, then P0 / extreme P0 / poor share of HOUSEHOLDS
        (unit_of_analysis household; national 68,2 / 43,2 are taken from the
        Ensemble row, its person-level cells repeat 18.2/18.3).
  (untitled) household size: share of households, P0, poor share.
  18.9  marital status of head; 18.10 labour-force status of head;
  18.11 branch of activity of head; 18.12 occupation of head -- share of
        households, P0, extreme P0, poor share. 18.11/18.12 cover persons in
        households whose head is EMPLOYED (the report says so on p. 341), so
        their shares are within that universe.
Not collected: 18.5 (elasticities), Graphiques 18.1-18.3 (chart labels whose
pairing with bars is not recoverable from the text layer), 18.13-18.14
(inequality -- a separate indicator).

CROSS-CHECK (verbatim): P0 77,0; extreme 53,3; P1 33,8; P2 18,4; Rural 83,3;
Capitale 37,1; Analamanga 51,3 (P1 17,5); Androy 98,0 (P1 63,4); female-headed
76,1; households poor 68,2; 7 ou plus 91,0.
"""
from __future__ import annotations

from ._vocab import label_rows
from .poverty_tables import make_parser

_EXT = {"line_level": "extreme",
        "line_name": "Seuil de pauvreté extrême (composante alimentaire du seuil)",
        "line_value": 986047, "line_unit": "MGA per person per year"}
_HH = {"unit_of_analysis": "household"}
_SKIP = {"skip": True}


def _tbl(caption_re: str, contains: list[str], columns, rows, **kw):
    """A table bounded by its own caption line and the next "Source :" line,
    so tables sharing a page (18.3 above 18.4) never read each other's rows."""
    return {"page_contains": contains, "start": caption_re, "end": r"^Source\s*:",
            "exact_numbers": True, "columns": columns, "rows": rows, **kw}


_MILIEU = [
    {"match": r"^Capitale(?=\s)", "topic": "locality", "locality": "other", "locality_label": "Capitale"},
    {"match": r"^Autre Urbain(?=\s)", "topic": "locality", "locality": "other", "locality_label": "Autre Urbain"},
    {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
]
_ENSEMBLE = {"match": r"^(?:Ensemble|Total)(?=\s)"}

# Characteristic-of-the-head tables 18.9-18.12: structure | P0 | P0 extreme | contribution
_HEAD4 = [{"metric": "population_share", **_HH}, {"metric": "headcount"},
          {"metric": "headcount", **_EXT}, {"metric": "poor_share"}]

LAYOUT = {
    "survey": "EPM 2021-2022", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté monétaire national",
    "line_value": 1453987, "line_unit": "MGA per person per year",
    "period": "2021", "reference_period": "2021-2022",
    "tables": [
        _tbl(r"^Tableau 18\.2\s*:", ["tableau 18.2", "structure de la population"],
             [{"metric": "headcount"}, {"metric": "poor_share"}, {"metric": "population_share"}],
             _MILIEU + [_ENSEMBLE]),
        _tbl(r"^Tableau 18\.3\s*:", ["tableau 18.3", "pauvreté extrême contribution"],
             [{"metric": "headcount", **_EXT}, {"metric": "poor_share", **_EXT}, _SKIP],
             _MILIEU + [_ENSEMBLE]),
        _tbl(r"^Tableau 18\.4\s*:", ["tableau 18.4", "p1 contribution p2 contribution"],
             [{"metric": "gap"}, {"metric": "gap_contribution"},
              {"metric": "severity"}, {"metric": "severity_contribution"}],
             _MILIEU + [_ENSEMBLE]),
        _tbl(r"^Tableau 18\.6\s*:", ["tableau 18.6", "p0 contribution p1 contribution"],
             [{"metric": "population_share"}, {"metric": "headcount"}, {"metric": "poor_share"},
              {"metric": "gap"}, {"metric": "gap_contribution"}],
             [{"match": r"^Urbain(?=\s)", "topic": "locality", "locality": "urban",
               "locality_label": "Urbain"}]),
        {   # 18.7 -- 23 regions
            "page_contains": ["tableau 18.7", "ensemble urbain rural contribution"],
            "start": r"^Tableau 18\.7\s*:", "end": r"^Source\s*:",
            "columns": [{"metric": "population_share"}, {"metric": "headcount"},
                        {"metric": "headcount", "topic": "locality", "locality": "urban", "locality_label": "Urbain"},
                        {"metric": "headcount", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
                        {"metric": "poor_share"}, {"metric": "gap"}, {"metric": "gap_contribution"}],
            "row_scan": {"expect_rows": 23, "exclude_labels": ["Ensemble"]},
        },
        _tbl(r"^Tableau 18\.8\s*:", ["tableau 18.8", "sexe du chef de ménage"],
             [{"metric": "population_share", **_HH}, {"metric": "headcount"},
              {"metric": "headcount", **_EXT}, {"metric": "poor_share"},
              {"metric": "headcount", **_HH}, {"metric": "headcount", **_HH, **_EXT},
              {"metric": "poor_share", **_HH}],
             [{"match": r"^Homme(?=\s)", "topic": "sex_of_head", "characteristic": "Homme", "sex": "male"},
              {"match": r"^Femme(?=\s)", "topic": "sex_of_head", "characteristic": "Femme", "sex": "female"},
              # Ensemble: only the household-level national rates are new.
              {"match": r"^Ensemble(?=\s)",
               "columns": [_SKIP, _SKIP, _SKIP, _SKIP, {"metric": "headcount", **_HH},
                           {"metric": "headcount", **_HH, **_EXT}, _SKIP]}]),
        _tbl(r"^Tableau\s*:\s*Incidence de la pauvreté selon la taille du ménage",
             ["incidence de la pauvreté selon la taille du ménage et le milieu"],
             [{"metric": "population_share", **_HH}, {"metric": "headcount"}, {"metric": "poor_share"}],
             label_rows("household_size", ["1 ou 2", "3 ou 4", "5 ou 6", "7 ou plus"])),
        _tbl(r"^Tableau 18\.9\s*:", ["tableau 18.9", "statut matrimonial du chef"], _HEAD4,
             [{"match": r"^Marié(?=\s)", "topic": "marital_status_of_head", "characteristic": "Marié"},
              {"match": r"^Divorcé\(e\) / Séparé\(e\)(?=\s)", "topic": "marital_status_of_head",
               "characteristic": "Divorcé(e) / Séparé(e) / Veuf(ve)"},
              {"match": r"^Célibataire/Union libre(?=\s)", "topic": "marital_status_of_head",
               "characteristic": "Célibataire/Union libre"}]),
        _tbl(r"^Tableau 18\.10\s*:", ["tableau 18.10", "main d’œuvre du chef"], _HEAD4,
             label_rows("employment_of_head", ["En emploi", "Chômeur", "Hors de la main d’œuvre"])),
        _tbl(r"^Tableau\s*18\.11\s*:", ["tableau18.11", "branche d’activités du chef"], _HEAD4,
             [{"match": r"^Agriculture(?=\s)", "topic": "employment_of_head", "characteristic": "Agriculture"},
              {"match": r"^Industrie manufacturière(?=\s)", "topic": "employment_of_head",
               "characteristic": "Industrie manufacturière"},
              {"match": r"^Construction(?=\s)", "topic": "employment_of_head", "characteristic": "Construction"},
              {"match": r"^Exploitation minière et extraction de car-(?=\s)", "topic": "employment_of_head",
               "characteristic": "Exploitation minière et extraction de carrières ; Production et "
                                 "distribution d’électricité, de gaz et d’eau"},
              {"match": r"^Services marchands \(Commerce ;(?=\s)", "topic": "employment_of_head",
               "characteristic": "Services marchands (Commerce ; Transport ; Hébergement et "
                                 "restauration ; et Services aux entreprises et services administratifs)"},
              {"match": r"^Services non marchands \(Administration(?=\s)", "topic": "employment_of_head",
               "characteristic": "Services non marchands (Administration publique ; Services "
                                 "communautaires, sociaux et autres services et activités)"}]),
        _tbl(r"^Tableau 18\.12\s*:", ["tableau 18.12", "profession du chef"], _HEAD4,
             [{"match": r"^Directeurs, cadres, professions intellectuelles(?=\s)", "topic": "employment_of_head",
               "characteristic": "Directeurs, cadres, professions intellectuelles et scientifiques"},
              {"match": r"^Employés de type administratif, de services et(?=\s)", "topic": "employment_of_head",
               "characteristic": "Employés de type administratif, de services et commerçants et vendeurs"},
              {"match": r"^Agriculteurs et ouvriers agricoles qualifiés et(?=\s)", "topic": "employment_of_head",
               "characteristic": "Agriculteurs et ouvriers agricoles qualifiés et artisans qualifiés"},
              {"match": r"^Conducteurs d’installations et de machines, et(?=\s)", "topic": "employment_of_head",
               "characteristic": "Conducteurs d’installations et de machines, et ouvriers de l’assemblage"},
              {"match": r"^Professions élémentaires(?=\s)", "topic": "employment_of_head",
               "characteristic": "Professions élémentaires"}]),
    ],
}

parse = make_parser(LAYOUT)
