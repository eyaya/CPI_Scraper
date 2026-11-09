"""Canonical tidy schema + validation for MONETARY POVERTY.

SDG 1.1 / 1.2. Each row is one Foster-Greer-Thorbecke measure -- the headcount
ratio P0 (share of people below the line), the poverty gap P1, the severity P2
-- or a count / share of the poor, for a geography and a POVERTY LINE,
optionally cut by a characteristic of the household. Emitted exactly as the NSO
publishes it; nothing is recomputed (P1 is never derived from P0, a count is
never derived from a rate and a population).

--- THE ONE THING THAT MATTERS MOST HERE ---------------------------------

A poverty rate is meaningless without its line, and African NSOs publish
several lines at once:

* an OVERALL (upper / "total") national line, food plus a non-food allowance;
* an EXTREME (food / lower) national line -- a different, much smaller number
  of poor people from the SAME survey, printed in the SAME table layout;
* sometimes an INTERNATIONAL line (US$2.15 or US$3.00 a day, PPP) that the NSO
  republishes, and occasionally a RELATIVE line (a share of median welfare).

Two rows that differ only in their line are different quantities. So the line
is described by three columns that are in the merge key, not by a note:

  line_type     national | international | relative
  line_level    overall | extreme | other
  line_name     the line exactly as the NSO names it ("Upper poverty line",
                "seuil de pauvreté extrême", "US$2.15 (2017 PPP)")

and `line_value` / `line_unit` carry the line itself where the report prints
it (GHS 1,314 per adult equivalent per year), because a line REBASED between
two rounds is the usual reason one country's series has a break.

--- TWO OTHER TRAPS THIS SCHEMA GUARDS -----------------------------------

**The welfare measure and the unit.** Most African NSOs measure CONSUMPTION per
adult equivalent; Mauritius and South Africa's relative measures use INCOME;
some count HOUSEHOLDS rather than PEOPLE. `welfare_aggregate` and
`unit_of_analysis` record which, since a household headcount is not a person
headcount even within one survey.

**Scale of P1 and P2.** Most reports print the gap and severity as percentages
(P1 = 8.4); a few print them as indices on 0-1 (P1 = 0.084). `unit` carries
which and `validate_poverty` range-checks each against ITS bound, the same rule
as MPI's M0, so a 0-1 gap can never be read as 0.084 per cent.
"""
from __future__ import annotations
import re
import pandas as pd

from core.schema_base import ValidationError

POVERTY_COLUMNS = [
    "country", "iso3", "indicator",   # indicator = "POVERTY"
    "survey",            # the NSO's own source survey, e.g. "GLSS 7", "EHCVM 2021/22"
    "welfare_aggregate", # consumption | income
    "unit_of_analysis",  # person | household
    "line_type",         # national | international | relative
    "line_level",        # overall | extreme | other
    "line_name",         # the line exactly as published
    "line_value",        # the line's amount where printed, else blank
    "line_unit",         # e.g. "GHS per adult equivalent per year", else blank
    "metric",            # headcount | gap | severity | poor_count | ...
    "topic",             # the cut being made: total | locality | sex_of_head | ...
    "characteristic",    # the cut's value as published, or "Total"
    "sex",               # male | female | total   (of the person or the head)
    "age_group",         # the NSO's own band, or "Total"
    "geography",         # "Total country", or a region/province/district
    "locality",          # all | urban | rural | other
    "locality_label",    # the stratum exactly as published ("Accra (GAMA)", "Bamako")
    "period",            # YYYY  -- the survey's reference year (see reference_period)
    "reference_period",  # as published, e.g. "2016/17", "2021-22"
    "frequency",         # annual | ad_hoc
    "value",
    "unit",              # percent | index | persons | households
    "series_code",
    "source_type", "source_url", "source_file", "extracted_at",
]

LINE_TYPES = {"national", "international", "relative"}
LINE_LEVELS = {"overall", "extreme", "other"}
WELFARE = {"consumption", "income"}

# Deliberately small and FGT-shaped. Inequality measures (Gini, quintile
# shares) are a separate indicator, even where the same table prints them.
METRICS = {
    "headcount",          # P0: % of the population below the line
    "gap",                # P1: mean shortfall from the line, as % of it
    "severity",           # P2: squared poverty gap
    "poor_count",         # number of poor people (or households)
    "poor_share",         # this group's share of all the poor, % ("CTR" of P0)
    "gap_contribution",   # this group's share of the national P1, % ("CTR" of P1)
    "severity_contribution",  # this group's share of the national P2, %
    "absolute_contribution",  # P0 x population share, in points of the national P0
                              # (ANSD's "contribution absolue": groups sum to P0)
    "population_share",   # this group's share of the population, % (printed beside it)
    "headcount_ci_low", "headcount_ci_high",   # a bound names what it bounds (see MPI)
}

