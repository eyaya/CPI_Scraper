"""Standardised columns for unemployment / labour-force status, derived from
the published ones (same contract as indicators/gdp/standardise.py and
core/standardise_base.py: appended, recomputed on every write, BLANK when the
source does not support a confident answer).

WHAT IS DIFFERENT FROM GDP. The concept is already a controlled vocabulary --
`topic` -- so most rows map one-to-one. The one topic that needs the label is
`labour_underutilisation_rate`, which holds three distinct ILO measures under
one name (LU2 / LU3 / LU4, or SU2-4 in French, CRUPLF in Zambia/Namibia); they
are told apart by the wording of `series_label`, and a label that names none
of them (Rwanda's "Combined rate of labour underutilization") stays blank.

DEFINITIONS NEVER SHARE AN ID. `definition` (strict / broad) and
`working_age_base` (15+, 15-64, 10+, ...) are both IN series_id: a strict
15+ rate and a broad 15-64 rate are different numbers, and a consumer that
pooled them would compare unlike with unlike.

THE COLUMNS (appended after the published ones):
  category_code   UNE_RATE, LFPR, EPR, LU2, LU3, LU4, TRU_RATE, NEET_RATE,
                  NEET, INF_EMP_SHARE, LTU_SHARE, POP_WA, LF, EMP, UNE, OLF, PLF, LTU
                  -- or blank (a rate topic stored as a count, a youth rate
                  with no readable age band, an underutilisation label naming
                  no LU measure, a PART of a count such as "Unemployed:
                  seeking work for the first time", a crude activity rate)
  category_std    English name
  sex_code        M | F | _T
  age_code        SDMX-style band (Y15T24, Y_GE65, _T), blank if unreadable
  education_code  _T for the total, _U for not stated, else blank (national
                  education levels are not mapped to ISCED here)
  geography_level national | subnational
  currency, unit_multiplier, unit_std   (persons / percent; thousand_persons -> x1000)
  value_std       value x unit_multiplier
  edition         publication year (and quarter) when it can be read
  series_id       UNE_<code>_<definition>_<ICLS13|ICLS19 where stated>_<working-age base>_<frequency>
  is_preferred    one True per (country, series_id, sex, age_group, education,
                  geography, locality_label, period): newest edition, then the
                  longest-running series (Kenya's Table 6 LU2 over Table 1's,
                  which prints 18.6 for 2022-Q4 against 9.0 everywhere else)
"""
from __future__ import annotations

import re

import pandas as pd

from core.standardise_base import drop_conflicts
from core.standardise_base import (age_code, drop_std, edition, edition_rank,
                                   finish, geography_level, mark_preferred, norm,
                                   locality_token, safe_id, textual, unit_parts,
                                   FREQ_NAME, age_name, join_name, locality_name, sex_name)

STD_COLUMNS = ["category_code", "category_std", "sex_code", "age_code",
               "education_code", "geography_level", "currency", "unit_multiplier",
               "unit_std", "value_std", "edition", "series_id", "series_name", "is_preferred"]

# (topic, measure) -> code. A rate topic stored as a count is a parser defect,
# not a concept: it maps to nothing.
_TOPIC = {
    ("unemployment_rate", "rate"): "UNE_RATE",
    ("youth_unemployment_rate", "rate"): "UNE_RATE",     # the band is in age_code
    ("labour_force_participation_rate", "rate"): "LFPR",
    ("employment_to_population_ratio", "rate"): "EPR",
    ("underemployment_rate", "rate"): "TRU_RATE",
    ("neet_rate", "rate"): "NEET_RATE",
    ("neet_rate", "count"): "NEET",
    ("informal_employment_share", "rate"): "INF_EMP_SHARE",
    ("long_term_unemployment_share", "rate"): "LTU_SHARE",
    ("working_age_population", "count"): "POP_WA",
    ("labour_force", "count"): "LF",
    ("employed", "count"): "EMP",
    ("unemployed", "count"): "UNE",
    ("outside_labour_force", "count"): "OLF",
    ("potential_labour_force", "count"): "PLF",
}

