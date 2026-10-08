"""Canonical tidy schema + validation for Labour / economic-activity data.

WHAT THIS INDICATOR IS, AND WHAT IT IS NOT. `labour/` holds the COMPOSITION of
employment -- what work people do -- and `unemployment/` holds the headline
labour-force status series -- how many are working, looking, or outside the
labour force. The boundary is deliberate and there is no overlap: a figure has
exactly one home.

    labour/         industry, occupation, status in employment, institutional
                    sector, formal/informal, activity status
    unemployment/   unemployment / participation / employment-to-population
                    rates, the level counts behind them, and LU1-LU4

`unemployment_rate` was previously a topic HERE as well, which put Ghana's
census-based regional rates in this file untagged as strict or broad while the
quarterly series lived next door. It has been removed from the vocabulary; the
census rates moved to `unemployment/` where the definitional columns exist.

THE CLASSIFICATION TRAVELS WITH THE CATEGORY. An industry or occupation label
means nothing without the scheme that produced it: "Commerce" is a division of
Mali's national 9-branch scheme and a very different thing from ISIC Rev.4's
"Wholesale and retail trade". Categories are captured exactly as the NSO prints
them -- never remapped -- and `classification` records which scheme they belong
to, in the same way the CPI collector keeps native nomenclatures beside COICOP.

Counts and published rates sit side by side, so `measure` allows both, and
`unit` allows thousand_persons because several NSOs publish levels in
thousands and rescaling them would be recomputation.
"""
from __future__ import annotations
import re

import pandas as pd

from core.schema_base import ValidationError

LABOUR_COLUMNS = [
    "country", "iso3", "indicator",       # indicator = "Labour"
    "survey",           # the NSO's own survey/publication name
    "topic",            # see TOPICS
    "characteristic",   # the published category within the topic (incl. "Total")
    "classification",   # the scheme that category belongs to -- see CLASSIFICATIONS
    "sex",              # male | female | total
    "age_group",        # the NSO's own band, or "Total"
    "education",        # the NSO's own level, or "Total"
    "geography",        # "Total country" or a sub-national unit
    "locality",         # all | urban | rural | other
    "locality_label",   # the stratum exactly as published
    "working_age_base", # "15+", "15-64", "10+", ... as the NSO defines it
    "period",           # YYYY | YYYY-Qn | YYYY-Hn
    "reference_period", # as published, e.g. "Apr-Jun 2026", "PHC 2021"
    "frequency",        # quarterly | semiannual | annual | ad_hoc
    "measure",          # count | rate | share
    "value",
    "unit",             # persons | thousand_persons | percent
    "series_code",
    "source_type", "source_url", "source_file", "extracted_at",
]

# The controlled topic vocabulary. Deliberately small: these are the cuts of
# employment essentially every LFS and census publishes. Anything a country
# reports that does not fit is dropped rather than bent into a neighbour.
TOPICS = {
    "activity_status",     # employed / unemployed / outside the labour force
    "employment_status",   # employee, employer, own-account, contributing family
    "industry",            # branch of economic activity of the main job
    "occupation",          # occupational group of the main job
    "sector",              # institutional sector: public / private / household
    "formality",           # formal vs informal sector, and informal employment
    "hours",               # hours actually or usually worked, where published
    "earnings",            # published average earnings, where the NSO gives them
}

# The scheme a `characteristic` belongs to. "National (<scheme>)" is used
# wherever an NSO publishes its own grouping rather than an international one --
# that is common and is NOT a defect, but a user joining two countries has to
# be able to see it.
CLASSIFICATIONS = {
    "ISIC Rev.3", "ISIC Rev.3.1", "ISIC Rev.4",
    "ISCO-88", "ISCO-08",
    # ICSE-18 has two hierarchies and NSOs say which they used. ZamStats
    # reports on ICSE-18-A (authority) and names ICSE-18-R (risk) as the other;
    # collapsing them to a bare "ICSE-18" would discard a distinction the
    # source is explicit about.
    "ICSE-93", "ICSE-18", "ICSE-18-A", "ICSE-18-R",
    "National", "Not applicable",
}

