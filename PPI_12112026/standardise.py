"""Standardised columns for the Producer Price Index, derived from the published ones.

series_id = PPI_[<variant>]_[PUB|PRIV]_[CUR_<basis>]_<industry>_<measure>_<base>_<freq>

  variant   ""  output (the standard PPI / IPPI: producers' output, all markets)
            DOM domestic market, EXP export, IMP import, FIN final goods,
            INT intermediate goods, AGR agricultural PPI, SRV services PPI,
            DCN commodities for domestic consumption (Stats SA pre-2012)
  PUB/PRIV  only when the NSO publishes the index by ownership sector (ONS Algeria)
  CUR_      only when the NSO publishes the same index in several currency
            bases (ZimStat: CUR_USD, CUR_ZWG, CUR_MIXED)
  industry  _T for the index's own total ("All industries", "Ensemble",
            "Overall Index", "ENSEMBLE (Indice Global IPPI)"); an ISIC Rev.4
            section letter (C) or a span of sections (BTE = B..E), from the
            NSO's printed code when it is a section, a section span or a
            division range on section boundaries ("05-39" -> BTE), else from
            the label via the GDP ISIC rules. Blank -- no ID -- for a narrower
            variant ("C hors raffinage", "Ensemble hors pétrole", "...*"), and
            for divisions and classes: NAEMA / NACE / ISIC Rev.3 / Rev.4
            divisions do not line up, so a division is never coded as a
            section ("08 Mining and Quarrying" is division 08, not section B).
  measure   INDEX, INFLATION_YOY, INFLATION_MOM, INFLATION_QOQ, INFLATION_AVG,
            INFLATION_YTD, INFLATION_YTD_AVG, WEIGHT
  base      B<year> from base_period ("2015=100" -> B2015): for a level, its
            base; for a weight, its reference; for a % change, the base of the
            index it is computed from (two editions on different bases print
            different changes for one month). BU for a level or weight whose
            base is not published; X for a change whose base is not stated.
  freq      M / Q / A

The TOTAL of one country's PPI covers what that NSO's index covers (Ghana's
includes services, most IPPIs only B..E): _T means "the whole index", and
index_name says which index.

value_std: weights on any printed scale (per mille, per ten thousand ...) are
put on the percent scale; everything else is unchanged.

is_preferred: among rows sharing an ID and period, the one from the NEWEST
SOURCE (the latest period its source file covers -- the latest bulletin
revises the months it republishes), then the latest extraction.
"""
from __future__ import annotations

import re

import pandas as pd

from core.standardise_base import (FREQ_NAME, drop_conflicts, drop_std, finish, join_name,
                                   mark_preferred, norm, safe_id, slug_name)
from .schema import WEIGHT_SCALE

STD_COLUMNS = ["industry_code", "base_year", "unit_std", "value_std",
               "series_id", "series_name", "is_preferred"]

_VARIANT = {"output": "", "domestic_market": "DOM", "export": "EXP", "import": "IMP",
            "final_goods": "FIN", "intermediate_goods": "INT", "agriculture": "AGR",
            "services": "SRV", "domestic_consumption": "DCN"}
_VARIANT_NAME = {"": "", "DOM": "domestic market", "EXP": "exported output",
                 "IMP": "imported products", "FIN": "final goods", "INT": "intermediate goods",
                 "AGR": "agriculture", "SRV": "services",
                 "DCN": "commodities for domestic consumption"}
_FREQ = {"monthly": "M", "quarterly": "Q", "annual": "A"}
_MEASURE_NAME = {"index": "index", "inflation_yoy": "change on a year earlier (%)",
                 "inflation_mom": "change on the previous month (%)",
                 "inflation_qoq": "change on the previous quarter (%)",
                 "inflation_avg": "change in the annual average (%)",
                 "inflation_ytd": "change since the start of the year (%)",
                 "inflation_ytd_avg": "change in the year-to-date average on a year earlier (%)",
                 "weight": "weight (%)"}
_TOTAL = re.compile(r"^(?:all industries|all industry|all groups|all items|total|grand total|total index|"
                    r"overall|overall index|ensemble|ensemble industrie|indice general|general index|"
                    r"indice global|indice global ippi|indice general ippi|indice d.?ensemble|"
                    r"geral|indice geral|total geral|industria total|total industria|total industrie|"
                    r"total industry|total industries|total de l.?industrie|"
                    r"final manufactured goods|intermediate manufactured goods)$")   # Stats SA FIN / INT headlines
