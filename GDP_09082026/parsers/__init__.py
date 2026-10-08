"""Parser registry: maps the `parser` id in a source descriptor to a
function `parse(local_path) -> tidy-ish DataFrame`."""
from . import algeria_ons_gdp
from . import botswana_gdp
from . import burkina_insd_gdp
from . import burundi_insbu_gdp
from . import cameroon_ins_gdp
from . import chad_inseed_gdp
from . import ci_anstat_gdp
from . import comoros_inseed_gdp
from . import drc_bcc_gdp
from . import egypt_cbe_gdp
from . import ethiopia_nbe_gdp
from . import gambia_gbos_gdp
from . import ghana_pxweb_gdp
from . import guinea_ins_gdp
from . import kenya_knbs_gdp
from . import liberia_lisgis_gdp
from . import libya_cbl_gdp
from . import madagascar_instat_gdp
from . import malawi_nso_gdp
from . import mali_instat_gdp
from . import mauritania_ansade_gdp
from . import mauritius_gdp
from . import morocco_hcp_gdp
from . import namibia_gdp
from . import nbs_nigeria_gdp
from . import niger_ins_gdp
from . import rwanda_nisr_gdp
from . import saotome_ine_gdp
from . import senegal_ansd_gdp
from . import seychelles_nbs_gdp
from . import sierraleone_stats_gdp
from . import somalia_snbs_gdp
from . import statssa_gdp
from . import tanzania_nbs_gdp
from . import togo_inseed_gdp
from . import tunisia_bct_gdp
from . import uganda_ubos_gdp
from . import zimbabwe_zimstat_gdp
from . import lesotho_bos_gdp
from . import angola_ine_gdp
from . import cabo_verde_ine_gdp
from . import mozambique_ine_gdp
from . import guinea_bissau_ine_gdp
from . import zambia_zamstats_gdp
from . import south_sudan_nbs_gdp
from . import sudan_cbos_gdp
from . import benin_insae_gdp
from . import congo_ins_gdp
from . import equatorial_guinea_inege_gdp
from . import djibouti_instad_gdp
from . import eswatini_cso_gdp
from . import gabon_dgs_gdp
from . import car_icasees_gdp

