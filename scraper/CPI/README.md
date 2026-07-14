# africa-stats-collector

Collect indicators published by African National Statistics Offices (NSOs) into
one **tidy, structured** data file per country/indicator — starting with **CPI
(inflation)**, one country at a time.

For each country we pick the **most robust source available**, in this order:

1. **Tier 1** — official API / SDMX endpoint
2. **Tier 2** — structured file download (CSV / Excel)
3. **Tier 3** — PDF / DOC scrape + table extraction

Only fall to a lower tier when the higher one doesn't exist. Each country is a
small, self-contained unit: a **descriptor** (`sources/<country>.yaml`) + a
**parser** (`collector/parsers/<agency>.py`). The shared pipeline handles the
rest, and one country breaking never stops the others.

## Layout

```
sources/          one YAML descriptor per country/indicator
collector/
  run.py          orchestrator: discover -> download -> extract -> parse
                  -> normalise -> validate -> write CSV (API sources skip
                  discover/download and fetch data directly)
  discover.py     resolve the current file URL (page_scrape | probe_monthly |
                  latest_dated | latest_dated_pdf | catalog_latest)
  fetch.py        download + unzip helpers
  pxweb.py        Tier-1 PxWeb JSON API client (e.g. Ghana StatsBank)
  parsers/        one parse() per source layout, registered in __init__.py
  schema.py       canonical tidy columns + validation (fail loud on garbage)
  coicop.py       COICOP 2018 division reference
source_data/      RETAINED raw NSO files as published (PDF/Excel/Word/zip),
                  one folder per country — a first-class deliverable
out/              tidy CSV output, one per country/indicator
```

Every run keeps **two** things per country: the original published source
document(s) under `source_data/<Country>/`, and the structured tidy CSV under
`out/`. The raw files are retained for auditability and so downstream users can
trace any value back to the primary NSO document.

## Run

```bash
pip install -r requirements.txt
python -m collector.run south_africa    # one country
python -m collector.run --all           # every descriptor
```

Output columns (tidy long format):

```
country, iso3, indicator, coicop_code, coicop_label, geography,
period (YYYY-MM), measure, value, unit, base_period, frequency,
source_type, source_url, source_file, extracted_at
```

`measure` records what `value` is, because NSOs publish different things:
`index` (a level, e.g. Stats SA / Nigeria) or `inflation_yoy` / `inflation_mom`
(% changes — all many PDF-only NSOs like Kenya publish by division).

## Countries

