"""Rwanda — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

from ._vocab import COLS_H_A_M0, _URBAN, _RURAL, _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# RWANDA -- NISR, "Multidimensional Poverty -- Thematic Report -- EICV7".
#
# PIN THE APEX DOMAIN: www.statistics.gov.rw serves a certificate with a
# hostname mismatch and fails TLS outright; statistics.gov.rw works.
#
# METHODOLOGY BREAK the report itself flags: EICV5 used k = 40%, EICV7 uses
# 33.3%, with an expanded asset list and adjusted education age ranges. Do not
# chain EICV5 and EICV7 values.
#
# COLUMN ORDER -- there is a POPULATION SHARE ahead of the three measures:
#
#     Province EICV7
#     Pop. Share  Incidence (H), %  Intensity (A); %  MPI (M0)
#     National    100   30.5   44.6   0.136
#
# The layout previously declared three columns and took the TRAILING three,
# which is right for this table but left the page selection doing the work:
# `page_contains: ["intensity"]` matches the methodology pages too, and a
# 'National ... 2023 ...' line in the front matter was read as a rate, which is
# what the 2023.0-outside-0..100 failure was. The caption is pinned instead and
# the share is consumed by an explicit skip, so neither depends on the other.
#
# The population share itself is dropped: it is a share of Rwanda's population,
# not an MPI measure, and this schema has no column for it.
#
# TABLES B.5 AND B.6 SHARE A PAGE and a shape -- area/province in one, wealth
# quintile in the other -- so one spec reads both and the row label decides.
#
# CROSS-CHECK (as PRINTED, not as rounded in the narrative -- the text says
# 'urban 15%' where Table B.5 prints 14.8): National 30.5 / 44.6 / 0.136;
# Urban 14.8 / 43.9 / 0.065; Rural 36.7 / 44.8 / 0.164; City of Kigali
# 12.4 / 43.0 / 0.053; Southern 35.2 / 45.0 / 0.158; Eastern 34.4 / 45.5 /
# 0.157. Quintiles Q1 54.6 / 46.3 / 0.253 down to Q5 7.0 / 42.2 / 0.030.
# =========================================================================
_QUINTILES = ["Q1", "Q2", "Q3", "Q4", "Q5"]

LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Rwanda MPI",
    "survey": "EICV7 (Integrated Household Living Conditions Survey)",
    "k_cutoff": 33.3, "n_dimensions": 4, "n_indicators": 13,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "period": "2024", "reference_period": "EICV7, October 2023 - October 2024",
    "tables": [{
        "page_contains": ["table b.5: incidence, intensity and mpi"],
        # THE QUINTILE LABELS CONTAIN A DIGIT -- 'Q1 20.00 54.6 46.3 0.253'
        # reads as five numbers, not four, and every quintile row came out
        # shifted one column left (H = the 20% population share, M0 = the
        # intensity). `leading_run` reads only the numbers that FOLLOW the
        # matched label.
        "leading_run": True,
        "columns": [{"skip": True}] + COLS_H_A_M0,   # 1st col = Pop. Share
        "rows": [
            {"match": r"^National\b", **_NATIONAL},
            {"match": r"^Urban\b", **_URBAN},
            {"match": r"^Rural\b", **_RURAL},
            {"match": r"^City of Kigali\b", "geography": "City of Kigali"},
            {"match": r"^Southern\b", "geography": "Southern Province"},
            {"match": r"^Western\b", "geography": "Western Province"},
            {"match": r"^Northern\b", "geography": "Northern Province"},
            {"match": r"^Eastern\b", "geography": "Eastern Province"},
        ] + [
            # Table B.6 -- the same three measures by consumption quintile.
            {"match": r"^%s\s+(?=[\d.])" % q, "topic": "quintile",
             "characteristic": q}
            for q in _QUINTILES
        ],
    }],
}


parse = make_parser(LAYOUT)
