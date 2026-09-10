"""Guinea — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# GUINEA -- INS, "Analyse de la pauvreté" (RGPH3 2014), Tableau 2-1.
#
# REWRITTEN against the downloaded PDF. Guinea's table is the widest in the
# set and the only one that puts the LOCALITY in the columns and the metric in
# a column group:
#
#            Incidence (H)          Intensité (A)          MPI
#           Urbain Rural Total   Urbain Rural Total   Urbain Rural Total
#   Boké      34,1  85,9  72,7     41,6  52,9  51,5     14,2  45,4  37,5
#
# so one printed row yields nine values across three metrics and three
# localities.
#
# *** THE INDEX IS PRINTED AS A PERCENTAGE, NOT AS A 0-1 INDEX. *** Guinée
# reads 35,4 and not 0,354, and 68,7 x 51,5 = 35,4 confirms it. The M0 columns
# therefore declare `unit: percent`; the value is never divided by 100 to make
# it look like everyone else's. This is the same trap Morocco sets, and the
# earlier run failed on it in the opposite direction, harvesting a population
# count of 100 110 769 as a percentage.
#
# Conakry is the one row with missing cells -- it has no rural population, so
# its three rural columns are printed as "-". Rather than let the row be
# dropped for being short, Conakry gets its own six-column spec. Nothing is
# shifted left to fill the gap.
#
# Tableau 2-2 ("contribution des indicateurs par région") is NOT harvested:
# its rows sum to about 165%, so despite the caption those numbers are not
# contributions, and guessing what they are would be worse than leaving them.
# It is recorded as deferred in PENDING.md.
#
# The report states the index uses NINE indicators ("Le MPI a utilisé neuf
# indicateurs"), which is what Tableau 2-2's nine columns show; the descriptor
# previously said eight.
#
# CROSS-CHECK (verbatim):
#   Guinée  H 33,1 / 87,7 / 68,7 | A 42,5 / 53,4 / 51,5 | MPI 14,1 / 46,8 / 35,4
#   Kankan  H 60,3 / 94,7 / 87,8 | MPI 26,4 / 53,3 / 47,9
#   Conakry H 16,8 / - / 16,8    | A 40,8 / - / 40,8 | MPI 6,8 / - / 6,8
#   Kindia  MPI total 34,1 (the lowest after Conakry)
# =========================================================================
def _gn_cols(with_rural: bool = True) -> list[dict]:
    out = []
    for metric, unit in (("incidence_H", None), ("intensity_A", None),
                         ("index_M0", "percent")):
        for loc, label in (("urban", "Urbain"), ("rural", "Rural"),
                           ("all", "Total")):
            if loc == "rural" and not with_rural:
                continue
            col = {"metric": metric, "locality": loc, "locality_label": label,
                   "topic": "locality" if loc != "all" else "total"}
            if unit:
                col["unit"] = unit
            out.append(col)
    return out


LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Pauvreté multidimensionnelle (RGPH3)",
    "survey": "RGPH3 2014 (3e Recensement Général de la Population et de l'Habitation)",
    "k_cutoff": 33.33, "n_dimensions": 3, "n_indicators": 9,
    "unit_of_analysis": "household", "frequency": "ad_hoc", "decimal": ",",
    "period": "2014", "reference_period": "RGPH3 2014",
    "tables": [{
        "page_contains": ["indice de pauvreté", "milieu de résidence"],
        "exact_numbers": True,
        "columns": _gn_cols(),
        "rows": [
            {"match": r"^Bok[ée]\b", "geography": "Boké"},
            {"match": r"^Conakry\b", "geography": "Conakry",
             "columns": _gn_cols(with_rural=False)},
            {"match": r"^Faranah\b", "geography": "Faranah"},
            {"match": r"^Kankan\b", "geography": "Kankan"},
            {"match": r"^Kindia\b", "geography": "Kindia"},
            {"match": r"^Lab[ée]\b", "geography": "Labé"},
            {"match": r"^Mamou\b", "geography": "Mamou"},
            {"match": r"^N'?z[ée]r[ée]kor[ée]\b", "geography": "Nzérékoré"},
            {"match": r"^Guin[ée]e\b", **_NATIONAL},
        ],
    }],
}


parse = make_parser(LAYOUT)
