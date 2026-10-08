"""Offline self-test for the GDP collector.

No network: it exercises the validator, the cross-field rules that make a GDP
row interpretable, invariants across the 38 outputs already on disk, and one
per-country replay of the trickiest published convention in the set.

    python -m indicators.gdp.tests.test_offline

WHY THIS SUITE IS SHAPED AS IT IS. `labour` and `unemployment` read most
countries through one declarative engine, so a fixture per trap covers a dozen
layouts. GDP, like CPI, has THIRTY-EIGHT BESPOKE PARSERS and no shared engine --
and unlike CPI it has no shared vocabulary module either (there is no `coicop.py`
analogue to test). What it has instead is an unusually rich SCHEMA: four
controlled vocabularies kept deliberately ORTHOGONAL, so that a constant-price
growth rate is unambiguous. That orthogonality is the thing worth pinning, and
it is checkable as a rule across every country at once.

So the legs are:

  * the validator, the only thing between a bad parse and an output file;
  * CROSS-FIELD CONSISTENCY -- measure/unit/price_basis/frequency agreeing --
    measured across all 38 outputs before being asserted here;
  * corpus invariants (period form, vocabulary membership, an aggregate series
    per country);
  * ONE per-country replay: Egypt CBE's fiscal-to-calendar quarter mapping.

Every expectation below was measured against the real corpus first. Two facts
that shaped it, both of which would have produced wrong assertions if assumed:
`growth_period` is declared in the schema but used by NO country, and GDP
set NO `merge_keys` until 2026-10-01 -- it now merges on write (see
`test_gdp_merge_keys_are_unique`).
"""
from __future__ import annotations
import datetime as dt
import glob
import os
import sys

import pandas as pd

from indicators.gdp import schema
from indicators.gdp.parsers import REGISTRY

FAILURES: list[str] = []

HERE = os.path.dirname(os.path.abspath(__file__))
GDP_DIR = os.path.dirname(HERE)
OUT_DIR = os.path.join(GDP_DIR, "out")


