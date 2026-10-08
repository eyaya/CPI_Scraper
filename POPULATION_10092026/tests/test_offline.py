"""Offline self-test for the Population collector.

No network: it exercises the validator, the merge-key behaviour that keeps a
census and a projection apart, and invariants across the 36 outputs on disk --
including the one arithmetic identity this indicator actually publishes.

    python -m indicators.population.tests.test_offline

WHY THIS SUITE IS SHAPED AS IT IS. Like `cpi` and `gdp`, Population has
THIRTY-SIX BESPOKE PARSERS, no shared engine and no shared vocabulary module.
Unlike either, it publishes a CHECKABLE IDENTITY -- male + female = total --
which is what caught Djibouti's shifted columns, and it carries `series_type`
inside its merge key precisely so a census and a projection for the same year
and geography cannot overwrite one another.

So the legs are: the validator; the sex identity as a REGRESSION PIN; the
merge-key separation, proved on a constructed collision; and corpus invariants.

THREE THINGS MEASURED BEFORE BEING ASSERTED, each of which would have produced
a wrong test if assumed:

  * the identity holds 38,772 times and breaks TWICE, both legitimately -- a
    Kenya 2019 row whose AGE GROUP is "Not stated" (a residual category that
    cannot satisfy a three-way identity) and a Benin 2002 row carrying the
    band "80 et plus" in its geography column. Asserting the identity always
    holds would be asserting something the sources do not publish;
  * NO country currently carries two series_types, so the census/projection
    protection cannot be shown from the corpus -- it is constructed here;
  * `south_africa_population` has no "Total country" row at all (Stats SA's
    MYPE is provincial), so a blanket national-total rule would be wrong.
"""
from __future__ import annotations
import datetime as dt
import glob
import os
import sys

import pandas as pd

from indicators.population import schema
from indicators.population.parsers import REGISTRY

FAILURES: list[str] = []

HERE = os.path.dirname(os.path.abspath(__file__))
POP_DIR = os.path.dirname(HERE)
OUT_DIR = os.path.join(POP_DIR, "out")
MERGE_KEYS = ["series_type", "sex", "age_group", "geography", "period", "measure"]

# Published breaks in the sex identity, named so a NEW one is visible. Tuples
# are (file, series_type, age_group, geography, period) -- the pivot index
# order. Both are the source's own doing, not a parse error:
#
#   * KENYA 2019 carries an age_group of "Not stated", a residual category the
#     census publishes and which cannot satisfy a three-way identity;
#   * BENIN 2002 has the age band "80 et plus" sitting in the GEOGRAPHY column
#     rather than age_group. That is a quirk of INStaD's workbook as parsed,
#     recorded here as observed rather than normalised inside a test -- if it
#     is ever corrected in `instad_benin_population`, this pin should be
#     updated deliberately.
KNOWN_IDENTITY_BREAKS = {
    ("benin_population", "census", "Total", "80 et plus", "2002"),
    ("kenya_population", "census", "Not stated", "Total country", "2019"),
    # ONS Algeria Rétrospective 1962-2020, 2002 mid-year estimate ('000s):
    # the 80+ row prints 129 + 125 = 244. A published misprint, pinned in
    # ons_algeria_population.py and collected as printed.
    ("algeria_population", "estimate", "80 ans et plus", "Total country", "2002"),
}
# Stats SA's mid-year estimates are published by province only.
NO_NATIONAL_TOTAL = {"south_africa_population"}


