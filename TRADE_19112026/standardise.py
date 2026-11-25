"""Standardised (cross-country) columns for Merchandise Trade.

Appended after the published columns, recomputed from them on every write:

  commodity_code  "All products" -> _T; HS chapters/headings/subheadings ->
                  HS2_27 / HS4_2709 / HS6_270900; SITC sections/divisions/groups
                  -> SITC1_3 / SITC2_33 / SITC3_333. From the NSO's printed
                  code, or a code leading the label ("27 - Mineral fuels ...").
                  BEC and national product lists stay blank: their groupings
                  differ by country, so a shared code would claim a match that
                  is not there.
  partner_code    "All partners" -> _W; a country -> its ISO 3166 alpha-3 code
                  from partners.csv (the NSOs' own spellings, English/French/
                  Portuguese); a group (ECOWAS, "Europe") or an unknown label
                  stays blank.
  currency        the ISO 4217 code of a value row; blank for weights/quantities.
  unit_std        the currency, "kg" for a net weight, the NSO's unit for a quantity.
  value_std       value x unit_multiplier (and x 1000 for tonnes -> kg): the ONLY
                  column that converts a scale.
  series_id       TRADE_<flow>_<commodity>_<partner>_<unit>[_FOB|_CIF][_CONST][_GEN|_SPE]_<M|Q|A>,
                  e.g. TRADE_EXPORT_HS2_18_FRA_XOF_FOB_M. Blank when the commodity
                  or partner has no code (a national product, a bloc) or the row
                  is a quantity: those stay as published, unidentified.
  series_name     built from the codes alone -- the English HS chapter / SITC
                  section or division title (commodity_names.csv; HS headings and
                  SITC groups by code only) and the partner's English name
                  (first spelling in partners.csv) -- so one ID has one name.
  is_preferred    one row per (country, series_id, period): the newest source --
                  the file whose latest period is latest (a revised figure in a
                  newer bulletin replaces the provisional one) -- then the latest
                  extraction.
"""
from __future__ import annotations

import csv
import os
import re

import pandas as pd

from core.standardise_base import (FREQ_NAME, currency_name, drop_conflicts, drop_std, finish,
                                   join_name, mark_preferred, norm, safe_id)

STD_COLUMNS = ["commodity_code", "partner_code", "currency", "unit_std", "value_std",
               "series_id", "series_name", "is_preferred"]

_FREQ = {"monthly": "M", "quarterly": "Q", "annual": "A"}
_FLOW_NAME = {"export": "Exports", "domestic_export": "Domestic exports", "re_export": "Re-exports",
              "import": "Imports", "total": "Total trade", "balance": "Trade balance"}
_CODE_DIGITS = {"hs2": ("HS2", 2), "hs4": ("HS4", 4), "hs6": ("HS6", 6),
                "sitc1": ("SITC1", 1), "sitc2": ("SITC2", 2), "sitc3": ("SITC3", 3)}
_LEADING_CODE = re.compile(r"^\s*(\d{1,6})\s*[-–:.)]?\s+\D")
# Currency names for series_name (codes not here fall back to core's names).
_CURRENCY = {"XOF": "CFA francs (XOF)", "XAF": "CFA francs (XAF)", "ZAR": "rand", "NGN": "naira",
             "GHS": "cedis", "KES": "Kenya shillings", "UGX": "Uganda shillings", "TZS": "Tanzania shillings",
             "RWF": "Rwanda francs", "BIF": "Burundi francs", "ETB": "birr", "EGP": "Egyptian pounds",
             "MAD": "dirhams", "TND": "Tunisian dinars", "DZD": "Algerian dinars", "LYD": "Libyan dinars",
             "MUR": "Mauritius rupees", "SCR": "Seychelles rupees", "MGA": "ariary", "KMF": "Comorian francs",
             "BWP": "pula", "NAD": "Namibia dollars", "LSL": "maloti", "SZL": "emalangeni", "ZMW": "kwacha (ZMW)",
             "MWK": "kwacha (MWK)", "MZN": "meticais", "AOA": "kwanzas", "ZWG": "Zimbabwe gold (ZWG)",
             "SLE": "leones (SLE)", "LRD": "Liberian dollars", "GMD": "dalasis", "CVE": "Cabo Verde escudos",
             "MRU": "ouguiyas (MRU)", "GNF": "Guinea francs", "CDF": "Congolese francs", "STN": "dobras (STN)",
             "DJF": "Djibouti francs", "SOS": "Somali shillings", "SSP": "South Sudanese pounds",
             "SDG": "Sudanese pounds", "ERN": "nakfa"}


