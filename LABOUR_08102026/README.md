# Labour — Africa Labour / Economic Activity Collector

Harvests the **composition of employment** — what work people actually do — from
African National Statistics Offices into one tidy, long-format dataset, captured
**exactly as each NSO publishes it**, with no estimation, imputation or
remapping.

**Status:** 53 of 54 countries collected, 48,725 rows (1977 to 2026 Q2), no
duplicate merge keys and no non-numeric values. Only Eritrea remains, recorded
in `sources_blocked/`: it has no statistics website. Sudan was unblocked
2026-10-01 from Wayback `id_` copies of CBS's own files (SLFS 2011 booklet and
the 2008 census, NORTHERN Sudan only).

Working-age bases are whatever the NSO uses, and there are now thirteen: 15+,
15-64, 16+, 10+, 14+, 14-64, 15-59, 16-65, 18-64, 15-29 (Benin's youth-only
survey), 6+, 5+ and `not stated`.
Ethiopia's shares are on persons aged 10 and over, Madagascar's ENEMPSI on 5+,
the Central African Republic's census on 6+; comparing any of them against a
15+ series without saying so is a real error, which is why `working_age_base`
travels on every row. Algeria's and Burundi's are `not stated`.

| | |
|---|---|
| Tier 1, API | Ghana (GSS StatsBank PxWeb) |
| Tier 2, workbook | Malawi, South Africa, Mauritius, Angola (fetched by POST), Cabo Verde, Mali, Madagascar (ENEMPSI) |
| Tier 2, HTML pages | Tunisia (INS theme pages) |
| Tier 3, report PDF | Kenya, Senegal, Republic of Congo, Côte d'Ivoire, Benin, Zambia, Botswana, Seychelles, Rwanda, Tanzania, Namibia, Eswatini, Ethiopia, Somalia, Egypt, Morocco, Burkina Faso, Algeria, Gambia, Uganda, Lesotho, Liberia, Chad, Cameroon, Zimbabwe, Burundi, Gabon, Equatorial Guinea, Niger, Nigeria, Mozambique, Libya, Guinea, Sierra Leone, São Tomé and Príncipe, Comoros, South Sudan, Guinea-Bissau, Mauritania, Central African Republic, DR Congo, Togo, Djibouti |

All three source tiers are now proven, so a new country is a layout plus a
descriptor rather than a new reader — and each of the eleven PDF countries reuses
the `discover:` block `unemployment/` already resolved for it. See *Where the
next countries come from* below.

- `Africa_Labour_Collector_Progress_Report.docx` — narrative (work done, challenges, outstanding)
- `Africa_Labour_Collector_Progress_Report.xlsx` — 4 sheets (Executive Summary, Country Status, Challenges & Remedies, Outstanding & Next Steps)

## What this indicator is, and what it is not

`labour/` holds the COMPOSITION of employment. `unemployment/` holds the
headline labour-force status series. The boundary is deliberate, and there is
**no overlap** — a figure has exactly one home:

