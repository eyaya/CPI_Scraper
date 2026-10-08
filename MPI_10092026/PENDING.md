# MPI — what is not in `sources/`, and why

> **Re-probed 2026-10-07.** Resolved and now in `sources/`: **Ghana report**
> (GLSS7 edition — Wayback `id_` capture of GSS's own file), **Sierra Leone
> 2023 update** (now on statistics.sl itself), and **Djibouti** (a NEW
> census-based IPM, RGPH-3 2024 Thématique 16, on INSTAD's own backend — the
> 2012-2017 report below is still UNDP-only). Re-verified, still not
> collectable: Namibia, Malawi, Egypt, Sudan (details in their rows).

Four kinds of entry, kept apart on purpose:

1. **NSO-authored, but not NSO-hosted** — a real national MPI produced by the
   statistics office, available only on OPHI, UNDP or UNICEF. Under the
   standing rule (aggregators are not sources, and for MPI that explicitly
   includes OPHI and UNDP HDR) these are **leads, not sources**. Each is worth
   a periodic re-probe of the NSO domain, because a site rebuild can put the
   file back within reach.
2. **Located but unverified** — a file on the NSO's own domain that the recon
   fetcher could not open (TLS, WAF, robots, SPA shell, 30 MB cap). These are
   the highest-value next additions: the access route is resolved and only the
   layout is missing. **A fetch tool's failure is not the site's verdict** —
   the pipeline's `requests` client with a Chrome UA and `verify=False` gets
   through several of these.
3. **Verified negative** — the NSO publishes no MPI. Recorded so nobody
   re-searches them.
4. **Fetched, but unreadable** — the file is on the NSO's own domain and
   downloads cleanly, and the numbers are simply not in it as text. These sit
   in `sources_blocked/` with the whole descriptor and layout intact. They are
   NOT the same as (2): nothing here is waiting on an access route.

---

## 1. NSO-authored, hosted only on an aggregator

| Country | Measure | Methodology | Where it actually is | Note |
|---|---|---|---|---|
| **Namibia** | Namibia MPI Report 2021 (NSA + NPC) | 3 dims, 11 ind., k = 30; NHIES 2015/16 | mppn.org, unicef.org | `nsa.org.na` was rebuilt around the 2023 census and the 2021 MPI did not survive the move. **2026-10-07:** site search for "multidimensional" lists only the 2008 poverty review, child poverty 2009-10 and NHIES 2015/16 key poverty indicators; the WordPress media API has nothing; Wayback CDX of `nsa.org.na/wp-content/uploads/2021/`, `/2022/` and the old `/files/downloads/` holds no MPI file. National H 43.3 / A 44.0 / M0 0.191. |
| **Malawi** | Second Malawi MPI Report (Nov 2022) | 4 dims, 13 ind., k = 38; IHS5 2019/20 | not on `cms.nsomalawi.mw` | The whole publications catalogue was paged — all 5 pages, now 65 entries (`/api/web/publications`, re-paged 2026-10-07). The only poverty items are IHS5 and IHS6, both **monetary**; the Statistical Yearbook 2023 has no MPI. **Lead:** the IHS6 Cross-Section Report (June 2026) lists "create the MPI and the Child MPI" among the survey's objectives — watch IHS6 record 138 for an MPI media file. |
| **Djibouti** | IPM Djibouti 2012-2017, Rapport Final (INSD + MASS) | 5 dims, 14 ind., k = 33.33, **household**; EDAM-IS 2012 & 2017 | UNDP CDN (`files.acquia.undp.org`) | **2026-10-07:** INSTAD's backend categories were enumerated (from the site's JS: Rapports, Sociale, Méthodes, RGPH, SNDS, …) and this 2012-2017 report is not among them. But RGPH holds a NEWER, census-based IPM (Thématique 16, Nov 2025), now collected as `sources/djibouti.yaml` — a different measure (3 dims, 3 ind., person), never to be chained to this one. |
| **Sudan** | Sudan Report: Multidimensional Poverty Survey 2023 (CBS) | 3 dims, 14 ind., k = 25 | OPHI only | `cbs.gov.sd` **fails at DNS — the domain is gone.** **2026-10-07:** the Wayback CDX of `cbs.gov.sd` (5,077 URLs) holds only `POVERTY 2009.pdf` and the NHBPS food-security/poverty report (2019) — no MPS. |
| ~~Sierra Leone (2023 edition)~~ | MPI 2023 update (DHS 2019) | 5 dims, 14 ind., k = 40 | **now on statistics.sl** | **RESOLVED 2026-10-07:** linked from Stats SL's home page (`/images/StatisticsSL/Documents/undp_sl_multidimentsional_poverty_index_2023.pdf`) and collected as `sources/sierra_leone_2023.yaml`. |
| **Ghana (quarterly series)** | 2024 Q1 – 2025 Q3 MPI Report | 4 dims, 13 ind., k = 33.3; AHIES + QLFS | `sdgsghana.gov.gh` | GSS-authored but off the GSS domain. Also a **methodology break** from both collected Ghana editions (3 dims/12 ind and 3 dims/13 ind) — do not build a time series across them. |
| **Eswatini** | CSO national MPI, branded "OFFICIAL STATISTICS" | 3 dims, 9 ind., k = 33; EHIES 2017 | an OPHI-hosted **slide deck** | No CSO report exists — the only artefact is a conference presentation. Structurally near-identical to the global MPI, which makes it exactly the kind of measure that gets mislabelled. **Recommend not ingesting** until CSO publishes a report. |
| **Ethiopia** | Multidimensional Child Deprivation in Ethiopia (CSA + UNICEF, 2018) | child deprivation, not an MPI | unicef.org | CSA is a genuine co-author. Ethiopia's official poverty analysis sits with the Ministry of Planning, not the NSO. |
| **Egypt** | Egypt National MPI (CAPMAS with ESCWA) | 7 dims, 19 ind., k = 29; HIECS 2021/22 | OPHI only | **Moved out of `sources/` after the first real run.** `censusinfo.capmas.gov.eg` no longer resolves — the run failed with a DNS NXDOMAIN, not a 404 — and the main CAPMAS site is a JavaScript application exposing no path to the report. The descriptor is kept whole in `sources_blocked/egypt.yaml`; moving it back is the entire fix if CAPMAS restores the host. |

