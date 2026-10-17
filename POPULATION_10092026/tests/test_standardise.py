"""Offline tests for population's standardised columns.

    py -3 -W ignore -m indicators.population.tests.test_standardise

House pattern: no pytest, a FAILURES list, main() -> 0/1.

THE ARITHMETIC CHECK. For each country/series/sex/geography/year, the narrowest
non-overlapping age bands chained from 0 to an open-ended top band must sum to
the published all-ages total. That is what proves `age_code` read each label
correctly -- '0-4 anos', '80 ou mais anos', '-15 ans', 'Under 5' all have to
land on the right band for the sum to close. Measured before asserting: 99.6%
of 17,386 chains across 43 countries close within 0.5%.
"""
from __future__ import annotations

import glob
import os
import re
import sys

import pandas as pd

from core.standardise_base import age_code
from indicators.population.schema import POPULATION_COLUMNS
from indicators.population.standardise import STD_COLUMNS, standardise

FAILURES: list[str] = []
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


def test_age_labels():
    cases = {"0-4": "Y0T4", "05-09": "Y5T9", "15 à 24 ans": "Y15T24", "0 - 4 ans": "Y0T4",
             "65 ou mais anos": "Y_GE65", "80 ou mais    anos": "Y_GE80", "65 ans et plus": "Y_GE65",
             "75 and over": "Y_GE75", "60 & +": "Y_GE60", "90 et +": "Y_GE90", "100+": "Y_GE100",
             "Menos de 1 ano": "Y_LT1", "Under 5": "Y_LT5", "-15 ans": "Y_LT15", "<1": "Y_LT1",
             "18": "Y18", "5 anos": "Y5", "Total": "_T", "Not stated": "_U", "N.D.": "_U",
             "Youth (15-35)": "Y15T35", "Adult (36+)": "Y_GE36",
             # parser leakage stays blank -- never coerced into a band
             "35-3": "", "sexe Masculin Féminin Total 14-19": "", "Jovens": ""}
    for label, want in cases.items():
        check(f"age_code({label!r})", age_code(label), want)


def _rows(**cols) -> pd.DataFrame:
    n = max([len(v) for v in cols.values() if isinstance(v, list)] or [1])
    base = {c: "" for c in POPULATION_COLUMNS}
    base.update(country="Testland", iso3="TST", indicator="Population", series_type="census",
                sex="total", age_group="Total", geography="National", period="2020",
                frequency="annual", measure="count", value="1", unit="persons")
    return pd.DataFrame([{**base, **{k: (v[i] if isinstance(v, list) else v) for k, v in cols.items()}}
                         for i in range(n)])


def test_series_type_is_a_method_not_a_quantity():
    df = _rows(series_type=["projection", "census", "estimate"], value=["3", "1", "2"])
    s = standardise(df)
    check("one id for all three", s["series_id"].nunique(), 1)
    check("census preferred", s.loc[s["is_preferred"], "series_type"].tolist(), ["census"])


def test_thousands_scaled():
    s = standardise(_rows(unit="thousand_persons", value="12.5"))
    check("value_std", s["value_std"].tolist(), [12500.0])


def _band(code):
    for rx, f in ((r"Y(\d+)T(\d+)", lambda m: (int(m[1]), int(m[2]))),
                  (r"Y_GE(\d+)", lambda m: (int(m[1]), 999)),
                  (r"Y_LT(\d+)", lambda m: (0, int(m[1]) - 1)),
                  (r"Y(\d+)", lambda m: (int(m[1]), int(m[1])))):
        m = re.fullmatch(rx, code)
        if m:
            return f(m)
    return None


def test_corpus():
    d = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, low_memory=False)
                   for f in glob.glob(os.path.join(OUT_DIR, "*.csv"))], ignore_index=True)
    missing = [c for c in STD_COLUMNS if c not in d.columns]
    check("standardised columns present (run: py -3 -m tools.standardise population)", missing, [])
    if missing:
        return
    ids = d.loc[d["series_id"] != "", "series_id"]
    check("unsafe series_id", sorted(ids[~ids.str.match(r"^[A-Z][A-Z0-9_]*$")].unique())[:5], [])
    p = d[d["is_preferred"] == "True"]
    check("one preferred per observation",
          int(p.duplicated(["country", "series_id", "geography", "period"]).sum()), 0)
    # Only parser leakage may lack an id (South Sudan's truncated '35-3').
    check("age labels without an id", sorted(d.loc[d["series_id"] == "", "age_group"].unique()), ["35-3"])

    c = d[(d["measure"] == "count") & (d["series_id"] != "")].assign(v=lambda x: pd.to_numeric(x["value_std"]))
    c["b"] = c["age_code"].map(_band)
    errs = []
    for _, g in c.groupby(["country", "series_type", "sex", "geography", "period"]):
        tot = g[g["age_code"] == "_T"]
        bands = sorted(set(g["b"].dropna()))
        if tot.empty or not bands:
            continue
        chain, nxt = [], 0
        while True:
            cand = [b for b in bands if b[0] == nxt]
            if not cand:
                break
            chain.append(min(cand, key=lambda b: b[1]))
            if chain[-1][1] == 999:
                break
            nxt = chain[-1][1] + 1
        if chain and chain[-1][1] == 999:
            total = g[g["b"].isin(chain)].groupby("b")["v"].first().sum()
            errs.append(abs(total / tot["v"].iloc[0] - 1))
    share = sum(e <= 0.005 for e in errs) / len(errs) if errs else 0
    check("age chains summing to the total within 0.5% (>= 99%)", share >= 0.99, True)
    check("age chains tested (>= 10,000)", len(errs) >= 10000, True)


def test_published_columns_untouched():
    path = sorted(glob.glob(os.path.join(OUT_DIR, "*.csv")))[0]
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    s = standardise(d)
    check("published columns unchanged",
          d[POPULATION_COLUMNS].reset_index(drop=True).equals(s[POPULATION_COLUMNS].reset_index(drop=True)), True)


def main() -> int:
    for fn in (test_age_labels, test_series_type_is_a_method_not_a_quantity,
               test_thousands_scaled, test_corpus, test_published_columns_untouched):
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