| | |
|---|---|
| **labour/** | industry, occupation, status in employment, institutional sector, formal/informal, activity status |
| **unemployment/** | unemployment / participation / employment-to-population rates, the level counts behind them, LU1–LU4 |

`unemployment_rate` was previously a topic here as well, which left Ghana's
census-based regional rates sitting among cross-tabs of employment composition
with no strict/broad definition and no working-age base recorded — which is to
say uninterpretable. It has been removed from the vocabulary and the census
series now lives in `unemployment/` as `ghana_census.yaml`, beside the quarterly
AHIES one.

## The classification travels with the category

An industry or occupation label means nothing without the scheme that produced
it. Stats SA's **"Trade"** is one of ten national groups; Malawi's *"Wholesale
and retail trade…"* is an ISIC Rev.4 section. Joining them because both are
industries would be wrong.

So categories are captured **exactly as printed, never remapped**, and a
`classification` column records the scheme — the same approach the CPI collector
takes with native nomenclatures beside COICOP. `_common.row()` **refuses** an
industry, occupation or status row that names no scheme, and `classification` is
part of the merge key.

The clearest case is South Africa, which publishes status in employment twice:

```
Table3.6   Employed by sex and status in employment           -> ICSE-93
Table3.6b  ... status in employment 20th ICLS (ICSE-18)       -> ICSE-18
```

Same country, same quarter, same people, two international standards, different
category sets. Without the scheme attached they read as contradictory
duplicates; with it, both are collected and neither can overwrite the other.

### A scheme is recorded only where the report names one

Deciding a country "is really using ISCO-08" because its group names look like
ISCO-08's is inference published as fact. So:

- NBS **Seychelles** prints "(ICSE 93)", "(ICSE 18) by type of authority",
  "(ISCO-08)" and "ISIC-Rev 4" — all four are recorded as printed, which is why
  one quarter carries three status classifications that cannot collide.
- Statistics **Botswana** names BOSCO for occupation and no scheme at all for
  industry, so both are `National` — even though its twenty-one industry groups
  follow ISIC Rev.4's sections.
- **NISR Rwanda** heads its industry table "ISIC High level" without a revision;
  its sections include *Information and communication*, which exists only in
  Rev.4, so `ISIC Rev.4`. Its occupation table names nothing: `National`.
- **NBS Tanzania** says TASCO is "domesticated from ISCO-08" — a national
  scheme with ISCO-88-era names (*Clerks*), so `National`.
- **ZamStats** goes furthest and names the hierarchy, ICSE-18-A; that is exactly
  the distinction that would be lost by defaulting.

### Row percentages are not collected

A table giving the sex split WITHIN each category ("Managers: 53.7% male") is a
different quantity from the share of employed men who are managers — but it
carries the same topic, category, sex and measure, so on merge one would
silently overwrite the other. Seychelles' 8B and 9B and Rwanda's 4.6 are
therefore left, and the column-percentage table is taken.

## Outputs accumulate

A run MERGES into `out/<country>_labour.csv` rather than replacing it, keyed on
`topic + characteristic + classification + sex + age_group + education +
geography + locality + locality_label + working_age_base + period + measure`.
These cross-tabs are published one round at a time — a quarterly bulletin, a
census volume — so without it every run would discard the periods before.

`characteristic` and `classification` are BOTH in the key because the same label
can belong to two schemes; collapsing them would silently drop one country's
category for another's.

## Layout

```
indicators/labour/
├── pipeline.py               # entry point: wires the labour CONFIG into the shared core
├── schema.py                 # LABOUR_COLUMNS (long format) + validate_labour()
├── sources/                  # one <country>.yaml descriptor per country
├── parsers/
│   ├── _common.py            # row builder + number/period/locale helpers
│   ├── excel_wide_labour.py  # engine: periods across columns, categories down rows
│   ├── <country>_labour.py   # one module per country: its LAYOUT
│   └── __init__.py           # REGISTRY: parser id -> parse()
├── source_data/              # RETAINED raw published files (audit trail)
└── out/                      # tidy <country>_labour.csv outputs
```

## Why the categories are SCANNED, not listed

An unemployment table has a fixed set of named indicator rows, and enumerating
them is right — a row that stops appearing is a real change worth failing on.

A labour cross-tab is a **classification**: ten industry groups, ten ISCO major
groups, twenty ISIC sections. Listing them in the layout would mean a new
category silently vanishing rather than being collected. So a layout says where
a block starts and what its categories MEAN, and every label between one block
header and the next is taken.

`expect_rows` is what makes scanning safe: a block yielding fewer categories
than the layout says it has raises, rather than quietly shipping half a table.

## The report-PDF engine, and what each option is for

`pdf_tables_labour.py` reads a report table from a declarative layout. Every
option below is opt-in, and a layout that sets none reads exactly as it did
before they existed (Zambia is the regression case: same 60 rows, same values).

| Option | The trap it answers |
|---|---|
| `caption` / `end` / `end_after` | **Several tables share a page, with the same row labels.** Statistics Botswana prints occupation counts (1.5a) directly above occupation percentages (1.5b), both nine columns wide, so selecting by page read the counts twice. A table is located by its caption and closed by the next caption — or, with `end_after`, by its own Total row, because Botswana's commentary quotes the table's figures: *"…from 144,200 persons (18.3 percent) in Q3 2023 to 153,044 persons (20.3 percent)…"* is six numbers and scans as a perfectly shaped industry row. |
| `caption_inline` | **The sub-heading shares its line with the first category.** Where a narrow first column wraps the heading, its tail sits level with the first data row and is rebuilt into it — HCP Morocco's *"groupes de professions (en %) Membres des corps législatifs … 0,9 0,5 1,3 0,1 0,9"* is heading, category and values on one line. Dropping the caption line whole would drop the first category of **every** block with it, so what follows the caption opens the region instead. Note the constraint this implies: a caption is tested against ONE line at a time, so a pattern spanning the heading's own wrap (*"selon les grands"* + *"groupes de professions"*) can never match, however well it matches the page. |
| `space_thousands` | **A space is not always a thousands separator, even in a French table.** Morocco's percentage blocks close on *"Total 100 100 100 100 100"* — five values, every group three digits, which the French space-grouping rule read as the single number 100100100100100. A table of percentages says so and gets five numbers back. |
| `barrier_pattern` | **A sub-heading is not a label fragment.** Naming the lines that introduce a stacked block keeps their text out of the following category's label, where it otherwise opened the region a row late and lost that block's first category. |
| `dash_placeholder` | **A dash is a cell, not a gap.** "613 - 613" is three columns. Dropping the dash slid every later value one column left; keeping its position and emitting nothing for it is right, because a dash is not a zero either. |
| `blocks` | **One table, several blocks.** Botswana's status-in-employment table repeats its categories for Total, Male and Female, marked only by a word at the start of each block's first row. |
| `period_header` + `period_index` | **Columns from more than one period.** Trend tables print Q4 2020 … Q1 2024 side by side. Periods are read from the table's own header line, never from an offset hardcoded against this issue — and the header line is then never read as data, or "ISIC High level 2019 … 2025" scans as an industry whose shares are years. |
| `label_is_period` | **Periods down the rows** (NISR's formality table), where each column names its category instead. |
| `split_digit_repair` | **Digits split by letter-spacing.** NBS Seychelles' text layer yields "7 5.4" for 75.4 and "1 00.0" for 100.0. Safe only where every value in the table carries a decimal — in a table of integers, "3 1.8" is two cells. |
| `text_mode: "words"` | **Labels wrapped over three to five lines**, with the numbers on whichever line is vertically central and continuations capitalised (NBS Tanzania: *"Water Supply, Sewerage,"* / *"Waste Management and 0.2 …"* / *"Remediation Activities"*). No line-by-line rule can tell whose label a fragment is; see below. |

### Rebuilding rows from word positions

`text_mode: "words"` splits each physical line into a label part and a trailing
number run. A line with numbers is a data row; a digit-free line lying entirely
left of a data row's first number is a label fragment; anything else (captions,
column headers) is a barrier no fragment is carried across.

Fragments between two data rows are shared out by **geometry, not by case or
punctuation**: a table cell centres its numbers against its label, so the split
chosen is the one leaving each row the most even number of label lines above
and below — solved for the whole page at once, because one row's choice fixes
its neighbour's. Ties go to reading sense: a lower-case fragment continues the
row above, a capitalised one starts the row below.

Two same-shaped cases show why case alone fails. In *"Agriculture, Forestry
and"* / *"52.4 …"* / *"Fishing"* / *"Mining and Quarrying 1.2"*, the
capitalised "Fishing" belongs **above**; in *"Transportation and Storage 8.1"* /
*"Accommodation and Food"* / *"1.5 …"*, the capitalised fragment belongs
**below**. Balance gets both right.

**Balance alone is not enough either**, and HCP Morocco is where it breaks. Two
occupation groups wrap around their own numbers with the second's label split
across the break:

```
Membres des corps législatifs, élus
locaux, responsables hiérarchiques
de la fonction publique directeurs et    0,9 0,5 1,3 0,1 0,9
cadres de direction d'entreprises
Cadres supérieurs et membres des
professions libérales                    3,4 10,7 7,3 0,8 4,9
```

Handing **both** loose lines to the row above balances the two rows perfectly —
it scored 1.1 against 3.0 for the right answer, and the capitalised-fragment
nudge could not overturn it. The result reads well and is wrong: one category
ends with the next one's opening words, and the next is published as
*"professions libérales"*, a fragment of *"Cadres supérieurs et membres des
professions libérales"* and a far narrower occupation than the group it names.

The missing evidence is in the second row itself: **a data row whose own label
starts lower-case is a continuation**, so its label began above it and it
cannot be left with none. That outweighs balance, as the lower-case fragment
rule does.

Which values belong to which group was settled by **geometry, not by reading**:
the "0,9" run sits at y=181, inside the first label's block (167–193), and the
"3,4" run at y=210, inside the second's (205–213). Read carelessly this
publishes the directors' 0,9 under "professions libérales". Worth restating,
because the arithmetic check cannot catch it — both readings sum to 100.

## The third engine: a cross-tab published as an HTML table

`html_wide_labour.py` exists for one NSO — **INS Tunisie**, which publishes its
quarterly series as real, server-rendered HTML tables on its theme pages rather
than as a file. The shape is the one `excel_wide_labour` reads (categories down
the rows, periods across the header) in a different container, so the layout
dict is the same idea: a `caption` regex, a `topic`, a `classification`, and
`expect_rows`.

**Why HTML and not the PDF** — this is the whole reason Tunisia is collectable.
INS's quarterly note is a bilingual Arabic/French document whose numeric runs
come out of the text layer **bidi-scrambled**, and differently in each table:
one row fully reversed, another rotated by four positions, a third with its
digits run together. There is no correct way to align those numbers with their
quarters, so the note is not parsed at all. `unemployment` reached the same
conclusion first, and both indicators read the same pages.

Three things the engine handles that a naive `read_html` would not:

- **The caption is above the table, not in it.** Each table is matched against
  the markup *preceding* it plus its own text, because INS titles each series
  in a heading.
- **Page furniture arrives as table rows.** "NoFilter", "Unité : Nombre",
  "Source : …" and the series title are rendered as rows with every period cell
  empty. They are skipped for **having no value**, not by being named, so one
  country's page chrome stays out of the engine.
- **A dash is a missing cell.** INS prints `--` where a quarter has no figure,
  and that cell is skipped rather than written as 0 — a fabricated zero would be
  a published figure that does not exist.

One more trap lived in the period parser rather than the engine. INS heads its
columns with French ordinal quarters — *"première-trimestre 2024"* — which
`parse_period` did not recognise, so every column would have fallen through to
the bare-year branch. Nine quarterly observations would have become three
annual ones **colliding on the merge key**: values that look entirely right,
filed under the wrong period. The ordinal form is now parsed, in step with
`unemployment`'s copy.

## Reading these tables — the traps met so far

1. **NaN is not a number.** `pandas.read_excel` returns NaN for every empty
   cell, and letting it through emits a row per blank. It also sweeps the
   sheet's FOOTNOTE lines in as categories — *"Due to rounding, numbers do not
   necessarily add up to totals."* became an industry — because a footnote with
   no values still looks like it produced some.
2. **A sheet can continue past the blocks you want, without a new header.**
   Stats SA's Table 3.10 gives formal/informal for Both sexes, Women and Men,
   then repeats the whole split by age, education, industry and occupation
   under sub-headings that are not block headers. Left to run, the scan
   attributed all of it to the last sex block: 164 colliding keys. `max_blocks`
   and `max_rows_per_block` bound it.
3. **Levels are often in thousands.** They are emitted as `thousand_persons`
   rather than multiplied out — multiplying is recomputation, and 14,437.74
   thousand is not an error.
4. **A block header carries the block total beside it.** That is a real
   published figure and is emitted as the topic's `"Total"`, not discarded.

Always check a parse against the source's own printed figures. Every country
module records the values it must reproduce, and `tests/test_offline.py` now
holds the sharpest of those checks as assertions.

## Where the next countries come from

Unusually cheap, and worth stating plainly: **23 of the 26 LFS documents already
discovered and retained by `unemployment/` contain industry, occupation, status
or formality tables.** The discovery routes are resolved and the files are on
disk; what is missing is a layout per country.

**Twelve of those have now been read**, which is what the richest of them were:
Botswana, Egypt, Ethiopia, Namibia, Rwanda, Seychelles, Somalia, Tanzania,
Zambia and Morocco through report PDFs, South Africa through its workbook, and
Tunisia through INS's server-rendered HTML pages.

**THAT TRANCHE IS NOW EXHAUSTED.** Every retained `unemployment` document has
been examined, and **no unexamined candidate remains**. Burkina Faso was the
last one that yielded anything.

> **Superseded 2026-09-29.** Every country in the table below except Benin,
> Côte d'Ivoire and Senegal is now collected from a *different* publication
> (see *The second tranche* further down). The verdicts stand for the documents
> they describe, which is why they are kept.

**Eight have been swept and carry no household composition**, recorded so none
is re-investigated blind:

| | |
|---|---|
| Mali | status as an infographic, industry as a three-sector chart |
| Nigeria | none of the four topics in the retained document |
| **Benin, Niger, Guinea-Bissau** | every *branche d'activité* / *ramo de atividade* / CSP table sits inside the ERI-ESI **informal-sector module** — UPI production units, capital in FCFA, aggregates — which is establishment-side, not household, data |
| **Sierra Leone** | the 2014 LFS report is **analytical**: Tables 12–17 are marginal effects, Heckman selection-corrected regressions and ordered probits, and only one table is composition |
| **Cameroon** | the retained file is a two-page *dépliant*. Its four composition titles — *par secteur d'activité*, *par secteur institutionnel*, *par statut du travailleur* — carry **no values at all**: checked word by word, there are zero numeric words anywhere near them. The figures on the page are rates, which `unemployment` already collects |
| **Côte d'Ivoire** | not reached: every anstat.ci URL, direct PDF paths included, answers with a Cloudflare interactive challenge (HTTP 403 "Just a moment...") to plain and browser-impersonating requests alike. Blocked on ACCESS, not content. The CPI and GDP descriptors for Côte d'Ivoire use the same host and fail the same way until it lifts |
| **Senegal** | ANSD's ENES is a *quarterly household* survey — the right universe, with fifteen issues listed back to 2022 Q3 — but every composition cut is a `Graphique`. Four issues across 2022–2026 carry **zero `Tableau` captions**, and the chart labels render as scattered glyph fragments (`% 8 .4`, `.1 6 7 .1 5`) that cannot be matched to their bars. Blocked, with the route kept |

Benin, Niger and Guinea-Bissau are the Kenya trap in French and Portuguese: an
informal-sector enterprise module reads like composition while counting a
different population. Each of the eight needs a **different publication** from
that NSO — Cameroon's full EESI3 phase-1 report, Guinea-Bissau's full ERI-ESI
report — which is *discovery* work, not parsing. Per the Kenya rule, check the
substitute is a household labour force survey before adopting it. Zimbabwe and
Kenya remain blocked.

**So further coverage came from NEW publications, not new layouts** -- and
the second tranche below is that.

### The second tranche (2026-09-29): 24 countries from publications not on disk

Every remaining NSO was searched for a HOUSEHOLD survey or census that prints
composition as tables, and 24 countries were added:

| Country | Publication | Rows | Periods |
|---|---|---|---|
| Cabo Verde | INE IMC "Mercado de Trabalho" workbook | 7,728 | 2011-2025 (13th/19th ICLS in `survey`) |
| Guinea | RGPH-3 2014 + EHCVM 2018/19 | 1,664 | 2014, 2019 |
| South Sudan | 2008 census tables (worked or worked previously) | 1,128 | 2008 |
| Mali | EMOP table workbooks | 1,074 | 2020-Q2..2025-Q2 |
| Madagascar | ENEMPSI 2012 workbook + RGPH-3 2018 | 1,049 | 2012, 2018 |
| São Tomé and Príncipe | RGPH 2012 thematic report 5 | 522 | 2012 |
| Comoros | EEIC 2021, RGPH 2017, EESIC 2013 | 495 | 2013-2021 |
| Nigeria | NLFS Annual Report 2023 | 479 | 2023 |
| Mozambique | IOF 2022 | 462 | 2022 |
| Equatorial Guinea | ENH2 2022-23 | 297 | 2023 |
| Libya | LFS 2022 (Libyan nationals) | 240 | 2022 |
| Zimbabwe | LFCLS 2019 annual report | 228 | 2019 |
| Sierra Leone | PHC 2015 + SLLFS 2014 Table 2 | 207 | 2014, 2015 |
| Cameroon | EESI3 main report | 200 | 2021 |
| Mauritania | ENESI 2017 + RGPH 2013 | 194 | 2013, 2017 |
| Central African Republic | RGPH03 economic characteristics | 189 | 2003 |
| Togo | ERI-ESI 2017, chapter 5 | 100 | 2017 |
| Niger | ERI-ESI 2017, chapter 5 | 96 | 2017 |
| Gabon | RGPL-2013 Résultats globaux | 80 | 2013 |
| Djibouti | RGPH-3 2024, Tome 3 | 78 | 2024 |
| Guinea-Bissau | RGPH 2009 annexes (counts only) | 40 | 2009 |
| DR Congo | Enquête 1-2-3 2012 (Wayback copy of INS's own file) | 40 | 2012 |
| Chad | ECOSIT4 2018-19 | 32 | 2019 |
| Burundi | Annuaire statistique, T6.01 (four surveys) | 24 | 2010-2020 |

Each module's docstring records what was taken, what was refused and why, the
traps, and hand-checked figures. What generalises:

* **"SWEPT" WAS A VERDICT ABOUT ONE DOCUMENT, NOT ABOUT THE NSO.** Mali's
  bulletin draws its cuts; its EMOP workbooks tabulate them. Cameroon's
  dépliant has no values; its main report does. Zimbabwe's quarterly QLFS draws
  composition; its annual report prints it. Niger's and Togo's ERI-ESI reports
  hide household tables in chapter 5 behind the UPI chapters. Before recording
  a country as empty, find the main report, the table workbook, the annual
  round and the census volume.
* **CHECK THE UNIVERSE AGAINST THE REPORT'S OWN EMPLOYED TOTAL.** Niger's
  "Bilan de l'emploi" was collected because its total is 99,3% of the
  report's employed count; Togo's (22% of it), Guinea-Bissau's ERI-ESI tables
  (61%), Zimbabwe's Table 4.8 and SLIHS 2018's Table 5.10 (larger than the
  employed) were refused for the same reason. A clean-looking distribution
  over an unstated population is not collectable.
* **"COM SITUAÇÃO DECLARADA" TURNS SHARES INTO A SELF-SELECTED SUBSET.**
  Guinea-Bissau's census declares occupation for 30% of the employed, and
  unevenly by sex; the counts and the declared subtotal are collected, the
  shares are not.
* **A TOTAL COLUMN MUST BE A WEIGHTED AVERAGE OF ITS PARTS.** An Ensemble
  outside its male/female range is not a national figure (Mali 2023: a copy of
  the Rural row, now caught by a guard); a national column that no weights can
  reproduce contradicts itself (DR Congo I.5.4's activity block, refused).
* **COPIED ROWS AND COLUMNS ARE A RECURRING PUBLISHED DEFECT** -- Mali 2023,
  Cabo Verde TAB_31 (urban/rural = national), CAR Eco 13 (Region 3 = Region 4),
  Chad 7.10 (Masculin = Ensemble urbain). Each is dropped by an explicit,
  re-checked rule so that a correction by the NSO is noticed.
* **A WORKBOOK THAT REPRINTS A CELL ACROSS SHEETS IS A FREE CONSISTENCY CHECK**
  (Cabo Verde): dedupe by comparing values, never keep-first silently.
* **ROTATED HEADERS AND ROTATED PAGES**: pdfplumber reverses tokens on rotated
  pages ("5,37" for 73,5); PyMuPDF word positions keep order. Column order from
  unreadable headers is taken from geometry or from a legible companion table,
  and ASSERTED every run (Mozambique, Guinea, South Sudan, Madagascar).
* **A BROKEN FONT MAPPING CAN CORRUPT DIGITS TOO** (Libya: "2022" reads "2222"
  in captions). Labels were stated from the rendered page; rows anchored by the
  table's own arithmetic.
* **A SCHEME NAMED IN THE METHODOLOGY MAY BE THE PREVIOUS ROUND'S** (Madagascar:
  "En 1993 ... CITI"; RGPH-3 used NOMAC). Read the sentence before tagging.
* **A "% distribution" beside a sex's counts can be a share of the GRAND
  total** (Sierra Leone PHC 2015 Table 3.7) -- divide before filing it by sex.

HARNESS CHANGES: `download_timeout` (seconds) is a new optional `discover:`
key for slow hosts (INS Cameroun stalls mid-transfer on a 43 MB report);
`pymupdf` joins requirements.txt (Burundi, Zimbabwe, Madagascar, South Sudan
and others read one-cell-per-line or word-position text with it).

### The third round (2026-10-01): five blocked countries unblocked, two deepened

| Country | Publication | Rows | Note |
|---|---|---|---|
| Kenya | KIHBS 2015/16 Labour Force Basic Report, Table 3.8 | 360 | usual weekly hours only -- KNBS prints no household industry/occupation/status table |
| Senegal | ERI-ESI 2017 chapter 5 + EHCVM 2018/19 ch. VII | 275 | the ENES quarterly notes stay chart-only |
| Benin | ETVA 2014 school-to-work survey (Wayback copy) | 258 | youth 15-29 only; CITI Rév.4 / CITP-08 named |
| Côte d'Ivoire | EHCVM 2021 (Wayback copy) | 64 | formal/informal only; base 16+ |
| Republic of Congo | ECOM 2005 + EESIC 2009 phase 1 (Wayback copies of cnsee.org) | 63 | EESIC covers Brazzaville and Pointe-Noire only |

Nigeria grew from 479 to 5,739 rows (145 of the NLFS's 148 per-state annex
tables) and Zimbabwe from 228 to 1,231 (chapter-5 youth tables), each with
every earlier row re-emitted unchanged.

* **"BLOCKED ON CONTENT" WAS STILL A VERDICT ON ONE PUBLICATION.** Kenya's and
  Senegal's blocks named the right reason for the document examined; the
  household survey that answers was a different series (KIHBS; ERI-ESI and
  EHCVM). Kenya's KNBS search page links none of its reports, but WordPress's
  `/wp-json/wp/v2/media?search=` lists every upload.
* **THE WAYBACK MACHINE IS THE ROUTE WHEN THE NSO HOST IS GONE, NOT AN
  AGGREGATOR.** DR Congo, Republic of Congo, Côte d'Ivoire and Benin are read
  from `id_` captures of the NSO's own PDFs (original bytes); each descriptor
  says so. The archive answers `requests` with 429 at times, so those set
  `impersonate`.
* **PUBLISHED DEFECTS KEEP APPEARING IN DEEPER TABLES**: Zimbabwe 5.4aii's
  female column copies the male one, 5.5aii's urban/rural rows are swapped, and
  5.6ai's two Matabeleland provinces are labelled the wrong way round (each
  refused or re-checked); Nigeria's T28 header misprints two groups, and T144
  and T148 wrap digits inside columns (refused, detected by the header).

HARNESS FIXES: `download_timeout` and `impersonate` now apply to `extra_urls`
as well as the primary file. And a CORPUS-WIDE MERGE BUG was found and fixed:
`_merge_with_existing` re-read the prior output with pandas' default NA
strings, so a category published as "NA", "N/A", "None" or "null" came back
blank, matched nothing, and was written again -- one duplicate per run. INE
São Tomé's CAE-STP column "NA" had already been duplicated (8 rows, repaired
by regenerating); Ghana's census "None" category would have been next.
`test_merge_keeps_literal_na_category` guards it, and is mutation-checked.

STILL TO WATCH: Kenya's 2026 Integrated LFS; instad.bj's rebuild (Benin -- its
ERI-ESI household chapter should replace the youth-only ETVA); anstat.ci's
Cloudflare challenge (Côte d'Ivoire -- the ENE reports have the full
composition); ANSD's ENES and ZIMSTAT's quarterly QLFS in case they start
printing tables. Eswatini's (gov.sz) and Mozambique's (ine.gov.mz) hosts timed
out on the 2026-10-01 `--all` run; their outputs are retained.

South Africa proves the pattern — its descriptor points at the same workbook
`unemployment/` collects, and each indicator opens only its own sheets, so no
figure is written twice. Botswana, Seychelles, Rwanda and Tanzania now do the
same with report PDFs, each reusing that country's `discover:` block verbatim.

**That gap is now closed.** `excel_wide_labour` reads wide workbooks and
`pdf_tables_labour` reads report PDFs with the same declarative layout, so a
new country is a layout plus a descriptor rather than a new engine.

**Namibia was the worst text layer met so far, and is now done.** The PHC 2023
report is present TWICE in the text layer, the copies three to five points
apart, so rows of one merge with rows of the other and the words interleave.
The dangerous product is not garbled nonsense but a row whose label is
destroyed while its numbers stay correct and well formed —
`EEmmppllooyyemee nt status 462,996 84.7 …` — which nothing downstream would
question. The copies are complementary, each printing cleanly what the other
mangles, so both pages are read and the labels dedupe; artefact lines are
excluded by three signatures no clean row carries. See
`parsers/namibia_labour.py`.

**Egypt was the last known-awkward one, and is now done** — but it is the most
fragile layout here and worth understanding before anyone edits it. CAPMAS
publishes TRANSPOSED tables: the categories run across the COLUMNS and each row
is a sex, so reading order names nothing. The bulletin is printed right to
left, so the columns run in REVERSE (Financial and insurance first, Agriculture
last), and the header cells resolve only by position.

That column order was established from PAGE GEOMETRY — each numeric column's
x-centre matched to the header cell above it — and then confirmed by the
report's own arithmetic: each sex's 21 activity shares sum to 100.0 across the
table's two pages (male 83.7 + 16.3). **The caveat is worth carrying:** those
sums corroborate the mapping but would also survive two similar-sized columns
being transposed. Geometry is the evidence; the arithmetic is the check.

Two deliberate omissions: the regional breakdowns (the block label is
vertically centred and lands on the middle row in one table, the first row in
another, so attributing a region would be guesswork) and Table (13) employment
status (two of its four column headers cannot be read from the page at all).

**Somalia set the precedent for a truncated source, and is now done.** SNBS's
table export clips every category at about 38 characters, mid-word —
*"Technicians and assoc"*, *"Production and specialized services ma"*. Those
are collected verbatim: completing them would publish text the NSO did not, and
guessing which ISCO group a clipped string denotes is the inference this
collector exists to avoid. A reader can see the truncation; a silent repair
would hide it.

**Zimbabwe WAS blocked, and is now collected from the annual report.**
ZIMSTAT's quarterly QLFS still publishes the composition of employment as
CHARTS only -- the text layer under *"Figure 10: Distribution of Employed
Population by Occupation and Sex"* carries the sex totals and nothing else --
but its 2019 Labour Force and Child Labour Survey report prints status,
industry, ISCO-08 occupation, sector and informal employment as tables. Table
4.8 (institutional sector) is refused: its base (1 422 153) is neither the
employed nor any stated subset of them.

**Kenya is blocked too, and for a reason worth reading before substituting any
source.** The KNBS Quarterly Labour Force Report has ten tables and all ten are
labour-force status — participation, employment-to-population, LU1/LU2/LU3,
long-term unemployment, NEET, persons outside the labour force. No composition
table exists in it, and the series ended: KNBS ran the QLFS to 2022 Q4 and
bulk-archived the run.

KNBS *does* publish employment by industry, in the Economic Survey's Chapter 3
workbook — and it is deliberately **not** used. That file is establishment and
administrative data: payroll and public-record jobs, excluding the informal
sector and agricultural self-employed, who are most of Kenyan employment. It
would land in the `industry` topic under the same merge key as household-survey
composition from a dozen other countries while counting a different population,
with nothing in the row to say so. That is the cross-country join the
`classification` column exists to prevent, one level up — and collecting it
would make the corpus look more complete while being less true. The 2026 Kenya
Integrated Labour Force Survey, now in the field, is what unblocks it.
Recorded in `sources_blocked/`.

**Liberia is done, through LISGIS's new API.** The old placeholder site is
gone; the new one is a single-page app whose `/api/survey-report-grid` lists
each survey report with a direct download. The LFS 2016-17 report follows the
same ILO template as Gambia's: ICSE-93 status, ISIC Rev 4 sections, ISCO-08,
and formal/informal jobs. One trap is new. Table 5.4 prints each label BELOW
its numbers, word geometry shifted them one row, and "Informal sector" got the
household figures. It is read from the text layer instead, with a sum check.
The report itself warns that "not elsewhere classified" is 43.5% of industry.

**Lesotho is done, and it was never really dataless.** bos.gov.ls builds its
publication list in the BROWSER from a JavaScript array in `publications.htm`,
so a crawler sees only policy PDFs, which is why earlier sessions recorded no
data files. The array lists the 2024 and 2019 LFS reports and the 2019
statistical-tables volume, each a ZIP holding one PDF. They give occupation
(ISCO-08) and industry (ISIC Rev.4) by sex and settlement type, ICSE-18-A and
ICSE-93 status, and 2019 formality. The trap: ICSE-18-A's five group headings sit
on lines of their own, and word geometry folded them into the category below
("Dependent contractors Dependent contractors Employees"). The layout now marks
them as barriers. The two "sector" tables count EMPLOYEES, not the employed,
and are left out.

**Uganda is done, and the earlier sweep was wrong about it.** That sweep read
only UBOS's findings DECK, where the sector split is a chart. The 247-page LMS
2025 main report prints it as a table twice: Table 3.2 on the ILO 15+ base and
Table A4.7 on the national 14-64 base, each by sex, rural-urban and 14
sub-regions. A4.7's two survey waves (March-May, June-August) straddle quarter
boundaries and are not taken; its Overall column is. The report's chapters
7-8 count employment through BUSINESSES, which is establishment data and is
excluded. The lesson for the other "swept" countries: a findings deck or key
findings note is not the report; look for the main report before recording a
country as chart-only.

**Gambia is done: four GLFS rounds from three findings reports.** GBoS names
its schemes, so these rows carry ISIC Rev.4, ISCO-08 and ICSE-93 rather than
National. The 2026 report prints 2025 (Q1) and 2026 (Q1) side by side, with
columns dated from the table header. The 2022-23 report adds status by sex and
residence, branch counts and occupation by sex. The 2018 round is on a 15-64
base. Two traps: GBoS wraps long labels both above and below their numbers,
so the layouts read WORD POSITIONS; and ISIC section T, once rejoined, is 120
characters long, past the engine's default 80, so the row was SKIPPED WITHOUT
AN ERROR until `expect_rows` caught 21 of 22. The 2025/2026 status and sector
cuts are image figures with no text values, and are not collected.

**Angola is done, and it needed the harness to learn POST.** INE publishes the
IEA as time-series workbooks whose "links" are onclick handlers that POST
`filepath` to `/Diretorios/Download`, so `core/fetch.download` now takes
`post_data` and the `ine_ao_directory_files` discovery walks INE's directory
tree by folder name. Two workbooks, one per METHODOLOGY, never chained:
13th-ICLS "Quadros complementares" (2019 Q2 to 2025 Q3, quarterly and annual:
ten branch groups, twelve "situações perante o emprego", and Quadro 9's
informal/formal counts) and 19th-21st-ICLS (from 2025 Q4: 21 branches, six
employer types filed as `sector`). `survey` names the basis on every row,
because employed fell from 14,3 to 8,9 million across the break by definition
alone.

Two published defects are handled explicitly rather than smoothed. The 2020
"Anual" branch column sums to 100 but its values sit against the wrong labels
(Agricultura 1,33, Administração 55,75), so it is dropped by name and
re-checked every run, so that a correction by INE is noticed. 2024 Q1 sums to
104,57 in both old blocks (and 2024 Anual to 101,07): a uniform inflation, not
a mislabelled row, so it is kept with the published sum pinned.

**Algeria came from a RETROSPECTIVE, not a bulletin, and is now done.** ONS's
only recent labour release is a three-page 2024 communiqué with the
unemployment rate in prose. The composition lives in the *Rétrospective
Statistique 1962-2020*, Chapitre II, which reprints one table per survey
round: 25 LFS rounds (June 2000 to May 2019, two a year in 2014 and 2016-18),
the 1989-92 Main d'œuvre surveys by sex, 1997, and the 1977 and 1987 censuses.
Where a country's current releases are thin, look for its yearbook or
retrospective before calling it blocked.

Its trap is **adjacent counts with SPACE thousands**: `964 020 11 090 975 110`
reads more than one way. `parsers/algeria_labour.py` splits each row under the
table's own arithmetic (hommes + femmes = total, urbain + rural = ensemble) and
raises on a row with no consistent split. That check found a real misprint
(RGPH 1977's Administration row +60, Autres Services -60, every column still
summing to its Total), which is collected as printed through an explicit,
digit-verified whitelist. Rounds are dated to the quarter of their reference
month, since two a year would collide on an annual period. The working-age base
is recorded as `not stated`, because the June 2000 age table counts 25 075
employed under 15.

**Mali and Nigeria were once "swept and found nothing"** -- Mali's bulletin
draws its cuts, Nigeria's retained quarterly carries none. Both are now
collected from different publications (EMOP workbooks; the NLFS annual
report), which is the point of the rule that followed: a different
publication, checked to be a household survey, not more parsing effort.

## Schema (tidy long format)

25 columns, `schema.LABOUR_COLUMNS`. Beyond the usual identity and provenance
fields, the ones that carry the meaning:

- `topic` — activity_status, employment_status, industry, occupation, sector,
  formality, hours, earnings
- `characteristic` — the published category, verbatim
- `classification` — ISIC Rev.3/3.1/4, ISCO-88/08, ICSE-93/18, National, or
  Not applicable
- `working_age_base` — "15+", "15-64", "10+" … as the NSO defines it
- `measure` / `unit` — count | rate | share, with persons | thousand_persons |
  percent
- `period` — `YYYY`, `YYYY-Qn` or `YYYY-Hn`

## Run

```bash
# offline self-test — no network. Run it after editing a layout or the engine,
# BEFORE running against the network.
PYTHONUTF8=1 py -W ignore -m indicators.labour.tests.test_offline
PYTHONUTF8=1 py -W ignore -m indicators.labour.tests.check_registry

# online (discover → download → parse → validate → merge → write)
PYTHONUTF8=1 py -W ignore -m indicators.labour.pipeline south_africa
PYTHONUTF8=1 py -W ignore -m indicators.labour.pipeline --all
```

## The test suite, and what it is for

`tests/test_offline.py` replays the **actual printed lines** of published
tables through the real parsers and the real validator, with no network. Every
fixture is verbatim from the document the collector downloaded — the MPI suite
learned that the hard way, when fixtures reconstructed from notes all turned
out to have the wrong number of columns and passed against a parser that could
not read the real report. *A fixture written to match the layout tests nothing.*

It exists for one failure mode: **a row whose value is well formed, in range,
correctly typed, and attached to the wrong series** — which no validator can
see. So the cases are the traps, not the happy paths:

| | |
|---|---|
| Morocco, word positions | two groups wrap around their own numbers; the wrong split publishes the directors' 0,9 under "professions libérales". Real page-25 coordinates |
| Eswatini, word positions | "supply" on its own line — balance alone assigns it to the row below, truncating one category and prefixing the next |
| Morocco, end to end | a caption sharing its line with the first category; five columns that are **two** dimensions; `Total 100 100 100 100 100` |
| Burkina Faso | a chart whose values are text data labels, with the x-axis tick line directly beneath them |
| Tunisia | HTML furniture rows, `--` as a missing cell, and French ordinal quarters |
| Zambia | six columns, labels wrapping three ways, a dash row that must be skipped — and published `0.0` shares that must **survive** |
| Morocco, lost leading zero | a category whose values print as `,0 ,1 ,3` must still be read — the label pattern has to end at the first *value*, comma or digit, not the first digit |
| The guards | `expect_rows`, the classification requirement, period format, share range |

**It is mutation-checked.** Removing the lower-case continuation rule, the
lower-case fragment penalty, the `space_thousands` opt-out or the French
ordinal branch each turns the suite red, on the assertions written for them —
breaking the ordinal branch collapses Tunisia's nine quarters to three bare
years, which is exactly the silent corruption the test exists to catch.

`tests/check_registry.py` is the offline pre-flight: every descriptor's
`parser:` resolves, every `discover.method` is one `core/run.py` dispatches on,
and nothing in `sources_blocked/` is also live in `sources/`.

> **Windows:** run as `PYTHONUTF8=1 py -W ignore -m …`. These reports carry
> accented French, Portuguese and Arabic, and the cp1252 console will throw
> `UnicodeEncodeError` mid-run without it.

## Principles

- **As published** — no estimation, imputation, rescaling or recomputation.
- **No aggregators** — ILOSTAT, the World Bank, IMF and similar re-estimate or
  harmonise national figures and are excluded. Only the NSO's own publication.
- **Never remap a category** — record the NSO's scheme instead.
- **All periods** — every period a document publishes, merged rather than
  replaced.
- **Auditable** — the raw published file is retained for every country.

## Adding a country

1. Write `sources/<country>.yaml` — agency, publication, and how to find the
   current file. If `unemployment/` already collects that country, reuse its
   `discover:` block verbatim.
2. Write `parsers/<country>_labour.py` — a `LAYOUT` naming each table's sheet
   or page, its `topic`, its `classification`, its blocks and its
   `expect_rows`.
3. Register it in `parsers/__init__.py`.
4. Run the country, and check the output against the figures the report prints.
   Record those figures in the module.
