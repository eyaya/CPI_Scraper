"""Offline tests for MPI's standardised columns.

    py -3 -W ignore -m indicators.mpi.tests.test_standardise

House pattern: no pytest, a FAILURES list, main() -> 0/1.

THE ARITHMETIC CHECK: M0 = H x A. Within one series family (same measure,
breakdown, place and year) the published adjusted headcount ratio must equal
incidence x intensity. It proves the breakdown codes group the right rows and
that value_std put M0 on one scale (INS Guinea prints it x100). Measured before
asserting: all 957 triples in 16 countries close within 0.051 (Ghana prints H
and A to one decimal; everyone else within 0.005).
"""
from __future__ import annotations

import glob
import os
import sys

import pandas as pd

from indicators.mpi.schema import MPI_COLUMNS
from indicators.mpi.standardise import STD_COLUMNS, standardise

FAILURES: list[str] = []
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


def _rows(**cols) -> pd.DataFrame:
    n = max([len(v) for v in cols.values() if isinstance(v, list)] or [1])
    base = {c: "" for c in MPI_COLUMNS}
    base.update(country="Testland", iso3="TST", indicator="MPI", mpi_type="national",
                measure_name="Testland MPI", metric="incidence_H", topic="total",
                characteristic="Total", mpi_indicator="Total", sex="total", age_group="Total",
                geography="National", locality="all", period="2020", value="50", unit="percent")
    return pd.DataFrame([{**base, **{k: (v[i] if isinstance(v, list) else v) for k, v in cols.items()}}
                         for i in range(n)])


def test_measures_never_share_an_id():
    s = standardise(_rows(country=["Ghana", "Nigeria"], measure_name=["Ghana MPI (PHC 2021)", "Nigeria MPI"]))
    check("national designs separate", s["series_id"].tolist(),
          ["MPI_GHANA_MPI_PHC_2021_INCIDENCE_H_T_T", "MPI_NIGERIA_MPI_INCIDENCE_H_T_T"])


def test_breakdowns():
    s = standardise(_rows(topic=["sex_of_head", "sex_of_head", "quintile", "locality", "locality",
                                 "age", "education", "contributor"],
                          characteristic=["Chefe mulher", "Masculin", "Quintile 3", "Urbain", "Coastal zone",
                                          "0 - 4 ans", "Secondary", "Cooking fuel"],
                          locality=["all", "all", "all", "urban", "other", "all", "all", "all"]))
    check("breakdown_code", s["breakdown_code"].tolist(),
          ["HEAD_F", "HEAD_M", "Q3", "LOC_U", "", "AGE_Y0T4", "", "IND_COOKING_FUEL"])


def test_m0_scale():
    s = standardise(_rows(metric=["index_M0", "index_M0"], unit=["percent", "index"], value=["37.5", "0.375"]))
    check("M0 on one scale", s["value_std"].tolist(), [0.375, 0.375])
    check("M0 unit_std", s["unit_std"].tolist(), ["index", "index"])


def test_corpus():
    d = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False)
                   for f in glob.glob(os.path.join(OUT_DIR, "*.csv"))], ignore_index=True)
    missing = [c for c in STD_COLUMNS if c not in d.columns]
    check("standardised columns present (run: py -3 -m tools.standardise mpi)", missing, [])
    if missing:
        return
    ids = d.loc[d["series_id"] != "", "series_id"]
    check("unsafe series_id", sorted(ids[~ids.str.match(r"^[A-Z][A-Z0-9_]*$")].unique())[:5], [])
    key = ["country", "series_id", "geography", "locality_label", "period"]
    p = d[d["is_preferred"] == "True"]
    check("one preferred per observation", int(p.duplicated(key).sum()), 0)
    w = d[d["metric"].isin(["incidence_H", "intensity_A", "index_M0"]) & (d["series_id"] != "")]
    w = w.assign(fam=w["series_id"].str.replace(r"_(INCIDENCE_H|INTENSITY_A|INDEX_M0)_", "_", regex=True),
                 v=pd.to_numeric(w["value_std"]))
    t = w.pivot_table(index=["country", "fam", "geography", "locality_label", "period"],
                      columns="metric", values="v", aggfunc="first").dropna()
    err = (t["index_M0"] - t["incidence_H"] * t["intensity_A"] / 10000).abs()
    check("M0 = H x A triples tested (>= 900)", len(t) >= 900, True)
    check("triples off by more than 0.06", int((err > 0.06).sum()), 0)


def test_published_columns_untouched():
    path = sorted(glob.glob(os.path.join(OUT_DIR, "*.csv")))[0]
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    s = standardise(d)
    check("published columns unchanged",
          d[MPI_COLUMNS].reset_index(drop=True).equals(s[MPI_COLUMNS].reset_index(drop=True)), True)


def main() -> int:
    for fn in (test_measures_never_share_an_id, test_breakdowns, test_m0_scale, test_corpus,
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
