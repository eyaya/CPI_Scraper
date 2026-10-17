# africa-stats-collector

Collect indicators published by African National Statistics Offices (NSOs) into
one **tidy, structured** data file per country/indicator — starting with **CPI
(inflation)**, one country at a time.

For each country we pick the **most robust source available**, in this order:

1. **Tier 1** — official API / SDMX endpoint
2. **Tier 2** — structured file download (CSV / Excel)
3. **Tier 3** — PDF / DOC scrape + table extraction

Only fall to a lower tier when the higher one doesn't exist. Each country is a
small, self-contained unit: a **descriptor** (`indicators/<indicator>/sources/<country>.yaml`)
+ a **parser** (`indicators/<indicator>/parsers/<agency>.py`). The shared pipeline
handles the rest, and one country breaking never stops the others.

## Layout

Each **indicator** (CPI, GDP, …) is its own pipeline under `indicators/`, sharing
one indicator-agnostic **core**:

```
core/                 shared, indicator-agnostic machinery
  run.py              orchestrator harness: discover -> download -> extract ->
                      parse -> normalise -> validate -> write CSV. Config-driven:
                      each indicator injects its paths/parsers/schema (Pipeline).
  discover.py         resolve the current file URL (page_scrape | probe_monthly |
                      latest_dated | static_url | two_hop_scrape | wp_media_latest
                      | … — one method per site shape)
  fetch.py            download + unzip helpers
  pxweb.py            Tier-1 PxWeb JSON API client (e.g. Ghana StatsBank)
  schema_base.py      shared ValidationError

indicators/
  cpi/
    pipeline.py       entry point: python -m indicators.cpi.pipeline <country>
    sources/          one YAML descriptor per country
    parsers/          one parse() per source layout, registered in __init__.py
    schema.py         CPI tidy columns + validation
    coicop.py         COICOP 2018 division reference
    out/              tidy <country>_cpi.csv output, one per country
    source_data/      RETAINED raw NSO files as published, one folder per country
  gdp/
    pipeline.py       entry point: python -m indicators.gdp.pipeline <country>
    sources/  parsers/  schema.py  out/  source_data/   (same shape as cpi/)
  population/
    pipeline.py       entry point: python -m indicators.population.pipeline <country>
    sources/  parsers/  schema.py  out/  source_data/   (sex x age x geography)
  census_characteristics/
    pipeline.py       entry point: python -m indicators.census_characteristics.pipeline <country>
    sources/  parsers/  schema.py  out/  source_data/
    #  shared "count by characteristic" schema for census cross-tabs:
    #  marital status, disability, ICT, dwelling/housing, household size (topic column)
  labour/             economic activity: status/industry/occupation/sector + unemployment rate
  unemployment/       LFS headline series, as each NSO defines them:
    #  unemployment / participation / employment-to-population rates, the level
    #  counts behind them, and the LU1-LU4 underutilisation ladder. Carries
    #  `definition` (strict vs broad -- Senegal publishes 5.4% AND 23.3% for the
    #  same quarter) and `working_age_base` (10+ in Ethiopia, 15-64 in Kenya and
    #  Sierra Leone, 16+ in Mauritius and Rwanda), without which a cross-country
    #  series is nonsense. Overlaps labour/'s `unemployment_rate` topic --
    #  narrower scope, far deeper coverage.
  education/          attainment, school attendance, literacy status, current attendance
  mpi/                multidimensional poverty, as each NSO's OWN national MPI:
    #  incidence H, intensity A, index M0, censored headcounts, contributions
  fertility/          mean children ever born/surviving, age at first birth, births last 12m
  mortality/          life expectancy, infant & under-5 mortality, crude death/birth rates
  trade/              merchandise trade: exports/imports/total by HS commodity chapter
  ppi/                producer price index: level + YoY/MoM change by industry
  public_debt/        debt stock by component (external/domestic, creditor, maturity)
  school_enrolment/   admin enrolment ratios: GER, NER, gender parity, pupil-teacher
    #  (each: pipeline.py schema.py parsers/ sources/ out/ source_data/)

scrape_local.py       offline extraction from files you already downloaded
```

Adding a **future indicator** = one new `indicators/<name>/` folder (sources,
parsers, schema, out, source_data, pipeline.py) — the core is reused unchanged.

