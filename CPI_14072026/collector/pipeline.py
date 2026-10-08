"""CPI pipeline entry point.

    python -m indicators.cpi.pipeline south_africa      # one country
    python -m indicators.cpi.pipeline --all             # every CPI descriptor

Wires the CPI sources / parsers / schema into the shared harness (core.run).
"""
from __future__ import annotations
import os

from core.run import Pipeline, run_cli
from . import parsers
from . import schema
from . import coicop

HERE = os.path.dirname(os.path.abspath(__file__))

CONFIG = Pipeline(
    sources_dir=os.path.join(HERE, "sources"),
    source_data_dir=os.path.join(HERE, "source_data"),
    out_dir=os.path.join(HERE, "out"),
    registry=parsers.REGISTRY,
    columns=schema.COLUMNS,
    sort_cols=["period", "coicop_code"],
    # One CPI observation = a division x geography x month x measure. Runs merge
    # on this key so the many one-month-per-PDF sources accumulate history rather
    # than replacing it (see core.run._merge_with_existing).
    merge_keys=["coicop_code", "geography", "period", "measure"],
    validate=lambda df, d: schema.validate(
        df, expect_divisions=d.get("expect_divisions", coicop.N_DIVISIONS)),
)

if __name__ == "__main__":
    raise SystemExit(run_cli(CONFIG))
