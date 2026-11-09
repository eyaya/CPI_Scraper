"""Equatorial Guinea -- monetary poverty (INEGE, ENH2 2023).

"II Encuesta Nacional de Hogares", informe definitivo (Nov 2024), section
9.2. Gráfico 33 prints the three FGT measures as TEXT DATA LABELS, each
place's name on the line with its three values, in the order of the three
panel headings (A. Incidencia | B. Brecha | C. Severidad) -- published
figures (the Burkina Faso rule). Its P0s are the same as the Anuario
Estadístico 2026's Tabla 160 (50,7 / 46,7 / 59,7; Bioko Norte 30,7; Wele
Nzas 65,8), which is a table. National line 810 022 FCFA per person per year
(67 502 a month; 6,26 USD PPA 2017 a day), consumption per capita.

NOT collected: the international US$2.15 / 6.85 (2017 PPP) rates (4,4 % /
55,3 %) -- prose and a cross-country chart only; Gini (inequality).
"""
from __future__ import annotations

from .poverty_tables import make_parser

_PROV = ["Wele Nzas", "Litoral", "Kie Ntem", "Centro Sur", "Bioko Sur", "Bioko Norte", "Annobón"]

LAYOUT = {
    "survey": "ENH2 2023", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Línea de pobreza nacional ENH2", "line_value": 810022,
    "line_unit": "XAF per person per year",
    "period": "2023", "reference_period": "2023",
    "tables": [{
        "page_contains": ["gráfico 33", "foster–greer–thorbecke"],
        "exact_numbers": True,
        "columns": [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}],
        "rows": [{"match": r"^Nacional(?=\s+\d)"}]
                + [{"match": r"^" + p + r"(?=\s+\d)", "geography": p} for p in _PROV]
                + [{"match": r"^Rural(?=\s+\d)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
                   {"match": r"^Urbana(?=\s+\d)", "topic": "locality", "locality": "urban", "locality_label": "Urbana"}],
    }],
}

parse = make_parser(LAYOUT)
