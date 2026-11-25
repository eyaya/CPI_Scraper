"""Merchandise Trade pipeline entry point.

    python -m indicators.trade.pipeline ghana
    python -m indicators.trade.pipeline --all
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
    columns=schema.TRADE_COLUMNS,
    sort_cols=["tradeflow", "commodity_classification", "commodity", "partner", "period"],
    validate=schema.validate_trade,
    # Merge-on-write: bulletins with overlapping windows accumulate; the
    # newest run of a key wins.
    merge_keys=schema.KEY,
    standardise=standardise,
)

if __name__ == "__main__":
    raise SystemExit(run_cli(CONFIG))
