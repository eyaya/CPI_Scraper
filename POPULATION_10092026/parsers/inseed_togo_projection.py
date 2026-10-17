"""INSEED Togo -- "Perspectives démographiques du Togo 2011-2031" (Edition
2015, RGPH-4 2010 based), MEDIUM scenario ("scénario moyen", the reference
hypothesis):

* Tableau 2.1   total population by sex, every year 2011-2031 (thousands);
* Annexes ii-xxii  population by 5-year age group (0-4 .. 80+) x sex, one
                page per year 2011-2031 (thousands).

Added 2026-10-13 as a SECOND Togo descriptor (togo_projections.yaml) beside
togo.yaml (RGPH-5 2022 census).

REFERENCE DATE: 1 JANUARY of each year -- the report says so (footnote to
Tableau 2.1: "Les effectifs ... se rapportent au 1er janvier de chaque
année"); series_code says so. Not converted to mid-year.

COLUMNS: Tableau 2.1 prints the scenarios Bas | Moyen | Haut, the annexes
Haut | Moyen | Bas -- the MEDIUM block is the middle three columns of both
(header order checked). Low / high scenarios are not read (no variant
column). Units: thousands (unit thousand_persons).

The annex Total rows repeat Tableau 2.1 (checked within 1 thousand) and are
not filed twice. NOT FROM INSEED'S OWN PROJECTIONS, NOT READ: the "1950 à
2100" files on the same INSEED page are UN World Population Prospects 2025
(file TGO_WPP2025_*) -- an aggregator's figures.

Checks: M + F = Ensemble (within 2 -- rounding to the thousand), bands sum
to Total (within 10), 21 years in both tables.
"""
from __future__ import annotations

import collections
import re

import fitz
import pandas as pd

_SC_T = "TG_INSEED_PERSP_2011_2031_MOYEN_T2.1_1JAN"
_SC_A = "TG_INSEED_PERSP_2011_2031_MOYEN_ANNEX_1JAN"
_BANDS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
          "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
          "75-79", "80+"]
_NUM = re.compile(r"\d{1,3}(?: \d{3})*(?:,\d+)?")


def _rows(page):
    rows = collections.defaultdict(list)
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                t = s["text"].strip()
                if t:
                    rows[round((s["bbox"][1] + s["bbox"][3]) / 2)].append((s["bbox"][0], t))
    out = []
    for y in sorted(rows):
        if out and y - out[-1][0] <= 2:
            out[-1][1].extend(rows[y])
        else:
            out.append([y, list(rows[y])])
    return [(y, sorted(ws)) for y, ws in out]


def _nums(ws, xmin):
    vals = []
    for x, t in ws:
        if x < xmin:
            continue
        # "Masculin Féminin" headers aside, a span may hold one or two figures
        for m in re.finditer(r"\d{1,3}(?: \d{3})?(?!\d)", t):
            vals.append(float(m.group(0).replace(" ", "")))
    return vals


def _band(label: str) -> str | None:
    s = label.replace(" ", "")
    m = re.match(r"(\d+)-(\d+)ans", s)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2))}"
    if s.startswith("80ans"):
        return "80+"
    return None


def parse(local_path: str) -> pd.DataFrame:
    t21: dict[str, list] = {}
    annex: dict[str, dict[str, list]] = {}
    with fitz.open(local_path) as doc:
        for page in doc:
            text = page.get_text()
            rows = _rows(page)
            if "Tableau 2.1 Effectif total de population" in text:
                head = next(ws for _, ws in rows if any(t == "Moyen" for _, t in ws))
                if [t for _, t in head if t in ("Haut", "Moyen", "Bas")] != ["Bas", "Moyen", "Haut"]:
                    raise ValueError(f"INSEED 2.1: scenario order {head}")
                year = None
                for _, ws in rows:
                    if re.fullmatch(r"20[1-3]\d", ws[0][1]) and ws[0][0] < 60:
                        year = ws[0][1]
                        vals = _nums(ws[1:], 70)
                    elif year and ws[0][0] > 70:
                        vals = _nums(ws, 70)
                    else:
                        continue
                    if len(vals) == 9:
                        t21[year] = vals[3:6]           # Moyen: M, F, Ensemble
                        year = None
                continue
            if "par groupe d" in text and "1" in text and "janvier de chaque" in text \
                    or ("Scénario" in text and "Groupe" in text and "Moyen" in text):
                head = next((ws for _, ws in rows if any(t == "Moyen" for _, t in ws)), None)
                if head is None:
                    continue
                if [t for _, t in head if t in ("Haut", "Moyen", "Bas")] != ["Haut", "Moyen", "Bas"]:
                    raise ValueError(f"INSEED annex p{page.number+1}: order {head}")
                year = None
                for _, ws in rows:
                    lab = ws[0][1]
                    if re.fullmatch(r"20[1-3]\d", lab) and len(ws) == 1:
                        year = lab
                        if year in annex:
                            raise ValueError(f"INSEED annex {year}: twice")
                        annex[year] = {}
                        continue
                    if year is None:
                        continue
                    b = "Total" if lab == "Total" else _band(lab)
                    if b is None:
                        continue
                    vals = _nums(ws[1:], 60)
                    if len(vals) != 9:
                        raise ValueError(f"INSEED annex {year} {b}: {vals}")
                    annex[year][b] = vals[3:6]
    years = [str(y) for y in range(2011, 2032)]
    if sorted(t21) != years:
        raise ValueError(f"INSEED 2.1: years {sorted(set(years) ^ set(t21))}")
    if sorted(annex) != years:
        raise ValueError(f"INSEED annex: years {sorted(set(years) ^ set(annex))}")
    out = []

    def emit(sex, age, yr, v, sc):
        out.append({"series_type": "projection", "sex": sex, "age_group": age,
                    "geography": "Total country", "period": yr,
                    "frequency": "annual", "measure": "count", "value": v,
                    "unit": "thousand_persons", "series_code": sc})

    for yr in years:
        m, f, t = t21[yr]
        if abs(m + f - t) > 2:
            raise ValueError(f"INSEED 2.1 {yr}: {m} + {f} != {t}")
        for sex, v in (("male", m), ("female", f), ("total", t)):
            emit(sex, "Total", yr, v, _SC_T)
        a = annex[yr]
        if set(a) != set(_BANDS) | {"Total"}:
            raise ValueError(f"INSEED annex {yr}: {sorted(set(a) ^ (set(_BANDS) | {'Total'}))}")
        for k in range(3):
            if abs(a["Total"][k] - t21[yr][k]) > 1:
                raise ValueError(f"INSEED {yr}: annex Total {a['Total']} vs 2.1 {t21[yr]}")
            s = sum(a[b][k] for b in _BANDS)
            if abs(s - a["Total"][k]) > 10:
                raise ValueError(f"INSEED annex {yr}: bands {s} != Total {a['Total'][k]}")
        for b in _BANDS:
            m, f, t = a[b]
            if abs(m + f - t) > 2:
                raise ValueError(f"INSEED annex {yr} {b}: {m} + {f} != {t}")
            for sex, v in (("male", m), ("female", f), ("total", t)):
                emit(sex, b, yr, v, _SC_A)
    return pd.DataFrame(out)
