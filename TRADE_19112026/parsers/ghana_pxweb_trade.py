"""Parser for Ghana GSS StatsBank merchandise trade (PxWeb, Tier 1).

Input: the descriptor's `api.tables`, each a saved json-stat2 response from
  trade_detail_hs2.px  Valuation_Parameter x Tradeflow x Year x Month x HS_2_digit x Partner_Country
  trade_general.px     Valuation_Parameter x Tradeflow x Year x Month x Product_Classification x Partner_Country
The descriptor asks for the commodity cut (every HS chapter / every GSS product
group, all partners) and the partner cut (all products, every partner, one
query per year -- the API refuses the five-year partner query with 403).

Every cell is emitted as published: "All Months" is the annual figure, a month
name the monthly one; nominal cedis are current prices, "real" cedis constant
prices (GSS does not print the base year in the table); net weight in kg.
GSS's partner list mixes countries with a few non-country lines
("Unknown", "Free Zones" ...) -- those are partner_type "group".
"""
from __future__ import annotations

import json
import os

import pandas as pd

from ._common import row

_FLOW = {"Total Trade": "total", "Export": "export", "Import": "import"}
_VALUATION = {   # -> measure, unit, prices
    "Value in Ghana Cedis (nominal)": ("value", "GHS", "current"),
    "Value in Ghana Cedis (real)": ("value", "GHS", "constant"),
    "Value in US Dollars": ("value", "USD", "current"),
    "Net weight in KG": ("net_weight", "kg", "current"),
}
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]
_COMMODITY_DIM = {"HS_2_digit": "hs2", "Product_Classification": "national"}
# GSS partner lines that are not a country or territory.
_NOT_COUNTRY = {"unknown", "free zones", "not specified", "other countries", "stores and provisions",
                "ships stores", "bunkers", "special categories", "areas nes", "others"}


def _cells(d: dict):
    dims, sizes, values = d["id"], d["size"], d["value"]
    pos = {dim: {p: c for c, p in d["dimension"][dim]["category"]["index"].items()} for dim in dims}
    items = values.items() if isinstance(values, dict) else enumerate(values)
    for flat, val in items:
        if val is None:
            continue
        flat, coords = int(flat), []
        for size in reversed(sizes):
            coords.append(flat % size)
            flat //= size
        coords.reverse()
        yield {dim: pos[dim][coords[i]] for i, dim in enumerate(dims)}, val


def _parse_table(path: str, table_id: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    cdim = next(k for k in _COMMODITY_DIM if k in d["id"])
    cls = _COMMODITY_DIM[cdim]
    rows = []
    for c, val in _cells(d):
        flow = _FLOW.get(str(c["Tradeflow"]).strip())
        valu = _VALUATION.get(str(c["Valuation_Parameter"]).strip())
        if flow is None or valu is None:
            continue
        measure, unit, prices = valu
        year, month = str(c["Year"]).strip(), str(c["Month"]).strip()
        if month.lower().startswith("all"):
            period, freq = year, "annual"
        elif month in _MONTHS:
            period, freq = f"{year}-{_MONTHS.index(month) + 1:02d}", "monthly"
        else:
            raise ValueError(f"ghana_pxweb_trade: unknown month {month!r}")
        com = str(c[cdim]).strip()
        commodity = None if com.lower() == "all products" else com
        code = com[:2] if cls == "hs2" and com[:2].isdigit() else ""
        par = str(c["Partner_Country"]).strip()
        if par.lower() == "all partner countries":
            partner, ptype = None, "world"
        else:
            partner, ptype = par, ("group" if par.lower() in _NOT_COUNTRY else "country")
        rows.append(row(tradeflow=flow, period=period, frequency=freq, value=val, unit=unit,
                        commodity=commodity, commodity_classification=cls if commodity else "",
                        commodity_code_nso=code, partner=partner, partner_type=ptype,
                        measure=measure, prices=prices, series_code=table_id))
    return rows


def parse(tables) -> pd.DataFrame:
    if isinstance(tables, str):                     # a single saved table
        tables = [{"path": tables, "table_url": tables}]
    rows = []
    for t in tables:
        table_id = os.path.basename(t["table_url"]).replace(".px", "")
        rows += _parse_table(t["path"], table_id)
    if not rows:
        raise ValueError("ghana_pxweb_trade: no rows decoded")
    df = pd.DataFrame.from_records(rows)
    # The all-products, all-partners totals are in every table. Keep them from
    # trade_general (the newer table, with the current year); the HS2 table's
    # copies would only duplicate them.
    tot = (df["commodity"] == "All products") & (df["partner"] == "All partners")
    if (tot & (df["series_code"] == "trade_general")).any():
        df = df[~(tot & (df["series_code"] != "trade_general"))]
    return df.reset_index(drop=True)
