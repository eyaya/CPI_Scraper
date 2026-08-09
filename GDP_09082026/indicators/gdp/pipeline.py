"""GDP pipeline entry point.

    python -m indicators.gdp.pipeline south_africa      # one country
    python -m indicators.gdp.pipeline --all             # every GDP descriptor

Wires the GDP sources / parsers / schema into the shared harness (core.run).
"""
from __future__ import annotations
import os

from core.run import Pipeline, run_cli
from . import parsers
from . import schema

HERE = os.path.dirname(os.path.abspath(__file__))

CONFIG = Pipeline(
    sources_dir=os.path.join(HERE, "sources"),
    source_data_dir=os.path.join(HERE, "source_data"),
    out_dir=os.path.join(HERE, "out"),
    registry=parsers.REGISTRY,
    columns=schema.GDP_COLUMNS,
    sort_cols=["period", "approach", "series_code"],
    validate=lambda df, d: schema.validate_gdp(df),
)

if __name__ == "__main__":
    raise SystemExit(run_cli(CONFIG))
