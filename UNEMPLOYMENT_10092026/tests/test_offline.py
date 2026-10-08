"""Offline self-test for the unemployment collector.

Runs with no network and no NSO files: it replays the ACTUAL printed lines of
three published tables (Namibia's Table 0.1, Zambia's 2024 summary and
Nigeria's NLFS Q2 2024 headline) through the real parser, then puts the result
through the real schema validator.

Its job is to prove the machinery -- row-by-column mapping, the trailing-offset
rule, label-embedded digits, mixed units, and the two residence orders (Zambia
prints Rural before Urban, Namibia Urban before Rural) -- rather than to prove
any live source is up. Run it after editing a layout, before running the
pipeline against the network:

    python -m indicators.unemployment.tests.test_offline
"""
from __future__ import annotations
import datetime as dt
import re
import sys

import pandas as pd

from indicators.unemployment import schema
from indicators.unemployment.parsers import pdf_key_indicators as P
from indicators.unemployment.parsers import _common as C
# LAYOUTS now lives on the package, assembled from the per-country
# modules that replaced the single layouts.py.
from indicators.unemployment.parsers import LAYOUTS

FAILURES: list[str] = []


def check(name: str, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


# --- unit checks on the shared helpers ------------------------------------

def test_numbers():
    # Portuguese/French: comma decimal, space thousands (Angola's Quadro 1).
    check("pt thousands", C.numbers_in("Força de trabalho 12 155 946 12 962 065", ","),
          [12155946.0, 12962065.0])
    check("pt decimal", C.numbers_in("Taxa de desemprego 21,3 21,5 0,2", ","),
          [21.3, 21.5, 0.2])
    # English: comma thousands, dot decimal (Namibia's Table 0.1).
    check("en thousands", C.numbers_in("Labour Force 867,247 459,723", "."),
          [867247.0, 459723.0])
    # A lost leading zero, as printed in Cameroon's EESI3 leaflet.
    check("lost zero", C.to_number(",4", ","), 0.4)
    # Non-numeric cells must be None, never 0.
    for token in ("-", "..", "ps", "n/a", ""):
        check(f"non-numeric {token!r}", C.to_number(token), None)


def test_periods():
    for text, want in [
        ("2022Q3", "2022-Q3"),
        ("Q1 2026", "2026-Q1"),
        ("second quarter of 2024", "2024-Q2"),
        ("Apr-Jun 2026", "2026-Q2"),
        ("T2 2026", "2026-Q2"),
        ("deuxieme trimestre 2026", "2026-Q2"),
        ("2e semestre 2025", "2025-H2"),
        ("2014", "2014"),
    ]:
        check(f"period {text!r}", C.parse_period(text), want)


# --- end-to-end: replayed published tables --------------------------------

NAMIBIA_PAGE = """
Table 0.1: Selected Key Indicators of the Labour Market by Urban/Rural and Sex
Indicators Total Male Female Urban Rural
Total Population 3,022,401 1,474,224 1,548,177 1,512,685 1,509,716
Working Age Population 15 + years 1,876,122 899,589 976,533 1,009,408 866,714
Employed 546,805 300,794 246,011 367,519 179,286
Unemployed 320,442 158,929 161,513 210,583 109,859
Labour Force 867,247 459,723 407,524 578,102 289,145
Potential Labour Force 341,931 149,369 192,562 138,599 203,332
Extended Labour Force 1,209,178 609,092 600,086 716,701 492,477
Labour Force Participation Rate 46.2 51.1 41.7 57.3 33.4
Employment to Population Ratio 29.1 33.4 25.2 36.4 20.7
Unemployment Rate 36.9 34.6 39.6 36.4 38.0
CRUPLF 54.8 50.6 59.0 48.7 63.6
"""

ZAMBIA_PAGE = """
Summary of 2024 Labour Force Survey
Indicator Mode of measurement Total Male Female Rural Urban
Working-age population 15 years or older Number 11,995,355 5,927,133 6,068,222 6,940,210 5,055,145
Labour force Number 4,560,760 2,732,732 1,828,028 1,944,705 2,616,054
Employed (market production activities) Number 3,972,883 2,410,984 1,561,899 1,719,237 2,253,646
Unemployed population Number 587,876 321,748 266,129 225,469 362,408
Labour force participation rate Percent 38.0 46.1 30.1 28.0 51.8
Employment-to-population ratio Percent 33.1 40.7 25.7 24.8 44.6
Unemployment rate Percent 12.9 11.8 14.6 11.6 13.9
Youth (19-34 years) unemployment rate Percent 18.4 16.7 20.8 15.0 21.0
"""

NIGERIA_PAGE = """
This report contains findings from the Nigeria Labour Force Survey (NLFS)
for the second quarter of 2024.
Labour Market Indicators by Sex and Place of Residence
Age 15 plus Total Male Female Total Male Female Total Male Female
Labour force population 79.5 79.9 79.1 77.2 77.3 77.2 83.2 84.1 82.3
Employed population 76.1 77.2 75.0 73.2 74.0 72.4 80.8 82.3 79.4
Unemployed population 4.3 3.4 5.1 5.2 4.2 6.1 2.8 2.1 3.5
Time-related underemployment 9.2 7.1 11.2 8.9 7.0 10.7 9.7 7.4 12.0
Informal employment 93.0 90.0 96.0 90.0 85.5 94.2 97.5 96.3 98.7
Informal employment (excluding agriculture) 90.4 84.3 95.1 88.0 81.9 93.4 95.7 91.1 98.3
Young unemployed (aged 15-24) 6.5 5.4 7.8 8.0 6.9 9.0 4.4 3.5 5.7
NEET (aged 15-24) 12.5 10.9 14.3 13.5 12.5 14.4 10.9 8.5 14.2
LU2 13.0 10.3 15.7 13.6 10.9 16.1 12.2 9.4 15.0
LU3 5.9 4.8 6.9 6.9 5.8 7.9 4.4 3.4 5.4
LU4 14.5 11.6 17.3 15.2 12.4 17.8 13.6 10.5 16.7
"""


def run_layout(country: str, page: str, extra_pages: list[str] | None = None):
    """Parse a replayed page with the country's real layout, monkeypatching
    only the PDF text extraction."""
    pages = [page] + (extra_pages or [])
    orig = P._pages
    P._pages = lambda _path, _cols=1: pages
    try:
        return P.make_parser(LAYOUTS[country])("<replay>")
    finally:
        P._pages = orig


def unmatched(country: str, pages: list[str], only_tables: list[int] | None = None):
    """Which row specs matched NOTHING, as a list.

    `make_parser` prints its misses and carries on -- "loud but non-fatal",
    which is right in production where a partial capture is better than none.
    In a test it is the opposite: a fixture that exercises a table should match
    every row spec in it, and a spec that quietly stops matching is how a
    layout rots while the suite stays green. This re-derives the misses so a
    test can assert on them instead of reading stderr.
    """
    import copy
    cfg = copy.deepcopy(LAYOUTS[country])
    tables = cfg.get("tables") or [cfg]
    if only_tables is not None:
        tables = [tables[i] for i in only_tables]
    out = []
    period, reference = P._resolve_period(pages, cfg)
    for t, tbl in enumerate(tables):
        _got, matched = P._parse_table(pages, cfg, tbl, period, reference)
        for ri, rspec in enumerate(tbl["rows"]):
            if ri not in matched:
                out.append(f"table[{t}].{rspec['match']!r}")
    return out


def finish(df: pd.DataFrame, country: str) -> pd.DataFrame:
    """Attach the identity columns run.py would add, then validate for real."""
    df = df.copy()
    df["country"] = country
    df["iso3"] = "XXX"
    df["indicator"] = "Unemployment"
    df["source_type"] = "pdf"
    df["source_url"] = "https://example.invalid/replay"
    df["source_file"] = "replay.pdf"
    df["extracted_at"] = dt.datetime.now().isoformat(timespec="seconds")
    for col in schema.UNEMPLOYMENT_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return schema.validate_unemployment(df)


def pick(df, topic, **kw):
    m = df["topic"] == topic
    for k, v in kw.items():
        m &= df[k] == v
    vals = df.loc[m, "value"].tolist()
    return vals[0] if len(vals) == 1 else vals


def test_namibia():
    df = finish(run_layout("namibia", NAMIBIA_PAGE), "Namibia")
    check("NA unemployment total", pick(df, "unemployment_rate", sex="total",
                                        locality="all"), 36.9)
    check("NA unemployment female", pick(df, "unemployment_rate", sex="female"), 39.6)
    # Urban before Rural: 36.4 is urban, 38.0 rural.
    check("NA unemployment urban", pick(df, "unemployment_rate", locality="urban"), 36.4)
    check("NA unemployment rural", pick(df, "unemployment_rate", locality="rural"), 38.0)
    check("NA WAP total", pick(df, "working_age_population", sex="total",
                               locality="all"), 1876122.0)
    check("NA CRUPLF broad", pick(df, "labour_underutilisation_rate", sex="total",
                                  locality="all"), 54.8)
    # "Labour Force" must not have swallowed "Potential"/"Extended".
    check("NA labour force total", pick(df, "labour_force", sex="total",
                                        locality="all"), 867247.0)
    check("NA counts are persons",
          set(df.loc[df.measure == "count", "unit"]), {"persons"})


def test_zambia():
    df = finish(run_layout("zambia", ZAMBIA_PAGE), "Zambia")
    check("ZM unemployment total", pick(df, "unemployment_rate", sex="total",
                                        locality="all"), 12.9)
    # Rural before Urban -- the reverse of Namibia. Getting this wrong swaps
    # two real series and nothing downstream would notice.
    check("ZM unemployment rural", pick(df, "unemployment_rate", locality="rural"), 11.6)
    check("ZM unemployment urban", pick(df, "unemployment_rate", locality="urban"), 13.9)
    # Label digits ("15 years or older", "(19-34 years)") must not be read as data.
    check("ZM WAP total", pick(df, "working_age_population", sex="total",
                               locality="all"), 11995355.0)
    check("ZM youth rate", pick(df, "youth_unemployment_rate", sex="total",
                                locality="all"), 18.4)
    check("ZM youth band", set(df.loc[df.topic == "youth_unemployment_rate",
                                      "age_group"]), {"19-34"})
    # The plain unemployment_rate spec must not have stolen the youth row.
    check("ZM strict rate count", len(df[df.topic == "unemployment_rate"]), 5)


def test_nigeria():
    df = finish(run_layout("nigeria", NIGERIA_PAGE), "Nigeria")
    check("NG unemployment total", pick(df, "unemployment_rate", sex="total",
                                        locality="all"), 4.3)
    check("NG unemployment urban female",
          pick(df, "unemployment_rate", sex="female", locality="urban"), 6.1)
    check("NG LFPR total", pick(df, "labour_force_participation_rate",
                                sex="total", locality="all"), 79.5)
    check("NG EPR total", pick(df, "employment_to_population_ratio",
                               sex="total", locality="all"), 76.1)
    # "Informal employment" must not have matched the "(excluding agriculture)"
    # row -- 93.0 is the plain series, 90.4 the excluded one.
    check("NG informal", pick(df, "informal_employment_share", sex="total",
                              locality="all"), 93.0)
    check("NG youth band", set(df.loc[df.topic == "youth_unemployment_rate",
                                      "age_group"]), {"15-24"})
    # LU2/LU3/LU4 share a topic but stay distinguishable by their labels.
    lu = df[df.topic == "labour_underutilisation_rate"]
    check("NG LU labels", sorted(set(lu.series_label)), ["LU2", "LU3", "LU4"])
    check("NG LU all broad", set(lu.definition), {"broad"})


def test_validator_rejects_garbage():
    """The guardrails must actually fire."""
    df = finish(run_layout("namibia", NAMIBIA_PAGE), "Namibia")

    bad = df.copy()
    bad.loc[bad.index[0], "value"] = 4200.0      # a rate outside [0, 100]
    bad.loc[bad.index[0], "measure"] = "rate"
    bad.loc[bad.index[0], "unit"] = "percent"
    try:
        schema.validate_unemployment(bad)
        FAILURES.append("validator accepted a 4200% rate")
    except Exception:
        pass

    bad2 = df.copy()
    bad2["period"] = "2023-13"                   # malformed period
    try:
        schema.validate_unemployment(bad2)
        FAILURES.append("validator accepted period '2023-13'")
    except Exception:
        pass

    bad3 = df.copy()
    bad3.loc[bad3.index[0], "topic"] = "unemployment_vibes"
    try:
        schema.validate_unemployment(bad3)
        FAILURES.append("validator accepted an unknown topic")
    except Exception:
        pass


def test_no_silent_undated_output():
    """A layout with neither a fixed period nor a matching pattern must raise,
    not guess."""
    cfg = dict(LAYOUTS["namibia"])
    cfg.pop("period", None)
    cfg.pop("period_patterns", None)
    orig = P._pages
    P._pages = lambda _p, _cols=1: [NAMIBIA_PAGE]
    try:
        P.make_parser(cfg)("<replay>")
        FAILURES.append("parser dated an undatable report instead of raising")
    except ValueError:
        pass
    finally:
        P._pages = orig


def test_ghana_pxweb():
    """Replay a miniature json-stat2 response in Ghana StatsBank's exact shape:
    Economic_Activity x Date x Region x Locality x Education x Sex x Age, values
    flat and row-major. Proves the coordinate decoding, the topic_map, and the
    refusal to drop an unmapped category."""
    import json
    import os
    import tempfile
    from indicators.unemployment.parsers import ghana_pxweb_unemployment as G

    dims = ["Economic_Activity", "Date", "Region", "Locality", "Education",
            "Sex", "Age"]
    cats = {
        "Economic_Activity": ["Total", "Labour force", "Employed", "Unemployed",
                              "Outside labour force"],
        "Date": ["2023Q2", "2023Q3"],
        "Region": ["Ghana", "Ashanti"],
        "Locality": ["All Locality Types", "Urban"],
        "Education": ["All Educational Levels"],
        "Sex": ["Both Sexes", "Male", "Female"],
        "Age": ["All Ages"],
    }
    sizes = [len(cats[d]) for d in dims]
    n = 1
    for s in sizes:
        n *= s
    doc = {
        "id": dims, "size": sizes,
        "dimension": {d: {"category": {"index": {v: i for i, v in
                                                 enumerate(cats[d])}}}
                      for d in dims},
        "value": list(range(n)),          # value == flat index, so we can
    }                                      # verify decoding exactly

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ghana_econact.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f)

        spec = {"path": path, "topic_map": {
            "Total": "working_age_population", "Labour force": "labour_force",
            "Employed": "employed", "Unemployed": "unemployed",
            "Outside labour force": "outside_labour_force"}}
        df = finish(G.parse([spec]), "Ghana")

        check("GH rows", len(df), n)
        check("GH topics", len(set(df.topic)), 5)
        check("GH periods", sorted(set(df.period)), ["2023-Q2", "2023-Q3"])
        check("GH geographies", sorted(set(df.geography)),
              ["Ashanti", "Total country"])
        check("GH sexes", sorted(set(df.sex)), ["female", "male", "total"])
        check("GH localities", sorted(set(df.locality)), ["all", "urban"])
        check("GH counts are persons", set(df.unit), {"persons"})
        # Flat index 0 is the first cell of every dimension.
        first = df[(df.topic == "working_age_population") &
                   (df.period == "2023-Q2") & (df.geography == "Total country") &
                   (df.locality == "all") & (df.sex == "total")]
        check("GH decode of flat index 0", first.value.tolist(), [0.0])

        # An unmapped category must RAISE, not vanish.
        spec2 = dict(spec, topic_map={"Employed": "employed"})
        try:
            G.parse([spec2])
            FAILURES.append("ghana parser silently dropped unmapped categories")
        except ValueError as e:
            if "topic_map" not in str(e):
                FAILURES.append(f"ghana parser raised the wrong error: {e}")


