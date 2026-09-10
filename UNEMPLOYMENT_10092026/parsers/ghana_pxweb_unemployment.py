"""Parser for Ghana GSS StatsBank AHIES labour tables (PxWeb, Tier 1).

The only genuine machine-readable NSO labour source found anywhere in Africa
during this build. GSS runs the Annual Household Income and Expenditure Survey
(AHIES) as a CONTINUOUS quarterly survey and publishes its labour tables through
the same PxWeb backend as Ghana GDP / Population / census_characteristics.

Input is the list of saved json-stat2 tables, each tagged in the descriptor with
the `topic_map` that says what its characteristic variable's categories mean.
Two table shapes occur and are auto-detected exactly as in
`indicators/labour/parsers/ghana_pxweb_labour.py`:

* a RATE table has no characteristic variable beyond the common dimensions
  (`unemploy.px`: Date x Region x Locality x Education x Sex x Age) -- its value
  is a percent and the descriptor names the single topic it carries;
* a COUNT table has one extra variable (`data_econact.px`'s
  `Economic_Activity` in {Total, Labour force, Employed, Unemployed, Outside
  labour force}) whose categories map to topics via `topic_map`.

Verified against the live API metadata (2026-09): variable codes are `Date`,
`Region`, `Locality`, `Education`, `Sex`, `Age`; the age total is spelled
"All Ages", the locality total "All Locality Types", the education total
"All Educational Levels", and the sex total "Both Sexes" -- in BOTH tables.

An unmapped characteristic category raises rather than being dropped: silently
omitting a category the NSO published would violate the collector's first rule.
"""
from __future__ import annotations
import json
import os
import pandas as pd

from . import _common as C

# The dimensions every AHIES labour table shares; anything else is the
# table's characteristic variable.
_COMMON = {"Date", "Region", "Locality", "Education", "Sex", "Age"}

_TOTALS = {
    "Age": "All Ages",
    "Locality": "All Locality Types",
    "Education": "All Educational Levels",
    "Sex": "Both Sexes",
}

SURVEY = "AHIES (Annual Household Income and Expenditure Survey)"
WORKING_AGE_BASE = "15+"


def _decode_coords(flat: int, sizes: list[int]) -> list[int]:
    """json-stat2 stores one flat array in row-major order; recover the index
    of each dimension for a given flat position."""
    coords = []
    for i in range(len(sizes)):
        stride = 1
        for s in sizes[i + 1:]:
            stride *= s
        coords.append(flat // stride % sizes[i])
    return coords


def _parse_table(spec: dict) -> list[dict]:
    path = spec["path"]
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    dims, sizes, values = d["id"], d["size"], d["value"]

    char_vars = [dim for dim in dims if dim not in _COMMON]
    if len(char_vars) > 1:
        raise ValueError(
            f"{os.path.basename(path)}: expected at most one characteristic "
            f"variable, got {char_vars}")
    char_var = char_vars[0] if char_vars else None
    topic_map = {k.strip().lower(): v for k, v in (spec.get("topic_map") or {}).items()}
    single_topic = spec.get("topic")

    if char_var is None and not single_topic:
        raise ValueError(f"{os.path.basename(path)}: rate table needs `topic:` "
                         f"in the descriptor")
    if char_var is not None and not topic_map:
        raise ValueError(f"{os.path.basename(path)}: count table needs "
                         f"`topic_map:` in the descriptor for {char_var}")

    pos2code = {}
    for dim in dims:
        cat = d["dimension"][dim]["category"]
        pos2code[dim] = {p: c for c, p in cat["index"].items()}

    series_code = os.path.basename(path)
    definition = spec.get("definition", "not_applicable")
    unmapped: set[str] = set()
    rows: list[dict] = []

    items = values.items() if isinstance(values, dict) else enumerate(values)
    for flat, val in items:
        if val is None:
            continue
        coords = _decode_coords(int(flat), sizes)
        codes = {dim: str(pos2code[dim][coords[i]]).strip()
                 for i, dim in enumerate(dims)}

        if char_var is not None:
            label = codes[char_var]
            topic = topic_map.get(label.lower())
            if topic is None:
                unmapped.add(label)
                continue
        else:
            label, topic = spec.get("series_label", single_topic), single_topic

        region = codes["Region"]
        geography = "Total country" if region == "Ghana" else region
        loc_label = codes["Locality"]
        age = codes["Age"]
        edu = codes["Education"]
        period = C.parse_period(codes["Date"])
        if period is None:
            raise ValueError(f"{series_code}: unreadable Date {codes['Date']!r}")

        rows.append(C.row(
            topic=topic, value=float(val), series_label=label, survey=SURVEY,
            definition=definition,
            period=period, reference_period=codes["Date"],
            frequency="quarterly", working_age_base=WORKING_AGE_BASE,
            sex=C.normalise_sex(codes["Sex"]),
            age_group="Total" if age == _TOTALS["Age"] else age,
            education="Total" if edu == _TOTALS["Education"] else edu,
            geography=geography,
            locality=C.normalise_locality(loc_label),
            locality_label="Total" if loc_label == _TOTALS["Locality"] else loc_label,
            series_code=series_code,
        ))

    if unmapped:
        raise ValueError(
            f"{series_code}: {len(unmapped)} category(ies) of {char_var} are not "
            f"in the descriptor's topic_map and would be silently dropped: "
            f"{sorted(unmapped)}. Map them (or map them to null deliberately) "
            f"rather than losing a published series.")
    return rows


def parse(tables: list[dict]) -> pd.DataFrame:
    rows: list[dict] = []
    for t in tables:
        rows.extend(_parse_table(t))
    if not rows:
        raise ValueError("ghana_pxweb_unemployment: no rows decoded")
    return pd.DataFrame.from_records(rows)
