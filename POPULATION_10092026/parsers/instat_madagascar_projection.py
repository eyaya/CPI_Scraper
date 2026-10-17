"""INSTAT Madagascar -- "RGPH-3 2018 : Projections démographiques" (Rapport
thématique, juillet 2023), chapter 3, MEDIUM variant (VM, "variante moyenne
ou tendancielle"):

* Tableau 3.1    population at mid-year by sex, every year 2018-2050;
* Tableaux 3.2, 3.4, ..., 3.26  national population by 5-year age group
                 (0-4 .. 80+) x sex at mid-year for 2018-2025, 2030, 2035,
                 2040, 2045, 2050.

Added 2026-10-13 as a SECOND Madagascar descriptor
(madagascar_projections.yaml) beside madagascar.yaml (the RGPH-3 census
count, series census).

ONE VARIANT: the low (VB) and high (VH) variants' tables (3.54 onwards) are
not read -- the merge key has no variant column. 2018 is the projection's
mid-year base (25 729 337), filed as projection beside the census count
(25 674 196).

The age tables' TOTAL rows repeat Table 3.1 (checked equal) and are not filed
twice. The RM (sex ratio) column is not collected.
NOT READ: regional tables (3.3, 3.5, ...: 22 regions x age x sex) and the
components tables -- deferred.

Checks: M + F = Ensemble (within 2), bands sum to TOTAL (within 5), 33 years
in 3.1, 15 national age tables, each TOTAL equal to 3.1.
"""
from __future__ import annotations

import collections
import re

import fitz
import pandas as pd

_SC_T = "MG_INSTAT_RGPH3_PROJ_VM_T3.1"
_SC_A = "MG_INSTAT_RGPH3_PROJ_VM_NATIONAL_AGE"
_NUM = re.compile(r"\d{1,3}(?: \d{3})*")
_BANDS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
          "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
          "75-79", "80+"]
_AGE_YEARS = [str(y) for y in list(range(2018, 2026)) + [2030, 2035, 2040, 2045, 2050]]


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


def _three(ws, xmin):
    vals = [float(t.replace(" ", "")) for x, t in ws
            if x >= xmin and _NUM.fullmatch(t)]
    return vals[:3] if len(vals) >= 3 else None


def parse(local_path: str) -> pd.DataFrame:
    t31: dict[str, list] = {}
    ages: dict[str, dict[str, list]] = {}
    with fitz.open(local_path) as doc:
        for page in doc:
            text = page.get_text()
            if "(VB)" in text or "(VH)" in text:
                continue
            rows = _rows(page)
            if "POPULATION TOTALE PAR ANNÉE SELON LE SEXE (VM)" in text and "...." not in text:
                for _, ws in rows:
                    if re.fullmatch(r"20[1-5]\d", ws[0][1]):
                        v = _three(ws, ws[0][0] + 20)
                        if v is None:
                            raise ValueError(f"INSTAT MG 3.1 {ws[0][1]}: {ws}")
                        t31[ws[0][1]] = v
                continue
            year = None
            for _, ws in rows:
                line = " ".join(t for _, t in ws)
                m = re.search(r"POPULATION NATIONALE EN (20[1-5]\d) \(VM\)", line)
                if m:
                    year = m.group(1)
                    if year in ages:
                        raise ValueError(f"INSTAT MG national {year}: twice")
                    ages[year] = {}
                    continue
                if year is None:
                    continue
                if line.startswith("REGION") or "Tableau" in line:
                    year = None
                    continue
                lab = ws[0][1]
                if lab in _BANDS or lab == "TOTAL":
                    v = _three(ws, ws[0][0] + 30)
                    if v is None:
                        raise ValueError(f"INSTAT MG {year} {lab}: {ws}")
                    ages[year][lab] = v
                    if lab == "TOTAL":
                        year = None
    years = [str(y) for y in range(2018, 2051)]
    if sorted(t31) != years:
        raise ValueError(f"INSTAT MG 3.1: years {sorted(set(years) ^ set(t31))}")
    if sorted(ages) != sorted(_AGE_YEARS):
        raise ValueError(f"INSTAT MG national tables: {sorted(ages)}")

    out = []

    def emit(sex, age, yr, v, sc):
        out.append({"series_type": "projection", "sex": sex, "age_group": age,
                    "geography": "Total country", "period": yr,
                    "frequency": "annual", "measure": "count", "value": v,
                    "unit": "persons", "series_code": sc})

    for yr, (t, m, f) in t31.items():
        if abs(m + f - t) > 2:
            raise ValueError(f"INSTAT MG 3.1 {yr}: {m} + {f} != {t}")
        for sex, v in (("total", t), ("male", m), ("female", f)):
            emit(sex, "Total", yr, v, _SC_T)
    for yr, tab in ages.items():
        if set(tab) != set(_BANDS) | {"TOTAL"}:
            raise ValueError(f"INSTAT MG {yr}: rows {sorted(set(tab) ^ (set(_BANDS) | {'TOTAL'}))}")
        if tab["TOTAL"] != t31[yr]:
            raise ValueError(f"INSTAT MG {yr}: TOTAL {tab['TOTAL']} != 3.1 {t31[yr]}")
        for k in range(3):
            s = sum(tab[b][k] for b in _BANDS)
            if abs(s - tab["TOTAL"][k]) > 5:
                raise ValueError(f"INSTAT MG {yr}: bands {s} != TOTAL {tab['TOTAL'][k]}")
        for b in _BANDS:
            t, m, f = tab[b]
            if abs(m + f - t) > 2:
                raise ValueError(f"INSTAT MG {yr} {b}: {m} + {f} != {t}")
            for sex, v in (("total", t), ("male", m), ("female", f)):
                emit(sex, b, yr, v, _SC_A)
    return pd.DataFrame(out)
