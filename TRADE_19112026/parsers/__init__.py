"""Parser registry for merchandise-trade sources (generated: one line per parser key)."""
from . import algeria_ons_trade
from . import angola_ine_trade
from . import benin_instad_trade
from . import botswana_statsbots_trade
from . import burkina_faso_insd_trade
from . import burundi_insbu_trade
from . import cabo_verde_ine_trade
from . import cameroon_ins_trade
from . import central_african_republic_icasees_trade
from . import chad_inseed_trade
from . import congo_ins_trade
from . import cote_divoire_ins_trade
from . import djibouti_instad_trade
from . import egypt_capmas_trade
from . import gabon_instat_trade
from . import gambia_gbos_trade
from . import ghana_gss_digest_trade
from . import ghana_pxweb_trade
from . import guinea_bissau_ine_trade
from . import guinea_ins_trade
from . import kenya_knbs_lei_trade
from . import lesotho_bos_trade
from . import liberia_lisgis_trade
from . import libya_bsc_trade
from . import madagascar_instat_trade
from . import malawi_nso_trade
from . import mali_instat_trade
from . import mauritania_ansade_trade
from . import mauritius_statsmauritius_trade
from . import morocco_oc_trade
from . import mozambique_ine_trade
from . import namibia_nsa_trade
from . import niger_ins_trade
from . import nigeria_nbs_pdf_trade
from . import nigeria_nbs_trade
from . import rwanda_nisr_trade
from . import senegal_ansd_trade
from . import seychelles_nbs_trade
from . import sierra_leone_statssl_trade
from . import somalia_snbs_trade
from . import south_africa_sars_trade
from . import south_sudan_nbs_trade
from . import sudan_cbos_trade
from . import tanzania_nbs_trade
from . import togo_inseed_trade
from . import tunisia_ins_trade
from . import zambia_zamstats_trade
from . import zimbabwe_zimstat_trade

REGISTRY = {
    "algeria_ons_trade": algeria_ons_trade.parse,
    "angola_ine_trade": angola_ine_trade.parse,
    "benin_instad_trade": benin_instad_trade.parse,
    "botswana_statsbots_pdf": botswana_statsbots_trade.parse_pdf,
    "botswana_statsbots_trade": botswana_statsbots_trade.parse,
    "burkina_faso_insd_annuaire": burkina_faso_insd_trade.parse_annuaire,
    "burkina_faso_insd_sce": burkina_faso_insd_trade.parse_sce,
    "burundi_insbu_trade": burundi_insbu_trade.parse,
    "cabo_verde_ine_trade": cabo_verde_ine_trade.parse,
    "cameroon_ins_trade": cameroon_ins_trade.parse,
    "central_african_republic_icasees_trade": central_african_republic_icasees_trade.parse,
    "chad_inseed_trade": chad_inseed_trade.parse,
    "congo_ins_trade": congo_ins_trade.parse,
    "cote_divoire_ins_trade": cote_divoire_ins_trade.parse,
    "djibouti_instad_trade": djibouti_instad_trade.parse,
    "egypt_capmas_trade": egypt_capmas_trade.parse,
    "gabon_instat_trade": gabon_instat_trade.parse,
    "gambia_gbos_trade": gambia_gbos_trade.parse,
    "ghana_gss_digest_trade": ghana_gss_digest_trade.parse,
    "ghana_pxweb_trade": ghana_pxweb_trade.parse,
    "guinea_bissau_ine_trade": guinea_bissau_ine_trade.parse,
    "guinea_ins_annual": guinea_ins_trade.parse_annual,
    "guinea_ins_notes": guinea_ins_trade.parse_notes,
    "kenya_knbs_lei": kenya_knbs_lei_trade.parse,
    "lesotho_bos_trade": lesotho_bos_trade.parse,
    "liberia_lisgis_trade": liberia_lisgis_trade.parse,
    "libya_bsc_trade": libya_bsc_trade.parse,
    "madagascar_instat_trade": madagascar_instat_trade.parse,
    "malawi_nso_trade": malawi_nso_trade.parse,
    "mali_instat_trade": mali_instat_trade.parse,
    "mauritania_ansade_trade": mauritania_ansade_trade.parse,
    "mauritius_statsmauritius_trade": mauritius_statsmauritius_trade.parse_historical,
    "mauritius_statsmauritius_trade_monthly": mauritius_statsmauritius_trade.parse_monthly,
    "morocco_oc_trade": morocco_oc_trade.parse,
    "mozambique_ine_trade": mozambique_ine_trade.parse,
    "namibia_nsa_trade": namibia_nsa_trade.parse,
    "niger_ins_trade": niger_ins_trade.parse,
    "nigeria_nbs_pdf_trade": nigeria_nbs_pdf_trade.parse,
    "nigeria_nbs_trade": nigeria_nbs_trade.parse,
    "rwanda_nisr_trade": rwanda_nisr_trade.parse,
    "senegal_ansd_bmsce": senegal_ansd_trade.parse_bmsce,
    "senegal_ansd_hs2_xlsx": senegal_ansd_trade.parse_hs2_xlsx,
    "senegal_ansd_nace": senegal_ansd_trade.parse_nace_all,
    "senegal_ansd_partners_xlsx": senegal_ansd_trade.parse_partners_xlsx,
    "seychelles_nbs_trade": seychelles_nbs_trade.parse,
    "seychelles_nbs_trade_series": seychelles_nbs_trade.parse_series,
    "sierra_leone_statssl_trade": sierra_leone_statssl_trade.parse,
    "somalia_snbs_abstract": somalia_snbs_trade.parse_abstract,
    "somalia_snbs_ff": somalia_snbs_trade.parse_ff,
    "somalia_snbs_qsb": somalia_snbs_trade.parse,
    "south_africa_sars_pdf": south_africa_sars_trade.parse_pdf,
    "south_africa_sars_trade": south_africa_sars_trade.parse,
    "south_sudan_nbs_trade": south_sudan_nbs_trade.parse,
    "sudan_cbos_trade": sudan_cbos_trade.parse,
    "tanzania_nbs_abstract": tanzania_nbs_trade.parse_abstract,
    "tanzania_nbs_fts": tanzania_nbs_trade.parse_fts,
    "tanzania_nbs_hfd": tanzania_nbs_trade.parse_hfd,
    "togo_inseed_trade": togo_inseed_trade.parse,
    "tunisia_ins_trade": tunisia_ins_trade.parse,
    "tunisia_ins_trade_notes": tunisia_ins_trade.parse_notes,
    "zambia_zamstats_trade": zambia_zamstats_trade.parse,
    "zimbabwe_zimstat_trade": zimbabwe_zimstat_trade.parse,
}
