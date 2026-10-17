# Africa CPI Collector — Developer Guide

A complete, follow-along guide for building a collector that harvests **Consumer
Price Index (CPI)** data from all 54 African National Statistics Offices (NSOs),
**exactly as each NSO reports it** — no estimation, no imputation, no omission.

This is written so that someone starting from an empty repo can reproduce the
whole thing, and — more importantly — **navigate every blocker** that stands
between you and an NSO's data. By the time this guide was written the collector
covered **41 of 54** countries; the remaining 13 are documented here as
"blocked, and exactly why."

---

## Table of contents

1. [Philosophy & the non-negotiable rules](#1-philosophy--the-non-negotiable-rules)
2. [Architecture & data flow](#2-architecture--data-flow)
3. [The canonical schema](#3-the-canonical-schema)
4. [Adding one country: the end-to-end workflow](#4-adding-one-country-the-end-to-end-workflow)
5. [Reconnaissance: how to find an NSO's data](#5-reconnaissance-how-to-find-an-nsos-data)
6. [The discovery-method catalogue](#6-the-discovery-method-catalogue)
7. [The parsing-pattern catalogue](#7-the-parsing-pattern-catalogue)
8. [The blocker taxonomy — defeating every wall](#8-the-blocker-taxonomy--defeating-every-wall)
9. [Classification handling (COICOP-1999 / 2018 / native)](#9-classification-handling)
10. [Gotchas & hard-won lessons](#10-gotchas--hard-won-lessons)
11. [Testing & validation workflow](#11-testing--validation-workflow)
12. [Quick-reference checklist](#12-quick-reference-checklist)

---

## 1. Philosophy & the non-negotiable rules

The single most important design constraint, from which everything else follows:

> **Capture the data exactly as the NSO publishes it. No estimation, no
> imputation, no omission. Native (non-COICOP) classifications are kept as-is.
> Every reported period is emitted. Never drop a reported series.**

Consequences you must internalise:

- **No aggregators.** IMF, World Bank, Knoema/opendataforafrica, Trading
  Economics, FRED, IndexMundi — all *re-estimate* or *harmonise*. They are
  banned as sources. Only **NSO-direct** data (or, as an explicit documented
  fallback, a **central bank** that republishes the NSO's own numbers without
  re-estimating them). The central-bank fallback is not a consolation prize — it
  yielded two *full* division-level captures (Libya, Mozambique) for countries
  whose NSO was unreachable. See the sourcing hierarchy in Section 5.5.
- **As-reported classification.** If a country publishes a native 8-group
  nomenclature (Algeria) instead of COICOP, you capture the 8 groups with their
  real labels — you do **not** force them into COICOP.
- **All periods.** If a workbook has a monthly series back to 1998, you emit all
  ~340 months, not just the latest.
- **Faithful, not pretty.** When a value is ugly (hyperinflation of 9795%,
  a negative index base era), you keep it. When you genuinely can't extract
  something reliably (chart-only divisions), you capture what you *can* verify
  and **document the gap** — you never fabricate the missing part.

### Source tiering (pick the most robust available)

1. **Tier 1 — API / SDMX / PxWeb.** Machine-readable, versioned, the gold
   standard. (Ghana StatsBank PxWeb.)
2. **Tier 2 — structured file** (CSV / Excel), including files hidden behind a
   SPA or a CMS API.
3. **Tier 3 — PDF / DOC scrape** with table extraction. The most common tier
   in Africa; most NSOs publish a monthly "note" or "bulletin" PDF.

Only drop to a lower tier when the higher one doesn't exist. And when even Tier 3
isn't cleanly possible, a **documented partial** (all-items only, or annual only)
is acceptable *if and only if* the limitation is written into the descriptor and
flagged in the README.

---

## 2. Architecture & data flow

The whole system is a small, boring pipeline where **one country breaking never
stops the others**. Each country is two files plus a row in a registry.

A shared, indicator-agnostic **core** + one self-contained pipeline per indicator:

```
core/                       # SHARED, indicator-agnostic machinery
  run.py                    # orchestrator harness: discover → download → extract
                            #   → parse → normalise → validate → write CSV.
                            #   Config-driven via a Pipeline dataclass; run_cli(cfg)
  discover.py               # resolve the current file URL (all discovery methods)
  fetch.py                  # download + unzip helpers; the shared HTTP HEADERS
  pxweb.py                  # Tier-1 PxWeb JSON API client
  schema_base.py            # shared ValidationError

indicators/<indicator>/     # one folder per indicator (cpi, gdp, …)
  pipeline.py               # entry point; injects paths/parsers/schema into core
  sources/<country>.yaml    # the DESCRIPTOR: where/how to get the data
  parsers/
    __init__.py             # REGISTRY: parser-id string → parse() function
    <agency>.py             # one parse(local_path) -> DataFrame per source layout
  schema.py                 # this indicator's columns + validate() (fail loud)
  coicop.py                 # (cpi only) COICOP division reference
  source_data/<Country>/    # RETAINED raw published files (first-class deliverable)
  out/<country>_<ind>.csv   # tidy long-format output, one per country
```

Run one pipeline: `python -m indicators.<indicator>.pipeline <country>` (or `--all`).
Adding a new indicator = a new `indicators/<name>/` folder; `core/` is reused.

### The flow for a single country

```
load indicators/<indicator>/sources/<country>.yaml
      │
      ▼
DISCOVER  ── resolve the exact current file/data URL (discover.py)
      │       (API sources skip this and fetch data directly)
      ▼
DOWNLOAD  ── stream the file to indicators/<indicator>/source_data/<Country>/ (retained for audit)
      │
      ▼
EXTRACT   ── unzip if needed; hand the local path to the parser
      │
      ▼
PARSE     ── parsers/<agency>.py: read the table → tidy DataFrame
      │       (coicop_code, coicop_label, geography, period, measure,
      │        value, unit, base_period, frequency)
      ▼
NORMALISE ── run.py adds identity/provenance columns from the descriptor
      │       (country, iso3, indicator, source_type, source_url,
      │        source_file, extracted_at)
      ▼
VALIDATE  ── schema.validate(): fail loud on malformed periods, bad measures,
      │       out-of-range values, too few divisions in the latest period
      ▼
WRITE     ── indicators/<indicator>/out/<country>_<ind>.csv
```

Two artifacts are kept per country: the **raw published document(s)** under
`indicators/<indicator>/source_data/<Country>/` (so any value can be traced to the primary source) and
the **tidy CSV** under `out/`.

### Why the descriptor / parser split

- The **descriptor** (`.yaml`) is declarative: it names the discovery method and
  its parameters, the parser id, the geography, `expect_divisions`, and notes.
  Changing *where* the data lives never touches Python.
- The **parser** (`parse(local_path) -> DataFrame`) only knows how to read one
  table layout. It returns the analytic columns; `run.py` fills in identity and
  provenance. This keeps parsers tiny and testable offline.

---

## 3. The canonical schema

Every parser returns rows with these analytic columns (run.py adds the rest):

| column | meaning |
|---|---|
| `coicop_code` | `"00"` = all-items; `"01".."13"` = divisions; native codes allowed |
| `coicop_label` | the label **as reported** |
| `geography` | `National`, or `Urban`/`Rural`/city names when reported separately |
| `period` | **`YYYY-MM`** — strictly enforced |
| `measure` | one of `index`, `inflation_yoy`, `inflation_mom` |
| `value` | numeric |
| `unit` | `Index` or `percent` |
| `base_period` | e.g. `2023 = 100` (empty for rate rows) |
| `frequency` | `monthly` / `annual` |

`run.py` then adds: `country, iso3, indicator, source_type, source_url,
source_file, extracted_at`.

### validate() — the guardrail that makes "fail loud" real

`schema.validate(df, expect_divisions=N)` rejects output before it can reach a
CSV. It enforces:

- **Period format**: must match `^\d{4}-(0[1-9]|1[0-2])$`. (This is why annual
  data must be dated `YYYY-12`, and why an EFY calendar must be converted.)
- **Measure**: must be in `{index, inflation_yoy, inflation_mom}`.
- **Numeric values**, with plausible ranges: `index ∈ [1, 100000]`,
  rates `∈ [-100, 100000]`. (This is why hyperinflation-era index values of
  `0.0` are dropped but a 9795% rate is kept.)
- **Division count**: the latest period must have **≥ `expect_divisions`**
  distinct `coicop_code`s. This catches a parser that silently lost half a table.

Set `expect_divisions` honestly:
- `14` for COICOP-2018 (00 + 01–13),
- `13` for COICOP-1999 (00 + 01–12),
- `9` / `8` etc. for native nomenclatures,
- `1` for an all-items-only (headline) capture.

---

## 4. Adding one country: the end-to-end workflow

This is the loop you repeat 54 times. Budget ~15 min for an easy static-PDF
country, ~1–2 h for a gated SPA you have to reverse-engineer.

1. **Recon** the NSO (Section 5). Find the *most robust* source (Tier 1 > 2 > 3)
   and the *exact* URL of the current file — or the API that lists it.
2. **Download one sample** by hand (a `requests.get` in a scratch script) and
   **open it** — inspect the real table layout, base year, period columns,
   label quirks, decimal/thousands conventions.
3. **Write the parser** `indicators/<indicator>/parsers/<agency>.py` with a `parse(path)`
   that returns the analytic DataFrame. **Test it offline** against your sample
   until every division and value matches the PDF/Excel by eye.
4. **Wire discovery**: pick or add a method in `discover.py`; write
   `indicators/<indicator>/sources/<country>.yaml`.
5. **Register** the parser in `indicators/<indicator>/parsers/__init__.py` (import + REGISTRY
   entry).
6. **Add a README row** (Country | Tier | Source | Status).
7. **Run end-to-end**: `PYTHONUTF8=1 py -W ignore -m indicators.<indicator>.pipeline <country>`.
   Confirm discovery resolved the newest file, the CSV wrote, validation passed.
8. **Sanity-check** the CSV: row count, period range, latest-month values vs the
   source document.

> **Windows note.** Run everything with `PYTHONUTF8=1 py -W ignore ...` — the
> Windows console is cp1252 and NSO PDFs are full of accented French/Portuguese
> and `?`-rendered glyphs. UTF-8 mode prevents `UnicodeEncodeError` mid-run.

---

## 5. Reconnaissance: how to find an NSO's data

Most of the work is **finding** the data, not parsing it. Modern NSO sites are
increasingly SPAs that hide their files behind an API. Here is the decision tree.

### Step 0 — identify the agency and its real domain

NSOs rename and move. Search for `"<country> institut national statistique IPC"`
or `"<country> national statistics office CPI"`. **Do not trust an old domain
that looks dead** — it may be a rebrand (see Burundi in Section 8). Central banks
(BCEAO region, BCC, BRB) often republish CPI too, and are the sanctioned
fallback when the NSO is truly unreachable.

### Step 1 — fetch the home page and classify the stack

```python
import requests, re
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 ... Chrome/125"}, verify=False, timeout=25)
print(len(r.text))                     # tiny (2–10k) → almost certainly a SPA shell
```

- **10k+ of real HTML with `<a href>` links** → classic server-rendered site.
  Look for `.pdf`/`.xls` links directly, or nav to a "prix / IPC / publications"
  page.
- **1–10k shell** → SPA. Go to Step 2.
- **WordPress** (`/wp-content/`, `/wp-json/`) → use the REST API (Section 6).
- **Joomla** (`/index.php/component/...`, Phoca/Edocman) → component download
  routes (Section 6).
- **Liferay** (`/web/guest/`, `/documents/d/guest/`) → document library or
  headless-delivery API (often auth-gated — Section 8).

### Step 2 — a SPA: find its backend API from the JS bundle

This is the single most valuable trick in the whole project. A SPA's data comes
from an API whose base URL is baked into its JavaScript.

```python
home = requests.get(url, headers=H, verify=False, timeout=25).text
js = re.findall(r'(?:src|href)="([^"]+\.js)"', home)     # main.<hash>.js, index-<hash>.js
blob = "".join(requests.get(join(url, j), headers=H, verify=False, timeout=20).text for j in js)

# hunt for the API base:
re.findall(r'https?://[a-z0-9.\-]*(?:api|admin|back|cms|strapi)[a-z0-9.\-/]*', blob, re.I)
re.findall(r'(?:apiUrl|baseUrl|api_url|serverUrl)["\s:=]+["\']([^"\']+)', blob, re.I)
re.findall(r'/api/[a-z0-9/_\-]+', blob)
```

Real examples this uncovered:
- **Malawi** (Nuxt): `cms.nsomalawi.mw/api/web/news/<slug>` → attachments list.
- **Chad** (custom SPA): `inseed.ssn-tchad.td/api/publications` (paginated).
- **Mauritania** (SPA over WordPress): `admin.ansade.mr/wp-json/wp/v2/media`.
- **Cabo Verde** (Angular): `bdmi.ine.cv/site_deploy_api/api` (but **401** —
  auth-gated, blocked).
- **Djibouti** (Nuxt): Heroku backend (routes found, but **500** — down).
- **Burundi** (SPA over Laravel): `api.insbu.bi/api/publications`.

Then probe the API's list endpoint (`/publications`, `/documents`, `/news`,
`/media`), read one JSON item's shape, and find the field that holds the file URL
(`document_url`, `fichier.url`, `source_url`, `attachments[].url`).

### Step 3 — the file path may be *deterministic*

Sometimes the detail page is gated (ephemeral hash) but the **file path is
derivable from a stable id**. Côte d'Ivoire: each publication card has a
thumbnail `Imageval_indicateur<ID>.png`, and the PDF is always
`assets/publications/files/File_val_indicateur<ID>.pdf`. You never need the
ephemeral detail hash — just map the id. **Always check whether a visible id
(thumbnail, slug, timestamp) maps to the download path by a fixed rule.**

### Reconnaissance scripting discipline

- Use a **browser User-Agent**. Many WAFs 403/406 a bare `python-requests` UA
  but pass a full Chrome UA. Some also need `Accept` and `Accept-Language`.
- Use `verify=False` (with `urllib3.disable_warnings()`) — a huge fraction of
  NSO sites serve **incomplete certificate chains**. Set `verify_ssl: false` in
  the descriptor to mirror this in production.
- **Write scratch scripts with the Write tool, not bash heredocs.** Heredocs
  mangle regex backslashes (`\d`, `\.`) and cause `re.error`. (Lesson 10.1.)
- Probe several candidate endpoints/domains **in parallel**
  (`concurrent.futures.ThreadPoolExecutor`) to keep recon fast.

### 5.5 When the NSO is unreachable: the fallback hierarchy

If the NSO site is down, WAF-blocked, or auth-gated, don't give up on the country —
work down this hierarchy. The key insight: **CPI is compiled by the NSO but often
republished verbatim elsewhere.**

1. **Regional/national central bank (BEST fallback).** Central banks routinely
   republish the NSO's *full* CPI workbook (index by division, all periods) — this
   is the NSO's own number, not a re-estimate, so it is allowed. Two full wins came
   this way:
   - **Libya (CBL)** — `cbl.gov.ly/en/eco_indicators_category/consumer-price-index/`
     hosts a "Consumer Price Index by Commodity Groups" PDF (full COICOP-1999
     monthly index) that republishes the Census & Statistics Dept.'s data. Libya has
     no reachable NSO site at all.
   - **Mozambique (BM)** — `bancomoc.mz` republishes INE's CPI `.xls` ("Quadro 8",
     full division index, 2016–) even though INE's own Liferay portal is auth-gated.

   **Recon:** hit the central-bank home, then a `statistics / estatísticas /
   inflation / prix / consumer-price` nav page, and look for a CPI PDF/xls. The
   regional banks — **BCEAO** (WAEMU) and **BEAC** (CEMAC) — publish per-country
   IHPC in their monthly statistics bulletins (useful when a WAEMU/CEMAC member's
   own site is down).

2. **Ministry of Finance / Economy / Planning (usually NOT worth it).** MoF sites
   carry budget documents and quarterly macro/"conjoncture" notes. These cite the
   CPI only as a **headline number in commentary**, or embed a **stale** IHPC table
   (Guinea-Bissau's DGPEE note lagged ~18 months). The full CPI series is essentially
   never on a MoF site — it's NSO/central-bank territory. Check it, but expect a
   headline-only partial at best.

3. **Document a partial, or hold for recovery.** If only a headline rate or a stale
   figure is available, weigh it against reality: a country whose NSO is *temporarily*
   down (a transient outage) is better served by **retrying later** than by baking in
   a thin 5-point headline series. Build a documented ⚠️ partial only when the full
   data genuinely isn't published anywhere (Section 8.12).

Provenance note: when you use a fallback, name it honestly in the descriptor's
`agency` field (e.g. "Central Bank of Libya — republishing the Census & Statistics
Dept. CPI") so the source of record is never misrepresented.

---

## 6. The discovery-method catalogue

`discover.py` resolves the *current* file URL so the month is never hardcoded.
`run.py` dispatches on `discover.method`. Here is every method and when to use it.

### Classic scrapers

| method | use when | key params |
|---|---|---|
| `page_scrape` | a listing page has an `<a href>` to the latest file; first match is fine | `page_url`, `link_contains` |
| `latest_dated` | a page lists many month-dated files; parse `<Month> <Year>` and pick the newest | `page_url`, `link_contains` |
| `probe_monthly` | the file URL is a dated template and the listing is behind a WAF; walk backward from this month until one exists | template, months back |
| `two_hop_scrape` | the file isn't linked from the listing directly (listing → doc page → file) | `index_url`, `page_link_contains`, `file_link_contains` |
| `static_url` | a stable, unchanging URL (e.g. an annual file) | `url` |
| `gsheet_from_page` | the page embeds a Google Sheet; build a `format=xlsx` export of the whole workbook | `page_url` |
| `regex_on_page` | the file path is baked into inline/obfuscated JS, not an `<a href>` | `page_url`, `pattern`, `base_url` |

### CMS / API methods (the modern-SPA toolkit)

| method | platform | how it works |
|---|---|---|
| `capmas_publication` | CAPMAS (Egypt) JSON API | `GET /api/Publication/<id>` → newest issue's `excelUrl`/`pdfUrl` |
| `ine_ao_directory_files` | INE Angola: files are POSTed, not linked (`baixarArquivoPost` onclick → POST `filepath` to /Diretorios/Download) | `index_url`, `dirs` (one folder-name substring per level), `files` (one list of name substrings per file, each matching exactly one; first = primary, rest = extras) |
| `malawi_cms_cpi` | Nuxt + Laravel | `/api/web/news` list → `/api/web/news/<slug>` → pick the index `.xlsx` attachment (not the YoY one) |
| `wp_media_latest` | WordPress media API | `wp/v2/media?search=...`; keep PDFs matching a name, parse the month from the filename, take the newest |
| `latest_month_file` | WP REST / any page | collect every URL containing terms with a numeric `_MM_YYYY` stamp, return the newest |
| `wpdm_latest` | WordPress Download-Monitor | union listing pages, pick newest dated slug, fetch its landing page, extract the `?wpdmdl=<id>` link |
| `edocman_latest` | Joomla Edocman | scrape doc slugs, parse the French date, hit `/component/edocman/<slug>/download?Itemid=0` |
| `inseed_tchad_latest` | custom Node API | paginate `/api/publications`, match a title with a trailing `MM-YYYY`, take the newest |
| `insbu_latest` | Laravel API | `/api/publications` (newest first) → newest item whose title matches → `document_url` |
| `anstat_ci_ihpc` | Angular SPA | `POST searchPublicationByCritere` → `{view: html cards}` → newest IHPC card's thumbnail id → deterministic PDF path |

### Tier-1 API

Set `source_type: api` and a PxWeb/SDMX client (see `pxweb.py`, Ghana). These
skip discover/download and fetch the data directly.

### Design principles for a new discovery method

- **Always resolve to the *newest*** by parsing a date (month/year) — from the
  filename, slug, or an API `date` field — and taking the max. Do **not** trust
  "first in the list" unless the list is provably newest-first.
- **Union multiple listings** when one page lags. Congo's price page had gone
  stale and missed the newest month; unioning it with the search page caught it.
- Beware **numeric ids that reset** (Chad/CAR bulletins numbered `n-01..n-12`
  per year). Sort by `(year, month)`, never by the sequence number.
- Return a clean absolute URL; set `save_as` in the descriptor when the URL
  carries no usable filename (see Lesson 10.4).

---

## 7. The parsing-pattern catalogue

After ~30 PDFs you realise African CPI tables come in a small number of shapes.
Recognise the shape and you're 80% done.

### 7.1 The WAEMU / CEMAC IHPC note — the `nums[-4] / -3 / -1` family

The single most common Tier-3 layout. UEMOA (West) and CEMAC (Central) share a
harmonised methodology, so Senegal, Togo, Mali, Niger, Guinea, Cameroon, Congo,
CAR, Chad, Côte d'Ivoire all publish a "Tableau" of:

```
Libellé   Pondération   <several monthly indices>   <a few variation columns>
```

The reliable trick: **anchor on the trailing columns.** Match comma-decimals
only; the current index and the MoM/YoY rates sit at fixed offsets from the end:

- 3 variation columns `[1-mois, 3-mois, 12-mois]` →
  **current index = `nums[-4]`, MoM = `nums[-3]`, YoY = `nums[-1]`**
  (Sierra Leone, Togo, Niger, Cameroon, Congo, CAR, Chad).
- Different column sets shift the offsets — always **verify against the
  `INDICE GLOBAL` row whose values you can read in the narrative** ("a atteint
  122,5 points … +1,7% … +2,9%"). Mauritania is `[-5]/[-4]/[-2]`; Burundi is
  `[-4]/[-2]/[-1]`. **Never assume — cross-check one row.**

Why comma-decimals only: the **weight** column is often an integer with a
**thousands space** (`10 000`), and integer weights have no comma. Matching
`-?\d+,\d+` drops the weight automatically, so trailing offsets stay stable
whether or not the weight is captured.

### 7.2 Division labels: prefixes, Romans, and wraps

Identifying which row is which division is the fiddly part.

- **Explicit codes** (`01 -`, `02 -`, … Côte d'Ivoire; `1`, `2`, … Burundi):
  match a leading `^(\d{1,2})` and zero-pad. Cleanest.
- **Roman numerals** (`I`, `II`, … Chad): match `^(XII|XI|X|...|I)(?=\s|$)`.
  The lookahead `(?=\s|$)` is essential — without it, `I` matches the word
  "**I**ndice". Sub-items use dotted romans (`I.1`) — exclude them.
- **Keyword match** (many CEMAC/WAEMU): a per-code keyword, first-match wins.
  **Watch for substring collisions**: "alcoholic beverages" also matches "Food &
  Non-**Alcoholic Beverages**" (use "tobacco" instead); "food" vs an aggregate
  "Food and non-alcoholic beverages" duplicate row (first-occurrence + not-in-
  picked handles it).
- **Wrapped labels.** A label can wrap so the numbers land on a different line:
  - *label above the numbers* (Guinea, Lesotho): carry a "pending" label forward
    to the next number line.
  - *label split above **and** below* (Congo CEMAC): match on a
    `prev + own + next` window.
  - *code digit alone on the number line, name on the line above* (Côte d'Ivoire
    04/05; Burundi 04/05): read the code from the previous line.
  - Refinement for sub-item collisions (CAR): only use the window when the own
    label is empty or a bare code; a row with a real own label is a sub-item and
    is matched on its own label so the two never collide.

### 7.3 Scope to the right table/page

A bulletin has many tables (national by function, by region, by secondary
nomenclature, plus summary blocks). Always **scope to the national "par
fonction" table** — e.g. `next(page for page in pages if "par fonction" in
page.lower() and "indice global" in page.lower())`. And beware a **summary block
that repeats the all-items label** with a different column count (Chad's
"Indice global" 12-column summary vs the Tableau-2 "INDICE GLOBAL 10000" row —
disambiguate by requiring the weight `10000`).

### 7.4 Report month: prefer the document text over the filename

The month often isn't in the URL (opaque `publication-<id>.pdf`) or the filename
gets renamed by `save_as`. **Read the report month from the PDF text** — e.g.
`"du mois d'avril 2026"`, `"Mois de JUIN 2026"`, `"Base 100 : 2018, avril 2026"`.
Keep the filename regex as a fallback only.

### 7.5 Wide Excel time series

Excel sources (South Africa, Namibia, Uganda, Senegal, Morocco, Madagascar,
Seychelles, Zimbabwe, Malawi) are usually a **wide matrix**: rows = divisions,
columns = months, with a datetime header row and a weight column.

- Find the **period header row** programmatically (the first row whose cells
  parse as dates via `pd.to_datetime(..., errors="coerce")`), then map each data
  column to `YYYY-MM`.
- Match division rows by keyword on the label column; take **first occurrence**
  so analytical aggregates at the bottom (Food/Non-food, Services) don't shadow a
  real division.
- Multi-section workbooks (Seychelles stacks index / %-change / weights blocks
  that repeat the same labels): the first block is the index — take the **first**
  matching row for each division.
- **Weight columns before the index block.** A sheet may put several `Pond. <year>`
  weight columns *before* the dated index columns (Mozambique's Quadro 8: 11 weight
  columns, then `Jan.16 … Jun.26`). Don't assume the numbers start at column 1 —
  locate the period header by the `Mon.YY` / datetime pattern and read only those
  columns, or you'll emit weights as if they were indices.
- **Multiple stacked *quadros* with repeating codes → first-occurrence dedup.**
  One sheet can hold índices, then variações, then contribuições, all keyed by the
  same COICOP codes (Mozambique). Matching a code across the whole sheet yields 5×
  the rows with mixed measures. Keep a `seen` set and take the **first** block only
  (it's the national index) — the tell that you got it wrong is an "index" value of
  4.57 where you expected ~115.
- Emit **every** dated column (this is where you honour "all reported periods").

### 7.5b Fixed-column-order tables (map by position)

Some CPI tables are a clean matrix with **no per-row code or keyword** — just a
fixed column order confirmed by a header/weights row (Libya's "CPI by Commodity
Groups": Month, then Food, Tobacco, Clothing, …, Misc, Overall). Don't fight the
messy multi-line header — **map columns by position**: parse each data row's
numbers, assign `nums[0]→01, nums[1]→02, …, nums[12]→Overall(00)`, and let a
trailing extra number (an annual-inflation column) become `inflation_yoy` for 00.
Verify the order once against the weights row, then trust it.

### 7.6 Decimal & separator conventions

- French/Portuguese decimals use a **comma**: `re.findall(r'-?\d+,\d+', ...)`
  then `.replace(",", ".")`.
- **Thousands spaces**: `10 000`, `5 030` — matching comma-decimals sidesteps
  these; if you must parse them, `re.sub(r'\s+', '', num)` first.
- Mixed conventions in one file happen (Angola: `12,09` and `10.11` on adjacent
  rows) — normalise defensively: strip, then handle both `,` and `.`.

### 7.7 Chart-only data → capture the headline, document the gap

When the by-division figures exist only as **bar charts** with values fused into
labels ("FOOD AND NON-ALCOHO-**L0IC.6**" — Liberia, Ethiopia), do **not** try to
un-fuse them (you'll get wrong numbers). Capture the clean tabular headline
(all-items index + rates) with `expect_divisions: 1`, and write the limitation
into the descriptor notes and a ⚠️ README row.

---

## 8. The blocker taxonomy — defeating every wall

This is the part you actually came for. Every category of obstacle, with the
concrete tactic that beats it (or the honest verdict when it can't be beaten by
scraping).

### 8.1 SPA hides everything (empty HTML shell)
**Tactic:** fetch the JS bundles, grep for the API base, hit its list endpoint,
find the file-URL field (Section 5, Step 2). Cracked: Malawi, Chad, Mauritania,
Burundi, Madagascar, Côte d'Ivoire.

### 8.2 Anti-bot WAF (403 / 406 / 200-with-empty-body)
**Tactic:** send a **full Chrome User-Agent** plus `Accept`, `Accept-Language`,
`Sec-Fetch-*`. Many WAFs pass on headers alone. If it returns **200 with a 0-byte
body**, it's a JS-challenge WAF (needs a real browser) — see 8.4. Mauritania's
`406` was pure header-fussiness (fixed by `Accept`); Côte d'Ivoire's `ins.ci`
was a JS challenge (but the *real* site was elsewhere — see 8.5).

### 8.3 Incomplete TLS certificate chain
**Symptom:** `requests` needs `verify=False`; the headless browser fails with
"unable to verify the first certificate." **Tactic:** set `verify_ssl: false` in
the descriptor (the pipeline passes `verify=False` through). Note this **also
disables the headless-browser fallback** for that host — so if the data is only
reachable by rendering JS *and* the cert is broken, you're stuck (Côte d'Ivoire's
`anstat.ci`; solved only because the PDF path turned out to be deterministic —
8.9).

### 8.4 JS-challenge WAF / SPA detail page that needs rendering
**Tactic 1 (preferred):** avoid rendering — find the API (8.1) or a deterministic
file path (8.9). **Tactic 2:** a headless browser (a `wrs`-style Chrome). But it
enforces cert validation, so it dies on 8.3, and it still times out on a genuinely
down host (8.7). Use it only when the cert is valid and the host is up.

### 8.5 Dead-looking domain (may be a rebrand or a hijack)
**Never accept "dead domain" at face value.** Two sub-cases:
- **Rebrand:** the agency renamed. Burundi's `isteebu.bi` was a parked/hijacked
  domain full of SEO spam — the NSO had become **INSBU** at `insbu.bi`. A single
  web search surfaced it, and its Laravel API delivered the data. **Always web-
  search the agency's current name + IPC.**
- **Wrong/old domain:** Côte d'Ivoire's `ins.ci` was a dead shared-hosting box;
  the live site was `anstat.ci`. Try `http://` (bypasses cert), try alternate
  TLDs/subdomains, and search.

### 8.6 Auth-gated API (401 / 403 with no public token)
**Tactic:** grep the client JS for a `Bearer`/`Authorization`/`apiKey`/token or a
login endpoint. If the token genuinely isn't in the client and there's no public
login, the NSO API is a **hard wall** — but before documenting it as blocked,
**try the central bank (Section 5.5)**: Mozambique's INE Liferay (headless + JSONWS
all 403) looked blocked, yet the Banco de Moçambique republishes INE's full CPI
`.xls` in the open. Cabo Verde (`bdmi.ine.cv/site_deploy_api` — 401 everywhere, no
token) remains blocked because its central bank publishes no CPI file either — that
one genuinely needs credentials.

### 8.7 Server genuinely down / regional outage
**Tactic:** confirm from **two independent network paths** (your requests *and*
the headless browser). If both time out, it's globally down, not a geo-block on
you — retrying immediately is futile; it needs calendar time. Check for a live
**alternate domain** (parked placeholders like the LWS "domaine créé" page don't
count). Persistent West-African outages hit Guinea-Bissau, Gabon, Eswatini, and
transiently Burkina/Guinea/Mali/Niger during a full run — all with confirmed-
existing data, all needing a later retry.

### 8.8 Ephemeral / encrypted detail hashes
**Symptom:** the SPA's detail URL contains a long hash that **regenerates every
request** (a random suffix). **Tactic:** don't chase the hash — either (a) follow
it *within the same session* immediately (it resolves once), or better (b) find
the **deterministic file path** from a stable id (8.9).

### 8.9 Deterministic file path from a visible id
The escape hatch for 8.4/8.8. Côte d'Ivoire: thumbnail `Imageval_indicateur<ID>.png`
⇒ PDF `File_val_indicateur<ID>.pdf`. **Whenever you see a stable id (thumbnail,
slug, timestamp), test whether it maps to the download path by a fixed rule** —
it often does, and it sidesteps every gate.

### 8.10 File served with no filename in the URL
**Symptom:** URL ends `/download/` or `?wpdmdl=4757`; `run.py` can't derive a
name and the parser can't read the month from it. **Tactic:** set `save_as:` in
the **discover** block (not top-level — Lesson 10.4), and read the report month
from the document **text** (Section 7.4).

### 8.11 Non-standard calendar (Ethiopian Fiscal Year)
**Symptom:** dates tagged `EFY 2018` with Gregorian month names. **Tactic:** it's
a calendar *conversion*, not estimation — Ethiopian year N spans Gregorian
Sep N+7 … Sep N+8, so a Jan–Aug month → EFY+8, Sep–Dec → EFY+7. Anchor the **last
table row** to the confirmed report month (cross-checked against the site's own
`...-may-2026` download page) and step back one month per row — this also
survives the NSO **mislabelling** an intermediate row (ESS labelled April as
"May").

### 8.12 Only partial / stale data is published (documented partial)
When the NSO publishes only a summary (Ethiopia: all-items + chart-only
divisions) or a central-bank annual file (DR Congo: BCC annual index to 2020,
INS-RDC WAF-blocked), capture what's **cleanly verifiable**, set
`expect_divisions: 1`, use `frequency: annual` + `YYYY-12` dating if annual, and
**flag ⚠️ PARTIAL** in the README with the limitation in the descriptor notes.

### 8.13 Empty CMS categories / microdata-only portals
Some sites *look* right but are empty (São Tomé's Phoca-Download categories) or
are NADA microdata portals with no CPI series (Gambia). Verify there's an actual
current file before investing.

### 8.14 Conflict states
Somalia, Sudan, South Sudan, Eritrea — typically no current NSO CPI online at all,
and their central banks / finance ministries publish none either. Documented as
out of reach. **But don't assume** — **Libya**, also a conflict state with no
reachable NSO site, turned out to have a *full* COICOP monthly index on its central
bank's site (Section 5.5). Always run the central-bank check before writing a
country off.

---

## 9. Classification handling

- **COICOP-1999** (12 divisions + all-items = **13**): the most common. Codes
  `00`–`12`.
- **COICOP-2018** (13 divisions + all-items = **14**): the modern revision;
  splits Information & Communication, adds Insurance & financial services (12) and
  Personal care/social protection (13). Côte d'Ivoire (rebased 2023) uses it.
- **Native nomenclatures**: capture as-reported. Algeria publishes an **8-group**
  scheme — keep the 8 native codes and labels, do **not** map to COICOP. Set
  `expect_divisions` to the native count and note it.
- **Local adaptations**: Mauritania's division 02 is "Tabac et stupéfiants" (no
  alcohol). Keep the country's actual label.

Never invent a division a country doesn't report, and never merge two reported
divisions to fit a template.

---

## 10. Gotchas & hard-won lessons

**10.1 Bash heredocs mangle regex.** `cat > x.py <<'PY' ... \d ... PY` eats
backslashes → `re.PatternError`. **Write scratch scripts with a file-write tool**,
not heredocs.

**10.2 WordPress REST JSON escapes slashes.** `wp-json` responses contain
`https:\/\/...`. Your URL regex `https?://[^"']+` won't match. **`text =
r.text.replace("\\/", "/")` before extracting URLs.**

**10.3 Keyword substring collisions.** "alcoholic beverages" ⊂ "Food & Non-
Alcoholic Beverages"; "services" ⊂ "Miscellaneous goods and services"; Roman "I"
⊂ "Indice". Use **unique** keywords ("tobacco"), **first-occurrence + not-in-
picked**, and **word-boundary lookaheads**.

**10.4 `save_as` lives in the `discover:` block, not top-level.** `run.py` reads
`disc.get("save_as")`. A top-level `save_as` is silently ignored and the file is
saved with a garbage name.

**10.5 Integer weights break decimal-only counts.** An all-items weight of `100`
(no decimal) isn't matched by `\d+\.\d+`, so that row has one fewer number than
its neighbours. Anchor on the **trailing** values, or require `>= N-1`, or count
all numbers — never assume a fixed leading offset.

**10.6 Report month: text beats filename.** Opaque URLs and `save_as` renames
destroy filename-based month detection. Parse the month from the document text.

**10.7 Newest ≠ first, and ids reset.** Always pick by parsed `(year, month)`.
Bulletin sequence numbers reset annually (`n-12-2024` is older than
`n-07-2025`).

**10.8 One listing can lag.** Union multiple listing pages (Congo's price page
missed the newest month that its search page had).

**10.9 Scope to the national "par fonction" table** and beware summary blocks
that repeat the all-items row with a different column count.

**10.10 Validate `expect_divisions` honestly** — it's your early-warning that a
parser silently dropped rows.

**10.11 Cross-check one readable row.** The narrative always states the all-items
index and its MoM/YoY ("122,5 points … +1,7% … +2,9%"). Use it to *prove* your
`nums[-k]` offsets before trusting the whole table.

**10.12 Keep the raw file.** `source_data/<Country>/` is a first-class
deliverable — every value must be traceable to the primary document.

**10.13 HTML-entity-encoded URLs.** A file href can contain entities — Mozambique's
`.../ipcmo&#231;ambient…xls` (`&#231;` = `ç`). BeautifulSoup decodes it to a literal
`ç`; `requests` then needs it percent-encoded (`%C3%A7`). The pipeline's
`find_download_link` + `fetch.download` handle this, but in scratch recon you may
need `url.replace("&#231;", "%C3%A7")` (or `html.unescape` then `quote`) to fetch.

**10.14 One sheet, many stacked tables.** An Excel sheet can hold índices, then
variações, then contribuições, all keyed by the same codes (Mozambique's Quadro
8). Dedup by first-occurrence and sanity-check a value's *magnitude* (an "index"
of 4.6 where you expected ~115 means you're reading a %-change block). See 7.5.

---

## 11. Testing & validation workflow

**Parser-first, offline.** Download one sample by hand, then iterate on the
parser against that local file until it's perfect — no network in the loop:

```python
from collector.parsers import <agency>
df = <agency>.parse("sample.pdf")
print(len(df), sorted(df.coicop_code.unique()), df.period.min(), df.period.max())
print(df[df.measure=="index"].set_index("coicop_code").value.to_dict())
# eyeball every division value against the PDF/Excel.
```

**End-to-end, once the parser is right:**

```bash
PYTHONUTF8=1 py -W ignore -m indicators.<indicator>.pipeline <country>
```

Confirm: discovery resolved the *newest* file, the source was retained, the CSV
wrote, and validation passed (row count + period range + latest-month values).

**The whole suite:**

```bash
PYTHONUTF8=1 py -W ignore -m collector.run --all
```

Read the failures carefully. A `ConnectTimeout` / `ReadTimeout` on an external
host is a **transient outage, not a regression** — the parser is unchanged and
its `out/*.csv` from a prior run is still valid. A `ValidationError` or
`Traceback` is a real bug. Keep a registry sanity check handy:

```python
from collector.parsers import REGISTRY   # every descriptor's parser must resolve
# assert every sources/*.yaml parser ∈ REGISTRY and discover.method is known
```

---

## 12. Quick-reference checklist

Adding a country, condensed:

- [ ] Identify the agency's **current** name & domain (web-search; beware
      rebrands/hijacks).
- [ ] Classify the stack (static / WordPress / Joomla / Liferay / SPA).
- [ ] Find the data: direct link → CMS API → SPA-JS API → deterministic path.
- [ ] **NSO unreachable? Try the central bank** (republishes the full CPI), then
      the regional bank (BCEAO/BEAC); MoF is a last, usually-headline-only resort
      (Section 5.5).
- [ ] Download **one** sample; **open it**; note base year, period columns,
      label style, decimal/thousands convention, which table is national.
- [ ] Write `parse()`; **verify every division value by eye**; cross-check the
      all-items row against the narrative.
- [ ] Choose/author a `discover` method that resolves the **newest** file.
- [ ] Write `sources/<country>.yaml` (`verify_ssl: false` if cert is broken;
      `save_as` in the discover block if the URL has no filename; honest
      `expect_divisions`; notes documenting any partial/limitation).
- [ ] Register the parser in `parsers/__init__.py`; add a README row.
- [ ] `run.py <country>` end-to-end; sanity-check the CSV.
- [ ] If blocked, classify the wall (Section 8) and either defeat it or
      **document it precisely** and move on.

Blocker cheat-sheet:

| symptom | first move |
|---|---|
| tiny HTML shell | grep JS bundles for the API base |
| 403 / 406 | full Chrome UA + `Accept` headers |
| 200 empty body | JS-challenge → find API or deterministic path |
| cert error | `verify_ssl: false`; browser won't help |
| 401 everywhere | token in JS? else **try the central bank** (5.5) |
| both requests & browser time out | globally down → retry later |
| NSO down / gated / conflict state | **check the central bank** — it may host the full CPI |
| ephemeral detail hash | map a stable id → deterministic file path |
| opaque file URL | `save_as` in discover; read month from text |
| EFY / odd calendar | convert (fact, not estimation); anchor last row |
| chart-only divisions | capture all-items headline; ⚠️ document gap |
| "index" value way too small | reading a %-change block → first-occurrence dedup |
| domain looks dead | web-search for a rebrand; try http:// & alt TLDs |

---

*Golden rule, restated: capture exactly what the NSO reports, prove every number
against the source, retain the raw file, and when you truly can't get something —
document the gap precisely rather than guess. The gaps are data too.*
