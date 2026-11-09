"""Comoros -- monetary poverty (INSEED, EHCVM 2024).

"Principaux résultats de l'enquête sur la pauvreté 2024" (updated 1 April
2026), Tableau 1: P0/P1/P2 nationally, for Moroni, the rest of Ngazidja,
Ndzuwani and Mwali, and urban/rural. Point decimals. The report prints no
line amount.

NOT collected:
* the 2020 figures. The 2024 note re-estimates 2020 on the 2024 method
  (national 51,3 %) only in a bar chart whose values are not ordered with
  their labels in the text layer; the 2020 note's own 44,8 % uses the older
  method, which the 2024 note says is not comparable -- and it, too, is
  charts and prose only.
* EIM 2004 / EBC 1995: collected by comoros_eim2004_poverty (printed as
  fractions, unit index).
"""
from __future__ import annotations

from .poverty_tables import make_parser

_COLS = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}]
_ISL = [("Ngazidja- Moroni", "Ngazidja - Moroni"),
        ("Ngazidja -Reste de Ngazidja", "Ngazidja - Reste de Ngazidja"),
        ("Ndzuwani", "Ndzuwani"), ("Mwali", "Mwali")]

LAYOUT = {
    "survey": "EHCVM 2024", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil national de pauvreté 2024",
    "period": "2024", "reference_period": "2024 (mai-novembre)",
    "tables": [{
        "page_contains": ["tableau 1", "profil de la pauvreté aux comores"],
        "exact_numbers": True, "columns": _COLS,
        "rows": [{"match": r"^Niveau national(?=\s+\d)"}]
                + [{"match": r"^" + printed.replace("-", r"\-") + r"(?=\s+\d)", "geography": name}
                   for printed, name in _ISL]
                + [{"match": r"^Zones urbaines(?=\s+\d)", "topic": "locality", "locality": "urban",
                    "locality_label": "Zones urbaines"},
                   {"match": r"^Zone rurale(?=\s+\d)", "topic": "locality", "locality": "rural",
                    "locality_label": "Zone rurale"}],
    }],
}

parse = make_parser(LAYOUT)
