"""Producer Price Index (PPI) pipeline entry point.

    python -m indicators.ppi.pipeline ghana
    python -m indicators.ppi.pipeline --all
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
    columns=schema.PPI_COLUMNS,
    sort_cols=["index_name", "industry", "measure", "period"],
    validate=schema.validate_ppi,
    # One observation = index x industry x measure x base x period. The base is
    # in the key, so a rebased series accumulates beside the old one instead of
    # overwriting it; monthly bulletins each republishing a window of months
    # build the back-series by merging.
    merge_keys=schema.KEY,
    standardise=standardise,
)

if __name__ == "__main__":
    raise SystemExit(run_cli(CONFIG))