---

## 2. On the NSO domain, located, not yet verified

These are the next descriptors to write. Each has a resolved URL.

| Country | File | Blocker | What to check |
|---|---|---|---|
| **Central African Republic** | — | 470-publication catalogue, no MPI found | ICASEES has an EHCVM living-conditions report and a poverty assessment roadmap; neither is an MPI. |
| **São Tomé & Príncipe** | — | PhocaDownload category 52 (`economia`) is **empty** | No poverty category exists on the site at all. |

---

**Resolved 2026-10-07** — the eight other rows of this table were settled by
opening each document:

* **Senegal → collected** (`sources/senegal.yaml`). The ANSD file is the
  OPCV's *rapport national de présentation de l'IPM* (ESPS-II 2011), led by
  ANSD's Director-General: 5 dimensions / 25 indicators, k = 32%. A national
  measure, cover marked *version provisoire*.
* **Mauritania → collected** (`sources/mauritania.yaml`) from a DIFFERENT
  ANSADE file: the IPM-M tables (H, A, IPM with CIs; national, urban/rural,
  13 wilayas, two age groups) are reprinted with a text layer in ANSADE's
  *Annuaire des Statistiques Sociodémographiques 2024*, Tableaux 6.7-6.9. The
  scanned brief is still not OCR'd; only its methodology parameters (4 dims /
  19 indicators, person) were read by eye from it, and say so.
* **Cabo Verde → not collectable, and correctly so.** Both INE-CV documents
  (bdmi API, publication 3368: "Medindo a pobreza multidimensional" and the
  2026 World Bank *Poverty Assessment* filed with it) call the measure a
  PROPOSAL (12 indicators, 3 dimensions, k = 1/3, IDRF 2015). Its only
  incidence (17,2%) is in prose, the deprivation rates are a chart, and
  intensity is stated as future work. Re-check when INE computes it on IDRF
  IV.
* **Côte d'Ivoire → verified negative.** The EHCVM 2021 poverty profile
  (Wayback id_ of anstat.ci/assets/projet/ehcvm2021.pdf, 148 pp) is monetary
  plus subjective poverty; the global MPI appears only in its literature
  review (p.121).