# Labels the GDP rules do not carry (French / Portuguese sections, GSS typos,
# the headline of a narrower index that IS a section or span).
_LOCAL = {"electricity and gas": "D", "accommdation and food service": "I",   # GSS typo
          "accommodation and food service": "I",
          "water supply, sewerage, waste management": "E",
          "industries extractives": "B", "activites extractives": "B",
          "industries manufacturieres": "C", "activites de fabrication": "C",
          "industrie manufacturiere": "C", "industria transformadora": "C",
          "industrias extractivas": "B", "industria extractiva": "B",
          "manufacturing and utilities": "CTE",            # UBOS PPI-M&U headline = C+D+E
          "all hotels and restaurants": "I",               # UBOS PPI-H&R headline
          "mining": "B", "eau": "E"}
_NARROWER = re.compile(r"\*|exclud|\bhors\b|except|non compris|\bsauf\b|\bsans\b|\bex\.|other than|"
                       r"\bexcl\b", re.I)
# ISIC Rev.4 sections as division ranges. A printed division SPAN is mapped
# only when it starts and ends on section boundaries ("05-39" = B..E; NAEMA
# rev.1 agrees at this level). A single division never is, except where the
# section IS one division AND the label agrees (35 electricity, 68 real
# estate) -- "35" is other transport equipment in ISIC Rev.3.
_SECTIONS = [("A", 1, 3), ("B", 5, 9), ("C", 10, 33), ("D", 35, 35), ("E", 36, 39), ("F", 41, 43),
             ("G", 45, 47), ("H", 49, 53), ("I", 55, 56), ("J", 58, 63), ("K", 64, 66), ("L", 68, 68),
             ("M", 69, 75), ("N", 77, 82), ("O", 84, 84), ("P", 85, 85), ("Q", 86, 88), ("R", 90, 93),
             ("S", 94, 96)]
_ONE_DIVISION = {"D": re.compile(r"electri|energ|\bgaz\b|\bgas\b", re.I),
                 "L": re.compile(r"immobil|real estate|imobili", re.I)}
_YEAR = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")


def _span(a: str, b: str) -> str:
    return a if a == b else f"{a}T{b}"


def _section_from_code(c: str, label: str):
    """Section or span from the NSO's printed code; "" when the code is a
    division / group / class (the label must then not be read as the whole
    section); None when there is no code or it is not ISIC-like (Stats SA's
    "PI000002"), so the label decides."""
    if not c:
        return None
    if re.fullmatch(r"[A-U]", c):
        return c
    m = re.fullmatch(r"([A-U])(?:-|À|TO|A)([A-U])", c)
    if m and m.group(1) < m.group(2):
        return _span(m.group(1), m.group(2))
    if re.fullmatch(r"[A-U](?:\+?[A-U])+", c):
        letters = c.replace("+", "")
        run = "".join(chr(x) for x in range(ord(letters[0]), ord(letters[-1]) + 1))
        return _span(letters[0], letters[-1]) if run == letters else ""
    m = re.fullmatch(r"(\d{2})(?:[-–](\d{2}))?", c)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        first = next((x for x, a, _ in _SECTIONS if a == lo), None)
        last = next((x for x, _, b in _SECTIONS if b == hi), None)
        if not first or not last or first > last:
            return ""
        if lo == hi:
            rx = _ONE_DIVISION.get(first)
            return first if rx and rx.search(label) else ""
        return _span(first, last)
    if re.fullmatch(r"[A-U]?\d{2,6}(?:[-_+/][A-U]?\d{2,6})*", c):
        return ""
    return None


def industry_code(label: str, nso_code: str = "") -> str:
    from indicators.gdp.standardise import code_for_label   # one set of ISIC rules
    lab = str(label)
    if _NARROWER.search(lab):
        return ""                      # a narrower variant is not the section / total
    n = norm(lab)
    bare = re.sub(r"\s*\([^)]*\)", "", n).strip(" :-")     # "ensemble (indice global ippi)"
    if _TOTAL.match(n) or _TOTAL.match(bare):
        return "_T"                    # the index's own total, whatever code it prints ("05-39")
    if n in _LOCAL or bare in _LOCAL:
        return _LOCAL.get(n, _LOCAL.get(bare))
    if re.fullmatch(r"utilit(?:y|ies)(?: \(.*\))?", n):
        return ""       # electricity AND water: wider than the "D" NBS Tanzania once prints for it
    sec = _section_from_code(re.sub(r"\s+", "", str(nso_code or "")).upper(), lab)
    if sec is not None:
        return sec
    code = code_for_label(lab, "production")
    return code[3:] if code.startswith("VA_") and len(code) <= 6 else ""


