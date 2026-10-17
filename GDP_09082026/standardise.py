"""Standardised columns for GDP, derived from the published ones.

WHY. The published columns are verbatim on purpose -- `category` is each NSO's
own label in four languages, `series_code` is whatever the office printed (its
own code, a table number, an edition tag, a formula), `base_period` and `unit`
are free text. That is right for provenance and wrong for anything that builds
identifiers from them: the Africa Data Commons app did exactly that (2026-10-15)
and produced variables named "... [Sac6314] (XAF Billion)" and IDs starting with
digits. These columns give such consumers something safe to key on.

RULES OF THE GAME.
* Every column here is a pure function of the published columns, recomputed on
  every write (`core.run` calls `standardise` after merge-on-write), so nothing
  can drift from what the NSO printed, and changing a rule only needs a re-run
  of `python -m tools.standardise gdp`.
* A label that cannot be mapped with confidence gets a BLANK `category_code`,
  never a guess. "Construction" is value added under the production approach
  but capital formation under expenditure; bare "Agriculture" is ISIC section A
  for some offices and crops only for others. Blank means "not yet comparable",
  and consumers should skip those rows for cross-country views.
* A sub-item is never promoted to its parent: "dont ...", "of which ...",
  "Change in stock, Crude Oil" stay blank.

THE COLUMNS (appended after the published ones):
  category_code   SNA concept or ISIC section(s): GDP, FCE_HH, GFCF, EXP, VA_C,
                  VA_DE (a published combination of sections D+E) ... or blank
  category_std    English name of category_code
  price_concept   current | fixed_base | chained | previous_year |
                  constant_unspecified | not_applicable
  base_year       first year of the base/reference period (2006/07 -> 2006), or blank
  currency        ISO 4217 for money values (CFA franc zone taken from iso3), else blank
  unit_multiplier 1, 1e3, 1e6, 1e9 for money values, else blank
  unit_std        currency code | percent | percentage_points | index | blank
  value_std       value x unit_multiplier (base currency units); imports printed
                  negative as a LEVEL or SHARE turned positive. Growth untouched.
  edition         the publication the row comes from, as YYYY or YYYY-Qn when
                  its year can be read off category_group/series_code/source_file
  series_id       safe ID: [A-Z][A-Z0-9_]*, blank when category_code is blank
  is_preferred    True on exactly one row per (series_id, currency, geography,
                  period): the newest edition. Older editions stay, as False.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

STD_COLUMNS = ["category_code", "category_std", "price_concept", "base_year",
               "currency", "unit_multiplier", "unit_std", "value_std", "edition",
               "series_id", "series_name", "is_preferred"]

# ---------------------------------------------------------------- labels ----

def _norm(label: str) -> str:
    """Lower-case, accent-free, numbering/sign/footnote stripped, one space."""
    s = unicodedata.normalize("NFKD", str(label))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("&", " and ").replace("’", "'").replace("_", " ")
    # Numbering first, before de-hyphenation turns "a-Education" into one word:
    # "1. ", "(1) ", "030 ", "a- ", "a-", "A. " (a letter prefix only before a word).
    s = re.sub(r"^[\s.…=+\-−()]*(?:\(?\d+\)?[.)]?\s+|\(\d+\)\s*|[a-z](?:[.)]\s*|-\s*)(?=[a-z]{3}))", "", s)
    s = re.sub(r"(?<=[a-z])-(?=[a-z])", "", s)          # Manufac-turing, Construc-tion
    s = re.sub(r"\[\d+\]|\(\*+\)|\*+", " ", s)            # footnote markers
    s = re.sub(r"\((?:[\d\s+\-=()]|\(\d+\))+\)", " ", s)  # (1+2+3 - 4), (3) + (4)
    s = re.sub(r"^[\s.…=+\-−()]+", "", s)
    s = re.sub(r"\(\s+", "(", s)
    s = re.sub(r"\s+\)", ")", s)
    s = re.sub(r",\s*k?shs? million$|,\s*k?shs?$", "", s)   # Kenya: "..., KSh Million"
    s = re.sub(r"\s+", " ", s).strip(" :;,.-")
    s = re.sub(r"(?:\s*[=+\-−])+$", "", s).strip()          # "PIB = (1) +(2) +(3)" -> "pib"
    return s


# A sub-item of something else, or a mixture of two concepts: never mapped.
_EXCLUDE = re.compile(
    r"^(?:of which|o/w|dont|do qual|incl)\b|\bdont\s*:|\bof which\b|"
    r"\bincl(?:uding|\.)? .*(?:discrepanc|inventor)|discrepanc.* (?:and|incl).*inventor|"
    r"^change in stock, |^(?:exportations|importations): (?!biens|services|exportation de|importation de)|"
    r"\bmarchande?\b|\bzone franche\b|\binformal\b|\bper ?(?:cent|centage)\b(?! change)|"
    r"\bshare of gdp\b|\bmemoire\b|\bihpc\b|\bcorrection territoriale\b")

_NPISH = r"(?:npish|isblsm|isbsl\w*|isblm|isbl|isfl\w*|ipsfl\w*|non[- ]?profit|sem fim lucrativo|isflsh)"
_HH = r"(?:households?|menages?|familias|agregados familiares|hogares)"
_GOV = (r"(?:general government|government|govt|apu|administrations? publiques?|"
        r"administrations publ|administacoes publicas|aministrations publiques|"
        r"administracao publica|administracoes publicas|publique|public|publica|publico|gobierno)")
_PRIV = r"(?:privee?|private|privada|privado|prive)"
_FCE = (r"(?:final consumption expenditures?|despesas? de consumo final|gastos de consumo final|"
        r"final consum\w*|consommation(?:s)? finale|consumo final|consumo total|"
        r"despesas? de consumo|gastos de consumo|depenses? de consommation|\bcf\b|\bfce\b|"
        r"consumption expenditure|consumption)")
_GFCF = (r"(?:(?:gross )?(?:domestic )?fixed capital fo\w*mation|gross fixed capital|fbcf|f\.b\.c\.f|"
         r"formation brute? d[eu] capitale? fixe|formacao bruta de capital fixo|"
         r"formacion bruta de capital fijo|accumulation brute de fonds fixes|gfcf)")
_EXP = r"(?:exports?|exportations?|exportions|exportac\w*|exportaciones|export\b)"
_IMP = r"(?:imports?|importations?|importac\w*|importaciones)"
_GOODS = r"(?:goods|biens|bens|bienes)"
_SERV = r"(?:services?|servicos|servicios)"

# (code, English name, pattern on the normalised label, approaches it may
# apply under -- None = any). FIRST MATCH WINS, so specific before general.
_RULES: list[tuple[str, str, str, set | None]] = [
    # --- aggregates -------------------------------------------------------
    ("GDP_PC", "GDP per capita",
     r"(?:per ?capita|par (?:tete|habitant)|per capita|/ ?capita|/ ?habitant|per cápita).*(?:gdp|pib|domestic product)|"
     r"(?:gdp|pib\w*).*(?:per ?capita|par (?:tete|habitant)|/ ?capita|/ ?habitant|per capita)", None),
    ("GNI_PC", "GNI per capita",
     r"(?:per ?capita|/ ?capita).*(?:gni|national income|pnb)|(?:pnb|gni|national income).*(?:per ?capita|/ ?capita)", None),
    ("GDP_NONOIL", "Non-oil GDP",
     r"^(?:non[- ]?oil gdp|pib hors (?:petrole|hydrocarbures)|produit interieur brut hors hydrocarbures)$", None),
    ("GDP_OIL", "Oil GDP", r"^pib petrol(?:e|ier)$", None),
    ("GDP_NONGOLD", "Non-gold GDP", r"^non[- ]?gold gdp$", None),
    ("GDP_NONAG", "Non-agricultural GDP",
     r"^(?:non[- ]?agricultural gdp|pib hors agriculture|produit interieur brut non agricole)$", None),
    ("GDP_FC", "GDP at factor cost",
     r"(?:gdp|pib|domestic product).*(?:factor cost|cout des facteurs)", None),
    ("GVA", "Gross value added at basic prices (all industries)",
     r"^(?:total )?(?:gross )?value added(?: at basic prices)?(?: \(total\))?$|^valeur ajoutee$|"
     r"^total (?:valeur ajoutee|des valeurs ajoutees|vab)$|^vab$|^valor acrescentado$|"
     r"^all indust(?:ry|ries|\.) at basic prices$|^gdp (?:at )?(?:\d{4} )?(?:constant |current )?basic prices?$|^total: all industries$|^total gross value added$|"
     r"^gva basic price|^gdp basic price|^gdp at basic prices$|^total gross value added|"
     r"^gross value added \(gva\) at basic prices$|^total des branches$|^total activites$",
     None),   # NOT "VA aux couts des facteurs" (factor cost) nor "... marchandes" (market only)
    ("GDP", "Gross domestic product",
     r"^(?:total |overall |real |nominal |the |le )?(?:gdp|pib|gross domestic product|produit interieur brut|"
     # NOT "production interieure brute": ONS Algeria's PIB "par genre
     # d'activite" is a narrower aggregate (1997: 2,423,614 vs GDP 2,780,168).
     r"produto interno bruto|producto interno bruto)"
     r"(?: \((?:gdp|pib|s c n|pm|production|emplois?|optique demande|approche \w+)\))?"
     r"(?:,? ?(?:at |a |aux? |au )?(?:market|purchasers'?|current|constant|mkt|du marche|prix|precios|"
     r"by economic activity|by expenditure|seasonally adjusted|- production|en valeur|en volume|reel|"
     r"real|nominal|total|\w* ?prix (?:courants? )?du marche|growth rate|implicit price deflator|"
     r"(?:\d{4} )?constant).*)?$|"
     r"^(?:taux de croissance (?:reelle |annuel )?du pib|gdp growth rate|crecimiento del pib \w+|"
     r"deflat\w+ du pib|gdp deflator|gdp[pe]|total contribution at market prices?|"
     r"pib (?:\(?en [^)]*\)?|\((?:usd|\d+ fcfa)\))|pib optica de demanda|gdp at purchasers prices by final expeniture categories|"
     r"expenditure on gdp(?: \(total\))?|gdp by expenditure|pib (?:nominal|real|total))$", None),
    ("GNI", "Gross national income",
     r"^(?:gross national income|revenu national brut|le pnb|pnb)(?: at market prices)?$", None),
    ("GNDI", "Gross national disposable income",
     r"gross national disposable income$|^revenu national disponible brut$", None),
    # Two concepts, not one: GSS Ghana prints "Domestic demand" AND "Gross
    # Domestic Expenditure" side by side and they differ by ~10% (2013).
    ("DOM_EXP", "Gross domestic expenditure (absorption)",
     r"^(?:gross )?domestic expenditure$|^gross expenditure domestic$|^gross national expenditure$", None),
    ("DOM_DEMAND", "Domestic demand",
     r"^domestic demand$|^demande interieure(?: totale)?$|^demanda interior final$", None),
    ("TAX_NET_PROD", "Taxes less subsidies on products",
     r"tax\w* (?:less|minus|net of) subsidies|tax\w* products less subsidies|net (?:indirect )?taxes(?: on products)?$|"
     r"taxes? on products \(net of subsidies\)|impots? (?:et taxes )?nets? (?:de subventions )?sur les produits|"
     r"taxes nettes sur les produits|impostos liquidos de subsidios sobre (?:os )?produtos|^impots et taxes nets", None),
    ("TAX_PROD", "Taxes on products",
     r"^(?:taxes|impostos?|impuestos) (?:on |sobre (?:os )?)products?$|^imposto sobre os produtos$|"
     r"^impots et taxes sur les produits$|^impuestos sobre productos$", None),
    ("SUB_PROD", "Subsidies on products",
     r"^(?:less )?subsidies on products$|^subvenciones sobre productos$|^subsidios$", None),
    ("FISIM", "FISIM", r"^(?:fisim|sifim)$", None),
    ("STAT_DISC", "Statistical discrepancy",
     r"^(?:statistical discrepanc(?:y|ies)|discrepancy(?: 1)?|ecart statistique.*|residual.*|"
     r"errors? (?:and|&) omissions)$", None),
    ("OUTPUT", "Output", r"^production de biens et services$", None),
    ("IC", "Intermediate consumption", r"^consommations? intermediaires?$", None),
    # --- income -----------------------------------------------------------
    ("COMP_EMP", "Compensation of employees",
     r"^(?:total economy: )?(?:compensation of employees|remunera(?:tions?|cao) (?:des|de|dos) (?:salaries|empregados))"
     r"(?: \(total\))?$", None),
    ("GOS_MI", "Gross operating surplus and mixed income",
     r"^(?:total economy: )?(?:gross operating surplus ?/ ?mixed income|excedent brut d.exploitation (?:et|/) revenu mixte brut|"
     r"excedente bruto de exploracao/rendimento misto)$", None),
    ("GOS", "Gross operating surplus",
     r"^(?:gross operating surplus|operating surplus, gross)(?: \(total\))?$", None),
    ("NOS", "Net operating surplus", r"^(?:net operating surplus|excedent net exploitation)$", None),
    ("MI", "Mixed income", r"^mixed income(?:, gross)?$", None),
    ("CFC", "Consumption of fixed capital",
     r"^(?:consumption of fixed capital|consommation de fonds fixes)$", None),
    ("TAX_NET_PROD_IMP", "Taxes less subsidies on production and imports",
     r"taxes on production and imports less subsidies|impots nets de subventions sur la production|"
     r"impostos, liquidos de subsidios sobre a producao|impot indirect net de subvention", None),
    ("TAX_PROD_IMP", "Taxes on production and imports",
     r"^(?:taxes on production and imports|impots sur la production et les importations)$", None),
    ("NPI_ROW", "Net primary income from abroad",
     r"^net (?:primary|property) income from abroad$", None),
    # --- expenditure ------------------------------------------------------
    ("NET_EXP", "Net exports of goods and services",
     rf"(?:net {_EXP}|{_EXP} (?:nett?es|liquidas?|netas)|exportacao liquida|solde exterieur|resource balance|"
     rf"balance des biens et services|exports less imports|net foreign transactions|exportation nette)", None),
    ("FCE_HH_NPISH", "Final consumption: households and NPISH",
     rf"{_HH}.*(?:\+|and|et) ?{_NPISH}|households and ngos|autoconsommation et isblsm", None),
    ("FCE_GOV_NPISH", "Final consumption: government and NPISH",
     rf"{_GOV}.*(?:\+|,) ?{_NPISH}|administrations? \+ isblm", None),
    ("FCE_NPISH", "Final consumption: NPISH",
     rf"{_FCE}.*{_NPISH}|{_NPISH}.*{_FCE}|^{_NPISH}$|consumption of private nonprofit bodies|"
     rf"instituicoes sem fim lucrativo", {"expenditure", "aggregate"}),
    ("FCE_PRIV", "Private final consumption (households and NPISH)",
     rf"^(?:{_FCE}:? (?:des? )?{_PRIV}|{_PRIV} (?:final )?{_FCE}|final {_PRIV} consumption|{_FCE} (?:dont )?{_PRIV}|"
     rf"consumo {_PRIV}|consommation {_PRIV}|depense de consommation finale: {_PRIV})$", None),
    ("FCE_HH", "Final consumption: households",
     rf"{_FCE}.*{_HH}|{_HH}.*{_FCE}|^cf_? ?menages$|^consommation finale individuelle des menages$|"
     rf"^private households consumption expenditure$|^hfce(?: \(residual\))?$|^household final consumption$|"
     rf"^despesa de consumo das familias$", None),
    ("FCE_GOV", "Final consumption: general government",
     rf"{_FCE}.*{_GOV}|{_GOV}.*{_FCE}|^(?:gfce|consommation publique|consumo publico|cf_? ?apu)$|"
     rf"despesa de consumo da administracao publica", None),
    ("FCE_COLL", "Collective consumption expenditure", r"^collective consumption(?: expenditure)?$", None),
    ("FCE_IND", "Individual consumption expenditure", r"^individual consumption(?: expenditure)?$", None),
    ("CHG_INV", "Changes in inventories",
     r"^(?:changes? in (?:inventor(?:y|ies)|stocks?)|increase in inventories|variations? (?:des?|in) stocks?|"
     r"variacao de (?:existencias?|estoque)|variacion de existencias)(?: \(cii\))?$", None),
    ("ACQ_VAL", "Acquisitions less disposals of valuables",
     r"^(?!.*capital formation).*(?:objets? (?:de )?valeurs?|valuables|objetos de valor)", None),
    ("GFCF_PRIV", "Gross fixed capital formation: private",
     rf"{_GFCF}.*{_PRIV}|{_PRIV}.*{_GFCF}", None),
    ("GFCF_GOV", "Gross fixed capital formation: government/public",
     rf"{_GFCF}.*{_GOV}|{_GOV}.*{_GFCF}", None),
    ("GFCF", "Gross fixed capital formation",
     rf"^(?:total )?{_GFCF}(?: \(fbcf\))?$|^gross domestic fixed capital formation$", None),
    ("GCF", "Gross capital formation",
     r"^(?:gross )?capital formation$|^gross capital fo\w*mation(?: \(gcf\))?$|^gcf$|"
     r"^formation brute? d[eu] capitale?$|^formacao bruta de capital$|^investissement(?: total)?$|"
     r"^investment$|^investimentos?$|^investissement \(2\+3\)$", {"expenditure", "aggregate"}),
    ("EXP_G", "Exports of goods",
     rf"^{_EXP}(?: \w+)? (?:of |de |des |-? ?){_GOODS}(?: \(?f\.?o\.?b\.?\)?)?$|^{_EXP}: (?:exportation de )?{_GOODS}$|"
     rf"^{_GOODS} \(f\.?o\.?b\)? \({_EXP}\)$|^exports of goods and services: goods$|^{_EXP} biens$|^exportation_biens$|"
     rf"^{_EXP} / {_EXP} des biens$|^export of goods f\.o\.b$", None),
    ("EXP_S", "Exports of services",
     rf"^{_EXP}(?: \w+)? (?:of |de |des |-? ?){_SERV}$|^{_EXP}: (?:exportation de )?{_SERV}$|^{_SERV} \({_EXP}\)$|"
     rf"^exports of goods and services: services$|^exportation_services$|^{_EXP} / {_EXP} des services$", None),
    ("IMP_G", "Imports of goods",
     rf"^{_IMP}(?: \w+)? (?:of |de |des |-? ?){_GOODS}(?: \(?f\.?o\.?b\.?\)?)?$|^{_IMP}: (?:importation de )?{_GOODS}$|"
     rf"^{_GOODS} \(f\.?o\.?b\)? \({_IMP}\)$|^imports of goods and services: goods$|^importation_biens$|"
     rf"^{_IMP} / {_IMP} des biens$|^import of goods f\.o\.b$", None),
    ("IMP_S", "Imports of services",
     rf"^{_IMP}(?: \w+)? (?:of |de |des |-? ?){_SERV}$|^{_IMP}: (?:importation de )?{_SERV}$|^{_SERV} \({_IMP}\)$|"
     rf"^imports of goods and services: services$|^importation_services$|^{_IMP} / {_IMP} des services$", None),
    ("EXP", "Exports of goods and services",
     rf"^(?:total )?{_EXP}(?: of goods (?:and|et) services?| de biens et services| des biens et services| b(?:and|et)s|"
     rf" de bens e servicos| totales| \(fob\))?(?: \(fob\))?(?: ?/ ?pib)?$|^{_EXP} of goods and$|"
     rf"^export of goods and services \(fob\)$", None),
    ("IMP", "Imports of goods and services",
     rf"^(?:less:? |minus:? |\(-\) |- )?(?:total )?{_IMP}(?: of goods (?:and|et) services?| de biens et services|"
     rf" des biens et services| b(?:and|et)s| de bens e servicos| totales)?(?: \(fob\))?(?: \(-\)| \(−\))?(?: ?/ ?pib)?$|"
     rf"^{_IMP} of goods and$|^import of goods and services \(fob\)$", None),
    ("FCE", "Final consumption expenditure",
     rf"^(?:total )?(?:{_FCE}s?|consommation finale(?: globale| \(cf\) ?totale)?|depenses? de consommation finale)$",
     None),
]

# ISIC Rev.4 sections, value added -- PRODUCTION approach only, because the same
# words under expenditure/income mean capital formation or compensation by
# industry. Combined sections are coded as published (VA_DE = D+E together).
_ISIC: list[tuple[str, str, str]] = [
    ("VA_PRIMARY", "Value added: primary sector",
     r"^(?:secteur )?primaire$|^(?:primary (?:sector|industries))$"),
    ("VA_SECONDARY", "Value added: secondary sector",
     r"^(?:secteur )?secondaire$|^(?:secondary (?:sector|industries))$"),
    ("VA_TERTIARY", "Value added: tertiary sector",
     r"^(?:secteur )?tertiaire$|^(?:tertiary (?:sector|industries))$"),
    ("VA_INDUSTRY", "Value added: industry (broad sector, as the office defines it)", r"^(?:industry|industrie)$"),
    ("VA_SERVICES", "Value added: services (broad sector, as the office defines it)", r"^services$"),
    ("VA_A", "Value added: agriculture, forestry and fishing (ISIC A)",
     r"^(?:agriculture|agricultura)[, ]+(?:forestry|sylviculture|silvicultura|fishing|peche|pesca)[, ]+(?:and |et |e )?"
     r"(?:forestry|fishing|fishery|peche|pesca|sylviculture|silvicultura)$|"
     r"^agriculture, irrigation and fishery$|^fishing agriculture, forestry and$"),
    ("VA_A01", "Value added: crop and animal production (ISIC A01)",
     r"^crop and animal production, hunting and related service activities$"),
    ("VA_A02", "Value added: forestry and logging (ISIC A02)",
     r"^(?:forestry(?: and logging)?|sylviculture(?: et (?:exploitation forestiere|chasse))?|silvicultura)$"),
    ("VA_A03", "Value added: fishing and aquaculture (ISIC A03)",
     r"^(?:fishing(?: and aquaculture)?|peche(?: et aquaculture)?|pesca(?: e aquacultura)?)$"),
    ("VA_B", "Value added: mining and quarrying (ISIC B)",
     r"^(?:mining and quarrying|activites extractives|industrias extrativas|extractions?|"
     r"extraction|mines? et carrieres)$"),
    ("VA_B06", "Value added: crude petroleum and natural gas (ISIC B06)",
     r"^(?:crude petroleum and natural gas|extraction des hydrocarbures|oil and gas)$"),
    ("VA_C", "Value added: manufacturing (ISIC C)",
     r"^(?:total )?(?:manufacturing(?: industries)?|activites manufacturieres|industries manufacturieres|"
     r"industrias transformadoras|produtos da industria transformadora)$"),
    ("VA_D", "Value added: electricity, gas, steam and air conditioning (ISIC D)",
     r"^(?:electricity(?: supply)?|electricite|electricity, gas, steam and air conditioning(?: supply)?)$"),
    ("VA_E", "Value added: water supply, sewerage and waste (ISIC E)",
     r"^water supply[;,] sewerage,? waste management and remediation(?: activities)?$|^eau et assainissement$|"
     r"^water and waste management$|^water and sewerage(?:; waste collection)?$|^water(?: supply)?$"),
    ("VA_DE", "Value added: electricity, gas and water (ISIC D+E)",
     r"^(?:electricity,? (?:gas )?and water|water and electricity|electricite ?-? ?eau(?: ?-? ?assainissement)?|"
     r"eletricidade e agua|electricidade e agua|producao de electricidade, agua e saneamento)$"),
    ("VA_F", "Value added: construction (ISIC F)",
     r"^(?:construction|construcao|btp|construction and building|batiments? et travaux publics)$"),
    ("VA_G", "Value added: wholesale and retail trade (ISIC G)",
     r"^(?:wholesale and retail trade(?:[;,] repair of motor ?(?:vehicles?|cycles?)(?: and motor ?cycles)?)?|"
     r"commerce(?: et reparation)?|comercio(?: e reparacao)?|comercio e raparacao de veiculos|trade and repair|"
     r"wholesale and retail trade; repair of motors and motocycles|trade; repair of vehicles, household goods)$"),
    ("VA_H", "Value added: transport and storage (ISIC H)",
     r"^(?:transport(?:ation)? and storage|transports? et entreposage|transportes? e armazenagem|transports?|"
     r"transports? et auxiliaires de transports?)$"),
    ("VA_I", "Value added: accommodation and food service (ISIC I)",
     r"^(?:accommodation and food services?(?: activities)?|accomodation and food services|hotels and restaurants|"
     r"hebergement et restaura\w+|alojamento e restauracao|servico de alojamento e restauracao|"
     r"restaurants and hotels|hotellerie, restauration|hotels, bars et restaurants|accommodation and restaurant)$"),
    ("VA_J", "Value added: information and communication (ISIC J)",
     r"^(?:information and communication|information et (?:tele)?communication|"
     r"actividades de informacao e de comunicacao|atividades? de informacao e de comunicacao|"
     r"technology information and communication)$"),
    ("VA_K", "Value added: financial and insurance activities (ISIC K)",
     r"^(?:financial and insurance(?: activities)?|finance and insurance|activites financieres(?: et d.assurance)?|"
     r"services financiers(?: et assurances)?|banques? et assurances?|intermediacao financeira e de seguros|"
     r"atividades financeiras e de seguros|financial services)$"),
    ("VA_L", "Value added: real estate activities (ISIC L)",
     r"^(?:real estate(?: activities)?|activites immobilieres|atividades imobiliarias|servicos imobiliarios e aluguer)$"),
    ("VA_M", "Value added: professional, scientific and technical (ISIC M)",
     r"^professional, scientific and technical (?:activities|services|act)$|^technical professional, activities scientiifc and$"),
    ("VA_N", "Value added: administrative and support services (ISIC N)",
     r"^administrative and supp?ort services?(?: activities)?$"),
    ("VA_MN", "Value added: professional and administrative services (ISIC M+N)",
     r"^professional, administrative and support service activities$|^business services$|"
     r"^activites (?:scientifiques et de soutien|professionnelles, scientifiques, techniques, services de soutien et de bureau)$|"
     r"^atividades de servicos as empresas$"),
    ("VA_O", "Value added: public administration and defence (ISIC O)",
     r"^public administration(?: and defen[cs]e)?(?:[;:,] (?:compulsory )?social security)?$|^public admi ?nistration$|"
     r"^administration publique$|^administracao publica,? (?:defesa e seguranca social obrigatoria|e seguranca social)$"),
    ("VA_P", "Value added: education (ISIC P)", r"^(?:education|educacao|enseignement)$"),
    ("VA_Q", "Value added: human health and social work (ISIC Q)",
     r"^human health and social (?:work(?: activities)?|services)$|^health and social work$|^work human health and social$|"
     r"^sante et action sociale$|^saude e acao social$|^health$"),
    ("VA_R", "Value added: arts, entertainment and recreation (ISIC R)",
     r"^arts, entertainmen?t and recreation$"),
    ("VA_S", "Value added: other service activities (ISIC S)",
     r"^other (?:personal )?service activities$"),
    ("VA_T", "Value added: households as employers (ISIC T)",
     r"^activities of households as employers"),
    ("VA_GI", "Value added: trade, catering and accommodation (ISIC G+I)",
     r"^trade, catering and accommodation$"),
    ("VA_HJ", "Value added: transport, storage and communication (ISIC H+J)",
     r"^transport, storage and communications?$"),
    ("VA_KLMN", "Value added: finance, real estate and business services (ISIC K-N)",
     r"^finance, real estate and business services$"),
]

_COMPILED = [(c, n, re.compile(p), a) for c, n, p, a in _RULES]
_ISIC_COMPILED = [(c, n, re.compile(p)) for c, n, p in _ISIC]
CODE_NAMES = {c: n for c, n, *_ in _RULES} | {c: n for c, n, _ in _ISIC}


def code_for_label(label: str, approach: str) -> str:
    """The standard concept a published label denotes, or "" when it is
    ambiguous, a sub-item, or not yet covered."""
    if re.match(r"^\s*(?:…|\.{2,})", str(label)):    # Guinea/Cameroon mark SUB-ITEMS with "…"
        return ""
    s = _norm(label)
    if not s or _EXCLUDE.search(s):
        return ""
    for code, _name, rx, approaches in _COMPILED:
        if (approaches is None or approach in approaches) and rx.search(s):
            return code
    if approach == "production":
        for code, _name, rx in _ISIC_COMPILED:
            if rx.search(s):
                return code
    return ""


# ------------------------------------------------------ prices and units ----

_YEAR = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")


def _price(price_basis: str, base_period: str, context: str) -> tuple[str, str]:
    """(price_concept, base_year) from price_basis + base_period, falling back
    on the category/table text for a constant series whose base_period is empty."""
    if price_basis == "current":
        return "current", ""
    if price_basis != "constant":
        y = _YEAR.search(base_period or "")       # deflators/indices: "2015=100"
        return "not_applicable", (y.group(1) if y else "")
    b = _norm(base_period or "")
    if re.search(r"previous year|annee precedente|n-1", b) and not re.search(r"chain", b):
        return "previous_year", ""
    y = _YEAR.search(base_period or "")
    if re.search(r"chain|chaine|encade", b):
        return "chained", (y.group(1) if y else "")
    if y:
        return "fixed_base", y.group(1)
    m = re.search(r"(?:constant|prix|precios|precos)\D{0,25}(19[5-9]\d|20[0-4]\d)|"
                  r"(19[5-9]\d|20[0-4]\d)\D{0,12}(?:constant|prices|prix)", context or "", re.I)
    if m:
        return "fixed_base", m.group(1) or m.group(2)
    return "constant_unspecified", ""


# Currency/scale, editions and safe IDs are shared by every indicator.
from core.standardise_base import edition as _edition  # noqa: E402
from core.standardise_base import edition_rank as _edition_rank  # noqa: E402
from core.standardise_base import safe_id as _safe  # noqa: E402
from core.standardise_base import unit_parts as _unit  # noqa: E402
from core.standardise_base import currency_class, currency_name, join_name, norm, FREQ_NAME  # noqa: E402
from core.standardise_base import drop_conflicts  # noqa: E402


_FREQ = {"annual": "A", "quarterly": "Q", "monthly": "M"}
_MEASURE_NAME = {"level": "level", "growth_yoy": "growth on a year earlier (%)",
                 "growth_qoq": "growth on the previous quarter (%)", "growth_period": "growth over the period (%)",
                 "deflator": "implicit price deflator", "per_capita": "per capita",
                 "share": "share (%)", "contribution": "contribution to growth (percentage points)"}
_SA = {"nsa": "NSA", "saa": "SA", "not_applicable": ""}


# WHERE THE LABEL IS NOT ENOUGH, THE OFFICE'S OWN CODE DECIDES. Stats SA prints
# "Final consumption expenditure" for the total (AN2010), households (AN2011)
# and general government (AN2012), and "Gross capital formation" for the total
# (AN2020), fixed (AN2021) and inventories (AN2022): only series_code tells them
# apart, so a label rule filed household consumption as total consumption (found
# 2026-10-15 by FCE+GCF+EXP-IMP missing GDP by ~80%). AN = current, AR = constant.
_CODE_OVERRIDES: dict[str, list[tuple[re.Pattern, str]]] = {
    "South_Africa": [(re.compile(rf"^A[NR]{n}P?$"), code) for n, code in (
        ("1000", "GDP"), ("2000", "GDP"), ("2001", "STAT_DISC"), ("2010", "FCE"),
        ("2011", "FCE_HH"), ("2012", "FCE_GOV"), ("2020", "GCF"), ("2021", "GFCF"),
        ("2022", "CHG_INV"), ("2030", "DOM_EXP"), ("2040", "EXP"), ("2050", "IMP"))],
}

_IMPORT_CODES = {"IMP", "IMP_G", "IMP_S"}


def _ambiguous(out: pd.DataFrame, s: pd.DataFrame) -> pd.Series:
    """Rows whose label repeats inside ONE table for the same observation with
    DIFFERENT values, told apart only by compact office codes (no spaces): the
    label alone cannot say which concept each is. Editions ("DGS Annuaire
    2004-2008 ...") have spaces and are a different situation."""
    k = ["country", "approach", "category_group", "category", "period", "frequency",
         "measure", "price_basis", "base_period", "seasonal_adjustment", "unit",
         "geography", "source_file"]
    v = pd.to_numeric(out["value"], errors="coerce").round(6)
    compact = ~s["series_code"].str.contains(r"\s") & (s["series_code"] != "")
    nv = v.groupby([s[c] for c in k]).transform("nunique")
    return (nv > 1) & compact


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    """Append STD_COLUMNS to a GDP frame (published columns untouched)."""
    out = df.reset_index(drop=True).copy()
    for c in STD_COLUMNS:             # recomputed from scratch every time
        if c in out.columns:
            out = out.drop(columns=c)
    s = out.fillna("").astype(str)

    # Labels repeat thousands of times; resolve each distinct one once.
    keys = list(zip(s["category"], s["approach"]))
    cache = {k: code_for_label(*k) for k in set(keys)}
    out["category_code"] = [cache[k] for k in keys]
    out.loc[_ambiguous(out, s), "category_code"] = ""
    # A growth-rate LABEL on a row whose measure is "level" is a parser slip
    # (GBoS Gambia "GDP growth rate" stored as a level of -0.0235): no code.
    growth_label = s["category"].map(norm).str.contains(r"growth|croissance|crecimiento|crescimento|taux de|variation annuelle")
    out.loc[growth_label & (s["measure"] == "level"), "category_code"] = ""
    for country, rules in _CODE_OVERRIDES.items():
        here = s["country"] == country
        for rx, code in rules:
            out.loc[here & s["series_code"].str.match(rx), "category_code"] = code
    out["category_std"] = out["category_code"].map(CODE_NAMES).fillna("")

    pk = list(zip(s["price_basis"], s["base_period"], s["category"] + " | " + s["category_group"] + " | " + s["unit"]))
    pc = {k: _price(*k) for k in set(pk)}
    out["price_concept"] = [pc[k][0] for k in pk]
    out["base_year"] = [pc[k][1] for k in pk]

    uk = list(zip(s["unit"], s["iso3"]))
    uc = {k: _unit(*k) for k in set(uk)}
    out["currency"] = [uc[k][0] for k in uk]
    out["unit_multiplier"] = [uc[k][1] for k in uk]
    out["unit_std"] = [uc[k][2] for k in uk]

    # A series_code names an edition only when it is text ("DGS Annuaire
    # 2004-2008 V.1.1.3"); a compact code's digits are not a year (Stats SA's
    # AN2012 is household consumption, not a 2012 edition).
    ed_code = s["series_code"].where(s["series_code"].str.contains(r"\s"), "")
    ek = list(zip(s["category_group"], ed_code, s["source_file"]))
    ec = {k: _edition(*k) for k in set(ek)}
    out["edition"] = [ec[k] for k in ek]

    # value_std: the value in base units (x unit_multiplier) for money, and
    # imports printed NEGATIVE turned positive, so every country's imports
    # compare the same way. A LEVEL or SHARE of imports cannot be negative --
    # the sign is the table's presentation ("- Importations", or Ghana's annual
    # table, whose label carries no minus at all) -- but a growth rate can, so
    # only levels/shares are flipped.
    v = pd.to_numeric(out["value"], errors="coerce")
    mult = pd.to_numeric(out["unit_multiplier"], errors="coerce").fillna(1.0)
    flip = (out["category_code"].isin(_IMPORT_CODES) & (v < 0)
            & s["measure"].isin(["level", "share", "per_capita"]))
    out["value_std"] = (v * mult).where(~flip, -(v * mult))

    sid, sname = [], []
    for code, meas, conc, by, fq, sa, cur, iso in zip(
            out["category_code"], s["measure"], out["price_concept"], out["base_year"],
            s["frequency"], s["seasonal_adjustment"], out["currency"], s["iso3"]):
        if not code:
            sid.append("")
            sname.append("")
            continue
        price = {"current": "CUR", "fixed_base": f"K{by}", "chained": f"CHAIN{by}",
                 "previous_year": "PYP", "constant_unspecified": "K",
                 "not_applicable": ""}[conc]
        unit = currency_class(cur, iso)   # LCU / USD / legacy code (ZWL, SLL)
        parts = ["GDP", code, meas.upper(), price, unit, _FREQ.get(fq, fq.upper()), _SA.get(sa, sa.upper())]
        sid.append(_safe("_".join(p for p in parts if p)))
        sname.append(join_name(
            CODE_NAMES[code], _MEASURE_NAME.get(meas, meas.replace("_", " ")),
            {"current": "current prices", "fixed_base": f"constant {by} prices",
             "chained": f"chained volume, reference {by}" if by else "chained volume",
             "previous_year": "previous-year prices",
             "constant_unspecified": "constant prices, base not stated",
             "not_applicable": ""}[conc],
            currency_name(unit), FREQ_NAME.get(_FREQ.get(fq, ""), fq),
            {"nsa": "not seasonally adjusted", "saa": "seasonally adjusted"}.get(sa, "")))
    out["series_id"] = sid
    out["series_name"] = sname

    # ONE PREFERRED ROW per observation: newest edition, then the longest-
    # running series (more periods = the main table, not a side extract).
    # One table, two values for one series/place/date: no ID (see core).
    drop_conflicts(out, ["country", "series_id", "currency", "geography", "period"],
                   ["source_file", "category_group"])
    out["is_preferred"] = False
    has = out["series_id"] != ""
    if has.any():
        sub = out.loc[has, ["country", "series_id", "currency", "geography", "period", "edition",
                            "category", "category_group", "series_code"]].copy()
        span = sub.groupby(["series_id", "category", "category_group", "series_code"])["period"].transform("nunique")
        sub["_ed"] = sub["edition"].map(_edition_rank)
        sub["_span"] = span
        sub = sub.sort_values(["_ed", "_span", "category_group", "series_code", "category"])
        best = sub.groupby(["country", "series_id", "currency", "geography", "period"]).tail(1).index
        out.loc[best, "is_preferred"] = True
    out = out[[c for c in out.columns if c not in STD_COLUMNS] + STD_COLUMNS]
    return out
