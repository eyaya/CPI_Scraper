"""Parser registry: maps the `parser` id in a source descriptor to a function
`parse(local_path) -> tidy-ish DataFrame` (missing only the constant identity
columns, which run.py fills in from the descriptor)."""
from . import statssa
from . import nbs_nigeria
from . import kenya_knbs
from . import rwanda_nisr
from . import ghana_pxweb
from . import egypt_capmas
from . import egypt_cbe
from . import uganda_ubos
from . import morocco_hcp
from . import waemu_ihpc
from . import togo_inseed
from . import burkina_insd
from . import namibia_nsa
from . import mali_instat
from . import niger_ins
from . import mauritius_cpi
from . import zambia_zamstats
from . import tanzania_nbs
from . import botswana_stats
from . import tunisia_ins
from . import cameroon_ins
from . import cbk_kenya
from . import algeria_ons
from . import sierraleone_stats
from . import lesotho_bos
from . import guinea_ins
from . import madagascar_instat
from . import seychelles_nbs
from . import malawi_nso
from . import congo_ins
from . import car_icasees
from . import angola_ine
from . import zimbabwe_zimstat
from . import liberia_lisgis
from . import mauritania_ansade
from . import chad_inseed
from . import ci_anstat
from . import drc_bcc
from . import ethiopia_ess
from . import burundi_insbu
from . import libya_cbl
from . import mozambique_bm

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
    "tanzania_nbs": tanzania_nbs.parse,
    "botswana_stats": botswana_stats.parse,
    "tunisia_ins": tunisia_ins.parse,
    "cameroon_ins": cameroon_ins.parse,
    "cbk_kenya": cbk_kenya.parse,         # Kenya fallback (CBK headline inflation)
    "algeria_ons": algeria_ons.parse,     # native 8-group nomenclature (not COICOP)
    "sierraleone_stats": sierraleone_stats.parse,
    "lesotho_bos": lesotho_bos.parse,
    "guinea_ins": guinea_ins.parse,
    "madagascar_instat": madagascar_instat.parse,
    "seychelles_nbs": seychelles_nbs.parse,
    "malawi_nso": malawi_nso.parse,
    "congo_ins": congo_ins.parse,
    "car_icasees": car_icasees.parse,
    "angola_ine": angola_ine.parse,
    "zimbabwe_zimstat": zimbabwe_zimstat.parse,
    "liberia_lisgis": liberia_lisgis.parse,
    "mauritania_ansade": mauritania_ansade.parse,
    "chad_inseed": chad_inseed.parse,
    "ci_anstat": ci_anstat.parse,
    "drc_bcc": drc_bcc.parse,             # PARTIAL: BCC annual all-items (INS-RDC unreachable)
    "ethiopia_ess": ethiopia_ess.parse,   # PARTIAL: General YoY+MoM (divisions are chart-only)
    "burundi_insbu": burundi_insbu.parse,
    "libya_cbl": libya_cbl.parse,         # CB fallback: CBL republishes Census & Stats Dept CPI
    "mozambique_bm": mozambique_bm.parse, # CB fallback: BM republishes INE CPI (NSO Liferay is gated)
}
