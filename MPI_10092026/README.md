# Multidimensional Poverty Index (MPI) — NSO collector

Harvests MPI statistics **strictly from African National Statistics Office
websites**. Aggregators are not sources: no ILOSTAT, no World Bank, no IMF, no
Knoema — and for this indicator, **OPHI and UNDP's HDR are aggregators too**,
which matters more here than anywhere else, because they are where almost every
African MPI figure in circulation actually lives.

---

## The headline finding: these are national MPIs, not the global MPI

You asked for the local/global distinction. It is the `mpi_type` column, and
the answer across the whole continent is lopsided:

> **Nearly every MPI an African NSO publishes on its own site is a NATIONAL
> ("local") measure — but not quite every one.** All 17 collected measures are
> national. Two of the reports carrying them also reprint the GLOBAL MPI
> alongside, as a comparison, and those columns are harvested separately and
> tagged `mpi_type: global`.

The global MPI (Alkire–Foster, 3 dimensions, 10 indicators, k = 33.3%,
harmonised across ~110 countries) is computed by OPHI and published through
OPHI's country briefings and UNDP's Human Development Report. **No African NSO
produces a global MPI of its own.** What two of them do is reprint OPHI's,
inside their own national report:

* **Botswana** — Appendix 5 of the Pilot National MPI report prints, for all
  26 districts and the nation, three side-by-side columns: monetary poverty,
  the **2020 global MPI** (credited to Alkire, Kanagaratnam and Suppa), and
  Botswana's own pilot national MPI. That is 27 rows of global-MPI incidence
  on `statsbots.org.bw`, and it is the substantial global series in this
  package. National global MPI incidence: **17.20%**, against Botswana's own
  national **20.84%**.
* **Nigeria** — a single comparison line quoting the 2018 global MPI
  (H 46.4%, M0 0.254) against NBS's own 2022 result.

Both are quotations of OPHI's number, published by the NSO. They are kept
because they are on the NSO's own site and because the whole point of the
`mpi_type` column is to keep them apart from the national measure printed
three inches away on the same page.

So `mpi_type` is not decorative: it is the column that stops a national
measure from being read as, or joined to, the global one. They are not
comparable. Each national MPI uses its own dimensions, its own indicators, its
own weights and its own poverty cutoff k, chosen to fit that country's policy
questions.

**How the distinction is enforced, not just recorded.**
`schema.validate_mpi` and `tests/check_registry.py` both refuse a row or a
descriptor declaring `mpi_type: global` unless it has exactly 3 dimensions and
10 indicators — that is what "the global MPI" means. A mislabelled national
measure cannot reach a CSV.

That rule is necessary but not sufficient, and one country proves it:
**Morocco's HCP measure is 3 dimensions, 10 indicators, k = 33% — the global
MPI's exact shape — and is still a national measure.** Its indicators are
census variables (scolarisation 6–14, handicap, conditions de logement), not
OPHI's. Shape alone never settles it; the descriptor's `notes` records the
authorship, which is what actually settles it. Eswatini's CSO measure (3 dims,
9 indicators, k = 33%) is a second near-twin, and is excluded for other
reasons — see `PENDING.md`.

---

## Coverage

**14 live descriptors, 14 countries**, plus 4 in `sources_blocked/` — kept
whole, so that restoring one is a file move rather than a rewrite.

The blocked four were each demoted on evidence from a real run, not on a
guess:

| Blocked | Why | What would unblock it |
|---|---|---|
| Egypt | `censusinfo.capmas.gov.eg` no longer resolves — DNS NXDOMAIN, not a 404 | CAPMAS restoring the host |
| Ghana (`ghana_report`) | GSS rebuilt its site; the catalogue still lists the 2020 report but every entry's `fileUrl` is `"#"` | GSS attaching the files |
| Morocco | The publication is a 263-page, 307 MB **map atlas**: the IPM figures live inside the map plates. HCP's per-region volumes were checked too — same shape | OCR, or HCP publishing the table |
| Somalia | Tables 3.1–3.3 are **raster images**; the numbers exist only in the executive summary's prose | OCR, or SNBS republishing with text |

