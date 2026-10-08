# CPI — Africa CPI Collector

Harvests **Consumer Price Index** and inflation from African National Statistics
Offices (NSOs) into one tidy, long-format dataset, captured **exactly as each NSO
publishes it** — native classifications and full historical series, with no
estimation, imputation or omission.

**Status:** 52 of 54 countries collected. The two outstanding are **Eswatini**
(eswatinistats.org.sz resolves but the host has not answered; no central-bank or
government mirror carries the CPI, and the legacy swazistats.org.sz domain is gone)
and **Eritrea** (no national statistics office or central bank site exists online —
only aggregators carry Eritrean inflation, and those are excluded as sources).
See the progress report for the full picture:

**Collector health (full `--all` run, 7 Sep 2026):** 52 descriptors, 49 collecting.
Three sources cannot be fetched, each for a reason outside this code:

- **Cote d'Ivoire** — anstat.ci sits behind a Cloudflare JS challenge that refuses
  every TLS fingerprint, the published files included.
- **Liberia** — LISGIS is rebuilding its site. The old content (`/pricestats.php`
  and `/admin_area/…`) now 404s, and the placeholder page links only to an
  aggregator portal, which this project excludes as a source. Nothing of LISGIS's
  own is currently served; the May 2026 output already collected is retained.
- **Central African Republic** — ICASEES' site appears COMPROMISED. Its edocman
  download route returns an empty body to a browser user-agent, but serves a
  cloaked Japanese e-commerce spam page (~425 KB) to any user-agent containing
  'bot' — the signature of an SEO-spam injection, not a bulletin. Do not try to
  work around it. Its July 2025 bulletin is the newest ICASEES published and that
  month is already in `out/`; the descriptor is left pointing at the legitimate
  route so collection resumes if the site is cleaned up.

Their existing outputs are intact — the harness writes only on success.

**Outputs accumulate.** A run MERGES into `out/<country>_cpi.csv` rather than
replacing it: keyed on `coicop_code + geography + period + measure`, the rows a run
produces win and rows it did not produce are kept. This is what makes the "history
accumulates across monthly runs" note in many descriptors true — most NSOs publish
one month per document, so without it each run would discard everything collected
before. It also protects against a source that loses its own back-issues: when INS
Congo's 2026 site rebuild dropped March–May 2026, the merge kept those months and
added the new February 2026 one. Revisions still propagate, because a rerun of the
same period overwrites its own rows, and `source_url` / `source_file` /
`extracted_at` are per-row, so mixed provenance stays auditable (Kenya's file
carries the CBK headline series back to 2005 alongside KNBS's current-month
divisions). Where a merge splices index levels across a rebase, the run says so.

- `Africa_CPI_Collector_Progress_Report.docx` — narrative (work done, challenges, outstanding)
- `Africa_CPI_Collector_Progress_Report.xlsx` — 4 sheets (Executive Summary, Country Status, Challenges & Remedies, Outstanding & Next Steps)

## Layout

```
indicators/cpi/
├── pipeline.py          # entry point: wires the CPI CONFIG into the shared core
├── schema.py            # COLUMNS (long format) + validate()
├── coicop.py            # COICOP division vocabulary / helpers
├── sources/             # one <country>.yaml descriptor per country
├── parsers/             # one parser per country (registered in parsers/__init__.py)
├── source_data/         # retained raw published files (audit trail)
├── out/                 # tidy <country>_cpi.csv outputs
└── Africa_CPI_Collector_Progress_Report.{docx,xlsx}
```

## Run

```bash
# online (discover → download → parse → validate → write)
python -m indicators.cpi.pipeline <country>
python -m indicators.cpi.pipeline --all

# offline (parse an already-downloaded file with the same extraction path)
python scrape_local.py --indicator cpi <country> <path-to-file>
python scrape_local.py --indicator cpi --dir <folder>
```

## Schema (tidy long format)

Keyed by **coicop_code · coicop_label · geography · period**, plus identity/provenance
columns. Each NSO's own nomenclature (e.g. Algeria's 8-group scheme) is captured
as-is rather than forced into COICOP; `period` is `YYYY-MM` for the monthly series.

## Tests

```bash
PYTHONUTF8=1 py -W ignore -m indicators.cpi.tests.check_registry   # descriptors resolve
PYTHONUTF8=1 py -W ignore -m indicators.cpi.tests.test_offline     # rules + validator + corpus
```

**This suite is shaped differently from `labour`'s and `unemployment`'s, on
purpose.** Those read most countries through one declarative engine, so a
fixture per trap exercises rules shared by a dozen layouts. CPI has **53
bespoke parsers and no shared engine** — replaying 52 fixtures would test 52
things once each and still miss what binds the corpus together. So it checks:

| | |
|---|---|
| `coicop.code_for_label` | the one shared rule set every parser can reach — all-items in its many wordings, the twelve divisions, and the non-divisions that must return `None` |
| `schema.validate` | malformed periods, unknown measures, non-numeric values, and `expect_divisions` firing |
| **all 52 outputs at once** | merge-key uniqueness, well-formed codes and periods, and an all-items series per country |
| KNBS Kenya | one per-country replay of Table 1, verbatim |

**Two things worth knowing before editing it.**

*The index ceiling is deliberately loose.* It exists to catch parse garbage (a
weight column read as an index), not to cap reality — Sudan's CPI passes
630,000 on its 2007 = 100 base and is a real published figure. Tightening it to
a tidy 100,000 would reject a whole country's series, and a test pins that.

*`"All items less food and energy"` currently maps to `00`.* The rule comments
say `startswith` prevents it; it does not. This is **latent, not live**: only
four parsers call `code_for_label`, and no output in the corpus carries a
core/less/excl label — but KNBS Kenya publishes a Core and Non-Core section, so
the day a parser reads it, core inflation would be filed as the headline
series. `test_core_inflation_is_a_known_sharp_edge` pins both halves: the
current behaviour, and that the corpus stays clean of it. If the rule is
tightened, change that test deliberately rather than deleting it.

**It is mutation-checked.** Breaking the transport rule, letting non-divisions
through, disabling any of the three validator guards, leaking Kenya's weight
column into its values, removing the parser's 14-division floor, or injecting a
duplicate merge key into a real output each turns the suite red on the
assertion written for it — the weight leak surfacing as
`KE all-items mom: got [100.0], want [0.4]`.

## Principles

- **As reported** — ugly-but-real values kept; ambiguous figures left out, never guessed.
- **No aggregators** — IMF, World Bank, Knoema, Trading Economics re-estimate or
  harmonise and are excluded as sources.
- **As classified** — native division schemes captured as published, not remapped.
- **All periods** — full historical series emitted where published.
- **Auditable** — the raw source file is retained under `source_data/` for every country.

## Adding a country

1. Drop a `sources/<country>.yaml` descriptor (source URL, parser name, identity cols).
2. Add `parsers/<country>.py` and register it in `parsers/__init__.py`.
3. Run `python -m indicators.cpi.pipeline <country>` and check `out/<country>_cpi.csv`.

The shared discovery/download/validation/output harness lives in `core/`; this folder
only holds what is CPI-specific.
