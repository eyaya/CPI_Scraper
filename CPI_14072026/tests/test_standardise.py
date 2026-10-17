"""Offline tests for CPI's standardised columns (indicators/cpi/standardise.py).

    py -3 -W ignore -m indicators.cpi.tests.test_standardise

House pattern: no pytest, a FAILURES list, main() -> 0/1.

THE ARITHMETIC CHECK. Within one index series_id, 100*(I_t / I_t-12 - 1) must
reproduce the year-on-year inflation the same office publishes. If an ID ever
spliced two bases (or two COICOP versions), that fails at the splice. Measured
before asserting: 89.8% of 19,286 pairs across 26 countries agree within 0.2
points. Countries whose own publications disagree are named in KNOWN below.
"""
from __future__ import annotations

import glob
import os
import sys

import pandas as pd

from indicators.cpi.schema import COLUMNS
from indicators.cpi.standardise import STD_COLUMNS, standardise

FAILURES: list[str] = []
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")

KNOWN_YOY_MISMATCH = {
    # Published inconsistencies at a rebase, not ID errors: the office's YoY
    # rate for the rebase year does not follow from its own new-base index.
    "Cameroon",   # 2024 (2022 = 100 introduced): Jan-2024 index gives 5.1, note says 7.2
    "Comoros",    # 2018 (2011 = 100 series): Jan-2018 index gives 4.0, release says 7.7
}


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


def _rows(**cols) -> pd.DataFrame:
    n = max([len(v) for v in cols.values() if isinstance(v, list)] or [1])
    base = {c: "" for c in COLUMNS}
    base.update(country="Testland", iso3="TST", indicator="CPI", geography="National",
                period="2024-01", measure="index", value="100", unit="Index",
                frequency="monthly", coicop_code="00", coicop_label="All items")
    rows = []
    for i in range(n):
        r = dict(base)
        for k, v in cols.items():
            r[k] = v[i] if isinstance(v, list) else v
        rows.append(r)
    return pd.DataFrame(rows)


def test_division_12_splits_by_version():
    """Mali-style: code 12 is 'Biens et services divers' before the rebase and
    'Assurance et services financiers' after; never one series."""
    df = _rows(coicop_code=["12", "12", "13"], period=["2023-06", "2024-06", "2024-06"],
               coicop_label=["Biens et services divers", "Assurance et services financiers",
                             "Soins personnels, protection sociale et biens divers"],
               base_period=["2014 = 100", "2023 = 100", "2023 = 100"])
    s = standardise(df)
    check("versions", s["coicop_version"].tolist(), ["C1999", "C2018", "C2018"])
    check("ids", s["series_id"].tolist(),
          ["CPI_C1999_12_INDEX_B2014_M", "CPI_C2018_12_INDEX_B2023_M", "CPI_C2018_13_INDEX_B2023_M"])
    # 'Biens et services divers' in a month that also has division 13 is still 1999 (Mali 2024-01..05)
    df2 = _rows(coicop_code=["12", "13"], period="2024-02",
                coicop_label=["Biens et services divers", "Soins personnels, protection sociale et biens divers"])
    check("12 misc beside 13", standardise(df2)["coicop_version"].tolist(), ["C1999", "C2018"])


def test_08_09_follow_the_month():
    df = _rows(coicop_code=["08", "09", "08", "09", "13"],
               period=["2019-01", "2019-01", "2025-01", "2025-01", "2025-01"],
               coicop_label="x")
    check("08/09 versions", standardise(df)["coicop_version"].tolist(),
          ["C1999", "C1999", "C2018", "C2018", "C2018"])


def test_bases_never_share_an_id():
    df = _rows(base_period=["2009 = 100", "", "Dec 2005 = 100"], period=["2020-01", "2024-01", "2010-01"])
    check("index ids", standardise(df)["series_id"].tolist(),
          ["CPI_00_INDEX_B2009_M", "CPI_00_INDEX_BU_M", "CPI_00_INDEX_B2005_M"])
    rate = _rows(measure="inflation_yoy", unit="percent", base_period=["2009 = 100", ""])
    check("rates carry no base", standardise(rate)["series_id"].tolist(),
          ["CPI_00_INFLATION_YOY_M", "CPI_00_INFLATION_YOY_M"])


def _corpus() -> list[pd.DataFrame]:
    return [pd.read_csv(f, dtype=str, keep_default_na=False)
            for f in sorted(glob.glob(os.path.join(OUT_DIR, "*.csv")))]


def test_corpus():
    files = _corpus()
    d = pd.concat(files, ignore_index=True)
    missing = [c for c in STD_COLUMNS if c not in d.columns]
    check("standardised columns present (run: py -3 -m tools.standardise cpi)", missing, [])
    if missing:
        return
    ids = d.loc[d["series_id"] != "", "series_id"]
    check("unsafe series_id", sorted(ids[~ids.str.match(r"^[A-Z][A-Z0-9_]*$")].unique())[:5], [])
    p = d[d["is_preferred"] == "True"]
    check("one preferred per observation",
          int(p.duplicated(["country", "series_id", "geography", "period"]).sum()), 0)
    check("rows without a series_id", int((d["series_id"] == "").sum()), 0)

    # index-derived YoY vs published YoY, per country
    bad = {}
    for f in files:
        f = f.assign(v=pd.to_numeric(f["value"]))
        idx = f[f["measure"] == "index"].assign(t=lambda x: pd.PeriodIndex(x["period"], freq="M"))
        prev = idx.assign(t=idx["t"] + 12)[["series_id", "geography", "t", "v"]].rename(columns={"v": "v12"})
        m = idx.merge(prev, on=["series_id", "geography", "t"])
        yoy = f[f["measure"] == "inflation_yoy"][["coicop_code", "coicop_version", "geography", "period", "v"]]
        m = m.merge(yoy.rename(columns={"v": "pub"}), on=["coicop_code", "coicop_version", "geography", "period"])
        if len(m) >= 24:
            off = ((100 * (m["v"] / m["v12"] - 1) - m["pub"]).abs() > 1).mean()
            if off > 0.10:
                bad[f["country"].iloc[0]] = round(off, 3)
    check("NEW countries where index YoY != published YoY (>10% of months off by 1pp)",
          sorted(set(bad) - KNOWN_YOY_MISMATCH), [])


def test_published_columns_untouched():
    d = _corpus()[0]
    s = standardise(d)
    check("published columns unchanged",
          d[COLUMNS].reset_index(drop=True).equals(s[COLUMNS].reset_index(drop=True)), True)


def main() -> int:
    for fn in (test_division_12_splits_by_version, test_08_09_follow_the_month,
               test_bases_never_share_an_id, test_corpus, test_published_columns_untouched):
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
