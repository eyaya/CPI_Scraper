"""Parser registry for labour sources.

This indicator holds the COMPOSITION of employment -- industry, occupation,
status in employment, institutional sector, formal/informal, activity status.
The headline status series (unemployment / participation / employment-to-
population rates and the level counts behind them) belongs to `unemployment`;
neither indicator carries the other's figures.

Three kinds of parser sit behind these ids:

* **Bespoke Tier-1/2 readers** -- Ghana's StatsBank PxWeb decoder and Malawi's
  census workbook reader, each written around one source's own shape.
* **`<country>_labour.py` layouts** -- one module per country, declarative, read
  by an engine. Wide workbooks (periods across the columns, categories down the
  rows) go through `excel_wide_labour`.
* **Shared helpers** -- `_common.py` builds every row and is the one place that
  knows the schema's vocabulary. It refuses a category row that names no
  classification, because an industry or occupation label is not comparable
  across countries without the scheme that produced it.

Adding a country is: write `<country>_labour.py`, add it below, write
`sources/<country>.yaml`.
"""
from . import _common  # noqa: F401  -- re-exported for the layouts
from . import excel_wide_labour  # noqa: F401
from . import html_wide_labour  # noqa: F401
from . import pdf_tables_labour  # noqa: F401
from . import algeria_labour
from . import angola_labour
from . import benin_labour
from . import botswana_labour
from . import burkina_faso_labour
from . import burundi_labour
from . import cabo_verde_labour
from . import cameroon_labour
from . import central_african_republic_labour
from . import chad_labour
from . import comoros_labour
from . import congo_labour
from . import cote_divoire_labour
from . import djibouti_labour
from . import drc_labour
from . import egypt_labour
from . import equatorial_guinea_labour
from . import eswatini_labour
from . import ethiopia_labour
from . import gabon_labour
from . import gambia_labour
from . import guinea_bissau_labour
from . import guinea_labour
from . import ghana_pxweb_labour
from . import kenya_labour
from . import lesotho_labour
from . import liberia_labour
from . import libya_labour
from . import madagascar_labour
from . import malawi_nso_labour
from . import mali_labour
from . import mauritania_labour
from . import mauritius_labour
from . import morocco_labour
from . import mozambique_labour
from . import namibia_labour
from . import niger_labour
from . import nigeria_labour
from . import rwanda_labour
from . import sao_tome_and_principe_labour
from . import senegal_labour
from . import seychelles_labour
from . import sierra_leone_labour
from . import somalia_labour
from . import south_africa_labour
from . import south_sudan_labour
from . import tanzania_labour
from . import togo_labour
from . import tunisia_labour
from . import zimbabwe_labour
from . import uganda_labour
from . import zambia_labour
from . import sudan_labour

