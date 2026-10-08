# GDP — Africa GDP Collector

Harvests **Gross Domestic Product** from African National Statistics Offices (NSOs)
into one tidy, long-format dataset, captured **exactly as each NSO publishes it** —
all four SNA approaches (production, expenditure, income, aggregate) and both
frequencies (annual + quarterly), with no estimation, imputation or omission.

**Status:** 53 of 54 countries collected (266k rows). Benin (Wayback copies of
INSAE's own workbooks) completed 2026-10-06 once the Wayback Machine's rate
limit lifted. Eritrea is in `sources_blocked/`: its government hosts resolve
but time out, and no archived capture holds any statistics. The progress report (last produced by hand) predates this round:

- `Africa_GDP_Collector_Progress_Report.docx` — narrative (work done, challenges, outstanding)
- `Africa_GDP_Collector_Progress_Report.xlsx` — 4 sheets (Executive Summary, Country Status, Challenges & Remedies, Outstanding & Next Steps)

## The 2026-10-01 round: 39 → 52 (+ Benin pending)

| Country | Source | Rows | Coverage |
|---|---|---|---|
| Angola | INE quarterly + annual workbooks (POSTed; annual via `extra_groups`) | 17,877 | 2002-2026Q2, production + expenditure + income |
| Eswatini | CSO QGDP tables + 2023 rebased report (Wayback; gov.sz unreachable) | 10,989 | 2013-2025Q4 |
| Cabo Verde | INE quarterly national accounts workbook | 9,999 | 2007-2026Q2, production + expenditure |
| Zambia | ZamStats QGDP + annual workbooks | 5,844 | 2010-2026Q2, all three approaches annually |
| Equatorial Guinea | INEGE quarterly accounts + Anuario 2026/2023 | 2,728 | 2018-2026Q2 |
| Guinea-Bissau | INE Síntese das Contas Nacionais 2020 | 2,416 | 2010-2020 |
| Djibouti | INSTAD Annuaire ch. 7.2 (2025 + 2024 editions) | 891 | 2014-2024 |
| Congo | INS quarterly national accounts note | 840 | 2024Q2-2025Q4 |
| South Sudan | NBS GDP 2021 release | 652 | 2008-2021, expenditure |
| Gabon | DGS Annuaire 2004-2008 (Wayback of stat-gabon.org) | 292 | 2004-2008 |
| Sudan | CBOS Annual Report 2018 reprinting CBS tables | 215 | 2014-2018 |
| Central African Republic | ICASEES Comptes nationaux 2019-2021 (posted 2026) | 128 | 2019-2021 |
| Mozambique | INE Anuário Estatístico 2025 ch. 5 | 115 | 2021-2025, expenditure |
| Benin | INSAE annual + quarterly series (Wayback) | 2,226 | 1999-2021 |

Deepened: Algeria 40 → 2,091 rows (ONS Rétrospective, 1963-2024, all four
approaches, the national and SNA GDP concepts kept apart), Tunisia 42 → 2,641
(INS's own accounts, quarterly, base 2015), Morocco 192 → 498 (HCP quarterly
notes, levels by sector).

THREE CORPUS-WIDE CHANGES, each worth knowing before editing:

* **GDP NOW MERGES ON WRITE.** INS Tunisie (8 quarters / 6 years) and HCP's
  quarterly notes publish rolling windows, so overwriting threw away every
  period that scrolled off. The key is the row's full identity (approach,
  category, category_group, series_code, geography, period, frequency,
  price_basis, seasonal_adjustment, measure, unit, base_period), checked
  unique in every output before enabling; `test_gdp_merge_keys_are_unique`
  replaces the old "overwrites rather than merges" pin. CONSEQUENCE: when a
  parser changes a row's identity (a relabel), regenerate that output from
  scratch, or the old rows survive beside the new.
* **MAURITIUS'S "DEFLATORS" WERE PERCENT CHANGES** -- 3,480 rows filed as a
  2018=100 index since the source was added. The values run negative, and for
  GDP each equals exactly the y/y change implied by the workbook's own levels
  (2018: published 1.7, implied change 1.7, implied index 100.0). Now
  `growth_yoy`, price basis `not_applicable`, category_group naming them.
  Tunisia's "Evolution des prix" is the same and is filed the same way.
  `deflator` means an index level, unit `index`, base in `base_period`.
* **DRIFT CAUGHT:** Statistics Mauritius began posting an ADVANCE-estimates
  workbook beside the full QNA; it matched `hs_qna` and was newer.
  `latest_datestamp_file` now takes `link_excludes`.

## Lesotho (added 2026-09-27)

Earlier sessions recorded Lesotho as having **no GDP file**, and they were
wrong. bos.gov.ls lists its publications in a JavaScript array inside
`publications.htm`, so a crawler sees no link. `regex_on_page` reads the array
directly and takes the newest "QGDP Publication Tables" ZIP. The workbook gives
production-approach levels at current and constant 2012 prices, real y/y growth,
SA q/q GDP growth and current-price shares, from 2007. Each growth column's
meaning was verified against the level sheets rather than read off the sheet
name. The "Contributions" sheet turned out to hold shares, not contributions.
One published inconsistency is handled explicitly. The 2025 annual row pairs a
current-vintage GDP with an older vintage of its components, so it doesn't add
up and its growth rates contradict the quarters (manufacturing 2.2% vs 9.1%).
The parser keeps 2025 annual GDP, drops the stale components, and raises once
BOS aligns the row. The expenditure approach (annual, 2014-2023) comes from
the Annual National Accounts 2023 PDF, checked each year against its own
identities. The catalogue's 2024 edition is a dead link. See
`parsers/lesotho_bos_gdp.py`.

