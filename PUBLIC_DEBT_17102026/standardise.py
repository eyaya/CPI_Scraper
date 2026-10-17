"""Standardised columns for Public Debt, derived from the published ones.

Same contract as GDP (indicators/gdp/standardise.py, core/standardise_base.py):
the published columns stay verbatim; these are APPENDED, derived only from
them, recomputed on every write (Pipeline.standardise, after merge-on-write),
and BLANK whenever the label does not support a confident answer.

THE TWO FREE-TEXT FIELDS.
* `component` -- 1,000+ publisher labels ("Dette extérieure: Dette
  bilatérale", "Credores Multilaterais: FMI", "Domestic: Treasury Bills").
  Labels are PATHS (": ", " > ", " - " separate levels), so a concept is read
  from the LAST level and only kept when every parent level is a container
  ("Encours", "Stock", "Total") or a broader concept (total / external /
  domestic). A named creditor ("Bilatéraux: EXIM BANK CHINE"), a holder
  ("Net Claims on Government - Bank of Sierra Leone: Treasury Bills"), a
  maturity, a currency, a sub-item ("dont", "o.w.") or a variant ("hors
  arriérés", "excluding Rand") is never promoted to the broader concept.
* `coverage` -- the debt perimeter as the source states it. Coded only when
  the text names a standard perimeter; "perimeter not stated" stays blank.
  Two countries' totals compare only when coverage_code matches.

THE COLUMNS (appended):
  category_code   TOTAL | TOTAL_NET | EXT | EXT_NET | DOM | DOM_NET |
                  MULTILATERAL | BILATERAL | BILAT_PARIS | BILAT_NONPARIS |
                  COMMERCIAL | TBILLS | BONDS | LOANS | ARREARS | ARREARS_EXT |
                  ARREARS_DOM | GUARANTEED | GUARANTEED_EXT | GUARANTEED_DOM | blank
  category_std    English name of category_code
  coverage_code   CG central government | BCG budgetary central government |
                  GG general government | PS public sector incl. SOEs |
                  PPG central government + guaranteed (= public & publicly
                  guaranteed) | GUAR guarantees only | SOE | LG local government |
                  EBU extra-budgetary units | PC public corporations |
                  CG_SG federal + state governments | blank
  currency, unit_multiplier, unit_std   (core.standardise_base.unit_parts;
                  "N$" pinned to NAD here; core also treats a prefixed "$"
                  as local since 2026-10-15, so this is belt-and-braces)
  value_std       value x unit_multiplier for stocks; percents unchanged
  edition         the publication's year (and quarter) when it can be read
  series_id       DEBT_<code>_<coverage>_<measure>_<LCU|USD|SDR..>_<freq>
  is_preferred    one True per (country, series_id, currency, period): newest edition
"""
from __future__ import annotations

import re

import pandas as pd

from core.standardise_base import drop_conflicts
from core.standardise_base import (FREQ_NAME, currency_class, currency_name, join_name)
from core.standardise_base import (LOCAL_CURRENCY, CEMAC, WAEMU, drop_std, edition,
                                   edition_rank, finish, mark_preferred, norm,
                                   safe_id, textual, unit_parts)

STD_COLUMNS = ["category_code", "category_std", "coverage_code", "currency",
               "unit_multiplier", "unit_std", "value_std", "edition",
               "series_id", "series_name", "is_preferred"]

