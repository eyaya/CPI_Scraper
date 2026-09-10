"""Canonical tidy output schema + validation for Population data.

Parallel to `indicators/gdp/schema.py` and the CPI schema. Population is its own
shape again — it is the *denominator* for every per-capita statistic in the
Commons, so it is classified by the demographic cross-tabs analysts actually
filter on (sex x age-group x geography), not by COICOP division or SNA approach:

* mid-year population **estimates** and forward **projections**, plus census /
  intercensal counts, kept distinct via `series_type`;
* broken down by `sex` (male/female/total), `age_group` (as the NSO bands it —
  "0-4", "80+", "15-64", "Total", or a single year), and `geography` (national
  plus sub-national units — provinces/regions — which international databases
  rarely carry);
* period is a mid-year `YYYY` (annual);
* mostly head **counts** (persons), but the same table often carries derived
  demographic measures (growth rate, sex ratio, density, median age, dependency
  ratio, life expectancy, total fertility) — captured as published via `measure`
  + `unit`, never recomputed.

Every population parser, whatever the country or source tier, emits a DataFrame
with exactly these columns so all 54 NSOs' population concatenates into one file.
Each NSO's own age bands and geography labels are kept as published (like the CPI
side keeps the source's own `coicop_label`); cross-country harmonisation of age
bands / sub-national codes is a later step.
"""
from __future__ import annotations
import re
import pandas as pd

from core.schema_base import ValidationError

# Canonical column order for every Population tidy output file.
POPULATION_COLUMNS = [
    "country",              # e.g. South_Africa
    "iso3",                 # e.g. ZAF
    "indicator",            # always "Population"
    "series_type",          # estimate | projection | census | intercensal
    "sex",                  # male | female | total
    "age_group",            # NSO's own band: "0-4" | "80+" | "15-64" | "Total" | "0"
    "geography",            # "Total country" (national) or a sub-national unit
    "period",               # YYYY (mid-year, annual)
    "frequency",            # annual
    "measure",              # what `value` is: count | growth_rate | share | ...
    "value",                # numeric value of the measure
    "unit",                 # persons | percent | per_km2 | years | ratio | births_per_woman
    "series_code",          # the NSO's own table/series code if any (provenance)
    "source_type",          # api | excel | csv | pdf | doc
    "source_url",           # where the data was fetched from
    "source_file",          # the raw file it was parsed from
    "extracted_at",         # ISO timestamp of the collection run
]

POP_MEASURES = {
    "count",            # a head count (persons) — the core denominator series
    "growth_rate",      # annual population growth (percent)
    "share",            # share of a total (percent) — e.g. % urban, % of national
    "density",          # persons per km^2
    "sex_ratio",        # males per 100 females (ratio)
    "median_age",       # years
    "dependency_ratio", # ratio (percent)
    "life_expectancy",  # years (at birth unless the NSO says otherwise)
    "fertility_rate",   # total fertility (births per woman)
}
SERIES_TYPES = {"estimate", "projection", "census", "intercensal"}
SEXES = {"male", "female", "total"}

_YEAR_RE = re.compile(r"^\d{4}$")


def _bad_periods(period: pd.Series) -> list[str]:
    s = period.astype(str)
    ok = s.str.match(_YEAR_RE)
    return sorted(s[~ok].unique())[:5]


def validate_population(df: pd.DataFrame) -> pd.DataFrame:
    """Fail loudly on garbage before it reaches the output file. Returns the
    column-ordered frame if it passes."""
    missing = [c for c in POPULATION_COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(f"missing columns: {missing}")
    if df.empty:
        raise ValidationError("no rows produced")

    bad = _bad_periods(df["period"])
    if bad:
        raise ValidationError(f"malformed period(s): {bad}")

    for col, allowed in (
        ("measure", POP_MEASURES), ("series_type", SERIES_TYPES), ("sex", SEXES),
    ):
        extra = set(df[col].dropna().unique()) - allowed
        if extra:
            raise ValidationError(f"unknown {col} value(s): {extra}")

    vals = pd.to_numeric(df["value"], errors="coerce")
    if vals.isna().any():
        raise ValidationError(f"{int(vals.isna().sum())} non-numeric value(s)")

    # A head count is a non-negative number of persons. Bound the magnitude to
    # catch a parse that grabbed the wrong cell (a year, a concatenation): the
    # largest single population cell is a national total (Nigeria ~2.3e8), so a
    # loose 5e9 ceiling (below the world total) still flags a mis-parse while
    # clearing every real figure — whether the NSO reports in persons or '000.
    counts = vals[df["measure"].astype(str) == "count"]
    if len(counts):
        if (counts < 0).any():
            raise ValidationError(f"{int((counts < 0).sum())} negative count(s)")
        if not counts.lt(5e9).all():
            raise ValidationError(f"count value(s) out of plausible range: "
                                  f"max={float(counts.max()):.3g}")

    # Rates/ratios/ages: a person's population growth or a median age landing in
    # the thousands means a count was mis-tagged as a rate. Life expectancy and
    # median age are years (<130); growth/share are percents that can be negative
    # (a shrinking population, an emigration province) but not wild.
    other = vals[df["measure"].astype(str) != "count"]
    if len(other) and not other.abs().lt(1e5).all():
        raise ValidationError(f"non-count value(s) implausible: "
                              f"max|.|={float(other.abs().max()):.3g}")

    return df[POPULATION_COLUMNS].copy()
