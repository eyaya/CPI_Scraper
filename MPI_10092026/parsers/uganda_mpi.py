"""Uganda — MPI table layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `mpi_tables.make_parser`; the comments beside it
record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

import re

from ._vocab import COLS_M0_H_A, _URBAN, _RURAL, _NATIONAL
from .mpi_tables import make_parser

# =========================================================================
# UGANDA -- UBOS, "National Population and Housing Census 2024 Monograph:
# Multidimensional Poverty Index Volume 5".
#
# NOTE THE HOST: the census monographs are on statistics.ubos.org, a DIFFERENT
# host from www.ubos.org where the 2022 edition lives.
#
# The 2022 (UNHS) and 2024 (census) editions are NOT comparable -- different
# dimension set (Employment/financial inclusion dropped, Basic Services added),
# 12 indicators against 13, survey against census. They are separate descriptors
# and must never be chained.
#
# COLUMN ORDER -- Table 2 leads with the INDEX, not the incidence:
#
#     Characteristics | Multidimensional | Headcount | Intensity  | Household
#                     | Poverty Index    | ratio (H) | (A)        | Population
#     National          0.270              53.1        50.9         44,138,557
#
# The layout previously declared `H | A | M0` here. Nothing about that is
# visibly wrong on the page -- all three are plausible numbers -- but it read
# the index as the incidence, the incidence as the intensity, and Uganda's
# 44.1 MILLION household population as M0. The schema caught only the last of
# the three, and only because an index above 1 is impossible; the H/A swap
# would have shipped. This is the exact failure `_vocab.py` warns about, so the
# order is spelled out above rather than named by a constant alone.
#
# The fourth column, the household population, is deliberately SKIPPED: it is a
# census count, not an MPI measure, and this schema has no home for it.
#
# ONE TABLE, FIVE STRATIFICATIONS. Table 2 disaggregates by sex of household
# head, residence, AGE of head, EDUCATION of head and sub-region, all under one
# header. The age and education blocks were previously dropped entirely.
#
# CROSS-CHECK (2024 census): National 0.270 / 53.1 / 50.9; Urban 0.193 / 39.1 /
# 49.3; Rural 0.315 / 61.1 / 51.5; Male-headed 0.262 / 51.9 / 50.5;
# Female-headed 0.289 / 55.9 / 51.8; Kampala 0.088 / 19.5 / 45.3;
# Karamoja 0.569 / 91.4 / 62.3; no formal education 0.435 / 78.3 / 55.5.
# =========================================================================

# The census's own 17 sub-regions, as printed. Bugisu/Sebei/Madi/Rwenzori were
# absent from the earlier list, which is why the run reported unmatched specs
# for names that are on the page (Elgon is the old name for Bugisu and does not
# appear in this edition at all).
_SUBREGIONS = [
    "Kampala", "Buganda", "Busoga", "Bukedi", "Bugisu", "Sebei", "Teso",
    "Karamoja", "Lango", "Acholi", "West Nile", "Madi", "Bunyoro", "Tooro",
    "Rwenzori", "Ankole", "Kigezi",
]

# Age of household head, as printed ('<10' first, '80+' last).
_AGE_BANDS = ["<10", "10-19", "20-29", "30-39", "40-49", "50-59", "60-69",
              "70-79", "80+"]

# Education of household head, as printed.
_EDUCATION = ["No formal education", "Some primary", "Completed primary",
              "Some secondary", "Completed secondary",
              "Post-secondary and above", "Not stated"]

LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Uganda MPI (census)",
    "survey": "National Population and Housing Census 2024",
    "k_cutoff": 40, "n_dimensions": 4, "n_indicators": 13,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "period": "2024", "reference_period": "Census 2024",
    "tables": [{
        # Anchored on the caption, not on the bare word 'mpi'. 'mpi' appears on
        # most of the 88 pages, and with `take: trailing` the layout was being
        # applied to Table A4 in the appendix.
        "page_contains": ["table 2: multidimensional poverty in uganda"],
        # THE AGE LABELS ARE THEMSELVES NUMBERS -- '<10', '10-19', '80+'. Read
        # naively, the whole line's numbers begin with the label's own digits,
        # so every age row's index came out as its age band (10-19 -> M0 10.0).
        # `leading_run` confines the read to the run of digits that FOLLOWS the
        # matched label, which also stops the national row's '**' footnote
        # marker from mattering.
        "leading_run": True,
        "columns": COLS_M0_H_A + [{"skip": True}],   # 4th col = population
        "rows": [
            {"match": r"^National\b", **_NATIONAL},
            {"match": r"^Urban\b", **_URBAN},
            {"match": r"^Rural\b", **_RURAL},
            # The report labels these 'Male'/'Female' under a 'Sex' sub-head;
            # they are the sex of the HOUSEHOLD HEAD, which the characteristic
            # says explicitly so the rows cannot be misread as a sex split of
            # the population.
            {"match": r"^Male\s+(?=[\d.])", "sex": "male",
             "topic": "sex_of_head", "characteristic": "Male-headed"},
            {"match": r"^Female\s+(?=[\d.])", "sex": "female",
             "topic": "sex_of_head", "characteristic": "Female-headed"},
        ] + [
            {"match": r"^%s\s+(?=[\d.])" % re.escape(b), "topic": "age",
             "characteristic": b, "age_group": b}
            for b in _AGE_BANDS
        ] + [
            {"match": r"^%s\s+(?=[\d.])" % re.escape(e),
             "topic": "education", "characteristic": e}
            for e in _EDUCATION
        ] + [
            {"match": r"^%s\s+(?=[\d.])" % re.escape(g), "geography": g}
            for g in _SUBREGIONS
        ],
    }],
}


parse = make_parser(LAYOUT)