# --- replayed tables for the second tranche of countries ------------------

# Replayed from the ERI-ESI recap table in its ACTUAL shape. The age rows are
# their own lines under a REPEATED heading, not a suffix on it, and the block
# below them -- average unemployment duration, in YEARS -- is the one whose
# "Ensemble 5,24 ... 6,65" was being read as a 6.65% underutilisation rate
# while the su4 block stayed open. This fixture used to carry the one-line form
# the layout had assumed, so it passed against a layout that could not read the
# report.
NIGER_PAGE = """
Principaux indicateurs de l'emploi, ERI-ESI, Niger 2017
Indicateurs Niamey urbain Autres urbains Ensemble urbain Rural Niger
Taux de chômage BIT
Ensemble 7,3 6,9 7,0 8,3 7,9
Homme 6,7 7,7 7,3 8,3 8,0
Femme 8,7 5,0 6,5 8,1 7,7
Taux de chômage BIT
15 - 34 ans 13,6 12,4 12,8 12,0 12,2
35 ans et plus 3,9 3,0 3,4 5,6 5,0
Taux combiné du sous-emploi lié au temps de travail et
du chômage (%)
Ensemble 16,9 35,7 28,0 30,4 29,8
Homme 15,3 31,0 24,6 28,1 27,2
Femme 20,6 46,4 35,8 35,7 35,7
Taux de sous-utilisation de la main œuvre (%)
Ensemble 29,4 51,9 43,3 64,0 60,2
Homme 21,1 41,1 33,4 56,3 51,9
Femme 43,8 69,0 59,8 75,3 72,6
Taux de sous-utilisation de la main œuvre (%)
15 - 34 ans 45,0 62,5 56,6 71,7 69,2
35 ans et plus 19,1 42,3 32,7 56,1 51,4
Durée moyenne de chômage (en années)
Ensemble 5,24 3,43 4,18 7,35 6,65
"""

