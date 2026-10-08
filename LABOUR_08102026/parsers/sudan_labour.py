"""Sudan — Central Bureau of Statistics (CBS), read from the Wayback Machine's
`id_` copies of CBS's own files (cbs.gov.sd no longer resolves). The same two
files `unemployment/` reads; each indicator takes only its own tables.

* "Labor Force" booklet (CBS, 2019 upload): the 2011 Sudan Labour Force Survey
  (Ministry of Labour with CBS). Employed persons by major occupation, % by
  Sudan / urban / rural x both sexes / male / female, for 10+ and for 15+ --
  read from the text layer; the column order (Sudan MF, M, F | Urban MF, M, F
  | Rural MF, M, F) was read off the rendered page and is asserted every run:
  each MF lies between its M and F, and each column sums to 100.
* 5th Population and Housing Census 2008, Economic Activity tables (CBS
  "Census _Tables.zip"): E2 major industry and E3 major occupation groups,
  counts, and E4 status in employment of the EMPLOYED.

THE CENSUS PREDATES THE 2011 SECESSION. Only its "Northern Sudan" block and
the 15 northern states are collected -- the territory of today's Sudan; the
parser asserts that the states sum to the block. South Sudan is collected
from its own NBS.

E2 AND E3 DISTRIBUTE THE ECONOMICALLY ACTIVE WHO HAVE A JOB OR HAD ONE --
the employed plus the unemployed who worked before (E2's total, 10 339 049
for All Sudan, is exactly employed + "unemployed worked before" in E4), by
the industry / occupation of the current or last job. The census prints no
industry or occupation table for the employed alone, so that universe is
collected and named in `survey` on every row, as for South Sudan's census.
E4's EMPLOYED block is the employed proper, and is what the status rows use.

Categories are printed in ISIC Rev.4 / ISCO-08 shape (Information and
communication; Water supply, sewerage ...; Managers ... Elementary
occupations) but neither scheme is named in the tables -> National. Labels
are kept as printed, typos included ("Finacial", "Mangers", "Techicians").

Census rows: Northern Sudan by residence (urban / rural / nomad) and sex, and
each northern state by residence and sex; age totals only. Values are
weighted census estimates stored with decimals; kept to 9 decimal places.

CROSS-CHECK: SLFS 2011 (10+) skilled agricultural workers 39.6 (rural women
74.9), services & sales 17.4; census 2008 Northern Sudan employed 6 677 410,
of whom own-account workers and unpaid family workers are the largest
statuses (see the output).
"""
from __future__ import annotations

import re
import zipfile

import fitz  # PyMuPDF
import pandas as pd
import xlrd

from . import _common as C

_LFS = ("Sudan Labour Force Survey (SLFS) 2011, Ministry of Labour with CBS, "
        "as published in CBS 'Labor Force'")
_CENSUS_EA = ("5th Sudan Population and Housing Census 2008, Northern Sudan "
              "(today's Sudan): economically active 10+ with a current or "
              "previous job (employed + unemployed who worked before)")
_CENSUS_EMP = ("5th Sudan Population and Housing Census 2008, Northern Sudan "
               "(today's Sudan): employed 10+")
_NORTH_STATES = [
    "Northern", "Nahr El Nil", "Red Sea", "Kassala", "Al Gedarif", "Khartoum",
    "Al Gezira", "White Nile", "Sinnar", "Blue Nile", "North Kordofan",
    "South Kordofan", "North Darfur", "West Darfur", "South Darfur"]
_OCC = ["Managers", "Professionals", "Technicians & associate professionals",
        "Clerical support", "Services & sales",
        "Skilled agricultural, forestry & fisheries workers", "Craft & related",
        "Plant and machine operators", "Elementary occupation",
        "Occupation not stated"]
_COLS9 = [(loc, lab, sex) for loc, lab in
          (("all", "Total"), ("urban", "Urban"), ("rural", "Rural"))
          for sex in ("total", "male", "female")]
_NUM = re.compile(r"^\d+(?:\.\d+)?$")


# ---------------------------------------------------------------- booklet --
def _occupation(path: str) -> list[dict]:
    out = []
    with fitz.open(path) as doc:
        pages = [[ln.strip() for ln in p.get_text().splitlines() if ln.strip()]
                 for p in doc]
    for base in ("10", "15"):
        title = (f"Employed persons ({base} Years and over) by Major occupation, "
                 f"rural/urban area and Sex- 2011 (%)")
        hits = [p for p in pages if title in p]
        if len(hits) != 1:
            raise ValueError(f"CBS 'Labor Force': {len(hits)} pages titled {title!r}")
        lines = hits[0][hits[0].index(title) + 1:]
        rows, nums, label = [], [], []
        for ln in lines:
            if ln.startswith("Source"):
                break
            if _NUM.match(ln):
                if label and nums:
                    rows.append((" ".join(label), nums))
                    nums, label = [], []
                nums.append(float(ln))
            elif nums and not re.search(r"[؀-ۿ]", ln) and ln != "Major occupation":
                label.append(ln)
        if label and nums:
            rows.append((" ".join(label), nums))
        if [r[0] for r in rows] != _OCC or any(len(r[1]) != 9 for r in rows):
            raise ValueError(f"CBS occupation {base}+: read {[(r[0], len(r[1])) for r in rows]}")
        for j in range(9):
            s = sum(r[1][j] for r in rows)
            if abs(s - 100) > 0.6:
                raise ValueError(f"CBS occupation {base}+: column {j} sums to {s:.1f}")
        for lab, v in rows:
            for k in (0, 3, 6):
                if not min(v[k + 1], v[k + 2]) - 0.05 <= v[k] <= max(v[k + 1], v[k + 2]) + 0.05:
                    raise ValueError(f"CBS occupation {base}+: {lab} MF outside M/F")
            for (loc, loc_lab, sex), val in zip(_COLS9, v):
                out.append(C.row(topic="occupation", characteristic=lab,
                                 classification="National", value=val,
                                 survey=_LFS, period="2011",
                                 reference_period="SLFS 2011", frequency="ad_hoc",
                                 measure="share", unit="percent", sex=sex,
                                 locality=loc, locality_label=loc_lab,
                                 working_age_base=f"{base}+",
                                 series_code=f"CBS LF: occupation {base}+"))
    return out


