"""Sierra Leone (2023 edition) — MPI table layout and parser.

One module per country edition. The layout is declarative and read by
`mpi_tables.make_parser`; the comments record the report's actual column
order and the cross-check values used to prove the layout still holds.
"""
from __future__ import annotations

from .mpi_tables import make_parser

# =========================================================================
# SIERRA LEONE -- "Multidimensional Poverty in Sierra Leone 2023", the SECOND
# official National MPI (Foreword), on DHS 2019 data, "produced in
# collaboration with Statistics Sierra Leone, with technical guidance and
# support from UNDP and [OPHI]". The cover is UNDP-branded and the file name
# begins "undp_", BUT THE FILE IS ON STATS SL'S OWN DOMAIN
# (statistics.sl/images/StatisticsSL/Documents/), linked from its home page --
# which is what this collector requires. Until 2026-10-07 the update was known
# only from UNDP/OPHI copies and was recorded as not collectable.
#
# SAME MEASURE AS THE 2019 EDITION (sierra_leone_mpi.py): 5 dimensions,
# 14 indicators, k = 40%, household identification / person analysis -- so it
# carries the same measure_name, and its 2019 rows sit beside the 2019
# edition's 2017 rows as a second year of one series.
#
# EXCEPT CHAPTER 4. Its "comparable measure" re-estimates 2017 so that the two
# years can be compared, and those 2017 figures are NOT the 2019 edition's
# published 2017 figures (East M0 0.343 here). They are kept under their own
# measure_name, "... 2017 re-estimate on the comparable measure", so the two
# 2017 estimates never share a merge key. Table 9's 2019 columns are the
# headline Table 4 values and are not read twice.
#
# Rows print 10 numbers: population share (dropped) | M0, CI | H, CI | A, CI.
# Table 2 (national) is laid out beside body text in two columns, so its
# lines are interleaved with prose; the national row is read from Table 3's
# "National" line instead, which prints the same nine values cleanly.
#
# NOT READ: Table 8 (household size -- no topic), Figure 17 (sex of head, a
# chart), the robustness appendix.
#
# CROSS-CHECK: national 0.322 (0.309-0.335), H 58.0 (55.8-60.2), A 55.5;
# Rural H 79.8; Western region M0 0.104; Pujehun 0.500 / 83.6; Western Area
# Urban 0.059; 0-14 H 63.6; no-education head H 72.1; 2017 comparable
# Northern 0.420 / 72.0 / 58.3.
# =========================================================================

_GROUP = [
    {"skip": True},
    {"metric": "index_M0"}, {"metric": "index_M0_ci_low", "unit": "index"},
    {"metric": "index_M0_ci_high", "unit": "index"},
    {"metric": "incidence_H"}, {"metric": "incidence_H_ci_low"},
    {"metric": "incidence_H_ci_high"},
    {"metric": "intensity_A"}, {"metric": "intensity_A_ci_low"},
    {"metric": "intensity_A_ci_high"},
]

# Table 5 prefixes some district rows with their region ("Eastern Kenema",
# "Northern Port Loko"), so districts are matched anywhere on the line.
_DISTRICTS = [
    ("Western Area Urban", r"\bWestern Area Urban\b"),
    ("Western Area Rural", r"\bWestern Area Rural\b"),
    ("Kono", r"\bKono\b"), ("Kenema", r"\bKenema\b"),
    ("Kailahun", r"\bKailahun\b"), ("Bombali", r"\bBombali\b"),
    ("Kambia", r"\bKambia\b"), ("Koinadugu", r"\bKoinadugu\b"),
    ("Port Loko", r"\bPort Loko\b"), ("Tonkolili", r"\bTonkolili\b"),
    ("Falaba", r"\bFalaba\b"), ("Karene", r"\bKarene\b"),
    ("Bo", r"^(?:Southern\s+)?Bo\b"), ("Bonthe", r"\bBonthe\b"),
    ("Moyamba", r"\bMoyamba\b"), ("Pujehun", r"\bPujehun\b"),
]

