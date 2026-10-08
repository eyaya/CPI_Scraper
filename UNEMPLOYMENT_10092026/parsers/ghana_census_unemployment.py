"""Ghana GSS StatsBank — the PHC 2021 census unemployment rate, by region.

A SECOND GHANA SERIES, and deliberately separate from the first. `ghana.yaml`
collects the AHIES quarterly survey; this collects the 2021 Population and
Housing Census. They are different instruments on different bases and must not
be chained: the census is a single 2021 observation of the 15+ population,
AHIES is a continuous quarterly survey.

This table used to live in the `labour` indicator, where it was the only rate
among cross-tabs of employment composition and carried no strict/broad
definition and no working-age base -- the two things a rate is uninterpretable
without. It belongs here, where both are first-class columns.

WHY NOT THE AHIES READER. `ghana_pxweb_unemployment` is written around the
AHIES table's own dimension names (`Region`, `Date`, ...) and hard-codes a
quarterly frequency. The census table uses `Geographic_Area` and has no date
dimension at all -- its period is the census year. Generalising that reader for
one extra table would have made both harder to read than this.

CROSS-CHECK (PHC 2021, 15+), read off the decoded table rather than recalled:
national unemployment rate 13.4, female 15.5 against male 11.6; Greater Accra
12.9; Ashanti 13.1; Upper East 21.1 (the highest of the sixteen regions).
"""
from __future__ import annotations

import json
import os

import pandas as pd

from . import _common as C

SURVEY = "Population and Housing Census 2021"
WORKING_AGE_BASE = "15+"
# GSS's spelling of each dimension's "all" category, verified against the live
# API metadata rather than assumed.
_TOTALS = {"Age": "All ages", "Locality": "All Locality Types",
           "Education": "Total"}


def _decode_coords(flat: int, sizes: list[int]) -> list[int]:
    coords = []
    for i in range(len(sizes)):
        stride = 1
        for s in sizes[i + 1:]:
            stride *= s
        coords.append(flat // stride % sizes[i])
    return coords


def _parse_table(spec: dict) -> list[dict]:
    path = spec["path"]
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    dims, sizes, values = d["id"], d["size"], d["value"]
    series_code = os.path.basename(path)

    topic = spec.get("topic")
    if not topic:
        raise ValueError(
            f"{series_code}: this table has no characteristic variable, so the "
            f"descriptor must declare `topic:` — there is nothing to infer it "
            f"from.")

    extra = [x for x in dims
             if x not in {"Geographic_Area", "Locality", "Education", "Sex", "Age"}]
    if extra:
        raise ValueError(
            f"{series_code}: unexpected dimension(s) {extra}. This reader is "
            f"for the census RATE table, which has no characteristic variable; "
            f"a table with one is a different shape.")

    pos2code = {}
    for dim in dims:
        cat = d["dimension"][dim]["category"]
        pos2code[dim] = {p: c for c, p in cat["index"].items()}

    items = values.items() if isinstance(values, dict) else enumerate(values)
    rows = []
    for flat, val in items:
        if val is None:
            continue
        coords = _decode_coords(int(flat), sizes)
        codes = {dim: str(pos2code[dim][coords[i]]).strip()
                 for i, dim in enumerate(dims)}

        area = codes["Geographic_Area"]
        loc_label = codes.get("Locality", _TOTALS["Locality"])
        age = codes.get("Age", _TOTALS["Age"])
        edu = codes.get("Education", _TOTALS["Education"])

        rows.append(C.row(
            topic=topic,
            # GSS publishes ONE rate here, on the ILO standard definition --
            # there is no relaxed/expanded variant in this table, so it is
            # tagged strict rather than left unqualified.
            definition="strict",
            value=float(val),
            series_label="Unemployment rate (PHC 2021)",
            survey=SURVEY,
            period="2021", reference_period="PHC 2021",
            frequency="ad_hoc", working_age_base=WORKING_AGE_BASE,
            sex=C.normalise_sex(codes["Sex"]),
            age_group="Total" if age in (_TOTALS["Age"], "Total") else age,
            education="Total" if edu == _TOTALS["Education"] else edu,
            geography="Total country" if area == "Ghana" else area,
            locality=C.normalise_locality(loc_label),
            locality_label="Total" if loc_label == _TOTALS["Locality"] else loc_label,
            measure="rate", unit="percent",
            series_code=series_code,
        ))
    return rows


def parse(tables: list[dict]) -> pd.DataFrame:
    rows = []
    for spec in tables:
        rows.extend(_parse_table(spec))
    if not rows:
        raise ValueError("ghana_census_unemployment: no rows decoded")
    df = pd.DataFrame.from_records(rows)
    rates = pd.to_numeric(df["value"], errors="coerce")
    if not rates.between(0, 100).all():
        raise ValueError(
            f"ghana_census_unemployment: rate outside 0..100 "
            f"(max={float(rates.max())}) -- the table is not what it claims.")
    return df
