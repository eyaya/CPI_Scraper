# GDP — Africa GDP Collector

Harvests **Gross Domestic Product** from African National Statistics Offices (NSOs)
into one tidy, long-format dataset, captured **exactly as each NSO publishes it** —
all four SNA approaches (production, expenditure, income, aggregate) and both
frequencies (annual + quarterly), with no estimation, imputation or omission.

**Status:** 38 of 54 countries collected (~199k rows). Every significant African
economy is covered except Angola. See the progress report for the full picture:

- `Africa_GDP_Collector_Progress_Report.docx` — narrative (work done, challenges, outstanding)
- `Africa_GDP_Collector_Progress_Report.xlsx` — 4 sheets (Executive Summary, Country Status, Challenges & Remedies, Outstanding & Next Steps)

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