CODE_NAMES = {
    "UNE_RATE": "Unemployment rate",
    "LFPR": "Labour force participation rate",
    "EPR": "Employment-to-population ratio",
    "LU2": "Combined rate of time-related underemployment and unemployment (LU2)",
    "LU3": "Combined rate of unemployment and potential labour force (LU3)",
    "LU4": "Composite measure of labour underutilisation (LU4)",
    "TRU_RATE": "Time-related underemployment rate",
    "NEET_RATE": "Share of youth not in employment, education or training",
    "NEET": "Youth not in employment, education or training",
    "INF_EMP_SHARE": "Informal employment share",
    "LTU_SHARE": "Long-term unemployment share",
    "POP_WA": "Working-age population",
    "LF": "Labour force",
    "EMP": "Employed persons",
    "UNE": "Unemployed persons",
    "OLF": "Persons outside the labour force",
    "PLF": "Potential labour force",
    "LTU": "Long-term unemployed persons",
}

# Labour underutilisation: the label decides. An explicit tag wins; otherwise
# the ILO wording, in English, French and Portuguese.
_LU_TAG = re.compile(r"\b(?:lu|su)\s*-?\s*([234])\b|labour underutilisation ([234])\b")
_LU_WORDS = [
    ("LU2", r"(?:time[- ]related underemployment|sous-emploi lie au temps|sous-emploi \+ chomage|"
            r"subemprego).*(?:unemployment|chomage|desemprego)|"
            r"(?:unemployment|chomage).*time[- ]related underemployment"),
    ("LU3", r"potential labou?r force|main[- ]d.?(?:oe|œ)uvre potentielle|population active potentielle|"
            r"forca de trabalho potencial|\bcruplf\b|\bycruplf\b"),
    ("LU4", r"composite|aggregated? measure|^(?:taux de )?sous-utilisation de la main|"
            r"^taxa de subutilizacao|^labour underutili[sz]ation$"),
]
_LU_COMPILED = [(c, re.compile(p)) for c, p in _LU_WORDS]


def lu_code(label: str) -> str:
    s = norm(label).replace("œ", "oe")
    m = _LU_TAG.search(s)
    if m:
        return f"LU{m.group(1) or m.group(2)}"
    for code, rx in _LU_COMPILED:
        if rx.search(s):
            return code
    return ""


# A PART of a count printed under the whole's topic. Found by LF = EMP + UNE
# failing: Sudan's 2008 census splits the unemployed into "Seeking work for the
# first time" / "Worked Before and Seeking Work", Malawi into "Seeking" / "Not
# Seeking Work", and Mauritius prints employment "in" / "outside large
# establishments" beside the Total -- the preferred row had picked "outside".
_PART = re.compile(r"seeking work|not seeking|first time|worked before|large establishments|"
                   r"premier emploi|primo|deja travaille")
# "Taux brut d'activite" (Gabon, CAR) is the CRUDE activity rate; its
# denominator is not stated as the working-age population, so it is not LFPR.
_NOT_LFPR = re.compile(r"taux brut d.activite")
# SUBSETS AND VARIANTS FILED AS THE WHOLE, found 2026-10-15 by comparing every
# superseded row with the preferred value of its series_id: Kenya's OLF "excl.
# potential labour force" (a subset of OLF), Mauritius's labour force split
# into "Mauritian" / "Foreign workers", Stats SA's "Discouraged job-seekers" (a
# subset of the potential labour force) and DR Congo's "doublement elargi"
# rate (broader than its own "sens large", which is the broad rate).
_SUBSET = re.compile(r"\bexcl\.?\b|excluding|non compris|\bhors\b|- mauritian|foreign workers|"
                     r"\bforeigners?\b|etrangers?|discouraged|decourages?|doublement elargi")


