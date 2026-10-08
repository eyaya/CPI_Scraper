"""Parser registry for unemployment / labour-force sources.

Four kinds of parser sit behind these ids:

* **`ghana_pxweb_unemployment`** -- a hand-written Tier-1 PxWeb reader. Ghana is
  the only NSO in Africa exposing its labour tables through a machine-readable
  API, so it earns bespoke code.
* **PDF layouts** -- ONE MODULE PER COUNTRY, `<country>_unemployment.py`, each
  holding a declarative layout read by `pdf_key_indicators.make_parser`. These
  were a single 1,900-line `layouts.py`; they are split so that a country's
  layout sits beside its own descriptor and its own notes, which is the shape
  every other indicator in this repo uses. Shared column vocabularies live in
  `_vocab.py`.
* **Structured workbooks** -- `excel_wide_series` over `excel_layouts.py` for
  the period-across-the-columns shape, plus two readers of their own where that
  model does not fit: Mauritius (periods run DOWN the rows) and Egypt (a
  single-quarter release with sex across the columns).
* **Server-rendered HTML** -- `html_wide_series` over `html_layouts.py`, for
  INS Tunisie, whose PDF is bidi-scrambled and unusable.

Mali is the exception to all of it: its bulletin is an INFOGRAPHIC, so
`mali_pdf_bulletin` reads it by glyph position rather than by line.

Adding a country is: write `<country>_unemployment.py`, add it below, write
`sources/<country>.yaml`. A country whose report has no parseable table (chart
labels or an image only) is NOT given an entry -- see PENDING.md for why, and
do not invent one to fill the gap.
"""
from . import ghana_pxweb_unemployment
from . import ghana_census_unemployment
from . import pdf_key_indicators  # noqa: F401  -- re-exported for the tests
from . import excel_wide_series
from . import html_wide_series
from . import mauritius_excel_cmphs
from . import egypt_excel_lfs
from . import mali_pdf_bulletin
from .excel_layouts import EXCEL_LAYOUTS
from .html_layouts import HTML_LAYOUTS

from . import angola_unemployment
from . import angola_ine_workbooks
from . import benin_unemployment
from . import botswana_unemployment
from . import burkina_faso_unemployment
from . import cameroon_unemployment
from . import egypt_unemployment
from . import eswatini_unemployment
from . import ethiopia_unemployment
from . import guinea_bissau_unemployment
from . import kenya_unemployment
from . import liberia_unemployment
from . import morocco_unemployment
from . import namibia_unemployment
from . import niger_unemployment
from . import nigeria_unemployment
from . import rwanda_unemployment
from . import seychelles_unemployment
from . import sierra_leone_unemployment
from . import somalia_unemployment
from . import tanzania_unemployment
from . import uganda_unemployment
from . import zambia_unemployment
from . import zimbabwe_unemployment
from . import sudan_unemployment
from . import burundi_unemployment
from . import equatorial_guinea_unemployment
from . import gabon_unemployment
from . import south_sudan_unemployment
from . import chad_unemployment
from . import central_african_republic_unemployment
from . import congo_unemployment
from . import drc_unemployment
from . import cabo_verde_unemployment
from . import mozambique_unemployment
from . import sao_tome_and_principe_unemployment
from . import madagascar_unemployment
from . import comoros_unemployment
from . import mauritania_unemployment
from . import djibouti_unemployment
from . import libya_unemployment
from . import togo_unemployment
from . import senegal_unemployment
from . import cote_divoire_unemployment
from . import guinea_unemployment
from . import algeria_unemployment
from . import gambia_unemployment
from . import lesotho_unemployment
from . import malawi_unemployment

