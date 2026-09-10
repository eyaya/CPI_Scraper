"""Unemployment / labour-force pipeline entry point.

    python -m indicators.unemployment.pipeline ghana
    python -m indicators.unemployment.pipeline --all

Reuses the shared `core/` harness (discover -> download -> extract -> parse ->
normalise -> validate -> write) and injects only what is specific to this
indicator: where its descriptors, raw sources and outputs live, its parser
registry, and its schema.
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
    columns=schema.UNEMPLOYMENT_COLUMNS,
    sort_cols=["topic", "definition", "geography", "locality",
               "sex", "age_group", "period"],
    validate=schema.validate_unemployment,
    # MERGE, DON'T OVERWRITE. Most of these sources publish one period per
    # document -- a quarterly bulletin, an annual report -- so a run that
    # replaced the file would throw away every earlier quarter the collector
    # had already read. (This is the same failure that cost the CPI collector
    # 258 Kenyan periods before merge-on-write was adopted there.)
    #
    # `series_label` IS PART OF THE KEY, and has to be. Kenya's Table 1 prints
    # LU2 and LU3 side by side: both are `labour_underutilisation_rate`, both
    # `broad`, same geography, sex, age and period, and they differ only in
    # the label the report gives them (18.6% against 13.9%). Without the label
    # in the key the second run would collapse them into one -- exactly how
    # the MPI collector silently lost four of its six confidence bounds.
    merge_keys=["topic", "definition", "series_label", "sex", "age_group",
                "education", "geography", "locality", "locality_label",
                "working_age_base", "period", "measure"],
)

if __name__ == "__main__":
    raise SystemExit(run_cli(CONFIG))
