"""Parser for South Sudan NBS "SS Trade Data" workbooks (Tier 2 Excel).

NBS (www.nbs.gov.ss, statistics/Trade_Statistics.php) publishes one workbook
per year (2022, 2023, 2024) in a long, SDMX-like layout:

    Reporter | Date (2022M1) | Trade Flow | Commodity | Partner | Indicator | Unit | Value

-- one line per 8-digit tariff line x partner (ISO 3166 alpha-2 code) x month
x indicator. It is the ONLY trade table NBS publishes: no totals, no HS
chapters, no partner totals (and nothing may be summed here), so the cells
are emitted as published:

  commodity              the 8-digit code as printed (no description is given);
                         classification "national" (the national tariff line,
                         finer than HS6), commodity_code_nso = the same code.
                         Codes that are not 8 digits (2024: 27 x 4-digit,
                         12 x 2-digit, 5 x 16-digit) are skipped.
  partner                the alpha-2 code as printed ("UG", "KE"); type country.
  Trade Flow             I -> import, E -> export, RE/Re -> re_export.
                         RI/Ri (re-imports) are not in the schema and skipped.
  Indicator              F_VALUE_CIF_USD -> value USD cif; F_VALUE_FOB_USD ->
                         value USD fob; F_VALUE_NET -> net_weight kg.
                         F_VALUE_QUANTITY (unit "None") is skipped.
A key printed twice with different values (2023: 327 lines -- two lines for
one tariff line/partner/month) is dropped entirely: they cannot be told apart
and must not be added up.
"""
from __future__ import annotations

import re

import pandas as pd

from ._common import row, to_number

_FLOW = {"I": "import", "E": "export", "RE": "re_export"}
_IND = {"F_VALUE_CIF_USD": ("value", "USD", "cif"), "F_VALUE_FOB_USD": ("value", "USD", "fob"),
        "F_VALUE_NET": ("net_weight", "kg", "")}


def _one(path):
    df = pd.read_excel(path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    out = []
    for r in df.itertuples(index=False):
        rec = dict(zip(df.columns, r))
        flow = _FLOW.get(str(rec["Trade Flow"]).strip().upper())
        ind = _IND.get(str(rec["Indicator"]).strip().upper())
        code = str(rec["Commodity"]).strip()
        par = str(rec["Partner"]).strip()
        m = re.fullmatch(r"(\d{4})M(\d{1,2})", str(rec["Date"]).strip())
        if not (flow and ind and m and re.fullmatch(r"\d{8}", code) and re.fullmatch(r"[A-Za-z]{2}", par)):
            continue
        val = to_number(rec["Value"])
        if val is None:
            continue
        measure, unit, pb = ind
        out.append(row(tradeflow=flow, period=f"{m.group(1)}-{int(m.group(2)):02d}", frequency="monthly",
                       value=val, unit=unit, measure=measure, price_basis=pb, commodity=code,
                       commodity_classification="national", commodity_code_nso=code,
                       partner=par, partner_type="country", series_code="SS Trade Data"))
    o = pd.DataFrame(out)
    if o.empty:
        return o
    key = ["tradeflow", "commodity", "partner", "period", "measure", "unit", "price_basis"]
    g = o.groupby(key)["value"].transform("nunique")
    return o.loc[g == 1].drop_duplicates(key).reset_index(drop=True)


def parse(path, extras=None):
    files = sorted([path] + list(extras or []))
    return pd.concat([_one(f) for f in files], ignore_index=True)
