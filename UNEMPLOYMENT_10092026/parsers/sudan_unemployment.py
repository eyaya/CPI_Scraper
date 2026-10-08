"""Sudan — Central Bureau of Statistics (CBS), read from the Wayback Machine's
`id_` copies of CBS's own files: cbs.gov.sd no longer resolves.

TWO CBS PUBLICATIONS, NEVER MIXED:

* "Labor Force" (CBS statistical booklet, 2019 upload, bilingual) -- republishes
  the 2011 Sudan Labour Force Survey (SLFS), "conducted in cooperation between
  the Ministry of Labor and the Central Bureau of Statistics" (the booklet's
  own definitions page). Unemployed = not working, looking for work AND ready
  to work in the last 7 days -> `strict`. National base 10+, with a 15+ series
  "for international comparison" (the booklet's words).
* "5th Population and Housing Census 2008", Economic Activity tables E1
  (Census_Tables.zip, 2011 upload) -- counts only; the census publishes no
  rates. Base 10+.

THE 2008 CENSUS PREDATES SOUTH SUDAN'S 2011 SECESSION, and its tables print
"All Sudan", "Northern Sudan" and "Southern Sudan" blocks plus 25 states. ONLY
the Northern Sudan block and the 15 northern states are collected -- the
territory of today's Sudan. South Sudan is collected separately from its own
NBS. This is not an assumption: the booklet's "Sudan, Census 2008"
economically active 10+ (8,027,413) is exactly E1's Northern Sudan figure,
and the parser asserts that the 15 states sum to the Northern Sudan block.
The census excludes the institutional, homeless and night-traveller
populations (the tables' own footnote).

COLLECTED
* SLFS 2011: economically active / employed / unemployed by sex, 15+, in
  thousands (booklet table "Economically Active Population ... By Sex and by
  Mode of Living" -- TOTAL block only, see below); labour force 10+ (persons);
  labour force by state, 10+ total and by sex, 15+ total and by sex
  (thousands); economically active youth 15-24 total / urban / rural
  (persons); youth unemployment rates for 15-24, 15-29, 15-19 and 20-24 by
  sex x Sudan / urban / rural (column order read from the rendered page:
  Sudan MF, M, F | Urban MF, M, F | Rural MF, M, F).
* Census 2008 (E1): population 10+, economically active, employed,
  unemployed (and its two published parts: worked before / first-time
  seekers), not economically active -- for Northern Sudan by residence (urban
  / rural / nomad), sex and five-year age group, and for each northern state
  by residence and sex.

REFUSED -- PUBLISHED URBAN/RURAL LABELS THAT CANNOT BE TRUE. The SLFS table's
"Urban" block reads 5,744.1 thousand economically active 15+ and "Rural"
3,228.0 -- but the booklet's own youth table (text) gives urban 573,052 and
rural 1,313,172 aged 15-24, every census figure puts rural above urban, and
the urban/rural unemployment levels (921.5 vs 740.7) only fit the youth
rates' urban > rural pattern if the labels are swapped. The evidence is
indirect, so neither block is collected (the SLIHS 2018 precedent: labels
that look swapped, with nothing in the table to settle it, are refused). The
bar charts of economically active by "mode of living" and by sex are not
read either: their data labels are not tied to their categories in the text.

NOT COLLECTED: the booklet's census figures (duplicates of E1, except youth
15-24 by sex, which E1 does not print -- collected); the "Projection
Unemployment Rates" sheet (projections, not survey results); youth by
education (chart, categories only in Arabic); E6 (E1's measures again in
broader age bands); census reasons for inactivity.

A PUBLISHED GAP KEPT: E1's population 10+ exceeds economically active + not
active + activity not stated by about 0,7% (All Sudan 26 671 458 against
26 476 087). Each measure is collected as printed; only economically active =
employed + unemployed is asserted, which holds exactly.

CROSS-CHECK: SLFS 2011 15+ economically active 8,972.1 thousand, employed
7,309.9, unemployed 1,662.2; youth 15-24 unemployment 33.8 (urban 49.4, rural
27); Khartoum labour force 10+ 1,602.0 thousand. Census 2008 Northern Sudan:
economically active 8 027 413, unemployed 1 350 003, nomad economically
active 901 500.
"""
from __future__ import annotations

import os
import re
import zipfile

import fitz  # PyMuPDF
import pandas as pd
import xlrd

from ._common import row

_LFS = ("Sudan Labour Force Survey (SLFS) 2011, Ministry of Labour with CBS, "
        "as published in CBS 'Labor Force'")
_CENSUS = ("5th Sudan Population and Housing Census 2008, Northern Sudan "
           "(today's Sudan)")
