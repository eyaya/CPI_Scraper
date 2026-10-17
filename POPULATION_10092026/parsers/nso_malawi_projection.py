"""NSO Malawi -- "Population Projections 2018-2050" (2018 Census thematic
report), annexes:

* Annex 1.1-1.17 -- Malawi projected population by five-year age group and
  sex, plus NSO's "Special Age Groups" (Less than 1, 1-4, 6-13, 14-17, 0-14,
  15-24, 15-44, 15-49, 15+, 18+, 50+, 60+), 2018-2050, two years per page
  (2050 alone on Annex 1.17).
* Annex 2.1-2.32 -- the same by five-year age group and sex for each of the
  32 districts/cities, 2018-2043, four years per page (two tables across, two
  down). Mangochi's last page (p.174, 2042-2043 by position) is printed
  without its year headers and is skipped, not dated by guess.

Added 2026-10-13 as a SECOND Malawi descriptor (malawi_projections.yaml) beside
the 2018 census Series A workbook.

PAGE GEOMETRY, NOT READING ORDER. Each page prints its tables two-across; a
row is split at the gutter between the left and right table and filed under
the nearest year header ABOVE it on its own side. A district's years run on
across pages without a repeated caption, so the geography is the last Annex
2.n caption seen.

Checks per table: the bands sum to the printed Total, Male + Female = Both
sexes on every row, and every table has every row exactly once. The 32
districts' Totals must sum to the national Total for each year they cover.

Geography names are NSO's own in THIS report ("Lilongwe Rural", "Blantyre
Rural", "Mzuzu City", ...); the census workbook calls the rural districts
"Lilongwe" and "Blantyre". Regions are not published here. Never sum the
districts with "Total country".

Table 4.1 (indicators: growth rate, births, deaths, e0, IMR, TFR, ...) is
deferred: its wrapped multi-level header cannot be bound to its columns
unambiguously from the text layer.

series_type = projection.
"""
from __future__ import annotations

import re

import fitz
import pandas as pd

_SC_NAT = "NSO_MW_PROJ_2018_2050_A1"
_SC_DIST = "NSO_MW_PROJ_2018_2050_A2"
_BANDS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
          "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
          "75-79", "80-84", "85-89", "90-94", "95+"]
_SPECIAL = {"Less than 1": "<1", "1-4": "1-4", "6-13": "6-13", "14-17": "14-17",
            "0-14": "0-14", "15-24": "15-24", "15-44": "15-44", "15-49": "15-49",
            "15+": "15+", "18+": "18+", "50+": "50+", "60+": "60+"}
_ROWS = {"Total": "Total", **{b: b for b in _BANDS}, **_SPECIAL}
_YEAR = re.compile(r"^20[1-5]\d$")
_NUM = re.compile(r"^\d{1,3}(,\d{3})*$")
_CAP2 = re.compile(r"Annexe?\s*2\.\s*(\d+)\s*:?\s*Population Projection By Age "
                   r"Groups And Sex,\s*(.+?)\s*$", re.I)
_CAP1 = re.compile(r"Annexe?\s*1\.\s*(\d+)\s*:", re.I)
_MID = 306          # gutter between the two tables (page width 612)


def _lines(page):
    """[(y, [(x0, x1, word), ...])] per visual line, clustered by distance."""
    ws = sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    out = []
    for x0, y0, x1, y1, w, *_ in ws:
        y = (y0 + y1) / 2
        if out and y - out[-1][0] <= 2.5:
            out[-1][1].append((x0, x1, w))
        else:
            out.append([y, [(x0, x1, w)]])
    for ln in out:
        ln[1].sort()
    return out


def _half(words):
    """(label, values) for one table's side of a line. Digits split by a
    hair-width gap inside one figure are rejoined by x-gap."""
    label, nums = [], []
    for x0, x1, w in words:
        fig = re.fullmatch(r"[\d,]+", w)
        # "Less than 1": its 1 is part of the label
        if not nums and (not fig or not label or " ".join(label) == "Less than"):
            label.append(w)
            continue
        if not fig:
            return " ".join(label), None      # prose, not a table row
        if nums and x0 - nums[-1][1] < 2.0:
            nums[-1] = (nums[-1][0], x1, nums[-1][2] + w)
        else:
            nums.append((x0, x1, w))
    lab = " ".join(label)
    vals = []
    for _, _, n in nums:
        if not _NUM.match(n):
            return lab, None
        vals.append(float(n.replace(",", "")))
    return lab, vals