CODE_NAMES = {
    "TOTAL": "Total debt (gross)", "TOTAL_NET": "Total debt (net)",
    "EXT": "External debt", "EXT_NET": "External debt (net)",
    "DOM": "Domestic debt", "DOM_NET": "Domestic debt (net)",
    "MULTILATERAL": "External debt: multilateral creditors",
    "BILATERAL": "External debt: bilateral creditors",
    "BILAT_PARIS": "External debt: Paris Club bilateral creditors",
    "BILAT_NONPARIS": "External debt: non-Paris Club bilateral creditors",
    "COMMERCIAL": "External debt: commercial creditors",
    "TBILLS": "Treasury bills", "BONDS": "Bonds",
    "BONDS_EXT": "External bonds", "TBILLS_EXT": "Treasury bills held/issued externally",
    "LOANS_DOM": "Domestic loans", "LOANS_EXT": "External loans",
    "ARREARS": "Arrears", "ARREARS_EXT": "External arrears", "ARREARS_DOM": "Domestic arrears",
    "GUARANTEED": "Guaranteed debt", "GUARANTEED_EXT": "Guaranteed external debt",
    "GUARANTEED_DOM": "Guaranteed domestic debt",
}
_CREDITOR = {"MULTILATERAL", "BILATERAL", "BILAT_PARIS", "BILAT_NONPARIS", "COMMERCIAL"}
_INSTRUMENT = {"TBILLS", "BONDS", "LOANS"}

# ------------------------------------------------------------- components ---

# A level that only says "the total of this table": the concept is its parent's.
_CONTAINER = re.compile(
    r"^(?:total|grand total|sub-?total|totaux?|stock|encours|outstanding|total debt stock|"
    r"total stock|stock total|total encours|g\.total|disbursed|dod)$")

# Anything that narrows or qualifies a concept: never coded.
_QUALIFIER = re.compile(
    r"\b(?:dont|of which|o\.?w\.?|do qual|hors|excl(?:\.|uding|ut)?|sans|avec|incl(?:\.|uding)?|"
    r"except|y compris|including)\b|"
    r"\b(?:fgn|states?|fct)\b|"            # Nigeria: perimeter inside the label
    r"\b(?:face value|principal|interest|penalt|contractual|delay|ira|pra)\b|"
    r"\b(?:short|medium|long)[- ]term|\bcourt terme\b|\bmoyen et long\b|curto prazo|longo prazo|"
    r"\b(?:monnaie|moeda|currency|devise)\b|\bconcessional\b|\bnon-?concessional\b|"
    r"\b(?:fixed|variable|taux fixe|taux variable|fixe|interest free)\b")

_SEG = r"(?:\s*:\s*|\s+>\s+|\s+-\s+|\s+—\s+|\s+o\.w\.\s+)"
_PERIM_PREFIX = re.compile(
    r"^(?:(?:budgetary )?central government(?: \(bcg\))?|public sector|general government|"
    r"government|gross|public|state|national|total)\s+")


def _clean(label: str) -> str:
    s = norm(label)
    s = re.sub(r"\[(?:grand total|total)\]", "", s)              # Zimbabwe level tags = totals
    s = re.sub(r"\((?:[a-z]\s*[+\-]\s*)+[a-z]\)", "", s)          # (a+b+c+d), (A+B)
    s = re.sub(r"\((?:\d\s*[+\-]\s*)+\d\)", "", s)                # (3+4+5)
    s = re.sub(r"\(share of [^)]*\)", "", s)                      # (share of gross loan debt)
    s = re.sub(r"\(gross\)|\(book value\)", "", s)
    s = re.sub(r"\*+|\++|\s/\s(?=dette)", " ", s)                 # footnotes; "Domestic debt / Dette intérieure"
    s = re.sub(r"^(?:[ivx]+|\d+(?:\.\d+)*|[a-z])\s*[.)\-]\s*", "", s)  # "1. ", "2.1. ", "I. ", "A- "
    return re.sub(r"\s+", " ", s).strip(" :;,.-")