def _currency_name(code: str) -> str:
    return _CURRENCY.get(code) or currency_name(code)


_PARTNERS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "partners.csv")


def commodity_code(label: str, classification: str, nso_code: str = "") -> str:
    if label == "All products" and not classification:
        return "_T"
    spec = _CODE_DIGITS.get(classification)
    if not spec:
        return ""
    prefix, digits = spec
    code = re.sub(r"\s", "", str(nso_code or ""))
    if not code:
        m = _LEADING_CODE.match(str(label))
        code = m.group(1) if m else ""
    # HS codes are zero-padded ("1" is chapter 01); SITC codes are not.
    if prefix.startswith("HS") and code.isdigit() and len(code) == digits - 1:
        code = "0" + code
    return f"{prefix}_{code}" if code.isdigit() and len(code) == digits else ""


def _partner_key(label: str) -> str:
    """Letters and digits only: 'Cote dIvoire', "Côte d'Ivoire" and 'COTE D'IVOIRE' meet.
    A trailing "(pays)" (INSEED Togo: "Chypre(pays)") and doubled "États-Unis
    d'Amérique (potorico" truncations are spelling noise, not part of the name."""
    s = re.sub(r"\(\s*pays\s*\)\s*$", "", norm(label))
    return re.sub(r"[^a-z0-9]", "", s)


