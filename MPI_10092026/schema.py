"""Canonical tidy schema + validation for MULTIDIMENSIONAL POVERTY (MPI).

SDG 1.2. MPI is index-shaped, not a head count: each row is a poverty *metric* —
the incidence (H, % of people multidimensionally poor), the intensity (A, the
average share of weighted deprivations among the poor), the adjusted headcount
M0 = H x A, a censored headcount ratio for one deprivation indicator, or an
indicator's percentage contribution to overall poverty — for a geography,
optionally cut by a characteristic. Emitted exactly as the NSO publishes it;
nothing is recomputed.

--- THE ONE THING THAT MATTERS MOST HERE ---------------------------------

`mpi_type` separates two measures that share a name and are not the same thing:

* **national** — designed by the NSO (usually with OPHI/UNDP technical support)
  using country-chosen dimensions, indicators, weights and deprivation cutoffs.
  **National MPIs are NOT comparable across countries.** Reading across them is
  a category error, and this collector exists partly to make that hard to do by
  accident.
* **global** — the OPHI/UNDP standard: 3 dimensions, 10 indicators, k = 33.3%,
  comparable across countries but computed by OPHI, not by the NSO. It is only
  ever collected here when an NSO republishes its own country's figure inside
  its own publication, and it stays tagged so it can never be pooled with the
  national series.

How different are national designs in practice? Across the African NSOs
collected here: dimensions range 3 to 7, indicators 8 to 21, and the deprivation
cutoff k runs from 25% (Seychelles) to 60% (Mali). Egypt uses seven dimensions
including Social Protection and Food Security; Nigeria has "Work and Shocks";
Seychelles counts Crime, Obesity and Substance abuse. Every one of those is a
legitimate national measure and none of them is the global MPI.

So `k_cutoff`, `n_dimensions` and `n_indicators` are first-class columns, not
metadata: a rate is meaningless without the rule that produced it.

--- TWO OTHER TRAPS THIS SCHEMA GUARDS -----------------------------------

**M0 scale.** Most NSOs print M0 as a decimal in [0, 1] (Mauritius 0.041,
Madagascar 0.386). Morocco prints it as a PERCENTAGE (IPM = 2,5%). The `unit`
column carries which, and `validate_mpi` range-checks each accordingly, so a
percentage M0 can never be silently read as a decimal one.

**Unit of analysis.** South Africa's SAMPI and Djibouti's IPM report the
HOUSEHOLD as poor; Uganda, Egypt, Somalia and most others report the PERSON.
`unit_of_analysis` records it, because an H over households is not the same
quantity as an H over people, even within one country's own time series.
"""
from __future__ import annotations
import re
import pandas as pd

from core.schema_base import ValidationError

MPI_COLUMNS = [
    "country", "iso3", "indicator",   # indicator = "MPI"
    "mpi_type",          # national | global  -- see the module docstring
    "survey",            # the NSO's own source survey, e.g. "EICV7", "RGPH 2024"
    "measure_name",      # the index's own published name ("SAMPI", "IPM-A", ...)
    "metric",            # incidence_H | intensity_A | index_M0 | ...
    "dimension",         # the MPI dimension as published, or "Total"
    "mpi_indicator",     # the deprivation indicator as published, or "Total"
    "topic",             # the cut being made: total | locality | sex_of_head | ...
    "characteristic",    # the cut's value as published, or "Total"
    "sex",               # male | female | total   (of the household head)
    "age_group",         # the NSO's own band, or "Total"
    "geography",         # "Total country", or a region/province/district
    "locality",          # all | urban | rural | other
    "locality_label",    # the stratum exactly as published ("Nomadic", "Bamako")
    "k_cutoff",          # the deprivation cutoff, in percent (25, 33.3, 60, ...)
    "n_dimensions",      # how many dimensions this measure uses
    "n_indicators",      # how many indicators this measure uses
    "unit_of_analysis",  # person | household
    "period",            # YYYY
    "reference_period",  # as published, e.g. "2015/16", "Census 2011"
    "frequency",         # annual | ad_hoc
    "value",
    "unit",              # percent | index | persons
    "series_code",
    "source_type", "source_url", "source_file", "extracted_at",
]

MPI_TYPES = {"national", "global"}

