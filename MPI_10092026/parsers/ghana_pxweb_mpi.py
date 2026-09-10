"""Parser for Ghana GSS StatsBank Multidimensional Poverty (PxWeb, Tier 1).

Ghana is the only NSO in Africa exposing its MPI through a machine-readable API,
so it earns bespoke code. Input is the list of saved json-stat2 tables, each
tagged in the descriptor with its `topic` (sex_of_head, locality, contributor)
and with the measure's methodology, which travels on every row.

Two table shapes:

* a METRIC table carries a `poverty_measure` dimension (Incidence H / Intensity
  A / MPI M0) plus one cut dimension (sex of household head, or locality);
* the CONTRIBUTORS table carries an `indicator` dimension whose value is each
  MPI indicator's percentage contribution to overall poverty.

Only the national row and the 16 regions are kept; the district detail is
dropped, and the descriptor records that as deferred rather than losing it
silently.

NOTE this is a DIFFERENT measure from the GSS MPI report collected as
`ghana_report`: this one is census-based (PHC 2021), that one is GLSS7-based
with a different indicator count. They are two products of the same agency and
must not be chained.
"""
from __future__ import annotations
import json
import os
import pandas as pd

from . import _common as C

_REGIONS = {
    "Ghana", "Western", "Central", "Greater Accra", "Volta", "Eastern", "Ashanti",
    "Western North", "Ahafo", "Bono", "Bono East", "Oti", "Northern", "Savannah",
    "North East", "Upper East", "Upper West",
}

# GSS's own spellings, mapped to the controlled metric vocabulary. An unmapped
# poverty_measure raises rather than being dropped.
_METRIC = {
    "Incidence of Poverty (H)": ("incidence_H", "percent"),
    "Intensity of Poverty (A)": ("intensity_A", "percent"),
    "Multidimensional Poverty Index (M0)": ("index_M0", "index"),
}


def _decode_coords(flat: int, sizes: list[int]) -> list[int]:
    """json-stat2 stores one flat array in row-major order; recover each
    dimension's index for a given flat position."""
    coords = []
    for i in range(len(sizes)):
        stride = 1
        for s in sizes[i + 1:]:
            stride *= s
        coords.append(flat // stride % sizes[i])
    return coords


def _parse_table(spec: dict) -> list[dict]:
    path, topic = spec["path"], spec["topic"]
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    dims, sizes, values = d["id"], d["size"], d["value"]
    series_code = os.path.basename(path)

    # Methodology travels from the descriptor onto every row: an MPI value
    # without its cutoff and shape is not interpretable.
    meth = {
        "mpi_type": spec.get("mpi_type", "national"),
        "measure_name": spec["measure_name"],
        "survey": spec["survey"],
        "k_cutoff": spec["k_cutoff"],
        "n_dimensions": spec["n_dimensions"],
        "n_indicators": spec["n_indicators"],
        "unit_of_analysis": spec.get("unit_of_analysis", "person"),
        "period": str(spec["period"]),
        "reference_period": spec.get("reference_period", str(spec["period"])),
        "frequency": spec.get("frequency", "ad_hoc"),
    }

    pm_dim = "poverty_measure" if "poverty_measure" in dims else None
    cut_dim = next((x for x in dims
                    if x not in ("Geographic_Area", "poverty_measure")), None)

    pos2code = {}
    for dim in dims:
        cat = d["dimension"][dim]["category"]
        pos2code[dim] = {p: c for c, p in cat["index"].items()}

    unmapped: set[str] = set()
    rows: list[dict] = []
    items = values.items() if isinstance(values, dict) else enumerate(values)
    for flat, val in items:
        if val is None:
            continue
        coords = _decode_coords(int(flat), sizes)
        codes = {dim: str(pos2code[dim][coords[i]]).strip()
                 for i, dim in enumerate(dims)}

        area = codes["Geographic_Area"]
        if area not in _REGIONS:
            continue                                    # district detail
        geography = "Total country" if area == "Ghana" else area
        cut = codes[cut_dim] if cut_dim else "Total"

        if pm_dim:
            key = codes[pm_dim]
            if key not in _METRIC:
                unmapped.add(key)
                continue
            metric, unit = _METRIC[key]
            extra = {"characteristic": cut}
            if topic == "sex_of_head":
                extra["sex"] = C.normalise_sex(cut)
            elif topic == "locality":
                extra["locality"] = C.normalise_locality(cut)
                extra["locality_label"] = cut
        else:                                           # contributors table
            metric, unit = "contribution", "percent"
            extra = {"characteristic": cut, "mpi_indicator": cut}

        rows.append(C.row(metric=metric, value=float(val), unit=unit,
                          topic=topic, geography=geography,
                          series_code=series_code, **meth, **extra))

    if unmapped:
        raise ValueError(
            f"{series_code}: unmapped poverty_measure value(s) {sorted(unmapped)}. "
            f"Map them in _METRIC rather than losing a published series.")
    return rows


def parse(tables: list[dict]) -> pd.DataFrame:
    rows: list[dict] = []
    for t in tables:
        rows.extend(_parse_table(t))
    if not rows:
        raise ValueError("ghana_pxweb_mpi: no rows decoded")
    return pd.DataFrame.from_records(rows)
