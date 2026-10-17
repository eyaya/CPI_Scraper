"""Public Debt pipeline entry point.

    python -m indicators.public_debt.pipeline ghana
    python -m indicators.public_debt.pipeline --all
"""
from __future__ import annotations
import os

from core.run import Pipeline, run_cli
from . import parsers
from . import schema
from .standardise import standardise

HERE = os.path.dirname(os.path.abspath(__file__))


def _validate(df, d):
    """Stamp the descriptor's publisher and coverage, then validate.

    `publisher` is the descriptor's `agency` -- the institution whose document
    the figures came from. `coverage` is the descriptor's default debt
    perimeter; a parser whose source publishes several perimeters (e.g.
    central government AND public sector) sets it per row, and those values
    are kept.
    """
    df = df.copy()
    df["publisher"] = d.get("agency")
    if "coverage" not in df.columns:
        df["coverage"] = d.get("coverage")
    else:
        df["coverage"] = df["coverage"].fillna(d.get("coverage"))
    return schema.validate_public_debt(df)


CONFIG = Pipeline(
    sources_dir=os.path.join(HERE, "sources"),
    source_data_dir=os.path.join(HERE, "source_data"),
    out_dir=os.path.join(HERE, "out"),
    registry=parsers.REGISTRY,
    columns=schema.DEBT_COLUMNS,
    sort_cols=["period", "component"],
    validate=_validate,
    # MERGE-ON-WRITE: monthly and quarterly debt bulletins usually show a
    # rolling window, so history accumulates rather than being overwritten.
    merge_keys=["coverage", "component", "period", "frequency", "measure",
                "unit", "series_code"],
    # Cross-country columns derived from the published ones (2026-10-15) --
    # see standardise.py. The published columns stay exactly as published.
    standardise=standardise,
)

if __name__ == "__main__":
    raise SystemExit(run_cli(CONFIG))