| Country | Tier | Source | Status |
|---------|------|--------|--------|
| South Africa (Stats SA, P0141) | 2 (Excel) | CPI (COICOP) index time series, Jan 2008– | ✅ done — index |
| Nigeria (NBS, catalog 154) | 2 (Excel in monthly zip) | CPI index 'Table2', national, Jan 2023– (2024 rebase) | ✅ done — index |
| Kenya (KNBS) | 3 (PDF) | Monthly press release Table 1 — inflation % by division | ✅ done — rates |
| Rwanda (NISR) | 3 (PDF) | 'Annex 3: All Rwanda' index by division (base Feb 2014) | ✅ done — index |
| Ghana (GSS StatsBank) | 1 (API) | PxWeb cpi.px — index + YoY + MoM, COICOP-2018, 1998– | ✅ done — index+rates |
| Egypt (CAPMAS) | 2 (Excel via site API) | Monthly CPI bulletin 'Table 1' — index+MoM+YoY by division for Urban/Rural/Total (base 2018/19). CBE note = Tier-3 fallback (urban+core) | ✅ done — index+rates |
| Uganda (UBOS) | 2 (Excel) | 'Division' sheet — index+YoY+MoM wide series (Jul 2017–, base 2016/17) by COICOP-2018 division (national) + 10 urban centres | ✅ done — index+rates |
| Morocco (HCP) | 2 (Excel / Google Sheets) | IPC index wide series (2017–, base 2017) by COICOP-1999 division + general; general in a 2nd sheet via extra_urls | ✅ done — index |
| Senegal (ANSD) | 2 (Excel) | IHPC (WAEMU) — index wide series (1998–, base 2023) by COICOP-2018 division + Global (All items) | ✅ done — index |
| Benin (INStaD) | 2 (Excel) | IHPC (WAEMU) connected series (1998–2024, base 2023); shares the `waemu_ihpc` parser with Senegal | ✅ done — index |
| Togo (INSEED) | 3 (PDF) | IHPC (WAEMU) monthly note — index+MoM+YoY by COICOP-2018 division + Global (base 2023) | ✅ done — index+rates |
| Burkina Faso (INSD) | 2 (Excel .xlsx/.xls) | IHPC (WAEMU) note 'Tableau 1' — index+MoM+YoY by COICOP-2018 division + Global (base 2023) | ✅ done — index+rates |
| Namibia (NSA) | 2 (Excel) | CPI Excel Tables 'Tab 2/3/4' — index+MoM+YoY wide series (2002–, base Dec 2012) by COICOP-1999 division | ✅ done — index+rates |
| Mali (INSTAT) | 3 (PDF) | IHPC (WAEMU) monthly note — index by COICOP-2018 division + INDICE NATIONAL (base 2023) | ✅ done — index |
| Niger (INS) | 3 (PDF) | IHPC (WAEMU) monthly note — index+MoM+YoY by COICOP-2018 division + Indice global (base 2023) | ✅ done — index+rates |
| Mauritius (Statistics Mauritius) | 3 (PDF) | Monthly CPI note 'Division' table — index (2 months) by COICOP-2018 division + All Divisions (base 2023) | ✅ done — index |
| Zambia (ZamStats) | 3 (PDF) | 'The Monthly' bulletin 'Table 1.2' — index wide series (2022–) by COICOP-1999 division + All items | ✅ done — index |
| Tanzania (NBS) | 3 (PDF) | NCPI release 'Main Groups' — index (3 months) by COICOP-2018 division + All items (base 2020) | ✅ done — index |
| Botswana (Statistics Botswana) | 3 (PDF) | CPI report 'Table 3' — index (5 months) by COICOP-1999 group + All items (base Dec 2018) | ✅ done — index |
| Tunisia (INS) | 2 (HTML) | IPC HTML table — index by COICOP-1999 group + Ensemble, rolling recent months (base 2015) | ✅ done — index |
| Cameroon (INS) | 3 (PDF) | CEMAC IHPC note 'Tableau 2' — index+MoM+YoY by COICOP function + INDICE GENERAL (base 2022); positional extraction | ✅ done — index+rates |
| Algeria (ONS) | 3 (PDF) | IPC note — index+MoM+YoY by **native 8-group** nomenclature + Ensemble (base 2001); NOT COICOP, captured as reported | ✅ done — index+rates |
| Sierra Leone (Stats SL) | 3 (PDF) | 'Table 1' CPI press release — index+MoM+YoY by COICOP-1999 division + All items (base Dec 2021) | ✅ done — index+rates |
| Lesotho (BOS) | 3 (PDF) | 'Table 1' monthly CPI report — index+MoM+YoY by COICOP-1999 division + Overall CPI (base Average 2022) | ✅ done — index+rates |
| Guinea (INS) | 3 (PDF) | INHPC note 'Tableau 2' — index+MoM+YoY by COICOP-1999 function + INDICE GLOBAL (UEMOA method, base 2019) | ✅ done — index+rates |
| Madagascar (INSTAT) | 2 (Excel behind SPA) | NIPC 'IPC' sheet — index wide series (2016–, base 2016) by COICOP-1999 FONCTION + Ensemble; two-hop discovery through the monthly NIPC page | ✅ done — index |
| Seychelles (NBS) | 2 (Excel) | 'CPI_Series' time series — index wide series (2007–, base 2014) by COICOP-1999 division + All items | ✅ done — index |
| Malawi (NSO) | 2 (Excel via CMS API) | 'Stats Flash' — index by COICOP-1999 division + All items (base Dec 2021), National/Urban/Rural + all-items MoM; discovered via the Nuxt SPA's headless CMS API | ✅ done — index+rates |
| Congo (INS) | 3 (PDF) | CEMAC INHPC bulletin 'Tableau 1.1' — index+MoM+YoY by COICOP-1999 function + INDICE GLOBAL (base 2018); discovered via the WordPress Download-Monitor wpdmdl link | ✅ done — index+rates |
| Central African Republic (ICASEES) | 3 (PDF) | CEMAC IHPC bulletin — index+MoM+YoY by COICOP-1999 function + INDICE NATIONAL (base 2019); discovered via the Joomla Edocman /download route | ✅ done — index+rates |
| Angola (INE) | 2 (Excel behind SPA) | Time-series DB — national all-items YoY inflation series (2015–); .xlsx path regexed from inline JS. No COICOP breakdown in this DB | ✅ done — rate (all-items YoY) |
| Zimbabwe (ZimStat) | 2 (Excel via WP API) | Weighted (blended) CPI 'CPI 2' sheet — index wide series (2024-04–, base Apr 2024) by COICOP-1999 division + All Items; newest workbook found via the WordPress REST API | ✅ done — index |
| Liberia (LISGIS) | 3 (PDF) | Monthly CPI Newsletter 'Table 1' — national all-items index+MoM+YoY 13-month series (base Dec 2005). By-division figures are chart-only | ✅ done — index+rates (all-items) |
| Mauritania (ANSADE) | 3 (PDF) | Monthly INPC note 'Tableau 2' — index+MoM+YoY by COICOP-1999 function + Indice général; note PDF found via the SPA's WordPress media API | ✅ done — index+rates |
| Chad (INSEED) | 3 (PDF) | CEMAC INHPC bulletin 'Tableau 2' — index+MoM+YoY by COICOP-1999 function (Roman I–XII) + INDICE GLOBAL (base 2022); found via the SPA's Node /api/publications feed | ✅ done — index+rates |
| Côte d'Ivoire (ANStat) | 3 (PDF) | UEMOA IHPC bulletin — index+MoM+YoY by **COICOP-2018** division (01–13) + INDICE GLOBAL (base 2023); PDF resolved from the SPA search API via the thumbnail id | ✅ done — index+rates |
| DR Congo (BCC) | 2 (Excel) | ⚠️ PARTIAL — national all-items **annual** index (base 2012) + YoY, 1992–2020 (INS-RDC WAF-blocked; BCC fallback) | ⚠️ partial — annual all-items |
| Ethiopia (ESS) | 3 (PDF) | ⚠️ PARTIAL — national all-items (General) YoY+MoM 13-month series; EFY dates mapped to Gregorian. Divisions are chart-only | ⚠️ partial — all-items rates |
| Burundi (INSBU) | 3 (PDF) | Monthly IPC 'Tableau 1' — index+MoM+YoY by COICOP-1999 function + Ensemble (base 2016/2017); found via the Laravel /api/publications (ISTEEBU→INSBU rebrand) | ✅ done — index+rates |
| Libya (CBL) | 3 (PDF) | Central-bank fallback — CBL republishes the Census & Statistics Dept. CPI: wide monthly index by COICOP-1999 group + Overall (2024–, base 2024) + overall YoY | ✅ done — index+rate |
| Mozambique (BM) | 2 (Excel) | Central-bank fallback — BM republishes INE's CPI 'Quadro 8': wide monthly index (2016–, base 2023) by COICOP-1999 division + Total (INE Liferay is gated) | ✅ done — index |

## Adding a country

1. Investigate the NSO: does it have an API (tier 1), a structured file
   (tier 2), or only PDFs (tier 3)?
2. Write `sources/<country>.yaml` (copy an existing one).
3. Write a `parse(local_path)` in `collector/parsers/`, register it in
   `parsers/__init__.py`. It returns a DataFrame with at least:
   `coicop_code, coicop_label, geography, period, value, unit, base_period,
   frequency`. `run.py` fills in the identity/provenance columns.
4. `python -m collector.run <country>` — validation will flag bad output.
