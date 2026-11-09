"""Offline tests for the monetary-poverty package.

    py -3 -W ignore -m indicators.poverty.tests.test_offline

House pattern: no pytest, a FAILURES list, main() -> 0/1. Fixtures are
VERBATIM lines from the downloaded reports (a fixture written to match the
layout tests nothing). The replay test reads the RETAINED PDF in source_data/,
so it needs no network.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

from indicators.poverty import schema
from indicators.poverty.parsers import REGISTRY
from indicators.poverty.parsers import _common as C
from indicators.poverty.parsers import poverty_tables as T
from indicators.poverty.standardise import standardise
from core.schema_base import ValidationError

FAILURES: list[str] = []
HERE = os.path.dirname(os.path.abspath(__file__))
CIV_PDF = os.path.join(os.path.dirname(HERE), "source_data", "Cote_dIvoire",
                       "ANStat_EHCVM2021_profil_pauvrete.pdf")

# Tableau 3-1 / 3-2 / 3-6, verbatim (ANStat, Profil de pauvreté 2021).
CIV_T31_TOTAL = "Total 37,5% 100,0% 10,4% 100,0% 4,1% 100,0% 29 809 425 100,0%"
CIV_T32_NZI = "N’ZI 168 252 65,2% 89 919 34,8% 51,3% 258 171 ,9%"
CIV_T36 = """Sexe du CM
Féminin 50,7% 1 647 760 11,7% 23,1% 3 228 141 20,5% 32,4% 4 875 901 16,4%
Masculin 54,9% 12 452 152 88,3% 22,0% 12 481 372 79,5% 38,5% 24 933 524 83,6%
Total 54,4% 14 099 912 100,0% 22,2% 15 709 513 100,0% 37,5% 29 809 425 100,0%
Alphabétisation du CM
Non 59,9% 8 515 071 60,4% 37,7% 5 316 154 33,8% 51,4% 13 831 225 46,4%
Oui 46,1% 5 584 841 39,6% 14,3% 10 393 359 66,2% 25,4% 15 978 200 53,6%
Total 54,4% 14 099 912 100,0% 22,2% 15 709 513 100,0% 37,5% 29 809 425 100,0%"""

CIV_T37 = """Alphabétisation des individus
Non 53,3% 4 511 764 60,3% 29,6% 3 028 847 31,0% 43,8% 7 540 611 43,7%
Oui 40,9% 2 970 274 39,7% 12,5% 6 748 267 69,0% 21,2% 9 718 541 56,3%
Total 54,4% 7 482 038 100,0% 22,2% 9 777 114 100,0% 37,5% 17 259 152 100,0%"""


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


def test_percent_cell_is_not_a_thousands_group():
    # Without percent_cells, "425 100,0" is one thousands group and the whole
    # count reads as 29 809 425 100,0 -- a population of 29 billion.
    got = C.numbers_in(CIV_T31_TOTAL[6:], decimal=",", percent_cells=True)
    check("CIV T3-1 Total numbers", got,
          [37.5, 100.0, 10.4, 100.0, 4.1, 100.0, 29809425.0, 100.0])


def test_leading_comma_is_a_lost_zero():
    got = C.numbers_in(CIV_T32_NZI[5:], decimal=",", percent_cells=True)
    check("CIV N'ZI population share", got[-1], 0.9)
    check("CIV N'ZI count of numbers", len(got), 7)


def _frame(rows):
    df = pd.DataFrame(rows)
    for c in schema.POVERTY_COLUMNS:
        if c not in df:
            df[c] = ""
    return df


def test_blocks_scope_repeated_labels():
    # "Non"/"Oui"/"Total" repeat in every block of Tableau 3-6; start/end must
    # keep literacy-of-head to its own block.
    from indicators.poverty.parsers.cote_divoire_poverty import LAYOUT
    tbl = [t for t in LAYOUT["tables"] if t.get("start") == r"^Alphabétisation du CM"][0]
    pages = {"full": ["Tableau 3-6 : Taux de pauvreté selon les caractéristiques "
                      "sociodémographiques du chef de ménage.\n" + CIV_T36]}
    rows, _ = T._parse_table(pages, LAYOUT, tbl, "2021", "2021")
    got = {(r["characteristic"], r["locality"]): r["value"] for r in rows if r["metric"] == "headcount"}
    check("CIV literacy of head, Non total", got.get(("Non", "all")), 51.4)
    check("CIV literacy of head, Oui rural", got.get(("Oui", "rural")), 46.1)
    check("CIV literacy block rows", len(rows), 12)
    # The individuals' table (3-7) prints the same "Non"/"Oui" labels. On a
    # page where the head-literacy block comes first, only `start` keeps the
    # 3-7 spec from taking the head's 51,4 as the individuals' 43,8.
    t37 = [t for t in LAYOUT["tables"] if t.get("start") == r"^Alphabétisation des individus"][0]
    page = ("Tableau 3-7: Taux de pauvreté selon l’alphabétisation et le niveau "
            "d’instruction des individus.\n" + CIV_T36 + "\n" + CIV_T37)
    rows, _ = T._parse_table({"full": [page]}, LAYOUT, t37, "2021", "2021")
    got = {(r["characteristic"], r["locality"]): r["value"] for r in rows if r["metric"] == "headcount"}
    check("CIV literacy of individuals, Non total", got.get(("Non", "all")), 43.8)


def test_fgt_ordering_catches_swapped_columns():
    base = dict(survey="S", welfare_aggregate="consumption", unit_of_analysis="person",
                line_type="national", line_level="overall", line_name="L",
                line_value="", line_unit="", topic="total", characteristic="Total",
                sex="total", age_group="Total", geography="Total country",
                locality="all", locality_label="Total", period="2021",
                reference_period="2021", frequency="ad_hoc", unit="percent")
    ok = [dict(base, metric="headcount", value=37.5), dict(base, metric="gap", value=10.4),
          dict(base, metric="severity", value=4.1)]
    try:
        schema.validate_poverty(_frame(ok))
        check("FGT in order passes", True, True)
    except ValidationError as e:
        check("FGT in order passes", str(e), "no error")
    swapped = [dict(base, metric="headcount", value=37.5), dict(base, metric="gap", value=4.1),
               dict(base, metric="severity", value=10.4)]
    try:
        schema.validate_poverty(_frame(swapped))
        check("FGT P1/P2 swap is caught", "accepted", "ValidationError")
    except ValidationError:
        pass
    # 0-1 gap must not pass as a percent, nor a percent as an index.
    try:
        schema.validate_poverty(_frame([dict(base, metric="gap", value=8.4, unit="index")]))
        check("gap 8.4 as index rejected", "accepted", "ValidationError")
    except ValidationError:
        pass


def test_civ_replay():
    """The retained report, end to end -- including the OFF-PAGE TEXT trap."""
    if not os.path.exists(CIV_PDF):
        FAILURES.append(f"CIV replay: retained file missing: {CIV_PDF}")
        return
    df = REGISTRY["cote_divoire_poverty"](CIV_PDF)
    df = schema.validate_poverty(_frame(df.to_dict("records")))

    def v(**kw):
        sub = df
        for k, x in kw.items():
            sub = sub[sub[k] == x]
        return list(sub["value"])

    nat = dict(geography="Total country", topic="total", locality="all")
    check("CIV P0 2021", v(metric="headcount", period="2021", **nat), [37.5])
    check("CIV P1 2021", v(metric="gap", period="2021", **nat), [10.4])
    check("CIV P2 2021", v(metric="severity", period="2021", **nat), [4.1])
    check("CIV P0 2018", v(metric="headcount", period="2018", **nat), [39.4])
    # Tableau 3-3 lives on a page whose text layer ALSO carries Tableau 3-2,
    # placed off-page; reading it would pair BOUNKANI with 3-2's numbers.
    check("CIV Bounkani P0 2018", v(metric="headcount", period="2018", geography="BOUNKANI"), [45.7])
    check("CIV Bounkani P1 2021", v(metric="gap", period="2021", geography="BOUNKANI"), [24.1])
    check("CIV Abidjan P0 2021", v(metric="headcount", period="2021", geography="ABIDJAN"), [6.8])
    check("CIV regions", df.loc[df.geography != "Total country", "geography"].nunique(), 33)
    shares = pd.to_numeric(df[(df.metric == "population_share") & (df.geography != "Total country")]["value"])
    check("CIV regional population shares sum to 100", round(float(shares.sum()), 0), 100.0)
    check("CIV female-headed P0", v(metric="headcount", characteristic="Féminin", locality="all"), [32.4])
    check("CIV 14+ persons P0", v(metric="headcount", characteristic="Quatorze personnes et plus",
                                  locality="all"), [61.1])
    check("CIV no duplicate keys", int(df.duplicated(
        [c for c in schema.POVERTY_COLUMNS if c not in ("value", "unit")]).sum()), 0)


def test_standardise_ids():
    base = dict(country="X", iso3="XXX", survey="S", welfare_aggregate="consumption",
                unit_of_analysis="person", line_type="national", line_name="L",
                line_value="", line_unit="", topic="total", characteristic="Total",
                sex="total", age_group="Total", geography="Total country",
                locality="all", locality_label="Total", period="2021",
                reference_period="2021", frequency="ad_hoc", unit="percent",
                source_file="f", extracted_at="t")
    df = pd.DataFrame([
        dict(base, line_level="overall", metric="headcount", value=37.5),
        dict(base, line_level="extreme", metric="headcount", value=6.8),
        dict(base, line_level="overall", metric="gap", value=0.104, unit="index"),
        dict(base, line_level="overall", metric="headcount", value=32.4,
             topic="sex_of_head", characteristic="Féminin", sex="female"),
        dict(base, line_level="overall", metric="headcount", value=48.3,
             topic="education_of_head", characteristic="Aucun"),
    ])
    out = standardise(df)
    ids = list(out["series_id"])
    check("overall headcount id", ids[0], "POV_NAT_P0")
    check("extreme line has its own id", ids[1], "POV_NAT_EXT_P0")
    check("female-headed id", ids[3], "POV_NAT_P0_HEAD_F")
    check("national category set left uncoded", ids[4], "")
    check("0-1 gap on percent scale", float(out["value_std"].iat[2]), 10.4)


def test_fraction_headcounts_and_dating():
    kw = dict(survey="S", welfare_aggregate="consumption", line_type="national",
              line_level="overall", line_name="L", frequency="ad_hoc")
    # A split-year round reported by its LAST year is dated by its first.
    check("split-year round dated by first year",
          C.row(metric="headcount", value=27.4, period="2024", reference_period="2023/24", **kw)["period"], "2023")
    check("single-year round untouched",
          C.row(metric="headcount", value=27.4, period="2011", reference_period="2011", **kw)["period"], "2011")
    base = dict(country="X", iso3="XXX", indicator="Poverty", unit_of_analysis="person",
                line_value="", line_unit="", topic="total", characteristic="Total", sex="total",
                age_group="Total", geography="Total country", locality="all",
                locality_label="Total", reference_period="2006", series_code="",
                source_type="t", source_url="u", source_file="f", extracted_at="t", **kw)
    ok = pd.DataFrame([dict(base, period="2006", metric="headcount", value=0.37, unit="index"),
                       dict(base, period="2006", metric="gap", value=0.104, unit="index")])
    schema.validate_poverty(ok)
    check("0-1 headcount on percent scale", float(standardise(ok)["value_std"].iat[0]), 37.0)
    for label, bad in (("0-1 headcount above 1", ok.assign(value=[37.0, 0.104])),
                       ("end-year dating rejected", ok.assign(period="2007", reference_period="2006/07"))):
        try:
            schema.validate_poverty(bad)
            FAILURES.append(f"{label}: not rejected")
        except ValidationError:
            pass
    # Newest report wins: the same round, original (report covering up to
    # 2016) vs re-estimate (report covering up to 2023).
    # The re-estimate comes FIRST, so row order alone would pick the original.
    rows = pd.DataFrame([dict(base, period="2016", reference_period="2016/17", metric="headcount",
                              value=39.8, unit="percent", source_file="new.xlsx", survey="R5 re-est"),
                         dict(base, period="2016", reference_period="2016/17", metric="headcount",
                              value=38.2, unit="percent", source_file="old.pdf", survey="R5"),
                         dict(base, period="2023", reference_period="2023/24", metric="headcount",
                              value=27.4, unit="percent", source_file="new.xlsx", survey="R7")])
    st = standardise(rows)
    check("newest report's re-estimate preferred", list(st["is_preferred"]), [True, False, True])


def main() -> int:
    for t in (test_percent_cell_is_not_a_thousands_group, test_leading_comma_is_a_lost_zero,
              test_blocks_scope_repeated_labels, test_fgt_ordering_catches_swapped_columns,
              test_civ_replay, test_standardise_ids, test_fraction_headcounts_and_dating):
        try:
            t()
        except Exception as e:  # noqa: BLE001
            FAILURES.append(f"{t.__name__}: {type(e).__name__}: {e}")
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("poverty offline tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