TOPICS = {
    "total",            # national or regional headline -- region rides in `geography`
    "locality",         # urban / rural / named stratum
    "sex_of_head",      # sex of the household head
    "sex",              # sex of the person
    "age",              # age group of the person
    "age_of_head",
    "education_of_head",
    "employment_of_head",  # activity status / sector of the head
    "household_size",
    "household_type",     # ménage unipersonnel, couple monogamique avec enfants ...
    "literacy_of_head",
    "marital_status_of_head",
    "literacy",           # literacy of the person (usually 15+)
    "education",          # education level of the person
    "quintile",         # welfare quintile -- printed by some offices, trivially 0/100 for P0
}

UNITS = {"percent", "percentage_points", "index", "persons", "households"}
SEXES = {"male", "female", "total"}
LOCALITIES = {"all", "urban", "rural", "other"}
FREQUENCIES = {"annual", "ad_hoc"}
UNITS_OF_ANALYSIS = {"person", "household"}

_SHARE_METRICS = {"headcount", "poor_share", "population_share",
                  "gap_contribution", "severity_contribution",
                  "headcount_ci_low", "headcount_ci_high"}
_FGT_METRICS = {"gap", "severity"}

_YEAR_RE = re.compile(r"^\d{4}$")
_SPLIT_RE = re.compile(r"^((?:19|20)\d{2})\s*[/-]\s*(\d{2}|(?:19|20)\d{2})$")


def split_year(reference_period) -> tuple[str, str] | None:
    """(start, end) years of a split-year fieldwork span ("2013/14",
    "2019-2020"); None for anything else. PERIOD CONVENTION: a round that
    spans two calendar years is dated by its FIRST year (GLSS 7 2016/17 ->
    2016, EICV7 2023/24 -> 2023), whatever year the report itself uses."""
    m = _SPLIT_RE.match(str(reference_period or "").strip())
    if not m:
        return None
    a, b = m.groups()
    return a, (b if len(b) == 4 else a[:2] + b)
_TEXT_COLS = ("survey", "line_name", "topic", "characteristic", "age_group",
              "geography", "locality_label", "reference_period")