_NORTH_STATES = [
    "Northern", "Nahr El Nil", "Red Sea", "Kassala", "Al Gedarif", "Khartoum",
    "Al Gezira", "White Nile", "Sinnar", "Blue Nile", "North Kordofan",
    "South Kordofan", "North Darfur", "West Darfur", "South Darfur"]
_LFS_STATES = [
    "Northern", "River Nile", "Red Sea", "Kassala", "Al-Gadarif", "Khartoum",
    "Al-Gezira", "White Nile", "Sinnar", "Blue Nile", "Northern Kordufan",
    "Southern Kordufan", "Northern Darfur", "Western Darfur", "Southern Darfur"]
_NUM = re.compile(r"^-?[\d,]+(?:\.\d+)?$")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


# ---------------------------------------------------------------- booklet --
def _pages(path: str) -> list[list[str]]:
    """Each page as its English/numeric lines, in reading order. The Arabic
    text layer is mis-encoded and is never read."""
    out = []
    with fitz.open(path) as doc:
        for page in doc:
            lines = [ln.strip() for ln in page.get_text().splitlines()]
            out.append([ln for ln in lines if ln and re.search(r"[A-Za-z0-9]", ln)
                        and not re.search(r"[؀-ۿ]", ln)])
    return out


def _page_with(pages, needle: str) -> list[str]:
    hits = [p for p in pages if any(needle in ln for ln in p)]
    if len(hits) != 1:
        raise ValueError(f"CBS 'Labor Force': {len(hits)} pages carry {needle!r}")
    return hits[0]


def _lfs(**kw) -> dict:
    return row(survey=_LFS, period="2011", reference_period="SLFS 2011",
               frequency="ad_hoc", **kw)


def _labour_force_numbers(pages) -> list[dict]:
    """The 'Labor Force in Numbers' table: label line, number, source line.
    Only the SLFS 10+ figure is taken (the 15+ figure is the Total block of
    the sex table; the census figures are E1's)."""
    p = _page_with(pages, "Labor Force in Numbers")
    out = []
    for i, ln in enumerate(p):
        if ln.startswith("Number of economically active population in Sudan 10 years"):
            val, src = p[i + 1], p[i + 2]
            if "Labor Force Survey" in src:
                out.append(_lfs(topic="labour_force", value=_num(val),
                                series_label=ln, working_age_base="10+",
                                series_code="CBS LF: in numbers"))
    if len(out) != 1 or out[0]["value"] != 9_288_718:
        raise ValueError(f"CBS 'Labor Force': SLFS 10+ figure read as {out}")
    return out


def _sex_table(pages) -> list[dict]:
    p = _page_with(pages, "Economically Active Population in Both (Employed/Unemployed) "
                          "By Sex and by Mode of Living")
    nums, rows, areas = [], [], []
    for ln in p:
        if _NUM.match(ln):
            nums.append(_num(ln))
        elif ln in ("Both Sexes", "Male", "Female"):
            rows.append((ln, nums[-3:]))
            nums = []
        elif ln in ("Total", "Urban", "Rural"):
            areas.append(ln)
    if areas != ["Total", "Urban", "Rural"] or len(rows) != 9:
        raise ValueError(f"CBS 'Labor Force' sex table: areas {areas}, {len(rows)} rows")
    for sex, (ea, emp, un) in rows:
        if abs(ea - emp - un) > 0.15:
            raise ValueError(f"CBS 'Labor Force' sex table: {sex} {ea} != {emp}+{un}")
    out = []
    # Only the Total block -- see the module docstring on the area labels.
    for sex, (ea, emp, un) in rows[:3]:
        for topic, v, lab in (("labour_force", ea, "Economically Active"),
                              ("employed", emp, "Employed"),
                              ("unemployed", un, "Unemployed")):
            out.append(_lfs(topic=topic, value=v, series_label=lab,
                            unit="thousand_persons", working_age_base="15+",
                            sex={"Both Sexes": "total", "Male": "male",
                                 "Female": "female"}[sex],
                            series_code="CBS LF: by sex and mode of living"))
    return out