* **Comoros → verified negative.** INSEED's EHCVM 2020 and 2024 results notes
  (NADA catalogue 9 and 15) are monetary. The MPI in the *Rapport d'évaluation
  de la pauvreté et de l'équité* (NADA 9, download 95) is authored by a World
  Bank team (13 indicators including consumption, cutoff 30%) — hosted by
  INSEED but not an INSEED measure.
* **Gabon → verified negative.** INSTAT's 2023 poverty notes (Wayback of
  instatgabon.org/wp-content/uploads/2023/10/) are monetary, from EGEP-II 2017.
* **Algeria → verified negative.** ons.dz is readable now; its search finds no
  poverty publication at all, only the 2011 consumption-expenditure survey.
* **DR Congo → verified negative.** INS's Enquête 1-2-3 2012 "pauvreté non
  monétaire ou de conditions de vie" is an UNWEIGHTED count of 17 housing and
  asset items with a cutoff (8) chosen to reproduce the monetary rate, and
  only its incidence is published — a living-conditions measure, not an MPI.

## 2b. Fetched, but the numbers are not text — `sources_blocked/`

Each of these ran, downloaded, and failed at the parse. The reason is written
in full at the top of its descriptor; the summary is here so the four are
visible in one place.

| Country | What arrives | Why it cannot be read | What would unblock it |
|---|---|---|---|
| **Morocco** | `hcp.ma/file/244249/` — 263 pages, **307 MB** | It is a **map atlas**. A scan of every page for a line carrying six or more numbers returns eleven, and ten of those are sentences. The regional and provincial IPM figures are inside the map plates as images. HCP's October 2025 per-region volumes (e.g. `hcp.ma/file/245986/`, 1.3 MB / 14 pages) were checked as a lighter alternative and have the same shape — prose around chart images. | OCR over the plates, or HCP publishing the underlying table. |
| **Somalia** | `nbs.gov.so/.../Multidimensional-Poverty-Index-MPI-2024.pdf`, 15.8 MB | Tables 3.1–3.3 — national, urban/rural/nomadic, and all 17 regions — are **raster images**. pdfplumber sees their captions and no rows. Every headline figure exists only in the executive summary's prose, which names four of the seventeen regions. | OCR, or SNBS republishing with a text layer. |
| ~~Ghana~~ (`ghana_report`) | **RESOLVED 2026-10-07:** the Wayback Machine holds an `id_` capture (2022-07-12) of GSS's own file; restored to `sources/ghana_report.yaml`, its layout rewritten against the printed pages (the old one read Table 3.5's male population share, 71.0, as national H). Previously: nothing — the old `/gssmain/fileUpload/pressrelease/` path 404s | GSS rebuilt on Next.js. Its catalogue **still lists** the report (`{"id":"BD50","title":"Multidimensional Poverty Ghana Report","year":2020,…}`) but with `"fileUrl":"#"` — and `"#"` for every other entry too. The site itself says it has no file. Ghana's census MPI (`sources/ghana.yaml`) is unaffected and runs green. | GSS attaching the documents. |
| **Egypt** | **2026-10-07:** the Wayback capture of the download (catalogue 1906, file 6861) is the 10-page ARABIC ESCWA policy brief; its figures are chart data labels and prose (national M0 0.077, rural 0.103, urban 0.042) with the category labels as garbled right-to-left text — the Somalia case. The English technical paper has no capture; CAPMAS's main API answered HTTP 500.30 all day. Previously: nothing — DNS NXDOMAIN | `censusinfo.capmas.gov.eg` no longer resolves; the main CAPMAS site is a JavaScript application exposing no path to the report. | CAPMAS restoring the host. |

Morocco and Somalia raise the same policy question and it has not been decided:
**does an OCR'd figure still count as "exactly as published"** for this
collector? Until that is answered, neither is scraped out of narrative text —
that would produce partial coverage (four regions of seventeen for Somalia)
wearing the appearance of a full table.

---

## 3. Verified negative — the NSO publishes no MPI

Checked directly, with the source read where the site allowed it. Do not
re-search these without new information.

