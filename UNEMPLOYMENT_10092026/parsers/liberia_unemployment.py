"""Liberia — unemployment / labour-force layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `pdf_key_indicators.make_parser`; the comments beside
it record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

import re  # noqa: F401  -- some layouts build their rows with it

from ._vocab import *  # noqa: F401,F403
from .pdf_key_indicators import make_parser

LAYOUTS: dict[str, dict] = {}

# =========================================================================
# LIBERIA -- LISGIS, Labour Force Survey 2016-2017.
# "Main labour force and labour underutilization (LU) indicators (%),
#  LBR-LFS 2016-2017 - Main job" (pp. 16-17).
#
# The widest table in the collector: SEVENTEEN columns in seven blocks --
# Sex | Residence | Region | Functional Difficulty | Age | Subsistence Farming
# | Total. Note the printed order puts FUNCTIONAL DIFFICULTY BEFORE AGE, and
# carries a Subsistence-Farming block that is easy to miss entirely.
#
# The caption claims "(%)" but the table is MIXED: the first five rows are
# absolute persons and the rest are percentages.
#
# The ICLS-19 ladder is labelled LU1-LU4 here (Cameroon and Burkina use SU1-SU4
# for the same concepts).
#
# Every count row sums correctly across all seven column blocks to the Total
# column, and LU1 reproduces as Unemployed/Labour force in all 17 columns --
# so a parse can be checked arithmetically rather than by eye.
#
# CROSS-CHECK (Total column): population 15+ 2,355,060; labour force 615,549;
# employed 538,902; unemployed 76,647; LFPR 26.1; EPR 22.9; LU1 12.5;
# LU3 18.0; LU4 27.1; informal employment 86.7.
# =========================================================================
_LR_COLS = [
    {"sex": "male"}, {"sex": "female"},
    {"locality": "urban", "locality_label": "Urban"},
    {"locality": "rural", "locality_label": "Rural"},
    {"geography": "Greater Monrovia"}, {"geography": "North Central"},
    {"geography": "North Western"}, {"geography": "South Central"},
    {"geography": "South Eastern A"}, {"geography": "South Eastern B"},
    {"education": "With functional difficulty"},
    {"education": "Without functional difficulty"},
    {"age_group": "Youth (15-35)"}, {"age_group": "Adult (36+)"},
    {"education": "Participated in subsistence farming"},
    {"education": "Not participated in subsistence farming"},
    {},                                    # Total
]

LAYOUTS["liberia"] = {
    "survey": "Liberia Labour Force Survey 2016-2017",
    "frequency": "ad_hoc",
    "working_age_base": "15+",
    "decimal": ".",
    "period": "2017",
    "reference_period": "2016-2017",
    "tables": [{
        "page_contains": ["main labour force and labour underutilization"],
        "take": "trailing",
        "columns": _LR_COLS,
        "rows": [
            {"match": r"^Population 15 years and older",
             "topic": "working_age_population", "drop_leading": 1,
             "label": "Population 15 years and older"},
            {"match": r"^Labour force\b", "exclude": r"participation",
             "topic": "labour_force", "label": "Labour force"},
            {"match": r"^-?\s*Employed\b", "topic": "employed", "label": "Employed"},
            {"match": r"^-?\s*Unemployed\b", "topic": "unemployed",
             "label": "Unemployed"},
            {"match": r"^Outside the labour force",
             "topic": "outside_labour_force", "label": "Outside the labour force"},
            {"match": r"^Labour force participation rate",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labour force participation rate"},
            {"match": r"^Employment-to-population ratio",
             "topic": "employment_to_population_ratio",
             "label": "Employment-to-population ratio"},
            {"match": r"^Time related underemployment rate",
             "topic": "underemployment_rate",
             "label": "Time related underemployment rate"},
            {"match": r"^LU1: Unemployment rate", "topic": "unemployment_rate",
             "definition": "strict", "drop_leading": 1,
             "label": "LU1: Unemployment rate"},
            {"match": r"^LU3: Combined rate of unemployment and potential",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "drop_leading": 1,
             "label": "LU3: Combined rate of unemployment and potential labour force"},
            {"match": r"^LU4: Composite measure",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "drop_leading": 1,
             "label": "LU4: Composite measure of labour underutilization"},
            {"match": r"^Persons with informal employment",
             "topic": "informal_employment_share",
             "label": "Persons with informal employment"},
        ],
    }],
}


LAYOUT = LAYOUTS['liberia']
parse = make_parser(LAYOUT)


# =========================================================================
# THE COPY SERVED BY LISGIS'S REBUILT SITE (/uploads/surveys/lfs-2016-2017.pdf)
# renders Table 3.1 differently from the file the layout above was written
# for: row labels wrap across two to four lines around their numbers, and the
# LU rows sit on a continuation page with no caption. Line matching then fails
# in the worst way -- `informal_employment_share` matched the COUNT row
# (467,318) because the percentage row's label is split across three lines.
#
# So the table is read by POSITION instead. Every data row prints exactly
# seventeen numbers, and the rows come in a fixed printed order (below). The
# seventeen-number lines are taken in order and mapped to that sequence, and
# the mapping is then PROVED by the table's own arithmetic in every column:
#   labour force = employed + unemployed
#   population 15+ = labour force + outside the labour force
#   LU1 = unemployed / labour force        (to 0.15 points)
#   participation = labour force / population 15+   (to 0.15 points)
# A slipped row breaks those identities at once, so the read raises rather
# than publishing figures under the wrong indicator.
# =========================================================================
import pdfplumber as _pdfplumber
import pandas as _pd

from . import _common as _C

_SEQ = [  # printed order of the 17-number rows, pages 33 and 34
    "wap", "lf", "emp", "unemp", "olf", "inf_n", "form_n", "employees_n",
    "self_n", "lu_n", "lu_unemp", "tru_n", "plf_n", "lfpr", "epr", "tru",
    "inf_pct", "form_pct", "employees_pct", "self_pct",
    "lu1", "lu2", "lu3", "lu4",
]
_EMIT = {  # key -> (topic, definition, series label)
    "wap": ("working_age_population", "not_applicable", "Population 15 years and older"),
    "lf": ("labour_force", "not_applicable", "Labour force"),
    "emp": ("employed", "not_applicable", "Employed"),
    "unemp": ("unemployed", "not_applicable", "Unemployed"),
    "olf": ("outside_labour_force", "not_applicable", "Outside the labour force"),
    "lfpr": ("labour_force_participation_rate", "strict", "Labour force participation rate"),
    "epr": ("employment_to_population_ratio", "not_applicable", "Employment-to-population ratio"),
    "tru": ("underemployment_rate", "not_applicable", "Time related underemployment rate"),
    "inf_pct": ("informal_employment_share", "not_applicable", "Persons with informal employment"),
    "lu1": ("unemployment_rate", "strict", "LU1: Unemployment rate"),
    "lu2": ("labour_underutilisation_rate", "broad",
            "LU2: Combined rate of time-related underemployment and unemployment"),
    "lu3": ("labour_underutilisation_rate", "broad",
            "LU3: Combined rate of unemployment and potential labour force"),
    "lu4": ("labour_underutilisation_rate", "broad",
            "LU4: Composite measure of labour underutilization"),
}
_NUM17 = re.compile(r"((?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:\s+(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)){16})\s*[^\d]*$")


def _table_3_1_lines(path: str) -> list[list[float]]:
    with _pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    start = next(i for i, t in enumerate(pages)
                 # (the list of tables carries the same caption, with dot leaders)
                 if re.search(r"^Table 3\.1: Main labour force and labour "
                              r"underutilization(?![^\n]*\.{4})", t, re.M))
    rows = []
    for t in pages[start:start + 2]:
        for ln in t.splitlines():
            m = _NUM17.search(ln)
            if m:
                toks = m.group(1).split()
                if len(toks) == 17:
                    rows.append([float(x.replace(",", "")) for x in toks])
    return rows


def parse_positional(path: str) -> _pd.DataFrame:
    rows = _table_3_1_lines(path)
    if len(rows) != len(_SEQ):
        raise ValueError(f"Liberia Table 3.1: {len(rows)} seventeen-number rows, "
                         f"expected {len(_SEQ)}")
    v = dict(zip(_SEQ, rows))
    for c in range(17):
        if abs(v["lf"][c] - v["emp"][c] - v["unemp"][c]) > 2:
            raise ValueError(f"Table 3.1 col {c}: labour force != employed + unemployed")
        if abs(v["wap"][c] - v["lf"][c] - v["olf"][c]) > 2:
            raise ValueError(f"Table 3.1 col {c}: population != labour force + outside")
        if abs(100 * v["unemp"][c] / v["lf"][c] - v["lu1"][c]) > 0.15:
            raise ValueError(f"Table 3.1 col {c}: LU1 != unemployed / labour force")
        if abs(100 * v["lf"][c] / v["wap"][c] - v["lfpr"][c]) > 0.15:
            raise ValueError(f"Table 3.1 col {c}: participation != labour force / population")
    lay = LAYOUTS["liberia"]
    out = []
    for key, (topic, definition, label) in _EMIT.items():
        for col, val in zip(_LR_COLS, v[key]):
            out.append(_C.row(
                topic=topic, value=val, series_label=label,
                survey=lay["survey"], period=lay["period"],
                reference_period=lay["reference_period"],
                frequency=lay["frequency"], working_age_base=lay["working_age_base"],
                definition=definition, series_code="LBR-LFS T3.1",
                **{k: col[k] for k in ("sex", "geography", "education", "age_group",
                                       "locality", "locality_label") if k in col}))
    return _pd.DataFrame(out)


parse = parse_positional
