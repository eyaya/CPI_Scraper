"""Offline tests for Public Debt's standardised columns (../standardise.py).

    py -3 -W ignore -m indicators.public_debt.tests.test_standardise

House pattern: no pytest, a FAILURES list, main() -> 0/1.

THE STRONGEST CHECK IS THE PUBLISHERS' OWN ARITHMETIC. Measured on the corpus
(2026-10-15) before being asserted, within ONE source table (same series_code):
EXT + DOM = TOTAL closes (median gap 0.00%) in 29 of 30 countries; MULTILATERAL
+ BILATERAL + COMMERCIAL = EXT closes exactly in all 6 countries that print all
four; published EXT + DOM shares sum to 99-100. Two traps were found that way:
GSS Ghana's "Commercial external debt" excludes Eurobonds (printed separately
as "International capital market"), and an instrument rule once suffixed
creditor codes ("BILATERAL_EXT").
"""
from __future__ import annotations

import glob
import os
import sys

import pandas as pd

from indicators.public_debt.schema import DEBT_COLUMNS
from indicators.public_debt.standardise import (STD_COLUMNS, code_for_component,
                                                coverage_code, standardise)

FAILURES: list[str] = []
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")

KNOWN_TOTAL_FAILURES = {
    # Published: MINECOFIN's PPG total = CG external + GG domestic + SOE loans,
    # so EXT + DOM alone misses it by the SOE loans (~6%).
    "Rwanda",
}


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


def test_component_traps():
    cases = [
        ("Dette extérieure", "EXT"), ("Dívida Interna", "DOM"), ("Total public debt", "TOTAL"),
        ("Stock de la dette publique: Dette extérieure", "EXT"),
        ("Dette extérieure: Dette bilatérale", "BILATERAL"),
        ("Credores Multilaterais", "MULTILATERAL"),
        ("External: Bilateral - Paris Club", "BILAT_PARIS"),
        ("Non Paris Club countries", "BILAT_NONPARIS"),
        ("Commercial: Total debt stock", "COMMERCIAL"),          # container level
        ("Domestic: Treasury Bills", "TBILLS"),
        ("Domestic: Loans", "LOANS_DOM"), ("External: Loans", "LOANS_EXT"),
        ("Loans", ""),                                            # domestic or external?
        ("Arriérés: Dette extérieure", "ARREARS_EXT"),           # NOT plain external debt
        ("Net loan debt", "TOTAL_NET"),
        ("Disbursed external debt by creditor category: Bilateral debt", "BILATERAL"),
        ("1.Bilateral Creditors [Total]", "BILATERAL"),
        # never promoted: named creditor, holder, sub-item, variant, perimeter, maturity
        ("Bilatéraux: EXIM BANK CHINE", ""),
        ("Net Claims on Government - Bank of Sierra Leone: Treasury Bills", ""),
        ("Multilatérale: dont appuis budgétaires", ""),
        ("Dette extérieure: Encours hors arriérés", ""),
        ("External debt excluding Rand", ""),
        ("Total External Debt: FGN Only", ""),
        ("Domestic debt: Central government", ""),
        ("1. External Debt (a+b+c+d) [Guaranteed total]", ""),
        ("Curto Prazo (<= 1 ano)", ""),
        ("Total", ""), ("Grand Total", ""),
    ]
    for label, want in cases:
        check(f"code_for_component({label!r})", code_for_component(label), want)


def test_coverage():
    cases = [
        ("Central government debt", "CG"), ("Budgetary Central Government", "BCG"),
        ("General Government", "GG"), ("Public Sector", "PS"),
        ("Central government debt and government-guaranteed debt", "PPG"),
        ("Central government debt excluding State-Owned Enterprises / Special Purpose Vehicles debt (BoG definition)", "CG"),
        ("Central government debt including State-Owned Enterprises / Special Purpose Vehicles debt (BoG definition)", "PS"),
        ("Public debt (perimeter not stated by GSS)", ""),
        ("National debt: external debt public and private (split by borrower) + government domestic debt", ""),
        ("Central government loan guarantees", "GUAR"),
    ]
    for text, want in cases:
        check(f"coverage_code({text[:50]!r})", coverage_code(text), want)


def _rows(**cols) -> pd.DataFrame:
    n = max([len(v) for v in cols.values() if isinstance(v, list)] or [1])
    base = {c: "" for c in DEBT_COLUMNS}
    base.update(country="Testland", iso3="TST", indicator="Public_Debt", publisher="MoF",
                coverage="Central government debt", period="2025", frequency="annual",
                measure="stock", value="1", unit="USD million", series_code="T1",
                source_file="f.pdf")
    return pd.DataFrame([{**base, **{k: (v[i] if isinstance(v, list) else v)
                                     for k, v in cols.items()}} for i in range(n)])