def _youth_active(pages) -> list[dict]:
    p = _page_with(pages, "Number of economically active youth in Sudan aged 15-24")
    want = {
        "Number of economically active youth in Sudan aged 15-24":
            ("Census 2008", "Census 2008", {}),
        "Number of economically active youth in Sudan aged 15-24, males":
            ("Census 2008", "Census 2008", {"sex": "male"}),
        "Number of economically active youth in Sudan aged (15-24), females":
            ("Census 2008", "Census 2008", {"sex": "female"}),
        "Number of economically active youth in Sudan aged 15-24, Urban":
            ("Source :Labor Force Survey", None, {"locality": "urban",
                                                  "locality_label": "Urban"}),
        "Number of economically active youth in Sudan aged 15-24, rural":
            ("Source :Labor Force Survey", None, {"locality": "rural",
                                                  "locality_label": "Rural"}),
    }
    out, seen = [], []
    for i, ln in enumerate(p):
        if ln not in want:
            continue
        val, src = _num(p[i + 1]), p[i + 2]
        if ln == "Number of economically active youth in Sudan aged 15-24" and \
                "Labor Force Survey" in src:
            ctx, census = {}, False
        else:
            exp_src, _, ctx = want[ln]
            if src != exp_src:
                raise ValueError(f"CBS 'Labor Force' youth: {ln!r} sourced {src!r}")
            census = exp_src.startswith("Census")
        seen.append(ln)
        if census:
            out.append(row(survey=_CENSUS + ", as published in CBS 'Labor Force'",
                           period="2008", reference_period="Census 2008",
                           frequency="ad_hoc", topic="labour_force", value=val,
                           series_label=ln, age_group="15-24",
                           working_age_base="10+",
                           series_code="CBS LF: youth in numbers", **ctx))
        else:
            out.append(_lfs(topic="labour_force", value=val, series_label=ln,
                            age_group="15-24", working_age_base="10+",
                            series_code="CBS LF: youth in numbers", **ctx))
    if len(out) != 6:
        raise ValueError(f"CBS 'Labor Force' youth: read {seen}")
    lfs = {r["locality"]: r["value"] for r in out if r["period"] == "2011"}
    if abs(lfs["all"] - lfs["urban"] - lfs["rural"]) > 2:
        raise ValueError("CBS 'Labor Force' youth: urban + rural != total")
    return out


_YOUTH_COLS = [(loc, lab, sex) for loc, lab in
               (("all", "Total"), ("urban", "Urban"), ("rural", "Rural"))
               for sex in ("total", "male", "female")]


def _youth_rates(pages) -> list[dict]:
    p = _page_with(pages, "Youth Unemployment Rates in Sudan by Sex and Mode of Living")
    out, i = [], 0
    while i < len(p):
        m = re.fullmatch(r"(15-24|15-29|15-19|20-24)", p[i])
        if m and i + 9 < len(p) and all(_NUM.match(x) for x in p[i + 1:i + 10]):
            vals = [_num(x) for x in p[i + 1:i + 10]]
            for k in range(0, 9, 3):        # MF lies between M and F
                if not min(vals[k + 1], vals[k + 2]) <= vals[k] <= max(vals[k + 1], vals[k + 2]):
                    raise ValueError(f"CBS youth rates {m.group(1)}: MF outside M/F")
            if not min(vals[3], vals[6]) <= vals[0] <= max(vals[3], vals[6]):
                raise ValueError(f"CBS youth rates {m.group(1)}: Sudan outside urban/rural")
            for (loc, lab, sex), v in zip(_YOUTH_COLS, vals):
                out.append(_lfs(topic="youth_unemployment_rate", definition="strict",
                                value=v, series_label="Youth Unemployment Rates",
                                age_group=m.group(1), sex=sex, locality=loc,
                                locality_label=lab, working_age_base="10+",
                                series_code="CBS LF: youth unemployment rates"))
            i += 10
        else:
            i += 1
    if len(out) != 36:
        raise ValueError(f"CBS youth rates: {len(out)} values, want 36")
    return out


def _states(pages) -> list[dict]:
    p14 = _page_with(pages, "Labor Force by State 10 years and Over (In thousands)")
    p15 = _page_with(pages, "Labor Force by State and Sex in 2011(In thousands)")
    tot = {}
    for i, ln in enumerate(p14):
        if ln in _LFS_STATES and _NUM.match(p14[i - 1]):
            tot[ln] = _num(p14[i - 1])
    by_sex = {}
    for i, ln in enumerate(p15):
        if ln in _LFS_STATES:
            vals = p15[i - 5:i]
            if not all(_NUM.match(v) for v in vals):
                raise ValueError(f"CBS LF by state and sex: {ln} reads {vals}")
            by_sex[ln] = [_num(v) for v in vals]   # 10+ M, F | 15+ T, M, F
    if sorted(tot) != sorted(_LFS_STATES) or sorted(by_sex) != sorted(_LFS_STATES):
        raise ValueError("CBS LF by state: not all 15 states read")
    out = []
    for st in _LFS_STATES:
        m10, f10, t15, m15, f15 = by_sex[st]
        if abs(m10 + f10 - tot[st]) > 1.0 or abs(m15 + f15 - t15) > 0.3:
            raise ValueError(f"CBS LF by state: {st} sexes do not sum")
        for v, sex, base, code in ((tot[st], "total", "10+", "state"),
                                   (m10, "male", "10+", "state and sex"),
                                   (f10, "female", "10+", "state and sex"),
                                   (t15, "total", "15+", "state and sex"),
                                   (m15, "male", "15+", "state and sex"),
                                   (f15, "female", "15+", "state and sex")):
            out.append(_lfs(topic="labour_force", value=v, unit="thousand_persons",
                            series_label="Labor Force", sex=sex, geography=st,
                            working_age_base=base, series_code=f"CBS LF: by {code}"))
    return out


