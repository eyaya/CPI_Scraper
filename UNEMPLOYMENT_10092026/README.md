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

**26 descriptors, 26 countries, all green on a full run — 10,866 rows.**

| | |
|---|---|
| Quarterly | Botswana, Egypt, Ghana, Kenya, Mauritius, Nigeria, Seychelles, South Africa, Tunisia, Zimbabwe |
| Annual | Rwanda, Tanzania, Zambia |
| Ad hoc / periodic | Benin, Burkina Faso, Cameroon, Eswatini, Ethiopia, Guinea-Bissau, Mali, Morocco, Namibia, Niger, Sierra Leone, Somalia, Uganda |

The deepest series are South Africa (2,618 rows, 74 quarters back to 2008 Q1),
Ghana (6,426 rows) and Mauritius (204 rows over five quarters). Tanzania and
Rwanda publish multi-year trend tables and both years/all seven are captured.

### Blocked — `sources_blocked/`

Kept whole, so restoring one is a file move rather than a rewrite:

| Country | Why | What would unblock it |
|---|---|---|
| **Liberia** | LISGIS's site is now a 9 KB placeholder whose only two links both point at Knoema. A **hosting** failure, not a fetching one — and aggregators are not sources | LISGIS rebuilding a document library |
| **Angola** | INE replaced the IEA bulletin PDF with time-series **workbooks** reachable only by a `POST` to `/Diretorios/Download`; the harness downloads by GET. The route is fully mapped in the descriptor | POST support in `core/fetch`, plus a new layout — the workbooks split on a 13th-vs-19th ICLS methodology break and must not be chained |

### Reachable, layout pending

Mauritania (**quarterly ENTE — still the best unclaimed source**), Malawi,
Côte d'Ivoire, Algeria, Burundi, Madagascar, Guinea, The Gambia, Lesotho,
Equatorial Guinea, Cabo Verde, Senegal, Togo, Comoros, Chad. Each has a proven
route and a located file — see [PENDING.md](PENDING.md), along with the
countries that genuinely publish no LFS.

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