def check(name: str, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


# ---------------------------------------------------------------------------
# the validator
# ---------------------------------------------------------------------------

def _frame(**over) -> pd.DataFrame:
    base = {
        "country": "Testland", "iso3": "TST", "indicator": "Population",
        "series_type": "census", "sex": "total", "age_group": "Total",
        "geography": "Total country", "period": "2022", "frequency": "annual",
        "measure": "count", "value": 1234567.0, "unit": "persons",
        "series_code": "T1", "source_type": "pdf",
        "source_url": "https://example.invalid", "source_file": "replay.pdf",
        "extracted_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    base.update(over)
    return pd.DataFrame([base])


def _rejects(name: str, df: pd.DataFrame):
    try:
        schema.validate_population(df)
        FAILURES.append(f"validator accepted {name}")
    except Exception:
        pass


def test_validator_guards():
    try:
        schema.validate_population(_frame())
    except Exception as e:
        FAILURES.append(f"validator rejected a valid frame: {e}")

    # PERIOD IS A BARE YEAR -- not a quarter (GDP) and not a month (CPI).
    _rejects("a quarterly period", _frame(period="2022-Q1"))
    _rejects("a monthly period", _frame(period="2022-03"))

    _rejects("an unknown series_type", _frame(series_type="forecast"))
    _rejects("an unknown measure", _frame(measure="urbanisation"))
    _rejects("an unknown sex", _frame(sex="both"))
    _rejects("a non-numeric value", _frame(value="n/a"))
    _rejects("a missing column", _frame().drop(columns=["series_type"]))

    # A HEAD COUNT CANNOT BE NEGATIVE, and cannot exceed the world.
    _rejects("a negative head count", _frame(value=-5.0))
    _rejects("a count of 6e9", _frame(value=6e9))

    # A count mis-tagged as a rate is the failure this bound exists for.
    _rejects("a median age of 1.2 million",
             _frame(measure="median_age", value=1.2e6, unit="years"))


def test_count_ceiling_clears_the_largest_real_figure():
    """The ceiling must clear Nigeria-scale national totals (~2.3e8) whether
    the NSO reports persons or thousands, while still flagging a mis-parse."""
    for name, v in (("a Nigeria-scale national total", 2.3e8),
                    ("a projection to 2050", 4.0e8)):
        try:
            schema.validate_population(_frame(value=v))
        except Exception as e:
            FAILURES.append(f"validator rejected {name}: {e}")


# ---------------------------------------------------------------------------
# what `series_type` in the merge key is FOR
# ---------------------------------------------------------------------------

def test_census_and_projection_do_not_collide():
    """A census and a projection can describe the SAME year and geography and
    mean different things. `series_type` is in the merge key so they coexist.

    No country in the corpus currently carries both, so this is constructed:
    two rows identical in every key field EXCEPT series_type must remain two
    rows after a merge-key dedupe, and would collapse to one if series_type
    were dropped from the key.
    """
    from indicators.population.pipeline import CONFIG
    check("series_type is in the merge key",
          "series_type" in CONFIG.merge_keys, True)

    pair = pd.concat([_frame(series_type="census", value=1000.0),
                      _frame(series_type="projection", value=1010.0)])
    check("census and projection are distinct rows",
          len(pair.drop_duplicates(MERGE_KEYS)), 2)
    # Drop series_type from the key and they collapse -- which is the bug the
    # key composition prevents.
    without = [k for k in MERGE_KEYS if k != "series_type"]
    check("without series_type they would collide",
          len(pair.drop_duplicates(without)), 1)


# ---------------------------------------------------------------------------
# corpus invariants, over all 36 outputs
# ---------------------------------------------------------------------------

def _outputs():
    for path in sorted(glob.glob(os.path.join(OUT_DIR, "*.csv"))):
        yield os.path.basename(path)[:-4], pd.read_csv(path, dtype=str,
                                                       low_memory=False)


def test_corpus_invariants():
    names, dups, bad_vocab, bad_period, empty, no_national = [], [], [], [], [], []
    for name, df in _outputs():
        names.append(name)
        if df.empty:
            empty.append(name)
            continue
        if len(df[df.duplicated(MERGE_KEYS, keep=False)]):
            dups.append(name)
        for col, allowed in (("measure", schema.POP_MEASURES),
                             ("series_type", schema.SERIES_TYPES),
                             ("sex", schema.SEXES)):
            if set(df[col].dropna().astype(str)) - allowed:
                bad_vocab.append((name, col))
        if not df["period"].astype(str).str.fullmatch(r"\d{4}").all():
            bad_period.append(name)
        if ("Total country" not in set(df["geography"].dropna().astype(str))
                and name not in NO_NATIONAL_TOTAL):
            no_national.append(name)

    check("outputs present", len(names) > 0, True)
    check("no empty outputs", empty, [])
    check("no duplicate merge keys", dups, [])
    check("no out-of-vocabulary values", bad_vocab, [])
    check("no malformed periods", bad_period, [])
    check("every country has a national total", no_national, [])


def test_sex_identity_holds():
    """MALE + FEMALE = TOTAL, the one arithmetic identity this indicator
    publishes -- and the check that caught Djibouti's shifted columns, where
    '(0)' and '*' markers moved every later value one column left.

    ITS BLIND SPOT IS WORTH STATING: the identity SURVIVES a column swap. INS
    Cameroun prints "Masculin Féminin" nationally and "Féminin Masculin"
    regionally, and male+female=total either way. Geometry, not arithmetic, is
    what catches that -- so this test is necessary and not sufficient.
    """
    breaks = []
    for name, df in _outputs():
        d = df[df["measure"] == "count"].copy()
        if d.empty:
            continue
        d["value"] = pd.to_numeric(d["value"], errors="coerce")
        piv = d.pivot_table(index=["series_type", "age_group", "geography", "period"],
                            columns="sex", values="value", aggfunc="sum")
        if not {"male", "female", "total"} <= set(piv.columns):
            continue
        piv = piv.dropna(subset=["male", "female", "total"])
        if piv.empty:
            continue
        diff = (piv["male"] + piv["female"] - piv["total"]).abs()
        # A tenth of a percent, plus one, absorbs published rounding.
        tol = piv["total"].abs() * 0.001 + 1
        for idx in piv.index[diff > tol]:
            breaks.append((name, *[str(x) for x in idx]))

    new = sorted(set(breaks) - KNOWN_IDENTITY_BREAKS)
    check("no NEW break in male+female=total", new, [])
    # And the known ones must still be there: if a parser stops emitting them,
    # this pin should be revisited deliberately rather than rotting.
    check("every known published break is still present",
          len(set(breaks) & KNOWN_IDENTITY_BREAKS), len(KNOWN_IDENTITY_BREAKS))


def test_overlapping_geographies_are_not_summable():
    """ETHIOPIA PUBLISHES A LEGACY REGION AND THE REGIONS CARVED OUT OF IT.

    SNNP REGION (22,922,998) is listed alongside its successors -- Central
    Ethiopia, Sidama, South West Ethiopia, Southern Ethiopia -- and zones are
    listed alongside their regions (Sidama Zone inside SIDAMA REGION). Summing
    every geography therefore DOUBLE COUNTS by tens of millions.

    Both rows are published, so both are kept; the defect would be a consumer
    summing them. This test states the hazard in code so it cannot be
    forgotten: the geography sum must EXCEED the published national total,
    which is the signature of overlap.
    """
    path = os.path.join(OUT_DIR, "ethiopia_population.csv")
    if not os.path.exists(path):
        return
    df = pd.read_csv(path, dtype=str, low_memory=False)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    sel = ((df.sex == "total") & (df.age_group == "Total") &
           (df.measure == "count"))
    nat = df[sel & (df.geography == "Total country")]["value"]
    subs = df[sel & (df.geography != "Total country")]

    check("Ethiopia publishes a national total", len(nat) >= 1, True)
    if not len(nat):
        return
    national = float(nat.iloc[0])
    check("Ethiopia national total", round(national), 111652998)

    # The legacy region and at least one successor both appear.
    geos = set(subs.geography.dropna())
    check("legacy SNNP region present", "SNNP REGION" in geos, True)
    check("a successor region present",
          any(g in geos for g in ("Central Ethiopia Region", "SIDAMA REGION",
                                  "South West Ethiopia Region")), True)

    # Summing everything overshoots -- the signature of overlapping units.
    check("summing all geographies double-counts",
          float(subs["value"].sum()) > national, True)


def test_every_descriptor_has_a_parser():
    import yaml
    problems = []
    for path in sorted(glob.glob(os.path.join(POP_DIR, "sources", "*.yaml"))):
        with open(path, encoding="utf-8") as fh:
            d = yaml.safe_load(fh) or {}
        parser = d.get("parser")
        if parser not in REGISTRY:
            problems.append(f"{os.path.basename(path)} -> {parser!r}")
        elif not callable(REGISTRY[parser]):
            problems.append(f"{os.path.basename(path)} -> not callable")
    check("every descriptor's parser resolves", problems, [])


def main() -> int:
    for fn in (test_validator_guards,
               test_count_ceiling_clears_the_largest_real_figure,
               test_census_and_projection_do_not_collide,
               test_corpus_invariants, test_sex_identity_holds,
               test_overlapping_geographies_are_not_summable,
               test_every_descriptor_has_a_parser):
        try:
            fn()
        except Exception as e:            # a crash is a failure too
            FAILURES.append(f"{fn.__name__} raised {type(e).__name__}: {e}")
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("all offline checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
