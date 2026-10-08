"""Offline self-test for the MPI collector.

No network, no NSO files: it replays the ACTUAL printed lines of published MPI
tables through the real parsers, then puts the result through the real schema
validator.

Every replayed page here is VERBATIM from a PDF the collector downloaded from
the NSO itself. That distinction is the point of this file: an earlier version
used tables reconstructed from research notes, and when the collector was first
run for real, every single reconstruction turned out to have the wrong number of
columns. These fixtures were rebuilt from the downloaded documents.

The cases are chosen for the things that would otherwise fail silently:

* **Mali** — ten numbers per row, because every metric carries a 95% confidence
  interval, and a label ("Autres villes urbaines") wrapped around its own data.
* **Botswana** — a standard-error column wedged between H and A; labels that
  wrap FORWARD, so "Kweneng" and "Kweneng" are only told apart by the next
  line; and Appendix 5, which republishes the GLOBAL MPI.
* **Guinea** — locality in the columns rather than the rows, M0 printed as a
  PERCENTAGE, and Conakry's missing rural cells.
* **Madagascar** — an infographic whose chart labels share lines with body
  prose, so only the numeric run after a label may be read.
* **Angola** — a transposed national table whose incidence row carries the
  cutoff itself as its first number.
* **Mauritius** — the index FIRST, and 166 scanned rows behind a four-digit
  geographical code.
* **Burkina Faso** — rows printed as region-then-province, so the province is
  the last word before the numbers.
* **Morocco** — nine numeric columns, and M0 printed as a PERCENTAGE.
* **Uganda** — `M0 | H | A` plus a trailing population count, and age bands
  whose own labels are numbers.
* **Ghana PxWeb** — the json-stat2 decoder and its methodology plumbing.
* **The validator** — that it actually rejects a percentage M0 read as a
  decimal, a global tag on a non-global shape, and a missing cutoff.

    python -m indicators.mpi.tests.test_offline
"""
from __future__ import annotations
import copy
import datetime as dt
import sys

import pandas as pd

from indicators.mpi import schema
from indicators.mpi.parsers import mpi_tables as T
from indicators.mpi.parsers import _common as C
from indicators.mpi.parsers import LAYOUTS

FAILURES: list[str] = []


