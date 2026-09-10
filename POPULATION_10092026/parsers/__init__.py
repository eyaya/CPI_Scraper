"""Parser registry: maps the `parser` id in a source descriptor to a
function `parse(local_path) -> tidy-ish DataFrame` for Population sources."""
from . import statssa_population
from . import ghana_pxweb_population
from . import namibia_nsa_population
from . import ubos_population
from . import nbs_tanzania_population
from . import knbs_population
from . import malawi_nso_population
from . import mauritius_population
from . import zimstat_population
from . import statsbots_population
from . import ansd_senegal_population
from . import niger_ins_population
from . import gbos_gambia_population
from . import lisgis_liberia_population
from . import nisr_rwanda_population
from . import ine_angola_population
from . import instat_madagascar_population
from . import burkina_insd_population
from . import inseed_togo_population
from . import icasees_car_population
from . import ine_guineabissau_population
from . import hcp_morocco_population
from . import statssl_population
from . import nbs_seychelles_population
from . import ine_caboverde_population
from . import instad_djibouti_population
from . import ins_tunisia_population
from . import nbs_southsudan_population
from . import zamstats_population
from . import ins_congo_population
from . import snbs_somalia_population
from . import ins_cameroun_population
from . import ess_ethiopia_population
from . import dgs_gabon_population
from . import instad_benin_population
from . import instat_mali_population

REGISTRY = {
    "instat_mali_population": instat_mali_population.parse,  # INSTAT RGPH-5 2022: 20 regions + 21 age bands x sex
    "instad_benin_population": instad_benin_population.parse,  # INStaD workbook: 4 censuses x 109 geographies, counts + density
    "dgs_gabon_population": dgs_gabon_population.parse,  # DGS EGEP II 2017 survey, national age x sex + median age
    "ess_ethiopia_population": ess_ethiopia_population.parse,  # ESS projection, 829 geographies (region/zone/wereda) x sex
    "ins_cameroun_population": ins_cameroun_population.parse,  # INS projections 2016-2025, 13 geographies x sex
    "snbs_somalia_population": snbs_somalia_population.parse,  # SNBS PESS 2014 age x sex + median age by region
    "ins_congo_population": ins_congo_population.parse,  # INS RGPH-5 2023 census, 12 departments + national x sex
    "zamstats_population": zamstats_population.parse,  # ZamStats projections 2023-2047, country + 10 provinces x sex
    "nbs_southsudan_population": nbs_southsudan_population.parse,  # NBS projections 2020-2040, country + 10 states x year x age x sex
    "ins_tunisia_population": ins_tunisia_population.parse,  # INS mid-year estimates 2016-2024, 24 governorates + age bands
    "instad_djibouti_population": instad_djibouti_population.parse,  # INSTAD RGPH-3 2024 census, national + 6 regions x age x sex
    "ine_caboverde_population": ine_caboverde_population.parse,  # INE CV projections 2010-2040, 23 geographies x age x sex
    "statssa_population": statssa_population.parse,   # Stats SA MYPE P0302, provincial by sex x age (2002-2026)
    "ghana_pxweb_population": ghana_pxweb_population.parse,  # GSS StatsBank PHC2021 projections (PxWeb Tier-1), yr x region x age x sex, 2021-2050
    "namibia_nsa_population": namibia_nsa_population.parse,  # NSA NPHC 2023 census: region x sex (T2.2) + national single-year age x sex (T2.5)
    "ubos_population": ubos_population.parse,  # UBOS national projections by 5-yr age & sex (2015-2050)
    "nbs_tanzania_population": nbs_tanzania_population.parse,  # NBS 2022 PHC national age-sex (Tier-3 PDF, Table 3.1)
    "knbs_population": knbs_population.parse,  # KNBS 2019 census Vol III national age-sex (Tier-3 PDF, Table 2.2)
    "malawi_nso_population": malawi_nso_population.parse,  # NSO Malawi 2018 census Series A xlsx (geo x sex A1 + region x age A4)
    "mauritius_population": mauritius_population.parse,  # Statistics Mauritius Demography T13 (age x sex, 1984-2024)
    "zimstat_population": zimstat_population.parse,  # ZimStat 2022 projection report (single-year age x sex, 2022-2042, Tier-3 PDF)
    "statsbots_population": statsbots_population.parse,  # Statsbots 2022 census Vol1 Table 5.4 (age x sex, Tier-3 PDF)
    "ansd_senegal_population": ansd_senegal_population.parse,  # ANSD RGPH-5 2023 Ch1 national age x sex (Tier-3 PDF, word-gap parse)
    "niger_ins_population": niger_ins_population.parse,  # INS Niger RGPH 2012 Tableau A1 national age x sex (Tier-3 PDF)
    "gbos_gambia_population": gbos_gambia_population.parse,  # GBoS 2024 GPHC Table 13 national age x sex (Tier-3 PDF, data portal)
    "lisgis_liberia_population": lisgis_liberia_population.parse,  # LISGIS 2022 census county x sex xlsx
    "nisr_rwanda_population": nisr_rwanda_population.parse,  # NISR RPHC5 2022 Table 3 mid-year age x sex (xls)
    "ine_angola_population": ine_angola_population.parse,  # INE Angola Censo 2024 province x sex + national + broad age (xlsx)
    "instat_madagascar_population": instat_madagascar_population.parse,  # INSTAT RGPH-3 2018 Tableau 69 national age x sex (urban+rural, Tier-3 PDF)
    "burkina_insd_population": burkina_insd_population.parse,  # INSD RGPH-5 2019 Tableau 5 national quinquennal age x sex (ruled table, Tier-3 PDF)
    "inseed_togo_population": inseed_togo_population.parse,  # INSEED RGPH-5 2022 Livret 01 NIVEAU NATIONAL age x sex (ruled table, Tier-3 PDF)
    "icasees_car_population": icasees_car_population.parse,  # ICASEES RGPH-4 projection national age x sex 2022+2023 (HTML table)
    "ine_guineabissau_population": ine_guineabissau_population.parse,  # INE-GB projection Tabela 10 national by-sex 2014-2026 (Tier-3 PDF)
    "hcp_morocco_population": hcp_morocco_population.parse,  # HCP Morocco projection single-year age x sex 2014-2050 (Tier-2 Google Sheet xlsx)
    "statssl_population": statssl_population.parse,  # Stats SL 2015 PHC national by sex (Tier-2 docx; sub-national incomplete)
    "nbs_seychelles_population": nbs_seychelles_population.parse,  # NBS Seychelles mid-year ERP single-year age x sex (Tier-3 PDF Table 3a)
}
