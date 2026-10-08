"""Parser for Ghana GSS StatsBank GDP (PxWeb, Tier 1).

Input is a list of saved json-stat2 tables (production + expenditure, annual +
quarterly), each tagged in the descriptor with its `approach`. Every table has
three dimensions: the time axis (`Year` or `Quarter`), `GDP_Series` (which encodes
price basis + measure + seasonal adjustment, e.g. "Nominal GDP (current prices)",
"Real GDP growth rate (year-on-year %)", "Seasonally adjusted GDP (constant 2013
prices)", "GDP share (basic prices)", "Contribution to Real GDP growth (p.p.)"),
and `Variable` (the sector / expenditure component / aggregate).

Everything emitted is published by GSS as-is — nominal & real levels, YoY/QoQ
growth, shares, contributions, seasonally-adjusted series, and per-capita GDP/GNI.
Nothing is derived. Units are taken from the published magnitudes: levels are in
GHS (Overall GDP 2024 ≈ GHS 1.18 trillion), per-capita in GHS per person.
"""
from __future__ import annotations
import json
import re
import pandas as pd

# Variables that are headline/whole-economy aggregates rather than a component of
# the table's approach.
_AGGREGATE_VARS = {
    "Overall GDP", "Gross Domestic Expenditure", "Informal GDP", "Non-oil GDP",
    "Non-gold GDP", "Per capita GDP", "Per capita GNI",
}
_PERCAPITA_VARS = {"Per capita GDP", "Per capita GNI"}

_YEAR_RE = re.compile(r"(\d{4})")
_QUARTER_RE = re.compile(r"^(\d{4})Q([1-4])$")


def _series_semantics(series: str) -> tuple[str, str, str, str]:
    """Map a GDP_Series label to (measure, price_basis, seasonal_adjustment, unit)."""
    s = series.lower()
    seasonal = "saa" if "seasonally adjusted" in s else "nsa"
    # "Nominal … (current prices)" -> current; "Real … / (constant … prices)" ->
    # constant (covers "Real GDP growth rate …" which names neither price word).
    if "nominal" in s or "current price" in s:
        basis = "current"
    elif "real" in s or "constant" in s:
        basis = "constant"
    elif seasonal == "saa":
        # GSS's seasonally-adjusted GDP is the constant-2013-prices series (see
        # its level label), so its growth rates are real too.
        basis = "constant"
    else:
        basis = "not_applicable"

    if "contribution" in s:
        return "contribution", "constant", seasonal, "percentage points"
    if "share" in s:
        return "share", "not_applicable", "not_applicable", "percent"
    if "quarter-on-quarter" in s:
        return "growth_qoq", basis, seasonal, "percent"
    if "year-on-year" in s:
        return "growth_yoy", basis, seasonal, "percent"
    # otherwise a level (nominal or real, possibly seasonally adjusted)
    return "level", basis, seasonal, "GHS"


def _decode_coords(flat: int, sizes: list[int]) -> list[int]:
    coords = []
    for i in range(len(sizes)):
        stride = 1
        for s in sizes[i + 1:]:
            stride *= s
        coords.append(flat // stride % sizes[i])
    return coords


def _parse_table(path: str, approach: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    dims, sizes, values = d["id"], d["size"], d["value"]
    pos2code, code2label = {}, {}
    for dim in dims:
        cat = d["dimension"][dim]["category"]
        pos2code[dim] = {p: c for c, p in cat["index"].items()}
        code2label[dim] = cat.get("label", {})

    time_dim = "Quarter" if "Quarter" in dims else "Year"
    is_quarterly = time_dim == "Quarter"
    items = values.items() if isinstance(values, dict) else enumerate(values)

    rows = []
    for flat, val in items:
        if val is None:
            continue
        coords = _decode_coords(int(flat), sizes)
        codes = {dim: pos2code[dim][coords[i]] for i, dim in enumerate(dims)}

        raw_t = codes[time_dim]
        if is_quarterly:
            m = _QUARTER_RE.match(raw_t.strip())
            if not m:
                continue
            period = f"{m.group(1)}-Q{m.group(2)}"
            frequency = "quarterly"
        else:
            m = _YEAR_RE.search(raw_t)          # strip provisional '*'/'**' marks
            if not m:
                continue
            period = m.group(1)
            frequency = "annual"

        var = codes["Variable"]
        measure, basis, seasonal, unit = _series_semantics(codes["GDP_Series"])
        if var in _PERCAPITA_VARS and measure == "level":
            measure, unit = "per_capita", "GHS per capita"
        if not is_quarterly:
            seasonal = "not_applicable"          # GSS annual series aren't SA-flagged
        row_approach = "aggregate" if var in _AGGREGATE_VARS else approach
        base_period = "Constant 2013 prices" if basis == "constant" else ""

        rows.append({
            "approach": row_approach,
            "category": var,
            # GSS's PxWeb table is a flat variable list with no SNA sub-grouping
            # and no official per-series code, so both are left blank (not faked).
            "category_group": "",
            "series_code": "",
            "geography": "National",
            "period": period,
            "frequency": frequency,
            "price_basis": basis,
            "seasonal_adjustment": seasonal,
            "measure": measure,
            "value": float(val),
            "unit": unit,
            "base_period": base_period,
        })
    return rows


def parse(tables: list[dict]) -> pd.DataFrame:
    rows = []
    for t in tables:
        rows.extend(_parse_table(t["path"], t["approach"]))
    if not rows:
        raise ValueError("no GDP rows decoded from Ghana StatsBank tables")
    return pd.DataFrame.from_records(rows)