LIBERIA_PAGE = """
Main labour force and labour underutilization (LU) indicators (%), LBR-LFS 2016-2017 - Main job
Population 15 years and older 1,108,829 1,246,231 1,282,106 1,072,954 713,355 699,849 189,586 392,502 191,792 167,976 94,948 2,260,112 1,409,787 945,273 774,702 1,580,358 2,355,060
Labour force 359,522 256,027 308,161 307,388 168,105 161,027 62,528 125,187 54,881 43,821 14,031 601,518 288,857 326,692 266,249 349,300 615,549
-Employed 317,698 221,204 247,237 291,665 122,738 151,724 59,870 114,657 50,581 39,332 13,045 525,857 239,203 299,699 248,433 290,469 538,902
-Unemployed 41,824 34,823 60,924 15,723 45,367 9,303 2,658 10,530 4,300 4,489 986 75,661 49,654 26,993 17,816 58,831 76,647
Outside the labour force 749,307 990,204 973,945 765,566 545,250 538,823 127,058 267,315 136,911 124,154 80,916 1,658,595 1,120,930 618,581 508,453 1,231,058 1,739,511
Labour force participation rate (%) 32.4 20.5 24.0 28.6 23.6 23.0 33.0 31.9 28.6 26.1 14.8 26.6 20.5 34.6 34.4 22.1 26.1
Employment-to-population ratio (%) 28.7 17.7 19.3 27.2 17.2 21.7 31.6 29.2 26.4 23.4 13.7 23.3 17.0 31.7 32.1 18.4 22.9
LU1: Unemployment rate (%) 11.6 13.6 19.8 5.1 27.0 5.8 4.3 8.4 7.8 10.2 7.0 12.6 17.2 8.3 6.7 16.8 12.5
LU3: Combined rate of unemployment and potential labour force (%) 16.8 19.7 27.5 7.8 36.0 8.6 5.8 12.6 10.1 18.7 15.0 18.1 24.1 12.4 10.0 23.8 18.0
Persons with informal employment (%) 82.6 92.6 79.6 92.8 79.1 93.0 95.9 85.9 78.7 85.1 88.9 86.7 91.3 83.1 95.1 79.6 86.7
"""

