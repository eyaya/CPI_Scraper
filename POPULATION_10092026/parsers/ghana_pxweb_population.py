"""Parser for Ghana GSS StatsBank population projections (PxWeb, Tier 1).

Input is one saved json-stat2 table (projections.px) with five dimensions:
`Year` (2021-2050), `Geographic_Area` (Ghana + 16 regions), `Age` (the all-ages
total + 18 five-year bands, as selected in the descriptor), `Sex` (Both sexes /
Male / Female) and `Locality` (fixed to the all-localities total in v1).

Every cell is a population head count published by GSS — the all-ages and
both-sexes figures are GSS's own totals, emitted as published, not summed here.
We only normalise the controlled-vocabulary labels: the national area "Ghana" ->
"Total country", "Both sexes" -> total, "All ages" -> the "Total" sentinel.
"""
from __future__ import annotations
import json
import re
import pandas as pd

_SEX = {"Both sexes": "total", "Male": "male", "Female": "female"}
_YEAR_RE = re.compile(r"^\d{4}$")


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

        year = str(codes["Year"]).strip()
        if not _YEAR_RE.match(year):
            continue
        sex = _SEX.get(str(codes["Sex"]).strip())
        if sex is None:
            continue

        area = str(codes["Geographic_Area"]).strip()
        geography = "Total country" if area == "Ghana" else area
        age = str(codes["Age"]).strip()
        age_group = "Total" if age == "All ages" else age

        rows.append({
            "series_type": "projection",
            "sex": sex,
            "age_group": age_group,
            "geography": geography,
            "period": year,
            "frequency": "annual",
            "measure": "count",
            "value": float(val),
            "unit": "persons",
            "series_code": "PHC2021",
        })

    if not rows:
        raise ValueError("ghana_pxweb_population: no population rows decoded")
    return pd.DataFrame.from_records(rows)