def _row(sex, age, geo, year, value, sc):
    return {"series_type": "projection", "sex": sex, "age_group": age,
            "geography": geo, "period": str(year), "frequency": "annual",
            "measure": "count", "value": float(value), "unit": "persons",
            "series_code": sc}


def parse(local_path: str) -> pd.DataFrame:
    tables: dict[tuple[str, str], dict] = {}   # (geo, year) -> {row: (b, m, f)}
    geo = None
    with fitz.open(local_path) as doc:
        for page in doc:
            text = page.get_text("text")
            m1 = _CAP1.search(text)
            for ln in text.splitlines():
                m2 = _CAP2.search(ln)
                if m2:
                    geo = re.sub(r"\s+District$", "", m2.group(2).strip())
            if m1 and not _CAP2.search(text):
                page_geo = "Total country"
            elif geo is not None:
                page_geo = geo
            else:
                continue
            lines = _lines(page)
            if not any(all(_YEAR.match(w) for _, _, w in ws) for _, ws in lines):
                # Mangochi's last page (p.174, by position 2042-2043) is
                # printed WITHOUT its year headers: not filed under a guessed
                # year. Pages with no table rows (Neno's blank caption page,
                # back matter) fall through here too.
                continue
            heads = []                          # (y, side, year)
            for y, words in lines:
                if all(_YEAR.match(w) for _, _, w in words) and words:
                    for x0, _, w in words:
                        heads.append((y, x0 >= _MID, w))
                    continue
                sides = ([w for w in words if w[0] < _MID],
                         [w for w in words if w[0] >= _MID])
                for right, ws in enumerate(sides):
                    if not ws:
                        continue
                    lab, vals = _half(ws)
                    if lab not in _ROWS:
                        continue
                    if vals is None or len(vals) != 3:
                        raise ValueError(f"NSO Malawi projection p{page.number+1}: "
                                         f"row {lab!r} figures {vals}")
                    above = [h for h in heads if h[1] == bool(right) and h[0] < y]
                    if not above:
                        # a single-table page (2050) prints its year left
                        above = [h for h in heads if h[0] < y]
                    if not above:
                        raise ValueError(f"NSO Malawi projection p{page.number+1}: "
                                         f"row {lab!r} has no year above it")
                    year = max(above)[2]
                    t = tables.setdefault((page_geo, year), {})
                    key = _ROWS[lab]
                    if key in t:
                        raise ValueError(f"NSO Malawi projection {page_geo} {year}: "
                                         f"row {key!r} read twice")
                    t[key] = vals
    out = []
    nat_years = sorted(y for g, y in tables if g == "Total country")
    if nat_years != [str(y) for y in range(2018, 2051)]:
        raise ValueError(f"NSO Malawi projection: national years {nat_years}")
    dist_tot: dict[str, float] = {}
    districts = sorted({g for g, _ in tables if g != "Total country"})
    if len(districts) != 32:
        raise ValueError(f"NSO Malawi projection: {len(districts)} districts")
    for (g, year), t in sorted(tables.items()):
        need = set(_BANDS) | {"Total"}
        if g == "Total country":
            need |= set(_SPECIAL.values())
        if set(t) != need:
            raise ValueError(f"NSO Malawi projection {g} {year}: rows "
                             f"{sorted(need ^ set(t))} differ")
        for k, sex in enumerate(("total", "male", "female")):
            s = sum(t[a][k] for a in _BANDS)
            if abs(s - t["Total"][k]) > 20:    # 20 rounded bands
                raise ValueError(f"NSO Malawi projection {g} {year} {sex}: "
                                 f"bands {s} != Total {t['Total'][k]}")
        for lab, (b, m, f) in t.items():
            if abs(m + f - b) > 3:
                raise ValueError(f"NSO Malawi projection {g} {year} {lab}: "
                                 f"{m} + {f} != {b}")
        if g != "Total country":
            dist_tot[year] = dist_tot.get(year, 0) + t["Total"][0]
        sc = _SC_NAT if g == "Total country" else _SC_DIST
        for lab, vals in t.items():
            for sex, v in zip(("total", "male", "female"), vals):
                out.append(_row(sex, lab, g, year, v, sc))
    full = {y for y in dist_tot
            if sum(1 for g, yy in tables if yy == y and g != "Total country") == 32}
    for year, s in dist_tot.items():
        if year not in full:
            continue
        nat = tables[("Total country", year)]["Total"][0]
        if abs(s - nat) > 40:
            raise ValueError(f"NSO Malawi projection {year}: districts {s} != "
                             f"national {nat}")
    return pd.DataFrame(out)
