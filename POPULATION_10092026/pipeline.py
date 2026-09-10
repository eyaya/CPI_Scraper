"""Population pipeline entry point.

    python -m indicators.population.pipeline south_africa   # one country
    python -m indicators.population.pipeline --all           # every descriptor

Wires the Population sources / parsers / schema into the shared harness
(core.run), exactly as the CPI and GDP pipelines do.
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
    columns=schema.POPULATION_COLUMNS,
    sort_cols=["period", "geography", "sex", "age_group"],
    # One population observation = series x sex x age x geography x year x measure.
    # `series_type` is part of the key on purpose: a census and a projection can
    # both cover the same year and geography and must not overwrite each other.
    # Merging also means a new census round accumulates alongside the previous one
    # instead of replacing it (see core.run._merge_with_existing).
    merge_keys=["series_type", "sex", "age_group", "geography", "period", "measure"],
    validate=lambda df, d: schema.validate_population(df),
)

if __name__ == "__main__":
    raise SystemExit(run_cli(CONFIG))
