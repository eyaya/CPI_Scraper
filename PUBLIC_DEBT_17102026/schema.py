"""Canonical tidy schema + validation for Public Debt statistics.

A roadmap indicator (DSA / debt-transparency). Each row is one published debt
figure -- total public debt, its external vs domestic split, the external
breakdown by creditor class, the domestic breakdown by maturity and by holder,
and debt as a share of GDP -- for a period. Components overlap (domestic debt is
broken down both by maturity and by holder), so this is not a single partition;
every published series is kept as-is under its `component` label, and
downstream use picks the relevant slice.

WHO PUBLISHES DEBT. Unlike the other indicators, the official compiler of
public-debt statistics is usually NOT the statistics office but the Ministry of
Finance / Debt Management Office, or the central bank. Those official national
compilers are accepted sources here (decided 2026-10-08); aggregators (IMF,
World Bank, AfDB, ...) are not. `publisher` names the institution on every row.

WHAT A DEBT FIGURE COVERS. "Public debt" is not one perimeter: central
government only, central government plus guarantees, the whole public sector
including state enterprises, general government... Two countries' totals are
comparable only when their `coverage` matches. It is recorded as the source
states it, never harmonised.
"""
from __future__ import annotations
import re
import pandas as pd

from core.schema_base import ValidationError

DEBT_COLUMNS = [
    "country", "iso3", "indicator",       # indicator = "Public_Debt"
    "publisher",        # the institution that published the figure (descriptor `agency`)
    "coverage",         # debt perimeter as published, e.g. "Central government"
    "component",        # the publisher's own series label (e.g. "External debt")
    "period",           # YYYY-MM | YYYY-Qn | YYYY
    "frequency",        # monthly | quarterly | annual
    "measure",          # stock | share_of_gdp | share
    "value",
    "unit",             # the currency/scale as published (e.g. "USD million"); percent for shares
    "series_code",
    "source_type", "source_url", "source_file", "extracted_at",
]

# stock        -- an outstanding amount, in the currency and scale published
# share_of_gdp -- debt (or a component) as a percent of GDP, AS PUBLISHED;
#                 never computed here from a stock and a GDP figure
# share        -- a component as a percent of total debt, as published
MEASURES = {"stock", "share_of_gdp", "share"}
FREQUENCIES = {"monthly", "quarterly", "annual"}
_PERCENT_MEASURES = {"share_of_gdp", "share"}

_PERIOD = {
    "monthly": re.compile(r"^\d{4}-(0[1-9]|1[0-2])$"),
    "quarterly": re.compile(r"^\d{4}-Q[1-4]$"),
    "annual": re.compile(r"^\d{4}$"),
}


def validate_public_debt(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in DEBT_COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(f"missing columns: {missing}")
    if df.empty:
        raise ValidationError("no rows produced")

    for col in ("publisher", "coverage", "component", "unit"):
        if df[col].isna().any() or (df[col].astype(str).str.strip() == "").any():
            raise ValidationError(f"empty {col} value(s)")

    extra = set(df["measure"].dropna().unique()) - MEASURES
    if extra:
        raise ValidationError(f"unknown measure value(s): {extra}")
    extra = set(df["frequency"].dropna().unique()) - FREQUENCIES
    if extra:
        raise ValidationError(f"unknown frequency value(s): {extra}")

    # FREQUENCY AND PERIOD MUST AGREE: a quarterly row dated "2025" silently
    # becomes an annual observation.
    for freq, rx in _PERIOD.items():
        p = df.loc[df["frequency"] == freq, "period"].astype(str)
        bad = p[~p.str.match(rx)]
        if len(bad):
            raise ValidationError(f"{freq} row(s) with malformed period: "
                                  f"{sorted(bad.unique())[:5]}")

    vals = pd.to_numeric(df["value"], errors="coerce")
    if vals.isna().any():
        raise ValidationError(f"{int(vals.isna().sum())} non-numeric value(s)")
    # Debt stocks and shares are non-negative; the loose upper bound catches a
    # wrong-cell parse (clears unscaled local currency in the hundreds of
    # billions).
    if (vals < 0).any():
        raise ValidationError(f"{int((vals < 0).sum())} negative debt value(s)")
    if not vals.lt(1e15).all():
        raise ValidationError(f"debt value(s) out of range: max={float(vals.max()):.3g}")

    pct = df["measure"].isin(_PERCENT_MEASURES)
    if pct.any():
        if set(df.loc[pct, "unit"].astype(str)) != {"percent"}:
            raise ValidationError("share measures must carry unit 'percent'")
        # A debt-to-GDP ratio can exceed 100 (and has, in Africa); a share of
        # total debt cannot.
        if (vals[df["measure"] == "share"] > 100.5).any():
            raise ValidationError("a share of total debt above 100 percent")
        if (vals[df["measure"] == "share_of_gdp"] > 1000).any():
            raise ValidationError("a debt-to-GDP ratio above 1000 percent -- "
                                  "a scale or cell error")

    return df[DEBT_COLUMNS].copy()