Every run keeps **two** things per country: the original published source
document(s) under `indicators/<indicator>/source_data/<Country>/`, and the tidy
CSV under `indicators/<indicator>/out/`. Raw files are retained for auditability
so any value can be traced back to the primary NSO document.

An indicator can also declare `merge_keys` in its `pipeline.py`, which makes runs
**merge into** the existing output instead of replacing it: rows the run produces
win, rows it did not produce are kept. Most NSOs publish one month per document,
so this is what lets a monthly series build up over successive runs — and what
stops a source that drops its own back-issues from silently shortening an output.
CPI has it on; the other indicators overwrite until they opt in.

## Run

```bash
pip install -r requirements.txt
python -m indicators.cpi.pipeline south_africa   # one CPI country
python -m indicators.cpi.pipeline --all          # every CPI descriptor
python -m indicators.gdp.pipeline south_africa   # one GDP country
python -m indicators.gdp.pipeline --all          # every GDP descriptor
```

### Scrape files you already have (offline, no network)

If you already downloaded the NSO PDFs/Excel yourself, `scrape_local.py` runs only
the extraction (skips discover/download) and writes the tidy CSV/xlsx. Pick the
pipeline with `--indicator` (default `cpi`):

```bash
# one file — <country> is the sources/<country>.yaml stem (see `--list`)
python scrape_local.py libya "C:\downloads\Consumer-Price-Index-...pdf"

# a whole folder — name each file after its country key (e.g. libya.pdf,
# south_africa.xlsx, kenya_june2026.pdf); the key just has to appear in the name
python scrape_local.py --dir "C:\downloads\nso_files"

# a folder INSIDE a GitHub repo (no clone needed) — lists + downloads via the API
python scrape_local.py --github owner/repo/data/nso_files
python scrape_local.py --github https://github.com/owner/repo/tree/main/data
python scrape_local.py --github owner/repo/data --token <gh_token>   # private repo

python scrape_local.py --list                 # list valid country keys
python scrape_local.py libya file.pdf --format xlsx   # csv | xlsx | both (default)
```

> If your platform already **clones** the repo (e.g. in CI / a GitHub Action), the
> files are on disk — just use `--dir <checkout>/data`. `--github` is only for
> reading a repo folder remotely without cloning.

The file must be the layout that country's parser expects (each country is paired
with its parser in `sources/<country>.yaml`). Batch mode is fail-soft — one bad
file doesn't stop the rest — and reports what was scraped, unmatched, or failed.

Output columns (tidy long format):

```
country, iso3, indicator, coicop_code, coicop_label, geography,
period (YYYY-MM), measure, value, unit, base_period, frequency,
source_type, source_url, source_file, extracted_at
```

`measure` records what `value` is, because NSOs publish different things:
`index` (a level, e.g. Stats SA / Nigeria) or `inflation_yoy` / `inflation_mom`
(% changes — all many PDF-only NSOs like Kenya publish by division).

## Standardised columns (all indicators, added 2026-10-15)

Every output keeps its published columns **verbatim** and appends derived, cross-country columns
after them — for anything that compares countries or builds identifiers (the Africa Data Commons
app had built variable IDs from free-text labels, giving names like "... [Sac6314] (XAF Billion)").

**The contract.** Derived only from the published columns; recomputed on every write
(`Pipeline.standardise`, run after merge-on-write; `scrape_local.py` too); **blank whenever the
source does not support a confident answer**. Backfill after a rule change, no download needed:

```bash
py -3 -m tools.standardise --all          # or: tools.standardise gdp [country]
```

Every indicator gets a `series_id` (`[A-Z][A-Z0-9_]*`, safe for any ID consumer), its plain-English
twin `series_name` (built from the same values, so one name per ID and one ID per name across the
corpus), and an `is_preferred` flag: exactly one `True` per country, place, date and `series_id` —
so sex, age band, urban/rural and currency are IN the ID. `tools/test_series_names.py` asserts all of
this for the 14 indicators. Shared helpers — ISO currency with the
CFA zone taken from iso3, scale, SDMX age bands, geography level, editions — are in
`core/standardise_base.py`; the seven seed indicators share `core/standardise_small.py`.