## Layout

```
indicators/gdp/
├── pipeline.py          # entry point: wires the GDP CONFIG into the shared core
├── schema.py            # GDP_COLUMNS (20-col long format) + validate_gdp()
├── sources/             # one <country>.yaml descriptor per country
├── parsers/             # one parser per country (registered in parsers/__init__.py)
├── source_data/         # retained raw published files (audit trail)
├── out/                 # tidy <country>_gdp.csv outputs
└── Africa_GDP_Collector_Progress_Report.{docx,xlsx}
```

## Run

```bash
# online (discover → download → parse → validate → write)
python -m indicators.gdp.pipeline <country>
python -m indicators.gdp.pipeline --all

# offline (parse an already-downloaded file with the same extraction path)
python scrape_local.py --indicator gdp <country> <path-to-file>
python scrape_local.py --indicator gdp --dir <folder>
```

## Schema (tidy long format)

Keyed by **approach · category · series_code · geography · period · frequency ·
price_basis · seasonal_adjustment · measure**, plus identity/provenance columns.

- **approach** — `production | expenditure | income | aggregate`
- **period** — `YYYY` (annual) or `YYYY-Qn` (quarterly)
- **price_basis** — `current | constant | not_applicable`
- **measure** — `level | growth_yoy | growth_qoq | deflator | per_capita | share | contribution`
- **value / unit / base_period** — the number, its unit, and the constant-price base

One shape holds a quarterly constant-price value-added figure, an annual expenditure
share and a per-capita level side by side, so all 38 countries concatenate into one file.

## Tests

```bash
PYTHONUTF8=1 py -W ignore -m indicators.gdp.tests.check_registry   # descriptors resolve
PYTHONUTF8=1 py -W ignore -m indicators.gdp.tests.test_offline     # validator + corpus + replay
```

GDP has **38 bespoke parsers and no shared engine**, and — unlike CPI — no
shared vocabulary module either. What it does have is a rich schema whose four
vocabularies are deliberately **orthogonal**, so that a constant-price growth
rate is unambiguous. That orthogonality is what the suite pins:

| | |
|---|---|
| `schema.validate_gdp` | the four vocabularies, `YYYY`/`YYYY-Qn` periods, and both magnitude bounds |
| **cross-field rules** | `growth_*` ⇒ percent; `deflator` ⇒ index on no price basis; `contribution` ⇒ percentage points; `share` ⇒ percent; **`frequency` and period form must agree** |
| **all 38 outputs at once** | vocabulary membership, period form, an `aggregate` series per country |
| CBE Egypt | one replay of the fiscal→calendar quarter mapping |

**Both magnitude bounds are loose on purpose.** The level ceiling must clear
currencies reported *unscaled* (Nigeria ≈ 2e14 NGN) and the growth bound must
clear a sector growing off a near-zero base (Ghana oil in 2011 ≈ +7000% YoY).
Tightening either to a "tidy" value rejects real published figures — the suite
fails if you do, which is the intended behaviour.

**The trap the Egypt replay exists for:** Egypt's fiscal year runs July–June,
so FY Q3 is January–March of the *next* calendar year. An off-by-one produces
periods that are perfectly well-formed and a full year wrong. Mutating the
mapping turns the test red with
`EG periods: got ['2022-Q1'…], want ['2022-Q3'…]`.

**Mutation-checked, 9/9.** Shifting the fiscal quarters, reading the
Public column instead of Total, dropping the `aggregate` reclassification,
swapping the EGP million/billion units between workbooks, disabling either
validator check, tightening either bound, or dating a quarterly row annually in
a real output each turns the suite red on the assertion written for it.

> **Note — GDP overwrites, it does not merge.** Unlike `cpi` and `labour`, the
> pipeline sets no `merge_keys`, so each run replaces its output. That is
> defensible (most GDP sources republish the whole series, and revisions should
> propagate) but it is the same configuration that cost the CPI collector 258
> Kenyan periods before merge-on-write. `test_gdp_overwrites_rather_than_merges`
> pins the current behaviour; if that changes, replace it with a merge-key
> uniqueness check of the kind `cpi` carries.

## Principles

- **As reported** — ugly-but-real values kept; ambiguous figures left out, never guessed.
- **No aggregators** — IMF, World Bank, Knoema/opendataforafrica re-estimate national
  accounts and are excluded as sources.
- **Central bank only as a documented fallback** — where the NSO does not compile GDP
  or its site is unreachable (DR Congo/BCC, Libya/CBL, Egypt/CBE, Ethiopia/NBE).
- **Auditable** — the raw source file is retained under `source_data/` for every country.

## Adding a country

1. Drop a `sources/<country>.yaml` descriptor (source URL, parser name, identity cols).
2. Add `parsers/<country>_gdp.py` and register it in `parsers/__init__.py`.
3. Run `python -m indicators.gdp.pipeline <country>` and check `out/<country>_gdp.csv`.

The shared discovery/download/validation/output harness lives in `core/`; this folder
only holds what is GDP-specific.