REGISTRY = {
    # --- Tier 1: API ------------------------------------------------------
    # GSS StatsBank PHC 2021 economic activity: activity status, and the
    # employment-status / industry / occupation / sector composition of the
    # employed. (The census unemployment RATE moved to `unemployment`.)
    "ghana_pxweb_labour": ghana_pxweb_labour.parse,

    # --- Tier 2: structured workbook --------------------------------------
    # NSO Malawi 2018 census, Series D (activity status D1 + industry D7).
    "malawi_nso_labour": malawi_nso_labour.parse,
    # Stats SA QLFS Trends: industry, occupation, status in employment on BOTH
    # ICLS bases, and formal/informal -- 74 quarters from 2008 Q1.
    "south_africa_labour": south_africa_labour.parse,
    # INE Angola IEA "Quadros complementares", one workbook per methodology
    # (13th ICLS to 2025 Q3, 19th-21st from 2025 Q4) -- fetched by POST.
    "angola_labour": angola_labour.parse,

    # --- Tier 3: report PDF -----------------------------------------------
    # ZamStats LFS 2024: status in employment on ICSE-18-A, which the report
    # names explicitly as its basis.
    "zambia_labour": zambia_labour.parse,
    # Statistics Botswana QMTS: BOSCO occupation, industry, employer sector,
    # status by sex, formality totals, plus the report's back-quarter columns.
    "botswana_labour": botswana_labour.parse,
    # NBS Seychelles LFS bulletin: status on ICSE-93, ICSE-18-A and ICSE-18-R,
    # ISCO-08 occupation, ISIC Rev.4 industry, informal sector/employment.
    "seychelles_labour": seychelles_labour.parse,
    # NISR annual LFS: 2019-2025 trends (status ICSE-93, occupation, industry,
    # formality) and ICSE-18 by sex and urban/rural.
    "rwanda_labour": rwanda_labour.parse,
    # NBS Tanzania ILFS: status, industry, TASCO occupation for Mainland,
    # Zanzibar and the Union. Rows rebuilt from word positions.
    "tanzania_labour": tanzania_labour.parse,
    # NSA Namibia PHC 2023: occupation (NASCO-96), industry (ISIC Rev.4),
    # status, and the youth 15-34 cuts -- read out of a text layer that
    # contains the whole report twice.
    "namibia_labour": namibia_labour.parse,
    # CSO Eswatini ILFS 2023: occupation, economic activity, unit of
    # production, and informal employment by region -- percentages only, and
    # no classification named anywhere in the booklet.
    "eswatini_labour": eswatini_labour.parse,
    # ESS Ethiopia LMS 2021 Summary Table 2: occupation, industrial divisions
    # and employment status across FOUR survey rounds (1999-2021), on a 10+
    # working-age base.
    "ethiopia_labour": ethiopia_labour.parse,
    # SNBS Somalia SLFS 2019: economic sector and branch, occupation in detail
    # and by sex, and unit of production -- with the report's own truncated
    # category labels kept as printed.
    "somalia_labour": somalia_labour.parse,
    # CAPMAS Egypt quarterly LFS bulletin: occupation and economic activity,
    # TRANSPOSED (categories across the columns, sex down the rows) and printed
    # right-to-left, so the column order runs in reverse.
    "egypt_labour": egypt_labour.parse,
    # Statistics Mauritius CMPHS workbook: status, industry (NSIC), occupation
    # (ISCO-08) and hours worked -- transposed the other way from every other
    # workbook here, with periods down the rows and a block per sex.
    "mauritius_labour": mauritius_labour.parse,
    # INSD Burkina Faso ENB-ESI 2023: Figure 4's sixteen branches of economic
    # activity. A "figure" whose category values are PRINTED AS TEXT data
    # labels -- unlike Zimbabwe's charts, which carry none and are blocked.
    "burkina_faso_labour": burkina_faso_labour.parse,
    # HCP Morocco annual ENE report: Tableau 4's four stacked distributions --
    # occupation, statut professionnel, secteurs d'emploi and branches
    # d'activité -- by sex and by urban/rural.
    "morocco_labour": morocco_labour.parse,
    # ONS Algeria Rétrospective 1962-2020, Chapitre II: employed by sector for
    # 25 LFS rounds (2000-2019), the 1989-92 MOD surveys by sex, 1997 and the
    # 1977/1987 censuses -- counts split under each table's own arithmetic.
    "algeria_labour": algeria_labour.parse,
    # GBoS Gambia GLFS findings reports: ISIC Rev.4 industry and ISCO-08
    # occupation for 2025/2026 (Q1), ICSE-93 status + industry + occupation for
    # 2022-23, and the 2018 round on a 15-64 base -- read by word positions.
    "gambia_labour": gambia_labour.parse,
    # UBOS Uganda LMS 2025 main report: broad sector by sex, rural-urban and
    # sub-region, on the ILO 15+ base and the national 14-64 base.
    "uganda_labour": uganda_labour.parse,
    # BOS Lesotho LFS 2024 + 2019 (ZIPs listed only in a JS array): ISCO-08
    # occupation, ISIC Rev.4 industry, ICSE-18-A / ICSE-93 status, formality.
    "lesotho_labour": lesotho_labour.parse,
    # LISGIS Liberia LFS 2016-17 (new API site): ICSE-93 status, ISIC Rev 4,
    # ISCO-08 and formality -- Table 5.4 read from the text layer.
    "liberia_labour": liberia_labour.parse,
    # INSEED Chad ECOSIT4 2018-19 (household consumption survey, employment
    # chapter): CSP, eleven branches and branche institutionnelle, national --
    # Tableau 7.08's wrapped rows split their values across lines.
    "chad_labour": chad_labour.parse,
    # INS Cameroun EESI3 2021 main report (not the dépliant `unemployment`
    # reads): institutional/activity sector and CSP by milieu, sex and age,
    # for all 14+ and for 15-34 -- Tableau 3.7's Ensemble column is LAST.
    "cameroon_labour": cameroon_labour.parse,
    # ZIMSTAT Zimbabwe 2019 LFCLS annual report (the quarterly QLFS prints
    # composition only as charts): status, 23 industries, ISCO-08 occupation,
    # formal/informal/household sector and informal employment counts.
    "zimbabwe_labour": zimbabwe_labour.parse,
    # INSTAT Mali EMOP table workbooks, 2020-2025 (April-June module):
    # four activity sectors and three statuts by region, milieu, sex and
    # education -- 2023's copied national row dropped and re-checked.
    "mali_labour": mali_labour.parse,
    # INE Cabo Verde IMC "Mercado de Trabalho" workbook: branch, occupation,
    # broad sector, situação na profissão and informal employment, 2011-2025
    # (13th/19th ICLS in `survey`), by residence, sex and (2025) concelho/age.
    "cabo_verde_labour": cabo_verde_labour.parse,
    # INSBU Burundi Annuaire statistique, Tableau 6.01: employed by status in
    # employment from four household surveys (2010-2020), each column its own
    # survey -- the rest of the chapter is INSS/civil-service registers.
    "burundi_labour": burundi_labour.parse,
    # INSTAT Gabon RGPL-2013 Résultats globaux: status in employment and
    # institutional sector of the employed 16-65, by milieu and sex.
    "gabon_labour": gabon_labour.parse,
    # INEGE Equatorial Guinea ENH2 2022-23 (household survey), base 18-64:
    # formal/informal, tipo de ocupación, occupation I-IX by región, zona,
    # sexo and provincia, plus employed counts per branch.
    "equatorial_guinea_labour": equatorial_guinea_labour.parse,
    # INS Niger ERI-ESI 2017, chapter 5 (household employment, NOT the UPI
    # module): institutional sector by sex, stratum and region, and the
    # overall formal/informal split -- universe checked against the report's
    # own employed count.
    "niger_labour": niger_labour.parse,
    # NBS NLFS Annual Report 2023 (four pooled quarters, state estimates):
    # self-employed/employees and informal-employment counts by state and sex,
    # plus Figures 9/11 (20 ISIC sections, 9 occupation groups) read from
    # text data labels -- all National, since no revision is ever named.
    "nigeria_labour": nigeria_labour.parse,
    # INE Mozambique IOF 2022 (household budget survey), chapter 6: ten ramos
    # de actividade and eleven posições no processo laboral for the employed
    # 15+, by sex, urban/rural, province and education -- rotated headers
    # re-read from page geometry.
    "mozambique_labour": mozambique_labour.parse,
    # INSTAT Madagascar: ENEMPSI 2012 Tome 1 workbook (institutional sector,
    # CSP, 12 branches by milieu/sex/region/age, base 5+) and RGPH-3 2018
    # (NOMAC branches and status by milieu x sex, base 15-59; T5.7 is rotated).
    "madagascar_labour": madagascar_labour.parse,
    # BSC Libya LFS 2022 (Libyan nationals 15+ only): sector by sex and by
    # region, 20 activity sections by sex, weekly hours -- Arabic labels
    # stated from the rendered pages; the text layer's font mapping is broken.
    "libya_labour": libya_labour.parse,
    # INS Guinée RGPH-3 2014 "Caractéristiques économiques" (occupation,
    # status and 20 branches by milieu x sex, region, age, education) plus
    # EHCVM 2018/19 section 10.17 (sector, CSP, 11 branches) -- rotated and
    # transposed headers mapped by order, each order proven.
    "guinea_labour": guinea_labour.parse,
    # Stats SL: PHC 2015 economic-characteristics report (occupation by sex
    # and by region, counts, 15-64) and SLLFS 2014 Table 2 (job type and five
    # sectors by sex, youth, education, locality and region). SLIHS 2018's
    # employment-type table refused (total exceeds its own employed count).
    "sierra_leone_labour": sierra_leone_labour.parse,
    # INE São Tomé and Príncipe RGPH 2012, thematic report 5 (employed 15+):
    # sector by sex x age, CAE-STP sections by district, CNP-STP occupation
    # groups by sex/age/residence, situação na profissão by district, hours.
    "sao_tome_and_principe_labour": sao_tome_and_principe_labour.parse,
    # INSEED Comoros (NADA): EEIC 2021 employed counts by status, branch and
    # occupation by sex/milieu plus formality; RGPH 2017 status, 17 branches
    # and occupational groups by milieu x sex; EESIC 2013 institutional sector
    # by island -- EEIC counts re-split under M+F=T, U+R=T.
    "comoros_labour": comoros_labour.parse,
    # NBS South Sudan 2008 census tables, chapter 5: occupation (10 groups),
    # nine industry aggregates and employment status on the 10+ and 15+
    # bases, by sex, urban/rural, age, education and state -- persons
    # "working or who worked previously"; sideways pages read by word position.
    "south_sudan_labour": south_sudan_labour.parse,
    # INE Guiné-Bissau RGPH 2009 "Características económicas", Anexos 11/13/14:
    # employed COUNTS by branch, occupation and situação na profissão, for
    # those with a declared answer (54/30/66% of 488 644) -- shares refused.
    "guinea_bissau_labour": guinea_bissau_labour.parse,
    # ANSADE Mauritania: ENESI 2017 annexe A4.1 (24 branches x sex, counts)
    # and RGPH 2013 Volume 3 (branch x sex, branch x milieu incl. Nomade,
    # statut dans l'emploi x sex), base 14-64 -- all National.
    "mauritania_labour": mauritania_labour.parse,
    # ICASEES Central African Republic RGPH03 (census, Dec 2003), employed
    # aged 6+: occupation by sex / milieu / region, branch by milieu, status
    # by sex x milieu -- Eco 13's copied Region 3/4 column not collected.
    "central_african_republic_labour": central_african_republic_labour.parse,
    # INS DR Congo Enquête 1-2-3 2011-12 (Wayback id_ copy of INS's own PDF),
    # Phase 1, employed 10+: institutional sector (formality) and CSP by
    # Kinshasa / other urban / rural / RDC.
    "drc_labour": drc_labour.parse,
    # INSEED Togo ERI-ESI 2017 Rapport Global, chapter 5 (household employment,
    # not the UPI module): institutional sector by sex, milieu and region, and
    # CITP major groups (counts + %) -- printed aggregates verified, not emitted.
    "togo_labour": togo_labour.parse,
    # INSTAD Djibouti RGPH-3 2024, Tome 3: occupation major groups (counts + %)
    # and formal/informal by region, milieu, sex, age and education -- the
    # branch and three-sector tables contradict the volume and are left out.
    "djibouti_labour": djibouti_labour.parse,
    # KNBS Kenya KIHBS 2015/16 Labour Force Basic Report, Table 3.8: usual
    # weekly hours of the employed 15-64 (eleven bands) by age and sex -- the
    # only household composition table KNBS publishes; Economic Survey refused.
    "kenya_labour": kenya_labour.parse,
    # ANSD Senegal: ERI-ESI 2017 employment chapter (institutional sector by
    # sex/milieu/region, sector counts + formal/informal, CITP groups) and
    # EHCVM 2018/19 ch. VII (sector, statut, 5 branches by milieu and
    # education) -- the quarterly ENES notes remain chart-only.
    "senegal_labour": senegal_labour.parse,
    # CNSEE/INS Congo via Wayback id_ copies of CNSEE's own files: ECOM 2005
    # branch and CSP (Ensemble columns, 15+ and all employed 10+), and EESIC
    # 2009 phase-1 sector / CSP / activity for Brazzaville, Pointe-Noire, urban.
    "congo_labour": congo_labour.parse,
    # ANStat Côte d'Ivoire EHCVM 2021 (Wayback id_ copy of ANStat's own PDF;
    # anstat.ci is behind a Cloudflare challenge): formal/informal employment
    # by sex, age, education and residence, counts + shares, base 16+.
    "cote_divoire_labour": cote_divoire_labour.parse,
    # INSAE Benin ETVA-2014 school-to-work survey (Wayback id_ copy; instad.bj
    # in maintenance): youth 15-29 only -- status, CITI Rév.4 branches and
    # CITP-08 occupations by sex, counts + %.
    "benin_labour": benin_labour.parse,

    # CBS Sudan via Wayback id_ copies: SLFS 2011 occupation % by area x sex
    # (10+, 15+) and 2008 census E2 industry / E3 occupation / E4 status counts
    # for NORTHERN Sudan and its 15 states, by residence (incl. nomad) and sex.
    "sudan_labour": sudan_labour.parse,
    # --- HTML theme pages -------------------------------------------------
    # INS Tunisie: employed by branch of economic activity, from the same
    # server-rendered pages `unemployment` reads. The only HTML source in the
    # corpus, and the only correct route for Tunisia -- INS's quarterly PDF is
    # bidi-scrambled beyond alignment.
    "tunisia_labour": tunisia_labour.parse,
}
