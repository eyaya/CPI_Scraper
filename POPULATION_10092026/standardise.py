"""Standardised columns for population, derived from the published ones.

Population's own vocabularies (series_type, sex, measure, unit) are already
controlled; what a consumer cannot use as published is the AGE label (380
spellings across indicators: '0-4 anos', '65 ans et plus', '80 ou mais anos')
and the absence of a single ID per quantity. So:

  sex_code        M | F | _T
  age_code        SDMX-style band: Y0T4, Y_GE80, Y_LT1, Y18, _T (all ages),
                  _U (not stated); BLANK when the label is parser leakage
                  ('sexe Masculin Féminin Total 14-19') -- such rows get no ID
  geography_level national | subnational
  unit_std / unit_multiplier   persons x1000 for 'thousand_persons', etc.
  value_std       value x unit_multiplier
  series_id       POP_<measure>_<sex>_<age>, e.g. POP_COUNT_F_Y15T19
  is_preferred    one row per (country, series_id, geography, period)

WHY series_type IS NOT IN series_id. A census count, an estimate and a
projection of the same population in the same year are the same quantity
measured three ways -- what Data Commons calls a measurement method -- so they
share an ID and `is_preferred` chooses between them: census, then estimate,
then projection (an observed count beats a modelled one for the same year).
The published `series_type` column still says which one each row is.
"""
from __future__ import annotations

import pandas as pd

from core.standardise_base import drop_conflicts
from core.standardise_base import (age_code, age_name, drop_std, finish, geography_level,
                                   join_name, mark_preferred, safe_id, sex_name, unit_parts)

STD_COLUMNS = ["sex_code", "age_code", "geography_level", "unit_std", "unit_multiplier",
               "value_std", "series_id", "series_name", "is_preferred"]

_SEX = {"male": "M", "female": "F", "total": "_T"}
_TYPE_RANK = {"census": 3, "estimate": 2, "projection": 1}
_MEASURE_NAME = {"count": "Population", "density": "Population density (persons per km2)",
                 "median_age": "Median age (years)", "sex_ratio": "Sex ratio",
                 "share": "Population share (%)", "growth_rate": "Population growth rate (%)",
                 "life_expectancy": "Life expectancy (years)",
                 "fertility_rate": "Total fertility rate (births per woman)"}


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    out = drop_std(df, STD_COLUMNS)
    s = out.fillna("").astype(str)
    out["sex_code"] = s["sex"].map(_SEX).fillna("")
    ages = {a: age_code(a) for a in s["age_group"].unique()}
    out["age_code"] = s["age_group"].map(ages)
    out["geography_level"] = s["geography"].map(geography_level)
    units = {(u, i): unit_parts(u, i) for u, i in set(zip(s["unit"], s["iso3"]))}
    parts = [units[(u, i)] for u, i in zip(s["unit"], s["iso3"])]
    out["unit_std"] = [p[2] for p in parts]
    out["unit_multiplier"] = [p[1] for p in parts]
    mult = pd.to_numeric(out["unit_multiplier"], errors="coerce").fillna(1.0)
    out["value_std"] = pd.to_numeric(out["value"], errors="coerce") * mult

    out["series_id"] = [
        safe_id("POP", m, sx, ag) if (m and sx and ag) else ""
        for m, sx, ag in zip(s["measure"], out["sex_code"], out["age_code"])]
    out["series_name"] = [
        join_name(_MEASURE_NAME.get(m, m.replace("_", " ")), sex_name(sx), age_name(ag)) if sid else ""
        for sid, m, sx, ag in zip(out["series_id"], s["measure"], out["sex_code"], out["age_code"])]
    rank = s["series_type"].map(_TYPE_RANK).fillna(0)
    drop_conflicts(out, ["country", "series_id", "geography", "period"], ["series_type", "source_file"])
    out["is_preferred"] = mark_preferred(
        out.assign(_c=s["country"], _g=s["geography"], _p=s["period"], _r=rank),
        ["_c", "series_id", "_g", "_p"], ["_r"])
    return finish(out, STD_COLUMNS)
