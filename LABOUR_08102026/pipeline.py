"""Labour pipeline entry point.

    python -m indicators.labour.pipeline ghana
    python -m indicators.labour.pipeline --all
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
    columns=schema.LABOUR_COLUMNS,
    sort_cols=["topic", "geography", "sex", "characteristic", "period"],
    validate=lambda df, d: schema.validate_labour(df),
    # MERGE, DON'T OVERWRITE. These cross-tabs are published one round at a
    # time -- a quarterly LFS bulletin, a census volume -- so a run that
    # replaced the file would discard every earlier period already collected.
    # (This is the failure that cost the CPI collector 258 Kenyan periods
    # before merge-on-write was adopted there.)
    #
    # `characteristic` AND `classification` are both in the key: the same label
    # can belong to two schemes -- "Commerce" is a division of Mali's national
    # 9-branch grouping and also appears in ISIC-based tables -- and collapsing
    # them would silently drop one country's category for another's.
    merge_keys=["topic", "characteristic", "classification", "sex",
                "age_group", "education", "geography", "locality",
                "locality_label", "working_age_base", "period", "measure"],
)

if __name__ == "__main__":
    raise SystemExit(run_cli(CONFIG))
