"""Canonical tidy schema + validation for the Producer Price Index (PPI).

A roadmap indicator -- the upstream companion to CPI (prices received by
domestic producers). Each row is, for one INDEX (the NSO's own: "PPI",
"Indice des prix à la production industrielle", Stats SA's "PPI for final
manufactured goods" ...) and one industry, the index level, a percentage
change, or the industry's weight, for one month / quarter / year. Emitted as
published: nothing is rebased, chained or recomputed.

WHICH INDEX. Many NSOs publish one PPI; some publish several that share
industry labels (Stats SA: final manufactured goods, intermediate
manufactured goods, exported commodities, imported commodities ...). So the
index is part of the identity: `index_name` is the NSO's title, and
`index_variant` the controlled kind of index (vocabulary below) that the
standardised series_id carries.

THE BASE IS PART OF THE IDENTITY of an index level: a series rebased from
2010=100 to 2019=100 is two series, and both are kept (merge key).
"""
from __future__ import annotations
import re
import pandas as pd

from core.schema_base import ValidationError

PPI_COLUMNS = [
    "country", "iso3", "indicator",       # indicator = "PPI"
    "index_name",       # the NSO's own title of the index ("Indice des prix à la production industrielle")
    "index_variant",    # INDEX_VARIANTS
    "industry",         # NSO's own industry / product label (or "All industries")
    "industry_code_nso",  # the NSO's own code for it when printed (ISIC/NACE/NAEMA "C", "10", "B-E"); else blank
    "period",           # YYYY-MM | YYYY-Qn | YYYY, by frequency
    "frequency",        # monthly | quarterly | annual
    "measure",          # MEASURES
    "value",
    "unit",             # index | percent (changes, weights) | per_mille | per_ten_thousand | per_hundred_thousand (weights)
    "base_period",      # index reference as printed ("2015=100", "T4 2018 = 100"); blank if not published
    "ownership",        # blank = all producers; "public" / "private" when the NSO publishes the
                        # index separately by ownership sector (ONS Algeria)
    "currency_basis",   # blank = the national currency, as almost everywhere; else the basis the NSO
                        # publishes the SAME index in ("USD", "ZWG", "mixed": ZimStat's three versions)
    "series_code",
    "source_type", "source_url", "source_file", "extracted_at",
]

# output             -- producers' output prices, all markets (the standard PPI / IPPI)
# domestic_market    -- output sold on the domestic market only
# export             -- output sold abroad (export producer prices)
# import             -- prices of imported products (Stats SA "imported commodities")
# final_goods        -- stage of processing: final manufactured goods (Stats SA)
# intermediate_goods -- stage of processing: intermediate goods
# agriculture        -- an agricultural producer price index (farm-gate), kept apart
#                       from the industrial index because it is not the same survey
# services           -- a services producer price index (SPPI)
# domestic_consumption -- commodities for domestic consumption, domestic AND imported
#                       (Stats SA's pre-2012 headline PPI)
INDEX_VARIANTS = {"output", "domestic_market", "export", "import", "final_goods",
                  "intermediate_goods", "agriculture", "services", "domestic_consumption"}
# index          -- the level
# inflation_yoy  -- % change on the same period a year earlier
# inflation_mom  -- % change on the previous month
# inflation_qoq  -- % change on the previous quarter
# inflation_avg  -- % change of the 12-month (or annual) average on the previous one
# inflation_ytd  -- cumulative % change since the start of the year (glissement depuis janvier)
# inflation_ytd_avg -- % change of the January-to-date average on the same months a year
#                   earlier ("variation des cumuls", ANSD / INS Côte d'Ivoire)
# weight         -- the industry's weight in the index, on the scale printed
MEASURES = {"index", "inflation_yoy", "inflation_mom", "inflation_qoq", "inflation_avg",
            "inflation_ytd", "inflation_ytd_avg", "weight"}
WEIGHT_SCALE = {"percent": 100, "per_mille": 1000, "per_ten_thousand": 10000,
                "per_hundred_thousand": 100000}
UNITS = {"index"} | set(WEIGHT_SCALE)
FREQUENCIES = {"monthly", "quarterly", "annual"}

_PERIOD_RE = {"monthly": re.compile(r"^\d{4}-(0[1-9]|1[0-2])$"),
              "quarterly": re.compile(r"^\d{4}-Q[1-4]$"),
              "annual": re.compile(r"^\d{4}$")}
_TEXT_COLS = ("index_name", "industry")
# One observation (pipeline.merge_keys uses the same list).
KEY = ["index_name", "index_variant", "industry", "industry_code_nso", "ownership", "currency_basis",
       "frequency", "measure", "base_period", "period"]


def _lag(period: str, freq: str, n: int) -> str:
    """The period `n` steps earlier, in the same notation."""
    if freq == "monthly":
        y, m = int(period[:4]), int(period[5:7])
        k = y * 12 + m - 1 - n
        return f"{k // 12:04d}-{k % 12 + 1:02d}"
    if freq == "quarterly":
        y, q = int(period[:4]), int(period[6])
        k = y * 4 + q - 1 - n
        return f"{k // 4:04d}-Q{k % 4 + 1}"
    return f"{int(period) - n:04d}"


