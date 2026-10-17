"""Parser for Ghana GSS StatsBank public debt (PxWeb, Tier 1).

Input is the saved json-stat2 table debt_data.px, with dimensions Month (YYYYMmm)
and Variable (the debt component). We emit one tidy row per (component, month) as a
debt stock. Values are in US$ million (Total public debt 2024M06 = 50,929.4 ≈
US$50.9 billion), kept as published.
"""
from __future__ import annotations
import json
import re
import pandas as pd

_MONTH_RE = re.compile(r"^(\d{4})M(\d{2})$")
_UNIT = "USD million"


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
        rows.append({
            "component": str(codes["Variable"]).strip(),
            "period": f"{m.group(1)}-{m.group(2)}", "frequency": "monthly",
            "measure": "stock", "value": float(val), "unit": _UNIT,
            "series_code": "debt_data",
        })
    if not rows:
        raise ValueError("ghana_pxweb_debt: no rows decoded")
    return pd.DataFrame.from_records(rows)