BOTSWANA_PAGE = """
This report presents results from the Labour Force module of the QMTS Q1 of 2024, covering the months of January to March 2024.
Table 1.0: National Headline Labour Force Indicators -QMTS Q3 2023 and Q1 2024
Population (15 years and above) 1,611,892 1,673,626 1,651,820 781,632 870,188 2.5 (1.3)
Labour Force (15 years and above) 962,319 1,063,776 1,041,204 510,574 530,630 8.2 (2.1)
Employed Population 717,725 788,616 754,146 371,638 382,509 5.1 (4.4)
Unemployed Population 244,594 275,160 287,059 138,937 148,122 17.4 4.3
Employment to Population Ration (EPR) 44.5 47.1 45.7 47.5 44.0 1.2 (1.4)
Labour Force Participation Rate (LFPR) 59.7 63.6 63.0 65.3 61.0 3.3 (0.5)
Unemployment Rate % (15 year and above) 25.4 25.9 27.6 27.2 27.9 2.2 1.7
Extended Unemployment Rate % (15 years and above) 31.4 31.2 32.5 32.6 32.4 1.1 1.3
Youth Unemployment Rate (15-35 years) 33.5 34.4 38.2 37.2 39.3 4.7 3.8
"""

RWANDA_PAGE = """
Trend of Labour force survey Main indicators (Compare 7 years), Rwanda.
Indicators 2019 2020 2021 2022 2023 2024 2025
Labour force participation rate(%) 53.4 56.4 54 56 59.3 62.9 63.8
Employment to population ratio (%) 45.3 46.3 42.6 44.5 49 53.5 55.9
Number of off-farm main jobs( agriculture excluded) in Thousands 2,049 2,061 1,721 1,886 2,239 2,670 2,908
Informal employment rate (%) 89.5 69.8 90.5 90.8 90.9 91.2 91.8
Unemployment rate (%) 15.2 17.9 21.1 20.5 17.2 14.9 12.4
Unemployment rate among females (%) 17.0 20.3 24.1 23.7 20.3 17.6 14.2
Unemployment rate among males (%) 13.8 15.9 18.5 17.9 14.5 12.6 10.8
Youth unemployment rate (%) 19.4 22.4 26.5 25.6 20.8 18.5 14.7
Time related underemployment rate(%) 26.8 23.7 31.2 31.7 29.4 32.6 36.1
Combined rate of labour underutilization (%) 55.7 57.7 58.9 57.6 54.4 54.2 56
Average monthly salary from paid employment (In Frw)) 57,878 57,306 54,073 58,784 68,656 73,948 82,996
"""


def test_niger_blocks():
    """Niger's recap is a BLOCK table: an indicator header with no numbers,
    then Ensemble/Homme/Femme sub-rows. Without block scoping the bare label
    'Ensemble' would collapse four different indicators into one."""
    df = finish(run_layout("niger", NIGER_PAGE), "Niger")
    check("NE chomage total Niger",
          pick(df, "unemployment_rate", sex="total", locality="all",
               age_group="Total"), 7.9)
    check("NE chomage femme Niger",
          pick(df, "unemployment_rate", sex="female", locality="all",
               age_group="Total"), 7.7)
    check("NE chomage Niamey",
          pick(df, "unemployment_rate", sex="total", locality_label="Niamey urbain",
               age_group="Total"), 7.3)
    # The three sex sub-rows must NOT have leaked between blocks.
    check("NE sous-utilisation total",
          pick(df, "labour_underutilisation_rate", sex="total", locality="all",
               age_group="Total"), 60.2)
    check("NE sous-utilisation homme",
          pick(df, "labour_underutilisation_rate", sex="male", locality="all",
               age_group="Total"), 51.9)
    check("NE sous-emploi total",
          pick(df, "underemployment_rate", sex="total", locality="all"), 29.8)
    # Age-split single lines carry their own band.
    check("NE youth 15-34", pick(df, "youth_unemployment_rate", locality="all",
                                 sex="total"), 12.2)
    check("NE su4 15-34", pick(df, "labour_underutilisation_rate",
                               locality="all", sex="total",
                               age_group="15-34"), 69.2)
    # Every block must have produced all five geographies x three sexes.
    unemp = df[(df.topic == "unemployment_rate") & (df.age_group == "Total")]
    check("NE unemployment cell count", len(unemp), 15)


def test_liberia_wide():
    """Seventeen columns in seven blocks, with Functional Difficulty BEFORE
    Age and a Subsistence Farming block before Total."""
    df = finish(run_layout("liberia", LIBERIA_PAGE), "Liberia")
    total = {"sex": "total", "locality": "all", "age_group": "Total",
             "education": "Total", "geography": "Total country"}
    check("LR WAP total", pick(df, "working_age_population", **total), 2355060.0)
    check("LR labour force total", pick(df, "labour_force", **total), 615549.0)
    check("LR unemployed total", pick(df, "unemployed", **total), 76647.0)
    check("LR LU1 total", pick(df, "unemployment_rate", **total), 12.5)
    check("LR LFPR total", pick(df, "labour_force_participation_rate", **total), 26.1)
    check("LR LU3 broad total",
          pick(df, "labour_underutilisation_rate", **total), 18.0)
    # Column-order checks that would break if a block were mis-placed.
    check("LR unemployment urban", pick(df, "unemployment_rate", locality="urban"), 19.8)
    check("LR unemployment rural", pick(df, "unemployment_rate", locality="rural"), 5.1)
    check("LR unemployment Greater Monrovia",
          pick(df, "unemployment_rate", geography="Greater Monrovia"), 27.0)
    check("LR unemployment youth",
          pick(df, "unemployment_rate", age_group="Youth (15-35)"), 17.2)
    check("LR unemployment subsistence",
          pick(df, "unemployment_rate",
               education="Participated in subsistence farming"), 6.7)
    # The published identity: LU1 == unemployed / labour force, in every column.
    for loc, lf, un in (("all", 615549.0, 76647.0), ("urban", 308161.0, 60924.0),
                        ("rural", 307388.0, 15723.0)):
        got = pick(df, "unemployment_rate", locality=loc, sex="total",
                   age_group="Total", education="Total",
                   geography="Total country")
        check(f"LR LU1 identity {loc}", round(un / lf * 100, 1), got)


def test_botswana_typos_and_bases():
    """Printed typos ('Ration', '15 year'), skipped historical columns, and
    two working-age bases running in parallel."""
    df = finish(run_layout("botswana", BOTSWANA_PAGE), "Botswana")
    check("BW period", sorted(set(df.period)), ["2024-Q1"])
    check("BW unemployment total", pick(df, "unemployment_rate", sex="total",
                                        definition="strict"), 27.6)
    check("BW unemployment female", pick(df, "unemployment_rate", sex="female",
                                         definition="strict"), 27.9)
    check("BW extended broad", pick(df, "unemployment_rate", sex="total",
                                    definition="broad"), 32.5)
    # "Employment to Population Ration" -- the typo must still match.
    check("BW EPR", pick(df, "employment_to_population_ratio", sex="total"), 45.7)
    check("BW LFPR", pick(df, "labour_force_participation_rate", sex="total"), 63.0)
    check("BW WAP", pick(df, "working_age_population", sex="total"), 1651820.0)
    check("BW youth band", set(df.loc[df.topic == "youth_unemployment_rate",
                                      "age_group"]), {"15-35"})
    # The two historical columns must have been skipped, not emitted.
    check("BW no 2022 value", 1611892.0 in set(df.value), False)


