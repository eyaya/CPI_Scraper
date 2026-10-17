"""Standardised columns for LABOUR, derived from the published ones.

Same contract as indicators/gdp/standardise.py: the published columns stay
verbatim (`characteristic` is the NSO's own category, in five languages and
under a dozen national schemes); these columns are APPENDED, derived only from
the published ones, recomputed on every write (core.run calls `standardise`
after merge-on-write), and BLANK whenever the label does not support a
confident answer. Backfill: `py -3 -m tools.standardise labour`.

THE CONCEPT CODE depends on `topic`:
  industry           ISIC Rev.4 section letter A..U, or a combination exactly as
                     published (DE = "Electricity, gas and water", HJ =
                     "Transport, storage and communication", GI, LMN, KLMN);
                     broad sectors BROAD_AGR / BROAD_IND / BROAD_SER and
                     PRIMARY / SECONDARY / TERTIARY as the office defines them
  occupation         ISCO major group ISCO_0..ISCO_9 (ISCO-88 and ISCO-08 major
                     groups share numbers and scope), ISCO_1_2_3-style when the
                     report itself prints the combination
  employment_status  ICSE-93: EES employees, EMP employers, OAW own-account,
                     CFW contributing family workers, COOP producers' co-ops
  sector             institutional: GOV, SOE, PUB (GOV+SOE), PRIV, HH, NGO, INTL
  formality          INFEMP / FORMEMP (jobs) vs INFSEC / FORMSEC / HHSEC (units)
  activity_status    EMP, UNE, OLF, LF
  hours              H<lo>T<hi>, H_LT<n>, H_GE<n>
  every topic        _T total, _U not stated, _X not classifiable

WHAT STAYS BLANK, ON PURPOSE. Residuals ("Other services", "Autres"), mixtures
("Apprenti, aide familiale", "Patron, travailleur indépendant", "Mines et
énergie"), sub-items ("Manufacturing - Sugar", "Agric self-employed without
employees", "Salarié public", Botswana's "Central Government"), truncated
labels (Somalia's "Technicians and assoc" -- completing them is inference),
national socio-professional groups that are not ISCO (Morocco's "Cadres
moyens", "Ouvrier qualifié"), and words whose scope varies by office: bare
"Transport" (H in Madagascar, H+J in Stats SA's QLFS), bare "Finance" (K-N in
QLFS), "Self-employed". Bare "Agriculture" is BROAD_AGR only in a table that
does not also list fishing/forestry/livestock separately -- otherwise it is a
part of section A and stays blank. South Africa's occupation "Elementary"
excludes the domestic workers the same table lists separately, so it is not
ISCO 9 and stays blank.

OTHER COLUMNS: sex_code (M/F/_T), age_code (SDMX bands from core), geography_level,
unit_std / unit_multiplier / value_std (thousand_persons x 1000), edition,
series_id, is_preferred. Education is NOT standardised (48 national level
names with no shared scheme): rows broken down by education get no series_id,
so they never compete for is_preferred with the education totals.

is_preferred: one True per (country, series_id, geography, locality,
locality_label, period) -- locality_label is in the key because Egypt and
Sudan publish several "other" strata (Urban Frontier Gov., Nomad ...).
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

from core.standardise_base import drop_conflicts
from core.standardise_base import (age_code, drop_std, edition, edition_rank, finish,
                                   geography_level, mark_preferred, norm, safe_id,
                                   locality_token, textual, unit_parts,
                                   age_name, join_name, locality_name, sex_name)

STD_COLUMNS = ["category_code", "category_std", "sex_code", "age_code",
               "geography_level", "unit_std", "unit_multiplier", "value_std",
               "edition", "series_id", "series_name", "is_preferred"]

# ------------------------------------------------------------ normalising ---

_TOTAL = re.compile(r"^(?:total|all activities|all occupations|all units|ensemble|todos|"
                    r"total geral|toutes branches|all industries)$")
_UNKNOWN = re.compile(r"^(?:not stated|not reported|non declares?|nd|n\.d|ns/nr|desconhecido|"
                      r"nao declarado|non determine|don.t know|occupation not stated)$")
_NEC = re.compile(r"^(?:not elsewhere classified|non classe ailleurs|not classified|"
                  r"otro: no clasificados en otra parte|lndividuals can not be classified|"
                  r"individuals can not be classified|activites mal designees|"
                  r"activities incomplete characterization|non classable par activite economique|"
                  r"workers not (?:classifiable|classified) by status|workers not elsewhere classified|"
                  r"travailleurs non classes par le statut|nao classificadas noutras categorias)$")
# A letter section prefix as printed by Liberia / Seychelles: "A - ", "A. ", "P – "
_LETTER = re.compile(r"^([a-ux])\s*[.\-–:]\s+(?=\S)")


def _fold(pattern: str) -> re.Pattern:
    """Compile a rule under the SAME folding norm() applies to labels: NFKD
    also strips Arabic hamza/madda marks, so a pattern typed with them would
    never match the folded label ("الأخصائيين")."""
    p = unicodedata.normalize("NFKD", pattern)
    return re.compile("".join(c for c in p if not unicodedata.combining(c)))


def _clean(label: str) -> str:
    s = norm(label).replace(",", ", ")              # Sudan prints "Arts,entertainment"
    s = re.sub(r"\s*\((?:working population|nsic [a-z\s-]+)\)\s*$", "", s)
    s = re.sub(r"\s*(?:…|\.\.\.+|etc\.?)\s*$", "", s)
    s = re.sub(r"^(?:\d{1,2}|[ivx]+)\s*[:\-–.]\s+", "", s)        # "6 - ", "VII: "
    s = re.sub(r"\s+", " ", s).strip(" .;:,*")
    return s


_SUB = re.compile(r"^(?:of which|o/w|dont|do qual|incl)\b|\bof which\b|\bdont\b|\s-\s")

# ----------------------------------------------------------------- industry ---

_ISIC: list[tuple[str, str]] = [
    # combinations first (exactly as published), then single sections
    ("DE", r"^(?:electricity,? (?:gas )?(?:and|&) water|electricity and water|water and electricity|"
           r"eau, gaz et electricite|production et distribution d'electricite,? de gaz et d'eau|"
           r"electricite,? gaz et eau|utilities)$"),
    ("HJ", r"^transports?,? (?:storage |entrepots )?(?:and|et|e|&) (?:tele)?communications?$|"
           r"^transport,? (?:storage|entrepots) (?:and|et|&) communications?$|"
           r"^transports, activites auxiliaires de transport et communication$|"
           r"^transporte e comunicacoes$|^transports et communications?$"),
    ("GI", r"^trade$|^wholesale (?:and|&) retail trade,? ?restaurants (?:and|&) hotels$|"
           r"^trade, catering and accommodation$"),
    ("LMN", r"^real estate, renting and business activities$|"
            r"^immobiliers?,? locations? et services aux entreprises$"),
    ("KLMN", r"^financ\w*,? insurance, real estate (?:and|&) business services$|"
             r"^finance, real estate and business services$"),
    ("A", r"^(?:agri\w*|agro)[ ,]*(?:\w+[ ,]+){0,6}(?:fish\w*|peche|pesca)(?: and forestry| et sylviculture)?$|^الزراعه وصيد الاسماك$"),
    ("A02", r"^(?:forestry(?: and logging)?|sylviculture(?:,? (?:et )?exploitation forestiere)?|"
            r"silvicultura e exploracao florestal)$"),
    ("A03", r"^(?:fishing(?: and aquaculture)?|peche(?:,? (?:et )?(?:pisciculture et )?aquaculture)?|"
            r"pesca(?: e aquacultura)?|pe?che, pisciculture et aquaculture)$"),
    ("B", r"^(?:mining(?: (?:and|&),? quarrying|, quarrying)?|activites? extractives?|activites d'extraction|"
          r"industries? extracti\w+|industrias extrativas|extraction|mining and extractive industries|"
          r"mineracao e extracao de pedreiras|actividades extractivas|extracao de minas|"
          r"mines et carrieres|التعدين واستغلال المحاجر|indust\. extr)$"),
    ("C", r"^(?:manufactur\w*|manufacture|(?:les )?industries? manufacturieres?|activites (?:de fabrication|"
          r"manufacturieres)|industria transformadora|industrias? transformadoras?|industria manufacturera|"
          r"industries de transformation|fabrication|industria manufatureira|manufacturing industries|"
          r"الصناعات التحويلية|الصناعه التحويلية)$"),
    ("D", r"^(?:electric\w*|eletric\w*)[, ]+(?:gas|gaz|gas,|gás)\b(?!.*(?:\bwater\b|\beau\b|\bagua\b(?! quente)|sewer|assainis)).*$|"
          r"^production,? (?:vente )?et distribution d'electricite,? (?:et |de )?(?:de )?gaz(?:,? de vapeur et climatisation)?$|"
          r"^generacion, transmision y distribucion de electricidad y gas$|^electricity(?: supply)?$|^electricite$|"
          r"^امدادات الكهرباء والغاز والبخار وتكييف الهواء$|^eletricidade, gas, vapor e ar condicionado$"),
    ("E", r"^water supply[;:,'& ]+(?:sewerage|waste)|^water supply,? ?(?:and|&) waste management$|"
          r"^(?:production et )?distribution d'eau\b|^captacao, tratamento e distribuicao de agua|"
          r"^abastecimento de agua|^suministro de agua|^eau et assainissement$|^water and sewerage|"
          r"^امدادات المياه"),
    ("F", r"^(?:construction|construcao(?: civil)?|construccion|btp|b\.t\.p|batiments? et trav\w* publics|"
          r"construction et (?:btp|travaux publics)|construction des batiments et genie civil|"
          r"construction \(btp°?|construction \(btp\)|التشييد والبناء)$"),
    ("G", r"^(?:wholesale (?:and|&) retail(?: ?trade)?[;,:]? ?(?:repair|sale)?.*|whole ?sale (?:and|&) retail trade|"
          r"commerce(?:,? (?:et )?reparation.*| de gros et de detail.*)?|comercio(?:,? reparacao de automoveis e motociclos| e reparacao)?|"
          r"comercio por grosso e a retalho.*|تجارة الجملة والتجزئة.*|wholesale (?:and|&) retail)$"),
    ("H", r"^(?:transport(?:ation(?:al)?)? (?:and|&) storage|transports? et entreposage|transporte e armazenagem|"
          r"transportes e armazenagem|transporte y almacenamiento|النقل والتخزين)$"),
    ("I", r"^(?:accommodation (?:and|&) food services?(?: activities| activity)?|accommodation and food servics activities|"
          r"hotels? (?:and|et|&) restaurants?|restaurants? (?:and|&) hotels|hebergement et restaura\w+|"
          r"hotels?,? bars et restaurants|hotel et restauration|restaurant/hotel|activites d'hebergement et de restauration|"
          r"alojamento e (?:restauracao|alimentacao)(?: \(restaurantes e similares\))?|hoteles y restaurantes|"
          r"انشطة الاقامة والخدمات الغذائية)$"),
    ("J", r"^(?:information (?:and|&|et) communicat\w*|atividades? de informacao e comunicacao|"
          r"informacao e comunicacao|informacion y comunicaciones|technology information and communication|"
          r"تكنولوجيا المعلومات والاتصالات)$"),
    ("K", r"^(?:financ\w* (?:and|&) insurance(?: activit\w*)?|finacial and insurance activities|"
          r"activites financieres(?: et d.assurances?)?|banques? et ass+urances?|actividades financieras y de seguros|"
          r"atividades financeiras e (?:de )?seguros|actividades financeiras(?: e de seguros)?|"
          r"financial intermediation|الأنشطة المالية وانشطة التأمين)$"),
    ("L", r"^(?:real estate(?:,? ?-? ?activities)?|activites immobilieres|atividades imobiliarias|"
          r"actividades imobiliarias|actividades inmobiliarias|الانشطة العقارية)$"),
    ("M", r"^(?:prof\w*,? scientific,? (?:and |&)?technical(?: activities| act)?|technical professional, activities scientiifc|"
          r"activites (?:professionnelles, scientifiques,? (?:et )?techniques|specialisees, scientifiques et techniques)|"
          r"actividades profissionais, cientificas e tecnicas|actividades especializadas cientificas y tecnicas|"
          r"atividades de consultoria cientificas e tecnicas|الانشطة المهنية والعلمية والتقنية)$"),
    ("N", r"^(?:admi\w* (?:and|&) supp?ort(?: service)?(?: activities)?|"
          r"activites de services administratifs et d.appui|activites de (?:services de )?soutien et de bureau|"
          r"atividades administrativas e dos servicos de apoio|servicos administrativos e de apoio|"
          r"actividades de oficina y servicios de apoyo|انشطة الخدمات الإدارية وخدمات الدعم)$"),
    ("O", r"^(?:public admi\w*(?: (?:and|&) defen[cs]e)?(?:[;:/, ]+(?:compulsory )?social security| ?compulsory social security)?|"
          r"administration publique(?:,? (?:et )?defense,? (?:et )?(?:;? ?)?securite sociale(?: obligatoire)?)?|"
          r"administration publique et defense ; securite sociale obligatoire|"
          r"administracao publica,? (?:e )?defesa,? (?:e )?seguranca social(?: obrigatoria)?|"
          r"actividades administrativas publica e defesa e seguranca social|activites d.administration publique|"
          r"actividades de la administracion publica|administracao publica e defesa|"
          r"الادارة العامة والدفاع والضمان الاجتماعي الالزامي)$"),
    ("P", r"^(?:education|educacao|enseignement|ensenanza|التعليم)$"),
    ("Q", r"^(?:human health (?:and|&|,) social work(?: activit\w+)?|health (?:and|&) social work|"
          r"sante et (?:activites d.)?action sociale|activites (?:pour la sante humaine,? (?:et )?l?.?action sociale|"
          r"de sante et d.action sociale)|saude humana e (?:accao|assistencia) social|"
          r"actividades de saude humana e accao social|actividades de atencion a la salud humana y de asistencia social|"
          r"saude e accao social|انشطة صحة الانسان والعمل الاجتماعي)$"),
    ("R", r"^(?:arts,? entertainmen?t,? (?:and )?recreation|arts entertainment and recreation|arts, entertainment|"
          r"arts, spectacles et loisirs|atividades artisticas, desportivas e recreativas|activites artistiques, sportives et recreatives|"
          r"artes, entretenimento e recreacao|actividades artisticas, deportivas y recreativas|انشطة الفنون والترفيه والتسلية)$"),
    ("S", r"^(?:other service activities|autres activites de services(?: n\.c\.a)?|outras actividades de servicos|"
          r"otras actividades de servicio n\.c\.a|انشطة الخدمات الاخري)$"),
    ("T", r"^(?:activities of (?:private )?households as employ\w+.*|households as employers|private households|"
          r"activites des menages (?:prives employant du personnel domestique|en tant qu.employeurs de personnels? domestiques?)|"
          r"actividades das familias como empregadas|familias empregadores de domesticos|actividades especiales de los hogares|"
          r"activites speciales des menages|activite des menages|household production for own use/domestic personnel|"
          r"activities of employer hhlds|انشطة الاسر المعيشية.*)$"),
    ("U", r"^(?:activities of extraterritorial organi[sz]ations?(?: and bodies)?|activities of extraterritorial organization bodies|"
          r"international organizations|activites des organisations (?:et organismes )?extra ?territori\w+|"
          r"activite des organisation extraterritoriale|extraterritorialite|actividades de organizaciones extraterritoriales)$"),
    ("PRIMARY", r"^(?:secteur )?primaire$|^primario$|^primary(?: sector)?$"),
    ("SECONDARY", r"^(?:secteur )?secondaire$|^secundario$|^secondary(?: sector)?$"),
    ("TERTIARY", r"^(?:secteur )?tertiaire$|^terciario$|^tertiary(?: sector)?$"),
    ("BROAD_IND", r"^(?:industry|industrie)$"),
    ("BROAD_SER", r"^services?$"),
]
_ISIC_C = [(c, _fold(p)) for c, p in _ISIC]
_AGRI_ONLY = re.compile(r"^(?:agriculture|agricultura)$")
_AGRI_PARTS = re.compile(r"\b(?:fish\w*|peche|pesca|forest\w*|sylvicult\w*|silvicult\w*|livestock|elevage|"
                         r"crops?|animal production|producao animal|pecuaria)\b")

_SECTION_NAMES = {
    "A": "Agriculture, forestry and fishing", "A02": "Forestry and logging",
    "A03": "Fishing and aquaculture", "B": "Mining and quarrying", "C": "Manufacturing",
    "D": "Electricity, gas, steam and air conditioning supply",
    "E": "Water supply; sewerage, waste management and remediation", "F": "Construction",
    "G": "Wholesale and retail trade; repair of motor vehicles", "H": "Transportation and storage",
    "I": "Accommodation and food service activities", "J": "Information and communication",
    "K": "Financial and insurance activities", "L": "Real estate activities",
    "M": "Professional, scientific and technical activities",
    "N": "Administrative and support service activities",
    "O": "Public administration and defence; compulsory social security", "P": "Education",
    "Q": "Human health and social work activities", "R": "Arts, entertainment and recreation",
    "S": "Other service activities", "T": "Activities of households as employers",
    "U": "Activities of extraterritorial organizations",
    "DE": "Electricity, gas and water (ISIC D+E, as published)",
    "HJ": "Transport, storage and communication (ISIC H+J, as published)",
    "GI": "Trade, restaurants and hotels (ISIC G+I, as published)",
    "LMN": "Real estate, renting and business activities (ISIC L-N, as published)",
    "KLMN": "Finance, real estate and business services (ISIC K-N, as published)",
    "PRIMARY": "Primary sector (as the office defines it)",
    "SECONDARY": "Secondary sector (as the office defines it)",
    "TERTIARY": "Tertiary sector (as the office defines it)",
    "BROAD_AGR": "Agriculture (broad sector, as the office defines it)",
    "BROAD_IND": "Industry (broad sector, as the office defines it)",
    "BROAD_SER": "Services (broad sector, as the office defines it)",
}


def _industry(s: str, raw: str, classification: str) -> str:
    m = _LETTER.match(s)
    if m and classification.startswith("ISIC"):
        letter = m.group(1).upper()
        return "_X" if letter == "X" else letter
    for code, rx in _ISIC_C:
        if rx.search(s):
            return code
    return ""


# --------------------------------------------------------------- occupation ---

_ISCO: list[tuple[str, str]] = [
    ("ISCO_1", r"^(?:managers?|mangers|legislators,? (?:senior officials|administrators) and managers|"
               r"legislators senior officials and managers|"
               r"directeurs,? cadres de direction et gerants?(?:,? membres? de l.executif et des corps legislatifs)?|"
               r"directeurs cadres de direction et gerant membre de l.executif et des corps legislatifs|"
               r"directores y gerentes|representantes poderes legislativos e executivos, diretores e gestores executivos|"
               r"membros do poder executivo e dos corpos legislativos, quadros superiores de administracao publica, "
               r"dirigentes e quadros superiores de empresas)$"),
    ("ISCO_2", r"^(?:professionals?|professions? intellectuelles? et scientifiques?|profession intellectuelle et scientifique|"
               r"especialistas (?:de|das) (?:atividades|profissoes) intel\w+ e ci\w*ntificas|"
               r"profesionales universitarios, cientificos e intelectuales)$"),
    ("ISCO_3", r"^(?:technicians?(?: (?:and|&) associate prof\w*\.?)?|techicians and associate professionals|"
               r"professions? intermediaires?|profession intermediaire|tecnicos e profissionais de nivel intermedio|"
               r"tecnicos y profesionales no universitarios|الفنيون ومساعدو الأخصائيين)$"),
    ("ISCO_4", r"^(?:clerical support(?: workers?| services)?|clerks?|employes de type administratif|"
               r"pessoal administrativo(?: e similar)?|empleados de oficina/personal de apoyo administrativo|"
               r"personnel administrati\w+ ou assimile)$"),
    ("ISCO_5", r"^(?:services? ?(?:and|&|/) ?sales(?: workers?)?|sales and services|"
               r"service workers,? (?:and )?shop (?:and market )?sales workers|service workers and shop and market sales workers|"
               r"personnel des services directs aux particuliers,? commercants et vendeurs|"
               r"pessoal dos servicos pessoais, de prote\w+ e seguros e vendas|pessoal de servicos e vendedores|"
               r"trabajadores de los servicios y vendedores de comercios y mercados|personnel de service et vendeurs)$"),
    ("ISCO_6", r"^(?:skilled agric\w*\.?,? (?:(?:and|&) )?(?:forestry,? )?(?:(?:and|&) )?(?:fishery|fisheries)(?: workers)?|"
               r"skilled agric\w*(?: workers)?|skilled agricultural,? forestry,? (?:and |& )?fisher(?:y|ies)(?: workers)?|"
               r"agricultores e trabalhadores qualificados da agricultura.*|"
               r"agriculteurs et ouvriers qualifies de l.agriculture,? de la sylviculture et de la peche|"
               r"agricultores y trabajadores independientes agropecuarios, forestales y pesqueros)$"),
    ("ISCO_7", r"^(?:craft (?:and|&) (?:related|other) trades?(?: workers)?|craft (?:and|&) related(?: workers)?|"
               r"metiers qualifies de l.industrie et de l.artisanat|operarios, artifices e trabalhadores similares|"
               r"oficiales, operarios y artesanos de .*)$"),
    ("ISCO_8", r"^(?:plant ?(?:/|and|&) ?machine operators?(?:,? ?(?:and|&) assemblers)?|"
               r"conducteurs d.installations et de machines,? et ouvriers de l.assemblage|"
               r"operadores de instala\w+ e maquinas e trabalhadores (?:da montagem|similares)|"
               r"operadores de instalaciones, de maquinas y ensambladores|"
               r"operateurs d.installations et de machines et assembleurs|conducteurs d.installations et de machines)$"),
    ("ISCO_9", r"^(?:elementary(?: occupations?| occupation workers)?|professions elementaires|profissoes elementares|"
               r"trabajadores no cualificados/ocupaciones elementales|trabalhadores nao qualificados)$"),
    ("ISCO_0", r"^(?:armed forces(?: occupations?)?|forces armees|professions militaires|militar(?:es)?|"
               r"forcas armadas|militaires)$"),
]
_ISCO_C = [(c, _fold(p)) for c, p in _ISCO]
_ISCO_NAMES = {"ISCO_0": "Armed forces occupations", "ISCO_1": "Managers", "ISCO_2": "Professionals",
               "ISCO_3": "Technicians and associate professionals", "ISCO_4": "Clerical support workers",
               "ISCO_5": "Service and sales workers", "ISCO_6": "Skilled agricultural, forestry and fishery workers",
               "ISCO_7": "Craft and related trades workers", "ISCO_8": "Plant and machine operators, and assemblers",
               "ISCO_9": "Elementary occupations"}


def _occupation(s: str) -> str:
    m = re.search(r"\(isco ([\d,\s]+)\)$", s)
    if m:
        nums = [n for n in re.split(r"[,\s]+", m.group(1)) if n]
        return "ISCO_" + "_".join(nums)
    for code, rx in _ISCO_C:
        if rx.search(s):
            return code
    return ""


# --------------------------------------------------------- status, sector ---

_STATUS = [
    ("COOP", r"^(?:members? of (?:producers.? )?cooperatives?|membres? (?:d.une |des )?cooperatives? de producteurs|"
             r"membre de cooperative/ groupement|miembro de cooperativas|uma cooperativa de produtores|"
             r"member of producers.? cooperative)$"),
    ("CFW", r"^(?:contrib\w*\.? family workers?|unpaid family workers?|aides? famili\w+|"
            r"travailleurs? famili\w+(?: non-?remuneres| contributeurs)?|"
            r"trabalhador(?:es)? familiar(?:es)? (?:sem|nao) remunera\w+|trab\. familiar sem remuneracao.*|"
            r"trabalho familiar sem remuneracao|ajuda familiar|trabajador familiar auxiliar|"
            r"helper \(without pay\) in a family business)$"),
    # NOT Stats SA's "Unpaid household member": printed BESIDE "Contributing
    # family workers" in one table with a different value (2025-Q3: 57 vs 28).
    ("EMP", r"^(?:employers?|employeurs?|employeur/patron|patrons?,? employeurs|patron|empregador|empresario \(propietario\)|"
            r"patrao/empregador|employer \(with hired employees\)|conta propria com (?:empregados|trabalhador\(es\))|self-employed with employees)$"),
    ("OAW", r"^(?:own[- ]?account workers?|travailleurs? (?:pour (?:son )?propre compte|a son propre compte|"
            r"compte propre|pour compte propre)|travailleurs? independants?|independants?|"
            r"conta propria(?: sem (?:empregados|trabalhador))?|trabalhador por conta propria|independiente o autonomo|"
            r"own-account worker \(without hired employees\)|self-employed without employees|"
            r"independent workers? without employees(?: \(own-account workers\))?)$"),
    ("EES", r"^(?:employees?|paid employees?|employes? remuneres?|salaries?|salaries? |wage employment|"
            r"paid employment|employe \(travail pour une tierce personne contre remuneration\)|"
            r"as an employee for someone else)$"),
]
_STATUS_C = [(c, _fold(p)) for c, p in _STATUS]
_STATUS_NAMES = {"EES": "Employees", "EMP": "Employers", "OAW": "Own-account workers",
                 "CFW": "Contributing family workers", "COOP": "Members of producers' cooperatives"}

_SECTOR = [
    ("SOE", r"^(?:entreprises? publiques? (?:et|/) ?(?:semi- ?publiques?|parapubliques?)|epp|"
            r"semi-public/parastatals?|parastatal sector|semi-public|parastatals?)$"),
    ("GOV", r"^(?:administration publique(?: et collectivites locales(?: \(y compris la promotion nationale\))?)?|"
            r"apu|etat/collectivites locales|public \(government\)|الجهاز الاداري)$"),
    ("PUB", r"^(?:public|secteur public|emploi secteur public|القطاع العام)$"),
    ("PRIV", r"^(?:secteur prive(?: \(y compris le secteur informel\))?|prive|private sector|emploi secteur prive|"
             r"القطاع الخاص)$"),
    ("HH", r"^(?:menage employeur|menages|private household|menage comme employeur de personnel domestique)$"),
    ("NGO", r"^(?:non-government organi[sz]ation|ngo)$"),
    ("INTL", r"^(?:international organi[sz]ation|organisme international/ambassade|organisation internationale)$"),
]
_SECTOR_C = [(c, _fold(p)) for c, p in _SECTOR]
_SECTOR_NAMES = {"GOV": "General government", "SOE": "Public and parastatal enterprises",
                 "PUB": "Public sector (government and public enterprises)", "PRIV": "Private sector",
                 "HH": "Households as employers", "NGO": "Non-governmental organisations",
                 "INTL": "International organisations"}

_FORMAL = [
    ("INFEMP", r"^(?:informal employment|emprego informal|emploi informel|emplois informels|ocupacion informal|"
               r"persons with informal (?:main )?jobs?(?: \(informal employment\))?)$"),
    ("FORMEMP", r"^(?:formal employment|emprego formal|emploi formel|emplois formels|ocupacion formal|"
                r"persons with formal (?:main )?jobs?(?: \(formal employment\))?)$"),
    ("INFSEC", r"^(?:informal sector(?: employment)?|secteur informel|sector informal|employment in informal sector)$"),
    ("FORMSEC", r"^(?:formal sector(?: employment)?|secteur formel|sector formal|employment in formal sector)$"),
    ("HHSEC", r"^(?:households?|household sector)$"),
]
_FORMAL_C = [(c, _fold(p)) for c, p in _FORMAL]
_FORMAL_NAMES = {"INFEMP": "Informal employment (jobs)", "FORMEMP": "Formal employment (jobs)",
                 "INFSEC": "Employment in the informal sector", "FORMSEC": "Employment in the formal sector",
                 "HHSEC": "Employment in the household sector"}

_ACT = [("EMP", r"^employed$"), ("UNE", r"^unemployed$"),
        ("OLF", r"^(?:outside labou?r force|economically inactive)$"), ("LF", r"^economically active$")]
_ACT_C = [(c, _fold(p)) for c, p in _ACT]
_ACT_NAMES = {"EMP": "Employed", "UNE": "Unemployed", "OLF": "Outside the labour force", "LF": "Labour force"}


def _hours(s: str) -> str:
    t = re.sub(r"\bhou?r[as]?s?\b|\bhoras?\b|\bheures?\b", "", s)
    t = re.sub(r"\s+", " ", t).strip()
    m = re.fullmatch(r"de (\d+) a menos de (\d+)", t)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2)) - 1
        return f"H{lo}T{hi}" if lo < hi else ""
    t = re.sub(r"^de ", "", t)
    a = age_code(t)
    if not a.startswith("Y"):
        return ""
    return "H" + a[1:]


def _first(rules, s: str) -> str:
    for code, rx in rules:
        if rx.search(s):
            return code
    return ""


def code_for(topic: str, label: str, classification: str = "") -> str:
    """Standard concept for one published category, or "" (see module doc)."""
    raw = str(label or "")
    s = _clean(raw)
    if not s:
        return ""
    if _TOTAL.match(s):
        return "_T"
    if _UNKNOWN.match(s):
        return "_U"
    if _NEC.match(s) or (topic == "industry" and s in ("activities n.e.c",)):
        return "_X"
    if re.search(r"[a-z]", s) and len(s) <= 2 and topic != "industry":
        return ""
    # a letter-coded section keeps its letter; any other " - " is a sub-item
    if not (_LETTER.match(s) and classification.startswith("ISIC")) and _SUB.search(s):
        return ""
    if topic == "industry":
        return _industry(s, raw, classification)
    if topic == "occupation":
        return _occupation(s)
    if topic == "employment_status":
        return _first(_STATUS_C, s)
    if topic == "sector":
        return _first(_SECTOR_C, s)
    if topic == "formality":
        return _first(_FORMAL_C, s)
    if topic == "activity_status":
        return _first(_ACT_C, s)
    if topic == "hours":
        return _hours(s)
    return ""


def _name(topic: str, code: str) -> str:
    if code == "_T":
        return "Total"
    if code == "_U":
        return "Not stated"
    if code == "_X":
        return "Not classifiable"
    if topic == "industry":
        return _SECTION_NAMES.get(code, "")
    if topic == "occupation":
        if code in _ISCO_NAMES:
            return _ISCO_NAMES[code]
        return "ISCO major groups " + ", ".join(code.split("_")[1:]) + " (as published)"
    if topic == "employment_status":
        return _STATUS_NAMES.get(code, "")
    if topic == "sector":
        return _SECTOR_NAMES.get(code, "")
    if topic == "formality":
        return _FORMAL_NAMES.get(code, "")
    if topic == "activity_status":
        return _ACT_NAMES.get(code, "")
    if topic == "hours":
        return "Hours usually worked " + code[1:].replace("_GE", ">=").replace("_LT", "<").replace("T", "-")
    return ""


_BROAD = {"BROAD_AGR", "BROAD_IND", "BROAD_SER", "PRIMARY", "SECONDARY", "TERTIARY"}
_SECTIONS = set("ABCDEFGHIJKLMNOPQRSTU") | {"A02", "A03", "DE", "HJ", "GI", "LMN", "KLMN"}

# Same table, different scope: Stats SA lists "Domestic worker" beside
# "Elementary", so its Elementary is ISCO 9 minus domestic workers.
_BLANK = {("South_Africa", "occupation", "Elementary")}

_TABLE = ["country", "survey", "topic", "classification", "series_code", "sex", "age_group",
          "education", "geography", "locality", "locality_label", "working_age_base",
          "period", "measure"]
_SEX = {"male": "M", "female": "F", "total": "_T"}
_TOPIC_NAME = {"industry": "Employment by industry", "occupation": "Employment by occupation",
               "employment_status": "Employment by status in employment",
               "sector": "Employment by institutional sector", "formality": "Employment by formality",
               "activity_status": "Population by labour force status",
               "hours": "Employed persons by hours usually worked"}
_TOPIC_ID = {"industry": "IND", "occupation": "OCC", "employment_status": "STE", "sector": "INS",
             "formality": "FORM", "activity_status": "ACT", "hours": "HRS"}


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    """Append STD_COLUMNS to a labour frame (published columns untouched)."""
    out = drop_std(df, STD_COLUMNS)
    s = out.fillna("").astype(str)

    keys = list(zip(s["topic"], s["characteristic"], s["classification"]))
    cache = {k: code_for(*k) for k in set(keys)}
    code = pd.Series([cache[k] for k in keys], index=out.index)

    # bare "Agriculture" is the broad sector only where its table does not
    # also list its parts (fishing, forestry, livestock ...) separately
    agri = (s["topic"] == "industry") & s["characteristic"].map(lambda x: bool(_AGRI_ONLY.match(_clean(x))))
    if agri.any():
        parts = s["characteristic"].map(lambda x: bool(_AGRI_PARTS.search(_clean(x))))
        has_parts = parts.groupby([s[c] for c in _TABLE]).transform("any")
        code[agri & ~has_parts] = "BROAD_AGR"
    # A BROAD sector is only broad in a table of broad sectors. INS Cameroun
    # prints "Primaire / Industrie / BTP / Commerce / Services": there
    # "Industrie" excludes construction and "Services" excludes trade, so
    # beside any ISIC section in the same table the broad words stay blank.
    broad = code.isin(_BROAD)
    if broad.any():
        is_sec = (s["topic"] == "industry") & code.isin(_SECTIONS)
        sec_in_table = is_sec.groupby([s[c] for c in _TABLE]).transform("any")
        code[broad & sec_in_table] = ""
    for country, topic, label in _BLANK:
        code[(s["country"] == country) & (s["topic"] == topic) & (s["characteristic"] == label)] = ""
    out["category_code"] = code
    out["category_std"] = [_name(t, c) if c else "" for t, c in zip(s["topic"], code)]

    out["sex_code"] = s["sex"].map(_SEX).fillna("")
    ac = {a: age_code(a) for a in s["age_group"].unique()}
    out["age_code"] = s["age_group"].map(ac)
    gl = {g: geography_level(g) for g in s["geography"].unique()}
    out["geography_level"] = s["geography"].map(gl)

    uk = list(zip(s["unit"], s["iso3"]))
    uc = {k: unit_parts(*k) for k in set(uk)}
    out["unit_std"] = [uc[k][2] for k in uk]
    out["unit_multiplier"] = [uc[k][1] for k in uk]
    v = pd.to_numeric(out["value"], errors="coerce")
    mult = pd.to_numeric(out["unit_multiplier"], errors="coerce").fillna(1.0)
    out["value_std"] = v * mult

    ek = list(zip(textual(s["series_code"]), s["source_file"], s["survey"]))
    ec = {k: edition(*k) for k in set(ek)}
    out["edition"] = [ec[k] for k in ek]

    sid, sname = [], []
    for c, t, meas, sx, ag, wab, edu, loc, ll, cstd, cls in zip(
            code, s["topic"], s["measure"], out["sex_code"], out["age_code"],
            s["working_age_base"], s["education"], s["locality"], s["locality_label"],
            out["category_std"], s["classification"]):
        # Seychelles prints status in employment under ICSE-93, ICSE-18-A AND
        # ICSE-18-R for one quarter, with different values: the 2018 standard
        # is part of the ID (ICSE-93 and national schemes carry no token).
        icse = cls.replace("-", "") if (t == "employment_status" and cls.startswith("ICSE-18")) else ""
        if not c or not ag or not sx or edu != "Total":
            sid.append("")
            sname.append("")
            continue
        wab_id = "WNS" if wab == "not stated" else "W" + wab.replace("+", "_GE").replace("-", "T")
        # Urban/rural is part of the ID: one value per series_id, place and date.
        # Totals/unknowns get WORDS, not bare letters: "_U" stripped to "U" was
        # ISIC section U (extraterritorial organisations) -- "industry not
        # stated" and section U shared one ID until 2026-10-15.
        ctok = {"_T": "TOTAL", "_U": "NOTSTATED", "_X": "NOTCLASS"}.get(c, c)
        sid.append(safe_id("LAB", _TOPIC_ID.get(t, t), ctok, meas, sx.lstrip("_") or "T", ag.lstrip("_"), wab_id,
                           locality_token(loc, ll), icse))
        sname.append(join_name(
            f"{_TOPIC_NAME.get(t, t)}: {cstd[:1].lower() + cstd[1:]}",
            {"share": "share (%)", "count": "number of persons"}.get(meas, meas),
            sex_name(sx), age_name(ag),
            "working-age base not stated" if wab == "not stated" else f"working-age base {wab}",
            locality_name(locality_token(loc, ll)), cls if icse else ""))
    out["series_id"] = sid
    out["series_name"] = sname

    out["_ed"] = out["edition"].map(edition_rank)
    drop_conflicts(out, ["country", "series_id", "geography", "period"],
                   ["source_file", "survey", "series_code"])
    out["is_preferred"] = mark_preferred(
        out, ["country", "series_id", "geography", "period"],
        ["_ed", "survey", "source_file", "series_code"])
    out = out.drop(columns="_ed")
    return finish(out, STD_COLUMNS)