def check(name: str, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


# ---------------------------------------------------------------------------
# the validator
# ---------------------------------------------------------------------------

def _frame(**over) -> pd.DataFrame:
    """A minimal valid GDP row, which each test then breaks one way."""
    base = {
        "country": "Testland", "iso3": "TST", "indicator": "GDP",
        "approach": "production", "category": "Agriculture",
        "category_group": "Value added by activity", "series_code": "T01",
        "geography": "Total country", "period": "2026-Q1",
        "frequency": "quarterly", "price_basis": "constant",
        "seasonal_adjustment": "nsa", "measure": "level",
        "value": 123456.0, "unit": "TST million",
        "base_period": "Constant 2015 prices", "source_type": "excel",
        "source_url": "https://example.invalid", "source_file": "replay.xlsx",
        "extracted_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    base.update(over)
    return pd.DataFrame([base])


def _rejects(name: str, df: pd.DataFrame):
    try:
        schema.validate_gdp(df)
        FAILURES.append(f"validator accepted {name}")
    except Exception:
        pass


def test_validator_guards():
    try:
        schema.validate_gdp(_frame())
    except Exception as e:
        FAILURES.append(f"validator rejected a valid frame: {e}")

    # PERIOD IS YYYY OR YYYY-Qn -- never a month, which is the CPI shape.
    _rejects("a monthly period", _frame(period="2026-03"))
    _rejects("a 5th quarter", _frame(period="2026-Q5"))
    _rejects("a bare quarter", _frame(period="Q1 2026"))

    # THE FOUR VOCABULARIES.
    _rejects("an unknown measure", _frame(measure="growth_mom"))
    _rejects("an unknown approach", _frame(approach="output"))
    _rejects("an unknown price basis", _frame(price_basis="real"))
    _rejects("an unknown seasonal flag", _frame(seasonal_adjustment="sa"))

    _rejects("a non-numeric value", _frame(value="n/a"))
    _rejects("a missing column", _frame().drop(columns=["price_basis"]))


def test_bounds_stay_loose_on_purpose():
    """BOTH MAGNITUDE BOUNDS ARE DELIBERATELY WIDE, and tightening either one
    would reject real published figures.

    Levels: currencies reported UNSCALED reach 2e14 (Nigeria, NGN), so the
    bound only has to catch a wrong-cell parse. Growth: a signed series
    crossing zero, or a sector growing off a near-zero base (Ghana oil in 2011
    was about +7000% YoY), legitimately exceeds +/-100%.
    """
    for name, kw in (
        ("an unscaled NGN level (2e14)", dict(value=2e14)),
        ("a large negative level (net exports)", dict(value=-5e11)),
        ("Ghana-oil-scale growth (+7000%)",
         dict(measure="growth_yoy", value=7000.0, unit="percent")),
        ("a negative growth rate", dict(measure="growth_yoy", value=-38.4,
                                        unit="percent")),
    ):
        try:
            schema.validate_gdp(_frame(**kw))
        except Exception as e:
            FAILURES.append(f"validator rejected {name}: {e}")

    # ... but genuine garbage is still refused.
    _rejects("a level of 1e17 (a concatenated number)", _frame(value=1e17))
    _rejects("a growth rate of 5e6", _frame(measure="growth_yoy", value=5e6,
                                            unit="percent"))


# ---------------------------------------------------------------------------
# cross-field rules + corpus invariants, over all 38 outputs
# ---------------------------------------------------------------------------

def _outputs():
    for path in sorted(glob.glob(os.path.join(OUT_DIR, "*.csv"))):
        yield os.path.basename(path)[:-4], pd.read_csv(path, dtype=str,
                                                       low_memory=False)


def test_cross_field_consistency():
    """WHAT MAKES A GDP ROW INTERPRETABLE IS THE COMBINATION, not any one
    column. These rules hold across all 38 outputs today; each was measured
    before being written down.

    A row that breaks one of these is not malformed in any way a validator
    sees -- it is a number whose meaning has quietly changed.
    """
    bad_growth, bad_defl, bad_contrib, bad_share, bad_qtr, bad_ann = \
        [], [], [], [], [], []

    for name, df in _outputs():
        m, u = df["measure"].astype(str), df["unit"].astype(str)
        basis = df["price_basis"].astype(str)

        g = m.str.startswith("growth")
        if len(u[g]) and set(u[g]) != {"percent"}:
            bad_growth.append((name, sorted(set(u[g]))[:3]))
        if len(u[m == "deflator"]) and (
                set(u[m == "deflator"]) != {"index"}
                or set(basis[m == "deflator"]) != {"not_applicable"}):
            bad_defl.append(name)
        if len(u[m == "contribution"]) and set(u[m == "contribution"]) != {"percentage points"}:
            bad_contrib.append((name, sorted(set(u[m == "contribution"]))[:3]))
        if len(u[m == "share"]) and set(u[m == "share"]) != {"percent"}:
            bad_share.append((name, sorted(set(u[m == "share"]))[:3]))

        # FREQUENCY AND PERIOD MUST AGREE. A quarterly row dated "2026" is
        # well-formed and wrong -- it silently becomes an annual observation.
        p = df["period"].astype(str)
        q = p[df["frequency"] == "quarterly"]
        if len(q) and not q.str.fullmatch(r"\d{4}-Q[1-4]").all():
            bad_qtr.append(name)
        a = p[df["frequency"] == "annual"]
        if len(a) and not a.str.fullmatch(r"\d{4}").all():
            bad_ann.append(name)

    check("growth is always percent", bad_growth, [])
    check("deflator is an index on no price basis", bad_defl, [])
    check("contribution is percentage points", bad_contrib, [])
    check("share is percent", bad_share, [])
    check("quarterly rows carry YYYY-Qn", bad_qtr, [])
    check("annual rows carry YYYY", bad_ann, [])


def test_corpus_invariants():
    """Thirty-eight countries checked at once -- the only tractable coverage
    for a corpus with thirty-eight bespoke parsers."""
    names = []
    bad_vocab, bad_period, no_aggregate, empty = [], [], [], []

    for name, df in _outputs():
        names.append(name)
        if df.empty:
            empty.append(name)
            continue
        for col, allowed in (("measure", schema.GDP_MEASURES),
                             ("approach", schema.APPROACHES),
                             ("price_basis", schema.PRICE_BASIS),
                             ("seasonal_adjustment", schema.SEASONAL)):
            if set(df[col].dropna().astype(str)) - allowed:
                bad_vocab.append((name, col))
        p = df["period"].astype(str)
        if not (p.str.fullmatch(r"\d{4}") | p.str.fullmatch(r"\d{4}-Q[1-4]")).all():
            bad_period.append(name)
        # Every NSO publishes a headline GDP series; a country without one has
        # almost certainly lost its aggregate classification rule.
        if "aggregate" not in set(df["approach"].dropna().astype(str)):
            no_aggregate.append(name)

    check("outputs present", len(names) > 0, True)
    check("no empty outputs", empty, [])
    check("no out-of-vocabulary values", bad_vocab, [])
    check("no malformed periods", bad_period, [])
    check("every country has an aggregate series", no_aggregate, [])


def test_gdp_merge_keys_are_unique():
    """GDP MERGES ON WRITE (since 2026-10-01), so its key must be unique.

    It used to overwrite each run -- defensible while every source republished
    its whole series, and pinned here as a fact. Then INS Tunisie's pages (a
    rolling 8 quarters / 6 years) and HCP Morocco's quarterly notes (each
    replacing the last) arrived, and overwriting would have thrown away every
    period that scrolled off: the configuration that once cost CPI 258 Kenyan
    periods. So `merge_keys` is now set, and what has to hold instead is the
    property `cpi` asserts: a DUPLICATE MERGE KEY IS A PARSER DEFECT, because
    `_merge_with_existing` merges on the key without enforcing uniqueness and
    one of two rows sharing it would silently vanish.
    """
    import pandas as pd
    from indicators.gdp.pipeline import CONFIG
    keys = list(getattr(CONFIG, "merge_keys", None) or [])
    check("gdp pipeline declares merge keys", bool(keys), True)
    dup_files = []
    for path in sorted(glob.glob(os.path.join(GDP_DIR, "out", "*_gdp.csv"))):
        df = pd.read_csv(path, dtype=str, keep_default_na=False,
                         na_values=[""], low_memory=False)
        n = int(df.duplicated(keys).sum())
        if n:
            dup_files.append(f"{os.path.basename(path)}: {n}")
    check("no duplicate GDP merge keys", dup_files, [])


def test_every_descriptor_has_a_parser():
    """A descriptor naming a parser that does not exist fails a whole run
    later; offline and instantly here."""
    import yaml
    problems = []
    for path in sorted(glob.glob(os.path.join(GDP_DIR, "sources", "*.yaml"))):
        with open(path, encoding="utf-8") as fh:
            d = yaml.safe_load(fh) or {}
        parser = d.get("parser")
        if parser not in REGISTRY:
            problems.append(f"{os.path.basename(path)} -> {parser!r}")
        elif not callable(REGISTRY[parser]):
            problems.append(f"{os.path.basename(path)} -> not callable")
    check("every descriptor's parser resolves", problems, [])


# ---------------------------------------------------------------------------
# one per-country replay: CBE Egypt's fiscal-to-calendar quarters
# ---------------------------------------------------------------------------
#
# Egypt's fiscal year runs July-June, and each workbook sheet is one fiscal
# year holding four fiscal quarters. The mapping is a faithful RELABEL of the
# same three months -- FY Q1 = Jul-Sep, Q2 = Oct-Dec, Q3 = Jan-Mar, Q4 =
# Apr-Jun -- so fiscal 2022/2023 Q1 is calendar 2022-Q3 and its Q3 is calendar
# 2023-Q1, a YEAR LATER. An off-by-one here produces periods that are
# perfectly well-formed and one to two quarters wrong, which no validator and
# no range check could ever see.


class _StubSheet:
    def __init__(self, grid):
        self._grid = grid

    def iter_rows(self, values_only=True):
        return iter(self._grid)


class _StubWorkbook:
    def __init__(self, sheets):
        self._sheets = sheets
        self.sheetnames = list(sheets)

    def __getitem__(self, name):
        return _StubSheet(self._sheets[name])

    def close(self):
        pass


# The factor-cost layout: a Q1..Q4 header row, then Public/Private/Total per
# quarter, then one row per sector. Values are chosen so each quarter is
# identifiable on sight.
_EGYPT_GRID = [
    ["GDP at factor cost at 2006/2007 prices", None, None, None, None,
     None, None, None, None, None, None, None, None],
    [None, "Q1", None, None, "Q2", None, None, "Q3", None, None, "Q4", None, None],
    [None, "Public", "Private", "Total", "Public", "Private", "Total",
     "Public", "Private", "Total", "Public", "Private", "Total"],
    ["Agriculture", 10, 20, 111.0, 10, 20, 222.0, 10, 20, 333.0, 10, 20, 444.0],
    ["Manufacturing", 10, 20, 555.0, 10, 20, 666.0, 10, 20, 777.0, 10, 20, 888.0],
    ["Gross Domestic Product", 10, 20, 1000.0, 10, 20, 2000.0, 10, 20, 3000.0,
     10, 20, 4000.0],
]


def test_egypt_fiscal_to_calendar_quarters():
    from indicators.gdp.parsers import egypt_cbe_gdp as E

    orig = E.openpyxl.load_workbook
    E.openpyxl.load_workbook = lambda *_a, **_k: _StubWorkbook(
        {"2022/2023": _EGYPT_GRID})
    try:
        df = E.parse("CBE_GDP_factorcost_constant.xlsx")
    finally:
        E.openpyxl.load_workbook = orig

    # FY 2022/2023: Q1->2022-Q3, Q2->2022-Q4, Q3->2023-Q1, Q4->2023-Q2.
    check("EG periods", sorted(set(df.period)),
          ["2022-Q3", "2022-Q4", "2023-Q1", "2023-Q2"])

    def val(cat, period):
        m = (df.category == cat) & (df.period == period)
        return df.loc[m, "value"].tolist()

    check("EG agriculture FY-Q1 -> 2022-Q3", val("Agriculture", "2022-Q3"), [111.0])
    check("EG agriculture FY-Q2 -> 2022-Q4", val("Agriculture", "2022-Q4"), [222.0])
    # THE YEAR ROLLS OVER HERE. FY Q3 is January-March of the NEXT calendar
    # year; reading it as 2022-Q1 would be an entire year out.
    check("EG agriculture FY-Q3 -> 2023-Q1", val("Agriculture", "2023-Q1"), [333.0])
    check("EG agriculture FY-Q4 -> 2023-Q2", val("Agriculture", "2023-Q2"), [444.0])

    # THE TOTAL COLUMN IS THE ONE READ. Public (10) and Private (20) must not
    # have been taken for the quarter's value.
    check("EG public/private not read",
          bool({10.0, 20.0} & set(df.value.astype(float))), False)

    # The GDP row is reclassified as the AGGREGATE approach, not production.
    agg = df[df.category.str.contains("Gross Domestic Product")]
    check("EG gdp row is aggregate", sorted(set(agg.approach)), ["aggregate"])
    check("EG sector rows are production",
          sorted(set(df[~df.category.str.contains("Gross Domestic Product")].approach)),
          ["production"])

    # Filename drives approach/basis/unit: factor cost -> production, EGP million.
    check("EG price basis", sorted(set(df.price_basis)), ["constant"])
    check("EG unit", sorted(set(df.unit)), ["EGP million"])
    check("EG base period read from the caption",
          sorted(set(df.base_period)), ["2006/2007"])
    check("EG frequency", sorted(set(df.frequency)), ["quarterly"])

    # And it validates once run.py's identity columns are attached.
    full = df.copy()
    for col, v in (("country", "Egypt"), ("iso3", "EGY"), ("indicator", "GDP"),
                   ("source_type", "excel"),
                   ("source_url", "https://example.invalid"),
                   ("source_file", "replay.xlsx"),
                   ("extracted_at", dt.datetime.now().isoformat(timespec="seconds"))):
        full[col] = v
    try:
        schema.validate_gdp(full)
    except Exception as e:
        FAILURES.append(f"EG parsed frame failed validation: {e}")


def test_egypt_expenditure_workbook_uses_billions():
    """The unit is decided by the FILENAME, and the two workbooks differ:
    factor-cost is EGP million, expenditure EGP billion. They reconcile, so a
    unit swapped between them would be invisible in the numbers."""
    from indicators.gdp.parsers import egypt_cbe_gdp as E
    check("EG factor-cost spec", E._spec("CBE_GDP_factorcost_constant.xlsx"),
          ("production", "constant", "EGP million"))
    check("EG expenditure spec", E._spec("CBE_GDP_expenditure_current.xlsx"),
          ("expenditure", "current", "EGP billion"))


def test_lesotho_stale_annual_row():
    """BOS's Q1-2026 edition prints a 2025 ANNUAL row whose GDP is the current
    vintage but whose industry/GVA/tax columns are an older one (GVA 38,002.7
    against 39,231.7 from the four quarters -- verbatim). The components must be
    dropped and GDP kept; and when BOS aligns the row, the parser must RAISE so
    the exclusion is lifted rather than silently hiding good data."""
    import tempfile
    import openpyxl
    from indicators.gdp.parsers import lesotho_bos_gdp as L

    def book(gva_2025):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "GDP_CP"
        ws.append([None, None, None, "Taxes", "GDP"])
        ws.append(["Year", "Quar-ter", "All indu-stries at basic prices",
                   "Taxes on products", "GDP"])
        ws.append(["2025", None, gva_2025, 5980.5, 45063.6])
        for q, g in (("Q1", 9500.0), ("Q2", 9800.0), ("Q3", 9900.0), ("Q4", 10031.7)):
            # taxes chosen so the quarters sum to the published annual GDP
            ws.append(["2025", q, g, 1457.975, g + 1457.975])
        path = os.path.join(tempfile.mkdtemp(), "q.xlsx")
        wb.save(path)
        return openpyxl.load_workbook(path, data_only=True)["GDP_CP"]

    stale = book(38002.7)
    L._check_still_stale(stale)                       # stale: no error
    rows = L._levels(stale, "current")
    annual = {r["category"] for r in rows if r["period"] == "2025"}
    check("ls 2025 annual keeps only GDP", annual, {"GDP"})

    fixed = book(39231.7)                             # = sum of the quarters
    try:
        L._check_still_stale(fixed)
        FAILURES.append("ls: an aligned 2025 row was still excluded silently")
    except ValueError:
        pass


def main() -> int:
    for fn in (test_validator_guards, test_bounds_stay_loose_on_purpose,
               test_cross_field_consistency, test_corpus_invariants,
               test_gdp_merge_keys_are_unique,
               test_every_descriptor_has_a_parser,
               test_egypt_fiscal_to_calendar_quarters,
               test_egypt_expenditure_workbook_uses_billions,
               test_lesotho_stale_annual_row):
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