Morocco and Somalia are the same class of problem and the same decision:
whether an OCR'd figure still counts as "exactly as published" for this
collector is a policy call, and until it is made, loosening a regex to scrape
narrative sentences would be the wrong way to appear to have coverage. Both
layouts are kept.

| Country | Measure | Type | Survey | k | dims | ind. | unit | ref. |
|---|---|---|---|---|---|---|---|---|
| Angola | IPM-A | national | IIMS 2015-16 | 30 | 4 | 16 | person | 2016 |
| Botswana | Pilot National MPI | national | BMTHS 2015/16 | 40 | 4 | 15 | person | 2016 |
| Burkina Faso | IPM local | national | RGPH 2019 | 38 | 5 | 21 | person | 2019 |
| Ghana | Ghana MPI (PHC 2021) | national | PHC 2021 census | 33.3 | 3 | 13 | person | 2021 |
| Guinea | Pauvreté multidim. (RGPH3) | national | RGPH3 2014 | 33.33 | 3 | 9 | **household** | 2014 |
| Madagascar | IPM Madagascar | national | MICS6 2018 | 33.3 | 3 | 14 | person | 2018 |
| Mali | IPM-Mali | national | EMOP 2023 | **60** | 5 | 19 | person | 2023 |
| Mauritius | Mauritius National MPI | national | Census 2022 | 30 | 5 | 15 | person | 2022 |
| Nigeria | Nigeria MPI | national | MPIS 2021/22 | **25** | 4 | 15 | person | 2022 |
| Rwanda | Rwanda MPI | national | EICV7 | 33.3 | 4 | 13 | person | 2024 |
| Seychelles | Seychelles MPI | national | LFS Q3 2019 | **25** | 4 | 14 | person | 2019 |
| Sierra Leone | Sierra Leone MPI | national | MICS 2017 | 40 | 5 | 14 | person | 2017 |
| South Africa | **SAMPI** | national | Census 2011 (vs 2001) | 33.3 | 4 | 11 | **household** | 2011 |
| Uganda | Uganda MPI (census) | national | Census 2024 | 40 | 4 | 13 | person | 2024 |

The spread is the point. **k runs from 25% to 60%; dimensions from 3 to 5;
indicators from 9 to 21; the unit of analysis is the household in two
countries and the person in the rest.** Two national MPIs are no more
comparable to each other than either is to the global one. That is why
`k_cutoff`, `n_dimensions`, `n_indicators` and `unit_of_analysis` are
**mandatory on every row** — `_common.row()` raises if any is missing — rather
than being kept in a metadata file somebody forgets to join.

The remaining African countries either have no NSO MPI at all, or have one
their NSO did not publish on its own site. Both cases are recorded, with
evidence, in `PENDING.md`.

---

## Schema

30 columns, `schema.MPI_COLUMNS`. Beyond the usual identity and provenance
fields, the ones that carry the meaning:

* `mpi_type` — `national` | `global`.
* `measure_name` — the index's own published name (`SAMPI`, `IPM-A`, `IPM-Mali`).
  Countries name their measures, and the name is how a user finds the report.
* `metric` — a small Alkire–Foster vocabulary: `incidence_H`, `intensity_A`,
  `index_M0`, `censored_headcount`, `uncensored_headcount`, `contribution`,
  `vulnerable`, `severe_poverty`, `population_poor`, and the confidence bounds
  `incidence_H_ci_low/high`, `intensity_A_ci_low/high`, `index_M0_ci_low/high`
  — each bound names the estimate it brackets, so a table publishing all
  three intervals keeps its six bound rows distinct.
  Anything a country reports that does not fit is left out rather than bent.
* `k_cutoff`, `n_dimensions`, `n_indicators`, `unit_of_analysis` — the rule
  that produced the number.
