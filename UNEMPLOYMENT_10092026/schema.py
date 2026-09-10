"""Canonical tidy schema + validation for LABOUR FORCE / UNEMPLOYMENT statistics.

Sibling of `indicators/cpi/schema.py` (prices), `indicators/gdp/schema.py`
(national accounts) and `indicators/labour/schema.py` (census economic-activity
cross-tabs). Unemployment gets its own schema rather than reusing `labour`'s
because the two are different animals:

* `labour/` is a CENSUS cross-tab — a count of persons by characteristic,
  one reference year, no rates beyond the headline unemployment rate.
* `unemployment/` is the LABOUR FORCE SURVEY headline family — a small, fixed
  vocabulary of published INDICATORS (unemployment rate, participation rate,
  employment-to-population ratio, the level counts behind them, plus the
  underutilisation ladder) measured repeatedly over time, usually quarterly.

Three things bite hard in this domain and each gets a first-class column,
because collapsing them silently produces a nonsense cross-country series:

1. `definition` — an unemployment rate is meaningless without saying WHICH one.
   Senegal publishes BIT-strict 5.4% and élargi 23.3% for the SAME quarter;
   South Africa publishes official 33.6% and expanded (LU3) 43.8%; Cameroon,
   Zimbabwe, Botswana and Namibia all publish a strict and a broad measure.
2. `working_age_base` — the denominator's lower bound is NOT 15+ everywhere.
   Rwanda and Zimbabwe and Mauritius use 16+, Ethiopia uses 10+, Uganda runs a
   14–64 national definition alongside ILO 15+. A rate computed on a different
   base is not comparable and must carry its base.
3. `locality` / `locality_label` — "urban/rural" is not always binary. Burkina
   reports Ouagadougou / Bobo-Dioulasso / autres urbains / rural; Benin reports
   Cotonou / autres urbains / rural. `locality` is the coarse controlled value
   for joining; `locality_label` keeps the NSO's own stratum name.

Everything is emitted exactly as the NSO publishes it. Nothing is derived,
rebased, re-estimated or harmonised — including the NSO's own "Total" rows.
"""
from __future__ import annotations
import re
import pandas as pd

from core.schema_base import ValidationError

UNEMPLOYMENT_COLUMNS = [
    "country",            # e.g. South_Africa
    "iso3",               # e.g. ZAF
    "indicator",          # always "Unemployment"
    "survey",             # the NSO's own survey/publication name, e.g. "QLFS", "ENES"
    "topic",              # controlled indicator id -- see TOPICS below
    "definition",         # strict | broad | not_applicable  (see DEFINITIONS)
    "series_label",       # the row label exactly as published by the NSO
    "sex",                # male | female | total
    "age_group",          # the NSO's own band ("15-24", "Youth 15-35"), or "Total"
    "education",          # the NSO's own level, or "Total"
    "geography",          # "Total country", or a region/province/district name
    "locality",           # all | urban | rural | other   (coarse, for joining)
    "locality_label",     # the stratum exactly as published ("Ouagadougou", "Rural")
    "working_age_base",   # "15+", "16+", "10+", "14-64", ... as the NSO defines it
    "period",             # YYYY | YYYY-Qn | YYYY-Hn
    "reference_period",   # as published, e.g. "Apr-Jun 2026", "Jan-Mar 2024", "2016-17"
    "frequency",          # quarterly | semiannual | annual | ad_hoc
    "measure",            # rate | count | share
    "value",              # numeric
    "unit",               # percent | persons | thousand_persons
    "series_code",        # the NSO's own table/series id where one exists
    "source_type",        # api | excel | csv | pdf | html
    "source_url",
    "source_file",
    "extracted_at",
]

# The controlled indicator vocabulary. Deliberately small: these are the
# headline series essentially every LFS in Africa publishes. Anything a country
# reports that does not fit is either dropped (never invented) or added here
# explicitly with a comment -- never squeezed into a neighbouring topic.
TOPICS = {
    # --- rates -----------------------------------------------------------
    "unemployment_rate",             # unemployed / labour force
    "labour_force_participation_rate",
    "employment_to_population_ratio",  # a.k.a. absorption rate (ZA), taux d'occupation
    "youth_unemployment_rate",       # age_group carries the country's youth band
    "neet_rate",                     # not in employment, education or training
    "underemployment_rate",          # time-related underemployment
    "labour_underutilisation_rate",  # LU2/LU3/LU4, CRUPLF, sous-utilisation
    "informal_employment_share",
    "long_term_unemployment_share",
    # --- counts ----------------------------------------------------------
    "working_age_population",
    "labour_force",
    "employed",
    "unemployed",
    "outside_labour_force",          # a.k.a. not economically active
    "potential_labour_force",        # incl. discouraged job-seekers
}