def check(name: str, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


# --- unit checks on the shared helpers ------------------------------------

def test_numbers():
    # FR/PT: comma decimal, space thousands (Mali, Angola).
    check("fr row", C.numbers_in("Rural 76,3 0,379 54,4 69,5", ","),
          [76.3, 0.379, 54.4, 69.5])
    check("fr thousands", C.numbers_in("Effectif 5 532 715", ","), [5532715.0])
    # EN: comma thousands, dot decimal.
    check("en row", C.numbers_in("National 53.1 50.9 0.270", "."),
          [53.1, 50.9, 0.270])
    check("en thousands", C.numbers_in("Poor 130,000 10.8", "."), [130000.0, 10.8])
    for token in ("-", "..", "n/a", ""):
        check(f"non-numeric {token!r}", C.to_number(token), None)


def test_localities():
    # Somalia's nomadic stratum is neither urban nor rural.
    check("nomadic", C.normalise_locality("Nomadic"), "other")
    check("rural", C.normalise_locality("Rural"), "rural")
    check("urbain", C.normalise_locality("Urbain"), "urban")
    check("urban villages", C.normalise_locality("Urban Villages"), "other")
    check("national", C.normalise_locality("National"), "all")
    check("female head", C.normalise_sex("Female-headed"), "female")
    check("male head", C.normalise_sex("Male-headed"), "male")


# --- end-to-end: replayed published tables ---------------------------------
#
# EVERY page below is a VERBATIM extract from the PDF the collector actually
# downloaded from the NSO, pasted exactly as pdfplumber renders it -- wrapped
# labels, stray spaces inside region names, confidence-interval columns and
# all. The first version of this file used tables reconstructed from research
# notes instead, and every one of those reconstructions turned out to have the
# wrong number of columns. A fixture that is not the real thing tests nothing.

MALI_MILIEU_PAGE = """
Milieu de résidence
Urbain 23,7 0,146 0,131 0,160 21,4 19,3 23,6 67,9 67,2 68,5
Bamako 12,1 0,083 0,062 0,103 12,6 9,4 15,7 65,8 64,6 67,0
Autres villes
11,7 0,211 0,191 0,230 30,6 27,8 33,5 68,7 68,1 69,4
urbaines
Rural 76,3 0,379 0,361 0,396 54,4 52,0 56,8 69,5 69,2 69,9
National 100,0 0,323 0,310 0,337 46,6 44,7 48,5 69,4 69,0 69,7
"""

MALI_REGION_PAGE = """
Région population Intervalle de
Ménaka
Kayes 13,7 0,413 0,376 0,450 58,7 53,7 63,7 70,4 69,5 71,2
Koulikoro 16,8 0,318 0,277 0,360 45,8 40,0 51,6 69,5 68,4 70,5
Sikasso 18,3 0,221 0,187 0,254 33,1 28,0 38,1 66,7 65,9 67,5
Ségou 16,3 0,338 0,302 0,375 49,9 44,7 55,1 67,9 67,0 68,8
Mopti 13,9 0,491 0,460 0,521 69,9 65,6 74,3 70,1 69,4 70,9
Tombouctou 4,6 0,415 0,386 0,443 59,4 55,5 63,3 69,8 69,0 70,6
Gao 2,6 0,350 0,301 0,399 49,6 42,9 56,3 70,6 69,4 71,9
Kidal 0,4 0,445 0,381 0,510 60,9 52,7 69,1 73,1 71,9 74,3
Taoudenni 0,1 0,449 0,325 0,572 62,9 45,9 80,0 71,3 70,1 72,5
Ménaka 1,1 0,767 0,712 0,822 93,4 87,6 99,1 82,1 80,8 83,4
Bamako 12,1 0,083 0,062 0,103 12,6 9,4 15,7 65,8 64,6 67,0
Mali 100,0 0,323 0,310 0,337 46,6 44,7 48,5 69,4 69,0 69,7
"""

BOTSWANA_STRATA_PAGE = """
Table 3.4.1 Multidimensional Poverty by Strata
Strata Incidence Standard Intensity (%) MPI Vulnerable Severe Population
Cities/Towns 5.34% 1.02% 47.64 0.025 7.97% 0.45% 19.60%
Urban 14.05% 1.27% 49.98 0.070 16.85% 2.07% 44.12%
Villages
Rural 37.48% 1.94% 51.85 0.194 19.15% 6.57% 36.28%
Areas.
National 20.84% 0.94% 51.09 0.106 15.94% 3.39% 100%
Source: Author, based on Statistics Botswana (BMTHS, 2015/16)
3.4.2 Censored headcount ratios
"""

BOTSWANA_APPENDIX5_PAGE = """
Appendix 5: Monetary, Global MPI and Pilot National MPI
District Monetary Global MPI National MPI
Barolong 13.70% 20.20% 14.19%
Central Bobonong 13.90% 19.80% 20.77%
Central Boteti 12.90% 31.20% 37.63%
Central Mahalapye 18.20% 25.30% 27.39%
Central Serowe 11.60% 22.60% 24.84%
Central Tutume 21.20% 30.70% 34.01%
National 16.30% 17.20% 20.84%
"""

GUINEA_PAGE = """
Tableau 2-1: Indice de pauvreté multidimensionnelle selon la région et le milieu de résidence
Urbain Rural Total Urbain Rural Total Urbain Rural Total
Boké 34,1 85,9 72,7 41,6 52,9 51,5 14,2 45,4 37,5
Conakry 16,8 - 16,8 40,8 - 40,8 6,8 - 6,8
Faranah 59,2 92,0 84,8 43,7 55,1 53,4 25,9 50,7 45,3
Kankan 60,3 94,7 87,8 43,7 56,3 54,5 26,4 53,3 47,9
Kindia 34,9 85,5 67,8 41,8 52,3 50,4 14,6 44,7 34,1
Labé 39,2 87,3 81,9 41,4 51,9 51,3 16,2 45,3 42,0
Mamou 35,4 87,5 80,5 41,2 50,4 49,9 14,6 44,1 40,1
Nzérékoré 57,6 79,8 74,6 44,4 51,9 50,5 25,6 41,4 37,7
Guinée 33,1 87,7 68,7 42,5 53,4 51,5 14,1 46,8 35,4
"""

MADAGASCAR_PAGE = """
Incidence, Intensité et Indice de pauvreté multidimensionnelle
Incidence de pauvreté Intensité de Indice de pauvreté
Les 3 indicateurs de pauvreté
Caractéristiques géographiques
Urb ain 50,3 50,9 0,256
Milieu présentent des variations presque
Rural 76,6 55,7 0,427
similaires selon la région et le
Androy 91,7 59,4 0,545
Ensemble du pays 70,3 54,9 0,386
"""

ANGOLA_PAGE = """
Quadro 2 - IPM-A, incidência e intensidade, IIMS 2015-2016
Linha de pobreza Descrição Valor Intervalo de confiança (95%)
IPM-A 0,264 0,252 0,276
30% Incidência (H, %) 54,0 51,7 56,3
Intensidade (A, %) 48,9 48,2 49,6
"""

MAURITIUS_PAGE = """
Table 2 – 2022 National MPI results by Island, Republic of Mauritius
Headcount Intensity of
MPI Ratio Poverty
Republic of Mauritius 0.041 10.8% 37.9%
Island of Mauritius 0.038 10.2% 37.5%
Island of Rodrigues 0.120 29.2% 41.2%
"""

BURKINA_PAGE = """
Tableau 1 : Incidence, intensité et indice de pauvreté multidimensionnelle selon les provinces
Centre Kadiogo 10,11 44,01 0,04
Hauts-Bassins Houet 20,62 44,47 0,09
Centre-Sud Bazèga 29,62 45,27 0,13
Boucle Du Mouhoun Bale 28,24 45,49 0,13
Centre-Sud Nahouri 29,53 45,68 0,13
Centre - Est Kouritenga 29,79 45,35 0,14
"""


MOROCCO_PAGE = """
Cartographie de la pauvreté multidimensionnelle, intensité et indice, 2024
Taux de pauvreté multidimensionnelle Intensité moyenne Indice de pauvreté
Urbain Rural Ensemble Urbain Rural Ensemble Urbain Rural Ensemble
National 3,0 13,1 6,8 35,3 39,1 36,7 1,1 5,1 2,5
Marrakech-Safi 4,2 12,0 7,9 35,0 39,0 37,4 1,5 4,7 3,0
Rabat-Salé-Kénitra 3,5 10,2 5,7 34,9 38,4 36,6 1,2 3,9 2,1
"""

EGYPT_PAGE = """
Multidimensional poverty in Egypt: MPI, incidence and intensity
Group MPI H (%) A (%) Population share (%)
National 0.077 21.2 36.5 100
Urban 0.042 11.9 35.1 42.1
Rural 0.103 28.0 36.9 57.9
Male-headed 0.079 21.8 36.5 86.7
Female-headed 0.064 17.7 36.4 13.3
"""

# Replayed from Table 2 of the UBOS monograph, in the report's ACTUAL shape:
# the INDEX leads, a household population count trails, the sex rows are
# labelled 'Male'/'Female' under a 'Sex' sub-head, and the age bands are
# themselves numbers. This fixture used to carry an invented `H | A | MPI`
# table with 'Male-headed' labels -- it passed against a layout that read the
# index as the incidence and Uganda's 44-million population as M0, because the
# fixture had been written to match the layout rather than the report.
UGANDA_PAGE = """
Table 2: Multidimensional Poverty in Uganda
Multidimensional Population
Poverty Index Headcount Intensity of Household
Characteristics (MPI=H*A) ratio (H) (A) Population 2024
Sex
Male 0.262 51.9 50.5 30,901,123
Female 0.289 55.9 51.8 13,237,434
Residence
Urban 0.193 39.1 49.3 16,151,542
Rural 0.315 61.1 51.5 27,987,015
Age of Household Head
10-19 0.280 55.4 50.4 556,256
80+ 0.317 61.1 52.0 1,182,922
Education Level of Household head
No formal education 0.435 78.3 55.5 10,683,113
Sub Region
Kampala 0.088 19.5 45.3 1,506,268
Buganda 0.182 37.1 49.1 10,440,451
West Nile 0.390 73.5 53.0 3,281,251
Karamoja 0.569 91.4 62.3 1,465,616
National 0.270 53.1 50.9 44,138,557**
"""


def run_layout(country: str, page: str, scan_expect: int | None = None):
    """Parse a replayed page with the country's real layout, monkeypatching
    only the PDF text extraction.

    `scan_expect` lowers the `expect_rows` guard on any `row_scan` table.
    That guard exists so a scan which quietly collects half a table fails
    loudly in production -- Mauritius expects 160 rows and Burkina 40. A
    fixture here is an EXCERPT of a few rows, so without this the guard would
    fire on every scanned country and the fixtures would have to grow to
    hundreds of lines to say nothing extra. The guard itself is never relaxed
    in the per-country layout modules.
    """
    cfg = copy.deepcopy(LAYOUTS[country])
    if scan_expect is not None:
        for tbl in cfg.get("tables", [cfg]):
            if tbl.get("row_scan"):
                tbl["row_scan"]["expect_rows"] = scan_expect
    orig = T._pages
    T._pages = lambda _path: [page]
    try:
        return T.make_parser(cfg)("<replay>")
    finally:
        T._pages = orig


def finish(df: pd.DataFrame, country: str) -> pd.DataFrame:
    """Attach the identity columns run.py would add, then validate for real."""
    df = df.copy()
    df["country"] = country
    df["iso3"] = "XXX"
    df["indicator"] = "MPI"
    df["source_type"] = "pdf"
    df["source_url"] = "https://example.invalid/replay"
    df["source_file"] = "replay.pdf"
    df["extracted_at"] = dt.datetime.now().isoformat(timespec="seconds")
    for col in schema.MPI_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return schema.validate_mpi(df)


def pick(df, metric, **kw):
    m = df["metric"] == metric
    for k, v in kw.items():
        m &= df[k] == v
    vals = df.loc[m, "value"].tolist()
    return vals[0] if len(vals) == 1 else vals


def test_mali():
    """Ten numbers per row -- value plus a 95% CI for each of M0, H and A --
    and a label that wraps around its own data."""
    df = finish(run_layout("mali", MALI_MILIEU_PAGE + MALI_REGION_PAGE), "Mali")
    nat = dict(geography="Total country", locality="all")
    check("ML national M0", pick(df, "index_M0", **nat), 0.323)
    check("ML national H", pick(df, "incidence_H", **nat), 46.6)
    check("ML national A", pick(df, "intensity_A", **nat), 69.4)
    check("ML rural M0", pick(df, "index_M0", locality="rural"), 0.379)
    check("ML rural H", pick(df, "incidence_H", locality="rural"), 54.4)
    check("ML urbain M0", pick(df, "index_M0", locality_label="Urbain"), 0.146)
    # The wrapped label was re-attached to its numbers.
    check("ML autres villes M0",
          pick(df, "index_M0", locality_label="Autres villes urbaines"), 0.211)
    check("ML Menaka M0", pick(df, "index_M0", geography="Ménaka"), 0.767)
    check("ML Mopti H", pick(df, "incidence_H", geography="Mopti"), 69.9)
    # The CI bounds must not have been read as measurements: 0,310 is the
    # national M0's lower bound and 0,337 its upper, and neither is a value.
    check("ML no CI leaked", {0.310, 0.337} & set(df.value), set())
    # Nor may the population-share column become a metric.
    check("ML no share leaked", 76.3 in set(df.value), False)
    check("ML k", set(df.k_cutoff), {60})
    check("ML M0 unit", set(df.loc[df.metric == "index_M0", "unit"]), {"index"})


def test_botswana_and_its_global_mpi():
    """A standard-error column between H and A, labels that wrap FORWARD, and
    the one appendix in this package that republishes the global MPI."""
    df = finish(run_layout("botswana",
                           BOTSWANA_STRATA_PAGE + BOTSWANA_APPENDIX5_PAGE,
                           scan_expect=0),
                "Botswana")
    nat = df[df.mpi_type == "national"]
    check("BW national H", pick(nat, "incidence_H", locality="all"), 20.84)
    check("BW national A", pick(nat, "intensity_A", locality="all"), 51.09)
    check("BW national M0", pick(nat, "index_M0", locality="all"), 0.106)
    # 0.94 is the standard error on the national incidence. If the column were
    # miscounted it would surface as the intensity.
    check("BW no std error leaked", 0.94 in set(nat.value), False)
    check("BW cities H", pick(nat, "incidence_H",
                              locality_label="Cities/Towns"), 5.34)
    check("BW urban villages H", pick(nat, "incidence_H",
                                      locality_label="Urban Villages"), 14.05)
    check("BW rural H", pick(nat, "incidence_H", locality="rural"), 37.48)
    check("BW vulnerable national", pick(nat, "vulnerable", locality="all"), 15.94)
    check("BW severe rural", pick(nat, "severe_poverty", locality="rural"), 6.57)
    # Urban Villages must not have collapsed into "urban".
    check("BW localities", sorted(set(nat.locality)),
          ["all", "other", "rural", "urban"])

    # --- the global MPI half -------------------------------------------
    g = df[df.mpi_type == "global"]
    check("BW global national H", pick(g, "incidence_H",
                                       geography="Total country"), 17.2)
    check("BW global Kweneng-free sample",
          pick(g, "incidence_H", geography="Central Boteti"), 31.2)
    # The global MPI is 3 dimensions and 10 indicators BY DEFINITION, and the
    # validator refuses the tag on anything else.
    check("BW global shape", (set(g.n_dimensions), set(g.n_indicators)),
          ({3}, {10}))
    # The monetary column is not an MPI and must not have been captured:
    # Barolong's monetary rate is 13.70 and its global MPI 20.20.
    check("BW monetary excluded", 13.7 in set(g.value), False)
    check("BW global count", len(g), 7)


def test_guinea_percent_m0_and_missing_cells():
    """Locality in the COLUMNS, the index printed as a percentage, and one row
    with three cells missing."""
    df = finish(run_layout("guinea", GUINEA_PAGE), "Guinea")
    check("GN national M0 total",
          pick(df, "index_M0", geography="Total country", locality="all"), 35.4)
    check("GN national H total",
          pick(df, "incidence_H", geography="Total country", locality="all"), 68.7)
    check("GN national M0 rural",
          pick(df, "index_M0", geography="Total country", locality="rural"), 46.8)
    check("GN Kankan M0 rural",
          pick(df, "index_M0", geography="Kankan", locality="rural"), 53.3)
    # 68,7 x 51,5 = 35,4: the index really is a percentage here, and must
    # carry that unit rather than being divided by 100 to look tidy.
    check("GN M0 unit", set(df.loc[df.metric == "index_M0", "unit"]), {"percent"})
    # Conakry has no rural population; its three rural cells are printed "-".
    # They must be ABSENT, not filled by shifting the total leftwards.
    ck = df[df.geography == "Conakry"]
    check("GN Conakry localities", sorted(set(ck.locality)), ["all", "urban"])
    check("GN Conakry M0 total",
          pick(df, "index_M0", geography="Conakry", locality="all"), 6.8)
    check("GN indicators", set(df.n_indicators), {9})


def test_madagascar_infographic():
    """Chart labels share lines with body prose, so only the numeric run that
    follows a row's own label may be read."""
    df = finish(run_layout("madagascar", MADAGASCAR_PAGE), "Madagascar")
    nat = dict(geography="Total country", locality="all")
    check("MG national H", pick(df, "incidence_H", **nat), 70.3)
    check("MG national A", pick(df, "intensity_A", **nat), 54.9)
    check("MG national M0", pick(df, "index_M0", **nat), 0.386)
    check("MG urbain M0", pick(df, "index_M0", locality="urban"), 0.256)
    check("MG rural H", pick(df, "incidence_H", locality="rural"), 76.6)
    # "Urb ain" -- pdfplumber splits the word; the pattern tolerates it.
    check("MG urbain label", pick(df, "intensity_A", locality="urban"), 50.9)
    check("MG Androy M0", pick(df, "index_M0", geography="Androy"), 0.545)
    check("MG H x A = M0", round(70.3 * 54.9 / 10000, 3),
          pick(df, "index_M0", **nat))


def test_angola_transposed_national():
    """Metrics in rows, and the incidence row leads with the CUTOFF itself."""
    df = finish(run_layout("angola", ANGOLA_PAGE, scan_expect=0), "Angola")
    check("AO M0", pick(df, "index_M0"), 0.264)
    check("AO H", pick(df, "incidence_H"), 54.0)
    check("AO A", pick(df, "intensity_A"), 48.9)
    # "30% Incidência (H, %) 54,0 ..." -- the 30 is k, not a measurement.
    check("AO cutoff not a value", 30.0 in set(df.value), False)
    check("AO k", set(df.k_cutoff), {30})


def test_mauritius_index_first():
    """`MPI | Headcount Ratio | Intensity` -- the index leads."""
    df = finish(run_layout("mauritius", MAURITIUS_PAGE, scan_expect=0), "Mauritius")
    check("MU republic M0", pick(df, "index_M0", geography="Total country"), 0.041)
    check("MU republic H", pick(df, "incidence_H", geography="Total country"), 10.8)
    check("MU republic A", pick(df, "intensity_A", geography="Total country"), 37.9)
    check("MU rodrigues M0",
          pick(df, "index_M0", geography="Island of Rodrigues"), 0.120)
    check("MU mainland H",
          pick(df, "incidence_H", geography="Island of Mauritius"), 10.2)
    check("MU k", set(df.k_cutoff), {30})


def test_burkina_region_then_province():
    """Rows read `region province H A M0`, so the province is the last word
    before the numbers and the region prefix is discarded."""
    df = finish(run_layout("burkina_faso", BURKINA_PAGE, scan_expect=6), "Burkina Faso")
    check("BF Kadiogo H", pick(df, "incidence_H", geography="Kadiogo"), 10.11)
    check("BF Kadiogo A", pick(df, "intensity_A", geography="Kadiogo"), 44.01)
    check("BF Kadiogo M0", pick(df, "index_M0", geography="Kadiogo"), 0.04)
    check("BF Houet M0", pick(df, "index_M0", geography="Houet"), 0.09)
    # "Boucle Du Mouhoun Bale" must land under the PROVINCE, not the region.
    check("BF Bale M0", pick(df, "index_M0", geography="Bale"), 0.13)
    check("BF no region rows", "Boucle Du Mouhoun" in set(df.geography), False)
    check("BF rows", len(set(df.geography)), 6)


def test_morocco_percent_m0():
    """Nine columns, and M0 printed as a PERCENTAGE -- the case the schema's
    per-unit range check exists for."""
    df = finish(run_layout("morocco", MOROCCO_PAGE), "Morocco")
    check("MA national H ensemble",
          pick(df, "incidence_H", geography="Total country", locality="all"), 6.8)
    check("MA national H urbain",
          pick(df, "incidence_H", geography="Total country", locality="urban"), 3.0)
    check("MA national H rural",
          pick(df, "incidence_H", geography="Total country", locality="rural"), 13.1)
    check("MA national A ensemble",
          pick(df, "intensity_A", geography="Total country", locality="all"), 36.7)
    check("MA national IPM ensemble",
          pick(df, "index_M0", geography="Total country", locality="all"), 2.5)
    check("MA Marrakech IPM",
          pick(df, "index_M0", geography="Marrakech-Safi", locality="all"), 3.0)
    # The whole point: M0 carries unit 'percent', not 'index'.
    check("MA M0 unit", set(df.loc[df.metric == "index_M0", "unit"]), {"percent"})


def test_egypt_index_first():
    """`MPI | H | A | share` -- the index FIRST, and seven dimensions."""
    df = finish(run_layout("egypt", EGYPT_PAGE), "Egypt")
    check("EG national M0", pick(df, "index_M0", locality="all", sex="total"), 0.077)
    check("EG national H", pick(df, "incidence_H", locality="all", sex="total"), 21.2)
    check("EG rural M0", pick(df, "index_M0", locality="rural"), 0.103)
    check("EG female-headed M0", pick(df, "index_M0", sex="female"), 0.064)
    check("EG male-headed H", pick(df, "incidence_H", sex="male"), 21.8)
    check("EG dims", set(df.n_dimensions), {7})
    check("EG k", set(df.k_cutoff), {29})
    # The population-share column must not have leaked in as a metric.
    check("EG no share leaked", 100.0 in set(df.value), False)


def test_uganda_control():
    """M0-leading columns, a trailing population count, and numeric row labels."""
    df = finish(run_layout("uganda", UGANDA_PAGE), "Uganda")
    # `geography` AND `topic` must both be pinned here. The sub-region rows
    # carry locality 'all' and sex 'total', so those two filters alone match
    # every region; and the age-of-head and education-of-head rows are national
    # too, so geography does not separate them either. Only `topic='total'`
    # says "the undisaggregated national headline". This assertion was
    # under-specified until Table 2's age and education blocks were read, which
    # is the failure mode the note above was written about.
    check("UG national",
          pick(df, "index_M0", geography="Total country", topic="total",
               locality="all", sex="total"), 0.270)
    check("UG rural H", pick(df, "incidence_H", locality="rural"), 61.1)
    check("UG Karamoja M0", pick(df, "index_M0", geography="Karamoja"), 0.569)
    check("UG female-headed A", pick(df, "intensity_A", sex="female"), 51.8)
    check("UG base", set(df.unit_of_analysis), {"person"})
    # H x A should reproduce M0 to rounding -- a free arithmetic check.
    h = pick(df, "incidence_H", geography="Karamoja")
    a = pick(df, "intensity_A", geography="Karamoja")
    m0 = pick(df, "index_M0", geography="Karamoja")
    check("UG Karamoja H*A=M0", round(h * a / 10000, 3), m0)


def test_ghana_pxweb():
    """Replay a miniature json-stat2 response in StatsBank's shape and prove
    the coordinate decoding plus the methodology plumbing."""
    import json
    import os
    import tempfile
    from indicators.mpi.parsers import ghana_pxweb_mpi as G

    dims = ["poverty_measure", "sex_head_of_household", "Geographic_Area"]
    cats = {
        "poverty_measure": ["Incidence of Poverty (H)", "Intensity of Poverty (A)",
                            "Multidimensional Poverty Index (M0)"],
        "sex_head_of_household": ["Total", "Male", "Female"],
        "Geographic_Area": ["Ghana", "Ashanti", "Ada East"],   # last is a district
    }
    sizes = [len(cats[d]) for d in dims]
    n = sizes[0] * sizes[1] * sizes[2]
    # Values chosen so M0 stays inside [0, 1] and H/A inside [0, 100].
    vals = []
    for pm in range(sizes[0]):
        for _sx in range(sizes[1]):
            for _ga in range(sizes[2]):
                vals.append(0.25 if pm == 2 else 40.0)
    doc = {"id": dims, "size": sizes,
           "dimension": {d: {"category": {"index": {v: i for i, v in
                                                    enumerate(cats[d])}}}
                         for d in dims},
           "value": vals}

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ghana_mpi_by_sex.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        spec = {"path": path, "topic": "sex_of_head", "mpi_type": "national",
                "measure_name": "Ghana MPI (PHC 2021)", "survey": "PHC 2021",
                "k_cutoff": 33.3, "n_dimensions": 3, "n_indicators": 13,
                "unit_of_analysis": "person", "period": 2021,
                "reference_period": "Census 2021", "frequency": "ad_hoc"}
        df = finish(G.parse([spec]), "Ghana")

    # 3 metrics x 3 sexes x 2 kept geographies -- the district must be dropped.
    check("GH rows", len(df), 18)
    check("GH geographies", sorted(set(df.geography)), ["Ashanti", "Total country"])
    check("GH no district", "Ada East" in set(df.geography), False)
    check("GH metrics", sorted(set(df.metric)),
          ["incidence_H", "index_M0", "intensity_A"])
    check("GH sexes", sorted(set(df.sex)), ["female", "male", "total"])
    check("GH M0 unit", set(df.loc[df.metric == "index_M0", "unit"]), {"index"})
    check("GH k travelled", set(df.k_cutoff), {33.3})
    check("GH type", set(df.mpi_type), {"national"})

    # An unmapped poverty_measure must RAISE, not vanish.
    doc2 = dict(doc)
    doc2["dimension"] = dict(doc["dimension"])
    doc2["dimension"]["poverty_measure"] = {
        "category": {"index": {"Some New Measure": 0, "Intensity of Poverty (A)": 1,
                               "Multidimensional Poverty Index (M0)": 2}}}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ghana_mpi_by_sex.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc2, f)
        try:
            G.parse([dict(spec, path=path)])
            FAILURES.append("ghana parser silently dropped an unmapped measure")
        except ValueError as e:
            if "unmapped" not in str(e):
                FAILURES.append(f"ghana parser raised the wrong error: {e}")