def test_rwanda_period_columns():
    """Rows are indicators, columns are seven YEARS -- the whole back-series
    arrives in one parse, and the non-percentage rows stay out."""
    df = finish(run_layout("rwanda", RWANDA_PAGE), "Rwanda")
    check("RW periods", sorted(set(df.period)),
          ["2019", "2020", "2021", "2022", "2023", "2024", "2025"])
    check("RW unemployment 2025",
          pick(df, "unemployment_rate", period="2025", sex="total"), 12.4)
    check("RW unemployment 2019",
          pick(df, "unemployment_rate", period="2019", sex="total"), 15.2)
    check("RW female 2025",
          pick(df, "unemployment_rate", period="2025", sex="female"), 14.2)
    check("RW LFPR 2025",
          pick(df, "labour_force_participation_rate", period="2025"), 63.8)
    check("RW underutilisation 2025",
          pick(df, "labour_underutilisation_rate", period="2025"), 56.0)
    check("RW base 16+", set(df.working_age_base), {"16+"})
    # The Frw salary row and the thousands-of-jobs row have no topic and must
    # not have been swept in as rates.
    check("RW all values are percents", bool((df.value <= 100).all()), True)


def _tunisia_html_body():
    return """<html><body>
    <h3>Taux de chomage selon le sexe (%)</h3>
    <table>
      <tr><th>Sexe</th><th>premiere-trimestre 2026</th><th>deuxieme-trimestre 2026</th></tr>
      <tr><td>Total</td><td>15.0</td><td>14.9</td></tr>
      <tr><td>Masculin</td><td>12.3</td><td>11.8</td></tr>
      <tr><td>Feminin</td><td>20.7</td><td>21.6</td></tr>
    </table>
    <h3>Evolution de la population active en chomage selon le sexe</h3>
    <table>
      <tr><th>Sexe</th><th>premiere-trimestre 2026</th><th>deuxieme-trimestre 2026</th></tr>
      <tr><td>Total</td><td>641.7</td><td>622.4</td></tr>
      <tr><td>Masculin</td><td>356.4</td><td>341.6</td></tr>
      <tr><td>Feminin</td><td>285.3</td><td>280.7</td></tr>
    </table>
    </body></html>"""


def test_tunisia_html_parser():
    import os
    import tempfile
    from indicators.unemployment.parsers import REGISTRY
    parse = REGISTRY["tunisia_html"]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "tunisia_chomage.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(_tunisia_html_body())
        df = finish(parse(path), "Tunisia")
    check("TN periods", sorted(set(df.period)), ["2026-Q1", "2026-Q2"])
    check("TN rate Q2 total",
          pick(df, "unemployment_rate", period="2026-Q2", sex="total"), 14.9)
    check("TN rate Q2 female",
          pick(df, "unemployment_rate", period="2026-Q2", sex="female"), 21.6)
    check("TN rate Q1 total",
          pick(df, "unemployment_rate", period="2026-Q1", sex="total"), 15.0)
    check("TN unemployed Q2 total (thousands)",
          pick(df, "unemployed", period="2026-Q2", sex="total"), 622.4)
    check("TN levels in thousands",
          set(df.loc[df.measure == "count", "unit"]), {"thousand_persons"})


# ---------------------------------------------------------------------------
# KENYA -- KNBS Quarterly Labour Force Report, 2022 Q4
# ---------------------------------------------------------------------------
#
# VERBATIM from the retained kenya_qlfs_2022q4.pdf. Three pages, because the
# trap only exists when they are read together.

# Page 3. EVERY caption here is followed by dot leaders, and each one matches
# a block heading exactly as the printed caption does.
KENYA_LIST_OF_TABLES = """List of Tables
Table 1: Key Labour Market Indicators ........................................................................................
Table 2: Labour Participation Rates by Age Cohorts ...........................................................................
Table 3: Employed and Employment to Population Ratios ................................................................. 4
Table 4: Unemployment (strict definition) by Age Cohorts [LU1] ..................................................... 6
Table 5: Combined rate of Unemployment and Potential Labour Force by Age Cohorts [LU3] ...... 6
Table 6: Unemployment and Time Related Underemployment by Age Cohorts [LU2] .................... 7
Table 7: Long Term Unemployment by Age Cohorts .......................................................................... 7
Table 8: Youth Not in Education, Employment or Training (NEET) ................................................. 9
Table 9a: Persons Outside the Labour force by Age Cohorts .............................................................. 9
Table 9b: Persons Outside the Labour force1 by Age Cohorts .......................................................... 10
Table 10: Sample Allocation for the 4th Quarter of 2022 KCHS ........................................................ 13
List of Figures
Figure 1: Labour Underutilization Framework ..................................................................................
Figure 2: Quarterly Trends of Selected Key Indicators of the Labour Market ................................... 2
iii
"""

