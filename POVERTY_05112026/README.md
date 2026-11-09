# Monetary poverty

Item 2 of "Indicators for Scrapping into the Data Commons" (2026-07-31): poverty
headcount, gap and severity against national (and, where the NSO republishes
them, international) lines, from household consumption surveys. Started
2026-11-04. Inequality (Gini, quintile shares) is item 4 and a separate
indicator, even where the same report prints both.

    py -3 -m indicators.poverty.pipeline cote_divoire
    py -3 -W ignore -m indicators.poverty.tests.test_offline
    py -3 -m indicators.poverty.tests.check_registry

## What a row is

One Foster-Greer-Thorbecke measure for one group, one line, one survey:
`headcount` (P0), `gap` (P1), `severity` (P2), plus the contributions and
shares the profiles print beside them (`poor_share`, `gap_contribution`,
`severity_contribution`, `absolute_contribution`, `population_share`) and
`poor_count`. Nothing is recomputed. See `schema.py` for the vocabulary.

**The line is part of the identity.** `line_type` (national / international /
relative), `line_level` (overall / extreme / other) and `line_name` are in the
merge key and in `series_id` (`POV_NAT_P0`, `POV_NAT_EXT_P0`, `POV_INT_<line>_P0`).
`line_value`/`line_unit` hold the line itself where printed.

## Guards

* `validate_poverty` enforces **P0 >= P1 >= P2** for every group and line --
  the commonest silent error in these tables is two FGT columns read in each
  other's place, and all three are plausible percentages. (It cannot catch a
  rate swapped with a share; check those against the printed table.)
* Values printed on 0-1 -- P1/P2, and the headcounts and shares of reports
  that print fractions (EMICoV 2006, ENV 1993-95) -- carry `unit: index`, are
  range-checked against that bound and kept as printed; `value_std` puts them
  on the percent scale.
* **Dating.** A round whose fieldwork spans two calendar years is dated by its
  FIRST year (GLSS 7 2016/17 -> 2016, EICV7 2023/24 -> 2023, IES 2022/23 ->
  2022), whatever year the report uses; `reference_period` keeps the span.
  `row()` re-dates a round passed by its last year, and the validator refuses
  any other dating. (NISR, HCP, Stats SA, ISTEEBU and Guinea's back rounds
  date by the last year; re-dated 2026-11-05.)
* `check_registry` refuses a layout that does not declare its line, survey and
  welfare aggregate, and an international line whose name omits its PPP basis.

## Which estimate is preferred

An original estimate and a later re-estimate of the same round share a
`series_id` (they differ only in `survey`). `is_preferred` marks the one from
the **newest report** -- a report's vintage being the latest round its source
file covers -- so EICV7's re-estimate of 2016/17 (39.8) is preferred over the
EICV5 profile's original (38.2). Both rows stay in the file. A preferred series
can therefore mix methodologies across rounds; `survey` says which.

**Joint and co-authored reports: hosted by the NSO = collected.** A report on
the NSO's own website is collected whoever wrote or co-wrote it (user's rule,
2026-11-05): ZIMSTAT/World Bank Poverty Update 2017-19, NBS Seychelles HBS
profiles, INE São Tomé IOF 2010 (UNDP), Stats SL/World Bank Poverty Profile
2014, SNBS/World Bank district estimates 2025, INSEED Comoros EIM 2004 and
2013/14 (AfDB). The same report fetched only from an aggregator's site is not.

**Text-layer decodes (a character map, never OCR).** Two PDFs store their
text under shifted codes: ZIMSTAT PICES 2011/12 (each Times subset draws code
c-2 at code c, proven by glyph widths) and Stats SA Poverty Trends 2017 (CID
N = character N, proven by all 108 page numbers). Both reproduce values the
agency prints elsewhere in plain text exactly; both were approved by the user.

## Engine (`parsers/poverty_tables.py`)

Adapted from `mpi/parsers/mpi_tables.py` (rows = groups, columns = metrics,
a column may carry its own `period`/`survey`/`locality`). Additions:

* **only text inside the page box is read.** ANStat's 2021 profile carries the
  previous page's content off-page at negative x on every other page; without
  the crop Tableau 3-2's regions interleave with 3-3's.
* `start`/`end` line regexes scope one block of a stacked table ("Sexe du CM",
  "Alphabétisation du CM" ... each with its own Non/Oui/Total).
* `percent_cells`: a cell carrying "%" is split off the number before it, or
  "29 809 425 100,0%" reads as one thousands group (29 809 425 100,0).
* a leading comma is a lost zero (",9%" = 0,9).
* `half: left|right` for genuine two-across pages.

## Coverage (2026-11-05, after the exhaustive back-series pass)

**50 of 54 countries, 51,904 rows, 1980..2025, 82.9% with a series_id;
156 descriptors; median 4.5 survey rounds per country** (Mali 17 annual EMOP
rounds; Morocco, Madagascar, Côte d'Ivoire, Uganda 10 each). Each report is its
own descriptor (`<country>_<round>.yaml`); a round republished or re-estimated
by a later report keeps its own `survey` label, so original and revised
estimates sit side by side.

**Blocked (4, `sources_blocked/`):** Algeria and Libya (NSOs publish spending
by decile, no poverty measure), Lesotho (the full 60,012-URL Wayback listing of
bos.gov.ls holds only an asset-index chapter), Eritrea (no NSO site).
Unblocked in the exhaustive pass: Egypt (CAPMAS SDG report + Egypt in
Figures), Ethiopia (NPC/MoFED, the official compiler), Mozambique (MPD/MEF
national assessments), South Africa (Stats SA 03-10-06, Wayback copy),
Eswatini (SHIES profile, Wayback), Seychelles (NBS HBS profiles).

**Single-round countries and why:** Angola (IBEP 2008/09 captures all 404),
CAR (ECASEB 2008 not archived), Congo (ECOM 2011 not found), Comoros (2013/14
decomposition authored by AfDB; EIM 2004 printed as fractions), Djibouti (EDAM
1996/2002/2012 not found), Equatorial Guinea (EEH 2006 not found), Somalia
(earlier rounds World Bank only), Sudan (NHBPS 2014/15 charts only).

**Biggest remaining blind spot: headcounts printed on a 0-1 scale** are
refused by the schema (only P1/P2 may carry `unit: index`). That alone skips
Benin EMICoV 2006, CIV ENV 1993-95, Ghana's 2005 poverty map, Ethiopia
1995/96 regions and 2010/11 cuts, Somalia districts, Comoros 2004.

**Line IDs.** `NAT` / `NAT_EXT` for national overall / extreme; `NAT_FOOD` for
food poverty (food consumption below the food line) however worded;
international lines as `INT_<amount>_PPP<base>` (`INT_1_90_PPP2011` for both
Botswana's "US$1.90 a day" and Togo's "US$1,9 par jour"). EHCVM 2018/19 is
dated 2018 everywhere (Guinea's report says "2019").

**Known gaps worth a later engine change:** a per-table `decimal`
(São Tomé mixes conventions), reading space-grouped counts from word positions
as an engine option (Senegal and Guinea do it in their own modules; Congo
2.2.4 is skipped for lack of it), contributions printed as 0-1 fractions
(São Tomé, skipped), and topics for individuals' marital status / occupation /
branch and the head's status in employment / branch.

Countries whose retained labour/unemployment reports carry poverty tables were
the first tranche (Senegal, Guinea, Chad, Congo, DR Congo, Madagascar, São
Tomé). Everything else needs a new publication: the poverty profiles of the
GLSS / EICV / UNHS / NLSS / KIHBS / IHS / LCMS family.