def test_validator_guards():
    """The guardrails must actually fire."""
    df = finish(run_layout("uganda", UGANDA_PAGE), "Uganda")

    # A percentage M0 mislabelled as a decimal index.
    bad = df.copy()
    i = bad.index[(bad.metric == "index_M0")][0]
    bad.loc[i, "value"] = 2.5
    bad.loc[i, "unit"] = "index"
    try:
        schema.validate_mpi(bad)
        FAILURES.append("validator accepted an index_M0 of 2.5 with unit 'index'")
    except Exception:
        pass

    # A national measure relabelled global without the global shape.
    bad2 = df.copy()
    bad2["mpi_type"] = "global"
    try:
        schema.validate_mpi(bad2)
        FAILURES.append("validator accepted mpi_type 'global' on a 4-dim/13-ind measure")
    except Exception:
        pass

    # A genuine global shape must be accepted.
    ok = df.copy()
    ok["mpi_type"] = "global"
    ok["n_dimensions"] = 3
    ok["n_indicators"] = 10
    ok["k_cutoff"] = 33.3
    try:
        schema.validate_mpi(ok)
    except Exception as e:
        FAILURES.append(f"validator rejected a legitimate global MPI: {e}")

    # A missing cutoff.
    bad3 = df.copy()
    bad3["k_cutoff"] = None
    try:
        schema.validate_mpi(bad3)
        FAILURES.append("validator accepted rows with no k_cutoff")
    except Exception:
        pass

    # k given as a fraction rather than a percentage.
    bad4 = df.copy()
    bad4["k_cutoff"] = 0.4
    try:
        schema.validate_mpi(bad4)
        FAILURES.append("validator accepted k_cutoff 0.4 (a fraction, not a percent)")
    except Exception:
        pass

    # An incidence above 100%.
    bad5 = df.copy()
    j = bad5.index[(bad5.metric == "incidence_H")][0]
    bad5.loc[j, "value"] = 153.0
    try:
        schema.validate_mpi(bad5)
        FAILURES.append("validator accepted an incidence of 153%")
    except Exception:
        pass


