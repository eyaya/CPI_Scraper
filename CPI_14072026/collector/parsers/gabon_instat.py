"""Parser for the DGS Gabon IHPC dashboard API (Tier 1).

Gabon (Direction Générale de la Statistique) runs a purpose-built IHPC portal at
ihpc.instatgabon.org whose dashboard is fed by a plain JSON API, so this is the
one CPI source that needs no file scraping at all. Three endpoints are retained
as the source documents, each answering `{"mode": …, "data": [ … ]}`:

  /api/ipch/series?limit=…      the national all-items index, month by month from
                                January 2019, with its 1-month and 12-month
                                variations — the full series in one call.
  /api/ipch/functions           the LATEST month only, by COICOP-1999 function
                                (01..12), index + both variations. The endpoint
                                ignores a `period` argument, so division history
                                accumulates across monthly runs.
  /api/ipch/regions-history     the all-items index for Libreville, Port-Gentil,
                                'autres urbains' and rural alongside the national
                                one, for the months the portal keeps (index only;
                                its rows carry the geography in `category_code`).

Every row is emitted as published: index from `index_value`, inflation_mom from
`variation_1_month_pct` and inflation_yoy from `variation_12_month_pct`, with
nulls (the first months of the series, where no variation exists yet) skipped.
Base 2018 = 100, as the API's own `base_code` (BASE_2018_100) states. French
labels kept as published; the regional rows carry only a code, mapped here to the
dashboard's own names.
"""
from __future__ import annotations
import json
import pandas as pd

_BASE_PERIOD = "2018 = 100"
_ALL_ITEMS = "ALL"
_NATIONAL = "National"
# geography code -> the name the portal itself shows
_GEOGRAPHIES = {
    "GA": _NATIONAL,
    "GA_LBV": "Libreville",
    "GA_POG": "Port-Gentil",
    "GA_AUTRES_URBAINS": "Autres urbains",
    "GA_RURAL": "Rural",
}
_MEASURES = [("index_value", "index", "Index", _BASE_PERIOD),
             ("variation_1_month_pct", "inflation_mom", "percent", ""),
             ("variation_12_month_pct", "inflation_yoy", "percent", "")]


def _rows(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, list) or not data:
        raise ValueError(f"Gabon IHPC: no data rows in {path}")
    return data


def _period(row: dict) -> str:
    start = str(row.get("period_start") or "")
    if len(start) < 7 or start[4] != "-":
        raise ValueError(f"Gabon IHPC: unusable period_start {start!r}")
    return start[:7]


def _emit(records: list, code: str, label: str, geography: str,
          period: str, row: dict) -> None:
    for field, measure, unit, base in _MEASURES:
        value = row.get(field)
        if value is None or pd.isna(value):
            continue
        records.append((code, label, geography, period, measure,
                        round(float(value), 4), unit, base))


def parse(json_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    records = []

    # national all-items series
    for row in _rows(json_path):
        if row.get("category_code") != _ALL_ITEMS:
            continue
        _emit(records, "00", row.get("category_name") or "Indice global",
              _GEOGRAPHIES.get(row.get("geography_code"), _NATIONAL),
              _period(row), row)
    if not records:
        raise ValueError("Gabon IHPC: no all-items rows in the series endpoint")

    divisions = set()
    for extra in extras or []:
        for row in _rows(extra):
            code = str(row.get("category_code") or "")
            if code in _GEOGRAPHIES:                 # a regions-history row
                _emit(records, "00", "Indice global", _GEOGRAPHIES[code],
                      _period(row), row)
            elif code.isdigit() and 1 <= int(code) <= 12:
                code = f"{int(code):02d}"
                divisions.add(code)
                _emit(records, code, row.get("category_name") or "",
                      _GEOGRAPHIES.get(row.get("geography_code"), _NATIONAL),
                      _period(row), row)
    if len(divisions) < 12:
        raise ValueError(
            f"Gabon IHPC: {len(divisions)} COICOP functions returned, expected 12")

    out = pd.DataFrame.from_records(
        records,
        columns=["coicop_code", "coicop_label", "geography", "period", "measure",
                 "value", "unit", "base_period"])
    out["frequency"] = "monthly"
    return out.drop_duplicates(["coicop_code", "geography", "period", "measure"])