# Page 7. TABLES 2 AND 3 SHARE THIS PAGE, with identical cohort labels, and
# the rate column is letter-spaced ("1 6.2" for 16.2).
KENYA_TABLES_2_3 = """Table 2: Labour Participation Rates by Age Cohorts
Quarter 4, 2021 Quarter 3, 2022 Quarter 4, 2022 Change
Labour Total Labour Total Labour Total Qrt4, 2022/ Qrt4, 2022/
Age Force Population Rate Force Population Rate Force Population Rate Qrt3, 2022 Qrt4, 2021
15-19 894,934 5,534,297 1 6.2 642,950 5,656,741 1 1.4 937,913 5,681,787 1 6.5 5.1 0.3
20-24 2,483,730 4,635,315 5 3.6 2,379,930 4,737,443 5 0.2 2,720,443 4,758,427 5 7.2 6.9 3.6
25-29 3,133,366 4,009,805 7 8.1 3,206,704 4,098,163 7 8.2 3,183,615 4,116,315 7 7.3 -0.9 -0.8
30-34 3,033,896 3,716,301 8 1.6 3,211,157 3,798,173 8 4.5 3,140,882 3,814,997 8 2.3 -2.2 0.7
35-39 2,406,613 2,757,188 8 7.3 2,534,580 2,818,175 8 9.9 2,423,637 2,830,654 8 5.6 -4.3 -1.7
40-44 2,059,961 2,353,886 8 7.5 2,207,701 2,405,975 9 1.8 2,131,875 2,416,628 8 8.2 -3.5 0.7
45-49 1,696,494 1,862,766 9 1.1 1,745,338 1,903,993 9 1.7 1,719,163 1,912,423 8 9.9 -1.8 -1.2
50-54 1,249,659 1,364,572 9 1.6 1,297,443 1,394,751 9 3.0 1,295,015 1,400,927 9 2.4 -0.6 0.9
55-59 1,014,043 1,168,554 8 6.8 1,088,300 1,194,345 9 1.1 1,071,583 1,199,634 8 9.3 -1.8 2.5
60-64 743,736 910,252 8 1.7 798,949 930,326 8 5.9 774,040 934,446 8 2.8 -3.0 1.1
Total 18,716,433 28,312,936 6 6.1 19,113,051 28,938,083 6 6.0 19,398,165 29,066,237 6 6.7 0.7 0.6
Table 3: Employed and Employment to Population Ratios
Quarter 4, 2021 Quarter 3, 2022 Quarter 4, 2022 Change
Total Total Total Qrt4, 2022/ Qrt4, 2022/
Age Employed Population Ratio Employed Population Ratio Employed Population Ratio Qrt3, 2022 Qrt4, 2021
15-19 819,977 5,534,297 14.8 496,958 5,656,741 8.8 835,263 5,681,787 14.7 5.9 -0.1
20-24 2,122,320 4,635,315 45.8 2,043,013 4,737,443 43.1 2,295,970 4,758,427 48.3 5.2 2.5
25-29 2,803,973 4,009,805 69.9 2,993,577 4,098,163 73.0 2,997,055 4,116,315 72.8 -0.2 2.9
30-34 2,945,150 3,716,301 79.2 3,083,752 3,798,173 81.2 3,047,035 3,814,997 79.9 -1.3 0.7
35-39 2,277,826 2,757,188 82.6 2,472,753 2,818,175 87.7 2,369,061 2,830,654 83.7 -4.0 1.1
40-44 2,038,108 2,353,886 86.6 2,178,907 2,405,975 90.6 2,085,360 2,416,628 86.3 -4.3 -0.3
45-49 1,661,237 1,862,766 89.2 1,685,734 1,903,993 88.5 1,696,947 1,912,423 88.7 0.2 -0.5
50-54 1,237,459 1,364,572 90.7 1,291,105 1,394,751 92.6 1,278,520 1,400,927 91.3 -1.3 0.6
55-59 1,010,830 1,168,554 86.5 1,068,661 1,194,345 89.5 1,065,795 1,199,634 88.8 -0.7 2.3
60-64 743,736 910,252 81.7 790,203 930,326 84.9 767,159 934,446 82.1 -2.8 0.4
Total 17,660,616 28,312,936 62.4 18,104,662 28,938,083 62.6 18,438,164 29,066,237 63.4 0.8 1.0
4
"""

# Page 10. Table 6's Total row is the OTHER half of the published LU2
# contradiction, and Table 7 prints "-" for a zero rate, which is why it is
# deliberately not collected.
KENYA_TABLE_6 = """Table 6: Unemployment and Time Related Underemployment by Age Cohorts [LU2]
Quarter 4, 2021 Quarter 3, 2022 Quarter 4, 2022 Change
Age Employed loyed Force [LU2] Employed loyed Force [LU2] Employed loyed Force [LU2] 2022 2021
15-19 46,562 74,957 894,934 13.6 37,567 145,992 642,950 28.5 38,479 102,650 937,913 15.0 -13.5 1.4
20-24 146,900 361,411 2,483,730 20.5 167,170 336,916 2,379,930 21.2 169,674 424,474 2,720,443 21.8 0.6 1.3
25-29 177,799 329,393 3,133,366 16.2 155,727 213,127 3,206,704 11.5 119,529 186,560 3,183,615 9.6 -1.9 -6.6
30-34 184,960 88,746 3,033,896 9.0 152,073 127,405 3,211,157 8.7 164,960 93,847 3,140,882 8.2 -0.5 -0.8
35-39 119,847 128,786 2,406,613 10.3 111,411 61,827 2,534,580 6.8 87,415 54,576 2,423,637 5.9 -0.9 -4.4
40-44 113,818 21,853 2,059,961 6.6 123,244 28,794 2,207,701 6.9 56,115 46,515 2,131,875 4.8 -2.1 -1.8
45-49 118,023 35,257 1,696,494 9.0 77,696 59,604 1,745,338 7.9 75,538 22,215 1,719,163 5.7 -2.2 -3.3
50-54 84,359 12,200 1,249,659 7.7 66,923 6,338 1,297,443 5.6 31,747 16,496 1,295,015 3.7 -1.9 -4.0
55-59 56,879 3,213 1,014,043 5.9 60,677 19,639 1,088,300 7.4 21,896 5,788 1,071,583 2.6 -4.8 -3.3
60-64 38,596 0 743,736 5.2 28,329 8,746 798,949 4.6 15,630 6,881 774,040 2.9 -1.7 -2.3
Total 1,087,744 1,055,816 18,716,433 11.5 980,817 1,008,389 19,113,051 10.4 780,983 960,001 19,398,165 9.0 -1.4 -2.5
7
"""


def test_kenya_list_of_tables_does_not_open_a_block():
    """THE TRAP THAT COST A CYCLE, and the reason this test exists.

    Every spec selects its own page AND the List of Tables, whose dot-leader
    entry matches a block heading just as the printed caption does. Block
    context is not reset between pages, so the block opened on page 3 was
    still open when page 7 was reached and Table 3's spec swallowed Table 2's
    rows: employment came out as 19,398,165 (the labour force) and the
    employment ratio as 66.7 (the participation rate).

    Every value was real, in range, correctly typed and in the WRONG SERIES.
    Nothing downstream could have seen it, which is why both guards -- skip
    the contents pages, and require the caption NOT to be followed by dot
    leaders -- are asserted here against the two pages together.

    ON MUTATION-CHECKING THIS TEST, so a future reader does not mistake a
    healthy result for a dead test: THE TWO GUARDS ARE REDUNDANT BY DESIGN,
    and removing EITHER ONE leaves this test green, correctly -- the survivor
    still keeps the contents page from opening a block. Only removing BOTH
    reproduces the corruption, and then this test fails on all four
    assertions below ("got 19398165.0, want 18438164.0"). That redundancy is
    deliberate: per the layout module, one guard silently not applying is
    exactly how this shipped the first time.
    """
    df = finish(run_layout("kenya", KENYA_LIST_OF_TABLES,
                           [KENYA_TABLES_2_3]), "Kenya")
    q4 = dict(period="2022-Q4", age_group="Total")

    # Table 2's Total row.
    check("KE labour force Q4",
          pick(df, "labour_force", definition="strict", **q4), 19398165.0)
    check("KE participation Q4",
          pick(df, "labour_force_participation_rate", **q4), 66.7)
    # Table 3's Total row -- and these are the two that went wrong.
    check("KE employed Q4", pick(df, "employed", **q4), 18438164.0)
    check("KE employment ratio Q4",
          pick(df, "employment_to_population_ratio", **q4), 63.4)

    # The corruption, stated explicitly: employment must NOT be the labour
    # force, and the ratio must NOT be the participation rate.
    check("KE employment is not the labour force",
          pick(df, "employed", **q4) == 19398165.0, False)
    check("KE ratio is not the participation rate",
          pick(df, "employment_to_population_ratio", **q4) == 66.7, False)


