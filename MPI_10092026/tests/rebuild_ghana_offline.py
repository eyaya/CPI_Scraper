"""Rebuild `out/ghana_mpi.csv` from the SAVED StatsBank responses, offline.

Ghana is the one country in this package whose raw source is already on disk:
the three json-stat2 tables in `source_data/Ghana/` were captured from GSS
StatsBank. So the second half of a real run — parse, normalise, validate,
write — can be replayed exactly, with no network, and the resulting CSV is
genuine published data rather than a fixture.

    python -m indicators.mpi.tests.rebuild_ghana_offline

Run it after any change to `ghana_pxweb_mpi.py`, `_common.py` or `schema.py`:
it is the only end-to-end check in the package that uses real NSO numbers, and
it is what caught `All locality types` being filed as an unnamed stratum
instead of the national total.
"""
from __future__ import annotations
import datetime as dt
import os
import sys

import pandas as pd
import yaml

from indicators.mpi import schema
from indicators.mpi.parsers import ghana_pxweb_mpi as G
from indicators.mpi.pipeline import CONFIG

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)


def main() -> int:
    desc = os.path.join(PKG, "sources", "ghana.yaml")
    with open(desc, encoding="utf-8") as f:
        d = yaml.safe_load(f)

    specs, url_of = [], {}
    for t in d["api"]["tables"]:
        path = os.path.join(PKG, "source_data", "Ghana", t["save_as"])
        if not os.path.exists(path):
            print(f"missing saved response {path} — nothing to replay")
            return 1
        spec = dict(t)
        spec["path"] = path
        specs.append(spec)
        url_of[t["save_as"]] = t["table_url"]

    df = G.parse(specs)
    df["country"] = d["country"]
    df["iso3"] = d["iso3"]
    df["indicator"] = d["indicator"]
    df["source_type"] = d["source_type"]
    # Each row is credited to the table it actually came from, not to the
    # first table in the descriptor.
    df["source_file"] = df["series_code"]
    df["source_url"] = df["series_code"].map(url_of)
    df["extracted_at"] = dt.datetime.now().isoformat(timespec="seconds")
    for col in schema.MPI_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    df = schema.validate_mpi(df, d)
    df = df[CONFIG.columns].sort_values(CONFIG.sort_cols, kind="mergesort")

    # Independent arithmetic check on real data: the 13 indicator
    # contributions for the national row must sum to 100%. If the flat-array
    # coordinate decoding were wrong, this would not hold.
    nat = df[(df.geography == "Total country") & (df.metric == "contribution")]
    total = round(float(nat.value.sum()), 1)
    if len(nat) != 13 or abs(total - 100.0) > 0.5:
        print(f"contribution check FAILED: {len(nat)} indicators summing to "
              f"{total} (expected 13 summing to 100)")
        return 1

    out = os.path.join(PKG, "out", "ghana_mpi.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.to_csv(out, index=False)
    print(f"wrote {out}: {len(df)} rows x {len(df.columns)} columns")
    print(f"national contributions: {len(nat)} indicators summing to {total}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