# One level -> concept. Patterns run on a cleaned, accent-free level.
_LEVEL: list[tuple[str, str]] = [
    ("TOTAL_NET", r"^(?:total: )?net (?:loan|central government|public)? ?debt$|^public sector net debt$|^net loan debt$"),
    ("EXT_NET", r"^net (?:foreign|external) debt$"),
    ("DOM_NET", r"^net domestic debt(?: of government)?$"),
    ("ARREARS_EXT", r"^(?:external (?:debt )?arrears|arrieres exterieurs)$"),
    ("ARREARS_DOM", r"^(?:domestic arrears|arrieres interieurs)$"),
    ("ARREARS", r"^(?:arrears|arrieres|stocks? arrieres)$"),
    ("GUARANTEED_EXT", r"^(?:guaranteed external debt|external-guaranteed)$"),
    ("GUARANTEED_DOM", r"^(?:guaranteed domestic debt|domestic-guaranteed|domestic guarantees)$"),
    ("GUARANTEED", r"^(?:total )?(?:government[- ])?guaranteed debt(?: \(domestic \+ external\))?$|"
                   r"^total (?:government )?guarantee[sd]?(?: debt)?$|^total government guaranteed debt$|"
                   r"^dette (?:avalisee|garantie)$"),
    ("BILAT_NONPARIS", r"^(?:bilateral )?non[- ]?paris club(?: countries)?$"),
    ("BILAT_PARIS", r"^(?:bilateral )?paris club(?: countries)?$|^club de paris$"),
    ("MULTILATERAL", r"^(?:dette |credores |external debt: )?multilat\w*(?: (?:debt|loans|creditors|external debt))?$|"
                     r"^international and regional institutions$|^loans from organisations$|"
                     r"^deuda externa: multilateral$"),
    ("BILATERAL", r"^(?:dette |credores |autres )?bilat\w*(?: (?:debt|loans|creditors|external debt))?$|"
                  r"^loans from governments$"),
    ("COMMERCIAL", r"^(?:dette )?commerci\w*(?: (?:debt|external debt|creditors))?$"),
    ("TBILLS", r"^(?:treasury bills(?: outstanding)?|t-bills|bons? du tresor|bilhetes d[eo] tesouro|bta)$"),
    ("BONDS", r"^(?:treasury bonds|t-bonds|obligations du tresor|obrigacoes do tesouro|ota|bonds|"
              r"government bonds|grz bonds outstanding)$"),
    ("LOANS_DOM", r"^domestic loans$"),
    ("LOANS", r"^loans$"),          # only meaningful under a domestic/external parent
    ("EXT", r"^(?:total |gross |public |stock |encours (?:de la )?)?(?:external|foreign|exterieure?|exterior)"
            r"(?: debt| public debt)?(?: stock| outstanding)?$|"
            r"^(?:total |gross |public |encours (?:de la )?|stock (?:de la )?)?(?:dette|divida|deuda) (?:publique )?"
            r"(?:exterieure?|externa)(?: publique| du tresor)?$|^public external debt$|"
            r"^encours de la dette exterieure (?:publique|du tresor)$|^part de la dette exterieure$|"
            r"^taux d.endettement exterieur$|^dette exterieure / pib$|^dette exterieure de l.administration centrale$|"
            r"^external debt outstanding$|^disbursed external debt(?: by creditor category)?$"),
    ("DOM", r"^(?:total |gross |public |stock |encours (?:de la )?)?(?:domestic|interieure?|interior)"
            r"(?: debt| public debt)?(?: stock| outstanding)?$|"
            r"^(?:total |gross |public |encours (?:de la )?|stock (?:de la )?)?(?:dette|divida|deuda) (?:publique )?"
            r"(?:interieure?|interna)(?: publique| du tresor)?$|^total dette interieure$|"
            r"^encours de la dette interieure du tresor$|^part de la dette interieure$|"
            r"^taux d.endettement interieur$|^dette interieure de l.administration centrale$|"
            r"^domestic debt outstanding$|^gross domestic debt$"),
    ("TOTAL", r"^(?:total |gross |outstanding )?(?:public |government |state )?debt(?: stock| outstanding)?$|"
              r"^(?:total|gross) (?:public |government |central government |loan )?debt(?: stock)?$|"
              r"^total public debt$|^dette (?:publique|totale)(?: totale)?(?: brute)?$|"
              r"^dette publique totale(?: brute)?$|^dette brute totale$|^(?:encours|stock) (?:de la )?dette(?: publique)?(?: du tresor)?$|"
              r"^encours dette publique$|^total (?:da )?divida$|^divida publica total$|^deuda publica$|"
              r"^outstanding public debt$|^public debt, end of period$|^gross loan debt$|"
              r"^gross central government debt$|^central government total debt$|^government debt$|"
              r"^taux d.endettement(?: public)?$|^dette totale de l.administration centrale$|"
              r"^dette de l.administration centrale en % du pib$|^dette de l.administration centrale / pib$|"
              r"^public (?:and|&) publicly guaranteed debt$|^total public and publicly guaranteed|"
              r"^total government and government guaranteed debt$"),
]
_LEVEL_RX = [(c, re.compile(p)) for c, p in _LEVEL]