def concept(topic: str, measure: str, label: str) -> str:
    n = norm(label)
    if _SUBSET.search(n) and not (re.search(r"\binclud\w*|\bincl\b", n)
                                   and not re.search(r"\bexcl\b|excluding", n)):
        return ""
    if topic == "labour_underutilisation_rate":
        return lu_code(label) if measure == "rate" else ""
    if topic == "unemployed" and measure == "count" and re.search(r"long[- ]term", n):
        return "LTU"                     # Kenya's "Long-Term Unemployed"
    if measure == "count" and _PART.search(n):
        return ""
    if topic == "labour_force_participation_rate" and _NOT_LFPR.search(n):
        return ""
    return _TOPIC.get((topic, measure), "")


# The ICLS convention, ONLY where the source states it (Angola "13a"/"19a CIET",
# Cabo Verde "Resolucao I da 19a CIET", Morocco's EMO "emploi contre revenu" =
# the 19th ICLS "employment for pay or profit"). Unstated stays blank: most
# surveys do not say, and guessing would split or merge series wrongly.
def icls(survey: str, label: str) -> str:
    t = norm(f"{survey} | {label}")
    if re.search(r"\b(?:19|20|21)(?:a|ª|th|e|eme)? (?:cit|ciet|icls|cist)|contre revenu|resolu\w+ i da 19", t):
        return "ICLS19"
    if re.search(r"\b13(?:a|ª|th|e|eme)? (?:cit|ciet|icls|cist)", t):
        return "ICLS13"
    return ""


_SEX = {"male": "M", "female": "F", "total": "_T"}
_FREQ = {"annual": "A", "ad_hoc": "A", "quarterly": "Q", "semiannual": "H"}
_DEF = {"strict": "STRICT", "broad": "BROAD", "not_applicable": ""}


def _education(e: str) -> str:
    n = norm(e)
    if n in {"total", "ensemble", "all"}:
        return "_T"
    if n in {"nd", "n.d.", "non declare", "desconhecido", "not stated", "unknown"}:
        return "_U"
    return ""


