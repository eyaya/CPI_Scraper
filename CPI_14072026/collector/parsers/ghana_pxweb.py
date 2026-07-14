"""Parser for Ghana GSS StatsBank CPI (PxWeb, Tier 1).

Input is the saved json-stat2 response of the cpi.px table. Dimensions:
Indicator (CPI / YoY / MoM), Month (YYYYMmm), Region, Product (COICOP-2018),
Source. We map Product -> COICOP code, Indicator -> measure, and emit tidy rows
for the national region ('Ghana').
"""
from __future__ import annotations
import json
import pandas as pd

from ..coicop import code_for_label

_MEASURE = {
    "Consumer Price Index": ("index", "Index"),
    "Year-on-year inflation (%)": ("inflation_yoy", "percent"),
    "Month-on-month inflation (%)": ("inflation_mom", "percent"),
}


def _decode_coords(flat: int, sizes: list[int]) -> list[int]:
    coords = []
    for i in range(len(sizes)):
        stride = 1
        for s in sizes[i + 1:]:
            stride *= s
        coords.append(flat // stride % sizes[i])
    return coords


def parse(json_path: str) -> pd.DataFrame:
    with open(json_path, "r", encoding="utf-8") as f:
        d = json.load(f)

    dims = d["id"]
    sizes = d["size"]
    values = d["value"]
    # position -> code, and code -> label, per dimension
    pos2code, code2label = {}, {}
    for dim in dims:
        cat = d["dimension"][dim]["category"]
        pos2code[dim] = {p: c for c, p in cat["index"].items()}
        code2label[dim] = cat.get("label", {})

    # json-stat2 value may be a list (with nulls) or a sparse dict
    items = values.items() if isinstance(values, dict) else enumerate(values)

    records = []
    for flat, val in items:
        if val is None:
            continue
        flat = int(flat)
        coords = _decode_coords(flat, sizes)
        codes = {dim: pos2code[dim][coords[i]] for i, dim in enumerate(dims)}

        measure_info = _MEASURE.get(codes["Indicator"])
        if measure_info is None:
            continue
        measure, unit = measure_info

        coicop = code_for_label(codes["Product"])
        if coicop is None:            # skip aggregates (Food, Non-food)
            continue

        ym = codes["Month"]           # 'YYYYMmm'
        period = ym.replace("M", "-")

        records.append({
            "coicop_code": coicop,
            "coicop_label": code2label["Product"].get(codes["Product"], codes["Product"]),
            "geography": "National",  # Region == 'Ghana'
            "period": period,
            "measure": measure,
            "value": float(val),
            "unit": unit,
        })

    out = pd.DataFrame.from_records(records)
    out["base_period"] = ""
    out["frequency"] = "monthly"
    return out
