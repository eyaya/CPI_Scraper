"""Liberia -- LISGIS Electricity Producer Price Index (LISGIS open-data API).

lisgis.gov.lr/api/datasets/ppi-electricity-index: the electricity PPI by
ISIC level (D Electricity; 35 Electricity Supply; 351 and 3510 Electric power
generation, transmission and distribution), monthly 2023-01..2024-09, copied
by LISGIS from its own workbook "LIBERIA PPI ELECTRICITY FINAL Q1-Q3 2024".
No base is printed (the workbook's reference columns are 2022 values), so
base_period stays blank. Weights are all 100 (each level is its own index)
and are not kept.

Not collected: ppi-electricity-changes -- LISGIS publishes its two change
columns UNLABELLED ("change_value_1/2", "source-order") beside #DIV/0! errors,
and value 2 of one month equals value 1 of the next, so which is the month's
change cannot be stated from the source; ppi-electricity-price-observations
(provider tariffs and provider-level index values, not the published PPI).
"""
from __future__ import annotations

import json

import pandas as pd

from . import _common as C

INDEX_NAME = "Electricity Producer Price Index"


def parse(local_path: str) -> pd.DataFrame:
    d = json.load(open(local_path, encoding="utf-8"))
    if d.get("id") != "ppi-electricity-index":
        raise ValueError(f"not the electricity PPI dataset: {d.get('id')}")
    rows = []
    for r in d["rows"]:
        if r.get("index_value") is None:
            continue
        rows.append(C.row(index_name=INDEX_NAME, industry=r["industry_name"].strip(),
                          industry_code_nso=str(r["industry_code"]), period=r["period"],
                          frequency="monthly", measure="index", value=round(float(r["index_value"]), 10)))
    if len(rows) < 80:
        raise ValueError(f"only {len(rows)} rows")
    return pd.DataFrame(rows)