def validate_poverty(df: pd.DataFrame, descriptor: dict | None = None) -> pd.DataFrame:
    """Fail loudly on garbage before it can reach a CSV.

    `expect_metrics` / `expect_rows` in the descriptor (if set) assert a
    minimum -- the early warning that a parser captured only part of a table.
    """
    missing = [c for c in POVERTY_COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(f"missing columns: {missing}")
    if df.empty:
        raise ValidationError("no rows produced")

    s = df["period"].astype(str)
    bad = sorted(s[~s.str.match(_YEAR_RE)].unique())[:5]
    if bad:
        raise ValidationError(f"malformed period(s): {bad}")
    sp = df["reference_period"].map(split_year)
    off = [(p, r) for p, r, y in zip(s, df["reference_period"], sp) if y and p != y[0]]
    if off:
        raise ValidationError(
            f"{len(off)} row(s) dated by other than the first year of a split-year "
            f"round (first: period {off[0][0]!r}, reference {off[0][1]!r})")

    for col, allowed in (
        ("metric", METRICS), ("unit", UNITS), ("sex", SEXES),
        ("locality", LOCALITIES), ("frequency", FREQUENCIES),
        ("unit_of_analysis", UNITS_OF_ANALYSIS), ("topic", TOPICS),
        ("line_type", LINE_TYPES), ("line_level", LINE_LEVELS),
        ("welfare_aggregate", WELFARE),
    ):
        extra = set(df[col].dropna().astype(str).unique()) - allowed
        if extra:
            raise ValidationError(f"unknown {col} value(s): {sorted(extra)}")

    for col in _TEXT_COLS:
        v = df[col]
        if v.isna().any() or (v.astype(str).str.strip() == "").any():
            raise ValidationError(f"empty {col} value(s)")

    vals = pd.to_numeric(df["value"], errors="coerce")
    if vals.isna().any():
        raise ValidationError(f"{int(vals.isna().sum())} non-numeric value(s)")

    m, u = df["metric"].astype(str), df["unit"].astype(str)

    # Shares as printed: percentages (0..100) or, where the report prints
    # them that way (EMICoV 2006, ENV 1993-95), fractions (0..1, unit
    # 'index'). Kept as printed; value_std puts both on the percent scale.
    sh = m.isin(_SHARE_METRICS)
    if not u[sh].isin(["percent", "index"]).all():
        raise ValidationError("headcount / share rows must carry unit 'percent' or 'index'")
    shares = vals[sh & (u == "percent")]
    if len(shares) and not shares.between(0, 100).all():
        raise ValidationError(
            f"share metric(s) outside 0..100: min={float(shares.min())}, "
            f"max={float(shares.max())}")
    frac = vals[sh & (u == "index")]
    if len(frac) and not frac.between(0, 1).all():
        raise ValidationError(
            f"share metric(s) with unit 'index' outside 0..1 (max {float(frac.max())}). "
            f"If the report prints them as percentages, set unit 'percent'.")

    # P1 and P2: each against ITS OWN bound (the MPI M0 rule).
    fgt = m.isin(_FGT_METRICS)
    if fgt.any() and not u[fgt].isin(["percent", "index"]).all():
        raise ValidationError("gap / severity rows must carry unit 'percent' or 'index'")
    idx = vals[fgt & (u == "index")]
    if len(idx) and not idx.between(0, 1).all():
        raise ValidationError(
            f"gap/severity with unit 'index' outside 0..1 (max {float(idx.max())}). "
            f"If the report prints them as percentages, set unit 'percent'.")
    pct = vals[fgt & (u == "percent")]
    if len(pct) and not pct.between(0, 100).all():
        raise ValidationError("gap/severity with unit 'percent' outside 0..100")

    # THE FGT ORDERING, a law and not a pin: for one line and one group,
    # P0 >= P1 >= P2 (on one scale). A violation means two columns were read
    # in the wrong order -- the commonest silent error in these tables, since
    # all three are plausible percentages.
    key = [c for c in POVERTY_COLUMNS if c not in
           ("metric", "value", "unit", "series_code", "source_type",
            "source_url", "source_file", "extracted_at", "indicator")]
    scaled = vals.where(u != "index", vals * 100)
    # Key cells as text: pivot_table silently DROPS groups with a NaN key, and
    # line_value is blank on most rows -- the check would then test nothing.
    keyed = df[key].astype(object).where(df[key].notna(), "").astype(str)
    keyed["metric"], keyed["_v"] = m, scaled
    wide = (keyed.loc[m.isin(["headcount", "gap", "severity"])]
              .pivot_table(index=key, columns="metric", values="_v", aggfunc="first"))
    for hi, lo in (("headcount", "gap"), ("gap", "severity")):
        if hi in wide and lo in wide:
            both = wide[[hi, lo]].dropna()
            bad = both[both[lo] > both[hi] + 0.05]
            if len(bad):
                raise ValidationError(
                    f"{len(bad)} group(s) with {lo} > {hi} (first: "
                    f"{bad.index[0]!r}) -- FGT measures satisfy P0 >= P1 >= P2; "
                    f"a violation means the columns were read in the wrong order")

    ac = m == "absolute_contribution"
    if ac.any() and (not u[ac].eq("percentage_points").all()
                     or not vals[ac].between(0, 100).all()):
        raise ValidationError("absolute_contribution must be percentage_points in 0..100")

    counts = vals[m == "poor_count"]
    if len(counts) and not (counts.ge(0) & counts.lt(5e9)).all():
        raise ValidationError("poor_count out of range")

    lv = df["line_value"].astype(str).str.strip()
    lvn = pd.to_numeric(lv[lv != ""], errors="coerce")
    if lvn.isna().any() or (lvn <= 0).any():
        raise ValidationError("line_value must be blank or a positive number")
    if ((lv != "") & (df["line_unit"].astype(str).str.strip() == "")).any():
        raise ValidationError("a line_value needs its line_unit (currency, per what, per when)")

    if descriptor:
        need = descriptor.get("expect_metrics")
        if need and df["metric"].nunique() < need:
            raise ValidationError(
                f"{df['metric'].nunique()} distinct metrics, expected >= {need}")
        need = descriptor.get("expect_rows")
        if need and len(df) < need:
            raise ValidationError(f"{len(df)} rows, expected >= {need}")
    return df