REGISTRY = {
    # --- Tier 1: API ------------------------------------------------------
    "ghana_pxweb_unemployment": ghana_pxweb_unemployment.parse,
    # Ghana's census series, moved here from `labour` -- a rate needs the
    # definition and working-age base that only this indicator records.
    "ghana_census_unemployment": ghana_census_unemployment.parse,

    # --- Tier 3: report PDF, one module per country -----------------------
    "angola_pdf": angola_unemployment.parse,
    # INE Angola IEA workbooks (POSTed): headline series on both ICLS bases,
    # rates by residence/sex/age, and the 18 provinces annually.
    "angola_ine_workbooks": angola_ine_workbooks.parse,
    "benin_pdf": benin_unemployment.parse,
    "botswana_pdf": botswana_unemployment.parse,
    "burkina_faso_pdf": burkina_faso_unemployment.parse,
    "cameroon_pdf": cameroon_unemployment.parse,
    "egypt_pdf": egypt_unemployment.parse,
    "eswatini_pdf": eswatini_unemployment.parse,
    "ethiopia_pdf": ethiopia_unemployment.parse,
    "guinea_bissau_pdf": guinea_bissau_unemployment.parse,
    "kenya_pdf": kenya_unemployment.parse,
    "liberia_pdf": liberia_unemployment.parse,
    "morocco_pdf": morocco_unemployment.parse,
    "namibia_pdf": namibia_unemployment.parse,
    "niger_pdf": niger_unemployment.parse,
    "nigeria_pdf": nigeria_unemployment.parse,
    "rwanda_pdf": rwanda_unemployment.parse,
    "seychelles_pdf": seychelles_unemployment.parse,
    "sierra_leone_pdf": sierra_leone_unemployment.parse,
    "somalia_pdf": somalia_unemployment.parse,
    "tanzania_pdf": tanzania_unemployment.parse,
    "uganda_pdf": uganda_unemployment.parse,
    "zambia_pdf": zambia_unemployment.parse,
    "zimbabwe_pdf": zimbabwe_unemployment.parse,

    # CBS Sudan via Wayback id_ copies: SLFS 2011 (CBS 'Labor Force' booklet)
    # counts by sex/state and youth unemployment rates by sex x area, plus
    # 2008 census E1 activity counts for NORTHERN Sudan and its 15 states only.
    "sudan_unemployment": sudan_unemployment.parse,
    # INSBU Burundi EICVMB 2019-20, Module Emploi (household survey, 15+):
    # activity rate strict/étendu, employment ratio, strict unemployment and
    # LU3, by milieu/sex/age/education/province, plus annex counts.
    "burundi_unemployment": burundi_unemployment.parse,
    # INEGE ENH2 2022-23 Tabla 46 (base 18-64): participation, employment
    # ratio, unemployment, underemployment by región/zona/sexo/provincia; plus
    # EPAFE 2015 (base 16+) from the Anuario Estadístico 2023 Tabla 88.
    "equatorial_guinea_unemployment": equatorial_guinea_unemployment.parse,
    # INSTAT Gabon RGPL-2013 ch. V: actifs/inactifs/working-age counts by
    # milieu x sex and province, TBA and taux de chômage by province x milieu
    # x sex, occupés by sex -- base 16-65.
    "gabon_unemployment": gabon_unemployment.parse,
    # NBS South Sudan 2008 census Tables 5-1/5-2: participation and
    # unemployment rates on the 10+ and 15+ bases, by sex, urban/rural, age,
    # education and state -- household-head blocks left out.
    "south_sudan_unemployment": south_sudan_unemployment.parse,
    # INSEED Chad ECOSIT4 2018-19 ch.7: activité 5+/15+, chômage BIT and élargi
    # (15+ and 15-64) by stratum, province, age, education/diploma; SU3 by province.
    "chad_unemployment": chad_unemployment.parse,
    # ICASEES CAR RGPH03 census: activity rates brut (6+) / spécifique (15+) by
    # milieu, région/préfecture, education; chômage 15+ (census concept, not BIT); 1988 as republished.
    "central_african_republic_unemployment": central_african_republic_unemployment.parse,
    # CNSEE/INS Congo via Wayback id_: ECOM 2005 national chômage + activité; EESIC 2009
    # and 2011 urban tables (BIT, élargi, activity) -- urban series never national.
    "congo_unemployment": congo_unemployment.parse,
    # INS DRC Enquête 1-2-3 2012 (Wayback id_): chômage BIT / sens large / doublement
    # élargi by age x stratum, activity 10+/15+, time-related underemployment.
    "drc_unemployment": drc_unemployment.parse,
    # INE Cabo Verde IMC workbook 2011-2025: population, labour force, employed,
    # unemployed, activity/employment/underemployment/unemployment rates, youth
    # (15-24, 15-35), NEET, underutilisation -- 13th/19th ICLS in survey.
    "cabo_verde_unemployment": cabo_verde_unemployment.parse,
    # INE Mozambique IOF 2022 + 2019/20 ch.6: PEA, employment (by age),
    # underemployment, unemployment by sex/residence/province/education --
    # 'definição alternativa' (Desempregado C counted), filed broad.
    "mozambique_unemployment": mozambique_unemployment.parse,
    # INE STP: RGPH 2012 activity/employment/unemployment rates by sex x
    # residence x age and district; IOF 2017 BIT unemployment, youth, NEET;
    # QUIBB 2005 activity and unemployment by sex/residence/domain/education.
    "sao_tome_and_principe_unemployment": sao_tome_and_principe_unemployment.parse,
    # INSTAT Madagascar: ENEMPSI 2012 (strict + élargi unemployment, activity,
    # underemployment; base 5+), RGPH-3 2018 (net activity, unemployment,
    # 15-59), EPM 2021-22 (participation, unemployment, youth, NEET, informal).
    "madagascar_unemployment": madagascar_unemployment.parse,
    # INSEED Comoros: EEIC 2021 key indicators (14-64; LU1 strict, LU2-4 broad, youth 15-34),
    # RGPH 2017 net activity / taux d'occupation / chômage global, EESIC 2013 counts by island.
    "comoros_unemployment": comoros_unemployment.parse,
    # ANSADE Mauritania: ENTE quarterly notes 2025 (annexes 4-9, each with the year-earlier quarter:
    # 2024-Q1..2025-Q4, base 14-64, by sex/age/education/milieu/7 zones) + ENESI 2017 annexes.
    "mauritania_unemployment": mauritania_unemployment.parse,
    # INSTAD Djibouti: RGPH-3 2024 BIT/élargi unemployment (15-64, 15-59, youth 15-34/15-24), EPR,
    # counts; plus EDST quarterly notes 2025 Q1-Q4 (16+, SU1-SU4, LFPR, EPR, NEEF).
    "djibouti_unemployment": djibouti_unemployment.parse,
    # BSC Libya LFS 2022 (Libyan nationals 15+): Tables 8 and 20 -- employed / activity rate and
    # unemployed / unemployment rate by 22 regions x sex; Arabic labels stated from rendered pages.
    "libya_unemployment": libya_unemployment.parse,
    # INSEED Togo ERI-ESI 2017: recap + Tableaux 5.4 / 5.15 (BIT, SU1-SU4,
    # participation counts, employment ratio, NEET). Hosts the shared ERI-ESI
    # template reader that Senegal imports.
    "togo_unemployment": togo_unemployment.parse,
    # ANSD Senegal: quarterly ENES summary box (2025 Q1 onward, accepted only
    # when its own arithmetic holds; the unlabelled élargi 'Chômage' is not
    # taken) + ERI-ESI 2017 tables.
    "senegal_unemployment": senegal_unemployment.parse,
    # ANStat Côte d'Ivoire via Wayback copies of its own files: EHCVM 2021
    # ch.4 (base 16+) and ENSETE 2013 (14+, February 2014).
    "cote_divoire_unemployment": cote_divoire_unemployment.parse,
    # INS Guinée ENESIG 2018/19: participation, employment, unemployment and
    # youth 15-35 rates by urban/rural x sex, region and age.
    "guinea_unemployment": guinea_unemployment.parse,
    # ONS Algeria Rétrospective 1962-2020 ch. II: 23 LFS rounds 2000-2019 (rates,
    # counts by sex x strate and age), unemployment rate back to 1966, RGPH 1998
    # labour force by wilaya, and the 2024 communiqué's 9,7%.
    "algeria_unemployment": algeria_unemployment.parse,
    # GBoS Gambia GLFS 2026 annex T0.3/T0.4, 2025 (from T2.2/2.3), 2022-23 T3.1,
    # 2018 (15-64) participation and unemployed counts -- read by position,
    # proved by arithmetic.
    "gambia_unemployment": gambia_unemployment.parse,
    # BOS Lesotho LFS 2024 and 2019: main indicators by sex/settlement, LU1-LU4,
    # participation by district/age/settlement, unemployed by age/district.
    "lesotho_unemployment": lesotho_unemployment.parse,
    # NSO Malawi LFS 2024 full report (broad unemployment, LU2-LU4, NEET, by
    # group and district) plus 2018 census Series D counts.
    "malawi_unemployment": malawi_unemployment.parse,
    # --- Read by position, not by line ------------------------------------
    "mali_pdf": mali_pdf_bulletin.parse,

    # --- Tier 2: structured workbook --------------------------------------
    # Mauritius is TRANSPOSED relative to `excel_wide_series` (periods down
    # column A) and Egypt is a single-quarter release with no period column at
    # all. Both reported "no period header row" on every sheet -- one wrong
    # model, not thirty-six changed layouts -- so each has its own reader.
    "mauritius_excel": mauritius_excel_cmphs.parse,
    "egypt_excel": egypt_excel_lfs.parse,
}

# --- Tier 2: structured workbook (period-across-the-columns) --------------
for _name, _cfg in EXCEL_LAYOUTS.items():
    REGISTRY.setdefault(f"{_name}_excel", excel_wide_series.make_parser(_cfg))

# --- Tier 2: server-rendered HTML table ----------------------------------
for _name, _cfg in HTML_LAYOUTS.items():
    REGISTRY[f"{_name}_html"] = html_wide_series.make_parser(_cfg)

# The offline tests reach for a country's layout by name; keep that working
# now that each lives in its own module.
LAYOUTS = {}
for _mod in list(globals().values()):
    _L = getattr(_mod, "LAYOUTS", None)
    name = getattr(_mod, "__name__", "")
    if (isinstance(_L, dict) and name.endswith("_unemployment")
            and not name.endswith("ghana_pxweb_unemployment")):
        LAYOUTS.update(_L)

del _name, _cfg, _mod, _L
