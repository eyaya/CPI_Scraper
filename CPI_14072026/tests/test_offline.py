"""Offline self-test for the CPI collector.

No network: it exercises the SHARED surfaces every parser depends on, replays a
published table through a real parser, and checks invariants across the 52
outputs already on disk.

    python -m indicators.cpi.tests.test_offline

WHY THIS SUITE IS SHAPED DIFFERENTLY FROM `labour` AND `unemployment`. Those
two read most countries through one declarative engine, so a fixture per trap
exercises rules shared by a dozen layouts. CPI has FIFTY-THREE BESPOKE PARSERS
and no shared engine -- each NSO's format got its own reader. Replaying 52
fixtures would test 52 things once each and still miss the parts that actually
bind the corpus together. So the leverage here is:

  * the one shared rule set every parser can reach -- `coicop.code_for_label`;
  * the validator, which is the only thing standing between a bad parse and an
    output file;
  * INVARIANTS ACROSS ALL 52 OUTPUTS, which cover every country at once;
  * one per-country replay, for a trap documented as having actually bitten.

Fixtures are VERBATIM from the retained source file, as everywhere in this
repo: a fixture written to match the parser tests nothing.
"""
from __future__ import annotations
import datetime as dt
import glob
import os
import re
import sys

import pandas as pd

from indicators.cpi import coicop, schema
from indicators.cpi.parsers import REGISTRY

FAILURES: list[str] = []

HERE = os.path.dirname(os.path.abspath(__file__))
CPI_DIR = os.path.dirname(HERE)
OUT_DIR = os.path.join(CPI_DIR, "out")
MERGE_KEYS = ["coicop_code", "geography", "period", "measure"]


