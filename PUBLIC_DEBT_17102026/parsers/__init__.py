"""Parser registry for public-debt sources."""
from . import ghana_pxweb_debt
from . import guinea_mef_debt
from . import burundi_insbu_debt
from . import djibouti_instad_debt
from . import mauritius_mof_debt
from . import seychelles_mof_debt
from . import angola_ugd_debt
from . import mozambique_mef_debt
from . import comoros_ddp_debt
from . import cote_divoire_dgf_debt
from . import burkina_faso_dgtcp_debt
from . import senegal_ddp_debt
from . import benin_cagd_debt
from . import kenya_cbk_debt
from . import uganda_mofped_debt
from . import tanzania_bot_debt
from . import rwanda_minecofin_debt
from . import ethiopia_mof_debt
from . import somalia_mof_debt
from . import cameroon_caa_debt
from . import drc_dgdp_debt
from . import congo_cca_debt
from . import central_african_republic_ddpe_debt
from . import equatorial_guinea_inege_debt
from . import tunisia_mof_debt
from . import egypt_cbe_debt
from . import sudan_cbos_debt
from . import mauritania_ddp_debt
from . import south_africa_nt_debt
from . import namibia_bon_debt
from . import malawi_rbm_debt
from . import lesotho_cbl_debt
from . import botswana_bob_debt
from . import zambia_boz_debt
from . import eswatini_cbe_debt
from . import zimbabwe_pdmo_debt
from . import nigeria_dmo_debt
from . import ghana_bog_debt
from . import sierra_leone_mof_debt
from . import gambia_mofea_debt
from . import liberia_mfdp_debt
from . import niger_dgdpf_debt
from . import togo_ddpf_debt
from . import guinea_bissau_dgdp_debt
from . import morocco_dtfe_debt
from . import algeria_ba_debt
from . import madagascar_bfm_debt
from . import chad_inseed_debt
from . import mali_instat_debt
from . import gabon_instat_debt
from . import sao_tome_ine_debt
from . import south_sudan_boss_debt
from . import south_sudan_mofp_debt
from . import morocco_datagov_debt
from . import togo_dgtcp_debt
from . import gabon_dgd_debt
from . import car_ddpe_rapport_gestion
from . import chad_dd_debt
from . import comoros_ddp_annual
from . import mali_dgdp_keyfigures

