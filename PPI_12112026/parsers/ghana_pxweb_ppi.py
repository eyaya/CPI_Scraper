"""Parser for Ghana GSS StatsBank Producer Price Index (PxWeb, Tier 1).

Input is the saved json-stat2 table ppi.px, with dimensions Month (YYYYMmm),
Indicator (the PPI level / YoY change / MoM change) and Industry. We emit one tidy
row per (industry, month, measure), with the GSS month code YYYYMmm normalised to
YYYY-MM. Emitted as published.

The table carries no base period (no note, no extension). GSS's own April
2025 PPI newsletter (Wayback copy, source_data/Ghana/gss_ppi_newsletter_2025-04.pdf)
states "index reference of March 2020 - February 2021 = 100", and EVERY
industry in the table, the 2006 back-series and starred groups included,
averages 100.0 over those twelve months (99.99-100.00) -- so it is set as
the base of every row (a % change carries the base of the index it is
computed from). The starred industries ("...
(excluding petroleum)*", "Water collection, treatment and supply*") are the
older, narrower groups GSS prints beside the current ones; they stay as
published and get no ISIC code.
"""
from __future__ import annotations
import json
import re
import pandas as pd

_MEASURE = {
    "Producer Price Index": ("index", "index"),
    "Year-on-year PPI change (%)": ("inflation_yoy", "percent"),
    "Month-on-month PPI change (%)": ("inflation_mom", "percent"),
}
BASE = "March 2020 - February 2021=100"
_MONTH_RE = re.compile(r"^(\d{4})M(\d{2})$")


def _decode_coords(flat: int, sizes: list[int]) -> list[int]:
    coords = []
    for i in range(len(sizes)):
        stride = 1
        for s in sizes[i + 1:]:
            stride *= s
        coords.append(flat // stride % sizes[i])
    return coords


def parse(local_path: str) -> pd.DataFrame:
    with open(local_path, "r", encoding="utf-8") as f:
        d = json.load(f)
    dims, sizes, values = d["id"], d["size"], d["value"]
    pos2code = {}
    for dim in dims:
        cat = d["dimension"][dim]["category"]
        pos2code[dim] = {p: c for c, p in cat["index"].items()}

    items = values.items() if isinstance(values, dict) else enumerate(values)
    rows = []
    for flat, val in items:
        if val is None:
            continue
        coords = _decode_coords(int(flat), sizes)
        codes = {dim: pos2code[dim][coords[i]] for i, dim in enumerate(dims)}

        m = _MONTH_RE.match(str(codes["Month"]).strip())
        if not m:
            continue
        period = f"{m.group(1)}-{m.group(2)}"
        meas = _MEASURE.get(str(codes["Indicator"]).strip())
        if meas is None:
            continue
        measure, unit = meas

        rows.append({
            "index_name": "Producer Price Index (PPI)", "index_variant": "output",
            "industry": str(codes["Industry"]).strip(), "industry_code_nso": "",
            "period": period, "frequency": "monthly",
            "measure": measure, "value": float(val), "unit": unit,
            "base_period": BASE, "series_code": "ppi",   # a change carries its index's base
        })
    if not rows:
        raise ValueError("ghana_pxweb_ppi: no rows decoded")
    return pd.DataFrame.from_records(rows)