# ----------------------------------------------------------------- census --
_RES = {"Total": ("all", "Total"), "Urban": ("urban", "Urban"),
        "Rural": ("rural", "Rural"), "Nomad": ("other", "Nomad")}
_SEX = {"Total": "total", "Male": "male", "Female": "female"}


def _sheet(z: zipfile.ZipFile, name: str):
    n = next(x for x in z.namelist() if x.endswith(f"Economic_Activity/{name}"))
    return xlrd.open_workbook(file_contents=z.read(n)).sheet_by_index(0)


def _blocks(sh, header_row: int, first: int, last: int) -> tuple[list, dict]:
    """Category names from `header_row` (columns first..last) and every
    age-Total data row keyed by (geo, residence, sex)."""
    cats = [str(sh.cell_value(header_row, c)).strip() for c in range(first, last + 1)]
    geo = res = sex = None
    data = {}
    for r in range(header_row + 1, sh.nrows):
        c = [str(sh.cell_value(r, k)).strip() for k in range(4)]
        if c[0].startswith(("E2", "E3", "E4", "This table")) or re.match(r"^\d\.", c[0]):
            continue
        if c[0] and c[0] not in ("North / South /STATE",):
            geo = c[0]
        if c[1] in _RES:
            res = c[1]
        if c[2] in _SEX:
            sex = c[2]
        if c[3] != "Total" or not isinstance(sh.cell_value(r, first), float):
            continue
        data[(geo, res, sex)] = [sh.cell_value(r, k) for k in range(first, last + 1)]
    return cats, data


def _census_table(z, name, header_row, first, last, topic, survey, code,
                  total_col=0) -> list[dict]:
    sh = _sheet(z, name)
    cats, data = _blocks(sh, header_row, first, last)
    if cats[total_col] != "Total":
        raise ValueError(f"Census {name}: first column is {cats[total_col]!r}")
    north = data[("Northern Sudan", "Total", "Total")]
    states = sum(data[(s, "Total", "Total")][total_col] for s in _NORTH_STATES)
    if abs(states - north[total_col]) > 1:
        raise ValueError(f"Census {name}: states sum to {states}, North {north[total_col]}")
    out = []
    for (geo, res, sex), vals in data.items():
        if geo == "Northern Sudan":
            geography = "Total country"
        elif geo in _NORTH_STATES:
            geography = geo
        else:
            continue
        if abs(sum(vals[1:]) - vals[0]) > 0.01 * max(vals[0], 1) + 1:
            raise ValueError(f"Census {name} {geo}/{res}/{sex}: categories "
                             f"{sum(vals[1:])} != Total {vals[0]}")
        loc, loc_lab = _RES[res]
        for cat, v in zip(cats, vals):
            if not isinstance(v, float):
                continue
            out.append(C.row(topic=topic, characteristic=cat,
                             classification="National", value=round(v, 9),
                             survey=survey, period="2008",
                             reference_period="Census 2008 (April 2008)",
                             frequency="ad_hoc", measure="count", unit="persons",
                             sex=_SEX[sex], geography=geography, locality=loc,
                             locality_label=loc_lab, working_age_base="10+",
                             series_code=code))
    return out


def _census(zip_path: str) -> list[dict]:
    with zipfile.ZipFile(zip_path) as z:
        rows = _census_table(z, "E2.xls", 3, 4, 26, "industry", _CENSUS_EA,
                             "Census 2008 E2")
        rows += _census_table(z, "E3.xls", 3, 4, 14, "occupation", _CENSUS_EA,
                              "Census 2008 E3")
        # E4: columns 4-10 are the EMPLOYED (Total + six statuses); 11-17 the
        # unemployed who worked before, which are not employment.
        rows += _census_table(z, "E4.xls", 4, 4, 10, "employment_status",
                              _CENSUS_EMP, "Census 2008 E4")
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = _occupation(path)
    zips = [p for p in (extras or []) if p.lower().endswith(".zip")]
    if len(zips) != 1:
        raise ValueError(f"Sudan: expected the census tables ZIP among extras, got {extras}")
    rows += _census(zips[0])
    return pd.DataFrame(rows)
