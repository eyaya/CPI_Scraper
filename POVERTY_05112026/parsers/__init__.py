"""Parser registry for monetary-poverty sources.

One module per country (plus `<country>_extra_poverty.py` / per-round modules
for back-series reports): each holds that report's declarative table layout
over the shared engine in `poverty_tables.py` (number and row helpers in
`_common.py`, column vocabularies in `_vocab.py`). One module may serve several
descriptors through several parse functions.

Adding a report: write its parser, register it here, add `sources/<name>.yaml`.
"""
from . import angola_poverty
from . import benin_emicov2006_poverty
from . import benin_emicov_poverty
from . import benin_poverty
from . import botswana_bcwis_poverty
from . import botswana_poverty
from . import burkina_faso_2003_poverty
from . import burkina_faso_2018_poverty
from . import burkina_faso_emc2014_poverty
from . import burkina_faso_poverty
from . import burundi_poverty
from . import cabo_verde_extra_poverty
from . import cabo_verde_poverty
from . import cameroon_poverty
from . import central_african_republic_poverty
from . import chad_ecosit3_poverty
from . import chad_poverty
from . import comoros_eesic2013_poverty
from . import comoros_eim2004_poverty
from . import comoros_poverty
from . import congo_poverty
from . import cote_divoire_env1993_poverty
from . import cote_divoire_env_poverty
from . import cote_divoire_poverty
from . import djibouti_poverty
from . import dr_congo_egiodd2020_poverty
from . import dr_congo_poverty
from . import egypt_poverty
from . import equatorial_guinea_poverty
from . import eswatini_poverty
from . import ethiopia_poverty
from . import gabon_egep2005_poverty
from . import gabon_poverty
from . import gambia_extra_poverty
from . import gambia_poverty
from . import ghana_extra_poverty
from . import ghana_poverty
from . import guinea_bissau_poverty
from . import guinea_poverty
from . import kenya_kihbs_poverty
from . import kenya_poverty
from . import liberia_extra_poverty
from . import liberia_poverty
from . import madagascar_ensomd_poverty
from . import madagascar_epm2001_poverty
from . import madagascar_epm2002_poverty
from . import madagascar_epm2004_poverty
from . import madagascar_epm2005_poverty
from . import madagascar_epm2010_poverty
from . import madagascar_poverty
from . import malawi_poverty
from . import malawi_rounds_poverty
from . import mali_2001_2013_poverty
from . import mali_2018_2019_poverty
from . import mali_emop_poverty
from . import mali_poverty
from . import mauritania_poverty
from . import mauritania_profils_poverty
from . import mauritius_poverty
from . import morocco_hcp_poverty
from . import morocco_poverty
from . import mozambique_poverty
from . import namibia_poverty
from . import namibia_rounds_poverty
from . import niger_back_poverty
from . import niger_poverty
from . import nigeria_extra_poverty
from . import nigeria_poverty
from . import rwanda_eicv_back_poverty
from . import rwanda_poverty
from . import sao_tome_iof2010_poverty
from . import sao_tome_poverty
from . import senegal_2021_poverty
from . import senegal_back_poverty
from . import senegal_poverty
from . import seychelles_poverty
from . import sierra_leone_extra_poverty
from . import sierra_leone_poverty
from . import sierra_leone_profile2014_poverty
from . import somalia_district_poverty
from . import somalia_poverty
from . import south_africa_poverty
from . import south_africa_ptr_back_poverty
from . import south_sudan_county_poverty
from . import south_sudan_poverty
from . import sudan_poverty
from . import tanzania_hbs_back_poverty
from . import tanzania_poverty
from . import togo_carto_poverty
from . import togo_poverty
from . import tunisia_ins_poverty
from . import tunisia_poverty
from . import uganda_poverty
from . import uganda_unhs_back_poverty
from . import uganda_unhs_poverty
from . import zambia_poverty
from . import zambia_rounds_poverty
from . import zimbabwe_2001_poverty
from . import zimbabwe_pices2011_poverty
from . import zimbabwe_poverty
from . import zimbabwe_update_poverty