MEASURES = {"count", "rate", "share"}
UNITS = {"persons", "thousand_persons", "percent"}
SEXES = {"male", "female", "total"}
LOCALITIES = {"all", "urban", "rural", "other"}
FREQUENCIES = {"quarterly", "semiannual", "annual", "ad_hoc"}

_ANNUAL_RE = re.compile(r"^\d{4}$")
_QUARTER_RE = re.compile(r"^\d{4}-Q[1-4]$")
_HALF_RE = re.compile(r"^\d{4}-H[12]$")

_TEXT_COLS = ("survey", "topic", "characteristic", "classification",
              "age_group", "education", "geography", "locality_label",
              "working_age_base", "reference_period")


def validate_labour(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in LABOUR_COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(f"missing columns: {missing}")
    if df.empty:
        raise ValidationError("no rows produced")

    # PERIODS ARE NOT ALL ANNUAL. This used to accept YYYY only, which was true
    # of a census-based collection and is not true of a labour force survey:
    # most NSOs publish these cross-tabs quarterly, and a quarterly period
    # would have been rejected outright.
    s = df["period"].astype(str)
    ok = s.str.match(_ANNUAL_RE) | s.str.match(_QUARTER_RE) | s.str.match(_HALF_RE)
    bad = sorted(s[~ok].unique())[:5]
    if bad:
        raise ValidationError(
            f"malformed period(s): {bad} -- expected YYYY, YYYY-Qn or YYYY-Hn")

    for col, allowed in (("topic", TOPICS), ("classification", CLASSIFICATIONS),
                         ("measure", MEASURES), ("unit", UNITS),
                         ("sex", SEXES), ("locality", LOCALITIES),
                         ("frequency", FREQUENCIES)):
        extra = set(df[col].dropna().astype(str).unique()) - allowed
        if extra:
            raise ValidationError(f"unknown {col} value(s): {sorted(extra)[:6]}")

    for col in _TEXT_COLS:
        if df[col].isna().any() or (df[col].astype(str).str.strip() == "").any():
            raise ValidationError(f"empty {col} value(s)")

    vals = pd.to_numeric(df["value"], errors="coerce")
    if vals.isna().any():
        raise ValidationError(f"{int(vals.isna().sum())} non-numeric value(s)")

    m, u = df["measure"].astype(str), df["unit"].astype(str)

    counts = vals[m == "count"]
    if len(counts):
        if (counts < 0).any():
            raise ValidationError("negative count(s)")
        # Bounded by the largest African population, with headroom. A count in
        # THOUSANDS is checked on its own scale rather than being multiplied
        # out -- multiplying would be recomputation, and a value of 8,481
        # thousand is not an error.
        limit = 5e9 if (u[m == "count"] == "persons").any() else 5e6
        if not counts.lt(limit).all():
            raise ValidationError(
                f"count out of range for its unit: max={float(counts.max()):.4g}")

    pct = vals[m.isin(["rate", "share"]) & (u == "percent")]
    if len(pct) and not pct.between(0, 100).all():
        raise ValidationError(
            f"percent rate/share outside 0..100: min={float(pct.min())}, "
            f"max={float(pct.max())}")

    # A category is meaningless without its scheme, and a scheme is meaningless
    # on a row that has no category. Both directions are checked, because the
    # commonest way to lose the classification is to default it.
    cat = df["topic"].astype(str).isin(["industry", "occupation",
                                        "employment_status"])
    unclassified = df.loc[cat, "classification"].astype(str) == "Not applicable"
    if unclassified.any():
        bad_topics = sorted(df.loc[cat & unclassified, "topic"].unique())
        raise ValidationError(
            f"{int(unclassified.sum())} {bad_topics} row(s) carry no "
            f"classification. An industry or occupation label cannot be "
            f"compared across countries without the scheme that produced it -- "
            f"record the NSO's own scheme, or 'National' where it is its own.")

    return df[LABOUR_COLUMNS].copy()