* `survey`, `reference_period` — the survey and how it was printed
  (`"2015/16"`, `"Census 2011"`), separate from the numeric `period` year.
* `unit` — `percent` | `index` | `persons`. **M0 is not rescaled.** Morocco
  prints its index as a percentage; that row carries `unit: percent` and the
  published value, not a silently divided one.

`validate_mpi` range-checks M0 per unit, rejects a `k_cutoff` outside 1–100
(a k of `0.333` is a units bug, not a 33.3% cutoff), and enforces the
3-and-10 rule for `global`.

---

## Layout

```
indicators/mpi/
├── pipeline.py             # entry point: wires the MPI CONFIG into the shared core
├── schema.py               # COLUMNS (long format) + validate()
├── sources/                # one <country>.yaml descriptor per country
├── sources_blocked/        # descriptors kept, but whose source cannot be fetched
├── parsers/
│   ├── <country>_mpi.py    # one module per country: a declarative LAYOUT + parse
│   ├── mpi_tables.py       # make_parser() — reads a LAYOUT, walks the PDF
│   ├── _vocab.py           # column vocabularies shared across layouts
│   └── __init__.py         # REGISTRY (parser id -> parse) and LAYOUTS
├── tests/                  # registry + offline fixture checks (no network)
├── source_data/            # retained raw published files (audit trail)
└── out/                    # tidy <country>_mpi.csv outputs
```

Most countries publish MPI as a handful of PDF tables, so a country module is
not a bespoke scraper but a **declarative `LAYOUT`**: which pages the table is
on, what the columns mean in order, and which row labels to take. `mpi_tables.
make_parser(LAYOUT)` turns that into the `parse(path) -> DataFrame` every other
indicator's parser exposes. Ghana is the exception — it has a PxWeb API, so
`ghana_pxweb_mpi.py` is a normal hand-written parser with no `LAYOUT`.

Each module's docstring and comments carry the report's own column order and
the published cross-check values, so a column-order regression is visible
without reopening the PDF.

## Verify before touching the network

    PYTHONUTF8=1 py -W ignore -m indicators.mpi.tests.check_registry
    PYTHONUTF8=1 py -W ignore -m indicators.mpi.tests.test_offline
    PYTHONUTF8=1 py -W ignore -m indicators.mpi.tests.rebuild_ghana_offline

All three run offline.

`check_registry` asserts every descriptor's parser and discovery method
resolve, and that every measure declares a complete, sane methodology.

`test_offline` replays the **actual printed tables** of Mali, Botswana,
Guinea, Madagascar, Angola, Mauritius, Burkina Faso, Morocco, Egypt and
Uganda through the real parsers and the real schema validator. Every fixture
in that file is a VERBATIM extract from the PDF the collector downloaded from
the NSO — wrapped labels, stray spaces inside region names, confidence-interval
columns and all. That matters more than it sounds: the first version of the
file used tables reconstructed from research notes, and when the collector was
first run for real, **every single reconstruction had the wrong number of
columns.** A fixture that is not the real thing tests nothing.

Each case is a trap the run actually sprang:
Mali prints ten numbers per row, because every metric carries a 95% confidence
interval; Botswana wedges a standard-error column between H and A and wraps its
labels FORWARD, so "Kweneng" and "Kweneng" are told apart only by the next
line; Guinea puts the locality in the columns, prints M0 as a percentage, and
leaves Conakry's rural cells empty; Madagascar is an infographic whose chart
labels share lines with body prose; Angola's national table is transposed and
its incidence row leads with the cutoff itself; Mauritius leads with the index
and hides 166 rows behind a four-digit geographical code; Burkina prints region
then province, so the province is the last word before the numbers; Morocco's
M0 is a percentage; and Uganda is the plain `H | A | M0` control, where
`H × A = M0` is checked arithmetically.