REGISTRY = {
    "ghana_pxweb_debt": ghana_pxweb_debt.parse,  # GSS StatsBank Debt Data (PxWeb Tier-1, by component, monthly)
    # MEF/DNDAPD Guinea 'Bulletin statistique de la dette': central-government
    # stock (total/external/domestic, USD+GNF, shares) 2020-2025, + BCRG workbook.
    "guinea_mef_debt": guinea_mef_debt.parse,
    # INSBU Burundi Annuaire T15.06 (debt by type) + T15.07 (external by sector),
    # FBU million 2012-2024, Ministère des Finances figures.
    "burundi_insbu_debt": burundi_insbu_debt.parse,
    # INSTAD Djibouti Annuaire T6.2.1: external public debt (State direct +
    # guaranteed), FDJ million 2013-2024 across five editions.
    "djibouti_instad_debt": djibouti_instad_debt.parse,
    # MoF Mauritius QPSDS Table 1: BCG / EBU / central / local / general government,
    # public corporations, public sector -- coverage per row; Rs million + % of GDP, 2003-2026Q2.
    "mauritius_mof_debt": mauritius_mof_debt.parse,
    # MoF Seychelles Quarterly Debt Bulletins Q1 2021-Q4 2024: residency, guarantee status,
    # external by creditor/instrument, domestic by instrument; SCR m + % of GDP.
    "seychelles_mof_debt": seychelles_mof_debt.parse,
    # UGD/MINFIN Angola Boletim Estatístico (Squidex CMS asset): government debt USD bn + Kz bn,
    # maturity, currency, debt/GDP; six-quarter window.
    "angola_ugd_debt": angola_ugd_debt.parse,
    # MEF Mozambique Boletim da Dívida Pública: external/domestic/total USD m + MZN m, % of GDP,
    # external by creditor, domestic by instrument.
    "mozambique_mef_debt": mozambique_mef_debt.parse,
    # DDP/MFB Comoros Bulletin statistique: central government debt, external by creditor,
    # domestic by financing type; KMF m (end-2025 + T1 2026).
    "comoros_ddp_debt": comoros_ddp_debt.parse,
    # MFB/DGF Côte d'Ivoire Bulletin statistique de la dette publique (Treasury site):
    # central-government stock total/external/domestic in M USD and Md FCFA + debt/GDP.
    "cote_divoire_dgf_debt": cote_divoire_dgf_debt.parse,
    # MEF/DGTCP Burkina Faso Bulletin statistique de la dette: AC stock (FCFA + USD),
    # dette publique totale, debt/GDP with/without arrears; watermark filtered.
    "burkina_faso_dgtcp_debt": burkina_faso_dgtcp_debt.parse,
    # MFB/DDP Senegal Bulletin statistique (Wayback id_ of sentresor.org, in maintenance):
    # central-government stock by type of interest rate, Md FCFA.
    "senegal_ddp_debt": senegal_ddp_debt.parse,
    # CAGD Benin Bulletin statistique: encours by creditor/instrument as stock,
    # share of total and % of GDP.
    "benin_cagd_debt": benin_cagd_debt.parse,
    # CBK Kenya Public Debt + Domestic Debt by Instrument CSVs (KSh million, monthly from 1999-09).
    "kenya_cbk_debt": kenya_cbk_debt.parse,
    # MoFPED Uganda Annual Debt Statistical Bulletin: Table 1 stocks (USD bn, UGX bn), Table 2 debt % of GDP.
    "uganda_mofped_debt": uganda_mofped_debt.parse,
    # BoT Monthly Economic Review Table A10 National Debt Developments (USD million, 13-month rolling window).
    "tanzania_bot_debt": tanzania_bot_debt.parse,
    # MINECOFIN Rwanda Debt Stock workbook, annual 2011-2025 (PPG, CG external by creditor, domestic, % GDP).
    "rwanda_minecofin_debt": rwanda_minecofin_debt.parse,
    # MoF Ethiopia Public Sector Debt Statistical Bulletin Table 25 (USD million and % of total, CG + SOEs).
    "ethiopia_mof_debt": ethiopia_mof_debt.parse,
    # MoF FGS Somalia Quarterly Public Debt Bulletin Table 1: external debt by creditor (USD million).
    "somalia_mof_debt": somalia_mof_debt.parse,
    # See the module docstring (CEMAC/central round, 2026-10-08).
    "cameroon_caa_debt": cameroon_caa_debt.parse,
    # See the module docstring (CEMAC/central round, 2026-10-08).
    "drc_dgdp_debt": drc_dgdp_debt.parse,
    # See the module docstring (CEMAC/central round, 2026-10-08).
    "congo_cca_debt": congo_cca_debt.parse,
    # See the module docstring (CEMAC/central round, 2026-10-08).
    "central_african_republic_ddpe_debt": central_african_republic_ddpe_debt.parse,
    # See the module docstring (CEMAC/central round, 2026-10-08).
    "equatorial_guinea_inege_debt": equatorial_guinea_inege_debt.parse,
    # MoF Tunisie monthly 'Résultats provisoires' bulletin, Dette publique page: encours total/intérieure/extérieure (MDT), % PIB, % parts; LF/LFR forecasts skipped.
    "tunisia_mof_debt": tunisia_mof_debt.parse,
    # CBE time series: Government block of External Debt by Debtor (US$ mn, quarterly, fiscal->calendar quarters) + Gross Domestic Debt (LE mn, 2004Q3..2020Q2).
    "egypt_cbe_debt": egypt_cbe_debt.parse,
    # CBOS Annual Report 2018 Tables 10-7/10-8: external debt by creditor group (US$ bn), weights, debt/GDP.
    "sudan_cbos_debt": sudan_cbos_debt.parse,
    # MAEF Direction de la Dette Publique quarterly Bulletin Statistique, Tableau 1: total/external/domestic, USD and MRU mn.
    "mauritania_ddp_debt": mauritania_ddp_debt.parse,
    # NT Budget Review statistical annexure T10: national government debt, annual, audited outcomes only.
    "south_africa_nt_debt": south_africa_nt_debt.parse,
    # BoN Total Government Debt xlsx: central government debt + guarantees, quarterly.
    "namibia_bon_debt": namibia_bon_debt.parse,
    # RBM Central Government External Debt xlsx, annual, MWK million.
    "malawi_rbm_debt": malawi_rbm_debt.parse,
    # CBL Quarterly Review 'Public Debt Stock' table, quarterly.
    "lesotho_cbl_debt": lesotho_cbl_debt.parse,
    # BoB BEFS sheet 7.5: central government + guaranteed debt, FY annual then quarterly.
    "botswana_bob_debt": botswana_bob_debt.parse,
    # BoZ Statistics Fortnightly T17/T18: T-bills + GRZ bonds outstanding, monthly (marketable securities only).
    "zambia_boz_debt": zambia_boz_debt.parse,
    # CBE Quarterly Review T4/T5: total public debt, quarterly.
    "eswatini_cbe_debt": eswatini_cbe_debt.parse,
    # ZPDMO Public Debt Report 2023 (Wayback copy): PPG debt, end-Sep 2023.
    "zimbabwe_pdmo_debt": zimbabwe_pdmo_debt.parse,
    # DMO Nigeria quarterly Total Public Debt PDFs, 2012-Q4..2026-Q2: stocks in US$ and N (as printed), % of total; perimeter changes kept in labels.
    "nigeria_dmo_debt": nigeria_dmo_debt.parse,
    # Bank of Ghana Summary of Economic and Financial Data, Public Debt block, monthly 2016-03..2026-07 (USD/GHC bn, % of GDP); coverage per issue footnote. Separate from GSS StatsBank.
    "ghana_bog_debt": ghana_bog_debt.parse,
    # MoF Sierra Leone (PDMD) public debt stock workbook: end-year totals 2021-2025 (Actual only), domestic debt by holder/instrument.
    "sierra_leone_mof_debt": sierra_leone_mof_debt.parse,
    # MoFEA Gambia quarterly Debt Bulletin: portfolio composition (GMD/US$, % total, % GDP), debt-to-GDP comparison, external by creditor/interest.
    "gambia_mofea_debt": gambia_mofea_debt.parse,
    # MFDP Liberia DMU quarterly Public Debt Management Report: PPG debt stock by creditors/holders, US$m, 2024-Q4..2026-Q1.
    "liberia_mfdp_debt": liberia_mfdp_debt.parse,
    # DGDPF Niger Bulletin Statistique sur la Dette Publique, Tableau 1: stocks by type (FCFA milliards), quarter-/year-ends 2020-2025 + % PIB and % total.
    "niger_dgdpf_debt": niger_dgdpf_debt.parse,
    # DDPF Togo Bulletin statistique de la dette de l'Administration centrale (only edition, 2013-2017): T1 stocks USD m + XOF m, T21 debt/GDP.
    "togo_ddpf_debt": togo_ddpf_debt.parse,
    # MF-DGDP Guinea-Bissau Boletim Estatístico da Dívida Pública, Quadro 9: Governo Central Orçamental stocks (total/interna/externa), XOF m + USD m.
    "guinea_bissau_dgdp_debt": guinea_bissau_dgdp_debt.parse,
    # MEF DTFE Morocco 'Chiffres et statistiques' workbooks (Wayback id_ of the live finances.gov.ma files): Treasury + public-enterprise debt quarterly 2007-Q1..2022-Q1, annual 1998-2021 with % of GDP.
    "morocco_dtfe_debt": morocco_dtfe_debt.parse,
    # Banque d'Algérie annual report annex 'Dette publique intérieure de l'Administration Centrale' (source DG Trésor), DZD bn, 2018-2024.
    "algeria_ba_debt": algeria_ba_debt.parse,
    # BFM Madagascar annual report 'Stock total de la dette extérieure publique et de BFM' (source MEF/DDP), by creditor, 2017-2022; unit per edition (SDR / USD).
    "madagascar_bfm_debt": madagascar_bfm_debt.parse,
    # INSEED Chad Annuaire 2024 Tableau 13 (source DG Trésor / Direction de la Dette): public, domestic, external debt as % of GDP, 2023-2024.
    "chad_inseed_debt": chad_inseed_debt.parse,
    # INSTAT Mali yearbook 2024 T80, credited to the DGDP: total/external/domestic stock, FCFA bn, 2020-2024.
    "mali_instat_debt": mali_instat_debt.parse,
    # INSTAT Gabon yearbook 2016-20, Tables V.1.2.1/V.1.2.5, credited to the DGD: direct + guaranteed, % of GDP.
    "gabon_instat_debt": gabon_instat_debt.parse,
    # INE STP 'em Números' T17.1 (MoF debt report): stock by source of financing, USD m, 2013-2017.
    "sao_tome_ine_debt": sao_tome_ine_debt.parse,
    # BoSS Macroeconomic Review Table 6 (MoFP/MoP figures): central-government external debt by creditor, USD m.
    "south_sudan_boss_debt": south_sudan_boss_debt.parse,
    # MoFP Debt Policy & MTDS 2025 Table 3: domestic debt by instrument at end-2022 (external table refused: contradicts itself).
    "south_sudan_mofp_debt": south_sudan_mofp_debt.parse,
    # DTFE annual series via data.gov.ma (Mar-2014 vintage, own series_code): Treasury + public external debt, 1998-2013.
    "morocco_datagov_debt": morocco_datagov_debt.parse,
    # Back-series (depth round, 2026-10-14); see the module docstring.
    "togo_dgtcp_debt": togo_dgtcp_debt.parse,
    # Back-series (depth round, 2026-10-14); see the module docstring.
    "gabon_dgd_debt": gabon_dgd_debt.parse,
    # Back-series (depth round, 2026-10-14); see the module docstring.
    "car_ddpe_rapport_gestion": car_ddpe_rapport_gestion.parse,
    # Back-series (depth round, 2026-10-14); see the module docstring.
    "chad_dd_debt": chad_dd_debt.parse,
    # Back-series (depth round, 2026-10-14); see the module docstring.
    "comoros_ddp_annual": comoros_ddp_annual.parse,
    # Back-series (depth round, 2026-10-14); see the module docstring.
    "mali_dgdp_keyfigures": mali_dgdp_keyfigures.parse,
}
