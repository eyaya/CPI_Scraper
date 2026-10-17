"""GBoS -- The 2016 Gambia Statistical Abstract, Chapter 1 (Population), which
reprints the census back-series:

* Table 1.1 -- population by Local Government Area, censuses 1973, 1983,
  1993, 2003, 2013 (both sexes);
* Table 1.2 -- population by five-year age group and sex, 2013 census;
* Table 1.3 -- population by LGA and sex, 2013 census;
* Table 1.5 -- population density (per sq km) by LGA, 1973-2013.

Added 2026-10-13 as a SECOND Gambia descriptor (gambia_abstract.yaml) beside
the 2024 census preliminary report. Later abstracts (2017-2023) carry no census
back-series (2020/2023 print Labour Force Survey weights; 2024 the 2024
census), so this edition is the one read.

Not read: the percent-share columns; Table 1.4 (growth over inter-censal
ranges, not years); the urban/rural rows of Table 1.3; TFR/ASFR (1.6-1.7).

Checks: the LGAs sum to the Total in every census year; Male + Female = Total
for every 2013 row; the age bands (with "Not stated") sum to the Total; the
2013 LGA totals in Table 1.1 equal those of Table 1.3. Table 1.4/1.5 spell
"Janjangbureh" for Table 1.1's "Janjanbureh"; filed under the latter.

series_type = census.
"""
from __future__ import annotations

import re

import fitz
import pandas as pd

_SC = "GBOS_ABSTRACT_2016_CH1"
_LGAS = ["Banjul", "Kanifing", "Brikama", "Mansakonko", "Kerewan", "Kuntaur",
         "Janjanbureh", "Basse"]
_YEARS = ["1973", "1983", "1993", "2003", "2013"]
_AGES = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
         "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
         "75-79", "80-84", "85+", "Not stated"]
_NUM = re.compile(r"^\d{1,3}(,\d{3})*(\.\d+)?$")


def _lines(page):
    ws = sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    out = []
    for x0, y0, x1, y1, w, *_ in ws:
        y = (y0 + y1) / 2
        if out and y - out[-1][0] <= 2.5:
            out[-1][1].append((x0, w))
        else:
            out.append([y, [(x0, w)]])
    return [[w for _, w in sorted(ws)] for _, ws in out]


def _split(words):
    label = []
    for w in words:
        if _NUM.match(w):
            break
        label.append(w)
    lab = " ".join(label)
    if lab == "Janjangbureh":
        lab = "Janjanbureh"
    return lab, [float(w.replace(",", "")) for w in words[len(label):] if _NUM.match(w)]


def _section(lines, start, stop):
    """Rows between the caption matching `start` and the next `stop` line."""
    on, rows = False, {}
    for words in lines:
        text = " ".join(words)
        if re.match(start, text):
            on = True
            continue
        if on and re.match(stop, text):
            break
        if on:
            lab, vals = _split(words)
            if lab and vals:
                rows[lab] = vals
    return rows


def _row(sex, age, geo, year, measure, value, unit):
    return {"series_type": "census", "sex": sex, "age_group": age,
            "geography": "Total country" if geo == "Total" else geo,
            "period": year, "frequency": "annual", "measure": measure,
            "value": float(value), "unit": unit, "series_code": _SC}


def parse(local_path: str) -> pd.DataFrame:
    with fitz.open(local_path) as doc:
        lines = []
        for page in doc:
            txt = page.get_text("text")
            if "List of Tables" in txt or ". . ." in txt or "....." in txt:
                continue
            if not lines and not re.search(r"Chapter 1\s*:?\s*Population", txt):
                continue
            lines += _lines(page)
            if "Table 1.6" in txt:
                break
    t11 = _section(lines, r"Table 1\.1:", r"Source")
    t12 = _section(lines, r"Table 1\.2:", r"Source")
    t13 = _section(lines, r"Table 1\.3:", r"Residence")
    t15 = _section(lines, r"Table 1\.5:", r"Source")
    out = []
    # Table 1.1: five census counts, then five percent shares
    need = _LGAS + ["Total"]
    for name, t in (("1.1", t11), ("1.3", t13), ("1.5", t15)):
        if not set(need) <= set(t):
            raise ValueError(f"GBoS abstract Table {name}: rows {sorted(set(need) - set(t))} missing")
    for i, y in enumerate(_YEARS):
        s = sum(t11[g][i] for g in _LGAS)
        if s != t11["Total"][i]:
            raise ValueError(f"GBoS abstract Table 1.1 {y}: LGAs {s} != Total {t11['Total'][i]}")
        for g in need:
            if y != "2013":
                out.append(_row("total", "Total", g, y, "count", t11[g][i], "persons"))
            # Table 1.5: area, then density per census year
            out.append(_row("total", "Total", g, y, "density", t15[g][1 + i], "per_km2"))
    for g in need:
        m, f, tot = t13[g][:3]
        if m + f != tot or tot != t11[g][4]:
            raise ValueError(f"GBoS abstract Table 1.3 {g}: {m}+{f} vs {tot} vs 1.1 {t11[g][4]}")
        for sex, v in zip(("male", "female", "total"), (m, f, tot)):
            out.append(_row(sex, "Total", g, "2013", "count", v, "persons"))
    missing = (set(_AGES) | {"Total"}) - set(t12)
    if missing:
        raise ValueError(f"GBoS abstract Table 1.2: rows {sorted(missing)} missing")
    for k, sex in enumerate(("male", "female", "total")):
        s = sum(t12[a][k] for a in _AGES)
        if s != t12["Total"][k]:
            raise ValueError(f"GBoS abstract Table 1.2 {sex}: bands {s} != {t12['Total'][k]}")
    for a in _AGES:
        m, f, tot = t12[a][:3]
        if m + f != tot:
            raise ValueError(f"GBoS abstract Table 1.2 {a}: {m}+{f} != {tot}")
        for sex, v in zip(("male", "female", "total"), (m, f, tot)):
            out.append(_row(sex, a, "Total", "2013", "count", v, "persons"))
    return pd.DataFrame(out)