`rebuild_ghana_offline` is the only end-to-end check on **real NSO data**: the
three StatsBank json-stat2 responses in `source_data/Ghana/` are already on
disk, so parse → normalise → validate → write replays exactly, with no
network. It independently verifies that the national row's 13 indicator
contributions sum to 100.0% — which they would not if the flat-array
coordinate decoding were wrong.

## Run

    PYTHONUTF8=1 py -W ignore -m indicators.mpi.pipeline ghana
    PYTHONUTF8=1 py -W ignore -m indicators.mpi.pipeline --all

Output lands in `out/<country>_mpi.csv`; the raw published file is retained
under `source_data/<Country>/` **before** parsing, so a country whose layout
fails still leaves its PDF behind — which is exactly what is needed to fix the
layout. Every layout in `parsers/<country>_mpi.py` carries the published cross-check
values in a comment, so a mis-parse is usually visible at a glance and a
column-order fix is one line.

---

## What this collector deliberately will not do

* **Recompute anything.** It never derives M0 from H × A, never converts a
  percentage to a decimal, never sums sub-national rows into a national one.
  Every value in the output is a number a national statistics office printed.
* **Chain incompatible editions.** Ghana's two MPIs, Uganda's 2022 survey-based
  and 2024 census-based editions, and Rwanda's EICV5 and EICV7 rounds each use
  different methodologies. The descriptors say so; the schema keeps `survey`
  and the methodology fields on every row so a naive time series is visibly
  wrong rather than quietly wrong.
* **Date a measure by its publication year.** MPI reports are unusually bad
  about this — Burkina's 2019 index sits in a `/2024-10/` upload folder under a
  December 2023 cover; Mali's 2024-titled bulletin describes 2021–22. `period`
  is pinned explicitly per country, and `mpi_tables._resolve_period` raises
  rather than guessing.
* **OCR a scanned PDF.** Mauritania's MPI brief has no text layer. The parser
  says so and stops, instead of loosening its regexes until something matches.
* **Take an NSO's measure from a non-NSO host.** Several genuine NSO-authored
  MPIs exist only on OPHI, UNDP or UNICEF. They are documented in `PENDING.md`
  as leads; they are not harvested.

---

## What the first real run changed

This package was built without network access to any NSO, so the layouts began
as reconstructions from research notes. The first live run downloaded the
actual PDFs, and the verdict was blunt: **seven of the seven layouts that got
as far as parsing had the wrong column structure.** Not subtly — Mali had ten
columns where the layout said four, Botswana was not transposed at all, Guinea
printed its index as a percentage.

None of them produced wrong numbers, because the schema validator caught every
one: M0 outside 0–1, a percentage above 100, a metric count below the expected
minimum. That is what those guards are for, and it is the reason this section
can be written honestly rather than discovered by a user six months from now.

The seven layouts have since been rewritten against the downloaded documents,
and `tests/test_offline.py` now replays their verbatim text. The remaining
caveats:

* **`nigeria`, `rwanda`, `seychelles`, `sierra_leone`, `somalia`,
  `south_africa`, `uganda`, `ghana_report` and `morocco` have still never been
  checked against a printed page.** Their reports had not downloaded when the
  run stopped. Expect the same class of failure and the same safe landing —
  a validator error naming the problem, with the PDF left in `source_data/`.
* **Morocco's PDF is 126 MB and its first download truncated**, so pdfplumber
  reports "Unexpected EOF". Re-run Morocco alone and let it finish.
* Two of Madagascar's severe-poverty rows (Haute Matsiatra, Sava) are dropped
  because their chart labels are glued to body prose carrying extra numbers.
  The parser reports the miss rather than guessing.

Sub-agent web research, separately, repeatedly produced *plausible* tables for
countries that have no MPI at all — invented table numbers, invented figures.
Every value now in `parsers/<country>_mpi.py` as a cross-check was read off a
document that was actually opened. Where a report could not be opened, the
country is in `PENDING.md` with the reason, not in `sources/` with a guess.
