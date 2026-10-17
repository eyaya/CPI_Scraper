"""Standardised columns for MPI, derived from the published ones.

`metric` is already controlled (incidence_H, intensity_A, index_M0, their CI
bounds, contribution, ...). The trap is different from GDP's: every NATIONAL
MPI is its own design -- its own dimensions, indicators, weights and poverty
cutoff k -- so Ghana's "MPI" and Nigeria's "MPI" are different quantities and
must never share an ID. The measure therefore goes INTO series_id (as a safe
slug of `measure_name`, which also separates a country's two measures, e.g.
Rwanda's first and second report). The global MPI is its own measure too.

Breakdowns get a code only where the category is standard:
  total         -> sex + age band of the population covered (Nigeria's child MPI = Y0T4)
  locality      -> LOC_U / LOC_R from the `locality` column; zones ("Coastal zone") blank
  sex_of_head   -> HEAD_F / HEAD_M ("Chefe mulher", "Féminin", "Female-headed" ...)
  quintile      -> Q1..Q5
  age           -> AGE_<band> via core age_code ('0 - 4 ans' -> AGE_Y0T4)
  contributor / per-indicator rows -> IND_<indicator slug>
  education, disability -> blank (national category sets)

Columns: breakdown_code, sex_code, geography_level, unit_std, value_std, series_id, is_preferred.

value_std puts M0 on ONE scale: INS Guinea prints it x100 ("37,5" = 72,7 x 51,5 / 100,
recorded as unit percent on purpose), every other office as 0-1. value_std is M0 on
0-1 everywhere (unit_std "index"); other metrics are unchanged.
"""
from __future__ import annotations

import re

import pandas as pd

from core.standardise_base import drop_conflicts
from core.standardise_base import (age_code, drop_std, finish, geography_level,
                                   locality_token, mark_preferred, norm, safe_id,
                                   age_name, join_name, locality_name, sex_name, slug_name)

STD_COLUMNS = ["breakdown_code", "sex_code", "geography_level", "unit_std", "value_std",
               "series_id", "series_name", "is_preferred"]

_SEX = {"male": "M", "female": "F", "total": "_T"}
_HEAD_F = re.compile(r"^(?:female(?:-headed)?|feminin|chefe mulher|femme)$")
_HEAD_M = re.compile(r"^(?:male(?:-headed)?|masculin|chefe homem|homme)$")


def _slug(text: str, n: int = 40) -> str:
    return safe_id(norm(text))[:n].rstrip("_")


def _breakdown(topic, char, locality, sex, age, indicator) -> str:
    c = norm(char)
    if indicator and norm(indicator) != "total":
        return "IND_" + _slug(indicator, 30)
    if topic == "total":
        a = age_code(age)
        sx = _SEX.get(sex, "")
        return f"{sx}_{a}" if (sx and a) else ""
    if topic == "contributor":
        return "IND_" + _slug(char, 30)
    if topic == "locality":
        return {"urban": "LOC_U", "rural": "LOC_R", "all": "_T"}.get(locality, "")
    if topic == "sex_of_head":
        if _HEAD_F.match(c):
            return "HEAD_F"
        if _HEAD_M.match(c):
            return "HEAD_M"
        return "_T" if c in ("both sexes", "total", "ensemble") else ""
    if topic == "quintile":
        m = re.fullmatch(r"(?:q|quintile )([1-5])", c)
        return f"Q{m.group(1)}" if m else ""
    if topic == "age":
        a = age_code(char)
        return f"AGE_{a}" if a.startswith("Y") else ""
    return ""


_METRIC_NAME = {
    "incidence_H": "incidence (H, % of people poor)", "intensity_A": "intensity (A, %)",
    "index_M0": "MPI value (M0)", "contribution": "contribution of indicator (%)",
    "severe_poverty": "in severe poverty (%)", "vulnerable": "vulnerable to poverty (%)",
    "censored_headcount": "censored headcount (%)", "uncensored_headcount": "uncensored headcount (%)"}
for _m in ("incidence_H", "intensity_A", "index_M0"):
    _METRIC_NAME[_m + "_ci_low"] = _METRIC_NAME[_m] + ", lower confidence bound"
    _METRIC_NAME[_m + "_ci_high"] = _METRIC_NAME[_m] + ", upper confidence bound"


def _breakdown_name(b: str) -> str:
    if b.startswith("IND_"):
        return "indicator: " + slug_name(b[4:])
    if b.startswith("AGE_"):
        return age_name(b[4:])
    if b.startswith("Q") and b[1:].isdigit():
        return f"wealth quintile {b[1:]}" + {"1": " (poorest)", "5": " (richest)"}.get(b[1:], "")
    fixed = {"HEAD_F": "female-headed households", "HEAD_M": "male-headed households",
             "LOC_U": "urban", "LOC_R": "rural", "_T": "all"}
    if b in fixed:
        return fixed[b]
    sx, _, ag = b.partition("_") if not b.startswith("_") else ("_T", "", b[3:])
    return ", ".join(x for x in (sex_name(sx), age_name(ag)) if x)


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    out = drop_std(df, STD_COLUMNS)
    s = out.fillna("").astype(str)
    keys = list(zip(s["topic"], s["characteristic"], s["locality"], s["sex"],
                    s["age_group"], s["mpi_indicator"]))
    cache = {k: _breakdown(*k) for k in set(keys)}
    out["breakdown_code"] = [cache[k] for k in keys]
    out["sex_code"] = s["sex"].map(_SEX).fillna("")
    out["geography_level"] = s["geography"].map(geography_level)
    out["unit_std"] = s["unit"].map(lambda u: u if u in ("percent", "index") else "")
    v = pd.to_numeric(out["value"], errors="coerce")
    m0pct = (s["metric"].str.startswith("index_M0")) & (s["unit"] == "percent")
    out["value_std"] = v.where(~m0pct, v / 100)
    out.loc[m0pct, "unit_std"] = "index"
    # The urban/rural cut is part of the ID (one value per series_id, place
    # and date); a LOC_ breakdown already carries it. Per-indicator rows of the
    # locality table (Angola IPM-A) need it too: urban and rural shared one ID.
    out["series_id"] = [
        safe_id("MPI", _slug(m), metric, b, "" if b.startswith("LOC_") else locality_token(loc, ll))
        if (m and metric and b) else ""
        for m, metric, b, t, loc, ll in zip(s["measure_name"], s["metric"], out["breakdown_code"],
                                            s["topic"], s["locality"], s["locality_label"])]
    out["series_name"] = [
        join_name(m.strip(), _METRIC_NAME.get(metric, metric.replace("_", " ")), _breakdown_name(b),
                  "" if b.startswith("LOC_") else locality_name(locality_token(loc, ll))) if sid else ""
        for sid, m, metric, b, t, loc, ll in zip(out["series_id"], s["measure_name"], s["metric"],
                                                 out["breakdown_code"], s["topic"], s["locality"],
                                                 s["locality_label"])]
    drop_conflicts(out, ["country", "series_id", "geography", "period"], ["source_file", "measure_name"])
    out["is_preferred"] = mark_preferred(
        out.assign(_c=s["country"], _g=s["geography"], _p=s["period"], _r=s["reference_period"]),
        ["_c", "series_id", "_g", "_p"], ["_r"])
    return finish(out, STD_COLUMNS)