REGISTRY = {
    "angola_poverty": angola_poverty.parse,
    "benin_emicov2006_poverty": benin_emicov2006_poverty.parse,
    "benin_emicov_2011_poverty": benin_emicov_poverty.parse_2011,
    "benin_emicov_2015_poverty": benin_emicov_poverty.parse_2015,
    "benin_note_2019_poverty": benin_emicov_poverty.parse_2019,
    "benin_poverty": benin_poverty.parse,
    "botswana_bcwis_2009_poverty": botswana_bcwis_poverty.parse,
    "botswana_poverty": botswana_poverty.parse,
    "burkina_faso_2003_poverty": burkina_faso_2003_poverty.parse,
    "burkina_faso_2018_poverty": burkina_faso_2018_poverty.parse,
    "burkina_faso_eicvm_poverty": burkina_faso_2003_poverty.parse_eicvm,
    "burkina_faso_emc2014_poverty": burkina_faso_emc2014_poverty.parse,
    "burkina_faso_poverty": burkina_faso_poverty.parse,
    "burundi_poverty": burundi_poverty.parse,
    "cabo_verde_idrf2001_poverty": cabo_verde_extra_poverty.parse_idrf2001,
    "cabo_verde_poverty": cabo_verde_poverty.parse,
    "cabo_verde_quibb2007_poverty": cabo_verde_extra_poverty.parse_quibb2007,
    "cameroon_poverty": cameroon_poverty.parse,
    "central_african_republic_poverty": central_african_republic_poverty.parse,
    "chad_ecosit3_poverty": chad_ecosit3_poverty.parse,
    "chad_poverty": chad_poverty.parse,
    "comoros_eesic2013_poverty": comoros_eesic2013_poverty.parse,
    "comoros_eim2004_poverty": comoros_eim2004_poverty.parse,
    "comoros_poverty": comoros_poverty.parse,
    "congo_poverty": congo_poverty.parse,
    "cote_divoire_env1993_poverty": cote_divoire_env1993_poverty.parse,
    "cote_divoire_env2002_poverty": cote_divoire_env_poverty.parse_2002,
    "cote_divoire_env2008_poverty": cote_divoire_env_poverty.parse_2008,
    "cote_divoire_env2011_poverty": cote_divoire_env_poverty.parse_2011,
    "cote_divoire_env2015_poverty": cote_divoire_env_poverty.parse_2015,
    "cote_divoire_poverty": cote_divoire_poverty.parse,
    "djibouti_poverty": djibouti_poverty.parse,
    "dr_congo_egiodd2020_poverty": dr_congo_egiodd2020_poverty.parse,
    "dr_congo_poverty": dr_congo_poverty.parse,
    "egypt_poverty": egypt_poverty.parse,
    "equatorial_guinea_poverty": equatorial_guinea_poverty.parse,
    "eswatini_poverty": eswatini_poverty.parse,
    "ethiopia_poverty": ethiopia_poverty.parse,
    "ethiopia_zones_poverty": ethiopia_poverty.parse_zones,
    "gabon_egep2005_poverty": gabon_egep2005_poverty.parse,
    "gabon_poverty": gabon_poverty.parse,
    "gambia_hps1998_poverty": gambia_extra_poverty.parse_hps1998,
    "gambia_ihs2003_poverty": gambia_extra_poverty.parse_ihs2003,
    "gambia_ihs2010_poverty": gambia_extra_poverty.parse_ihs2010,
    "gambia_poverty": gambia_poverty.parse,
    "ghana_glss6_poverty": ghana_extra_poverty.parse_glss6,
    "ghana_map2005_poverty": ghana_extra_poverty.parse_map2005,
    "ghana_map2010_poverty": ghana_extra_poverty.parse_map2010,
    "ghana_poverty": ghana_poverty.parse,
    "ghana_sae2017_poverty": ghana_extra_poverty.parse_sae2017,
    "guinea_bissau_poverty": guinea_bissau_poverty.parse,
    "guinea_poverty": guinea_poverty.parse,
    "kenya_kihbs_2005_constituency_poverty": kenya_kihbs_poverty.parse_constituency,
    "kenya_kihbs_poverty": kenya_kihbs_poverty.parse,
    "kenya_poverty": kenya_poverty.parse,
    "liberia_hies2014_poverty": liberia_extra_poverty.parse,
    "liberia_poverty": liberia_poverty.parse,
    "madagascar_ensomd_poverty": madagascar_ensomd_poverty.parse,
    "madagascar_epm2001_poverty": madagascar_epm2001_poverty.parse,
    "madagascar_epm2002_poverty": madagascar_epm2002_poverty.parse,
    "madagascar_epm2004_poverty": madagascar_epm2004_poverty.parse,
    "madagascar_epm2005_poverty": madagascar_epm2005_poverty.parse,
    "madagascar_epm2010_poverty": madagascar_epm2010_poverty.parse,
    "madagascar_poverty": madagascar_poverty.parse,
    "malawi_ihs2_poverty": malawi_rounds_poverty.parse_ihs2,
    "malawi_ihs4_poverty": malawi_rounds_poverty.parse_ihs4,
    "malawi_poverty": malawi_poverty.parse,
    "mali_2001_2013_poverty": mali_2001_2013_poverty.parse,
    "mali_2018_2019_poverty": mali_2018_2019_poverty.parse,
    "mali_emop_latest_poverty": mali_emop_poverty.parse_latest,
    "mali_emop_poverty": mali_emop_poverty.parse,
    "mali_poverty": mali_poverty.parse,
    "mauritania_2014_poverty": mauritania_poverty.parse_2014,
    "mauritania_annuaire_poverty": mauritania_poverty.parse_annuaire,
    "mauritania_poverty": mauritania_poverty.parse,
    "mauritania_profil1996_poverty": mauritania_profils_poverty.parse_1996,
    "mauritania_profil2000_poverty": mauritania_profils_poverty.parse_2000,
    "mauritania_profil2004_poverty": mauritania_profils_poverty.parse,
    "mauritania_profil2008_poverty": mauritania_profils_poverty.parse_2008,
    "mauritania_tendances_poverty": mauritania_profils_poverty.parse_tendances,
    "mauritius_poverty": mauritius_poverty.parse,
    "morocco_carte2004_poverty": morocco_hcp_poverty.parse_carte2004,
    "morocco_carte2007_poverty": morocco_hcp_poverty.parse_carte2007,
    "morocco_carte2014_poverty": morocco_hcp_poverty.parse_carte2014,
    "morocco_dynamique_poverty": morocco_hcp_poverty.parse_dynamique,
    "morocco_hcp_poverty": morocco_hcp_poverty.parse_indices,
    "morocco_poverty": morocco_poverty.parse,
    "morocco_prosperite_poverty": morocco_hcp_poverty.parse_prosperite,
    "morocco_series_poverty": morocco_hcp_poverty.parse_series,
    "mozambique_poverty": mozambique_poverty.parse,
    "mozambique_terceira_poverty": mozambique_poverty.parse_terceira,
    "namibia_final_2016_poverty": namibia_rounds_poverty.parse_final,
    "namibia_poverty": namibia_poverty.parse,
    "namibia_summary_2009_poverty": namibia_rounds_poverty.parse_summary2009,
    "niger_back_poverty": niger_back_poverty.parse,
    "niger_enbc_poverty": niger_back_poverty.parse_enbc,
    "niger_poverty": niger_poverty.parse,
    "niger_quibb_poverty": niger_back_poverty.parse_quibb,
    "nigeria_hnlss2010_poverty": nigeria_extra_poverty.parse_hnlss2010,
    "nigeria_nlss2004_poverty": nigeria_extra_poverty.parse_profile2004,
    "nigeria_poverty": nigeria_poverty.parse,
    "rwanda_eicv4_poverty": rwanda_eicv_back_poverty.parse,
    "rwanda_eicv5_poverty": rwanda_eicv_back_poverty.parse_eicv5,
    "rwanda_poverty": rwanda_poverty.parse,
    "sao_tome_iof2010_poverty": sao_tome_iof2010_poverty.parse,
    "sao_tome_poverty": sao_tome_poverty.parse,
    "senegal_2021_poverty": senegal_2021_poverty.parse,
    "senegal_esam_poverty": senegal_back_poverty.parse_esam,
    "senegal_esps_poverty": senegal_back_poverty.parse,
    "senegal_poverty": senegal_poverty.parse,
    "seychelles_2018_poverty": seychelles_poverty.parse_2018,
    "seychelles_poverty": seychelles_poverty.parse,
    "sierra_leone_poverty": sierra_leone_poverty.parse,
    "sierra_leone_profile2014_poverty": sierra_leone_profile2014_poverty.parse,
    "sierra_leone_slihs2011_poverty": sierra_leone_extra_poverty.parse,
    "somalia_district_poverty": somalia_district_poverty.parse,
    "somalia_poverty": somalia_poverty.parse,
    "south_africa_poverty": south_africa_poverty.parse,
    "south_africa_ptr2014_poverty": south_africa_ptr_back_poverty.parse_2014,
    "south_africa_ptr2017_poverty": south_africa_ptr_back_poverty.parse_2017,
    "south_sudan_county_poverty": south_sudan_county_poverty.parse,
    "south_sudan_poverty": south_sudan_poverty.parse,
    "sudan_poverty": sudan_poverty.parse,
    "tanzania_hbs2001_poverty": tanzania_hbs_back_poverty.parse,
    "tanzania_hbs2007_poverty": tanzania_hbs_back_poverty.parse_2007,
    "tanzania_hbs2011_poverty": tanzania_hbs_back_poverty.parse_2011,
    "tanzania_poverty": tanzania_poverty.parse,
    "togo_carto_poverty": togo_carto_poverty.parse,
    "togo_poverty": togo_poverty.parse,
    "tunisia_carte2020_poverty": tunisia_ins_poverty.parse_carte2020,
    "tunisia_ins_poverty": tunisia_ins_poverty.parse,
    "tunisia_poverty": tunisia_poverty.parse,
    "tunisia_vol2015_poverty": tunisia_ins_poverty.parse_vol2015,
    "tunisia_web_poverty": tunisia_poverty.parse_web,
    "uganda_poverty": uganda_poverty.parse,
    "uganda_unhs_2002_poverty": uganda_unhs_back_poverty.parse,
    "uganda_unhs_2005_poverty": uganda_unhs_back_poverty.parse_2005,
    "uganda_unhs_2009_poverty": uganda_unhs_back_poverty.parse_2009,
    "uganda_unhs_2012_poverty": uganda_unhs_back_poverty.parse_2012,
    "uganda_unhs_poverty": uganda_unhs_poverty.parse,
    "zambia_1993_poverty": zambia_rounds_poverty.parse_1993,
    "zambia_1996_poverty": zambia_rounds_poverty.parse_1996,
    "zambia_1998_poverty": zambia_rounds_poverty.parse_1998,
    "zambia_2002_poverty": zambia_rounds_poverty.parse_2002,
    "zambia_2010_poverty": zambia_rounds_poverty.parse_2010,
    "zambia_2015_poverty": zambia_rounds_poverty.parse_2015,
    "zambia_poverty": zambia_poverty.parse,
    "zimbabwe_2001_poverty": zimbabwe_2001_poverty.parse,
    "zimbabwe_pices2011_poverty": zimbabwe_pices2011_poverty.parse,
    "zimbabwe_poverty": zimbabwe_poverty.parse,
    "zimbabwe_update_poverty": zimbabwe_update_poverty.parse,
}

