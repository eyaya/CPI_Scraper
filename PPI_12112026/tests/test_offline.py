"""Offline tests for the PPI package.

    py -3 -W ignore -m indicators.ppi.tests.test_offline

House pattern: no pytest, a FAILURES list, main() -> 0/1.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

from core.schema_base import ValidationError
from indicators.ppi import schema
from indicators.ppi.parsers import REGISTRY
from indicators.ppi.standardise import standardise

FAILURES: list[str] = []
HERE = os.path.dirname(os.path.abspath(__file__))


def check(label, got, want):
    if got != want:
        FAILURES.append(f"{label}: got {got!r}, want {want!r}")


def _rows(n=24, freq="monthly", **kw):
    base = dict(country="X", iso3="XXX", indicator="PPI", index_name="IPPI", index_variant="output",
                industry="Ensemble", industry_code_nso="", frequency=freq, unit="index",
                base_period="2015=100", currency_basis="", ownership="", series_code="", source_type="pdf", source_url="u",
                source_file="f", extracted_at="t")
    base.update(kw)
    out, lvl = [], 100.0
    for i in range(n):
        y, m = 2020 + i // 12, i % 12 + 1
        lvl *= 1.01
        out.append(dict(base, period=f"{y}-{m:02d}", measure="index", value=round(lvl, 1)))
        if i >= 12:
            out.append(dict(base, period=f"{y}-{m:02d}", measure="inflation_yoy", unit="percent", base_period="",
                            value=round((1.01 ** 12 - 1) * 100, 1)))
    return pd.DataFrame(out)


def test_yoy_guard():
    good = _rows()
    schema.validate_ppi(good)
    # Simulate a misread column: the y/y change replaced by the m/m change.
    bad = good.copy()
    bad.loc[bad.measure == "inflation_yoy", "value"] = 1.0
    try:
        schema.validate_ppi(bad)
        FAILURES.append("yoy guard: m/m filed as y/y not caught")
    except ValidationError:
        pass


def test_periods_and_units():
    q = pd.DataFrame([dict(_rows(1).iloc[0], period="2024-Q3", frequency="quarterly")])
    schema.validate_ppi(q)
    for label, df in (("monthly period as quarter", q.assign(frequency="monthly")),
                      ("index carrying percent", q.assign(unit="percent")),
                      ("unknown variant", q.assign(index_variant="wholesale"))):
        try:
            schema.validate_ppi(df)
            FAILURES.append(f"{label}: not rejected")
        except ValidationError:
            pass


def test_standardise_ids():
    df = pd.concat([_rows(13),
                    _rows(13, index_variant="export", index_name="PPI exports"),
                    _rows(1, industry="Industries manufacturières").assign(measure="weight", unit="per_mille", value=612.0)],
                   ignore_index=True)
    st = standardise(df)
    ids = set(st.series_id)
    check("output total index id", "PPI_T_INDEX_B2015_M" in ids, True)
    check("export variant has its own id", "PPI_EXP_T_INDEX_B2015_M" in ids, True)
    check("change carries no base", "PPI_T_INFLATION_YOY_X_M" in ids, True)
    w = st[st.measure == "weight"].iloc[0]
    check("weight id", w.series_id, "PPI_C_WEIGHT_B2015_M")
    check("per mille on percent scale", float(w.value_std), 61.2)


def test_newest_source_preferred():
    old = _rows(13).assign(source_file="bulletin_2021-01.pdf")
    new = _rows(13).assign(source_file="bulletin_2021-06.pdf", extracted_at="a")   # extracted EARLIER
    new = pd.concat([new, _rows(18).iloc[-3:].assign(source_file="bulletin_2021-06.pdf", extracted_at="a")])
    st = standardise(pd.concat([new, old], ignore_index=True))
    jan = st[(st.period == "2020-01") & (st.measure == "index")]
    check("the newer bulletin's value is preferred", list(jan.source_file[jan.is_preferred]), ["bulletin_2021-06.pdf"])


def test_ghana_replay():
    p = os.path.join(os.path.dirname(HERE), "source_data", "Ghana", "ghana_ppi.json")
    df = REGISTRY["ghana_pxweb_ppi"](p)
    for c in schema.PPI_COLUMNS:
        if c not in df:
            df[c] = ""
    schema.validate_ppi(df)
    v = df[(df.industry == "All industries") & (df.measure == "index")].set_index("period")["value"]
    check("Ghana PPI 2006-09", float(v["2006-09"]), 14.1)


def main() -> int:
    for t in (test_yoy_guard, test_periods_and_units, test_standardise_ids,
              test_newest_source_preferred, test_ghana_replay):
        try:
            t()
        except Exception as e:  # noqa: BLE001
            FAILURES.append(f"{t.__name__}: {type(e).__name__}: {e}")
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("ppi offline tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