def test_kenya_cohorts_and_quarter_columns():
    """Ten cohorts x three quarters, with the two back quarters existing in no
    other source the collector reads, and a letter-spaced rate column."""
    df = finish(run_layout("kenya", KENYA_TABLES_2_3), "Kenya")

    check("KE periods", sorted(set(df.period)),
          ["2021-Q4", "2022-Q3", "2022-Q4"])
    check("KE cohorts", len(set(df.age_group)), 11)      # ten bands + Total
    check("KE base", set(df.working_age_base), {"15-64"})

    # A cohort row, in each of the three quarters.
    check("KE 15-19 labour force Q4 2022",
          pick(df, "labour_force", definition="strict", age_group="15-19",
               period="2022-Q4"), 937913.0)
    check("KE 15-19 labour force Q4 2021",
          pick(df, "labour_force", definition="strict", age_group="15-19",
               period="2021-Q4"), 894934.0)
    check("KE 20-24 employed Q3 2022",
          pick(df, "employed", age_group="20-24", period="2022-Q3"), 2043013.0)

    # DESPACING: the rate column prints "1 6.2" for 16.2 and "6 6.7" for 66.7.
    check("KE 15-19 participation despaced",
          pick(df, "labour_force_participation_rate", age_group="15-19",
               period="2022-Q4"), 16.5)
    check("KE 25-29 participation despaced",
          pick(df, "labour_force_participation_rate", age_group="25-29",
               period="2022-Q4"), 77.3)
    # "15-19" must not have been read as the numbers 15 and -19.
    check("KE label digits not data", -19.0 in set(df.value), False)

    # The two derived Change columns are not data.
    check("KE change columns skipped", 5.1 in set(df.value), False)


def test_kenya_lu2_contradiction_is_preserved():
    """THE REPORT CONTRADICTS ITSELF AND BOTH FIGURES STAND.

    Table 1 gives LU2 for Q4 2022 as 18.6; Table 6 and the report's own prose
    give 9.0. Table 1's companion count is exactly twice what its footnote
    defines, so that figure looks doubled -- but picking a winner would be
    correcting the NSO. The two tables label the row differently, and
    `series_label` is part of the merge key, so both survive and stay
    distinguishable.
    """
    df = finish(run_layout("kenya", KENYA_TABLE_6), "Kenya")
    lu2 = df[(df.series_label == "Under - Utilization [LU2]") &
             (df.age_group == "Total")]
    check("KE LU2 from Table 6, Q4 2022",
          lu2[lu2.period == "2022-Q4"].value.tolist(), [9.0])
    check("KE LU2 from Table 6, Q3 2022",
          lu2[lu2.period == "2022-Q3"].value.tolist(), [10.4])
    check("KE LU2 labelled distinctly",
          "Under - Utilization [LU2]" in set(df.series_label), True)
    # Table 6's own unemployed/labour-force columns belong to Tables 4 and 2;
    # re-emitting them here would be one figure under one key from two pages.
    check("KE Table 6 emits only the rate",
          set(df.topic), {"labour_underutilisation_rate"})


def test_kenya_backfill_dates_each_file_from_its_name():
    """THE PERIOD COMES FROM THE FILENAME, AND A FILE THAT CANNOT BE DATED
    MUST RAISE.

    This series cannot be dated from its own text: the 2020-2021 issues carry
    no "for the period" sentence, and 2019 Q4 prints "September to December
    2019" for October-December -- KNBS's own typo, which `parse_period` reads
    as 2019-Q3. A pattern that silently failed would leave the layout's pinned
    2022-Q4 in place and publish an entire file under the wrong quarter.
    """
    from indicators.unemployment.parsers import kenya_unemployment as K

    for name, want in (("kenya_qlfs_2020q1.pdf", (2020, 1)),
                       ("kenya_qlfs_2021q1.pdf", (2021, 1)),
                       ("Quarterly-Labour-Force-Report-2020-Quarter-3.pdf", (2020, 3)),
                       ("kenya_qlfs_2022q4.pdf", (2022, 4))):
        check(f"quarter from {name!r}", K._quarter_from_name(name), want)

    for bad in ("kenya_qlfs.pdf", "labour-report.pdf", "kenya_2022.pdf"):
        try:
            K._quarter_from_name(bad)
            FAILURES.append(f"undatable filename {bad!r} did not raise")
        except ValueError:
            pass

    # The three column groups follow from the report's own quarter, in the
    # (year-ago, previous, current) order every issue prints.
    check("quarters for 2022 Q4", [p for p, _ in K._quarters_for(2022, 4)],
          ["2021-Q4", "2022-Q3", "2022-Q4"])
    check("quarters for 2020 Q1", [p for p, _ in K._quarters_for(2020, 1)],
          ["2019-Q1", "2019-Q4", "2020-Q1"])
    check("quarters for 2021 Q1", [p for p, _ in K._quarters_for(2021, 1)],
          ["2020-Q1", "2020-Q4", "2021-Q1"])

    # ... and a rebuilt layout carries them through to its columns.
    cfg = K._layout_for(2020, 1)
    check("rebuilt layout period", cfg["period"], "2020-Q1")
    t2 = next(t for t in cfg["tables"]
              if t.get("blocks") and t["blocks"][0]["id"] == "t2")
    check("rebuilt column periods",
          sorted({c["period"] for c in t2["columns"] if not c.get("skip")}),
          ["2019-Q1", "2019-Q4", "2020-Q1"])


def test_kenya_captions_survive_knbs_renaming():
    """KNBS RENAMED TWO TABLES MID-SERIES, and the tokens must not care.

    Table 5 is "Unemployment (under relaxed definition) ... [LU3]" in 2020
    Q1-Q2 and "Combined rate of Unemployment and Potential Labour Force ...
    [LU3]" from 2020 Q3. Table 6 is hyphenated ("Time Related Under-employment")
    in every issue except 2022 Q4. A token written for one vintage silently
    drops that table from the others.
    """
    from indicators.unemployment.parsers import LAYOUTS
    tbls = {t["blocks"][0]["id"]: t for t in LAYOUTS["kenya"]["tables"]
            if t.get("blocks")}

    headings = {
        "t5": ["Table 5: Unemployment (under relaxed definition) by Age Cohorts [LU3]",
               "Table 5: Combined rate of Unemployment and Potential Labour Force by Age Cohorts [LU3]"],
        "t6": ["Table 6: Unemployment and Time Related Under-employment by Age Cohorts [LU2]",
               "Table 6: Unemployment and Time Related Underemployment by Age Cohorts [LU2]"],
    }
    for tid, lines in headings.items():
        token = tbls[tid]["page_contains"][0]
        rx = tbls[tid]["blocks"][0]["match"]
        for line in lines:
            check(f"{tid} page token vs {line[:34]!r}", token in line.lower(), True)
            check(f"{tid} block regex vs {line[:34]!r}",
                  bool(re.search(rx, line, re.I)), True)