def validate_ppi(df: pd.DataFrame, descriptor: dict | None = None) -> pd.DataFrame:
    """Fail loudly on garbage before it can reach a CSV."""
    missing = [c for c in PPI_COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(f"missing columns: {missing}")
    if df.empty:
        raise ValidationError("no rows produced")

    extra = set(df["ownership"].dropna().astype(str).unique()) - {"", "public", "private"}
    if extra:
        raise ValidationError(f"unknown ownership value(s): {sorted(extra)}")
    for col, allowed in (("measure", MEASURES), ("unit", UNITS),
                         ("frequency", FREQUENCIES), ("index_variant", INDEX_VARIANTS)):
        extra = set(df[col].dropna().astype(str).unique()) - allowed
        if extra:
            raise ValidationError(f"unknown {col} value(s): {sorted(extra)}")
    for col in _TEXT_COLS:
        v = df[col]
        if v.isna().any() or (v.astype(str).str.strip() == "").any():
            raise ValidationError(f"empty {col} value(s)")

    f, p = df["frequency"].astype(str), df["period"].astype(str)
    for freq, rx in _PERIOD_RE.items():
        bad = sorted(p[(f == freq) & ~p.str.match(rx)].unique())[:5]
        if bad:
            raise ValidationError(f"malformed {freq} period(s): {bad}")

    vals = pd.to_numeric(df["value"], errors="coerce")
    if vals.isna().any():
        raise ValidationError(f"{int(vals.isna().sum())} non-numeric value(s)")
    m, u = df["measure"].astype(str), df["unit"].astype(str)
    if not u[m == "index"].eq("index").all():
        raise ValidationError("index rows must carry unit 'index'")
    infl = m.str.startswith("inflation")
    if not u[infl].eq("percent").all():
        raise ValidationError("inflation rows must carry unit 'percent'")
    if not u[m == "weight"].isin(list(WEIGHT_SCALE)).all():
        raise ValidationError(f"weight rows must carry a weight unit {sorted(WEIGHT_SCALE)}")
    idx = vals[m == "index"]
    if len(idx) and not (idx.gt(0) & idx.lt(1e6)).all():
        raise ValidationError(f"index value(s) out of range (min {float(idx.min())}, max {float(idx.max())})")
    if len(vals[infl]) and not vals[infl].abs().lt(1e4).all():
        raise ValidationError("inflation value(s) implausible")
    w = m == "weight"
    if w.any() and (vals[w].lt(0).any() or (vals[w] > u[w].map(WEIGHT_SCALE)).any()):
        raise ValidationError("weight(s) outside 0..the scale of their unit")

    # One observation per key. Exact repeats (a workbook printing a row twice)
    # are dropped; the same key with DIFFERENT values is a misread and fails.
    dupkey = df.duplicated(KEY, keep=False)
    if dupkey.any():
        k = df.loc[dupkey, KEY].astype(str).agg("|".join, axis=1)
        clash = vals[dupkey].groupby(k).nunique()
        if (clash > 1).any():
            raise ValidationError(f"{int((clash > 1).sum())} key(s) with conflicting values "
                                  f"(first: {clash[clash > 1].index[0]})")
        df = df.loc[~df.duplicated(KEY)]
        vals = vals.loc[df.index]

    _check_yoy(df, vals)

    if descriptor:
        need = descriptor.get("expect_rows")
        if need and len(df) < need:
            raise ValidationError(f"{len(df)} rows, expected >= {need}")
        need = descriptor.get("expect_periods")
        if need and df["period"].nunique() < need:
            raise ValidationError(f"{df['period'].nunique()} periods, expected >= {need}")
    return df[PPI_COLUMNS].copy()


def _check_yoy(df: pd.DataFrame, vals: pd.Series) -> None:
    """THE COLUMN-SWAP GUARD. Where a run publishes both the index and its
    year-on-year change, the change must agree with the index a year apart --
    a misread column (last year's index read as this year's, the m/m change
    filed as y/y) breaks it for most rows. Rounded published indices disagree
    a little, so the test is loose: |published - implied| <= 0.6 pp + 1 % of
    the change, failing only when more than a quarter of >= 12 comparable
    rows disagree. It checks; it never fills or corrects a value."""
    # A change carries no base, a level does: match on the index and industry,
    # and test the change against EVERY base whose level exists at both dates.
    key = ["index_name", "index_variant", "industry", "industry_code_nso", "ownership", "currency_basis", "frequency"]
    k = df[key].astype(str).agg("\x1f".join, axis=1)
    lvl: dict = {}
    for a, b, p, v, mm in zip(k, df["base_period"].astype(str), df["period"].astype(str), vals, df["measure"]):
        if mm == "index":
            lvl.setdefault(a, {}).setdefault(b, {})[p] = v
    lag = {"monthly": 12, "quarterly": 4, "annual": 1}
    n = bad = 0
    first = None
    for a, p, v, mm, fq in zip(k, df["period"].astype(str), vals, df["measure"], df["frequency"]):
        if mm != "inflation_yoy":
            continue
        pairs = [(s.get(p), s.get(_lag(p, fq, lag[fq]))) for s in lvl.get(a, {}).values()]
        pairs = [(x, y) for x, y in pairs if x is not None and y]
        if not pairs:
            continue
        implied = min(((x / y - 1) * 100 for x, y in pairs), key=lambda i: abs(i - v))
        n += 1
        if abs(implied - v) > 0.6 + 0.01 * abs(v):
            bad += 1
            first = first or (a.replace("\x1f", " | "), p, v, round(implied, 2))
    if n >= 12 and bad > n / 4:
        raise ValidationError(
            f"{bad}/{n} year-on-year changes disagree with the published index a year "
            f"apart (first: {first}) -- a column was probably read in the wrong place")