# The metric vocabulary. Deliberately small and Alkire-Foster-shaped: anything a
# country reports that does not fit is left out rather than bent to fit.
METRICS = {
    "incidence_H",            # % of the population identified as MPI-poor
    "intensity_A",            # average deprivation share among the poor, %
    "index_M0",               # the MPI itself, H x A
    "censored_headcount",     # % deprived in an indicator AND MPI-poor
    "uncensored_headcount",   # % deprived in an indicator, poor or not
    "contribution",           # an indicator's or dimension's % share of M0
    "vulnerable",             # % near-poor (below k but within a band of it)
    "severe_poverty",         # % poor at a higher, "severe" cutoff
    "population_poor",        # a count of poor people, when published
    # A CONFIDENCE BOUND NAMES WHAT IT BOUNDS. The vocabulary used to carry a
    # bare `confidence_low`/`confidence_high` pair, which cannot say whether a
    # bound belongs to H, to A or to M0. Every identifying column was then
    # identical across the three bounds a table publishes for one stratum, so
    # `merge_keys` saw them as one row and the second run of a country with
    # confidence intervals collapsed nine Seychelles rows to five -- silently,
    # and leaving the survivors unattributable. The subject is in the name.
    "incidence_H_ci_low", "incidence_H_ci_high",
    "intensity_A_ci_low", "intensity_A_ci_high",
    "index_M0_ci_low", "index_M0_ci_high",
}

# Which disaggregation a row belongs to. `total` is the undisaggregated series,
# including the sub-national rows -- for those the cut is carried by
# `geography`, not by `topic`, so that a region's headline MPI and the national
# headline MPI sit in the same topic and can be compared without a filter that
# knows every region's name.
TOPICS = {
    "total",         # national or regional headline, no further cut
    "locality",      # urban / rural / named stratum
    "sex_of_head",   # sex of the household head
    "contributor",   # per-indicator contribution to M0
    "dimension",     # per-dimension breakdown
    "age",           # age of the household head or of the person
    "education",     # education of the household head
    "quintile",      # consumption/wealth quintile (Rwanda EICV7 Table B.6)
    "disability",    # household includes a person living with a disability
}

UNITS = {"percent", "index", "persons"}
SEXES = {"male", "female", "total"}
LOCALITIES = {"all", "urban", "rural", "other"}
FREQUENCIES = {"annual", "ad_hoc"}
UNITS_OF_ANALYSIS = {"person", "household"}

# Metrics whose value is a share of a population, so bounded to [0, 100].
_PERCENT_METRICS = {"incidence_H", "intensity_A", "censored_headcount",
                    "uncensored_headcount", "contribution", "vulnerable",
                    "severe_poverty",
                    # Naming the subject of each bound buys the bounds the same
                    # range check as the estimate they bracket. A bare
                    # `confidence_low` could not be checked at all.
                    "incidence_H_ci_low", "incidence_H_ci_high",
                    "intensity_A_ci_low", "intensity_A_ci_high"}

_YEAR_RE = re.compile(r"^\d{4}$")
_TEXT_COLS = ("survey", "measure_name", "dimension", "mpi_indicator", "topic",
              "characteristic", "age_group", "geography", "locality_label",
              "reference_period")


