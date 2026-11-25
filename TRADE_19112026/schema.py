"""Canonical tidy schema + validation for Merchandise Trade statistics.

A roadmap indicator (AfCFTA, current-account and revenue monitoring): monthly
exports, imports and the trade balance, by commodity and by partner. Each row is
ONE published figure -- a flow (exports, imports, re-exports, the balance ...)
for one commodity grouping and one partner, in one currency or weight unit, for
one month / quarter / year. Emitted as published: nothing is summed, converted,
deflated or derived (no balance computed from exports and imports, no dollar
value computed from a local-currency one).

TWO CUTS, NOT THE CROSS-TABULATION. The roadmap asks for flows "by partner and
commodity". NSOs publish commodity tables (all partners) and partner tables
(all commodities); a few also publish the full partner x commodity matrix
(GSS StatsBank: 232 partners x 97 chapters x months). The schema can hold any
cell, but the collection takes the two cuts plus the totals; a matrix cell
appears only where it is the NSO's own table (e.g. "main exports to the EU").

COMMODITIES are kept in the NSO's own grouping (HS chapters, SITC sections,
BEC, or national product lists such as "Cocoa beans", "Gold"), named by
`commodity_classification`; the standardised layer codes HS and SITC.
"""
from __future__ import annotations
import re
import pandas as pd

from core.schema_base import ValidationError

TRADE_COLUMNS = [
    "country", "iso3", "indicator",       # indicator = "Trade"
    "tradeflow",        # TRADEFLOWS
    "commodity",        # the NSO's label as printed; "All products" for the all-commodity total
    "commodity_classification",  # COMMODITY_CLASSIFICATIONS; blank for "All products"
    "commodity_code_nso",        # the code printed beside the label ("27", "0", "271000"); else blank
    "partner",          # the NSO's label as printed ("France", "CEDEAO", "Europe"); "All partners" for the world
    "partner_type",     # PARTNER_TYPES
    "period",           # YYYY-MM | YYYY-Qn | YYYY, by frequency
    "frequency",        # monthly | quarterly | annual
    "measure",          # value | net_weight | quantity
    "value",            # as printed, in `unit` x `unit_multiplier`
    "unit",             # ISO 4217 currency of a value (GHS, XOF, USD); kg | tonnes for a weight; the
                        # NSO's unit for a quantity (e.g. "head", "litres")
    "unit_multiplier",  # the scale printed on the table: 1, 1000 ("thousands"), 1000000 ("millions"), 1e9
    "price_basis",      # fob | cif | blank when the table does not say
    "prices",           # current | constant (a "real" value at the prices of a base year, as printed)
    "trade_system",     # general | special | blank when not stated
    "series_code",
    "source_type", "source_url", "source_file", "extracted_at",
]

# export          -- total exports (domestic exports + re-exports, or as the NSO defines "exports")
# domestic_export -- exports of domestic produce only
# re_export       -- re-exports
# import          -- imports (general imports, or imports for home use, as the NSO defines it)
# total           -- total trade = exports + imports (the NSO's "volume des échanges")
# balance         -- exports minus imports, SIGNED (a printed "deficit of 120" is -120)
TRADEFLOWS = {"export", "domestic_export", "re_export", "import", "total", "balance"}
# hs2/hs4/hs6 -- Harmonized System chapters / headings / subheadings
# sitc1/sitc2/sitc3 -- SITC sections / divisions / groups
# bec -- Broad Economic Categories (consumption / intermediate / capital goods)
# national -- the NSO's own product list or grouping ("Cocoa beans", "Produits pétroliers")
COMMODITY_CLASSIFICATIONS = {"", "hs2", "hs4", "hs6", "sitc1", "sitc2", "sitc3", "bec", "national"}
# world -- all partners; country -- one country (or territory); group -- a bloc,
# region or continent as printed ("ECOWAS", "Union européenne", "Asia", "Rest of the world")
PARTNER_TYPES = {"world", "country", "group"}
MEASURES = {"value", "net_weight", "quantity"}
FREQUENCIES = {"monthly", "quarterly", "annual"}
PRICE_BASES = {"", "fob", "cif"}
PRICES = {"current", "constant"}
TRADE_SYSTEMS = {"", "general", "special"}
MULTIPLIERS = {1.0, 1e3, 1e6, 1e9}
WEIGHT_UNITS = {"kg", "tonnes"}

_PERIOD_RE = {"monthly": re.compile(r"^\d{4}-(0[1-9]|1[0-2])$"),
              "quarterly": re.compile(r"^\d{4}-Q[1-4]$"),
              "annual": re.compile(r"^\d{4}$")}
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")

