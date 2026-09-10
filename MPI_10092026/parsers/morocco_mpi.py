"""Morocco — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# MOROCCO -- HCP, "Cartographie de la pauvreté multidimensionnelle, paysage
# territorial et dynamique".
#
# TWO THINGS MAKE THIS THE MOST ERROR-PRONE LAYOUT HERE.
#
# 1. **M0 IS PRINTED AS A PERCENTAGE**, not a decimal in [0,1]: the national
#    IPM for 2024 is 2,5 -- meaning 2,5%, not 2.5 index points. The M0 columns
#    therefore declare `unit: percent`, and the schema range-checks them against
#    0..100 instead of 0..1. Nothing is rescaled: rescaling to force it into the
#    usual convention would be recomputing a published figure.
# 2. **NINE NUMERIC COLUMNS**, not three: each of H, A and IPM is split
#    Urbain / Rural / Ensemble. The order is H(u,r,e), A(u,r,e), IPM(u,r,e).
#
# Census-based (RGPH 2014 and 2024), which is why it maps to commune level and
# carries no confidence intervals.
#
# CROSS-CHECK (national 2024): H 3,0 / 13,1 / 6,8 ; A 35,3 / 39,1 / 36,7 ;
# IPM 1,1 / 5,1 / 2,5. National 2014 ensemble: H 11,9 ; A 38,1 ; IPM 4,5.
# Marrakech-Safi 2024 ensemble: 7,9 / 37,4 / 3,0.
# =========================================================================
def _ma_triplet(metric: str, unit: str | None = None) -> list[dict]:
    base = {"metric": metric}
    if unit:
        base["unit"] = unit
    return [
        {**base, "locality": "urban", "locality_label": "Urbain", "topic": "locality"},
        {**base, "locality": "rural", "locality_label": "Rural", "topic": "locality"},
        {**base, "locality": "all", "locality_label": "Ensemble"},
    ]


LAYOUT = {
    "mpi_type": "national",
    "measure_name": "IPM (Cartographie de la pauvreté multidimensionnelle)",
    "survey": "RGPH 2024 (Recensement Général de la Population et de l'Habitat)",
    "k_cutoff": 33, "n_dimensions": 3, "n_indicators": 10,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "period": "2024", "reference_period": "RGPH 2024",
    "tables": [{
        "page_contains": ["intensit"],
        "take": "trailing",
        "columns": (_ma_triplet("incidence_H")
                    + _ma_triplet("intensity_A")
                    + _ma_triplet("index_M0", unit="percent")),
        "rows": [
            {"match": r"^National\b", **_NATIONAL},
            {"match": r"^R[ée]gion\b", "characteristic": "Région"},
            {"match": r"^Tanger[- ]T[ée]touan", "geography": "Tanger-Tétouan-Al Hoceïma"},
            {"match": r"^Oriental\b", "geography": "Oriental"},
            {"match": r"^F[èe]s[- ]Mekn[èe]s", "geography": "Fès-Meknès"},
            {"match": r"^Rabat[- ]Sal[ée]", "geography": "Rabat-Salé-Kénitra"},
            {"match": r"^B[ée]ni Mellal", "geography": "Béni Mellal-Khénifra"},
            {"match": r"^Casablanca[- ]Settat", "geography": "Casablanca-Settat"},
            {"match": r"^Marrakech[- ]Safi", "geography": "Marrakech-Safi"},
            {"match": r"^Dr[âa]a[- ]Tafilalet", "geography": "Drâa-Tafilalet"},
            {"match": r"^Souss[- ]Massa", "geography": "Souss-Massa"},
            {"match": r"^Guelmim[- ]Oued Noun", "geography": "Guelmim-Oued Noun"},
            {"match": r"^La[âa]youne[- ]Sakia", "geography": "Laâyoune-Sakia El Hamra"},
            {"match": r"^Dakhla[- ]Oued", "geography": "Dakhla-Oued Ed-Dahab"},
        ],
    }],
}


parse = make_parser(LAYOUT)