LAYOUT = {
    "mpi_type": "national",
    "measure_name": "Sierra Leone MPI",
    "survey": "DHS 2019 (Demographic and Health Survey)",
    "k_cutoff": 40, "n_dimensions": 5, "n_indicators": 14,
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "period": "2019", "reference_period": "DHS 2019 (15 May-31 Aug 2019)",
    "tables": [
        {   # Table 3 -- rural / urban, and the national row
            "page_contains": ["table 3. incidence, intensity and mpi by rural"],
            "take": "trailing", "exact_numbers": True,
            "columns": _GROUP,
            "rows": [
                {"match": r"^Rural\b", "topic": "locality", "locality": "rural",
                 "locality_label": "Rural", "characteristic": "Rural"},
                {"match": r"^Urban\b", "topic": "locality", "locality": "urban",
                 "locality_label": "Urban", "characteristic": "Urban"},
                {"match": r"^National\b"},
            ],
        },
        {   # Table 4 -- the four regions
            "page_contains": ["table 4. incidence, intensity and mpi by region"],
            "take": "trailing", "exact_numbers": True,
            "columns": _GROUP,
            "rows": [{"match": rf"^{r}\b", "geography": f"{r} Region"}
                     for r in ("Eastern", "Northern", "Southern", "Western")],
        },
        {   # Table 5 -- the 16 districts (post-2017 boundaries: Falaba, Karene)
            "page_contains": ["table 5. incidence, intensity and mpi by district"],
            "take": "trailing", "exact_numbers": True,
            "columns": _GROUP,
            "rows": [{"match": pat, "geography": name}
                     for name, pat in _DISTRICTS],
        },
        {   # Table 6 -- age group of the person
            "page_contains": ["table 6. incidence, intensity and mpi by age"],
            "take": "trailing", "exact_numbers": True,
            "columns": _GROUP, "defaults": {"topic": "age"},
            # The label's own digits ("0-14" reads as 0 and -14; "65+" as 65)
            # are dropped before the ten values are counted.
            "rows": [{"match": rf"^{a}\s", "age_group": a, "characteristic": a,
                      "drop_leading": 2}
                     for a in ("0-14", "15-35", "36-64")]
                    + [{"match": r"^65\+", "age_group": "65+",
                        "characteristic": "65+", "drop_leading": 1}],
        },
        {   # Table 7 -- education of the household head (labels wrap)
            "page_contains": ["table 7. incidence, intensity and mpi by education"],
            "take": "trailing", "exact_numbers": True, "join_wrapped_labels": True,
            "columns": _GROUP, "defaults": {"topic": "education"},
            "rows": [{"match": rf"^{e}\b", "characteristic": e}
                     for e in ("No education", "Completed primary",
                               "Completed secondary", "Higher education")],
        },
        {   # Table 9 -- the 2017 RE-ESTIMATE on the comparable measure; columns
            # `M0 2017 | M0 2019 | H 2017 | H 2019 | A 2017 | A 2019`. Only the
            # 2017 columns are read (2019 = Table 4).
            "page_contains": ["table 9. incidence, intensity and mpi across regions"],
            # Table 9 shares its lines with body text ("Figure 27 shows ...
            # Southern 0.426 ..."), so the six values are the TRAILING six and
            # the count is not required to be exact.
            "take": "trailing",
            "defaults": {"period": "2017",
                         "reference_period": "MICS 2017, comparable 2017-2019 measure",
                         "survey": "MICS 2017 (re-estimated on the 2017-2019 comparable measure)",
                         "measure_name": "Sierra Leone MPI, 2017 re-estimate on the comparable measure"},
            "columns": [{"metric": "index_M0"}, {"skip": True},
                        {"metric": "incidence_H"}, {"skip": True},
                        {"metric": "intensity_A"}, {"skip": True}],
            "rows": [{"match": rf"\b{r} 0\.\d", "geography": f"{r} Region"}
                     for r in ("Eastern", "Northern", "Southern", "Western")],
        },
    ],
}


_engine = make_parser(LAYOUT)


def parse(path: str):
    """The engine's output, less ONE published cell the schema cannot hold.

    Table 7 prints the "Higher education" incidence interval as -0.3 to 4.1 --
    a normal-approximation bound below zero, around an estimate of 1.9%. A
    negative percentage fails the schema's range check, and clipping it to 0
    would publish a number the report does not print, so that bound alone is
    dropped. Any OTHER out-of-range bound still reaches the validator and fails
    the run, which is the point: this is a named exception, not a filter.
    """
    df = _engine(path)
    neg = (df["metric"] == "incidence_H_ci_low") & (df["value"] < 0)
    expected = neg & (df["characteristic"] == "Higher education")
    if (neg & ~expected).any() or int(expected.sum()) != 1:
        raise ValueError("Sierra Leone 2023: negative incidence bounds changed: "
                         f"{df[neg][['characteristic', 'value']].values.tolist()}")
    return df[~expected].reset_index(drop=True)