def _level(seg: str) -> str:
    s = _PERIM_PREFIX.sub("", seg) if not re.match(r"^(?:total|gross)\b", seg) else seg
    for cand in (seg, s):
        for code, rx in _LEVEL_RX:
            if rx.search(cand):
                return code
    return ""


def code_for_component(label: str) -> str:
    s = _clean(label)
    if not s or _QUALIFIER.search(s):
        return ""
    segs = [x.strip() for x in re.split(_SEG, s) if x.strip()]
    while len(segs) > 1 and _CONTAINER.match(segs[-1]):      # "Commercial: Total debt stock"
        segs = segs[:-1]
    child = _level(segs[-1])
    if not child:
        return ""
    for p in segs[:-1]:
        if _CONTAINER.match(p):
            continue
        pc = _level(p)
        if pc == "TOTAL":
            if child in {"TOTAL", "EXT", "DOM", "ARREARS"} | _CREDITOR | _INSTRUMENT:
                continue
        elif pc in ("EXT", "DOM"):
            if child in _CREDITOR | _INSTRUMENT:
                if pc == "DOM" and child in _CREDITOR:
                    return ""
                # an instrument keeps its parent: Seychelles prints both
                # "Domestic: Loans" and "External: Loans"
                if child in _INSTRUMENT and (child == "LOANS" or pc == "EXT"):
                    child = f"{child}_{pc}"
                continue
            if child == "ARREARS":
                child = f"ARREARS_{pc}"
                continue
        elif pc == "ARREARS" and child in ("EXT", "DOM"):
            child = f"ARREARS_{child}"
            continue
        elif pc in ("MULTILATERAL", "BILATERAL") and child == pc:
            continue
        elif pc == "BILATERAL" and child in ("BILAT_PARIS", "BILAT_NONPARIS"):
            continue
        return ""                       # an unrecognised or narrowing parent
    return "" if child == "LOANS" else child      # bare "Loans": domestic or external?


# --------------------------------------------------------------- coverage ---

_COVERAGE: list[tuple[str, str]] = [
    ("", r"perimeter not (?:stated|restated)|not stable|public and private|external debt public and private"),
    ("CG", r"^central government debt excluding state-owned"),
    ("GUAR", r"^(?:central government loan guarantees|government guaranteed debt|passifs conditionnels)"),
    ("PPG", r"public(?:ly)? (?:and|&) publicly guaranteed|\bppg\b|directe et garantie|garantie et directe|"
            r"central government (?:debt )?and (?:government[- ])?guaranteed|state direct debt \+ state-guaranteed"),
    ("PS", r"^public sector|secteur public|central government and state-owned enterprises|"
           r"central government debt including state-owned"),
    ("GG", r"^general government"),
    ("BCG", r"budgetary central government|governo central orcamental"),
    ("EBU", r"^extra budgetary units"),
    ("PC", r"^public corporations"),
    ("SOE", r"^(?:public establishments and enterprises|entreprises et etablissements publics)"),
    ("LG", r"^(?:local government|collectivites territoriales)"),
    ("CG_SG", r"federal government, 36 states"),
    ("CG", r"central government debt excluding state-owned|central government|administration centrale|\(etat\)|dette publique de l.etat|"
           r"^federal government|national government|treasury \(central government\)|"
           r"^government debt \(divida governamental\)|^dette publique \(etat\)"),
]
_COVERAGE_RX = [(c, re.compile(p)) for c, p in _COVERAGE]