# One observation (pipeline.merge_keys uses the same list). The multiplier is
# NOT part of it: one figure printed in millions in a bulletin and in billions
# in a yearbook is one observation, and the newer source replaces the older.
KEY = ["tradeflow", "commodity_classification", "commodity_code_nso", "commodity", "partner_type",
       "partner", "frequency", "period", "measure", "unit", "price_basis", "prices", "trade_system"]


def validate_trade(df: pd.DataFrame, descriptor: dict | None = None) -> pd.DataFrame:
    """Fail loudly on garbage before it can reach a CSV."""
    missing = [c for c in TRADE_COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(f"missing columns: {missing}")
    if df.empty:
        raise ValidationError("no rows produced")
    df = df.copy()
    for col in ("commodity_classification", "commodity_code_nso", "price_basis", "trade_system"):
        df[col] = df[col].fillna("").astype(str)

    for col, allowed in (("tradeflow", TRADEFLOWS), ("commodity_classification", COMMODITY_CLASSIFICATIONS),
                         ("partner_type", PARTNER_TYPES), ("measure", MEASURES),
                         ("frequency", FREQUENCIES), ("price_basis", PRICE_BASES),
                         ("prices", PRICES), ("trade_system", TRADE_SYSTEMS)):
        extra = set(df[col].dropna().astype(str).unique()) - allowed
        if extra:
            raise ValidationError(f"unknown {col} value(s): {sorted(extra)}")
    for col in ("commodity", "partner", "unit"):
        v = df[col]
        if v.isna().any() or (v.astype(str).str.strip() == "").any():
            raise ValidationError(f"empty {col} value(s)")

    _check_labels(df)

    f, p = df["frequency"].astype(str), df["period"].astype(str)
    for freq, rx in _PERIOD_RE.items():
        bad = sorted(p[(f == freq) & ~p.str.match(rx)].unique())[:5]
        if bad:
            raise ValidationError(f"malformed {freq} period(s): {bad}")

    # The world total is "All products" / "All partners", with no classification.
    allp = df["commodity"].astype(str) == "All products"
    if (allp != (df["commodity_classification"] == "")).any():
        raise ValidationError("'All products' rows, and only they, carry a blank commodity_classification")
    world = df["partner_type"].astype(str) == "world"
    if (world != (df["partner"].astype(str) == "All partners")).any():
        raise ValidationError("partner_type 'world' goes with partner 'All partners', and only with it")

    m, u = df["measure"].astype(str), df["unit"].astype(str)
    if not u[m == "value"].str.match(_CURRENCY_RE).all():
        raise ValidationError(f"value rows need an ISO 4217 unit: {sorted(u[m == 'value'].unique())[:5]}")
    if not u[m == "net_weight"].isin(WEIGHT_UNITS).all():
        raise ValidationError(f"net_weight rows need a unit in {sorted(WEIGHT_UNITS)}")

    mult = pd.to_numeric(df["unit_multiplier"], errors="coerce")
    if not mult.isin(MULTIPLIERS).all():
        raise ValidationError(f"unit_multiplier must be one of {sorted(MULTIPLIERS)}")
    vals = pd.to_numeric(df["value"], errors="coerce")
    if vals.isna().any():
        raise ValidationError(f"{int(vals.isna().sum())} non-numeric value(s)")
    neg = (vals < 0) & (df["tradeflow"] != "balance")
    if neg.any():
        raise ValidationError(f"{int(neg.sum())} negative value(s) outside the balance")
    if not (vals * mult).abs().lt(1e16).all():
        raise ValidationError(f"value(s) out of range: max {float((vals * mult).abs().max()):.3g}")

    # One observation per key. Exact repeats (a figure printed in two tables of
    # one file) are dropped; the same key with DIFFERENT values is a misread.
    full = vals * mult
    dupkey = df.duplicated(KEY, keep=False)
    if dupkey.any():
        k = df.loc[dupkey, KEY].astype(str).agg("|".join, axis=1)
        g = full[dupkey].groupby(k)
        spread = g.max() - g.min()
        tol = 0.5 * mult[dupkey].groupby(k).max() + 1e-9
        clash = spread > tol
        if clash.any():
            raise ValidationError(f"{int(clash.sum())} key(s) with conflicting values "
                                  f"(first: {clash[clash].index[0]})")
        df = df.loc[~df.duplicated(KEY)]
        full, mult = full.loc[df.index], mult.loc[df.index]

    _check_identities(df, full, mult)

    if descriptor:
        need = descriptor.get("expect_rows")
        if need and len(df) < need:
            raise ValidationError(f"{len(df)} rows, expected >= {need}")
        need = descriptor.get("expect_periods")
        if need and df["period"].nunique() < need:
            raise ValidationError(f"{df['period'].nunique()} periods, expected >= {need}")
    return df[TRADE_COLUMNS].copy()


# A printed figure: "4 163", "1 491 951", "202 673,1", "56,9", ",87".
_FIGURE = re.compile(r"(?<![\w.])(?:\d{1,3}(?:[  ]\d{3})+(?:,\d+)?|\d+,\d+|,\d+)(?![\w])")
# A trailing dash is an empty cell fused onto the label; a LEADING dash is the
# nomenclature's indent ("- - Effets personnels", "- Beurre") and is fine.
_PLACEHOLDER = re.compile(r"\s[-–](?:\s*[-–,])*\s*$")
_GLYPH = re.compile(r"\(cid:\d+\)")


def _check_labels(df: pd.DataFrame) -> None:
    """THE ROW-SPLIT GUARD. A label that swallowed table cells -- "Chine 1 491 951",
    "Angola - -", "Belgique BF Burkina Faso 202 673,1 ...", "CEPGL (cid:3)" -- means
    the row was split in the wrong place, and the values beside it are almost
    certainly shifted onto the wrong period. Partner labels may not contain a
    printed figure, a dash placeholder or an unmapped glyph; commodity labels
    (which may legitimately carry one number, "n'excédant pas 37,5 W") may not
    carry two figures, consist of a figure, end in a placeholder, or hold a glyph."""
    p = df["partner"].astype(str)
    bad = p[p.str.contains(_FIGURE) | p.str.contains(_PLACEHOLDER) | p.str.contains(_GLYPH)]
    if len(bad):
        raise ValidationError(f"{bad.nunique()} partner label(s) hold table cells -- the row split is wrong "
                              f"(first: {bad.iloc[0][:70]!r})")
    c = df["commodity"].astype(str)
    figures = c.str.count(_FIGURE.pattern)
    only = c.str.fullmatch(r"\s*[-–]?\s*" + _FIGURE.pattern + r"\s*")
    bad = c[(figures >= 2) | only | c.str.contains(_PLACEHOLDER) | c.str.contains(_GLYPH)]
    if len(bad):
        raise ValidationError(f"{bad.nunique()} commodity label(s) hold table cells -- the row split is wrong "
                              f"(first: {bad.iloc[0][:70]!r})")


# Flow identities: (result, terms, signs).
_IDENTITIES = (("balance", ("export", "import"), (1, -1)),
               ("total", ("export", "import"), (1, 1)),
               ("export", ("domestic_export", "re_export"), (1, 1)))


def _check_identities(df: pd.DataFrame, full: pd.Series, mult: pd.Series) -> None:
    """THE COLUMN-SWAP GUARD. Where one parse publishes the flows of an
    identity for the same commodity, partner, unit and period -- balance =
    exports - imports, total = exports + imports, exports = domestic exports +
    re-exports -- they must agree. A misread column (last year's exports read
    as this year's, imports filed under the wrong month) breaks it for most
    cells. Each printed figure is rounded to its multiplier, so a cell may miss
    by half a printed unit per term, plus 0.5 % for NSOs that round the parts
    and the total separately. Fails only when more than a quarter of >= 6
    comparable cells disagree. Exports FOB against imports CIF is the normal
    balance, so the price basis is not part of the match. It checks; it never
    fills or corrects a value."""
    # Within ONE source: a merged file mixes vintages (a balance from the 2011
    # abstract, exports revised in the 2025 one), and revisions are not misreads.
    key = ["commodity_classification", "commodity_code_nso", "commodity", "partner_type", "partner",
           "frequency", "period", "measure", "unit", "prices", "trade_system"]
    key += [c for c in ("source_file",) if c in df.columns]
    k = df[key].astype(str).agg("\x1f".join, axis=1)
    cell: dict = {}
    for a, fl, v, mu in zip(k, df["tradeflow"], full, mult):
        cell.setdefault(a, {})[fl] = (v, mu)
    n = bad = 0
    first = None
    for a, flows in cell.items():
        for res, terms, signs in _IDENTITIES:
            if res not in flows or not all(t in flows for t in terms):
                continue
            implied = sum(s * flows[t][0] for t, s in zip(terms, signs))
            got = flows[res][0]
            slack = 0.5 * sum(flows[t][1] for t in (res,) + terms) + 0.005 * max(abs(got), abs(implied))
            n += 1
            if abs(got - implied) > slack:
                bad += 1
                first = first or (res, a.replace("\x1f", " | "), got, implied)
    if n >= 6 and bad > n / 4:
        raise ValidationError(
            f"{bad}/{n} flow identities fail (first: {first}) -- a column or row was probably "
            f"read in the wrong place, or a balance's sign was lost")