def validate_mpi(df: pd.DataFrame, descriptor: dict | None = None) -> pd.DataFrame:
    """Fail loudly on garbage before it can reach a CSV.

    `descriptor` is the source YAML; `expect_metrics` in it (if set) asserts a
    minimum number of distinct metrics -- the early warning that a parser
    silently captured only part of a table.
    """
    missing = [c for c in MPI_COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(f"missing columns: {missing}")
    if df.empty:
        raise ValidationError("no rows produced")

    s = df["period"].astype(str)
    bad = sorted(s[~s.str.match(_YEAR_RE)].unique())[:5]
    if bad:
        raise ValidationError(f"malformed period(s): {bad}")

    for col, allowed in (
        ("mpi_type", MPI_TYPES), ("metric", METRICS), ("unit", UNITS),
        ("sex", SEXES), ("locality", LOCALITIES), ("frequency", FREQUENCIES),
        ("unit_of_analysis", UNITS_OF_ANALYSIS), ("topic", TOPICS),
    ):
        extra = set(df[col].dropna().astype(str).unique()) - allowed
        if extra:
            raise ValidationError(f"unknown {col} value(s): {sorted(extra)}")

    for col in _TEXT_COLS:
        v = df[col]
        if v.isna().any() or (v.astype(str).str.strip() == "").any():
            raise ValidationError(f"empty {col} value(s)")

    # A national MPI without its cutoff and shape is not interpretable, and
    # pooling one that lacks them is exactly the error this schema exists to
    # prevent -- so they are required, not optional.
    for col in ("k_cutoff", "n_dimensions", "n_indicators"):
        nums = pd.to_numeric(df[col], errors="coerce")
        if nums.isna().any():
            raise ValidationError(
                f"{col} is missing or non-numeric on {int(nums.isna().sum())} "
                f"row(s); a national MPI cannot be interpreted without it")
    k = pd.to_numeric(df["k_cutoff"], errors="coerce")
    if not k.between(1, 100).all():
        raise ValidationError(
            f"k_cutoff outside 1..100 percent: {sorted(k.unique())[:5]} -- "
            f"give it as a percentage (33.3), not a fraction (0.333)")
    nd = pd.to_numeric(df["n_dimensions"], errors="coerce")
    ni = pd.to_numeric(df["n_indicators"], errors="coerce")
    if not nd.between(1, 20).all() or not ni.between(1, 60).all():
        raise ValidationError("implausible n_dimensions / n_indicators")
    if (ni < nd).any():
        raise ValidationError("n_indicators is below n_dimensions")

    vals = pd.to_numeric(df["value"], errors="coerce")
    if vals.isna().any():
        raise ValidationError(f"{int(vals.isna().sum())} non-numeric value(s)")

    m, u = df["metric"].astype(str), df["unit"].astype(str)

    pct = vals[m.isin(_PERCENT_METRICS)]
    if len(pct) and not pct.between(0, 100).all():
        raise ValidationError(
            f"percent metric(s) outside 0..100: min={float(pct.min())}, "
            f"max={float(pct.max())}")

    # M0 is bounded by construction: it is H x A, both shares. As a decimal it
    # cannot exceed 1; where an NSO prints it as a percentage the unit says so
    # and the bound is 100. Checking against the WRONG bound is precisely how a
    # Morocco-style percentage M0 would slip through as a decimal one.
    is_m0 = m.isin(["index_M0", "index_M0_ci_low", "index_M0_ci_high"])
    if is_m0.any() and not u[is_m0].isin(["index", "percent"]).all():
        raise ValidationError("index_M0 rows must carry unit 'index' or 'percent'")
    m0_index = vals[is_m0 & (u == "index")]
    m0_pct = vals[is_m0 & (u == "percent")]
    if len(m0_index) and not m0_index.between(0, 1).all():
        raise ValidationError(
            f"index_M0 with unit 'index' outside 0..1: max="
            f"{float(m0_index.max())}. If the NSO prints M0 as a percentage "
            f"(Morocco does), set unit 'percent' rather than rescaling it.")
    if len(m0_pct) and not m0_pct.between(0, 100).all():
        raise ValidationError("index_M0 with unit 'percent' outside 0..100")

    counts = vals[m == "population_poor"]
    if len(counts) and not (counts.ge(0) & counts.lt(5e9)).all():
        raise ValidationError("population_poor out of range")

    # An indicator-level metric must actually name what it is about, or the row
    # is unusable: "something contributes 13.6%" says nothing.
    per_ind = df[m.isin(["censored_headcount", "uncensored_headcount",
                         "contribution"])]
    if len(per_ind):
        no_ind = per_ind["mpi_indicator"].astype(str).str.strip().str.lower() == "total"
        no_dim = per_ind["dimension"].astype(str).str.strip().str.lower() == "total"
        if (no_ind & no_dim).any():
            raise ValidationError(
                f"{int((no_ind & no_dim).sum())} indicator-level metric row(s) "
                f"name neither `mpi_indicator` nor `dimension`")

    # A global MPI has a fixed shape. If a row claims to be one, hold it to
    # that -- the guard against a national measure being mislabelled global
    # merely because it happens to use three dimensions.
    g = df[df["mpi_type"].astype(str) == "global"]
    if len(g):
        if not pd.to_numeric(g["n_indicators"]).eq(10).all() or \
           not pd.to_numeric(g["n_dimensions"]).eq(3).all():
            raise ValidationError(
                "rows tagged mpi_type 'global' must have 3 dimensions and 10 "
                "indicators (the OPHI/UNDP specification). A country-designed "
                "index that merely resembles it is still 'national'.")

    if descriptor:
        need = descriptor.get("expect_metrics")
        if need and df["metric"].nunique() < need:
            raise ValidationError(
                f"{df['metric'].nunique()} distinct metrics, expected >= {need}")

    return df[MPI_COLUMNS].copy()