def test_frame_rules():
    # the label's own perimeter beats the file's
    s = standardise(_rows(component=["Central government external debt", "Total public debt"],
                          coverage="Public and publicly guaranteed (PPG) debt"))
    check("label perimeter", s["coverage_code"].tolist(), ["CG", "PPG"])
    # Namibia dollar is not USD
    s = standardise(_rows(component="Total debt", iso3="NAM", unit="N$ million"))
    check("N$", (s["currency"][0], s["unit_multiplier"][0]), ("NAD", "1000000"))
    # stock (incl. arrears) vs encours: both printed -> stock not coded
    s = standardise(_rows(component=["Encours de la dette publique", "Stock de la dette publique"],
                          value=["100", "120"], series_code=["T2", "T3"]))
    check("stock vs encours", s["category_code"].tolist(), ["TOTAL", ""])
    # Ghana: commercial excludes the capital-market line printed beside it
    s = standardise(_rows(component=["Commercial external debt",
                                     "International capital market external debt"]))
    check("commercial beside ICM", s["category_code"].tolist(), ["", ""])
    # two labels, one table, same code, different values -> neither coded
    s = standardise(_rows(component=["Domestic debt", "Total Domestic Debt"], value=["5", "6"]))
    check("collision in one table", s["category_code"].tolist(), ["", ""])
    s = standardise(_rows(component=["Domestic debt", "Total Domestic Debt"], value=["5", "6"],
                          series_code=["T4", "T5"]))
    check("same code across tables is fine", s["category_code"].tolist(), ["DOM", "DOM"])
    # USD and local-currency stocks get different series_ids
    s = standardise(_rows(component="Total public debt", iso3="GHA", unit=["USD million", "GHC billion"]))
    check("currency class in series_id", s["series_id"].tolist(),
          ["DEBT_TOTAL_CG_STOCK_USD_A", "DEBT_TOTAL_CG_STOCK_LCU_A"])
    check("value_std", s["value_std"].tolist(), [1e6, 1e9])


def _corpus() -> pd.DataFrame:
    return pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, low_memory=False)
                      for f in glob.glob(os.path.join(OUT_DIR, "*.csv"))], ignore_index=True)


def test_corpus():
    d = _corpus()
    missing = [c for c in STD_COLUMNS if c not in d.columns]
    check("standardised columns in out/ (run: py -3 -m tools.standardise public_debt)", missing, [])
    if missing:
        return
    ids = d.loc[d["series_id"] != "", "series_id"]
    check("unsafe series_id", sorted(ids[~ids.str.match(r"^[A-Z][A-Z0-9_]*$")].unique())[:5], [])
    p = d[d["is_preferred"] == "True"]
    check("one preferred row per observation",
          int(p.duplicated(["country", "series_id", "currency", "period"]).sum()), 0)

    d = d.assign(v=pd.to_numeric(d["value_std"], errors="coerce"))
    st = d[(d["measure"] == "stock") & (d["category_code"] != "")]
    w = st.pivot_table(index=["country", "coverage", "series_code", "period", "unit"],
                       columns="category_code", values="v", aggfunc="first")
    x = w.dropna(subset=["TOTAL", "EXT", "DOM"])
    gap = ((x["EXT"] + x["DOM"] - x["TOTAL"]) / x["TOTAL"]).abs().groupby(level="country").median()
    check("NEW countries failing EXT+DOM=TOTAL", sorted(set(gap[gap > 0.01].index) - KNOWN_TOTAL_FAILURES), [])
    check("countries EXT+DOM=TOTAL tests (>= 25)", len(gap) >= 25, True)
    y = w.dropna(subset=["EXT", "MULTILATERAL", "BILATERAL", "COMMERCIAL"])
    g2 = ((y["MULTILATERAL"] + y["BILATERAL"] + y["COMMERCIAL"] - y["EXT"]) / y["EXT"]).abs()
    g2 = g2.groupby(level="country").median()
    check("countries failing MULTI+BILAT+COMM=EXT", sorted(g2[g2 > 0.01].index), [])
    sh = d[(d["measure"] == "share") & d["category_code"].isin(["EXT", "DOM"])].pivot_table(
        index=["country", "coverage", "series_code", "period"], columns="category_code",
        values="v", aggfunc="first").dropna()
    tot = sh["EXT"] + sh["DOM"]
    check("EXT+DOM shares outside 98.5-101.5", int(((tot < 98.5) | (tot > 101.5)).sum()), 0)


def test_published_columns_untouched():
    path = sorted(glob.glob(os.path.join(OUT_DIR, "*.csv")))[0]
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    s = standardise(d)
    check(f"published columns unchanged ({os.path.basename(path)})",
          d[DEBT_COLUMNS].reset_index(drop=True).equals(s[DEBT_COLUMNS].reset_index(drop=True)), True)


def main() -> int:
    for fn in (test_component_traps, test_coverage, test_frame_rules, test_corpus,
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