def test_row_scan_guard_fires():
    """The `expect_rows` guard is the only thing standing between a scanned
    table and silently shipping a fraction of it, so prove it actually fires:
    Burkina's real layout expects 40 provinces, and this excerpt has six."""
    try:
        run_layout("burkina_faso", BURKINA_PAGE)     # no scan_expect override
        FAILURES.append("row_scan accepted 6 rows where the layout expects 40")
    except ValueError as e:
        if "expect_rows" not in str(e) and "expects at least" not in str(e):
            FAILURES.append(f"row_scan raised the wrong error: {e}")


def test_no_silent_undated_output():
    """A layout with neither a fixed period nor a matching pattern must raise
    rather than dating the measure to whatever year it can find -- MPI reports
    routinely carry three different years."""
    cfg = dict(LAYOUTS["uganda"])
    cfg.pop("period", None)
    cfg.pop("period_patterns", None)
    orig = T._pages
    T._pages = lambda _p: [UGANDA_PAGE]
    try:
        T.make_parser(cfg)("<replay>")
        FAILURES.append("parser dated an undatable measure instead of raising")
    except ValueError:
        pass
    finally:
        T._pages = orig


def main() -> int:
    for fn in (test_numbers, test_localities,
               test_mali, test_botswana_and_its_global_mpi,
               test_guinea_percent_m0_and_missing_cells,
               test_madagascar_infographic, test_angola_transposed_national,
               test_mauritius_index_first, test_burkina_region_then_province,
               test_morocco_percent_m0, test_egypt_index_first,
               test_uganda_control, test_ghana_pxweb, test_validator_guards,
               test_row_scan_guard_fires,
               test_no_silent_undated_output):
        try:
            fn()
        except Exception as e:
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