def _industry_name(code: str) -> str:
    from indicators.gdp.standardise import CODE_NAMES
    if code == "_T":
        return "all industries covered"
    m = re.fullmatch(r"([A-U])T([A-U])", code)
    if m:
        return f"ISIC sections {m.group(1)} to {m.group(2)}"
    n = CODE_NAMES.get("VA_" + code, "")
    return n.replace("Value added: ", "") if n else f"ISIC {code}"


def _currency(basis: str) -> str:
    b = re.sub(r"[^A-Za-z0-9]+", "_", str(basis or "")).strip("_").upper()
    return f"CUR_{b}" if b else ""


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    out = drop_std(df, STD_COLUMNS)
    s = out.fillna("").astype(str)
    blank = pd.Series("", index=s.index)
    nso = s.get("industry_code_nso", blank)
    cache = {(l, c): industry_code(l, c) for l, c in set(zip(s["industry"], nso))}
    out["industry_code"] = [cache[(l, c)] for l, c in zip(s["industry"], nso)]
    out["base_year"] = s["base_period"].str.extract(_YEAR)[0].fillna("")
    v = pd.to_numeric(out["value"], errors="coerce")
    scale = s["unit"].map(WEIGHT_SCALE)
    w = (s["measure"] == "weight") & scale.notna() & (s["unit"] != "percent")
    out["value_std"] = v.where(~w, (v * 100 / scale).round(10))
    out["unit_std"] = s["unit"].where(~w, "percent")

    variant = s.get("index_variant", blank).map(lambda x: _VARIANT.get(x or "output"))
    cur = s.get("currency_basis", blank).map(_currency)
    own = s.get("ownership", blank).map({"public": "PUB", "private": "PRIV"}).fillna("")
    ids, names = [], []
    for ind, var, ow, cu, meas, by, fq in zip(out["industry_code"], variant, own, cur, s["measure"],
                                              out["base_year"], s["frequency"].map(_FREQ).fillna("")):
        if not ind or var is None or not fq or meas not in _MEASURE_NAME:
            ids.append("")
            names.append("")
            continue
        base = f"B{by}" if by else ("BU" if meas in ("index", "weight") else "X")
        ids.append(safe_id("PPI", var, ow, cu, ind, meas.upper(), base, fq))
        names.append(join_name(
            "Producer price index" + (f", {_VARIANT_NAME[var]}" if var else "")
            + ({"PUB": ", public sector", "PRIV": ", private sector"}.get(ow, ""))
            + (f", {cu[4:].lower() if cu == 'CUR_MIXED' else cu[4:]} basis" if cu else "")
            + ", " + _industry_name(ind),
            _MEASURE_NAME.get(meas, slug_name(meas)),
            ("base not stated" if base == "BU" else f"base {by} = 100") if meas == "index"
            else (f"base {by}" if by else ""),
            FREQ_NAME.get(fq, fq)))
    out["series_id"], out["series_name"] = ids, names
    # One file printing two values for one ID and month (Uganda 2024-12:
    # MANUFACTURING 124.9334 on one sheet, MANUFACTURING [C] 124.9259 on
    # another) is a conflict however small: no ID rather than an arbitrary pick.
    drop_conflicts(out, ["country", "series_id", "period"], ["source_file", "index_name"], tol=1e-9)
    src = s.get("source_file", blank)
    per = s["period"].str[:4] + s["period"].str[4:].str.replace(r"\D", "", regex=True).str.zfill(2)
    vintage = per.groupby([s["country"], src]).transform("max")
    out["is_preferred"] = mark_preferred(
        out.assign(_c=s["country"], _p=s["period"], _v=vintage, _x=s.get("extracted_at", blank)),
        ["_c", "series_id", "_p"], ["_v", "_x"])
    return finish(out, STD_COLUMNS)
