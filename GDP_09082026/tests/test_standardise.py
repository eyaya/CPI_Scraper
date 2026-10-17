"""Offline tests for GDP's standardised columns (indicators/gdp/standardise.py).

    py -3 -W ignore -m indicators.gdp.tests.test_standardise

Same house pattern as test_offline: no pytest, a FAILURES list, main() -> 0/1.

THE STRONGEST CHECK HERE IS THE COUNTRIES' OWN ARITHMETIC, not a list of
labels. A mapping is right when the codes it assigns add up the way national
accounts must: FCE + GCF + EXP - IMP = GDP (expenditure side) and
GVA + net taxes on products = GDP (production side). Both were measured over
the corpus before being asserted: 404 of 452 country-periods closed within 1%
on the expenditure side, and 17 countries closed (median) within 0.35% on the
production side. Two bugs were found that way and nowhere else -- Stats SA
repeats "Final consumption expenditure" for the total, households and
government (only series_code tells them apart), and "fbcf" contains "cf".

The label cases below are the traps met while building the rules, each one a
mapping that was once wrong or is ambiguous on purpose.
"""
from __future__ import annotations

import glob
import os
import sys

import pandas as pd

from indicators.gdp.schema import GDP_COLUMNS
from indicators.gdp.standardise import STD_COLUMNS, code_for_label, standardise

FAILURES: list[str] = []
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")

# Countries whose expenditure identity does NOT close, for a reason that is not
# the mapping. A NEW country failing is a mapping bug until shown otherwise.
KNOWN_IDENTITY_FAILURES = {
    # Published: ZamStats prints a statistical discrepancy; with it the gap is 0.
    "Zambia",
    # Published: NSO Malawi's table has GCF == GFCF exactly and no inventories
    # or discrepancy line, so it misses GDP by ~1.4% (2022: 11.80tn vs 11.63tn).
    "Malawi",
    # Published: CSO's table A2.1 prints "GDP by economic activity" (77,576)
    # AND "GDP by expenditure" (71,640) for 2022 with no discrepancy line; one
    # table, two GDP values, so the expenditure-side GDP gets no ID and the
    # official production GDP (A1.1) is preferred.
    "Eswatini",
}


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


def test_label_traps():
    cases = [
        # (label, approach, code) -- "" means deliberately NOT mapped
        ("Final consumption expenditure", "expenditure", "FCE"),
        ("1. Dépense de Consommation Finale", "expenditure", "FCE"),
        ("CF Ménages", "expenditure", "FCE_HH"),
        ("Consommation Finale des ISBLSM", "expenditure", "FCE_NPISH"),
        ("2. FBCF / publique", "expenditure", "GFCF_GOV"),      # "fbcf" contains "cf"
        ("FBCF: PRIVEE", "expenditure", "GFCF_PRIV"),
        ("Gross Fixed Capital Fomation", "expenditure", "GFCF"),  # NSO typo
        ("Gross Fixed Capital Formation, incl. valuables", "expenditure", ""),
        ("Acquisitions nettes en objets de valeur", "expenditure", "ACQ_VAL"),
        ("(-) Importations de Biens et Services", "expenditure", "IMP"),
        ("Exportations nettes", "expenditure", "NET_EXP"),
        ("Services (Exports)", "expenditure", "EXP_S"),
        ("GDP at market prices", "aggregate", "GDP"),
        ("PIB = (1) +(2) +(3)", "aggregate", "GDP"),
        ("GDP Constant Basic Price", "aggregate", "GVA"),        # basic prices = GVA, not GDP
        ("Production Intérieure Brute", "aggregate", ""),        # ONS Algeria: narrower than GDP
        ("VA aux coûts des facteurs", "aggregate", ""),          # factor cost, not basic prices
        ("Total des valeurs ajoutées marchandes", "production", ""),  # market GVA only
        ("Taxes on products", "aggregate", "TAX_PROD"),
        ("Taxes less subsidies on products", "production", "TAX_NET_PROD"),
        ("PIB/capita en US$", "aggregate", "GDP_PC"),
        ("Non-oil GDP", "aggregate", "GDP_NONOIL"),
        ("Informal GDP", "aggregate", ""),
        # same words, different concept by approach
        ("Construction", "production", "VA_F"),
        ("Construction", "expenditure", ""),
        ("Electricity, gas and water", "production", "VA_DE"),
        ("Electricity, gas and water", "income", ""),
        # ambiguous across offices: never guessed
        ("Agriculture", "production", ""),
        ("Government", "expenditure", ""),
        ("Households", "expenditure", ""),
        # sub-items are never promoted to their parent
        ("………dont extraction d'hydrocarbure", "production", ""),
        ("…Transports", "production", ""),
        ("Of which: Food", "production", ""),
        ("Change in stock, Crude Oil", "expenditure", ""),
        # numbering stripped before de-hyphenation
        ("a-Education", "production", "VA_P"),
        ("030 Construction", "production", "VA_F"),
        # Kenya's parser put two numbers in the label column
        ("(90,687) (111,574)", "production", ""),
    ]
    for label, approach, want in cases:
        check(f"code_for_label({label!r}, {approach})", code_for_label(label, approach), want)


def _rows(**cols) -> pd.DataFrame:
    n = max([len(v) for v in cols.values() if isinstance(v, list)] or [1])
    base = {c: "" for c in GDP_COLUMNS}
    base.update(country="Testland", iso3="TST", indicator="GDP", approach="expenditure",
                geography="National", period="2024", frequency="annual",
                price_basis="current", seasonal_adjustment="nsa", measure="level",
                value="1", unit="R million", source_file="f.xlsx")
    rows = []
    for i in range(n):
        r = dict(base)
        for k, v in cols.items():
            r[k] = v[i] if isinstance(v, list) else v
        rows.append(r)
    return pd.DataFrame(rows)


