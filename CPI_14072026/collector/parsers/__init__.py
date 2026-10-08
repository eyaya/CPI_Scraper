"""Parser registry: maps the `parser` id in a source descriptor to a
function `parse(local_path) -> tidy-ish DataFrame`."""
from . import algeria_ons
from . import angola_ine
from . import botswana_stats
from . import gabon_instat
from . import gambia_gbos
from . import burkina_insd
from . import burundi_insbu
from . import cabo_verde_ine
from . import cameroon_ins
from . import car_icasees
from . import cbk_kenya
from . import chad_inseed
from . import ci_anstat
from . import comoros_inseed
from . import congo_ins
from . import djibouti_instad
from . import drc_bcc
from . import egypt_capmas
from . import egypt_cbe
from . import equatorial_guinea_inege
from . import ethiopia_ess
from . import ghana_pxweb
from . import guinea_bissau_ine
from . import guinea_ins
from . import kenya_knbs
from . import lesotho_bos
from . import liberia_lisgis
from . import liberia_lisgis_api
from . import libya_cbl
from . import madagascar_instat
from . import malawi_nso
from . import mali_instat
from . import mauritania_ansade
from . import mauritius_cpi
from . import morocco_hcp
from . import mozambique_bm
from . import namibia_nsa
from . import nbs_nigeria
from . import niger_ins
from . import rwanda_nisr
from . import sao_tome_ine
from . import seychelles_nbs
from . import sierraleone_stats
from . import somalia_snbs
from . import south_sudan_nbs
from . import statssa
from . import sudan_cbos
from . import tanzania_nbs
from . import togo_inseed
from . import tunisia_ins
from . import uganda_ubos
from . import waemu_ihpc
from . import zambia_zamstats
from . import zimbabwe_zimstat

REGISTRY = {
    "statssa_cpi_coicop": statssa.parse,
    "nbs_nigeria_cpi": nbs_nigeria.parse,
    "kenya_knbs_cpi": kenya_knbs.parse,
    "rwanda_nisr_cpi": rwanda_nisr.parse,
    "ghana_pxweb_cpi": ghana_pxweb.parse,
    "egypt_capmas": egypt_capmas.parse,   # primary: CAPMAS (NSO) Excel, urban/rural/total
    "egypt_cbe": egypt_cbe.parse,         # fallback: CBE inflation-note PDF, urban only
    "ubos_uganda_cpi": uganda_ubos.parse,
    "morocco_hcp": morocco_hcp.parse,
    "waemu_ihpc": waemu_ihpc.parse,       # shared: Senegal, Benin, … (UEMOA IHPC Excel)
    "togo_inseed_ihpc": togo_inseed.parse,
    "burkina_insd": burkina_insd.parse,
    "namibia_nsa": namibia_nsa.parse,
    "mali_instat_ihpc": mali_instat.parse,
    "niger_ins_ihpc": niger_ins.parse,
    "mauritius_cpi": mauritius_cpi.parse,
    "zambia_zamstats": zambia_zamstats.parse,
    "sudan_cbos": sudan_cbos.parse,       # CB fallback: CBOS republishes CBS CPI (all-items only)
    "tanzania_nbs": tanzania_nbs.parse,
    "botswana_stats": botswana_stats.parse,
    "tunisia_ins": tunisia_ins.parse,
    "cabo_verde_ine": cabo_verde_ine.parse,
    "cameroon_ins": cameroon_ins.parse,
    "cbk_kenya": cbk_kenya.parse,         # Kenya fallback (CBK headline inflation)
    "algeria_ons": algeria_ons.parse,     # native 8-group nomenclature (not COICOP)
    "sierraleone_stats": sierraleone_stats.parse,
    "lesotho_bos": lesotho_bos.parse,
    "guinea_ins": guinea_ins.parse,
    "guinea_bissau_ine": guinea_bissau_ine.parse,  # glyph-geometry read of the INHPC note
    "madagascar_instat": madagascar_instat.parse,
    "sao_tome_ine": sao_tome_ine.parse,
    "seychelles_nbs": seychelles_nbs.parse,
    "malawi_nso": malawi_nso.parse,
    "congo_ins": congo_ins.parse,
    "car_icasees": car_icasees.parse,
    "angola_ine": angola_ine.parse,
    "zimbabwe_zimstat": zimbabwe_zimstat.parse,
    "liberia_lisgis": liberia_lisgis.parse,
    # LISGIS dataset API (site rebuilt 2026): all-items + 12 divisions from
    # 2006, with the workbooks' own published monthly/annual changes.
    "liberia_lisgis_api": liberia_lisgis_api.parse,
    "mauritania_ansade": mauritania_ansade.parse,
    "chad_inseed": chad_inseed.parse,
    "ci_anstat": ci_anstat.parse,
    "djibouti_instad": djibouti_instad.parse,
    "drc_bcc": drc_bcc.parse,             # PARTIAL: BCC annual all-items (INS-RDC unreachable)
    "ethiopia_ess": ethiopia_ess.parse,   # PARTIAL: General YoY+MoM (divisions are chart-only)
    "burundi_insbu": burundi_insbu.parse,
    "libya_cbl": libya_cbl.parse,         # CB fallback: CBL republishes Census & Stats Dept CPI
    "mozambique_bm": mozambique_bm.parse, # CB fallback: BM republishes INE CPI (NSO Liferay is gated)
    "south_sudan_nbs": south_sudan_nbs.parse,  # PARTIAL: all-items index series + MoM only
    "somalia_snbs": somalia_snbs.parse,   # rates only (index is chart-only) + FMS state breakdown
    "comoros_inseed": comoros_inseed.parse,  # Strapi CMS JSON -> Tableau 1 HTML (Moroni basket)
    "equatorial_guinea_inege": equatorial_guinea_inege.parse,  # index+MoM x national/5 cities
    "gabon_instat": gabon_instat.parse,   # DGS IHPC dashboard API (series + functions + regions)
    "gambia_gbos": gambia_gbos.parse,     # GBoS chained CPI index, COICOP x months (data portal)
}
