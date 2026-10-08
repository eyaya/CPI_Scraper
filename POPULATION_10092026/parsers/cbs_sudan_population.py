"""CBS Sudan — 5th Sudan Population and Housing Census 2008, "Population" tables
(the census-tables ZIP, a Wayback `id_` copy of CBS's own file; cbs.gov.sd no
longer resolves -- the same file `labour/` and `unemployment/` read).

THE CENSUS PREDATES SOUTH SUDAN'S 2011 SECESSION. Its tables print an "All
Sudan" block, then North and South (P02) or each of the 25 states (P01, P04).
Only TODAY'S SUDAN is collected:

* P02  the "North" region block -> geography "Total country", by 5-year age
       group and sex;
* P01  the 15 northern states, by 5-year age group and sex;
* P04  the 15 northern states, by SINGLE year of age and sex.

The ten southern states and the "SUDAN TOTAL" / "South" blocks are not read:
filing a pre-2011 all-Sudan figure as Sudan would put South Sudan's population
inside a country that no longer contains it.

UNIVERSE (each sheet's own footnote): excludes the institutional population,
the homeless, night travellers and (in the South) the cattle-camp population.
Only the Total/Male/Female columns are read; the urban / rural / nomad
("mode of living") columns have no home in this schema.

CHECKED EVERY RUN: male + female = total on every row, to +-1 -- CBS's
weighted counts are rounded independently, and 8-15% of rows (P01 35 of 442,
P04 664 of 2 991) miss by exactly one person, never more; the 15 northern states'
totals sum to the North block (30 504 166, to one person per state); P01's and P04's state totals agree
(the "Total" age row is emitted once).

State names are CBS's own spellings ("Nahr Elnil", "Algadarif", "Aljazeera").
Period 2008 (census night, April 2008).

CROSS-CHECK: North 30 504 166 (M 15 413 282 / F 15 090 883); Khartoum state
(P01 block); Northern state 686 098.
"""
from __future__ import annotations

import io
import re
import zipfile

import pandas as pd
import xlrd

_NORTH_STATES = [
    "Northern", "Nahr Elnil", "Red Sea", "Kassala", "Algadarif", "Khartoum",
    "Aljazeera", "White Nile", "Sinnar", "Blue Nile", "Northern Kordofan",
    "Southern Kordofan", "Northern Darfur", "Western Darfur", "Southern Darfur",
]
_SOUTH_STATES = [
    "Upper Nile", "Jonglei", "Unity", "Warrab", "Northern Bahr El Ghazal",
    "Western Bahr El Ghazal", "Lakes", "Western Equatoria", "Central Equatoria",
    "Eastern Equatoria",
]


def _sheet(zf: zipfile.ZipFile, stem: str):
    name = next(n for n in zf.namelist()
                if n.endswith(".xls") and "/Population/" in n
                and n.rsplit("/", 1)[1].startswith(stem))
    return xlrd.open_workbook(file_contents=zf.read(name)).sheet_by_index(0)


def _age(a) -> str:
    if isinstance(a, float):
        return str(int(a))
    a = re.sub(r"[\s\xa0]+", " ", str(a)).strip()
    return "Total" if a == "Total" else a


def _blocks(sh) -> dict[str, list[tuple[str, list[float]]]]:
    """Block heading -> [(age label, [total, male, female]), ...]."""
    out, cur = {}, None
    for r in range(3, sh.nrows):
        head = str(sh.cell_value(r, 0)).replace("\xa0", " ").strip()
        vals = [sh.cell_value(r, c) for c in (1, 2, 3)]
        if head.startswith("This table excludes"):
            break
        if head and all(v == "" for v in vals):
            cur = head
            out[cur] = []
            continue
        if cur is None or vals[0] == "":
            continue
        # CBS prints "-" for a zero count (single-year ages in small states).
        out[cur].append((_age(sh.cell_value(r, 0)),
                         [0.0 if str(v).strip() == "-" else float(v) for v in vals]))
    return out


def _rows(block, geo, code):
    rows = []
    for age, (tot, m, f) in block:
        if abs(m + f - tot) > 1:
            raise ValueError(f"CBS Sudan {code} {geo} {age}: {m} + {f} != {tot}")
        for sex, v in (("total", tot), ("male", m), ("female", f)):
            rows.append({"series_type": "census", "sex": sex, "age_group": age,
                         "geography": geo, "period": "2008",
                         "frequency": "annual", "measure": "count",
                         "value": v, "unit": "persons", "series_code": code})
    return rows


def parse(path: str) -> pd.DataFrame:
    zf = zipfile.ZipFile(path)
    p02 = _blocks(_sheet(zf, "P02"))
    if "North" not in p02:
        raise ValueError(f"CBS Sudan P02: no North block in {list(p02)}")
    rows = _rows(p02["North"], "Total country", "CBS 2008 P02")
    north_total = dict(p02["North"])["Total"][0]

    for stem in ("P01", "P04"):
        blocks = _blocks(_sheet(zf, stem))
        missing = [s for s in _NORTH_STATES + _SOUTH_STATES if s not in blocks]
        if missing:
            raise ValueError(f"CBS Sudan {stem}: state blocks missing {missing}")
        s = sum(dict(blocks[st])["Total"][0] for st in _NORTH_STATES)
        if abs(s - north_total) > len(_NORTH_STATES):
            raise ValueError(f"CBS Sudan {stem}: northern states sum to {s}, "
                             f"North block {north_total}")
        for st in _NORTH_STATES:
            rows += _rows(blocks[st], st, f"CBS 2008 {stem}")

    df = pd.DataFrame(rows)
    key = ["series_type", "sex", "age_group", "geography", "period", "measure"]
    clash = df[df.duplicated(key, keep=False)].groupby(key)["value"].nunique()
    if (clash > 1).any():
        raise ValueError(f"CBS Sudan: P01 and P04 disagree on {clash[clash > 1].index[0]}")
    return df.drop_duplicates(key)