REGISTRY = {
    "statssa_gdp": statssa_gdp.parse,           # GDP (P0441), all four SNA approaches
    "ghana_pxweb_gdp": ghana_pxweb_gdp.parse,   # GDP StatsBank PxWeb (prod+exp, ann+qtr)
    "nbs_nigeria_gdp": nbs_nigeria_gdp.parse,   # GDP quarterly report (production approach)
    "rwanda_nisr_gdp": rwanda_nisr_gdp.parse,   # GDP National Accounts xlsx (prod+exp)
    "mauritius_gdp": mauritius_gdp.parse,       # QNA workbook (GVA + expenditure, ann+qtr)
    "namibia_gdp": namibia_gdp.parse,           # NSA quarterly GDP tables (prod+exp)
    "uganda_ubos_gdp": uganda_ubos_gdp.parse,   # UBOS QGDP current-prices (prod+exp levels, share)
    "morocco_hcp_gdp": morocco_hcp_gdp.parse,   # HCP national-accounts indicators (Google Sheets)
    "botswana_gdp": botswana_gdp.parse,         # Statsbots quarterly GDP report PDF (prod+exp)
    "kenya_knbs_gdp": kenya_knbs_gdp.parse,     # KNBS quarterly GDP report PDF (mirror-reversed)
    "cameroon_ins_gdp": cameroon_ins_gdp.parse, # INS Cameroun quarterly CNT note PDF (prod+exp levels)
    "ci_anstat_gdp": ci_anstat_gdp.parse,       # ANStat CI quarterly CNT PDF (production levels)
    "burkina_insd_gdp": burkina_insd_gdp.parse, # INSD Burkina CNT xlsx (levels/deflator/share/growth)
    "mali_instat_gdp": mali_instat_gdp.parse,   # INSTAT Mali quarterly PIB note PDF (prod+exp levels)
    "zimbabwe_zimstat_gdp": zimbabwe_zimstat_gdp.parse,  # ZimStat quarterly GDP xlsx (ZWG, prod)
    "seychelles_nbs_gdp": seychelles_nbs_gdp.parse,  # NBS Seychelles QNA xlsx (by-industry, stacked)
    "malawi_nso_gdp": malawi_nso_gdp.parse,     # NSO Malawi GDP-by-expenditure xlsx (annual)
    "algeria_ons_gdp": algeria_ons_gdp.parse,   # ONS Algeria comptes economiques PDF (exp+income, annual)
    "niger_ins_gdp": niger_ins_gdp.parse,       # INS Niger CNA PDF (production by branch, annual)
    "chad_inseed_gdp": chad_inseed_gdp.parse,   # INSEED Chad quarterly CNT PDF (production levels+deflator)
    "guinea_ins_gdp": guinea_ins_gdp.parse,     # INS Guinea CNT PDF (real growth + contributions by sector)
    "sierraleone_stats_gdp": sierraleone_stats_gdp.parse,  # Stats SL annual GDP report PDF (prod+exp; drops old-leone 2020 col)
    "gambia_gbos_gdp": gambia_gbos_gdp.parse,     # GBoS annual GDP xlsx x2 (prod+exp; level/growth/deflator/contribution, base 2013)
    "liberia_lisgis_gdp": liberia_lisgis_gdp.parse,  # LISGIS annual GDP xlsx x2 (prod+exp; LRD block only, base 2016)
    # BOS Lesotho QGDP publication tables (ZIP listed in a JS catalogue)
    "lesotho_bos_gdp": lesotho_bos_gdp.parse,
    "saotome_ine_gdp": saotome_ine_gdp.parse,     # INE STP annual GDP xlsx x2 (prod+exp; stacked blocks, value-classified)
    "drc_bcc_gdp": drc_bcc_gdp.parse,             # BCC (central bank) aggregate PIB series xlsx (1959-2020, CDF base 2000)
    "togo_inseed_gdp": togo_inseed_gdp.parse,     # INSEED Togo VAB-by-branch xlsx (production/current, 2007-2015)
    "senegal_ansd_gdp": senegal_ansd_gdp.parse,   # ANSD Senegal base-2021 CN xlsx (3 approaches + by-sector level/constant/growth)
    "mauritania_ansade_gdp": mauritania_ansade_gdp.parse,  # ANSADE Mauritania GDP xlsx x5 (prod+exp; level/growth/contribution, 1998-2022)
    "somalia_snbs_gdp": somalia_snbs_gdp.parse,   # SNBS Somalia GDP CSV x4 (expenditure; level/growth/share/per-capita, USD)
    "comoros_inseed_gdp": comoros_inseed_gdp.parse,  # INSEED Comoros CSV x2 (prod+exp contributions + PIB growth, 2021-2023)
    "madagascar_instat_gdp": madagascar_instat_gdp.parse,  # INSTAT Madagascar TBE xlsx (VAB by branch, annual+qtr, constant+current)
    "libya_cbl_gdp": libya_cbl_gdp.parse,         # CBL Libya bilingual GDP-by-sector PDF (constant/current/deflator, 2013-2019)
    "egypt_cbe_gdp": egypt_cbe_gdp.parse,         # CBE Egypt GDP xlsx x4 (factor-cost+expenditure, quarterly, fiscal->calendar)
    "tunisia_bct_gdp": tunisia_bct_gdp.parse,     # BCT Tunisia GDP+expenditure HTML tables (current, 2017-2022)
    "tanzania_nbs_gdp": tanzania_nbs_gdp.parse,   # NBS Tanzania quarterly GDP xlsx (by activity, constant/current/growth/share, base 2015)
    "ethiopia_nbe_gdp": ethiopia_nbe_gdp.parse,   # NBE Ethiopia annual-report PDF Table 1.1 (real GDP by 3 sectors + growth/share/pc, base 2015/16)
    "burundi_insbu_gdp": burundi_insbu_gdp.parse,  # INSBU Burundi CNT PDF (text-strategy grid; real growth + share by branch, quarterly)
    # INE Angola Contas Nacionais Trimestrais xlsx (POSTed) + the annual workbook
    # (extra_group): production by 16 activities, chained volume SA+NSA, growth,
    # contributions, current levels; annual expenditure/income approaches.
    "angola_ine_gdp": angola_ine_gdp.parse,
    # INE Cabo Verde CNT xlsx (base 2015): production + expenditure, current and
    # chained volume, y/y growth, quarterly and annualised (2024-25 provisional).
    "cabo_verde_ine_gdp": cabo_verde_ine_gdp.parse,
    # INE Mozambique Anuário Estatístico ch.5: GDP by expenditure, current and
    # constant 2019 prices, volume growth, per capita (MT, US$), 2021-2025.
    "mozambique_ine_gdp": mozambique_ine_gdp.parse,
    # INE Guiné-Bissau Síntese das Contas Nacionais 2020 (base 2015): production,
    # expenditure and VAB by sector, current/chained volume, growth, deflators,
    # contributions (2015 rebase column refused).
    "guinea_bissau_ine_gdp": guinea_bissau_ine_gdp.parse,
    # ZamStats QGDP xlsx + annual xlsx: production quarterly+annual, current and
    # constant 2010; expenditure + income annual.
    "zambia_zamstats_gdp": zambia_zamstats_gdp.parse,
    # NBS South Sudan GDP 2021 release: expenditure, current + constant 2009,
    # 2008-2021; GNI, per capita SSP/USD.
    "south_sudan_nbs_gdp": south_sudan_nbs_gdp.parse,
    # CBOS Annual Report 2018 ch.7 reprinting CBS national accounts (CBS site
    # dead): activity constant 1981/82 + current, expenditure, deflator.
    "sudan_cbos_gdp": sudan_cbos_gdp.parse,
    # INSAE/INStaD Benin (Wayback id_ copies of its own workbooks; instad.bj in
    # maintenance): annual 1999-2021 production + expenditure, current and
    # constant 2015, vintage flag per year; quarterly 2018-2021 VA by branch.
    "benin_insae_gdp": benin_insae_gdp.parse,
    # INS Congo quarterly national accounts note (CNT): 20 branches, chained
    # volume (ref 2005) + current levels, real y/y growth, contributions.
    "congo_ins_gdp": congo_ins_gdp.parse,
    # INEGE Equatorial Guinea: quarterly national accounts (Anexos 1-6,
    # 2025-Q1..2026-Q2) + Anuario Estadístico 2026/2023 national accounts
    # (2018-2025, supply and demand) -- 2006 base, newest edition wins.
    "equatorial_guinea_inege_gdp": equatorial_guinea_inege_gdp.parse,
    # INSTAD Djibouti Annuaire statistique ch. 7.2: production and emplois
    # accounts, current and 2013 prices, 2014-2024 (2025 + 2024 editions).
    "djibouti_instad_gdp": djibouti_instad_gdp.parse,
    # CSO Eswatini via Wayback id_ (gov.sz unreachable): QGDP Tables 2013Q1-2025Q4
    # (production, current + constant 2019, SA, shares, y/y growth, contributions)
    # + Rebased GDP Report 2023 annexes (annual production + expenditure, deflators).
    "eswatini_cso_gdp": eswatini_cso_gdp.parse,
    # DGS Gabon Annuaire 2004-2008 via Wayback id_ of stat-gabon.org: expenditure
    # current + constant 2001, contributions/growth, VA by branch, GDP per head.
    "gabon_dgs_gdp": gabon_dgs_gdp.parse,
    # ICASEES CAR Comptes nationaux 2019-2021 (base 2019, SCN 2008, posted 2026):
    # VA by 32 branches current prices + report Tableau 1 aggregates.
    "car_icasees_gdp": car_icasees_gdp.parse,
}
