# Unemployment / Labour Force collector

Captures the headline labour force survey indicators — unemployment rate,
labour force participation rate, employment-to-population ratio, the level
counts behind them, and the underutilisation ladder — **strictly from each
NSO's own publication**, exactly as published.

```bash
python -m indicators.unemployment.pipeline south_africa
python -m indicators.unemployment.pipeline --all
```

Offline checks (no network, run these first and after every layout edit):

```bash
python -m indicators.unemployment.tests.check_registry   # descriptors resolve
python -m indicators.unemployment.tests.test_offline     # parsers + validator
```

> **Windows:** run everything as `PYTHONUTF8=1 py -W ignore -m …`. These reports
> are full of accented French, Portuguese and Arabic and the cp1252 console
> will throw `UnicodeEncodeError` mid-run without it.

---

## 1. What makes this indicator different

Three things bite hard here and each gets a first-class schema column, because
collapsing them silently produces a nonsense cross-country series.

**`definition` — an unemployment rate is meaningless without saying which one.**
Senegal publishes 5.4% (BIT strict) and 23.3% (élargi) for the *same quarter* —
a four-fold difference. South Africa publishes 33.6% official and 43.8%
expanded. Cameroon, Zimbabwe, Botswana, Namibia and Eswatini all publish a
strict and a broad measure under different names (élargi, expanded, relaxed,
extended, LU3, CRUPLF). Every rate row carries `strict` or `broad`.

**`working_age_base` — the denominator's lower bound is not 15+ everywhere.**

| base | countries |
|---|---|
| 15+ | most |
| 16+ | Rwanda, Zimbabwe, Mauritius, Burkina Faso |
| 14+ | Cameroon (collected 10+, published on the legal working age) |
| 10+ | Ethiopia |
| 15–64 | Sierra Leone (the only closed upper bound) |
| 15+ *and* 14–64 in parallel | Uganda |
| 15+ *and* 18+ in parallel | Angola, Botswana |

**`locality` / `locality_label` — urban/rural is not always binary.** Burkina
reports Ouagadougou / Bobo-Dioulasso / autres urbains / rural; Benin reports
Cotonou / autres urbains / rural; Cameroon reports Douala / Yaoundé / urbain /
rural. `locality` is the coarse controlled value for joining; `locality_label`
keeps the NSO's own stratum name.

Also worth knowing before using the data: **youth is not one age band.** Zambia
defines it as 19–34, Botswana/Eswatini/Namibia as 15–35, South Africa reports
15–24 and 15–34, Zimbabwe reports both 15–24 and 15–35. `age_group` always
carries the country's own band.

---

## 2. Architecture

Standard collector shape — the shared `core/` harness plus this indicator's
descriptors, parsers and schema. See the repo's `DEVELOPER_GUIDE.md`.

```
indicators/unemployment/
  pipeline.py               entry point; injects paths/parsers/schema into core
  schema.py                 the 25 canonical columns + validate_unemployment()
  sources/<country>.yaml    the DESCRIPTOR: where/how to get the data
  sources_blocked/          descriptors kept whole, but not currently fetchable
  parsers/
    __init__.py             REGISTRY: parser id -> parse()
    _common.py              number/period/locale helpers shared by all parsers
    _vocab.py               column vocabularies shared across layouts
    <country>_unemployment.py   ONE MODULE PER COUNTRY: its LAYOUT + parse
    pdf_key_indicators.py   the engine those layouts are read by
    ghana_pxweb_unemployment.py  bespoke Tier-1 PxWeb reader
    mali_pdf_bulletin.py    reads an infographic by glyph position
    excel_wide_series.py + excel_layouts.py   periods-across-the-columns workbooks
    mauritius_excel_cmphs.py     periods DOWN the rows
    egypt_excel_lfs.py           a single-quarter workbook (kept for when
                                 CAPMAS next publishes one)
    html_wide_series.py + html_layouts.py     INS Tunisie's theme pages
  tests/                    offline checks (no network)
  source_data/<Country>/    retained raw NSO files
  out/<country>_unemployment.csv
```

**One module per country.** The PDF layouts began as a single 1,900-line
`layouts.py`. They are now one module each, so a country's layout sits beside
its own descriptor and its own notes — the shape every other indicator in this
repo uses. Splitting them changed no output: all 26 files were byte-identical
before and after.