| Indicator | Concept code | Rows with a `series_id` | Verified by |
| --- | --- | --- | --- |
| gdp | SNA aggregate / ISIC section (`FCE_HH`, `VA_C`) | 59.6% | FCE+GCF+EXP−IMP = GDP; GVA + net taxes = GDP |
| cpi | COICOP **version per row** (div. 12 changes meaning at a rebase) | 100% | index-derived YoY = published YoY |
| population | sex, age band; census > estimate > projection | 100% | age bands sum to the total |
| unemployment | `UNE_RATE`, `LFPR`, `EPR`, `LU1-4` …; definition + ICLS + base + sex/age/locality in the ID | 86.4% | rate = count / labour force, LF = EMP + UNE |
| labour | ISIC section, ISCO major group, ICSE-93, formality | 68.9% | categories sum to the table's Total |
| public_debt | `TOTAL`/`EXT`/`DOM`/creditor/instrument + `coverage_code` | 36.5% | EXT + DOM = TOTAL; creditors = EXT |
| mpi | breakdowns; the **measure** is in the ID (national designs differ) | 91.4% | M0 = H × A |
| trade, ppi, school_enrolment, census_characteristics, education, fertility, mortality | HS2, ISIC, ISCED, slugs | 70.6–100% | trade totals; categories sum to Total |

Each indicator's README has its own section; each has a `tests/test_standardise.py` (the seeds:
`tools/test_standardise_small.py`), all mutation-checked.

## Countries