def test_no_row_spec_goes_unmatched():
    """A SPEC THAT MATCHES NOTHING IS HOW A LAYOUT ROTS QUIETLY.

    The parser prints its misses and carries on, which is right in production.
    Here it is not: each fixture below is the page its table is printed on, so
    every row spec in that table must fire. This is the check that would have
    caught a renamed label or a changed caption before a run shipped a
    half-empty table.
    """
    for country, pages, tables, label in (
        ("kenya", [KENYA_TABLES_2_3], [1, 2], "Kenya tables 2 and 3"),
        ("namibia", [NAMIBIA_PAGE], None, "Namibia table 0.1"),
        ("zambia", [ZAMBIA_PAGE], None, "Zambia summary"),
        ("rwanda", [RWANDA_PAGE], None, "Rwanda trends"),
    ):
        missed = unmatched(country, pages, tables)
        check(f"no unmatched specs -- {label}", missed, [])


# ---------------------------------------------------------------------------
# Angola -- a headline repeated across two workbooks that disagree slightly
# ---------------------------------------------------------------------------
def _angola_books(repeat_rate: float) -> tuple[str, str]:
    """A SERIES and a QUADROS workbook in INE's layout, one quarter (2025 IV
    trim, new basis). Values VERBATIM from INE; `repeat_rate` is what the
    QUADROS 'Taxa de desemprego' sheet prints for the national row."""
    import os
    import tempfile
    import openpyxl
    d = tempfile.mkdtemp()
    hdr = [[None, 2025], [None, "IV trim"]]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PRINCIPAIS INDICADORES IEA "
    for r in [["Indicadores sobre emprego e desemprego"]] + hdr + [
            ["População com 15 ou mais anos", 22424975],
            ["Taxa de desemprego", 20.210575970751428]]:
        ws.append(r)
    series = os.path.join(d, "3.SERIES CRONOLOGICAS_IEA (NOVA).xlsx")
    wb.save(series)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for sheet, val in (("Taxa da força de trabalho", 49.598919062340094),
                       ("Taxa de emprego", 39.58376631412075),
                       ("Taxa de emprego informal", 78.5573514295602),
                       ("Taxa de desemprego", repeat_rate)):
        ws = wb.create_sheet(sheet)
        for r in [[sheet]] + hdr + [["Angola", val], ["Sexo", None],
                                    ["Homens", 18.42]]:
            ws.append(r)
    quadros = os.path.join(d, "4.QUADROS COMPLEMETARES_IEA (NOVA).xlsx")
    wb.save(quadros)
    return series, quadros


def test_angola_repeated_headline():
    """INE repeats the headline in the complementary workbook; the repeat is a
    CHECK, never a second row. Its published 0,02-point gap (20,192 against
    20,211) is tolerated with the series value kept; a gap beyond 0,1 raises."""
    from indicators.unemployment.parsers import angola_ine_workbooks as A
    series, quadros = _angola_books(20.19151)
    rows = A._series(series, A.SURVEY_NEW)
    head = {(r["topic"], r["period"], r["age_group"], r["working_age_base"]):
            r["value"] for r in rows}
    cuts = A._rates(quadros, A.SURVEY_NEW, head)
    ur = [r for r in rows + cuts if r["topic"] == "unemployment_rate"
          and r["sex"] == "total"]
    check("ao one national rate", len(ur), 1)
    check("ao series value kept", round(ur[0]["value"], 3), 20.211)
    check("ao male cut kept",
          [r["value"] for r in cuts if r["topic"] == "unemployment_rate"],
          [18.42])

    _, far = _angola_books(21.5)
    try:
        A._rates(far, A.SURVEY_NEW, head)
        FAILURES.append("ao: a 1,3-point disagreement passed the repeat check")
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Liberia -- Table 3.1 read by position, proved by its own arithmetic
# ---------------------------------------------------------------------------
def test_liberia_positional_rows_are_proved():
    """The LISGIS copy wraps labels so badly that Table 3.1 is read by row
    POSITION. That is only safe because the mapping is checked: a slipped row
    must break LF = E + U or LU1 = U/LF and raise. The Total column is used
    (verbatim), padded to 17 columns."""
    from indicators.unemployment.parsers import liberia_unemployment as L
    total = {"wap": 2355060, "lf": 615549, "emp": 538902, "unemp": 76647,
             "olf": 1739511, "inf_n": 467318, "form_n": 71584,
             "employees_n": 161633, "self_n": 361644, "lu_n": 178144,
             "lu_unemp": 76647, "tru_n": 59775, "plf_n": 41722, "lfpr": 26.1,
             "epr": 22.9, "tru": 9.7, "inf_pct": 86.7, "form_pct": 13.3,
             "employees_pct": 30.0, "self_pct": 67.1, "lu1": 12.5,
             "lu2": 22.2, "lu3": 18.0, "lu4": 27.1}
    good = [[float(total[k])] * 17 for k in L._SEQ]
    orig = L._table_3_1_lines
    try:
        L._table_3_1_lines = lambda path: [r[:] for r in good]
        df = L.parse_positional("stub.pdf")
        check("lr LU1", df[(df.series_label == "LU1: Unemployment rate")].value.iloc[0], 12.5)
        slipped = [r[:] for r in good]
        slipped[2], slipped[3] = slipped[3], slipped[2]     # employed <-> unemployed
        L._table_3_1_lines = lambda path: slipped
        try:
            L.parse_positional("stub.pdf")
            FAILURES.append("lr: a swapped employed/unemployed row was not caught")
        except ValueError:
            pass
    finally:
        L._table_3_1_lines = orig


def main() -> int:
    for fn in (test_numbers, test_periods, test_namibia, test_zambia,
               test_nigeria, test_ghana_pxweb, test_niger_blocks,
               test_liberia_wide, test_botswana_typos_and_bases,
               test_rwanda_period_columns, test_tunisia_html_parser,
               test_kenya_list_of_tables_does_not_open_a_block,
               test_kenya_cohorts_and_quarter_columns,
               test_kenya_lu2_contradiction_is_preserved,
               test_kenya_backfill_dates_each_file_from_its_name,
               test_kenya_captions_survive_knbs_renaming,
               test_no_row_spec_goes_unmatched,
               test_validator_rejects_garbage,
               test_no_silent_undated_output,
               test_angola_repeated_headline,
               test_liberia_positional_rows_are_proved):
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