**Why one config-driven parser instead of thirty bespoke ones.** Thirty LFS
reports were read while building this, and they all fit one model: *a table is
a grid of row specs by column specs, and every cell inherits the union of its
row's and its column's attributes.* That absorbs every layout encountered —
indicator-rows (Nigeria), the transpose (Sierra Leone), period-columns (Rwanda),
one-topic-per-table (Tanzania, Eswatini), and a two-level `Number | Percent`
header (Zimbabwe). A column-order fix becomes a one-line edit in that country's module
rather than a rewrite. Write a bespoke parser when a country is genuinely odd;
`ghana_pxweb_unemployment.py` is the model for that.

---

## 3. Country registry

**54 descriptors, 53 countries — 57,248 rows, 1966 to 2026 Q2** (2026-10-01).
Only Eritrea is missing: it has no statistics website at all.

| | |
|---|---|
| Quarterly | Botswana, Egypt, Ghana, Kenya, Mauritius, Nigeria, Seychelles, South Africa, Tunisia, Zimbabwe, Senegal (ENES), Mauritania (ENTE), Djibouti (EDST), Morocco |
| Annual / per round | Rwanda, Tanzania, Zambia, Cabo Verde (IMC 2011-2025), Mali (EMOP 2020-2025), Algeria (23 LFS rounds 2000-2019, rate back to 1966), Gambia, Lesotho, Malawi |
| Ad hoc / periodic | Benin, Burkina Faso, Cameroon, Eswatini, Ethiopia, Guinea-Bissau, Namibia, Niger, Sierra Leone, Somalia, Uganda, Angola, Liberia, Burundi, Chad, Comoros, Congo, Côte d'Ivoire, DR Congo, Central African Republic, Equatorial Guinea, Gabon, Guinea, Libya, Madagascar, Mozambique, São Tomé and Príncipe, South Sudan, Sudan, Togo |

The deepest series are South Africa (2,618 rows, 74 quarters back to 2008 Q1),
Ghana (6,426 rows) and Mauritius (204 rows over five quarters). Tanzania and
Rwanda publish multi-year trend tables and both years/all seven are captured.

### Angola — unblocked by POST support

INE serves the IEA as five workbooks whose "links" POST a file path to
`/Diretorios/Download`; `core/fetch.download(post_data=…)` and the
`ine_ao_directory_files` discovery now fetch them (`parsers/angola_ine_workbooks.py`).
The headline series come in three blocks (15+, the 15-24 youth cut, an 18+ base),
the complementary workbook gives rates by residence, sex and age, and a fifth
file gives the 18 provinces annually. **Never chain across the methodology
break**: participation is 87-89% on the 13th-ICLS basis (to 2025 Q3) and 50-56%
on the 19th (from 2025 Q4); `survey` names the basis on every row. The
complementary workbook repeats headline cells and five differ by up to 0,05
points; the series value is kept and a gap over 0,1 raises. The earlier bulletin
layout (`angola_pdf`) is kept in case INE resumes the PDF.

### Liberia — unblocked by LISGIS's rebuilt site

LISGIS's placeholder site is gone; the rebuilt one is a single-page app whose
`/api/survey-report-grid` lists each survey report with a direct download, and
the LFS 2016-17 report sits at `/uploads/surveys/lfs-2016-2017.pdf`. The copy
served there wraps Table 3.1's row labels across up to four lines, and line
matching read the informal-employment COUNT as its share. So the table is
read BY POSITION (`parse_positional`): its 17-number rows are taken in printed
order and the mapping is proved in every column (LF = E + U, population = LF +
outside, LU1 = U/LF, LFPR = LF/population). An offline test swaps two rows and
must see it raise.

### Blocked — `sources_blocked/`

None at present. Liberia and Angola, the last two, are both restored.

### The 2026-10-01 round: 28 → 53 countries

Twenty-five countries were added, most from documents `labour/` had already
retained (its parsers had skipped the rate tables as this indicator's
territory), and the rest from NEW publications found for this purpose: Malawi's
full LFS 2024 report (the default link is a charts-only brochure), Guinea's
ENESIG 2018/19, Madagascar's EPM 2021-22, Mozambique's IOF 2019/20, São Tomé's
IOF 2017 and QUIBB 2005, Equatorial Guinea's EPAFE 2015, the quarterly ENTE
(Mauritania), EDST (Djibouti) and ENES summary boxes (Senegal), and Wayback
`id_` copies of the NSO's own files where the host is gone (Congo, DR Congo,
Côte d'Ivoire's ENSETE 2013, Sudan's CBS booklet and 2008 census -- NORTHERN
Sudan only, the census predating the South's secession).