# A component that names its OWN perimeter overrides the file-level coverage:
# Rwanda's PPG file prints "Central government external debt" and "General
# government domestic debt"; Namibia's prints "Gross Central Government debt"
# beside "Total debt" (central government + guarantees).
_LABEL_PERIMETER: list[tuple[str, re.Pattern]] = [(c, re.compile(p)) for c, p in (
    ("PPG", r"government and government guaranteed debt|public (?:and|&) publicly guaranteed"),
    ("BCG", r"budgetary central government"),
    ("CG", r"central government|administration centrale|^total government debt$"),
    ("GG", r"general government"),
    ("PS", r"^public sector"),
)]


def label_perimeter(label: str) -> str:
    s = norm(label)
    for code, rx in _LABEL_PERIMETER:
        if rx.search(s):
            return code
    return ""


def coverage_code(text: str) -> str:
    s = norm(text)
    for code, rx in _COVERAGE_RX:
        if rx.search(s):
            return code
    return ""


# -------------------------------------------------------------- the frame ---

_LEGACY = {"SLE": {"SLL"}, "ZWE": {"ZWL"}, "STP": {"STD"}}   # pre-redenomination currencies


def _local(iso3: str) -> set:
    cur = {LOCAL_CURRENCY.get(iso3, "")} | _LEGACY.get(iso3, set())
    if iso3 in WAEMU:
        cur.add("XOF")
    if iso3 in CEMAC:
        cur.add("XAF")
    return cur


def _units(unit: str, iso3: str) -> tuple[str, str, str]:
    if re.search(r"\bN\$", unit or ""):               # Namibia dollar, not USD
        u = unit_parts(re.sub(r"N\$", "NAD", unit), iso3)
        return u
    return unit_parts(unit, iso3)


def _collisions(out: pd.DataFrame, s: pd.DataFrame) -> pd.Series:
    """Two DIFFERENT labels claiming the same code for the same observation with
    different values: the labels cannot both be that concept, and the label
    alone cannot say which is -- blank every row of both labels."""
    k = ["country", "coverage", "series_code", "period", "frequency", "measure", "unit", "category_code"]
    has = out["category_code"] != ""
    v = pd.to_numeric(out["value"], errors="coerce").round(6)
    sub = pd.DataFrame({**{c: s[c] for c in k[:-1]}, "category_code": out["category_code"],
                        "component": s["component"], "v": v})[has]
    g = sub.groupby(k)
    clash = (g["component"].transform("nunique") > 1) & (g["v"].transform("nunique") > 1)
    bad = set(map(tuple, sub.loc[clash, ["country", "coverage", "series_code", "measure", "unit", "component"]].values))
    key = list(zip(s["country"], s["coverage"], s["series_code"], s["measure"], s["unit"], s["component"]))
    return pd.Series([x in bad for x in key], index=out.index)


