# Public Debt — Africa Stats Collector

Harvests **public debt statistics** — debt stocks, the external/domestic split,
creditor and holder breakdowns, and debt-to-GDP as published — into one tidy,
long-format dataset, **exactly as each official national source publishes it**.

## Who counts as a source (decided 2026-10-08)

This is the one indicator where the statistics office is usually *not* the
official compiler. Public-debt statistics are compiled and published by the
**Ministry of Finance / Debt Management Office (DMO)** or the **central bank**.
Those official national compilers are accepted; a statistics office that
publishes debt (Ghana's StatsBank) is accepted too.

**Aggregators are not sources**: no IMF (WEO, Article IV, DSA), World Bank (IDS,
QPSD), AfDB, OECD, Jubilee, TradingEconomics, CEIC, Knoema. A regional central
bank (BCEAO, BEAC) counts only where it republishes the member state's own
national figures, credited and unchanged.

## Two columns that make a debt figure interpretable

* **`publisher`** — the institution whose document the figure came from. It is
  the descriptor's `agency`, stamped on every row by `pipeline._validate`.
* **`coverage`** — the debt perimeter *as the source states it*: central
  government only, central government plus guarantees, the whole public sector
  including state enterprises, general government. Two countries' totals are
  comparable only when their coverage matches. It is required on every
  descriptor (`tests/check_registry.py`); a parser whose source publishes
  several perimeters sets it per row. Never harmonised. Where the source does
  not state it, say so ("perimeter not stated by <publisher>").

## Schema

`schema.py`. `measure` is `stock` (in the currency and scale published),
`share_of_gdp` (as published — never computed from a stock and a GDP figure) or
`share` (a component as a percent of total debt, as published). `frequency` is
monthly / quarterly / annual with periods `YYYY-MM` / `YYYY-Qn` / `YYYY`, and
the validator refuses a period that does not match its frequency.

## Outputs accumulate

Merge-on-write, keyed on coverage · component · period · frequency · measure ·
unit · series_code. Monthly and quarterly debt bulletins usually show a rolling
window, so a parser reads the current issue and history accumulates. Where a
publisher revises a figure, the newest issue wins.

## Standardised columns (added 2026-10-15)

Ten columns are appended after the published ones (`standardise.py`, same contract
as GDP: derived only from published columns, recomputed on every write, backfilled
with `py -3 -m tools.standardise public_debt`, blank when not certain):
`category_code` (TOTAL, EXT, DOM, *_NET, MULTILATERAL, BILATERAL, BILAT_PARIS,
BILAT_NONPARIS, COMMERCIAL, TBILLS, BONDS, LOANS_DOM/_EXT, ARREARS[_EXT/_DOM],
GUARANTEED[_EXT/_DOM]), `category_std`, `coverage_code` (CG, BCG, GG, PS, PPG, GUAR,
SOE, LG, EBU, PC, CG_SG — from `coverage`, or from the component when it names its own
perimeter), `currency`/`unit_multiplier`/`unit_std` (ISO 4217; CFA zone from iso3;
"N$" = NAD), `value_std`, `edition`, `series_id` (`DEBT_<code>_<coverage|UNSTATED>_<measure>_<LCU|USD|SDR>_<freq>`),
`is_preferred` (one per country/series_id/currency/period, newest edition).

Components are read as paths ("Dette extérieure: Dette bilatérale"); a concept counts
only under container or broader-concept parents, so named creditors, holders,
maturities, currencies and "dont/hors/excluding" variants stay blank (36.5% of rows
coded; TOTAL for 33 countries, EXT 39, DOM 41). Three published conventions handled:
"Stock" includes arrears where the same office also prints "Encours" (Chad, CAR) →
not coded; GSS Ghana's "Commercial" excludes Eurobonds → not coded; two labels with the
same code but different values in one table → neither coded.

Verified within each source table (`tests/test_standardise.py`): EXT + DOM = TOTAL in
29 of 30 countries (Rwanda's PPG total also adds SOE loans, as published); MULTILATERAL
+ BILATERAL + COMMERCIAL = EXT in all 6 countries that print all four; EXT + DOM shares
sum to 99-100.

## Rules (as for every indicator)

* As published: no rescaling, no currency conversion, no computed ratios, no
  filling gaps. Units as printed ("USD million", "FCFA milliards", "KSh million").
* Every published period, not just the latest.
* A published inconsistency (components that do not sum to the total, two
  tables disagreeing) is kept and pinned, never smoothed.
* The raw document is retained in `source_data/` for audit.

## Run

```bash
python -m indicators.public_debt.pipeline <country>
python -m indicators.public_debt.tests.check_registry
```