Depth was added to eight existing countries: Nigeria 90 → 10,316 rows (2023
annual report, all states), Kenya 464 → 2,091 (QLFS back issues + KIHBS
2015/16), Uganda 8 → 1,447, Mali 9 → 1,061, Botswana 51 → 656, Zimbabwe 18 →
486, Morocco 20 → 296, Seychelles 21 → 177 -- every earlier row re-emitted
unchanged.

Each module's docstring records the published defects refused or pinned. The
recurring kinds: ladders out of order (SU4 below SU2: Mali 2021-22, Guinea);
copied rows/columns (Mali 2023's 65+ row, Djibouti Q2's underemployment row,
Gambia 2025's sex columns, Mauritania A4.3); captions naming the wrong
population (Libya Table 8 "active" = employed; Gambia 2018 "unemployment rate"
tables that are distributions); and summary boxes disagreeing with their own
annex (Djibouti Q4 37,7 vs 37,3).

`definition` stays the NSO's own: Mozambique's "definição alternativa" (job
search dropped) and Malawi's report-wide rate are `broad`; census concepts
without an availability test (CAR, South Sudan) are `not_applicable`.

STILL TO DO: discovery methods so Mauritania's ENTE and Djibouti's EDST notes
update themselves (they are pinned per quarter today); Kenya's six scanned QLFS
issues; Nigeria's Q1 2024 report layout; Tanzania/Egypt/Namibia back issues.
ANSADE throttles hard (Mauritania `download_timeout: 900`); ine.gov.mz and
instat-mali.org time out intermittently -- retry before concluding a source
is broken.

---

## 4. What this collector deliberately will not do

Several NSOs publish their headline numbers **only as infographics or chart
data labels**, with no table anywhere in the document. Chart labels drop
trailing zeros (`80` for 80,0, `6` for 6,0), carry no category names, and sit
immediately next to the y-axis tick sequence (`0 2 4 6 8 10 …`), which a
positional parser will happily ingest as data. Scraping them produces numbers
that look right and are wrong.

Where a country has a *different* document that does contain tables, that one
is collected instead — which is why Burkina Faso is collected from the ENB-ESI
note rather than the fresher ENSE bulletin, Rwanda from the annual report rather
than the quarterly panel, and Mali from a summary box rather than its eleven
figures. Where no such document exists, the country is documented, not bodged:

- **Senegal (ANSD, ENES)** — the current release is a four-page note whose
  front page is an infographic and whose body is prose plus Graphiques 1–7.
  Zero `Tableau` captions. Worse: the infographic's bare "Chômage 23,3%" is the
  **élargi** figure, unlabelled, while the BIT-strict rate (5,4%) appears only
  in prose — a parser keying on the word "Chômage" would be wrong by a factor
  of four. The 2022–2024 "Rapport ENES" releases *do* carry tables and are the
  route in; see PENDING.md.
- **Burkina Faso (INSD, ENSE bulletin)** — 26 `Graphique` captions and zero
  `Tableau`, and INSD's own NADA listing attaches no Excel or CSV to any ENSE
  round. The ENB-ESI note is collected in its place.
- **Rwanda (NISR, quarterly bulletin)** — a graphic panel; its disaggregations
  are chart images. The annual report's trend table is collected instead.
- **Mali (INSTAT bulletin)** — eleven `Figure` captions and zero `Tableau`.
  Three attempts to read the chart labels returned mutually contradictory
  category sets and values. Only the arithmetically self-verifying summary box
  is taken.
- **Uganda (UBOS, LMS 2025)** — the indicators are bar charts; only two slides
  are genuine grids, and only those two are parsed.

Recovering the rest needs either a bespoke chart-label parser with the category
order pinned from the surrounding prose, or a different source tier.

The same discipline applies to **aggregators**: ILOSTAT, World Bank, IMF,
Trading Economics and `*.opendataforafrica.org` (Knoema) all re-estimate and
are banned as sources — including where the NSO's *own site* links to them,
which Botswana, Lesotho, Malawi, Gabon, CAR and Congo all do. Two live examples
of why this matters: Côte d'Ivoire's widely quoted 2.3% unemployment rate is an
**ILOSTAT re-estimate** from ANStat microdata, not an ANStat figure (its own
published rates are 3.1% and 3.4%); and `data.gouv.ci` exposes a clean,
working JSON API of Ivorian employment indicators that is published by a
private data firm, not the NSO.

And it applies to **the wrong document from the right agency**. Kenya's
Economic Survey Chapter 3 workbook is fresher and more structured than the
discontinued QLFS, but it is establishment and administrative employment, not
an ILO household unemployment rate — a different universe, so the QLFS
backfill is collected and the workbook is not. Guinea's quarterly BTSMT
bulletin is likewise AGUIPE/CNSS registry data with no unemployment rate at
all, and Gabon's quarterly SIMT bulletin is formal-sector administrative data.
Freshness does not make a series the right one.

---

## 5. Known limitations of this build

Stated plainly, because they determine what the first run will do.

1. **No PDF or workbook could be downloaded during development.** The build
   environment sits behind an egress allowlist that 403s every NSO domain, so
   layouts were written against report text rendered through a fetch tool, not
   against the binaries. **Ghana's API source and the parsing machinery are
   verified** — the offline suite replays the actual printed tables of Namibia,
   Zambia, Nigeria, Niger, Liberia, Botswana and Rwanda, plus a synthetic Ghana
   PxWeb response and a Tunisia HTML page, through the real parsers and the real
   validator. The per-country PDF and Excel *layouts* are grounded in the real
   printed tables but have not been run against the real files. Expect some to
   need a column-order or regex adjustment on the first run — that is a one-line
   edit in `layouts.py`, and every layout carries its published cross-check
   values in a comment so you can tell immediately whether it worked.
2. **Three layouts are explicitly unverified beyond their structure.** Egypt's
   Arabic workbook, South Africa's and Mauritius's workbooks: their internal
   sheet names could not be read, so those layouts scan every sheet and find the
   period header row and label column by structure. Narrow `sheet_contains`
   after the first successful run.
3. **Guinea-Bissau's sex sub-rows are lower-confidence than its totals.** The
   Total rows reproduced identically across four independent reads; the
   Homem/Mulher rows did not. Verify them against the PDF on the first run.
4. **Seychelles pins the year folder** (`page_link_contains: ["-2026"]`). Bump
   it each January or replace it with a folder-picking discovery method.
5. **`core/` is untouched.** This package adds no discovery methods; every
   descriptor uses a method `core/run.py` already dispatches. Adding one is
   fine — it is purely additive — but it was not needed, even after the
   expansion to 28 countries.

## 6. How to fix a layout that fails

1. Run the one country: `python -m indicators.unemployment.pipeline <country>`.
2. Read the error. `pdf_key_indicators` fails loudly and specifically: no rows
   matched, an undatable report, a scanned PDF with no text layer, or a partial
   capture printed as `no match for N row spec(s)`.
3. Open the retained source in `source_data/<Country>/` and compare against the
   layout's `CROSS-CHECK` comment. If the numbers are shifted by one column,
   the column order changed; if a row vanished, the label was reworded.
4. Edit `parsers/<country>_unemployment.py`, then re-run `tests/test_offline`
   and the country.

Never loosen a regex to make a failure go away. A parser that matches the wrong
row still produces a CSV, and nothing downstream will ever tell you.

### What the offline suite covers, and two things to know before editing it

Fixtures are **verbatim** from the retained PDFs. Most are excerpts of a few
rows, which is why a run prints `no match for N row spec(s)` for Niger,
Liberia, Botswana and Tunisia: those specs belong to rows the excerpt does not
carry. That output is honest reporting, not rot — the parser is "loud but
non-fatal" about a partial capture on purpose. Where a fixture IS a whole
table (Kenya's Tables 2 and 3, Namibia, Zambia, Rwanda),
`test_no_row_spec_goes_unmatched` asserts there are **zero** misses, which is
what would catch a renamed label or a changed caption.

**KENYA'S TRAP TEST IS REDUNDANT BY DESIGN — do not "fix" it.** Two guards stop
the List of Tables opening a block that outlives its page: the contents pages
are excluded, *and* a caption followed by dot leaders cannot open a block.
Mutation-checking them one at a time shows each removal **surviving**, because
the other still holds. Only removing BOTH reproduces the original corruption,
and then the test fails exactly as it should:

```
KE employed Q4:        got 19398165.0, want 18438164.0   # the labour force
KE employment ratio Q4: got 66.7,      want 63.4         # the participation rate
```

Real values, in range, correctly typed, in the wrong series — the failure mode
no validator can see, and the reason both guards exist.