**Côte d'Ivoire**, **Comoros**, **Gabon**, **Algeria**, **DR Congo** (each opened 2026-10-07; see §2) · **Tanzania** (NBS/OCGS — monetary only: basic-needs and food poverty lines) ·
**Kenya** (KNBS — the 2025 *Brighter Futures* child-poverty report is
multidimensional in spirit but is not an Alkire–Foster MPI) ·
**Burundi** (ISTEEBU/INSBU — EICVMB 2019-20 has monetary, subjective and
food-security measures and standalone deprivation indicators, never aggregated
into a weighted index) ·
**Ethiopia** (ESS — see above) · **South Sudan** (NBS — `Poverty.php` 404s;
poverty is not a live topic) · **Eritrea** (no functional publications portal) ·
**Zimbabwe** · **Zambia** · **Lesotho** · **Mozambique** ·
**Niger** · **Benin** · **Togo** · **Liberia** · **The Gambia** ·
**Guinea-Bissau** ·
**Tunisia** (INS — poverty framework is *strictly* monetary, confirmed against
its own methodology paper) ·
**Cameroon** (INS — ECAM5 2021-22 is monetary; press release read) ·
**Chad** (INSEED — full 136-publication API enumerated across both pages; one
poverty publication, ECOSIT4, monetary) ·
**Congo-Brazzaville** (INS Congo — surveys page holds COVID-era EESC bulletins
and the price index only) ·
**Libya** (BSC — nothing in English or Arabic; the only Libya MPI artefacts are
UNDP HDR profiles).

**Equatorial Guinea is the one live forward lead** (re-checked 2026-10-07: the ENH2 final report has no multidimensional measure in 184 pages, and inege.org lists no *Perfil de Pobreza Multidimensional* yet). INEGE held a
multidimensional-poverty measurement workshop on 15 May 2024 (`inege.org/?p=5576`)
with UNECA, the World Bank and UNDP, and has stated it will produce a *Perfil de
Pobreza Multidimensional* from its second national household survey. Worth a
scheduled re-check.

---

## Deferred within countries already collected

* **Ghana StatsBank** — district-level detail is requested and dropped by the
  parser (national + 16 regions are kept); the MPI-by-education and
  MPI-by-industry cuts in the same StatsBank folder are not yet mapped.
* **Ghana** methodology block is **partly inferred**: the 13-indicator count is
  read off the contributors table, but the 3 dimensions and k = 33.3 follow
  GSS's stated methodology rather than a StatsBank metadata field. Confirm
  against the GSS PHC 2021 MPI documentation — those values travel onto every
  row.
* **Nigeria** — the 109-senatorial-district and child-MPI (5 dims, 24
  indicators) tables are not mapped; the collected layout is the national /
  state headline only, and its **column order is unverified**.
* **Rwanda** — EICV5 (2018) prior edition, and the child MPI.
* **Uganda** — the 2022 UNHS-based edition (different methodology from the
  collected 2024 census edition).
* **South Africa** — SAMPI exists only for Census 2001 and 2011. A 2024 Stats
  SA presentation cites a 2016 headcount of 7.0% and says Stats SA is
  *"exploring the option"* of updating SAMPI with survey data. **No 2016 or
  Census-2022 SAMPI report exists — do not chase one.**


---

## Found during the first real run

**Botswana republishes the global MPI.** Appendix 5 of the Pilot National MPI
report prints the 2020 global MPI (Alkire, Kanagaratnam & Suppa) for all 26
districts and the nation, beside monetary poverty and Botswana's own index.
That column is now harvested as `mpi_type: global` — 27 rows, national
incidence 17.20%. It is the one substantial global-MPI series any African NSO
hosts on its own site, and it was not visible from the recon summaries.

**Guinea uses nine indicators, not eight**, and prints its index as a
PERCENTAGE. Both corrected; see the note at the foot of `sources/guinea.yaml`.

**Guinea's Tableau 2-2 is not what its caption says.** Titled "contribution des
différents indicateurs à l'IPM au régional (%)", its rows sum to roughly 165%.
Whatever those numbers are, they are not contributions, so they are left
unharvested rather than mislabelled.

**Mauritius Table A1 is now collected** — all 166 administrative areas, with H,
A and MPI each. Table A2 (censored headcount ratios for the same 166 areas) is
still deferred.

**Angola turned out to be the richest document in the set** and now yields
eight tables: national, locality, three province tables, age group, sex of
head, and the uncensored/censored headcount ratios by indicator.

**Still never checked against a printed page:** `nigeria`, `rwanda`,
`seychelles`, `sierra_leone`, `somalia`, `south_africa`, `uganda`,
`ghana_report`, `morocco`. Their downloads had not completed when the run
stopped. Morocco's is a 126 MB file whose first attempt truncated.
