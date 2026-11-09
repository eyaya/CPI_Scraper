"""Monetary-poverty pipeline entry point.

    python -m indicators.poverty.pipeline cote_divoire
    python -m indicators.poverty.pipeline --all
"""
from __future__ import annotations
import os

from core.run import Pipeline, run_cli
from . import parsers
from . import schema
from .standardise import standardise

HERE = os.path.dirname(os.path.abspath(__file__))

CONFIG = Pipeline(
    sources_dir=os.path.join(HERE, "sources"),
    source_data_dir=os.path.join(HERE, "source_data"),
    out_dir=os.path.join(HERE, "out"),
    registry=parsers.REGISTRY,
    columns=schema.POVERTY_COLUMNS,
    sort_cols=["line_type", "line_level", "metric", "geography", "topic",
               "characteristic", "locality", "period"],
    validate=schema.validate_poverty,
    # One observation = line x metric x group x period x survey. The LINE is in
    # the key (an extreme and an overall rate for one group are two rows), and
    # so is the survey, so a re-estimate of an old round republished under a
    # new methodology accumulates beside the original instead of replacing it.
    merge_keys=["survey", "welfare_aggregate", "unit_of_analysis", "line_type",
                "line_level", "line_name", "metric", "topic", "characteristic",
                "sex", "age_group", "geography", "locality", "locality_label",
                "period"],
    standardise=standardise,
)

if __name__ == "__main__":
    raise SystemExit(run_cli(CONFIG))