# `definition` disambiguates rates that a country publishes in more than one
# flavour. "strict" = ILO/BIT standard (actively searched AND available);
# "broad" = the relaxed / expanded / élargi / LU3 / CRUPLF variant that counts
# discouraged job-seekers. Counts and unambiguous rates use "not_applicable".
DEFINITIONS = {"strict", "broad", "not_applicable"}

MEASURES = {"rate", "count", "share"}
UNITS = {"percent", "persons", "thousand_persons"}
SEXES = {"male", "female", "total"}
LOCALITIES = {"all", "urban", "rural", "other"}
FREQUENCIES = {"quarterly", "semiannual", "annual", "ad_hoc"}

_ANNUAL_RE = re.compile(r"^\d{4}$")
_QUARTER_RE = re.compile(r"^\d{4}-Q[1-4]$")
_HALF_RE = re.compile(r"^\d{4}-H[12]$")

_TEXT_COLS = ("survey", "series_label", "age_group", "education", "geography",
              "locality_label", "working_age_base", "reference_period")


def _bad_periods(period: pd.Series) -> list[str]:
    s = period.astype(str)
    ok = s.str.match(_ANNUAL_RE) | s.str.match(_QUARTER_RE) | s.str.match(_HALF_RE)
    return sorted(s[~ok].unique())[:5]


def validate_unemployment(df: pd.DataFrame, descriptor: dict | None = None) -> pd.DataFrame:
    """Fail loudly on garbage before it can reach a CSV.

    `descriptor` is the source YAML; `expect_topics` in it (if set) asserts a
    minimum number of distinct topics in the latest period -- the early-warning
    that a parser silently lost half a table, exactly like CPI's
    `expect_divisions`.
    """
    missing = [c for c in UNEMPLOYMENT_COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(f"missing columns: {missing}")
    if df.empty:
        raise ValidationError("no rows produced")

    bad = _bad_periods(df["period"])
    if bad:
        raise ValidationError(f"malformed period(s): {bad}")

    for col, allowed in (
        ("topic", TOPICS), ("definition", DEFINITIONS), ("measure", MEASURES),
        ("unit", UNITS), ("sex", SEXES), ("locality", LOCALITIES),
        ("frequency", FREQUENCIES),
    ):
        extra = set(df[col].dropna().astype(str).unique()) - allowed
        if extra:
            raise ValidationError(f"unknown {col} value(s): {sorted(extra)}")

    for col in _TEXT_COLS:
        s = df[col]
        if s.isna().any() or (s.astype(str).str.strip() == "").any():
            raise ValidationError(f"empty {col} value(s)")

    # measure/unit must agree: a rate is a percent, a count is people.
    m, u = df["measure"].astype(str), df["unit"].astype(str)
    if ((m == "count") & (u == "percent")).any():
        raise ValidationError("count row(s) carrying unit 'percent'")
    if (m.isin(["rate", "share"]) & (u != "percent")).any():
        raise ValidationError("rate/share row(s) not carrying unit 'percent'")

    vals = pd.to_numeric(df["value"], errors="coerce")
    if vals.isna().any():
        raise ValidationError(f"{int(vals.isna().sum())} non-numeric value(s)")

    # Rates are percentages of a population: [0, 100]. A parser that grabbed the
    # wrong cell (a year, a count, a weight) lands outside this immediately.
    rates = vals[m.isin(["rate", "share"])]
    if len(rates) and not rates.between(0, 100).all():
        raise ValidationError(
            f"rate/share out of [0,100]: min={float(rates.min())}, "
            f"max={float(rates.max())}"
        )

    counts = vals[m == "count"]
    if len(counts):
        if (counts < 0).any():
            raise ValidationError("negative count(s)")
        # Loose upper bound: Nigeria's working-age population is ~1.3e8; a
        # thousand_persons series is ~1e5. 5e9 only catches a real mis-parse.
        if not counts.lt(5e9).all():
            raise ValidationError(
                f"count out of range: max={float(counts.max()):.3g}")

    # A youth rate must actually carry a youth band, or the row is unusable.
    youth = df[df["topic"].astype(str) == "youth_unemployment_rate"]
    if len(youth) and (youth["age_group"].astype(str).str.strip().str.lower()
                       == "total").any():
        raise ValidationError("youth_unemployment_rate row(s) with age_group 'Total'")

    if descriptor:
        need = descriptor.get("expect_topics")
        if need:
            latest = df["period"].max()
            got = df[df["period"] == latest]["topic"].nunique()
            if got < need:
                raise ValidationError(
                    f"latest period {latest} has {got} topics, expected >= {need}")

    return df[UNEMPLOYMENT_COLUMNS].copy()
