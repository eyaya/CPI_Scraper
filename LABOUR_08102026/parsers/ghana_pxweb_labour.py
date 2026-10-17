"""Parser for Ghana GSS StatsBank labour / economic-activity (PxWeb, Tier 1).

Input is the list of saved json-stat2 tables, each tagged with its `topic`. Most
are count-by-characteristic tables (activity status, employment status, industry,
occupation, sector) with the same skeleton as the census cross-tabs; one is a
RATE table (the unemployment rate) that carries no characteristic variable — its
value is a percent. We auto-detect which is which: the characteristic variable is
the one dimension not shared by the common census dimensions, and when there is
none the table is a rate.
"""
from __future__ import annotations
import json
import os
import pandas as pd

_COMMON = {"Geographic_Area", "Region", "Date", "Locality", "Age", "Sex", "Education"}
_SEX = {"Both sexes": "total", "Both Sexes": "total", "Male": "male", "Female": "female"}

# AHIES (Annual Household Income and Expenditure Survey) -- added 2026-10-12.
# The same StatsBank holds GSS's QUARTERLY household-survey composition tables
# (industry, occupation, employment status, employment sector, informality,
# 2022-Q1 onward), with a `Date` dimension ("2022Q1") and `Region` in place of
# the census's `Geographic_Area`. A table carrying `Date` is read as AHIES: the
# period comes from each cell's Date, never from the census constants. AHIES
# names no classification scheme against these tables, so its categories are
# National unless the descriptor's table entry says otherwise
# (`classification:`).
_AHIES_SURVEY = "Annual Household Income and Expenditure Survey (AHIES)"
_LOCALITY = {"All Locality Types": "all", "Rural": "rural", "Urban": "urban"}


def _decode_coords(flat: int, sizes: list[int]) -> list[int]:
    coords = []
    for i in range(len(sizes)):
        stride = 1
        for s in sizes[i + 1:]:
            stride *= s
        coords.append(flat // stride % sizes[i])
    return coords


# WHICH SCHEME EACH TABLE'S CATEGORIES BELONG TO.
#
# GSS publishes these cross-tabs against the international classifications, at
# the revisions current for PHC 2021, and says so in the StatsBank metadata.
# Recording it is what lets a user tell Ghana's "Wholesale and retail trade"
# (an ISIC Rev.4 section) apart from a national grouping that happens to carry
# a similar name -- see `schema.CLASSIFICATIONS`.
CLASSIFICATION = {
    "industry": "ISIC Rev.4",
    "occupation": "ISCO-08",
    "employment_status": "ICSE-93",
    "activity_status": "Not applicable",
    "sector": "Not applicable",
}

_LOCALITY_LABEL = {"all": "Total", "urban": "Urban", "rural": "Rural"}


def _parse_table(path: str, topic: str, classification: str | None = None) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    dims, sizes, values = d["id"], d["size"], d["value"]

    char_vars = [dim for dim in dims if dim not in _COMMON]
    if len(char_vars) > 1:
        raise ValueError(f"{os.path.basename(path)}: >1 characteristic var {char_vars}")
    char_var = char_vars[0] if char_vars else None      # None -> a rate table
    is_rate = char_var is None
    has_sex = "Sex" in dims
    has_age = "Age" in dims
    series_code = os.path.basename(path)

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
        codes = {dim: pos2code[dim][coords[i]] for i, dim in enumerate(dims)}

        area = str(codes.get("Geographic_Area", codes.get("Region", "Ghana"))).strip()
        geography = "Total country" if area == "Ghana" else area
        sex = _SEX.get(str(codes["Sex"]).strip(), "total") if has_sex else "total"
        if has_age:
            age = str(codes["Age"]).strip()
            age_group = "Total" if age in ("All ages", "All Ages", "Total") else age
        else:
            age_group = "Total"
        locality = _LOCALITY.get(str(codes.get("Locality", "")).strip(), "all")

        if is_rate:
            # A TABLE WITH NO CHARACTERISTIC DIMENSION IS A RATE TABLE, and
            # rates are not this indicator's business any more -- the headline
            # series lives in `unemployment/`, where the strict/broad
            # definition and the working-age base are first-class columns.
            # Ghana's StatsBank unemployment table moved there; if a rate table
            # is configured here again, say so rather than emitting an
            # untagged rate.
            raise ValueError(
                f"{os.path.basename(path)}: this is a RATE table (no "
                f"characteristic dimension) and `labour` holds the composition "
                f"of employment, not headline rates. Add it to the "
                f"`unemployment` indicator instead.")
        characteristic = str(codes[char_var]).strip()
        education = str(codes.get("Education", "Total")).strip() or "Total"
        if education == "All Educational Levels":
            education = "Total"
        if "Date" in dims:                       # an AHIES quarterly table
            q = str(codes["Date"]).strip()       # "2022Q1"
            stamp = dict(period=f"{q[:4]}-Q{q[-1]}", reference_period=q,
                         survey=_AHIES_SURVEY, frequency="quarterly",
                         classification=classification or "National")
        else:                                    # the PHC 2021 census tables
            stamp = dict(period="2021", reference_period="PHC 2021",
                         survey="Population and Housing Census 2021",
                         frequency="annual",
                         classification=CLASSIFICATION.get(topic, "National"))

        rows.append({
            "topic": topic, "characteristic": characteristic,
            "classification": stamp["classification"],
            "sex": sex, "age_group": age_group,
            "education": education,
            "geography": geography,
            "locality": locality, "locality_label": _LOCALITY_LABEL.get(locality, "Total"),
            "working_age_base": "15+",
            "period": stamp["period"], "reference_period": stamp["reference_period"],
            "survey": stamp["survey"],
            "frequency": stamp["frequency"],
            "measure": "count", "value": float(val), "unit": "persons",
            "series_code": series_code,
        })
    return rows


def parse(tables: list[dict]) -> pd.DataFrame:
    rows = []
    for t in tables:
        rows.extend(_parse_table(t["path"], t["topic"], t.get("classification")))
    if not rows:
        raise ValueError("ghana_pxweb_labour: no rows decoded")
    return pd.DataFrame.from_records(rows)
