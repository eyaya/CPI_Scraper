# Producer Price Index (PPI)

Prices received by domestic producers -- the upstream companion to CPI.
`python -m indicators.ppi.pipeline <country>` / `--all`; tests:
`python -m indicators.ppi.tests.test_offline`.

## What a row is

One value for one INDEX, one industry and one period: the index level, a %
change (y/y, m/m, q/q, annual average), or the industry's weight. Emitted as
published -- nothing is rebased, chained or recomputed. See `schema.py`.

* **The index is part of the identity.** `index_name` is the NSO's own title;
  `index_variant` the controlled kind (output, domestic_market, export,
  import, final_goods, intermediate_goods, agriculture, services) -- Stats SA
  publishes several PPIs over the same industry labels.
* **The base is part of the identity** of a level: a rebased series is a new
  series and both are kept (`base_period` is in the merge key).
* Monthly (`YYYY-MM`), quarterly (`YYYY-Qn`) and annual (`YYYY`) series.
* **Merge-on-write**: each bulletin republishes a window of months; the
  back-series accumulates across bulletins.

## Guards

* **Column-swap guard**: where a run carries both the index and its y/y
  change, the change must agree with the index a year apart (loosely, to
  allow rounding); more than a quarter of >= 12 comparisons disagreeing means
  a column was read in the wrong place.
* Units by measure (index -> index; changes -> percent; weights -> percent or
  per mille), period format by frequency, positive index levels.

## Standardised columns (`standardise.py`)

`series_id = PPI_[variant]_<industry>_<measure>_<base>_<freq>`, e.g.
`PPI_T_INDEX_B2015_M`, `PPI_EXP_C_INFLATION_YOY_X_M`. Industry is `_T` for the
index's own total, an ISIC Rev.4 section letter, or a span (`BTE`); NSO
division codes are not mapped (NAEMA / NACE / ISIC Rev.3 divisions differ).
`_T` covers what that NSO's index covers -- `index_name` says which.
Weights in per mille go onto the percent scale in `value_std`.
`is_preferred`: the newest source (latest period its file covers), then the
latest extraction -- the latest bulletin's revision of a month wins.

## Coverage (2026-11-08, after the follow-up pass)

**33 of 54 countries, 409,346 rows, 21 blocked** (`sources_blocked/`, each with the
routes tried). Every period each NSO publishes was sought, every base kept.

Deepest: South Africa (monthly 1970-2026, five bases, Wayback copies of Stats
SA's own P0142.1 files -- statssa.gov.za now serves a bot challenge), Mauritius
(PPI-M and PPI-A from 1993, six bases), Egypt (2006-2026), Ghana (2006-2026),
Morocco (2007-2026, three nomenclatures/bases), Senegal (2009-2026, two
bases), Algeria (quarterly 2002-2025, public and private sectors), Rwanda
(2010-2026), Gambia (2010-2025), Kenya (2011-2026), Tanzania (2013-2026).

**Blocked -- the NSO publishes no producer price index:** Lesotho, Eswatini,
Zambia, Gabon, São Tomé, Cabo Verde, Guinea-Bissau, Mozambique, Madagascar,
Comoros, Somalia (PPI in preparation), South Sudan, Niger, Libya, Mauritania,
Eritrea (no NSO site). **Blocked -- host unreachable and no archived PPI:**
Nigeria, DR Congo, Equatorial Guinea, Ethiopia, Sudan.

**Series IDs.** 8.6% of rows carry one: totals and ISIC sections are coded,
divisions, groups and products deliberately are not (division codes differ
between NAEMA, NACE and ISIC Rev.3/Rev.4). 29 of 33 countries have a coded
headline (`_T`); Botswana, Liberia, Namibia and Morocco publish section-level
indices only.

**Conventions set in this pass.** A % change carries the base of the index it
is computed from (`base_period`), so two editions' changes for one month stay
two series. `currency_basis` separates ZimStat's USD / ZWG / weighted
versions; `ownership` ONS Algeria's public / private indices. A file printing
two different values for one ID and month gets no ID there (Uganda 2024-12).
Revisions: the newest bulletin's value is the one kept (merge-on-write, run
oldest first) and the one preferred.

**Follow-up pass (2026-11-08).** Collected what the first pass had to drop:
Stats SA's pre-2012 headline "Commodities for South African consumption"
(`domestic_consumption`, 1970-2007, 27,945 rows), weights printed per ten /
hundred thousand (Gambia 2009 base, Congo, CAR, Mali), ANSD's "variation des
cumuls" (`inflation_ytd_avg`, tested on its own index). Côte d'Ivoire's same
column is NOT collected: its notes lack the January months that would prove
which change it is. Tanzania's 2025 releases print no ISIC codes; each such
label takes the one code NBS prints for it in every other release ("Utility"
stays blank: printed "D" once, "35&36" elsewhere, and coded nowhere).

**Replay (2026-11-08):** every one of the 194 descriptors re-parsed from its
retained files, one process each; every out row is reproduced with the same
value by the descriptor whose file it names (409,346 of 409,346).