def check(name: str, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


# ---------------------------------------------------------------------------
# the one shared rule set: COICOP label -> division code
# ---------------------------------------------------------------------------

def test_coicop_labels():
    """Every wording below is one an NSO in this corpus actually prints.

    A mis-mapped label is the quintessential silent defect here: it files
    Transport's inflation under Health with a perfectly valid code, in range,
    correctly typed, and wrong.
    """
    for label, want in [
        # all-items, in the many forms NSOs use for it
        ("All items", "00"), ("ALL ITEMS", "00"), ("All Groups", "00"),
        ("General Index", "00"), ("Overall index", "00"), ("Total", "00"),
        ("all products", "00"),
        # the twelve divisions
        ("Food and non-alcoholic beverages", "01"),
        ("Food and Non Alcoholic Beverages", "01"),
        ("Alcoholic beverages, tobacco and narcotics", "02"),
        ("Clothing and footwear", "03"),
        ("Housing, water, electricity, gas and other fuels", "04"),
        ("Furnishings, household equipment and routine household maintenance", "05"),
        ("Health", "06"), ("Transport", "07"),
        ("Information and communication", "08"),
        ("Recreation, sport and culture", "09"),
        ("Education services", "10"), ("Education", "10"),
        ("Restaurants and accommodation services", "11"),
        ("Insurance and financial services", "12"),
        ("Personal care, social protection and miscellaneous goods and services", "13"),
    ]:
        check(f"coicop {label!r}", coicop.code_for_label(label), want)

    # NOT divisions -- these must return None so a parser skips them rather
    # than filing an aggregate or a sub-item as a division.
    for label in ("Housing (rent)", "Food inflation", "Core inflation",
                  "Weights", "", "   ", "Bread & Cereals"):
        check(f"coicop non-division {label!r}", coicop.code_for_label(label), None)

    check("coicop table is 14 divisions", len(coicop.DIVISIONS), 14)
    check("coicop N_DIVISIONS", coicop.N_DIVISIONS, 14)


def test_core_inflation_is_a_known_sharp_edge():
    """A REGRESSION PIN, NOT AN ENDORSEMENT.

    `_LABEL_RULES` comments say `startswith` keeps "all items less food..."
    from matching -- but "00"'s predicate tests `s.startswith("all item")`,
    so it DOES match, and core inflation would be filed as the headline
    all-items series.

    That is latent, not live: only four parsers call `code_for_label` (Ghana,
    Kenya, South Sudan; Egypt deliberately maps its own wording), and no
    output in this corpus carries a "less"/"core"/"excl" label. But Kenya's
    release does publish a Core and Non-Core section, so the day a parser
    reads it, this fires. If the rule is tightened, CHANGE THIS TEST
    DELIBERATELY -- do not delete it.
    """
    check("core inflation currently collides with all-items",
          coicop.code_for_label("All items less food and energy"), "00")
    # And the corpus must stay clean of it, which is the property that matters.
    offenders = []
    for path in sorted(glob.glob(os.path.join(OUT_DIR, "*.csv"))):
        df = pd.read_csv(path, dtype=str, low_memory=False)
        bad = df[df["coicop_label"].astype(str)
                 .str.contains(r"\bless\b|core|excl", case=False, na=False)]
        if len(bad):
            offenders.append(os.path.basename(path))
    check("no core/less/excl label reached any output", offenders, [])


# ---------------------------------------------------------------------------
# the validator
# ---------------------------------------------------------------------------

def _frame(**over) -> pd.DataFrame:
    """A minimal valid CPI frame, which each test then breaks one way."""
    base = {
        "country": "Testland", "iso3": "TST", "indicator": "CPI",
        "coicop_code": "00", "coicop_label": "All items",
        "geography": "Total country", "period": "2026-08",
        "measure": "index", "value": 155.85, "unit": "Index",
        "base_period": "February 2019 = 100", "frequency": "monthly",
        "source_type": "pdf", "source_url": "https://example.invalid",
        "source_file": "replay.pdf",
        "extracted_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    base.update(over)
    return pd.DataFrame([base])


def _rejects(name: str, df: pd.DataFrame):
    try:
        schema.validate(df)
        FAILURES.append(f"validator accepted {name}")
    except Exception:
        pass


def test_validator_guards():
    # A frame that is fine must pass, or every rejection below proves nothing.
    try:
        schema.validate(_frame())
    except Exception as e:
        FAILURES.append(f"validator rejected a valid frame: {e}")

    _rejects("a malformed period '2026-13'", _frame(period="2026-13"))
    _rejects("a period without a month", _frame(period="2026"))
    _rejects("an unknown measure", _frame(measure="inflation_qoq"))
    _rejects("a non-numeric value", _frame(value="n/a"))
    _rejects("an index of 0", _frame(value=0.0))
    _rejects("an inflation rate of -250%",
             _frame(measure="inflation_yoy", value=-250.0, unit="percent"))

    # expect_divisions is the early warning that a parser silently dropped
    # divisions -- a 14-division report yielding 3 must fail, not ship.
    thin = pd.concat([_frame(coicop_code=c) for c in ("00", "01", "07")])
    try:
        schema.validate(thin, expect_divisions=14)
        FAILURES.append("validator accepted 3 divisions where 14 were expected")
    except Exception:
        pass


def test_index_ceiling_stays_wide_for_hyperinflation():
    """THE CEILING IS DELIBERATELY LOOSE AND MUST STAY SO.

    It exists to catch parse garbage (a weight column read as an index), not
    to cap reality: Sudan's CPI passes 630,000 on its 2007 = 100 base and is a
    real published figure. Anyone "tightening" this to a tidy 100,000 would
    reject a whole country's series.
    """
    try:
        schema.validate(_frame(value=630_000.0))
    except Exception as e:
        FAILURES.append(f"validator rejected Sudan-scale hyperinflation: {e}")
    # ... but genuine garbage is still refused.
    _rejects("an index of 50,000,000", _frame(value=50_000_000.0))


# ---------------------------------------------------------------------------
# invariants across every output already on disk
# ---------------------------------------------------------------------------

def test_corpus_invariants():
    """Fifty-two countries checked at once, which is the only tractable way to
    cover a corpus with fifty-three bespoke parsers."""
    files = sorted(glob.glob(os.path.join(OUT_DIR, "*.csv")))
    check("outputs present", len(files) > 0, True)

    dup_files, bad_code, bad_period, bad_measure, no_allitems = [], [], [], [], []
    for path in files:
        name = os.path.basename(path)[:-4]
        df = pd.read_csv(path, dtype=str, low_memory=False)

        # A DUPLICATE MERGE KEY IS A PARSER DEFECT. `_merge_with_existing`
        # merges ON this key but does not enforce uniqueness, so nothing else
        # would catch one figure written twice under one identity.
        if len(df[df.duplicated(MERGE_KEYS, keep=False)]):
            dup_files.append(name)

        # Codes are 2-digit divisions, optionally with sub-division detail:
        # Gambia legitimately publishes a chained series (01.1, 01.1.1 ...).
        if len(df.loc[~df["coicop_code"].astype(str)
                      .str.fullmatch(r"\d{2}(\.\d+)*")]):
            bad_code.append(name)

        if len(df.loc[~df["period"].astype(str)
                      .str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])")]):
            bad_period.append(name)

        if set(df["measure"].dropna()) - schema.MEASURES:
            bad_measure.append(name)

        # Every country publishes a headline all-items series; a country
        # without one has almost certainly lost its label mapping.
        if "00" not in set(df["coicop_code"].astype(str)):
            no_allitems.append(name)

    check("no duplicate merge keys", dup_files, [])
    check("no malformed coicop codes", bad_code, [])
    check("no malformed periods", bad_period, [])
    check("no unknown measures", bad_measure, [])
    check("every country has an all-items series", no_allitems, [])


def test_every_descriptor_has_a_parser():
    """The registry check, inline: a descriptor naming a parser that does not
    exist fails a whole run later, offline and instantly here."""
    import yaml
    problems = []
    for path in sorted(glob.glob(os.path.join(CPI_DIR, "sources", "*.yaml"))):
        with open(path, encoding="utf-8") as fh:
            d = yaml.safe_load(fh) or {}
        parser = d.get("parser")
        if parser not in REGISTRY:
            problems.append(f"{os.path.basename(path)} -> {parser!r}")
        elif not callable(REGISTRY[parser]):
            problems.append(f"{os.path.basename(path)} -> not callable")
    check("every descriptor's parser resolves", problems, [])


# ---------------------------------------------------------------------------
# one per-country replay: KNBS Kenya, Table 1
# ---------------------------------------------------------------------------
#
# VERBATIM from Kenya-Consumer-Price-Indices-and-Inflation-Rates-August-2026.pdf,
# page 5. The shape is <label> <weight> <month-on-month> <year-on-year>, and
# the WEIGHT COLUMN IS THE TRAP: 32.9094 is a basket weight, not a price
# change, and reading it as one would publish 32.9% food inflation.
KENYA_TABLE1 = """Table 1: One and Twelve-Month Percentage Changes in the Consumer Price Indices
% Change on same
% Change on
month of the
last month
13 COICOP Divisions Weight % previous year
(August 2026 /
August 2026
July 2026)
/August 2025)
Food and Non-Alcoholic Beverages 32.9094 0.6 9.0
Alcoholic Beverages, Tobacco and Narcotics 3.3289 0.1 2.6
Clothing and Footwear 2.9914 0.1 2.2
Housing, Water, Electricity, Gas and Other Fuels 14.6124 0.1 3.6
Furnishings, Household Equipment and Routine Household Maintenance 3.7372 0.3 2.9
Health 2.9116 0.1 2.8
Transport 9.6468 0.7 15.7
Information and Communication 7.7840 0.4 0.8
Recreation, Sport and Culture 1.7219 1.0 3.6
Education Services 5.5620 0.0 2.9
Restaurants and Accommodation Services 8.0991 0.2 3.0
Insurance and Financial Services 2.2423 0.4 1.2
Personal Care, Social Protection and Miscellaneous Goods and Services 4.4532 0.2 2.4
Total 100.0000 0.4 6.6
3
"""


class _StubPage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _StubPdf:
    def __init__(self, pages):
        self.pages = [_StubPage(p) for p in pages]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_kenya_knbs_table1():
    """Thirteen divisions plus Total, two measures each, and the weight column
    left where it belongs."""
    from indicators.cpi.parsers import kenya_knbs as K

    orig = K.pdfplumber.open
    K.pdfplumber.open = lambda _p: _StubPdf(["cover", KENYA_TABLE1])
    try:
        df = K.parse("Kenya-Consumer-Price-Indices-and-Inflation-Rates-August-2026.pdf")
    finally:
        K.pdfplumber.open = orig

    check("KE period from filename", sorted(set(df.period)), ["2026-08"])
    check("KE divisions", len(set(df.coicop_code)), 14)
    check("KE measures", sorted(set(df.measure)), ["inflation_mom", "inflation_yoy"])
    check("KE rows", len(df), 28)          # 14 divisions x 2 measures

    def val(code, measure):
        m = (df.coicop_code == code) & (df.measure == measure)
        return df.loc[m, "value"].tolist()

    check("KE all-items yoy", val("00", "inflation_yoy"), [6.6])
    check("KE all-items mom", val("00", "inflation_mom"), [0.4])
    check("KE food yoy", val("01", "inflation_yoy"), [9.0])
    check("KE transport yoy", val("07", "inflation_yoy"), [15.7])
    check("KE housing yoy", val("04", "inflation_yoy"), [3.6])
    check("KE education yoy", val("10", "inflation_yoy"), [2.9])

    # THE WEIGHT COLUMN MUST NOT HAVE BECOME A VALUE. 32.9094 is food's basket
    # weight; published as inflation it would read as 32.9 per cent.
    weights = {32.9094, 14.6124, 9.6468, 100.0000}
    check("KE no weight leaked into values",
          bool(weights & set(df.value.astype(float))), False)
    # Every value is a plausible monthly/annual rate, not a weight or an index.
    check("KE values are rates",
          bool(df.value.astype(float).between(-50, 100).all()), True)

    # And the frame the parser hands back validates once run.py's identity
    # columns are attached.
    full = df.copy()
    for col, v in (("country", "Kenya"), ("iso3", "KEN"), ("indicator", "CPI"),
                   ("source_type", "pdf"), ("source_url", "https://example.invalid"),
                   ("source_file", "replay.pdf"),
                   ("extracted_at", dt.datetime.now().isoformat(timespec="seconds"))):
        full[col] = v
    try:
        schema.validate(full, expect_divisions=14)
    except Exception as e:
        FAILURES.append(f"KE parsed frame failed validation: {e}")


def test_kenya_refuses_a_short_table():
    """The parser's own floor: fewer than 14 division rows must raise rather
    than ship a partial table."""
    from indicators.cpi.parsers import kenya_knbs as K
    short = "\n".join(KENYA_TABLE1.splitlines()[:7])
    orig = K.pdfplumber.open
    # The cover text is deliberately dateless in both Kenya tests: the period
    # comes from the FILENAME, and the cover-page regex is only a fallback.
    # Giving the stub a date here would imply that fallback is under test.
    K.pdfplumber.open = lambda _p: _StubPdf(["cover", short])
    try:
        K.parse("Kenya-CPI-August-2026.pdf")
        FAILURES.append("kenya parser shipped a table with fewer than 14 divisions")
    except ValueError:
        pass
    finally:
        K.pdfplumber.open = orig


def main() -> int:
    for fn in (test_coicop_labels, test_core_inflation_is_a_known_sharp_edge,
               test_validator_guards, test_index_ceiling_stays_wide_for_hyperinflation,
               test_corpus_invariants, test_every_descriptor_has_a_parser,
               test_kenya_knbs_table1, test_kenya_refuses_a_short_table):
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