| Country | Tier | Source | Status |
|---------|------|--------|--------|
| South Africa (Stats SA, P0141) | 2 (Excel) | CPI (COICOP) index time series, Jan 2008– | ✅ done — index |
| Nigeria (NBS, catalog 154) | 2 (Excel in monthly zip) | CPI index 'Table2', national, Jan 2023– (2024 rebase) | ✅ done — index |
| Kenya (KNBS) | 3 (PDF) | Monthly press release Table 1 — inflation % by division | ✅ done — rates |
| Rwanda (NISR) | 3 (PDF) | 'Annex 3: All Rwanda' index by division (base Feb 2014) | ✅ done — index |
| Ghana (GSS StatsBank) | 1 (API) | PxWeb cpi.px — index + YoY + MoM, COICOP-2018, 1998– | ✅ done — index+rates |
| Egypt (CAPMAS) | 2 (Excel via site API) | Monthly CPI bulletin 'Table 1' — index+MoM+YoY by division for Urban/Rural/Total (base 2018/19). CBE note = Tier-3 fallback (urban+core) | ✅ done — index+rates |
| Uganda (UBOS) | 2 (Excel) | 'Division' sheet — index+YoY+MoM wide series (Jul 2017–, base 2016/17) by COICOP-2018 division (national) + 10 urban centres | ✅ done — index+rates |
| Morocco (HCP) | 2 (Excel / Google Sheets) | IPC index wide series (2017–, base 2017) by COICOP-1999 division + general; general in a 2nd sheet via extra_urls | ✅ done — index |
| Senegal (ANSD) | 2 (Excel) | IHPC (WAEMU) — index wide series (1998–, base 2023) by COICOP-2018 division + Global (All items) | ✅ done — index |
| Benin (INStaD) | 2 (Excel) | IHPC (WAEMU) connected series (1998–2024, base 2023); shares the `waemu_ihpc` parser with Senegal | ✅ done — index |
| Togo (INSEED) | 3 (PDF) | IHPC (WAEMU) monthly note — index+MoM+YoY by COICOP-2018 division + Global (base 2023) | ✅ done — index+rates |
| Burkina Faso (INSD) | 2 (Excel .xlsx/.xls) | IHPC (WAEMU) note 'Tableau 1' — index+MoM+YoY by COICOP-2018 division + Global (base 2023) | ✅ done — index+rates |
| Namibia (NSA) | 2 (Excel) | CPI Excel Tables 'Tab 2/3/4' — index+MoM+YoY wide series (2002–, base Dec 2012) by COICOP-1999 division | ✅ done — index+rates |
| Mali (INSTAT) | 3 (PDF) | IHPC (WAEMU) monthly note — index by COICOP-2018 division + INDICE NATIONAL (base 2023) | ✅ done — index |
| Niger (INS) | 3 (PDF) | IHPC (WAEMU) monthly note — index+MoM+YoY by COICOP-2018 division + Indice global (base 2023) | ✅ done — index+rates |
| Mauritius (Statistics Mauritius) | 3 (PDF) | Monthly CPI note 'Division' table — index (2 months) by COICOP-2018 division + All Divisions (base 2023) | ✅ done — index |
| Zambia (ZamStats) | 3 (PDF) | 'The Monthly' bulletin 'Table 1.2' — index wide series (2022–) by COICOP-1999 division + All items | ✅ done — index |
| Tanzania (NBS) | 3 (PDF) | NCPI release 'Main Groups' — index (3 months) by COICOP-2018 division + All items (base 2020) | ✅ done — index |
| Botswana (Statistics Botswana) | 3 (PDF) | CPI report 'Table 3' — index (5 months) by COICOP-1999 group + All items (base Dec 2018) | ✅ done — index |
| Tunisia (INS) | 2 (HTML) | IPC HTML table — index by COICOP-1999 group + Ensemble, rolling recent months (base 2015) | ✅ done — index |
| Cameroon (INS) | 3 (PDF) | CEMAC IHPC note 'Tableau 2' — index+MoM+YoY by COICOP function + INDICE GENERAL (base 2022); positional extraction | ✅ done — index+rates |
| Algeria (ONS) | 3 (PDF) | IPC note — index+MoM+YoY by **native 8-group** nomenclature + Ensemble (base 2001); NOT COICOP, captured as reported | ✅ done — index+rates |
| Sierra Leone (Stats SL) | 3 (PDF) | 'Table 1' CPI press release — index+MoM+YoY by COICOP-1999 division + All items (base Dec 2021) | ✅ done — index+rates |
| Lesotho (BOS) | 3 (PDF) | 'Table 1' monthly CPI report — index+MoM+YoY by COICOP-1999 division + Overall CPI (base Average 2022) | ✅ done — index+rates |
| Guinea (INS) | 3 (PDF) | INHPC note 'Tableau 2' — index+MoM+YoY by COICOP-1999 function + INDICE GLOBAL (UEMOA method, base 2019) | ✅ done — index+rates |
| Madagascar (INSTAT) | 2 (Excel behind SPA) | NIPC 'IPC' sheet — index wide series (2016–, base 2016) by COICOP-1999 FONCTION + Ensemble; two-hop discovery through the monthly NIPC page | ✅ done — index |
| Seychelles (NBS) | 2 (Excel) | 'CPI_Series' time series — index wide series (2007–, base 2014) by COICOP-1999 division + All items | ✅ done — index |
| Malawi (NSO) | 2 (Excel via CMS API) | 'Stats Flash' — index by COICOP-1999 division + All items (base Dec 2021), National/Urban/Rural + all-items MoM; discovered via the Nuxt SPA's headless CMS API | ✅ done — index+rates |
| Congo (INS) | 3 (PDF) | CEMAC INHPC bulletin 'Tableau 1.1' — index+MoM+YoY by COICOP-1999 function + INDICE GLOBAL (base 2018); discovered via the WordPress Download-Monitor wpdmdl link | ✅ done — index+rates |
| Central African Republic (ICASEES) | 3 (PDF) | CEMAC IHPC bulletin — index+MoM+YoY by COICOP-1999 function + INDICE NATIONAL (base 2019); discovered via the Joomla Edocman /download route | ✅ done — index+rates |
| Angola (INE) | 2 (Excel behind SPA) | Time-series DB — national all-items YoY inflation series (2015–); .xlsx path regexed from inline JS. No COICOP breakdown in this DB | ✅ done — rate (all-items YoY) |
| Zimbabwe (ZimStat) | 2 (Excel via WP API) | Weighted (blended) CPI 'CPI 2' sheet — index wide series (2024-04–, base Apr 2024) by COICOP-1999 division + All Items; newest workbook found via the WordPress REST API | ✅ done — index |
| Liberia (LISGIS) | 3 (PDF) | Monthly CPI Newsletter 'Table 1' — national all-items index+MoM+YoY 13-month series (base Dec 2005). By-division figures are chart-only | ✅ done — index+rates (all-items) |
| Mauritania (ANSADE) | 3 (PDF) | Monthly INPC note 'Tableau 2' — index+MoM+YoY by COICOP-1999 function + Indice général; note PDF found via the SPA's WordPress media API | ✅ done — index+rates |
| Chad (INSEED) | 3 (PDF) | CEMAC INHPC bulletin 'Tableau 2' — index+MoM+YoY by COICOP-1999 function (Roman I–XII) + INDICE GLOBAL (base 2022); found via the SPA's Node /api/publications feed | ✅ done — index+rates |
| Côte d'Ivoire (ANStat) | 3 (PDF) | UEMOA IHPC bulletin — index+MoM+YoY by **COICOP-2018** division (01–13) + INDICE GLOBAL (base 2023); PDF resolved from the SPA search API via the thumbnail id | ✅ done — index+rates |
| DR Congo (BCC) | 2 (Excel) | ⚠️ PARTIAL — national all-items **annual** index (base 2012) + YoY, 1992–2020 (INS-RDC WAF-blocked; BCC fallback) | ⚠️ partial — annual all-items |
| Ethiopia (ESS) | 3 (PDF) | ⚠️ PARTIAL — national all-items (General) YoY+MoM 13-month series; EFY dates mapped to Gregorian. Divisions are chart-only | ⚠️ partial — all-items rates |
| Burundi (INSBU) | 3 (PDF) | Monthly IPC 'Tableau 1' — index+MoM+YoY by COICOP-1999 function + Ensemble (base 2016/2017); found via the Laravel /api/publications (ISTEEBU→INSBU rebrand) | ✅ done — index+rates |
| Libya (CBL) | 3 (PDF) | Central-bank fallback — CBL republishes the Census & Statistics Dept. CPI: wide monthly index by COICOP-1999 group + Overall (2024–, base 2024) + overall YoY | ✅ done — index+rate |
| Mozambique (BM) | 2 (Excel) | Central-bank fallback — BM republishes INE's CPI 'Quadro 8': wide monthly index (2016–, base 2023) by COICOP-1999 division + Total (INE Liferay is gated) | ✅ done — index |
| Somalia (SNBS) | 3 (PDF) | Monthly CPI report — YoY+MoM by COICOP-2018 division + CPI TOTAL, 3-month window; index is chart-only. Also the 6 Federal Member States as `geography` | ✅ done — rates (+states) |
| Comoros (INSEED) | 2 (JSON/HTML) | Strapi CMS record — 'Tableau 1' index by COICOP-1999 function + Indice global, 5 dated months (m-12, m-3…m) + MoM/YoY (base 2011). **Moroni basket, not national** | ✅ done — index+rates |
| Equatorial Guinea (INEGE) | 3 (PDF) | Monthly IPC note annexes — index + MoM by CEMAC/NCAC function + IPC general (base 2008), national **and 5 cities**. Cloudflare-gated: needs a browser TLS fingerprint (`impersonate`) + URL-probe discovery | ✅ done — index+mom |
| Gabon (DGS/INSTAT) | — | ❌ **blocked, no descriptor.** instatgabon.org is unreachable at the network level (TCP connects, TLS handshake times out on both IPs — verified from two different networks); dgstat.ga times out, statgabon.ga 503s, stat-gabon.org is frozen at 2012. No live source has monthly by-division CPI: BEAC's workbook is annual all-items, frozen since Oct 2023, and yields only 3 true year-on-year points (2021–23) — its 12-year series is an annual-*average*, which no `measure` expresses. AFRISTAT's bulletin had the right shape but was discontinued after Dec 2021. Revisit when the domain returns | ❌ no source |

## Adding a country

Work inside the relevant indicator folder (`indicators/cpi/` or `indicators/gdp/`):

1. Investigate the NSO: does it have an API (tier 1), a structured file
   (tier 2), or only PDFs (tier 3)?
2. Write `indicators/<indicator>/sources/<country>.yaml` (copy an existing one).
3. Write a `parse(local_path)` in `indicators/<indicator>/parsers/`, register it
   in that folder's `parsers/__init__.py`. It returns a DataFrame with the
   indicator's core columns (CPI: `coicop_code, coicop_label, …`; GDP: `approach,
   category, series_code, …`). The harness fills in the identity/provenance columns.
4. `python -m indicators.<indicator>.pipeline <country>` — validation flags bad output.

## Adding a new indicator

Create `indicators/<name>/` with `sources/`, `parsers/` (+ `__init__.py` registry),
`schema.py`, `out/`, `source_data/`, and a `pipeline.py` that wires them into the
shared harness (copy `indicators/gdp/pipeline.py` and point it at the new schema).
The `core/` machinery is reused unchanged.
