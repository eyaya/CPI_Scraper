"""Canonical tidy output schema + validation for GDP / national-accounts data.

Parallel to `schema.py` (CPI). GDP is a different shape from a price index, so it
gets its own columns rather than bending the COICOP/monthly CPI schema:

* classified by SNA *approach* (production / expenditure / income) plus the
  headline *aggregate*, not by COICOP division;
* published quarterly AND annually (period is `YYYY` or `YYYY-Qn`, not `YYYY-MM`);
* measured as value *levels* (current & constant prices) and as growth rates,
  not as index numbers and inflation.

Every GDP parser, whatever the country or source tier, must emit a DataFrame with
exactly these columns so that all 54 NSOs' GDP concatenates into one file. Cross-
country standardisation of the category vocabulary (ISIC / SNA codes) is a later
step; for now we keep each NSO's own `series_code` + published `category` label,
exactly as the CPI side keeps the source's own `coicop_label`.
"""
from __future__ import annotations
import re
import pandas as pd

from core.schema_base import ValidationError

# Canonical column order for every GDP tidy output file.
GDP_COLUMNS = [
    "country",              # e.g. South_Africa
    "iso3",                 # e.g. ZAF
    "indicator",            # always "GDP"
    "approach",             # production | expenditure | income | aggregate
    "category",             # component/sector as published by the NSO (H05)
    "category_group",       # the SNA table it sits under, as published (H04)
    "series_code",          # the NSO's own series code (provenance + join key)
    "geography",            # e.g. "Total country" (national)
    "period",               # YYYY (annual) or YYYY-Qn (quarterly)
    "frequency",            # annual | quarterly
    "price_basis",          # current | constant | not_applicable
    "seasonal_adjustment",  # nsa | saa | not_applicable
    "measure",              # what `value` is: level | growth_yoy | growth_qoq | ...
    "value",                # numeric value of the measure
    "unit",                 # e.g. "R million" | "percent" | "index"
    "base_period",          # e.g. "Constant 2015 prices" (levels); blank otherwise
    "source_type",          # api | excel | csv | pdf | doc
    "source_url",           # where the data was fetched from
    "source_file",          # the raw file it was parsed from
    "extracted_at",         # ISO timestamp of the collection run
]

# `measure` says what `value` represents; `price_basis` says nominal vs real, kept
# orthogonal so a real (constant-price) growth rate is unambiguous.
GDP_MEASURES = {"level", "growth_yoy", "growth_qoq", "growth_period", "deflator",
                "per_capita", "share", "contribution"}
APPROACHES = {"production", "expenditure", "income", "aggregate"}
PRICE_BASIS = {"current", "constant", "not_applicable"}
SEASONAL = {"nsa", "saa", "not_applicable"}

_ANNUAL_RE = re.compile(r"^\d{4}$")
_QUARTER_RE = re.compile(r"^\d{4}-Q[1-4]$")


def _bad_periods(period: pd.Series) -> list[str]:
    s = period.astype(str)
    ok = s.str.match(_ANNUAL_RE) | s.str.match(_QUARTER_RE)
    return sorted(s[~ok].unique())[:5]


def validate_gdp(df: pd.DataFrame) -> pd.DataFrame:
    """Fail loudly on garbage before it reaches the output file. Returns the
    column-ordered frame if it passes."""
    missing = [c for c in GDP_COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(f"missing columns: {missing}")
    if df.empty:
        raise ValidationError("no rows produced")

    bad = _bad_periods(df["period"])
    if bad:
        raise ValidationError(f"malformed period(s): {bad}")

    for col, allowed in (
        ("measure", GDP_MEASURES), ("approach", APPROACHES),
        ("price_basis", PRICE_BASIS), ("seasonal_adjustment", SEASONAL),
    ):
        extra = set(df[col].dropna().unique()) - allowed
        if extra:
            raise ValidationError(f"unknown {col} value(s): {extra}")

    vals = pd.to_numeric(df["value"], errors="coerce")
    if vals.isna().any():
        raise ValidationError(f"{int(vals.isna().sum())} non-numeric value(s)")

    # GDP levels can be negative (change in inventories, residual, net exports);
    # only bound the magnitude to catch a parse that grabbed the wrong cell. The
    # bound must clear currencies reported UNSCALED (Ghana GDP ~1.4e12 GHS,
    # Nigeria ~2e14 NGN), so it's deliberately loose — a wrong-cell parse (a date,
    # a concatenation) still lands far outside it.
    is_growth = df["measure"].astype(str).str.startswith("growth")
    lvl = vals[~is_growth]
    if len(lvl) and not lvl.abs().lt(1e16).all():
        raise ValidationError(f"level value(s) out of plausible range: "
                              f"max|.|={float(lvl.abs().max()):.3g}")
    gr = vals[is_growth]
    # Growth is a %. No tight floor: a SIGNED series (net exports, change in
    # inventories) crossing zero, or a sector growing off a near-zero base
    # (Ghana oil in 2011 ≈ +7000% YoY), legitimately exceeds ±100% — these are
    # published as-is. The loose bound only flags a level mis-parsed as a rate.
    if len(gr) and not gr.abs().lt(1e6).all():
        raise ValidationError(f"growth value(s) implausible: "
                              f"min/max=({float(gr.min())}, {float(gr.max())})")

    return df[GDP_COLUMNS].copy()
