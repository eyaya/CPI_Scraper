"""Parser registry for PPI sources (generated: one line per parser key)."""
from . import algeria_ons_ppi
from . import angola_ine_ppi
from . import benin_instad_ppi
from . import botswana_statsbots_ppi
from . import burkina_faso_insd_ppi
from . import burundi_insbu_ppi
from . import cameroon_ins_ppi
from . import car_icasees_ppi
from . import chad_inseed_ppi
from . import congo_ins_ppi
from . import cote_divoire_ppi
from . import djibouti_instad_ppi
from . import egypt_capmas_ppi
from . import gambia_gbos_ppi
from . import ghana_pxweb_ppi
from . import guinea_ins_ppi
from . import kenya_knbs_ppi
from . import liberia_lisgis_ppi
from . import malawi_nso_ppi
from . import mali_instat_ppi
from . import mauritius_statsmauritius_ppi
from . import morocco_hcp_ppi
from . import namibia_nsa_ppi
from . import rwanda_nisr_ppi
from . import senegal_ansd_ppi
from . import seychelles_nbs_ppi
from . import sierra_leone_statssl_ppi
from . import south_africa_statssa_ppi
from . import tanzania_nbs_ppi
from . import togo_inseed_ppi
from . import tunisia_ins_ppi
from . import uganda_ubos_ppi
from . import zimbabwe_zimstat_ppi

REGISTRY = {
    "algeria_ons_ppi": algeria_ons_ppi.parse,
    "angola_ine_issues_ppi": angola_ine_ppi.parse_issues,
    "benin_instad_ppi": benin_instad_ppi.parse,
    "botswana_statsbots_ppi": botswana_statsbots_ppi.parse,
    "burkina_faso_insd_ppi": burkina_faso_insd_ppi.parse,
    "burundi_insbu_ippab": burundi_insbu_ppi.parse,
    "cameroon_ins_ppi": cameroon_ins_ppi.parse,
    "car_icasees_ppi": car_icasees_ppi.parse,
    "chad_inseed_ppi": chad_inseed_ppi.parse,
    "congo_ins_ppi": congo_ins_ppi.parse,
    "cote_divoire_anstat_ppi": cote_divoire_ppi.parse_anstat,
    "cote_divoire_ins_ppi": cote_divoire_ppi.parse_ins,
    "djibouti_instad_ppi": djibouti_instad_ppi.parse,
    "egypt_capmas_ppi": egypt_capmas_ppi.parse,
    "gambia_gbos_ppi": gambia_gbos_ppi.parse,
    "ghana_pxweb_ppi": ghana_pxweb_ppi.parse,
    "guinea_ins_ppi": guinea_ins_ppi.parse,
    "kenya_knbs_ppi": kenya_knbs_ppi.parse,
    "liberia_lisgis_ppi": liberia_lisgis_ppi.parse,
    "malawi_nso_annex_ppi": malawi_nso_ppi.parse_annex,
    "malawi_nso_release2016_ppi": malawi_nso_ppi.parse_release_2016,
    "mali_instat_ippi": mali_instat_ppi.parse_ippi,
    "mali_instat_ppi": mali_instat_ppi.parse,
    "mauritius_ppia_esi_ppi": mauritius_statsmauritius_ppi.parse_ppia_esi,
    "mauritius_ppia_hs_ppi": mauritius_statsmauritius_ppi.parse_ppia_hs,
    "mauritius_ppim_esi_ppi": mauritius_statsmauritius_ppi.parse_ppim_esi,
    "mauritius_ppim_hs_ppi": mauritius_statsmauritius_ppi.parse_ppim_hs,
    "morocco_hcp_ppi": morocco_hcp_ppi.parse,
    "namibia_nsa_ppi": namibia_nsa_ppi.parse,
    "namibia_nsa_ppi_dec2015": namibia_nsa_ppi.parse_dec2015,
    "rwanda_nisr_ppi": rwanda_nisr_ppi.parse,
    "senegal_ansd_ippi_note": senegal_ansd_ppi.parse_note,
    "senegal_ansd_ippi_serie": senegal_ansd_ppi.parse_serie,
    "seychelles_nbs_bulletin_ppi": seychelles_nbs_ppi.parse_bulletin,
    "seychelles_nbs_timeseries_ppi": seychelles_nbs_ppi.parse_timeseries,
    "sierra_leone_statssl_ppi": sierra_leone_statssl_ppi.parse,
    "south_africa_statssa_ppi": south_africa_statssa_ppi.parse,
    "tanzania_nbs_ppi": tanzania_nbs_ppi.parse,
    "togo_inseed_ppi": togo_inseed_ppi.parse,
    "tunisia_ins_ppi": tunisia_ins_ppi.parse,
    "uganda_ubos_ppi_hr": uganda_ubos_ppi.parse_hr,
    "uganda_ubos_ppi_m_annual": uganda_ubos_ppi.parse_m_annual,
    "uganda_ubos_ppi_mu": uganda_ubos_ppi.parse_mu,
    "uganda_ubos_ppi_yoy2019": uganda_ubos_ppi.parse_yoy_2019,
    "zimbabwe_zimstat_ppi": zimbabwe_zimstat_ppi.parse,
}
