"""Standardised columns for CPI, derived from the published ones.

CPI already carries a standard code (`coicop_code`), so the work here is not
label mapping but two traps a consumer would otherwise fall into:

1. THE SAME CODE CHANGES MEANING AT A REBASE. COICOP 1999 has 12 divisions,
   COICOP 2018 has 13, and four of them moved: 12 is "Miscellaneous goods and
   services" in 1999 but "Insurance and financial services" in 2018 (whose 13
   is "Personal care, social protection and miscellaneous"), 08 widened from
   "Communication" to "Information and communication", 09 added sport. Mali,
   Mauritius, Nigeria, Togo and Guinea-Bissau publish code 12 with the 1999
   meaning up to their rebase and the 2018 meaning after it, under ONE merge
   key -- a chart of "division 12" would splice two different things. So
   `coicop_version` is decided PER ROW: for 12 by its own label, for 08/09/13
   by whether that country-month publishes a division 13. Divisions whose
   content did not materially change (00-07, 10, 11) carry no version.

2. INDEX LEVELS ARE ONLY COMPARABLE WITHIN ONE BASE. The base year is part of
   an index's series_id, so a rebased series never shares an ID with the old
   one. An index whose base the source does not print gets base token "BU"
   (base unstated): separate from every printed base, never guessed. Index
   levels are never comparable ACROSS countries -- cross-country views should
   use inflation_yoy / inflation_mom.

Columns (appended; published columns untouched):
  coicop_version  C1999 | C2018 | "" (version-neutral division)
  coicop_std      English COICOP name for the code in that version
  base_year       first year of the printed base ("Dec 2005 = 100" -> 2005)
  geography_level national | subnational
  unit_std        index | percent
  series_id       e.g. CPI_00_INFLATION_YOY_M, CPI_C2018_12_INDEX_B2023_M
  is_preferred    True on one row per (country, series_id, geography, period)
"""
from __future__ import annotations

import re

import pandas as pd

from core.standardise_base import (FREQ_NAME, drop_std, finish, geography_level, join_name,
                                   mark_preferred, norm, safe_id)

STD_COLUMNS = ["coicop_version", "coicop_std", "base_year", "geography_level",
               "unit_std", "series_id", "series_name", "is_preferred"]

_VERSIONED = {"08", "09", "12", "13"}

_NAMES = {
    "00": "All items",
    "01": "Food and non-alcoholic beverages",
    "02": "Alcoholic beverages, tobacco and narcotics",
    "03": "Clothing and footwear",
    "04": "Housing, water, electricity, gas and other fuels",
    "05": "Furnishings, household equipment and routine household maintenance",
    "06": "Health",
    "07": "Transport",
    "10": "Education",
    "11": "Restaurants and accommodation services",
    ("C1999", "08"): "Communication",
    ("C1999", "09"): "Recreation and culture",
    ("C1999", "12"): "Miscellaneous goods and services",
    ("C2018", "08"): "Information and communication",
    ("C2018", "09"): "Recreation, sport and culture",
    ("C2018", "12"): "Insurance and financial services",
    ("C2018", "13"): "Personal care, social protection and miscellaneous goods and services",
}

_MISC = re.compile(r"divers|misc|diversos")
_FIN = re.compile(r"insurance|assurance|financ|seguros?")


def _base_year(base_period: str) -> str:
    m = re.search(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)", base_period or "")
    return m.group(1) if m else ""


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    out = drop_std(df, STD_COLUMNS)
    s = out.fillna("").astype(str)
    div = s["coicop_code"].str.slice(0, 2)

    # A country-month on COICOP 2018 publishes division 13.
    has13 = (div == "13").groupby([s["country"], s["period"]]).transform("any")
    lab = s["coicop_label"].map(norm)
    version = pd.Series("", index=out.index)
    versioned = div.isin(_VERSIONED)
    version[versioned] = has13[versioned].map({True: "C2018", False: "C1999"})
    is12 = div == "12"
    version[is12 & lab.str.contains(_MISC) & ~lab.str.contains(_FIN)] = "C1999"
    version[is12 & lab.str.contains(_FIN)] = "C2018"
    version[div == "13"] = "C2018"
    out["coicop_version"] = version

    def name(code, ver):
        d = code[:2]
        n = _NAMES.get((ver, d)) if ver else _NAMES.get(d)
        if not n:
            return ""
        return n if code == d else f"{n} (sub-class {code})"
    out["coicop_std"] = [name(c, v) for c, v in zip(s["coicop_code"], version)]

    out["base_year"] = s["base_period"].map(_base_year)
    out["geography_level"] = s["geography"].map(geography_level)
    out["unit_std"] = s["unit"].map(lambda u: "index" if norm(u) == "index" else
                                    "percent" if norm(u) == "percent" else "")

    sid, sname = [], []
    for code, ver, meas, by, freq, cname in zip(s["coicop_code"], version, s["measure"],
                                                out["base_year"], s["frequency"], out["coicop_std"]):
        if not code or not cname:
            sid.append("")
            sname.append("")
            continue
        base = (f"B{by}" if by else "BU") if meas == "index" else ""
        sid.append(safe_id("CPI", ver, code.replace(".", "_"), meas, base,
                           {"monthly": "M", "quarterly": "Q", "annual": "A"}.get(freq, freq)))
        f = {"monthly": "M", "quarterly": "Q", "annual": "A"}.get(freq, freq)
        sname.append(join_name(
            f"Consumer price index, {cname[:1].lower() + cname[1:]}"
            + {"C1999": " (COICOP 1999)", "C2018": " (COICOP 2018)"}.get(ver, ""),
            {"index": "index", "inflation_yoy": "inflation on a year earlier (%)",
             "inflation_mom": "inflation on the previous month (%)"}.get(meas, meas.replace("_", " ")),
            (f"base {by} = 100" if by else "base not stated") if meas == "index" else "",
            FREQ_NAME.get(f, freq)))
    out["series_id"] = sid
    out["series_name"] = sname
    out["is_preferred"] = mark_preferred(out.assign(_c=s["country"], _g=s["geography"], _p=s["period"]),
                                         ["_c", "series_id", "_g", "_p"], ["_p"])
    return finish(out, STD_COLUMNS)
