"""South Africa — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import COLS_H_A_M0, _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# SOUTH AFRICA -- Stats SA, "The South African MPI: Creating a
# multidimensional poverty index using census data" (Report 03-10-08).
# Columns `Headcount (H) | Intensity (A) | SAMPI`.
#
# UNIT OF ANALYSIS IS THE HOUSEHOLD, not the person -- alone among the
# survey-based measures here except Djibouti and Guinea. An H over households is
# not the same quantity as an H over people, so it is recorded and never pooled.
#
# The report is COMPARATIVE across Census 2001 and Census 2011, and both national
# rows appear in the same table. Each is captured with its own period.
#
# Fetch note: statssa.gov.za answers over http:// but 504s/403s over https://
# through Incapsula, and the file is only ever this one edition -- no SAMPI has
# been published from Census 2022.
#
# CROSS-CHECK: 2001 national 17.9 / 43.9 / 0.08; 2011 national 8.0 / 42.3 / 0.03.
# Provinces 2011: Eastern Cape 14.4 / 41.9 / 0.06; Gauteng 4.8 / 43.8 / 0.02;
# Western Cape 3.6 / 42.6 / 0.02. Unemployment contributed 39.8% of SAMPI by 2011.
# =========================================================================
# Stats SA writes COMMA decimals ("17,9%", "0,08"). Declaring "." here silently
# mis-read every cell (national H came out as 3.0, A as 0.0 and SAMPI as 3.0 —
# an M0 above 1, which the schema then rightly refused).
_DECIMAL = ","

# Table 6 prints BOTH census years side by side, six columns per province:
#   Province | 2001 H | 2001 A | 2001 SAMPI | 2011 H | 2011 A | 2011 SAMPI
_SA_PROVINCE_COLS = [
    {"metric": "incidence_H", "period": "2001", "reference_period": "Census 2001"},
    {"metric": "intensity_A", "period": "2001", "reference_period": "Census 2001"},
    {"metric": "index_M0", "period": "2001", "reference_period": "Census 2001"},
    {"metric": "incidence_H", "period": "2011", "reference_period": "Census 2011"},
    {"metric": "intensity_A", "period": "2011", "reference_period": "Census 2011"},
    {"metric": "index_M0", "period": "2011", "reference_period": "Census 2011"},
]

_PROVINCES = ["Western Cape", "Eastern Cape", "Northern Cape", "Free State",
              "KwaZulu-Natal", "North West", "Gauteng", "Mpumalanga", "Limpopo"]

LAYOUT = {
    "mpi_type": "national",
    "measure_name": "SAMPI",
    "survey": "Census 2011 (compared with Census 2001)",
    "k_cutoff": 33.3, "n_dimensions": 4, "n_indicators": 11,
    "unit_of_analysis": "household", "frequency": "ad_hoc", "decimal": _DECIMAL,
    "period": "2011", "reference_period": "Census 2011",
    "tables": [
        # Table 4 -- national, one row per census year (NOT per province).
        {
            "page_contains": ["poverty measures for census"],
            # This table's ROW LABEL IS ITSELF A NUMBER ('2001 17,9% 43,9% 0,08'),
            # so the year is scanned as the first data cell and shifts every
            # column by one -- H would read 2001, M0 would read A. The leading
            # skip consumes it.
            "columns": [{"skip": True}] + COLS_H_A_M0,
            "rows": [
                {"match": r"^2001\b", "period": "2001",
                 "reference_period": "Census 2001", **_NATIONAL},
                {"match": r"^2011\b", "period": "2011",
                 "reference_period": "Census 2011", **_NATIONAL},
            ],
        },
        # Table 6 -- the same measures by province, both years on one line.
        {
            "page_contains": ["provincial level"],
            "columns": _SA_PROVINCE_COLS,
            "rows": [
                {"match": r"^%s\b" % p.replace("-", "[- ]"), "geography": p}
                for p in _PROVINCES
            ],
        },
    ],
}


parse = make_parser(LAYOUT)
