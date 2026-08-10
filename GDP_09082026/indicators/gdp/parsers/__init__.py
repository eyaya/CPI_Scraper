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
}