_FREQ = {"annual": "A", "quarterly": "Q", "monthly": "M"}
_COVERAGE_NAME = {
    "CG": "central government", "BCG": "budgetary central government", "GG": "general government",
    "PS": "public sector incl. state-owned enterprises",
    "PPG": "public and publicly guaranteed", "GUAR": "government guarantees only",
    "SOE": "state-owned enterprises", "LG": "local government", "EBU": "extra-budgetary units",
    "PC": "public corporations", "CG_SG": "federal and state governments"}


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    out = drop_std(df, STD_COLUMNS)
    s = out.fillna("").astype(str)

    cache = {c: code_for_component(c) for c in s["component"].unique()}
    out["category_code"] = s["component"].map(cache)
    out.loc[_collisions(out, s), "category_code"] = ""
    # "STOCK" VS "ENCOURS". Where an office prints both, the stock INCLUDES
    # arrears (Chad DD's Tableau 1.1 footnote; CAR DDPE's "Bilatéraux
    # (encours + arriérés)"): filing both as EXT would splice two concepts.
    lab = s["component"].map(norm)
    has_encours = lab.str.contains(r"\bencours\b").groupby(s["country"]).transform("any")
    out.loc[has_encours & lab.str.contains(r"\bstocks?\b") & ~lab.str.contains(r"arriere"), "category_code"] = ""
    # "COMMERCIAL" NARROWER THAN ITS NAME. GSS Ghana prints "International
    # capital market external debt" (Eurobonds, 13.1bn of 31.0bn) beside
    # "Commercial external debt", so its commercial line excludes bonds and
    # multilateral + bilateral + commercial misses external debt by ~44%.
    icm = lab.str.contains(r"capital market").groupby([s["country"], s["series_code"]]).transform("any")
    out.loc[icm & (out["category_code"] == "COMMERCIAL"), "category_code"] = ""
    out["category_std"] = out["category_code"].map(CODE_NAMES).fillna("")

    cc = {c: coverage_code(c) for c in s["coverage"].unique()}
    lp = {c: label_perimeter(c) for c in s["component"].unique()}
    out["coverage_code"] = s["component"].map(lp).where(s["component"].map(lp) != "", s["coverage"].map(cc))

    uk = list(zip(s["unit"], s["iso3"]))
    uc = {k: _units(*k) for k in set(uk)}
    out["currency"] = [uc[k][0] for k in uk]
    out["unit_multiplier"] = [uc[k][1] for k in uk]
    out["unit_std"] = [uc[k][2] for k in uk]

    v = pd.to_numeric(out["value"], errors="coerce")
    mult = pd.to_numeric(out["unit_multiplier"], errors="coerce").fillna(1.0)
    out["value_std"] = v * mult

    ek = list(zip(textual(s["series_code"]), s["source_file"]))
    ec = {k: edition(*k) for k in set(ek)}
    out["edition"] = [ec[k] for k in ek]

    sid, sname = [], []
    for code, cov, meas, cur, fq, iso in zip(out["category_code"], out["coverage_code"],
                                             s["measure"], out["currency"], s["frequency"], s["iso3"]):
        if not code:
            sid.append("")
            sname.append("")
            continue
        # A pre-redenomination currency (SLL, ZWL, STD) keeps its own code, so
        # its values never splice into the current currency's series.
        cls = currency_class(cur, iso)
        sid.append(safe_id("DEBT", code, cov or "UNSTATED", meas, cls, _FREQ.get(fq, fq)))
        sname.append(join_name(
            f"Public debt, {CODE_NAMES[code][:1].lower() + CODE_NAMES[code][1:]}",
            _COVERAGE_NAME.get(cov, "coverage not stated"),
            {"stock": "stock", "share_of_gdp": "% of GDP", "share": "share of total debt (%)"}.get(meas, meas),
            currency_name(cls), FREQ_NAME.get(_FREQ.get(fq, ""), fq)))
    out["series_id"] = sid
    out["series_name"] = sname

    out["_ed"] = out["edition"].map(edition_rank)
    out["_span"] = out.groupby(["series_id", "component", "series_code"])["period"].transform("nunique")
    drop_conflicts(out, ["country", "series_id", "currency", "period"], ["source_file", "series_code"])
    out["is_preferred"] = mark_preferred(out, ["country", "series_id", "currency", "period"],
                                         ["_ed", "_span", "series_code", "component"])
    out = out.drop(columns=["_ed", "_span"])
    return finish(out, STD_COLUMNS)