def _base_token(wab: str) -> str:
    """'15+' -> WA15P, '15-64' -> WA15T64, 'not stated' -> WAU."""
    s = norm(wab)
    m = re.fullmatch(r"(\d+)\s*\+", s)
    if m:
        return f"WA{m.group(1)}P"
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", s)
    if m:
        return f"WA{m.group(1)}T{m.group(2)}"
    return "WAU"


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    """Append STD_COLUMNS to an unemployment frame (published columns untouched)."""
    out = drop_std(df, STD_COLUMNS)
    s = out.fillna("").astype(str)

    keys = list(zip(s["topic"], s["measure"], s["series_label"]))
    cache = {k: concept(*k) for k in set(keys)}
    out["category_code"] = [cache[k] for k in keys]

    ages = {a: age_code(a) for a in s["age_group"].unique()}
    out["age_code"] = s["age_group"].map(ages)
    # A youth rate is only an unemployment rate once its band is known.
    youth_unbanded = (s["topic"] == "youth_unemployment_rate") & ~out["age_code"].str.startswith("Y")
    out.loc[youth_unbanded, "category_code"] = ""
    out["category_std"] = out["category_code"].map(CODE_NAMES).fillna("")

    out["sex_code"] = s["sex"].map(_SEX).fillna("")
    out["education_code"] = s["education"].map(_education)
    geos = {g: geography_level(g) for g in s["geography"].unique()}
    out["geography_level"] = s["geography"].map(geos)

    uk = list(zip(s["unit"], s["iso3"]))
    uc = {k: unit_parts(*k) for k in set(uk)}
    out["currency"] = [uc[k][0] for k in uk]
    out["unit_multiplier"] = [uc[k][1] for k in uk]
    out["unit_std"] = [uc[k][2] for k in uk]
    v = pd.to_numeric(out["value"], errors="coerce")
    out["value_std"] = v * pd.to_numeric(out["unit_multiplier"], errors="coerce").fillna(1.0)

    ek = list(zip(textual(s["series_code"]), s["survey"], s["source_file"]))
    ec = {k: edition(*k) for k in set(ek)}
    out["edition"] = [ec[k] for k in ek]

    # The convention belongs to the SURVEY: Morocco's EMO says "contre revenu"
    # only on its employment labels, but its labour force and unemployment are
    # the same 19th-ICLS survey. One stated token spreads to the whole survey.
    ik = list(zip(s["survey"], s["series_label"]))
    ic = {k: icls(*k) for k in set(ik)}
    row_icls = pd.Series([ic[k] for k in ik], index=out.index)
    per_survey = (pd.DataFrame({"c": s["country"], "sv": s["survey"], "t": row_icls})
                  .query("t != ''").groupby(["c", "sv"])["t"].agg(lambda t: t.iloc[0] if t.nunique() == 1 else ""))
    survey_icls = pd.Series([per_survey.get((c, sv), "") for c, sv in zip(s["country"], s["survey"])],
                            index=out.index)
    tok = row_icls.where(row_icls != "", survey_icls)
    # Sex, age band and urban/rural are IN the ID: a place + date must hold one
    # value per series_id. Rows cut by a national education level get no ID
    # (the levels are not harmonised), as in labour.
    out["series_id"] = [
        safe_id("UNE", c, _DEF.get(d, ""), t, _base_token(w), _FREQ.get(f, ""),
                sx.lstrip("_") or "T", ag.lstrip("_"), locality_token(loc, ll))
        if (c and sx and ag and ed == "_T") else ""
        for c, d, t, w, f, sx, ag, ed, loc, ll in zip(
            out["category_code"], s["definition"], tok, s["working_age_base"], s["frequency"],
            out["sex_code"], out["age_code"], out["education_code"], s["locality"], s["locality_label"])]

    out["series_name"] = [
        join_name(CODE_NAMES[c], {"STRICT": "strict definition", "BROAD": "broad (relaxed) definition"}.get(
                      _DEF.get(d, ""), ""),
                  {"ICLS13": "13th ICLS standards", "ICLS19": "19th ICLS standards"}.get(t, t),
                  "working-age base not stated" if _base_token(w) == "WAU" else f"working-age base {w}",
                  FREQ_NAME.get(_FREQ.get(f, ""), f), sex_name(sx), age_name(ag),
                  locality_name(locality_token(loc, ll))) if sid else ""
        for sid, c, d, t, w, f, sx, ag, loc, ll in zip(
            out["series_id"], out["category_code"], s["definition"], tok, s["working_age_base"],
            s["frequency"], out["sex_code"], out["age_code"], s["locality"], s["locality_label"])]

    key = ["country", "series_id", "geography", "period"]
    out["_ed"] = out["edition"].map(edition_rank)
    out["_span"] = out.groupby(["country", "series_id", "series_label", "survey"])["period"].transform("nunique")
    # A label naming one sex while the sex column says the other is a parser
    # slip (Angola: "Taxa de desemprego - Homens" filed as female): no ID.
    lab = s["series_label"].map(norm)
    says_m = lab.str.contains(r"\b(?:homens|masculino|hommes|masculin|men|male)\b")
    says_f = lab.str.contains(r"\b(?:mulheres|feminino|femmes|feminin|women|female)\b")
    clash = (says_m & ~says_f & (s["sex"] == "female")) | (says_f & ~says_m & (s["sex"] == "male"))
    out.loc[clash, ["series_id", "series_name"]] = ""
    # The label is part of the TABLE identity: Kenya prints LU2 in Table 1 and
    # Table 6 with different values and labels; the preference rules decide.
    drop_conflicts(out, key, ["source_file", "survey", "series_label"])
    out["is_preferred"] = mark_preferred(out, key, ["_ed", "_span", "series_label"])
    out = out.drop(columns=["_ed", "_span"])
    return finish(out, STD_COLUMNS)
