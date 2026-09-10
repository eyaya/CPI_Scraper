# Population — Africa Stats Collector

Harvests **population** — censuses, intercensal estimates and official projections
— from African National Statistics Offices into one tidy, long-format dataset,
captured **exactly as each NSO publishes it**: the source's own age bands,
geography names and series definitions, with no estimation, imputation or
recomputation.

**Status:** 36 of 54 countries, 126,359 rows. A full `--all` run collects 35 of
the 36. The one that cannot be fetched is host-side, not code:

- **Liberia** — LISGIS is rebuilding its site; its old paths 404 and the
  placeholder links only to an aggregator, which this project excludes.

**Central African Republic is intermittent.** ICASEES serves its population page
as a ~24 KB stub with no tables on some requests and the real ~142 KB page on
others, so this source fails and recovers between runs without anything changing
here. It also needs `html5lib` (lxml rejects the page's markup) — see
requirements.txt. Retry before investigating.

Existing outputs are never lost to a failure: the harness writes only on success.

## Schema

Keyed by **series_type · sex · age_group · geography · period · measure**, plus
identity/provenance columns. `period` is a mid-year `YYYY`. Most rows are head
counts, but the same tables often publish derived demographic measures (sex ratio,
growth rate, density, median age, …) which are captured via `measure` + `unit`
as published, never recomputed. See `schema.py`.

## Outputs accumulate

A run MERGES into `out/<country>_population.csv` rather than replacing it, keyed
on the six columns above. `series_type` is deliberately part of that key: a census
and a projection can cover the same year and geography and must not overwrite each
other, and a new census round accumulates alongside the previous one. See
`core.run._merge_with_existing`.

## Reading NSO PDFs — the recurring traps

Most remaining countries publish population only as a census PDF. Four problems
come up again and again, and the parsers here solve each in a reusable way:

1. **Space thousands separators.** French/Portuguese tables write `63 217`, and a
   percentage may be written without a decimal, so splitting a line on whitespace
   is ambiguous. Rebuild each number from word **x-gaps** (a gap under ~8 pt
   continues one number; 16 pt or more starts a new column) — see
   `instad_djibouti_population.py`, `ansd_senegal_population.py`.
2. **Tables printed two across.** `extract_text()` then returns two tables' rows
   concatenated on one line. Split the page on the word x-midpoint and walk each
   column top-to-bottom — see `nbs_southsudan_population.py`.
3. **Captions that wrap.** `… projections, 2020-` / `2040` will, on the truncated
   line alone, match a bare year and make a year-keyed table look like a
   single-year table. Match the line joined with its successor **first**.
4. **Column order that is not constant.** INStaD Benin lists Total, Masculin,
   Féminin — the total FIRST — while most sources put it last; and INS Cameroun's national table lists
   'Masculin Féminin' and every regional table lists 'Féminin Masculin'. Read each
   table's own header to bind columns to sexes — assuming a fixed order swaps male
   and female for most of the country, and NO total check catches it, because
   male + female = total either way.
5. **Rows split by y-bucket rounding.** Grouping words into rows by rounding the
   y-coordinate into fixed buckets breaks when a label is typeset a couple of
   points off its own numbers: the bucket boundary falls between them for some
   rows and not others. Cluster sequentially by vertical distance instead. This
   silently cost 282 of Cameroon's 390 rows.
6. **A text layer too mangled for `extract_words()`.** A spreadsheet pasted in
   with per-glyph letter spacing (DGS Gabon) breaks age labels apart and fuses
   adjacent columns into nonsense. Work from the raw CHAR stream instead:
   ordering characters by x reconstructs each line exactly, and digits group into
   numbers by x-delta. Where the count columns then sit at no fixed index, locate
   them by the table's own identity rather than by position — see
   `dgs_gabon_population.py`.
7. **Markers that shift columns.** A percentage rounding to zero printed as `(0)`
   or `*` is non-numeric and drops out of the parsed groups, so positional column
   indices move. Validate every row against the table's own identity
   (male + female = total) and treat that identity as the fallback for locating
   the counts.

Always check a parse by **reconciling against the source's own totals**, and by
**counting coverage per geography** — between them those two checks caught a whole
missing projection year, an invented province named "Fe", a dropped oldest age
band, and 282 rows lost to y-bucket rounding. A plausible row count proves
nothing on its own.

## Overlapping geographies — do not blindly sum

Some sources publish a geography AND the units that replaced it. Ethiopia's
projection lists the legacy SNNP Region alongside the four regions carved out of
it, and the successors sum to exactly the legacy row (22,922,998), so adding all
thirteen regions double-counts 22.9 million. Both are kept because both are
published; the descriptor records the overlap. The same caution applies to any
country mid-reorganisation — check a region sum against the published national
total before trusting it.

## Find the site's own navigation before concluding a source is absent

Three countries were on the rejected list below and turned out to be collectable —
because the rejection had tested a guessed URL or a dead host, not the source:

- **Gabon** — checked against `dgstat.ga`, which is dead. The live DGS host is
  `new.instatgabon.org`.
- **Benin** — `instad.bj/statistiques` redirects endlessly, but the
  `/statistiques/statistiques-demographiques` SUB-path serves fine.
- **Mali** — a guessed `/fr/publications/demographie` 404s; the real path,
  linked from the home page, is
  `/fr/publications/recensement-general-de-la-population-et-de-lhabitat-rgph`,
  which lists the entire RGPH-5 report set.

So: read the site's own nav links and match on keywords, rather than guessing
paths. A 404, a 500 or a redirect loop on a path you invented is evidence about
your guess, not about the NSO.

## Sources investigated and rejected

Recorded so they are not re-attempted without new information:

- **São Tomé e Príncipe** — ine.st's demography category lists four files whose
  own preview paths all 404. The links are stale; nothing is fetchable.
- **Burundi** — the INSBU publications API carries only a 1987 DHS and notices
  about the census currently in the field (RPPCUB 2026); no results yet.
- **Mauritania** — the ANSADE socio-demographic yearbook publishes poverty and
  unemployment tables, but no population counts by age, sex or wilaya. NOTE its
  files need `core.fetch.download`; a plain requests GET returns an HTML page.
- **Guinea** — the RGPH-4 preliminary report is a 233 MB PDF yielding ~33 rows of
  *overlapping* analytical bands ("moins de 15 ans", "15-64 ans", …) with no plain
  total row, so a national figure could only be derived. Poor trade; wait for the
  detailed RGPH-4 volumes.
- **Egypt** — the CAPMAS publication API exposes housing and the economic census,
  but no population/demographic publication in the range scanned.
- **Lesotho** — its own `census.htm` carries only policy documents (the Statistics
  Act, the dissemination strategy), no census data.
- **Nigeria, Mozambique** — no population file surfaced on the relevant NSO pages;
  Nigeria's microdata portal also times out.
- **Algeria** — `ons.dz/rgph2020` is linked from the home page but returns HTTP
  500.

## Run

```bash
python -m indicators.population.pipeline <country>
python -m indicators.population.pipeline --all
```
