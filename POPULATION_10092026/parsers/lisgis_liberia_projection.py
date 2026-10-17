"""LISGIS Liberia -- population back-series and projections from LISGIS's own
dataset API (lisgis.gov.lr/api/datasets/<id>), each dataset a JSON copy of a
census thematic-report workbook table ("values copied from the supplied
workbook cells ... no calculations" -- LISGIS's own extraction note).

Added 2026-10-13 as a SECOND Liberia descriptor (liberia_projections.yaml)
beside liberia.yaml (the 2022 census by county / age / sex, same API).

Datasets read (files identified by their JSON `id`):
* census-population-size            census totals by sex, 1962, 1974, 1984,
                                    2008 (2022 is liberia.yaml's; checked equal)
                                    -> series census
* census-population-county-trend    county populations at the 1984 and 2008
                                    censuses (2022 left to liberia.yaml)
                                    -> series census
* lisgis-population-projection-table-2-6
                                    "Projected population by sex and
                                    variants, 2022-2065": MEDIUM variant only
                                    (no variant column), five-yearly
* lisgis-population-projection-table-a8 / a9 / a10
                                    projected population by 5-year age group,
                                    2022-2032 annually, both sexes / males /
                                    females. Broad groups (0-14, 15-64, 65+,
                                    18+) and the dependency ratio / mean /
                                    median age rows are not read.
* lisgis-population-projection-table-4-3
                                    projected population by sex and county,
                                    2022, 2027, 2032, 2035
-> projections are series projection (2022 = the projection's base, filed as
projection beside the census count).

ONE PRINTING PER KEY: a figure printed in two tables (national totals in 2-6,
a8-a10's Total row and 4-3's Total row) is filed once -- from 2-6 where it
has the year, else from a8-a10 (annual years), else 4-3 (2035) -- and the
other printings are checked equal (within 2 persons).

County names as liberia.yaml spells them ("Rivercess", from the API's
county_name; 4-3's row label prints "River Cess").
"""
from __future__ import annotations

import json
import re

import pandas as pd

_BANDS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
          "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
          "75-79", "80+"]
_AGE_TABLES = {"lisgis-population-projection-table-a8": "total",
               "lisgis-population-projection-table-a9": "male",
               "lisgis-population-projection-table-a10": "female"}
# Published, pinned: (table, sex, geo, year, this printing, filed printing)
# 2032: tables a8/a9 and 4-3 print 6 618 845 (males 3 301 533); table 2-6,
# whose figure is filed, prints 6 618 852 (males 3 301 538).
_KNOWN: set = {
    ("4-3", "male", "Total country", "2032", 3301533.0, 3301538.0),
    ("4-3", "total", "Total country", "2032", 6618845.0, 6618852.0),
    ("lisgis-population-projection-table-a8", "total", "Total country", "2032", 6618845.0, 6618852.0),
    ("lisgis-population-projection-table-a9", "male", "Total country", "2032", 3301533.0, 3301538.0),
}
_SEX_WORD = {"Both sexes": "total", "Total": "total", "Males": "male",
             "Male": "male", "Females": "female", "Female": "female"}


