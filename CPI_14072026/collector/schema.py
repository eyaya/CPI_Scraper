"""Canonical tidy output schema + validation for all countries/indicators.

Every parser, regardless of country or source tier, must emit a DataFrame with
exactly these columns. That is what makes 54 heterogeneous NSO sources
concatenate into one analysable file.
"""
from __future__ import annotations
import re
import pandas as pd

# Canonical column order for every tidy output file.
COLUMNS = [
    "country",        # e.g. South_Africa
    "iso3",           # e.g. ZAF
    "indicator",      # e.g. CPI
    "coicop_code",    # 2-digit COICOP division: "00" (All items) .. "13"
    "coicop_label",   # division label as published by the source NSO
    "geography",      # e.g. "Total country" (national) / province
    "period",         # YYYY-MM
    "measure",        # what `value` is: index | inflation_yoy | inflation_mom
    "value",          # numeric value of the measure
    "unit",           # e.g. "Index" or "percent"
    "base_period",    # e.g. "Dec 2024 = 100" (for index); blank for rates
    "frequency",      # e.g. "monthly"
    "source_type",    # api | excel | csv | pdf | doc
    "source_url",     # where the data was fetched from
    "source_file",    # the raw file it was parsed from
    "extracted_at",   # ISO timestamp of the collection run
]

# Different NSOs publish different measures. Index levels (SA, Nigeria) or, for
# many PDF-only NSOs, only inflation rates by division (Kenya).
MEASURES = {"index", "inflation_yoy", "inflation_mom"}

_PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class ValidationError(Exception):
    pass


def validate(df: pd.DataFrame, *, expect_divisions: int | None = None) -> pd.DataFrame:
    """Fail loudly on garbage before it ever reaches the output file.

    Returns the frame (column-ordered) if it passes.
    """
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(f"missing columns: {missing}")

    if df.empty:
        raise ValidationError("no rows produced")

    bad_period = df.loc[~df["period"].astype(str).str.match(_PERIOD_RE), "period"]
    if len(bad_period):
        raise ValidationError(f"malformed period(s): {sorted(bad_period.unique())[:5]}")

    bad_measure = set(df["measure"].unique()) - MEASURES
    if bad_measure:
        raise ValidationError(f"unknown measure(s): {bad_measure}")

    # values must be numeric; plausible range depends on the measure
    vals = pd.to_numeric(df["value"], errors="coerce")
    if vals.isna().any():
        n = int(vals.isna().sum())
        raise ValidationError(f"{n} non-numeric value(s)")
    is_index = df["measure"] == "index"
    idx_vals = vals[is_index]
    if len(idx_vals) and not idx_vals.between(1, 100000).all():
        rng = (float(idx_vals.min()), float(idx_vals.max()))
        raise ValidationError(f"index value(s) out of plausible range: min/max={rng}")
    rate_vals = vals[~is_index]
    if len(rate_vals) and not rate_vals.between(-100, 100000).all():
        rng = (float(rate_vals.min()), float(rate_vals.max()))
        raise ValidationError(f"inflation-rate value(s) implausible: min/max={rng}")

    if expect_divisions is not None:
        # per period, we expect a stable count of division series
        counts = df.groupby("period")["coicop_code"].nunique()
        latest = counts.index.max()
        if counts.loc[latest] < expect_divisions:
            raise ValidationError(
                f"latest period {latest} has {counts.loc[latest]} divisions, "
                f"expected >= {expect_divisions}"
            )

    return df[COLUMNS].copy()
