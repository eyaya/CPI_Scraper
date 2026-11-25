# Merchandise trade

Roadmap item 7: monthly exports, imports and the trade balance, by commodity and
by partner, from each country's national statistics office or official compiler.

    python -m indicators.trade.pipeline ghana
    python -m indicators.trade.pipeline --all
    py -3 -W ignore -m indicators.trade.tests.test_offline

## What a row is

One published figure. It is a flow for one commodity grouping and one partner,
in one currency or weight unit, for one month, quarter or year. The columns are
in `schema.py`. Nothing is summed, converted, deflated or derived:
- no balance is worked out from exports and imports;
- no dollar figure is worked out from a local-currency one;
- `value` stays exactly as printed, and `unit_multiplier` records the scale the
  table states ("millions of FCFA" is 1e6).

The flows are `export`, `domestic_export`, `re_export`, `import`, `total` and
`balance`. The balance is signed: a printed deficit is stored as a negative.

## Two cuts, not the matrix

The roadmap asks for flows "by partner and commodity". NSOs publish two cuts:
- commodity tables, covering all partners;
- partner tables, covering all products.

GSS StatsBank alone offers the full matrix (232 partners × 97 chapters × months).
The collection takes the two cuts plus the totals. A matrix cell is kept only
when it is the NSO's own table.

## Commodities and partners

- **Commodities.** Each stays in the NSO's own grouping, named by
  `commodity_classification`:
  - `hs2`, `hs4`, `hs6`;
  - `sitc1`, `sitc2`, `sitc3`;
  - `bec`;
  - `national`, the NSO's own product list ("Gold", "Cocoa beans and products").
  
  We collect no finer than HS2 or SITC2 when that level exists.
- **Partners.**
  - "All partners" has partner_type `world`.
  - A country has type `country`.
  - A bloc, region, "Others" or "Unknown" has type `group`.

## Guards (schema.validate_trade)

- **Flow identities.** Where one parse publishes all the flows of an identity
  for the same cell, they must agree within rounding:
  - balance = exports − imports;
  - total = exports + imports;
  - exports = domestic exports + re-exports.
  
  The check fails when more than a quarter of 6 or more cells disagree. This
  catches a misread column, a month-shifted row, or a balance printed without
  its sign. Exports FOB against imports CIF is the normal balance, so the price
  basis is not matched.
- **One observation per key** (`schema.KEY`; the multiplier is not part of it).
  A figure printed in millions in one table and in billions in another is one
  observation and is deduplicated. Two different figures for one key are a
  misread, and validation fails.
- The world total must be spelled "All products" / "All partners", with no
  classification. Only the balance may be negative.

## Standardised columns (standardise.py)

- **commodity_code**:
  - `_T` for all products;
  - `HS2_27`, `HS4_2709`, `HS6_270900`;
  - `SITC1_3`, `SITC2_33`.
  
  BEC and national lists stay blank, because their groupings differ by country.
- **partner_code**: `_W` for the world. A country gets its ISO alpha-3 code from
  `partners.csv`, which lists the NSOs' own spellings. A group gets none.
- **currency**, **unit_std**, and **value_std** = value × multiplier (tonnes are
  converted to kg). `value_std` is the only column that converts a scale.
- **series_id**: `TRADE_<flow>_<commodity>_<partner>_<unit>[_FOB|_CIF][_CONST][_GEN|_SPE]_<M|Q|A>`,
  for example `TRADE_EXPORT_HS2_18_FRA_XOF_FOB_M`. It is blank when the
  commodity or partner has no code.
- **series_name**: built from the codes, never the printed labels, so one ID
  has one name across countries. It uses the English HS chapter or SITC
  section/division title (`commodity_names.csv`; HS headings and SITC groups by
  code only) and the partner's English name (first spelling in `partners.csv`).
- **is_preferred**: the newest source wins, meaning the file whose latest period
  is latest. A revised figure in a newer bulletin therefore replaces the
  provisional one.

## Sources

- **Ghana:** GSS StatsBank (PxWeb), from 2021-01. It covers HS chapters and
  GSS's 11 product groups, and partner countries one year per query, because
  the API refuses the five-year partner query with a 403. Values come in
  nominal cedis, real cedis, US dollars and net weight. The parts sum exactly to
  the published totals in all 2,400 cells. Add one partner table each new year.
- **Other countries:** see `sources/*.yaml`. Countries with no published trade
  statistics, or none reachable, are recorded in `sources_blocked/`.
- **Policy:**
  - Sources are the NSO's own domain, or a Wayback `id_` copy of the NSO's file.
  - An official compiler counts where it, not the NSO, compiles the country's
    trade statistics, such as SARS in South Africa or the Office des Changes in
    Morocco.
  - No aggregators: IMF DOTS/IFS, UN Comtrade, WITS, ITC TradeMap and the like.
  - No OCR.

## Coverage (2026-11-19)

46 of 54 countries, 1.28 million rows. The headline (all products, all
partners) starts by 2000 for 10 countries, by 2010 for 18, by 2015 for 29 and by
2020 for 39. 37 countries reach 2025 or later, and 24 have a monthly headline.

2026-11-19: Sudan added (Central Bank of Sudan Foreign Trade Statistical
Digest, monthly 2003-01..2026-06, annual 2000-2025, by commodity and partner);
Côte d'Ivoire extended to 2011-01..2018-06 (2012/2015/2017/2018 files recovered
from Wayback).

Not collected (`sources_blocked/`): Comoros (no trade publication), DR Congo
and Equatorial Guinea (Cloudflare), Eritrea (no NSO site), Eswatini, Ethiopia
and São Tomé and Príncipe (trade files not posted or host unreachable), and
Uganda (the certificate chain does not verify).

Known limits:
- South Africa's releases before October 2013 exclude Botswana, Lesotho,
  Namibia and Eswatini, so they are not collected until the schema has a
  coverage field.
- Burundi's HS chapters come from the 2026-Q2 bulletin's back series. Labels
  fused across two chapters (673 rows), and 14 cells two pages print
  differently, are dropped, as are 49 partner lines split mid-name.
- South Sudan publishes tariff-line records only: no headline, and no series IDs.