LAYOUTS = {
    "angola_poverty": angola_poverty.LAYOUT,
    "benin_emicov2006_poverty": benin_emicov2006_poverty.LAYOUT,
    "benin_emicov_2011_poverty": benin_emicov_poverty.LAYOUT_2011,
    "benin_emicov_2015_poverty": benin_emicov_poverty.LAYOUT,
    "benin_note_2019_poverty": benin_emicov_poverty.LAYOUT_2019,
    "benin_poverty": benin_poverty.LAYOUT,
    "botswana_bcwis_2009_poverty": botswana_bcwis_poverty.LAYOUT,
    "botswana_poverty": botswana_poverty.LAYOUT,
    "burkina_faso_2003_poverty": burkina_faso_2003_poverty.LAYOUT,
    "burkina_faso_2018_poverty": burkina_faso_2018_poverty.LAYOUT,
    "burkina_faso_eicvm_poverty": burkina_faso_2003_poverty.LAYOUT_EICVM,
    "burkina_faso_emc2014_poverty": burkina_faso_emc2014_poverty.LAYOUT,
    "burkina_faso_poverty": burkina_faso_poverty.LAYOUT,
    "burundi_poverty": burundi_poverty.LAYOUT,
    "cabo_verde_idrf2001_poverty": cabo_verde_extra_poverty.LAYOUT_IDRF2001,
    "cabo_verde_poverty": cabo_verde_poverty.LAYOUT,
    "cabo_verde_quibb2007_poverty": cabo_verde_extra_poverty.LAYOUT_QUIBB2007,
    "cameroon_poverty": cameroon_poverty.LAYOUT,
    "central_african_republic_poverty": central_african_republic_poverty.LAYOUT,
    "chad_ecosit3_poverty": chad_ecosit3_poverty.LAYOUT,
    "chad_poverty": chad_poverty.LAYOUT,
    "comoros_eesic2013_poverty": comoros_eesic2013_poverty.LAYOUT,
    "comoros_eim2004_poverty": comoros_eim2004_poverty.LAYOUT,
    "comoros_poverty": comoros_poverty.LAYOUT,
    "congo_poverty": congo_poverty.LAYOUT,
    "cote_divoire_env1993_poverty": cote_divoire_env1993_poverty.LAYOUT,
    "cote_divoire_env2002_poverty": cote_divoire_env_poverty.LAYOUT_2002,
    "cote_divoire_env2008_poverty": cote_divoire_env_poverty.LAYOUT,
    "cote_divoire_env2011_poverty": cote_divoire_env_poverty.LAYOUT_2011,
    "cote_divoire_env2015_poverty": cote_divoire_env_poverty.LAYOUT_2015,
    "cote_divoire_poverty": cote_divoire_poverty.LAYOUT,
    "djibouti_poverty": djibouti_poverty.LAYOUT,
    "dr_congo_egiodd2020_poverty": dr_congo_egiodd2020_poverty.LAYOUT,
    "dr_congo_poverty": dr_congo_poverty.LAYOUT,
    "egypt_poverty": egypt_poverty.LAYOUT,
    "equatorial_guinea_poverty": equatorial_guinea_poverty.LAYOUT,
    "eswatini_poverty": eswatini_poverty.LAYOUT,
    "ethiopia_poverty": ethiopia_poverty.LAYOUT,
    "ethiopia_zones_poverty": ethiopia_poverty.LAYOUT_ZONES,
    "gabon_egep2005_poverty": gabon_egep2005_poverty.LAYOUT,
    "gabon_poverty": gabon_poverty.LAYOUT,
    "gambia_hps1998_poverty": gambia_extra_poverty.LAYOUT_HPS1998,
    "gambia_ihs2003_poverty": gambia_extra_poverty.LAYOUT_IHS2003,
    "gambia_ihs2010_poverty": gambia_extra_poverty.LAYOUT_IHS2010,
    "gambia_poverty": gambia_poverty.LAYOUT,
    "ghana_glss6_poverty": ghana_extra_poverty.LAYOUT_GLSS6,
    "ghana_map2005_poverty": ghana_extra_poverty.LAYOUT_MAP2005,
    "ghana_map2010_poverty": ghana_extra_poverty.LAYOUT_MAP2010,
    "ghana_poverty": ghana_poverty.LAYOUT,
    "ghana_sae2017_poverty": ghana_extra_poverty.LAYOUT_SAE2017,
    "guinea_bissau_poverty": guinea_bissau_poverty.LAYOUT,
    "guinea_poverty": guinea_poverty.LAYOUT,
    "kenya_kihbs_2005_constituency_poverty": kenya_kihbs_poverty.LAYOUT_CONSTITUENCY,
    "kenya_kihbs_poverty": kenya_kihbs_poverty.LAYOUT,
    "kenya_poverty": kenya_poverty.LAYOUT,
    "liberia_hies2014_poverty": liberia_extra_poverty.LAYOUT,
    "liberia_poverty": liberia_poverty.LAYOUT,
    "madagascar_ensomd_poverty": madagascar_ensomd_poverty.LAYOUT,
    "madagascar_epm2001_poverty": madagascar_epm2001_poverty.LAYOUT,
    "madagascar_epm2002_poverty": madagascar_epm2002_poverty.LAYOUT,
    "madagascar_epm2004_poverty": madagascar_epm2004_poverty.LAYOUT,
    "madagascar_epm2005_poverty": madagascar_epm2005_poverty.LAYOUT,
    "madagascar_epm2010_poverty": madagascar_epm2010_poverty.LAYOUT,
    "madagascar_poverty": madagascar_poverty.LAYOUT,
    "malawi_ihs2_poverty": malawi_rounds_poverty.LAYOUT_IHS2,
    "malawi_ihs4_poverty": malawi_rounds_poverty.LAYOUT_IHS4,
    "malawi_poverty": malawi_poverty.LAYOUT,
    "mali_2001_2013_poverty": mali_2001_2013_poverty.LAYOUT,
    "mali_2018_2019_poverty": mali_2018_2019_poverty.LAYOUT,
    "mali_emop_latest_poverty": mali_emop_poverty.LAYOUT,
    "mali_emop_poverty": mali_emop_poverty.LAYOUT,
    "mali_poverty": mali_poverty.LAYOUT,
    "mauritania_2014_poverty": mauritania_poverty.LAYOUT_2014,
    "mauritania_annuaire_poverty": mauritania_poverty.LAYOUT_ANNUAIRE,
    "mauritania_poverty": mauritania_poverty.LAYOUT,
    "mauritania_profil1996_poverty": mauritania_profils_poverty.LAYOUT_1996,
    "mauritania_profil2000_poverty": mauritania_profils_poverty.LAYOUT_2000,
    "mauritania_profil2004_poverty": mauritania_profils_poverty.LAYOUT,
    "mauritania_profil2008_poverty": mauritania_profils_poverty.LAYOUT_2008,
    "mauritania_tendances_poverty": mauritania_profils_poverty.LAYOUT_TENDANCES,
    "mauritius_poverty": mauritius_poverty.LAYOUT,
    "morocco_carte2004_poverty": morocco_hcp_poverty.LAYOUT_CARTE,
    "morocco_carte2007_poverty": morocco_hcp_poverty.LAYOUT_CARTE,
    "morocco_carte2014_poverty": morocco_hcp_poverty.LAYOUT_CARTE,
    "morocco_dynamique_poverty": morocco_hcp_poverty.LAYOUT_DYN,
    "morocco_hcp_poverty": morocco_hcp_poverty.LAYOUT,
    "morocco_poverty": morocco_poverty.LAYOUT,
    "morocco_prosperite_poverty": morocco_hcp_poverty.LAYOUT_PP,
    "morocco_series_poverty": morocco_hcp_poverty.LAYOUT_SERIES,
    "mozambique_poverty": mozambique_poverty.LAYOUT,
    "mozambique_terceira_poverty": mozambique_poverty.LAYOUT_TERCEIRA,
    "namibia_final_2016_poverty": namibia_rounds_poverty.LAYOUT_FINAL,
    "namibia_poverty": namibia_poverty.LAYOUT,
    "namibia_summary_2009_poverty": namibia_rounds_poverty.LAYOUT_SUMMARY,
    "niger_back_poverty": niger_back_poverty.LAYOUT,
    "niger_enbc_poverty": niger_back_poverty.LAYOUT_ENBC,
    "niger_poverty": niger_poverty.LAYOUT,
    "niger_quibb_poverty": niger_back_poverty.LAYOUT_QUIBB,
    "nigeria_hnlss2010_poverty": nigeria_extra_poverty.LAYOUT_HNLSS2010,
    "nigeria_nlss2004_poverty": nigeria_extra_poverty.LAYOUT_PROFILE2004,
    "nigeria_poverty": nigeria_poverty.LAYOUT,
    "rwanda_eicv4_poverty": rwanda_eicv_back_poverty.LAYOUT,
    "rwanda_eicv5_poverty": rwanda_eicv_back_poverty.LAYOUT_EICV5,
    "rwanda_poverty": rwanda_poverty.LAYOUT,
    "sao_tome_iof2010_poverty": sao_tome_iof2010_poverty.LAYOUT,
    "sao_tome_poverty": sao_tome_poverty.LAYOUT,
    "senegal_2021_poverty": senegal_2021_poverty.LAYOUT,
    "senegal_esam_poverty": senegal_back_poverty.LAYOUT_ESAM,
    "senegal_esps_poverty": senegal_back_poverty.LAYOUT,
    "senegal_poverty": senegal_poverty.LAYOUT,
    "seychelles_2018_poverty": seychelles_poverty.LAYOUT_2018,
    "seychelles_poverty": seychelles_poverty.LAYOUT,
    "sierra_leone_poverty": sierra_leone_poverty.LAYOUT,
    "sierra_leone_profile2014_poverty": sierra_leone_profile2014_poverty.LAYOUT,
    "sierra_leone_slihs2011_poverty": sierra_leone_extra_poverty.LAYOUT,
    "somalia_district_poverty": somalia_district_poverty.LAYOUT,
    "somalia_poverty": somalia_poverty.LAYOUT,
    "south_africa_poverty": south_africa_poverty.LAYOUT,
    "south_africa_ptr2014_poverty": south_africa_ptr_back_poverty.LAYOUT_2014,
    "south_africa_ptr2017_poverty": south_africa_ptr_back_poverty.LAYOUT_2017,
    "south_sudan_county_poverty": south_sudan_county_poverty.LAYOUT,
    "south_sudan_poverty": south_sudan_poverty.LAYOUT,
    "sudan_poverty": sudan_poverty.LAYOUT,
    "tanzania_hbs2001_poverty": tanzania_hbs_back_poverty.LAYOUT,
    "tanzania_hbs2007_poverty": tanzania_hbs_back_poverty.LAYOUT_2007,
    "tanzania_hbs2011_poverty": tanzania_hbs_back_poverty.LAYOUT_2011,
    "tanzania_poverty": tanzania_poverty.LAYOUT,
    "togo_carto_poverty": togo_carto_poverty.LAYOUT,
    "togo_poverty": togo_poverty.LAYOUT,
    "tunisia_carte2020_poverty": tunisia_ins_poverty.LAYOUT_CARTE2020,
    "tunisia_ins_poverty": tunisia_ins_poverty.LAYOUT,
    "tunisia_poverty": tunisia_poverty.LAYOUT,
    "tunisia_vol2015_poverty": tunisia_ins_poverty.LAYOUT_VOL2015,
    "tunisia_web_poverty": tunisia_poverty.LAYOUT_WEB,
    "uganda_poverty": uganda_poverty.LAYOUT,
    "uganda_unhs_2002_poverty": uganda_unhs_back_poverty.LAYOUT,
    "uganda_unhs_2005_poverty": uganda_unhs_back_poverty.LAYOUT_2005,
    "uganda_unhs_2009_poverty": uganda_unhs_back_poverty.LAYOUT_2009,
    "uganda_unhs_2012_poverty": uganda_unhs_back_poverty.LAYOUT_2012,
    "uganda_unhs_poverty": uganda_unhs_poverty.LAYOUT,
    "zambia_1993_poverty": zambia_rounds_poverty.LAYOUT_1993,
    "zambia_1996_poverty": zambia_rounds_poverty.LAYOUT_1996,
    "zambia_1998_poverty": zambia_rounds_poverty.LAYOUT_1998,
    "zambia_2002_poverty": zambia_rounds_poverty.LAYOUT_2002,
    "zambia_2010_poverty": zambia_rounds_poverty.LAYOUT_2010,
    "zambia_2015_poverty": zambia_rounds_poverty.LAYOUT_2015,
    "zambia_poverty": zambia_poverty.LAYOUT,
    "zimbabwe_2001_poverty": zimbabwe_2001_poverty.LAYOUT,
    "zimbabwe_pices2011_poverty": zimbabwe_pices2011_poverty.LAYOUT,
    "zimbabwe_poverty": zimbabwe_poverty.LAYOUT,
    "zimbabwe_update_poverty": zimbabwe_update_poverty.LAYOUT,
}
