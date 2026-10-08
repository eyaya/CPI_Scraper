"""INEGE Equatorial Guinea — Anuario Estadístico de Guinea Ecuatorial,
chapter 3.1 "Población": the four censuses (1983, 1994, 2001, 2015).

* Tabla 19  population by census year x región / provincia (counts)
* Tabla 20  2015 sex distribution (% hombres / % mujeres) by área
* Tabla 22  2015 population by DISTRITO (counts)
* Tabla 23  population density (hab./km2) by área, census years

Spanish numbers use a DOT as the thousands separator ("1.225.377") and a comma
for decimals, so -- unlike the francophone sources -- no row is ambiguous.

OVERLAPPING GEOGRAPHIES, kept as published and NOT to be summed together: the
two regions (Región Continental, Región Insular) contain the seven provinces,
and the districts (Tabla 22) partition the same territory again. Checked here:
provinces sum to their region and regions to the national total in every
census year; districts sum to the 2015 national total. Annobón is both a
province and a district with the same population (5 314) -- one key, one value.
Province names are kept as printed per table ("Kie Ntem" in Tabla 19,
"Kie-Ntem" in Tablas 20/23) -- they are written differently by INEGE, not
normalised here.

NOT READ: Tabla 20's nationality and urban/rural shares, and Tabla 21
(nationality x sex) -- no schema dimension holds nationality; Gráfico 3's
"2025 Estim" population (1 727 151), which appears only as a chart label;
household tables 24-25.

DENSITY AS PUBLISHED: Centro Sur prints 30 hab./km2 in 2001 and 14 in 2015
while its population rose (125 856 -> 141 986); kept as printed, not
"corrected" (2015's 14 is consistent with the province's area).

CROSS-CHECK: 2015 total 1 225 377; Litoral 2015 367 348; 1983 total 300 000;
Bata 309 345; national 2015 hombres 52,4%.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_SERIES = "GQ_CGPV"
_NUM = re.compile(r"^\d{1,3}(?:\.\d{3})*$")
_DEC = re.compile(r"^\d{1,3},\d$")
_NATIONAL = "Guinea Ecuatorial"


def _int(t: str) -> int:
    return int(t.replace(".", ""))


def _row(sex, geo, period, measure, value, unit, age="Total"):
    return {"series_type": "census", "sex": sex, "age_group": age,
            "geography": "Total country" if geo == _NATIONAL else geo,
            "period": period, "frequency": "annual", "measure": measure,
            "value": float(value), "unit": unit, "series_code": _SERIES}


def _lines(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        out = []
        for p in pdf.pages[90:115]:
            out += [ln.strip() for ln in (p.extract_text() or "").splitlines()
                    if ln.strip()]
    return out


def _block(lines, caption):
    i = next((i for i, ln in enumerate(lines) if re.search(caption, ln)), None)
    if i is None:
        raise ValueError(f"INEGE: {caption!r} not found")
    out = []
    for ln in lines[i + 1:]:
        if ln.startswith("Fuente"):
            break
        out.append(ln)
    return out


def _split(ln):
    toks = ln.split()
    lab = []
    while toks and not (_NUM.match(toks[0]) or _DEC.match(toks[0]) or toks[0] == "-"):
        lab.append(toks.pop(0))
    return " ".join(lab), toks


def _t19(lines, out):
    blk = _block(lines, r"Tabla 19: Distribuci.n de la poblaci.n de G\.E\. por a.o censal")
    years = re.findall(r"\b(19\d\d|20\d\d)\b", blk[0])
    if len(years) != 4:
        raise ValueError(f"INEGE T19: header years {years}")
    rows, pending = {}, ""
    for ln in blk[1:]:
        lab, toks = _split(ln)
        if toks and all(_NUM.match(t) for t in toks) and len(toks) == 4:
            name = (pending + " " + lab).strip() if lab else pending
            rows[name] = [_int(t) for t in toks]
            pending = ""
        elif lab and not toks:
            # "Región" / numbers / "Continental": a label wrapped around its
            # figures; the tail completes the row read just before it
            if pending == "" and rows and list(rows)[-1] in ("Región", ""):
                last = list(rows)[-1]
                rows[f"{last} {lab}".strip()] = rows.pop(last)
            else:
                pending = lab
    if "Región" in rows:
        raise ValueError("INEGE T19: wrapped region label not rejoined")
    regions = {"Región Continental": ["Centro Sur", "Kie Ntem", "Litoral", "Wele Nzas"],
               "Región Insular": ["Annobón", "Bioko Norte", "Bioko Sur"]}
    for reg, provs in regions.items():
        for k in range(4):
            if sum(rows[p][k] for p in provs) != rows[reg][k]:
                raise ValueError(f"INEGE T19: {reg} {years[k]} provinces do not sum")
    for k in range(4):
        if sum(rows[r][k] for r in regions) != rows[_NATIONAL][k]:
            raise ValueError(f"INEGE T19: regions do not sum in {years[k]}")
    for name, vals in rows.items():
        for y, v in zip(years, vals):
            out.append(_row("total", name, y, "count", v, "persons"))


def _t20(lines, out):
    blk = _block(lines, r"Tabla 20: Distribuci.n de la poblaci.n de G\.E\. por sexo")
    n = 0
    for ln in blk:
        lab, toks = _split(ln)
        if not lab or len(toks) != 6 or not all(_DEC.match(t) or t == "-" for t in toks):
            continue
        h, m = float(toks[0].replace(",", ".")), float(toks[1].replace(",", "."))
        if abs(h + m - 100) > 0.15:
            raise ValueError(f"INEGE T20: {lab} sexes sum {h + m}")
        out.append(_row("male", lab, "2015", "share", h, "percent"))
        out.append(_row("female", lab, "2015", "share", m, "percent"))
        n += 1
    if n != 10:
        raise ValueError(f"INEGE T20: {n} areas read")


def _t22(lines, out):
    blk = _block(lines, r"Tabla 22: Distribuci.n de la poblaci.n total por nacionalidad y zona")
    rows = {}
    for ln in blk:
        lab, toks = _split(ln)
        if lab and toks and _NUM.match(toks[0]) and "." in toks[0] or (
                lab and toks and _NUM.match(toks[0]) and len(toks) >= 4):
            rows[lab] = _int(toks[0])
    nat = rows.pop(_NATIONAL, None)
    if nat is None or sum(rows.values()) != nat or len(rows) != 18:
        raise ValueError(f"INEGE T22: {len(rows)} districts sum "
                         f"{sum(rows.values())} vs {nat}")
    for name, v in rows.items():
        out.append(_row("total", name, "2015", "count", v, "persons"))


def _t23(lines, out):
    blk = _block(lines, r"Tabla 23: Densidad de poblaci.n por .rea geogr.fica")
    years = re.findall(r"\b(19\d\d|20\d\d)\b", blk[0])
    n = 0
    for ln in blk[1:]:
        lab, toks = _split(ln)
        if lab and len(toks) == 4 and all(t.isdigit() for t in toks):
            for y, t in zip(years, toks):
                out.append(_row("total", lab, y, "density", int(t), "per_km2"))
            n += 1
    if n != 10:
        raise ValueError(f"INEGE T23: {n} areas read")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    lines = _lines(path)
    out: list[dict] = []
    _t19(lines, out)
    _t20(lines, out)
    _t22(lines, out)
    _t23(lines, out)
    df = pd.DataFrame(out)
    key = ["series_type", "sex", "age_group", "geography", "period", "measure"]
    dup = df[df.duplicated(key, keep=False)]
    if len(dup) and (dup.groupby(key)["value"].nunique() > 1).any():
        bad = dup.groupby(key)["value"].nunique()
        raise ValueError(f"INEGE: conflicting values for {list(bad[bad > 1].index)[:3]}")
    return df.drop_duplicates(key).reset_index(drop=True)