# ----------------------------------------------------------------- census --
_E1_COLS = [  # (column, topic, series_label as printed)
    (4, "working_age_population", "Total Population (10 years and over)"),
    (5, "labour_force", "Total Economically Active"),
    (6, "employed", "Employed"),
    (9, "unemployed", "Unemployed"),
    (10, "unemployed", "Unemployed: Worked Before and Seeking Work"),
    (11, "unemployed", "Unemployed: Seeking work for the first time"),
    (12, "outside_labour_force", "Not economically active (Q20_REASON_REC: Total)"),
]
_RES = {"Total": ("all", "Total"), "Urban": ("urban", "Urban"),
        "Rural": ("rural", "Rural"), "Nomad": ("other", "Nomad")}
_SEX = {"Total": "total", "Male": "male", "Female": "female"}


def _e1_rows(xls: bytes) -> dict:
    """{(geo, residence, sex, age): [values by column]} for every data row."""
    sh = xlrd.open_workbook(file_contents=xls).sheet_by_index(0)
    geo = res = sex = None
    out = {}
    for r in range(sh.nrows):
        c = [str(sh.cell_value(r, k)).strip() for k in range(4)]
        if c[0].startswith("E1-") or c[0].startswith("This table") or \
                re.match(r"^\d\.", c[0]):
            continue
        if c[0]:
            geo = c[0]
        if c[1]:
            res = c[1]
        if c[2]:
            sex = c[2]
        if not c[3] or not isinstance(sh.cell_value(r, 4), float):
            continue
        out[(geo, res, sex, c[3])] = [sh.cell_value(r, k) if isinstance(
            sh.cell_value(r, k), float) else None for k in range(sh.ncols)]
    return out


def _census(zip_path: str) -> list[dict]:
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist()
                    if n.endswith("Economic_Activity/E1.xls"))
        e1 = _e1_rows(z.read(name))
    north = e1[("Northern Sudan", "Total", "Total", "Total")]
    if round(north[5]) != 8_027_413:
        raise ValueError(f"Census E1: Northern Sudan economically active {north[5]}")
    states = sum(e1[(s, "Total", "Total", "Total")][5] for s in _NORTH_STATES)
    if abs(states - north[5]) > 1:
        raise ValueError(f"Census E1: northern states sum to {states}, "
                         f"Northern Sudan prints {north[5]}")
    out = []
    for (geo, res, sex, age), v in e1.items():
        if geo == "Northern Sudan":
            geography = "Total country"
        elif geo in _NORTH_STATES:
            if age != "Total":
                continue            # states: residence x sex only
            geography = geo
        else:
            continue                # All Sudan, Southern Sudan, southern states
        if abs(v[5] - v[6] - v[9]) > 0.01:
            raise ValueError(f"Census E1 {geo}/{res}/{sex}/{age}: EA != E + U")
        loc, loc_lab = _RES[res]
        for col, topic, label in _E1_COLS:
            if v[col] is None:
                continue
            out.append(row(survey=_CENSUS, period="2008",
                           reference_period="Census 2008 (April 2008)",
                           frequency="ad_hoc", topic=topic,
                           value=round(v[col], 9), series_label=label,
                           sex=_SEX[sex],
                           age_group="Total" if age == "Total" else
                           re.sub(r"\s*-\s*", "-", age),
                           geography=geography, locality=loc,
                           locality_label=loc_lab, working_age_base="10+",
                           series_code="Census 2008 E1"))
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    pages = _pages(path)
    rows = (_labour_force_numbers(pages) + _sex_table(pages) +
            _youth_active(pages) + _youth_rates(pages) + _states(pages))
    zips = [p for p in (extras or []) if p.lower().endswith(".zip")]
    if len(zips) != 1:
        raise ValueError(f"Sudan: expected the census tables ZIP among extras, got {extras}")
    rows += _census(zips[0])
    return pd.DataFrame(rows)