def _load(paths):
    out = {}
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        if d.get("id") in out:
            raise ValueError(f"LISGIS: {d.get('id')} twice")
        out[d.get("id")] = d
    need = {"census-population-size", "census-population-county-trend",
            "lisgis-population-projection-table-2-6",
            "lisgis-population-projection-table-4-3", *_AGE_TABLES}
    if set(out) != need:
        raise ValueError(f"LISGIS: datasets {sorted(set(out) ^ need)}")
    return out


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    ds = _load([local_path] + list(extras or []))
    out, seen = [], {}

    def emit(st, sex, age, geo, yr, v, sc):
        k = (st, sex, age, geo, yr)
        if k in seen:
            raise ValueError(f"LISGIS: {k} filed twice")
        seen[k] = v
        out.append({"series_type": st, "sex": sex, "age_group": age,
                    "geography": geo, "period": str(yr), "frequency": "annual",
                    "measure": "count", "value": float(v), "unit": "persons",
                    "series_code": sc})

    diffs = set()

    def check(k, v, where):
        if k in seen and abs(seen[k] - float(v)) > 2:
            diffs.add((where, k[1], k[3], k[4], float(v), float(seen[k])))

    # county code -> name, from 4-3 (rows carry both)
    names = {r["geo_code"]: r["county_name"]
             for r in ds["lisgis-population-projection-table-4-3"]["rows"]
             if r.get("geo_level") == "county"}

    # --- censuses --------------------------------------------------------
    for r in ds["census-population-size"]["rows"]:
        yr = int(r["year"])
        t, m, f = r["total_population"], r["male_population"], r["female_population"]
        if abs(m + f - t) > 2:
            raise ValueError(f"LISGIS census {yr}: {m} + {f} != {t}")
        if yr == 2022:
            if t != 5250187:
                raise ValueError(f"LISGIS census 2022: {t} (liberia.yaml has 5 250 187)")
            continue
        for sex, v in (("total", t), ("male", m), ("female", f)):
            emit("census", sex, "Total", "Total country", yr, v, "LR_CENSUS_SIZE_TREND")
    for r in ds["census-population-county-trend"]["rows"]:
        if r["geo_level"] == "country":
            for yr in (1984, 2008):
                check(("census", "total", "Total", "Total country", str(yr)),
                      r[f"population_{yr}"], "county-trend")
            continue
        geo = names.get(r["geo_code"])
        if geo is None:
            raise ValueError(f"LISGIS county-trend: code {r['geo_code']}")
        for yr in (1984, 2008):
            emit("census", "total", "Total", geo, yr, r[f"population_{yr}"],
                 "LR_CENSUS_COUNTY_TREND")

    # --- projections: 2-6 medium -----------------------------------------
    for r in ds["lisgis-population-projection-table-2-6"]["rows"]:
        if r["variant"] != "Medium":
            continue
        sex = _SEX_WORD[r["measure"].split("/")[-1].strip()]
        emit("projection", sex, "Total", "Total country", r["period"], r["value"],
             "LR_PROJ2022_T2.6_MEDIUM")
    if len([k for k in seen if k[0] == "projection"]) != 30:
        raise ValueError("LISGIS 2-6: expected 10 years x 3 sexes")

    # --- a8-a10: 5-year bands, 2022-2032 ---------------------------------
    for tid, sex in _AGE_TABLES.items():
        tab: dict[tuple, float] = {}
        for r in ds[tid]["rows"]:
            lab = r["row_label"]
            if lab in _BANDS or lab == "Total":
                tab[(lab, r["period"])] = float(r["value"])
        years = sorted({y for _, y in tab})
        if years != [str(y) for y in range(2022, 2033)]:
            raise ValueError(f"LISGIS {tid}: years {years}")
        for y in years:
            s = sum(tab[(b, y)] for b in _BANDS)
            if abs(s - tab[("Total", y)]) > 20:
                raise ValueError(f"LISGIS {tid} {y}: bands {s} != Total {tab[('Total', y)]}")
            for b in _BANDS:
                emit("projection", sex, b, "Total country", y, tab[(b, y)],
                     f"LR_PROJ2022_{tid[-3:].upper().strip('-')}")
            k = ("projection", sex, "Total", "Total country", y)
            if k in seen:
                check(k, tab[("Total", y)], tid)
            else:
                emit(*k, tab[("Total", y)], f"LR_PROJ2022_{tid[-3:].upper().strip('-')}")
    for y in [str(v) for v in range(2022, 2033)]:
        m_ = seen[("projection", "male", "Total", "Total country", y)]
        f_ = seen[("projection", "female", "Total", "Total country", y)]
        t_ = seen[("projection", "total", "Total", "Total country", y)]
        if abs(m_ + f_ - t_) > 3:
            diffs.add(("M+F", "total", "Total country", y, m_ + f_, t_))

    # --- 4-3: county x sex, 2022/2027/2032/2035 ---------------------------
    for r in ds["lisgis-population-projection-table-4-3"]["rows"]:
        yr, word = [s.strip() for s in r["measure"].split("/")]
        sex = _SEX_WORD[word]
        if r["geo_level"] == "country":
            k = ("projection", sex, "Total", "Total country", yr)
            if k in seen:
                check(k, r["value"], "4-3")
            else:
                emit(*k, r["value"], "LR_PROJ2022_T4.3")
            continue
        emit("projection", sex, "Total", r["county_name"], yr, r["value"],
             "LR_PROJ2022_T4.3")
    if diffs != _KNOWN:
        raise ValueError(f"LISGIS: inconsistencies changed: new {sorted(diffs - _KNOWN)}, "
                         f"gone {sorted(_KNOWN - diffs)}")
    return pd.DataFrame(out)
