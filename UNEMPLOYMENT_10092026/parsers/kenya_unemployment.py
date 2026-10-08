"""Kenya — unemployment / labour-force layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `pdf_key_indicators.make_parser`; the comments beside
it record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

import copy
import os
import re  # noqa: F401  -- some layouts build their rows with it

import pandas as pd

from ._vocab import *  # noqa: F401,F403
from .pdf_key_indicators import make_parser

LAYOUTS: dict[str, dict] = {}

# =========================================================================
# KENYA -- KNBS, Quarterly Labour Force Report.
#
# A HISTORICAL BACKFILL, not a live series. KNBS ran the QLFS from 2019 Q1 to
# 2022 Q4 and then stopped; the whole run was bulk-uploaded into a single
# /2023/09/ folder, which is itself the evidence the series was archived rather
# than continued. The 2026 Kenya Integrated Labour Force Survey is in the field
# and will supersede it, but has published nothing yet.
#
# The Economic Survey's Chapter 3 workbook is NOT used: it is establishment /
# administrative employment (wage employment by industry), not an ILO household
# unemployment rate, and does not belong in this indicator.
#
# Table shape: Indicator | <year-ago quarter> | <previous quarter> |
# <current quarter>. Only the current quarter's column is captured.
#
# WORKING-AGE BASE IS 15-64 -- a closed upper bound, like Sierra Leone.
# Both ICLS rates are published and labelled LU1 (strict) and LU3 (broad).
#
# CROSS-CHECK (2022 Q4): population 15-64 29,066,237; labour force 19,398,165;
# employed 18,438,164; LFPR 66.7; EPR 63.4; LU1 4.9; LU3 13.9;
# long-term unemployment 3.2; NEET 19.0.
# =========================================================================
LAYOUTS["kenya"] = {
    "survey": "Quarterly Labour Force Report (QLFS)",
    "frequency": "quarterly",
    "working_age_base": "15-64",
    "decimal": ".",
    # THE PERIOD IS PINNED, NOT SCANNED. The table's header is split over two
    # lines --
    #     Quarter 4,  Quarter 3,  Quarter 4,
    #     Indicator      2021        2022        2022
    # -- so a pattern looking for a quarter near a year finds "Quarter 4" next
    # to 2021 and dated the whole release 2021-Q4. The values taken are the
    # THIRD column, which is Q4 2022. Pinning is safe here in a way it would
    # not be for a live series: the descriptor points at one archived file and
    # KNBS discontinued the QLFS after this issue.
    "period": "2022-Q4",
    "reference_period": "October - December 2022",
    "tables": [{
        "page_contains": ["unemployment rate"],
        # Every label is followed by LEADER DOTS out to the first column:
        #     Labour Force.......................... 18,716,433 19,113,051 19,398,165
        # so `^Labour Force\s*$` -- and four patterns like it -- matched
        # nothing, and this table shipped four of its nineteen rows. The
        # `\.{2,}` is also what stops "Labour Force" swallowing "Labour Force
        # Participation (%)".
        #
        # Three labels had been guessed rather than read. The report prints:
        #     "Employment/Population Ratio (%)"  not "Employment-to-Population Ratio"
        #     "Labour Force Participation (%)"   not "... Participation Rate"
        #     "Long-Term Unemployed (%)"         not "Long-Term Unemployment Rate"
        #
        # `take: trailing` picks the current quarter and, as a side effect,
        # absorbs digits inside a label ("(15-64)", "[LU1]", "Unemployed1"),
        # so no row needs `drop_leading`.
        "take": "trailing",
        "columns": [{"skip": True}, {"skip": True}, {}],
        "rows": [
            {"match": r"^Population \(15", "topic": "working_age_population",
             "label": "Population (15-64)"},
            {"match": r"^Labour Force\.{2,}", "topic": "labour_force",
             "definition": "strict", "label": "Labour Force"},
            {"match": r"^Extended Labour Force\.{2,}", "topic": "labour_force",
             "definition": "broad", "label": "Extended Labour Force"},
            {"match": r"^Employed\.{2,}", "topic": "employed", "label": "Employed"},
            {"match": r"^Employment/Population Ratio",
             "topic": "employment_to_population_ratio",
             "label": "Employment/Population Ratio (%)"},
            {"match": r"^Unemployed1", "topic": "unemployed",
             "definition": "strict", "label": "Unemployed (strict)"},
            {"match": r"^Unemployment Rate \[?LU1", "topic": "unemployment_rate",
             "definition": "strict", "label": "Unemployment Rate [LU1]"},
            {"match": r"^Unemployed2", "topic": "unemployed", "definition": "broad",
             "label": "Unemployed incl. potential labour force"},
            {"match": r"^Unemployment Rate \[?LU3",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Unemployment Rate [LU3]"},
            {"match": r"^Long-?Term Unemployed \(%\)",
             "topic": "long_term_unemployment_share",
             "label": "Long-Term Unemployed (%)"},
            {"match": r"^Long-?Term Unemployed\.{2,}", "topic": "unemployed",
             "label": "Long-Term Unemployed"},
            # Two inactivity lines are printed: the first includes the
            # potential labour force, the second (footnote 3) excludes it.
            # Only the first is taken -- the schema has a single
            # `outside_labour_force` topic and nowhere to hang the difference.
            {"match": r"^Not in Labor Force \(Inactive\)\.{2,}",
             "topic": "outside_labour_force",
             "label": "Not in Labour Force (Inactive)"},
            {"match": r"^Labour Force Participation \(%\)",
             "topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labour Force Participation (%)"},
            {"match": r"^Labour Under Utilization \(LU2\)",
             "topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Labour Underutilization (LU2)"},
            # The report's youth band is 15-34; this row previously said 15-24.
            {"match": r"^Youth \(15-34", "topic": "working_age_population",
             "age_group": "15-34", "label": "Youth (15-34)"},
            {"match": r"^Youth Not in Employment, Education or Training",
             "topic": "neet_rate", "age_group": "15-34", "measure": "count",
             "unit": "persons", "label": "Youth NEET (count)"},
            {"match": r"^NEET Rate", "topic": "neet_rate", "age_group": "15-34",
             "label": "NEET Rate"},
        ],
    }],
}


# =========================================================================
# THE AGE-COHORT TABLES -- where nine tenths of this report's data lives.
#
# Table 1 gives the national headline and nothing else. Tables 2 to 9b repeat
# every one of those series for TEN AGE COHORTS (15-19 ... 60-64) plus Total,
# and each does so for THREE QUARTERS side by side:
#
#     Age   | Q4 2021: LF, Pop, Rate | Q3 2022: LF, Pop, Rate | Q4 2022: ... | 2 change cols
#
# Capturing only Table 1 threw away the cohorts AND two whole quarters. The
# earlier quarters are not redundant: KNBS archived the QLFS after 2022 Q4 and
# this descriptor fetches that one file, so Q4 2021 and Q3 2022 exist in no
# other source the collector reads.
#
# COLUMNS CARRY THE PERIOD. `_emit` reads `period` off the cell, and a cell is
# the union of its row and column specs, so three column groups date themselves
# -- the same shape the module docstring describes for Rwanda's year columns.
#
# BLOCKS, BECAUSE TWO TABLES SHARE A PAGE. Tables 2 and 3 are both on page 7,
# 4 and 5 on page 9, 8 and 9a on page 12 -- with identical "15-19 ..." row
# labels in each. `seen` is keyed on (row spec, block), so one cohort row spec
# fires once per block and each table's caption opens its own block.
#
# EACH SERIES IS TAKEN FROM ONE TABLE ONLY. Total population repeats in six
# tables and labour force in five; re-emitting them would be the same figure
# under the same merge key from a different page. Population comes from Table
# 2, labour force from Table 2, extended labour force from Table 5.
#
# DEFERRED, AND WHY:
#   * Table 7 (long-term unemployment by cohort) prints "-" for a zero rate,
#     so those rows carry ten numbers where the layout expects eleven. The
#     engine skips a short row rather than shifting it, which is safe -- but it
#     would silently drop 50-54 and 60-64, so the whole table is left until it
#     can be read with a dash-aware column map. The national figure is already
#     captured from Table 1.
#   * Table 6's time-related underemployed COUNT and Tables 9a/9b's
#     "Prop." column have no topic in this vocabulary (there is no
#     underemployed-count or inactivity-rate topic). Dropped, not bent into a
#     neighbouring topic.
# =========================================================================

# Ten cohorts, printed the same way in every table. `drop_leading: 2` discards
# the two numbers inside the label itself ("15-19" reads as 15 and -19).
_COHORTS = [{"match": rf"^{lo}\s*-\s*{hi}\b", "age_group": f"{lo}-{hi}",
             "drop_leading": 2}
            for lo, hi in ((15, 19), (20, 24), (25, 29), (30, 34), (35, 39),
                           (40, 44), (45, 49), (50, 54), (55, 59), (60, 64))]
# The Total row is taken too: for Q4 2021 and Q3 2022 it is the only national
# figure in the file, and for Q4 2022 it restates Table 1 exactly -- same key,
# same value, so the merge collapses the pair rather than contradicting itself.
_AGE_ROWS = _COHORTS + [{"match": r"^Total\b"}]

_CHANGE = [{"skip": True}, {"skip": True}]   # the two derived "Change" columns


_MONTHS_OF_Q = {1: "January - March", 2: "April - June",
                3: "July - September", 4: "October - December"}


def _quarters_for(year: int, q: int) -> list[tuple[str, str]]:
    """The three column groups a report for `year`-Q`q` prints, in order.

    EVERY ISSUE SHOWS (year-ago, previous, current) -- verified against the
    printed headers of 2020 Q1 ("Quarter 1, 2019 | Quarter 4, 2019 | Quarter 1,
    2020"), 2020 Q4, 2021 Q1 and 2022 Q4. So the three periods follow from the
    report's own quarter and nothing has to be hardcoded per file.
    """
    prev_y, prev_q = (year, q - 1) if q > 1 else (year - 1, 4)
    return [(f"{year - 1}-Q{q}", f"{_MONTHS_OF_Q[q]} {year - 1}"),
            (f"{prev_y}-Q{prev_q}", f"{_MONTHS_OF_Q[prev_q]} {prev_y}"),
            (f"{year}-Q{q}", f"{_MONTHS_OF_Q[q]} {year}")]


def _by_quarter(*per_quarter: dict) -> list[dict]:
    """One column group per printed quarter, for the layout's own quarter.

    The module-level layout is built for 2022 Q4; `parse()` rewrites these
    periods per file when backfilling earlier issues.
    """
    out = []
    for period, reference in _quarters_for(2022, 4):
        for col in per_quarter:
            out.append({**col, "period": period, "reference_period": reference})
    return out + _CHANGE


_SKIP = {"skip": True}

LAYOUTS["kenya"]["tables"] += [
    # --- Table 2: labour force, population and participation, by cohort ----
    {
        "page_contains": ["labour participation rates by age cohorts"],
        "blocks": [{"id": "t2", "match": r"^Table 2: Labour Participation Rates"}],
        "rows": [{**r, "block": "t2"} for r in _AGE_ROWS],
        "columns": _by_quarter(
            {"topic": "labour_force", "definition": "strict",
             "label": "Labour Force", "measure": "count", "unit": "persons"},
            {"topic": "working_age_population", "label": "Population (15-64)",
             "measure": "count", "unit": "persons"},
            {"topic": "labour_force_participation_rate", "definition": "strict",
             "label": "Labour Force Participation (%)",
             "measure": "rate", "unit": "percent"},
        ),
    },
    # --- Table 3: employed and employment-to-population ratio --------------
    {
        "page_contains": ["employed and employment to population ratios"],
        "blocks": [{"id": "t3", "match": r"^Table 3: Employed and Employment"}],
        "rows": [{**r, "block": "t3"} for r in _AGE_ROWS],
        "columns": _by_quarter(
            {"topic": "employed", "label": "Employed",
             "measure": "count", "unit": "persons"},
            _SKIP,                                   # population -> Table 2
            {"topic": "employment_to_population_ratio",
             "label": "Employment/Population Ratio (%)",
             "measure": "rate", "unit": "percent"},
        ),
    },
    # --- Table 4: unemployment on the strict definition [LU1] -------------
    {
        "page_contains": ["unemployment (strict definition) by age cohorts"],
        "blocks": [{"id": "t4", "match": r"^Table 4: Unemployment \(strict"}],
        "rows": [{**r, "block": "t4"} for r in _AGE_ROWS],
        "columns": _by_quarter(
            {"topic": "unemployed", "definition": "strict",
             "label": "Unemployed (strict)", "measure": "count", "unit": "persons"},
            _SKIP,                                   # labour force -> Table 2
            {"topic": "unemployment_rate", "definition": "strict",
             "label": "Unemployment Rate [LU1]", "measure": "rate", "unit": "percent"},
        ),
    },
    # --- Table 5: unemployment plus the potential labour force [LU3] ------
    {
        # KNBS RENAMED THIS TABLE MID-SERIES. 2020 Q1 and Q2 print
        # "Unemployment (under relaxed definition) ... [LU3]"; from 2020 Q3 it
        # is "Combined rate of Unemployment and Potential Labour Force ...
        # [LU3]". Same indicator, two names -- so both the page token and the
        # block heading match on what does NOT change.
        "page_contains": ["by age cohorts [lu3]"],
        "blocks": [{"id": "t5", "match": r"^Table 5:.*\[LU3\]"}],
        "rows": [{**r, "block": "t5"} for r in _AGE_ROWS],
        "columns": _by_quarter(
            {"topic": "unemployed", "definition": "broad",
             "label": "Unemployed incl. potential labour force",
             "measure": "count", "unit": "persons"},
            {"topic": "labour_force", "definition": "broad",
             "label": "Extended Labour Force", "measure": "count", "unit": "persons"},
            {"topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Unemployment Rate [LU3]", "measure": "rate", "unit": "percent"},
        ),
    },
    # --- Table 6: LU2, the rate only --------------------------------------
    {
        # HYPHENATED IN EVERY ISSUE BUT THE LAST: 2020 Q1 - 2021 Q1 print
        # "Time Related Under-employment", 2022 Q4 "Time Related
        # Underemployment". The token stops before the hyphen.
        "page_contains": ["time related under"],
        "blocks": [{"id": "t6", "match": r"^Table 6: Unemployment and Time"}],
        "rows": [{**r, "block": "t6"} for r in _AGE_ROWS],
        "columns": _by_quarter(
            _SKIP,          # time-related underemployed count: no topic for it
            _SKIP,          # unemployed -> Table 4
            _SKIP,          # labour force -> Table 2
            # THE REPORT CONTRADICTS ITSELF ON LU2, AND BOTH FIGURES STAND.
            # Table 1 prints "Labour Under Utilization (LU2) ... 11.5 10.6
            # 18.6"; this table and the report's own prose give 11.5, 10.4 and
            # 9.0 ("LU2 ... increased to 9.0 per cent in the fourth quarter").
            # Table 1's companion count, 3,481,968, is exactly twice the
            # 1,740,984 its own footnote defines (time-related underemployed
            # 780,983 + unemployed 960,001), so the Q4 figure there looks
            # doubled -- but picking a winner would be correcting the NSO.
            # The two tables label it differently, so both are kept and stay
            # distinguishable: `series_label` is part of the merge key.
            {"topic": "labour_underutilisation_rate", "definition": "broad",
             "label": "Under - Utilization [LU2]",
             "measure": "rate", "unit": "percent"},
        ),
    },
    # --- Table 8: NEET, on the report's own 15-34 youth cohorts -----------
    {
        "page_contains": ["youth not in education, employment or training"],
        "blocks": [{"id": "t8", "match": r"^Table 8: Youth Not in Education"}],
        # Only four cohorts are published here, and the Total row IS the 15-34
        # youth aggregate Table 1 reports -- so it carries that age band.
        "rows": [{**r, "block": "t8"} for r in _COHORTS[:4]]
                + [{"match": r"^Total\b", "block": "t8", "age_group": "15-34"}],
        "columns": _by_quarter(
            {"topic": "neet_rate", "label": "Youth NEET (count)",
             "measure": "count", "unit": "persons"},
            _SKIP,                                   # population -> Table 2
            {"topic": "neet_rate", "label": "NEET Rate",
             "measure": "rate", "unit": "percent"},
        ),
    },
    # --- Tables 9a / 9b: persons outside the labour force ------------------
    # 9a counts the potential labour force in, 9b leaves it out. Same topic,
    # told apart by `series_label`, which is part of the merge key.
    {
        "page_contains": ["persons outside the labour force by age cohorts"],
        "blocks": [{"id": "t9a", "match": r"^Table 9a: Persons Outside"}],
        "rows": [{**r, "block": "t9a"} for r in _AGE_ROWS],
        "columns": _by_quarter(
            {"topic": "outside_labour_force",
             "label": "Not in Labour Force (incl. potential labour force)",
             "measure": "count", "unit": "persons"},
            _SKIP,                                   # population -> Table 2
            _SKIP,                                   # "Prop." has no topic
        ),
    },
    {
        "page_contains": ["persons outside the labour force1 by age cohorts"],
        "blocks": [{"id": "t9b", "match": r"^Table 9b: Persons Outside"}],
        "rows": [{**r, "block": "t9b"} for r in _AGE_ROWS],
        "columns": _by_quarter(
            {"topic": "outside_labour_force",
             "label": "Not in Labour Force (excl. potential labour force)",
             "measure": "count", "unit": "persons"},
            _SKIP,
            _SKIP,
        ),
    },
]

# THE LIST OF TABLES OPENS EVERY BLOCK, AND A BLOCK OUTLIVES ITS PAGE.
#
# Each of these specs selects its own page AND page 3, the List of Tables,
# whose dot-leader entry --
#
#     Table 3: Employed and Employment to Population Ratios ............... 4
#
# -- matches the block heading just as the real caption does. Block context is
# not reset between pages, so the block opened on page 3 was still open when
# page 7 was reached, and Table 3's spec swallowed Table 2's rows: employment
# came out as 19,398,165 (the labour force) and the employment ratio as 66.7
# (the participation rate). Every value was real and in the wrong series.
#
# Two independent guards, because one of them silently not applying is exactly
# how this got through the first time:
#   * skip the contents pages outright;
#   * require the caption NOT to be followed by dot leaders, so only the
#     printed table heading opens a block.
for _tbl in LAYOUTS["kenya"]["tables"]:
    if not _tbl.get("blocks"):
        continue                      # Table 1 matches on dot leaders by design
    _tbl.setdefault("page_excludes", ["list of tables", "table of contents"])
    for _b in _tbl["blocks"]:
        _b["match"] = _b["match"] + r"(?!.*\.{4})"

# Tables 2, 7, 9a and 9b letter-space their rate column ("1 6.2" for 16.2,
# "8 3.8" for 83.8). Set once for the document: the renderer that does it to
# one table does it throughout, and no Kenyan row label carries a bare single
# digit for the second pass to catch on.
LAYOUTS["kenya"]["despace_numbers"] = True

LAYOUT = LAYOUTS['kenya']

# ==========================================================================
# BACKFILL -- one parse per published quarter.
#
# KNBS ran the QLFS from 2019 Q1 to 2022 Q4 and archived the whole run into a
# single /2023/09/ folder. All sixteen files are still served, so the series
# can be read in full rather than from its last issue alone. Three facts shape
# how:
#
# 1. SIX OF THE SIXTEEN ARE SCANNED IMAGES. 2021 Q2-Q4 and 2022 Q1-Q3 contain
#    ZERO text characters and one image per page. They need OCR, which this
#    collector refuses, and they are listed in the descriptor as such rather
#    than silently skipped.
#
# 2. THE PERIOD MUST COME FROM THE FILENAME. In-document dating is not
#    reliable across the series: 2020-2021 issues carry no "for the period"
#    sentence at all, and 2019 Q4 prints "for the period September to December
#    2019" for what is plainly October-December -- KNBS's own typo, which
#    `parse_period` reads as 2019-Q3. A pattern that silently fails would leave
#    the layout's pinned period in place and date a whole file to 2022 Q4, so
#    `_quarter_from_name` RAISES rather than guessing.
#
# 3. THE 2019 ISSUES ARE A DIFFERENT REPORT. Four separate caption vintages
#    (Table 1 is even "Key Labor Market Indicators" in Q2), Table 5 means
#    long-term unemployment rather than LU3, and Table 1 carries one quarter
#    column, not three. They are deliberately NOT backfilled here: the yield is
#    the headline only, and the risk of reading a renumbered table is real.
#    2020 Q1 - 2021 Q1 share this layout's shape and are.
# ==========================================================================
_NAME_Q = re.compile(r"(20\d{2})[-_]?q(?:uarter[-_]?)?([1-4])", re.I)


def _quarter_from_name(path: str) -> tuple[int, int]:
    """(year, quarter) from the retained filename, or raise.

    Never falls back to the layout's pinned period: a file whose quarter
    cannot be read would otherwise be published under 2022 Q4's key.
    """
    m = _NAME_Q.search(os.path.basename(path))
    if not m:
        raise ValueError(
            f"cannot read the quarter from {os.path.basename(path)!r}. The "
            f"period is taken from the filename because this series cannot be "
            f"dated from its own text -- refusing to guess.")
    return int(m.group(1)), int(m.group(2))


def _layout_for(year: int, q: int) -> dict:
    """The Kenya layout with every period rewritten for one issue."""
    cfg = copy.deepcopy(LAYOUT)
    quarters = _quarters_for(year, q)
    cfg["period"], cfg["reference_period"] = quarters[-1]
    for tbl in cfg["tables"]:
        cols = tbl.get("columns") or []
        # The cohort tables carry three column groups in (year-ago, previous,
        # current) order; Table 1 carries none of its own.
        per_group = (len(cols) - len(_CHANGE)) // 3 if len(cols) > len(_CHANGE) else 0
        if per_group <= 0:
            continue
        for gi, (period, reference) in enumerate(quarters):
            for ci in range(per_group):
                col = cols[gi * per_group + ci]
                if col.get("skip"):
                    continue
                col["period"], col["reference_period"] = period, reference
    return cfg


_MERGE_KEY = ["topic", "definition", "series_label", "sex", "age_group",
              "education", "geography", "locality", "locality_label",
              "working_age_base", "period", "measure"]


def parse(path: str, extras: list[str] | None = None):
    """Parse the primary file and every retained back-issue beside it.

    The 2022 Q4 issue is read by the engine with this layout, exactly as
    before. The 2020 Q1 - 2021 Q1 issues are read CELL BY CELL by
    `kenya_qlfs_issues` (PyMuPDF), with the same layout re-dated per issue --
    see that module for why the engine cannot read them.

    ISSUES RESTATE EACH OTHER. Each prints (year-ago, previous, current), so a
    quarter appears in up to three issues; 728 of the 752 overlapping keys
    agree exactly. The rest are published revisions and the NEWEST ISSUE WINS
    (files are read oldest first and the last value is kept, as merge-on-write
    does across runs):
      * youth NEET for 2019 Q4 -- 13.3% (2,279,410) in the 2020 Q1 issue,
        17.8% (3,060,200) in the 2020 Q4 issue, for every cohort; both rows pass
        their own count/population = rate check, so this is a restatement, not
        a misread;
      * 2020 Q1 NEET and some outside-labour-force counts, revised by a few
        hundred persons in the 2021 Q1 issue;
      * WITHIN one issue, Table 1 and the cohort tables' Total row differ by
        one or two persons (labour force 19,130,994 vs 19,130,992 in 2020 Q4):
        the cohort table, read later, is kept.
    """
    from . import kenya_kihbs, kenya_qlfs_issues as issues

    every = [path] + list(extras or [])
    # The 2015/16 KIHBS labour report is a different survey with its own
    # reader; it is dated by its own text (2016), not by a quarter in its name.
    kihbs = [p for p in every if "kihbs" in os.path.basename(p).lower()]
    files = sorted([p for p in every if p not in kihbs], key=_quarter_from_name)
    frames = [kenya_kihbs.parse(p) for p in kihbs]
    for p in files:
        year, q = _quarter_from_name(p)
        cfg = _layout_for(year, q)
        if (year, q) == (2022, 4):
            frames.append(make_parser(cfg)(p))
        else:
            frames.append(pd.DataFrame(issues.read_issue(p, cfg)))
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates(subset=_MERGE_KEY, keep="last").reset_index(drop=True)
