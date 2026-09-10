"""MPI pipeline entry point.

    python -m indicators.mpi.pipeline ghana
    python -m indicators.mpi.pipeline --all
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
    columns=schema.MPI_COLUMNS,
    sort_cols=["mpi_type", "metric", "geography", "locality", "sex",
               "characteristic", "mpi_indicator", "period"],
    validate=schema.validate_mpi,
    # One MPI observation = measure x metric x geography x cut x period. Runs
    # merge into the existing output rather than replacing it, as for CPI and
    # population; `mpi_type` and `measure_name` are in the key so a national and
    # a global MPI for the same country and year cannot overwrite each other.
    merge_keys=["mpi_type", "measure_name", "metric", "dimension",
                "mpi_indicator", "topic", "characteristic", "sex", "age_group",
                "geography", "locality", "locality_label", "period"],
)

if __name__ == "__main__":
    raise SystemExit(run_cli(CONFIG))
