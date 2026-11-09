"""Madagascar -- EPM 2001, INSTAT rapport principal (novembre 2002).

Tableau 154 "Le profil de pauvreté par milieu et par faritany": population
share, P0 and share of the poor for Madagascar, the six former provinces, and
urban / rural x province. POINT decimals in this report ("69.6"). Person
level, national line. Provinces named "<name> (province)" as in the other
EPM modules.

The 2001 P0s here are the ones EPM 2002's Tableau 37 republishes (identical:
Mahajanga urbain 49.8, Toamasina urbain 60.1); EPM 2005's Tableau 178 prints
slightly different 2001 urban cells (50,7 / 60,8). All are kept under their
own survey labels.
NOT collected: Tableau 157 (probit determinants), the faritany chart.
The EPM 1993, 1997 and 1999 reports print no poverty-measure table; those
rounds come from EPM 2010's Tableaux 174-175 and EPM 2002's Tableau 37.

CROSS-CHECK (verbatim): 69.6; urban 44.1, rural 77.1; Fianarantsoa 83.2;
shares of the poor by province sum to 100.0.
"""
from __future__ import annotations

from .poverty_tables import make_parser

_PROV = ["Antananarivo", "Fianarantsoa", "Toamasina", "Mahajanga", "Toliara", "Antsiranana"]
_COLS = [{"metric": "population_share"}, {"metric": "headcount"}, {"metric": "poor_share"}]
_UL = {"topic": "locality", "locality": "urban", "locality_label": "Urbain"}
_RL = {"topic": "locality", "locality": "rural", "locality_label": "Rural"}


def _block(start, end, loc, national):
    rows = [{"match": rf"^{p}(?=\s+\d)", "geography": f"{p} (province)", **loc} for p in _PROV]
    rows.append({"match": rf"^{national}(?=\s+\d)", **loc})
    return {"page_contains": ["tableau 154 : le profil de pauvreté par milieu et par faritany"],
            "start": start, "start_inclusive": True, "end": end, "exact_numbers": True,
            "columns": _COLS, "rows": rows}


LAYOUT = {
    "survey": "EPM 2001", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ".", "line_type": "national", "line_level": "overall",
    "line_name": "Seuil national de pauvreté", "period": "2001", "reference_period": "2001",
    "tables": [
        _block(r"^Madagascar", r"^Urbaine", {}, "Madagascar"),
        _block(r"^Urbaine", r"^Rurale", _UL, "Total"),
        _block(r"^Rurale", r"^Source", _RL, "Total"),
    ],
}

parse = make_parser(LAYOUT)