def test_repeated_label_needs_the_code():
    """Stats SA's three "Final consumption expenditure" rows: the series code
    decides; without an override the label alone must NOT be mapped."""
    sa = _rows(country="South_Africa", iso3="ZAF", category="Final consumption expenditure",
               category_group="Expenditure on GDP",
               series_code=["AN2010", "AN2011", "AN2012"], value=["6163", "4752", "1410"])
    check("ZA codes", standardise(sa)["category_code"].tolist(), ["FCE", "FCE_HH", "FCE_GOV"])
    other = sa.assign(country="Testland", iso3="TST")
    check("ambiguous repeat left blank", standardise(other)["category_code"].tolist(), ["", "", ""])
    same = other.assign(value="5")             # same value repeated = not ambiguous
    check("identical repeat still mapped", standardise(same)["category_code"].tolist(), ["FCE"] * 3)


def test_edition_ignores_compact_codes():
    df = _rows(category="GDP", approach="aggregate",
               series_code=["AN2012", "DGS Annuaire 2004-2008 V.1.1.3"],
               source_file="Report_2025.xlsx")
    check("edition", standardise(df)["edition"].tolist(), ["2025", "2008"])
    q = _rows(category="GDP", approach="aggregate", category_group="INS CNT note T3 2017")
    check("quarterly edition", standardise(q)["edition"].tolist(), ["2017-Q3"])


def test_currency_and_scale():
    df = _rows(category="GDP", approach="aggregate",
               iso3=["BEN", "CMR", "SLE", "GNQ", "STP"],
               unit=["XAF billion", "XAF billion", "SLL million (pre-2022 leone)",
                     "FCFA thousand million", "mil STD"])
    s = standardise(df)
    check("currency", s["currency"].tolist(), ["XOF", "XAF", "SLL", "XAF", "STD"])  # Benin is WAEMU
    check("multiplier", s["unit_multiplier"].tolist(),
          ["1000000000", "1000000000", "1000000", "1000000000", "1000"])


def test_price_concepts():
    df = _rows(category=["GDP", "GDP", "GDP", "GDP at 2019 constant price", "GDP"],
               approach="aggregate", price_basis="constant",
               base_period=["chained volume (reference 2015)", "previous year prices",
                            "2006/2007", "", ""])
    s = standardise(df)
    check("price_concept", s["price_concept"].tolist(),
          ["chained", "previous_year", "fixed_base", "fixed_base", "constant_unspecified"])
    check("base_year", s["base_year"].tolist(), ["2015", "", "2006", "2019", ""])


def test_import_sign():
    df = _rows(category="Imports of goods and services",
               measure=["level", "growth_yoy"], value=["-90", "-3"],
               unit=["R million", "percent"])
    check("value_std", standardise(df)["value_std"].tolist(), [90_000_000.0, -3.0])


def _corpus() -> pd.DataFrame:
    return pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, low_memory=False)
                      for f in glob.glob(os.path.join(OUT_DIR, "*.csv"))], ignore_index=True)


def test_corpus():
    d = _corpus()
    missing = [c for c in STD_COLUMNS if c not in d.columns]
    check("standardised columns present in out/ (run: py -3 -m tools.standardise gdp)", missing, [])
    if missing:
        return
    ids = d.loc[d["series_id"] != "", "series_id"]
    check("unsafe series_id", sorted(ids[~ids.str.match(r"^[A-Z][A-Z0-9_]*$")].unique())[:5], [])
    p = d[d["is_preferred"] == "True"]
    k = ["country", "series_id", "currency", "geography", "period"]
    check("one preferred row per observation", int(p.duplicated(k).sum()), 0)
    check("preferred rows all carry a series_id", int((p["series_id"] == "").sum()), 0)

    # the expenditure identity, on the preferred current-price levels
    p = p.assign(v=pd.to_numeric(p["value_std"]))
    lv = p[(p["measure"] == "level") & (p["price_concept"] == "current")]
    w = lv.pivot_table(index=["country", "currency", "period"], columns="category_code",
                       values="v", aggfunc="first").dropna(subset=["GDP", "FCE", "GCF", "EXP", "IMP"])
    gap = ((w["FCE"] + w["GCF"] + w["EXP"] - w["IMP"] - w["GDP"]) / w["GDP"]).abs()
    med = gap.groupby(level="country").median()
    failing = set(med[med > 0.01].index)
    check("NEW countries failing FCE+GCF+EXP-IMP=GDP", sorted(failing - KNOWN_IDENTITY_FAILURES), [])
    check("countries the identity tests (>= 15)", len(med) >= 15, True)


def test_published_columns_untouched():
    path = sorted(glob.glob(os.path.join(OUT_DIR, "*.csv")))[0]
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    s = standardise(d)
    same = d[GDP_COLUMNS].reset_index(drop=True).equals(s[GDP_COLUMNS].reset_index(drop=True))
    check(f"published columns unchanged ({os.path.basename(path)})", same, True)


def main() -> int:
    for fn in (test_label_traps, test_repeated_label_needs_the_code,
               test_edition_ignores_compact_codes, test_currency_and_scale,
               test_price_concepts, test_import_sign, test_corpus,
               test_published_columns_untouched):
        try:
            fn()
        except Exception as e:
            FAILURES.append(f"{fn.__name__} raised {type(e).__name__}: {e}")
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("all standardise checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