def _load_partners() -> dict:
    """key -> ISO3, from partners.csv (iso3, name; one row per spelling). A
    spelling claimed by two codes is a table error and fails loudly."""
    if not os.path.exists(_PARTNERS_CSV):
        return {}
    table: dict = {}
    with open(_PARTNERS_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            k = _partner_key(r["name"])
            if table.get(k, r["iso3"]) != r["iso3"]:
                raise ValueError(f"partners.csv: {r['name']!r} is both {table[k]} and {r['iso3']}")
            table[k] = r["iso3"]
    return table


_PARTNERS = _load_partners()


def _load_iso2() -> dict:
    p = os.path.join(os.path.dirname(_PARTNERS_CSV), "partners_iso2.csv")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return {r["iso2"]: r["iso3"] for r in csv.DictReader(f)}


_ISO2 = _load_iso2()
# An alpha-2 code printed alone ("UG", NBS South Sudan) or leading the name
# ("AT:AUSTRIA", NSA Namibia). Upper case only: "Mali" must not read as "MA".
_ISO2_LEAD = re.compile(r"^([A-Z]{2})(?::|$)")


def partner_code(label: str, partner_type: str) -> str:
    if partner_type == "world":
        return "_W"
    if partner_type != "country":
        return ""
    label = str(label).strip()
    m = _ISO2_LEAD.match(label)
    if m and m.group(1) in _ISO2:
        return _ISO2[m.group(1)]
    name = label.split(":", 1)[1] if m and ":" in label else label    # "UK" is not alpha-2: a name
    return _PARTNERS.get(_partner_key(name), "")


def _load_names(fname: str, key: str) -> dict:
    p = os.path.join(os.path.dirname(_PARTNERS_CSV), fname)
    out: dict = {}
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out.setdefault(r[key], r["name"])        # partners.csv: the first spelling is English
    return out


# Names come from the CODES, never the printed labels: one ID is one series across
# countries, and Ghana's "Live animals", Chad's "Animaux vivants" and Tanzania's
# "LIVE ANIMALS" (or a label wrapped across PDF lines) must not give it three names.
_COMMODITY_NAMES = _load_names("commodity_names.csv", "code")    # HS chapters, SITC sections/divisions
_PARTNER_NAMES = _load_names("partners.csv", "iso3")


def _commodity_name(code: str) -> str:
    if code == "_T":
        return "all products"
    kind, c = code.split("_", 1)
    noun = {"HS2": "HS chapter", "HS4": "HS heading", "HS6": "HS subheading",
            "SITC1": "SITC section", "SITC2": "SITC division", "SITC3": "SITC group"}[kind]
    text = _COMMODITY_NAMES.get(code, "")
    return f"{noun} {c}" + (f" ({text})" if text else "")


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    out = drop_std(df, STD_COLUMNS)
    s = out.fillna("").astype(str)
    blank = pd.Series("", index=s.index)
    cls, nso = s.get("commodity_classification", blank), s.get("commodity_code_nso", blank)
    cache = {k: commodity_code(*k) for k in set(zip(s["commodity"], cls, nso))}
    out["commodity_code"] = [cache[k] for k in zip(s["commodity"], cls, nso)]
    ptype = s.get("partner_type", blank)
    pcache = {k: partner_code(*k) for k in set(zip(s["partner"], ptype))}
    out["partner_code"] = [pcache[k] for k in zip(s["partner"], ptype)]

    meas, unit = s["measure"], s["unit"]
    out["currency"] = unit.where(meas == "value", "")
    out["unit_std"] = unit.where(unit != "tonnes", "kg")
    mult = pd.to_numeric(out["unit_multiplier"], errors="coerce").fillna(1.0)
    mult = mult.where(unit != "tonnes", mult * 1000)
    out["value_std"] = (pd.to_numeric(out["value"], errors="coerce") * mult).round(6)

    basis = s.get("price_basis", blank).str.upper()
    const = s.get("prices", blank).map({"constant": "CONST"}).fillna("")
    system = s.get("trade_system", blank).map({"general": "GEN", "special": "SPE"}).fillna("")
    ids, names = [], []
    for fl, cc, pc, me, un, ba, co, sy, fq in zip(
            s["tradeflow"], out["commodity_code"], out["partner_code"], meas, out["unit_std"], basis,
            const, system, s["frequency"].map(_FREQ).fillna("")):
        if not cc or not pc or me == "quantity" or not fq or fl not in _FLOW_NAME:
            ids.append("")
            names.append("")
            continue
        ids.append(safe_id("TRADE", fl, cc, pc, "KG" if me == "net_weight" else un, ba, co, sy, fq))
        where = "" if pc == "_W" else (" to " if fl in ("export", "domestic_export", "re_export")
                                       else " from " if fl == "import" else " with ") + _PARTNER_NAMES.get(pc, pc)
        names.append(join_name(
            f"{_FLOW_NAME[fl]}, {_commodity_name(cc)}{where}",
            "net weight, kilograms" if me == "net_weight" else "value, " + _currency_name(un),
            ba, "constant prices" if co else "",
            {"GEN": "general trade system", "SPE": "special trade system"}.get(sy, ""),
            FREQ_NAME.get(fq, fq)))
    out["series_id"], out["series_name"] = ids, names
    # One file giving two values for one ID and period is a lost dimension,
    # not a revision: no ID rather than an arbitrary pick.
    drop_conflicts(out, ["country", "series_id", "period"], ["source_file", "series_code"],
                   tol=1e-6)
    src = s.get("source_file", blank)
    per = s["period"].str[:4] + s["period"].str[4:].str.replace(r"\D", "", regex=True).str.zfill(2)
    vintage = per.groupby([s["country"], src]).transform("max")
    out["is_preferred"] = mark_preferred(
        out.assign(_c=s["country"], _p=s["period"], _v=vintage, _x=s.get("extracted_at", blank)),
        ["_c", "series_id", "_p"], ["_v", "_x"])
    return finish(out, STD_COLUMNS)
