"""INSTAD Djibouti -- Annuaire Statistique, Edition 2023, section 2.1: the
INSTAD-FNUAP population PROJECTIONS, 2010-2022.

Added 2026-10-13 as a SECOND Djibouti descriptor (djibouti_annuaire.yaml)
beside djibouti.yaml (the 2024 census, Etat et structure de la population).

* Tableau 2.1.2  "Répartition de la population totale résidente par sexe et par
                 année", 2012-2022: male, female, total (persons) and the
                 annual growth rate (percent). Source line: INSTAD-FNUAP,
                 Projections démographiques 2019.
* Tableau 2.1.3  "... par sexe et par âge", 2010-2022 over four pages: 5-year
                 age group (0-4 .. 80+, Total) x Ensemble/Masculin/Féminin.
                 Source line: Projections démographiques, INSTAD & FNUAP 2018.

The 2023 edition is the LAST to print these tables: the 2024 and 2025
editions print the 2024 census by region instead.

TWO PRINTINGS OF THE SAME TOTALS. 2.1.2 and 2.1.3's Total row both give the
2012-2022 totals by sex and differ by a few persons (2012 male 464 937 vs
464 936). One merge key holds one figure, so the sex-by-year table (2.1.2) is
the one filed for 2012-2022; 2.1.3's Total row is filed only for 2010-2011,
which 2.1.2 does not cover. Differences beyond 5 persons raise.

AGE LABELS. The tables were set in a spreadsheet that turned two bands into
dates: "05-sept" (2019-2022 page) and "oct-14" are 5-9 and 10-14 (the other
pages print "05-09" and "10-14"). They are filed as "5-9" and "10-14", the
spelling of djibouti.yaml's census output. Every other label as printed.

Checks: bands sum to the Total row (within 10 persons), M + F = Ensemble
(within 3), the two printings agree within 5, 13 years present; the two
Total rows where M + F misses Ensemble by 4 (2011, 2014) are pinned.
"""
from __future__ import annotations

import collections
import re

import fitz
import pandas as pd

_SC_SEX = "DJ_INSTAD_FNUAP_PROJ2019_T2.1.2"
_SC_AGE = "DJ_INSTAD_FNUAP_PROJ2018_T2.1.3"
# "98 632", or unspaced "112563" (the 2014 column prints without separators)
_NUM = re.compile(r"(?<!\d)(?:\d{1,3}(?: \d{3})+|\d+)(?!\d)")
_AGE_FIX = {"05-09": "5-9", "05-sept": "5-9", "oct-14": "10-14"}
_BANDS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
          "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
          "75-79", "80+"]
# Published, pinned (filed as printed): (year, check, row, computed, printed)
_KNOWN_ISSUES: set = {
    ("2011", "2.1.3 M+F", "Total", 852581.0, 852585.0),
    ("2014", "2.1.3 M+F", "Total", 902347.0, 902343.0),   # 2014 Total not filed
}
_SUB = {"Ensemble": "total", "Masculin": "male", "Féminin": "female"}


def _rows(page):
    rows = collections.defaultdict(list)
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            if tuple(round(v) for v in ln["dir"]) != (1, 0):
                continue
            for s in ln["spans"]:
                t = s["text"].strip()
                if t:
                    y = round((s["bbox"][1] + s["bbox"][3]) / 2)
                    rows[y].append((s["bbox"][0], s["bbox"][2], t))
    out = []
    for y in sorted(rows):
        if out and y - out[-1][0] <= 2:
            out[-1][1].extend(rows[y])
        else:
            out.append([y, list(rows[y])])
    return [(y, sorted(ws)) for y, ws in out]


def _num(t: str) -> float:
    return float(t.replace(" ", ""))


def _table_212(page) -> dict[str, dict[str, float]]:
    """{year: {male, female, total, growth}}. A row's figures sit on the year's
    line or one line above/below it (the cells are vertically offset)."""
    rows = _rows(page)
    head = next((ws for _, ws in rows if any(t == "Masculin" for _, _, t in ws)), None)
    if head is None:
        raise ValueError("INSTAD 2.1.2: no header")
    cols = {"male": next(x for x, _, t in head if t == "Masculin"),
            "female": next(x for x, _, t in head if t == "Féminin"),
            "total": next(x for x, _, t in head if t == "Total")}
    yrows = [(y, t) for y, ws in rows for x, _, t in ws
             if x < cols["male"] - 10 and re.fullmatch(r"20[12]\d", t)]
    out = {}
    for y, yr in yrows:
        cells = [(x, t) for yy, ws in rows if abs(yy - y) <= 3
                 for x, _, t in ws if x >= cols["male"] - 10]
        rec = {}
        for x, t in cells:
            if t.endswith("%"):
                rec["growth"] = float(t.rstrip("%").replace(",", "."))
                continue
            if not _NUM.fullmatch(t):
                continue
            k = min(cols, key=lambda c: abs(cols[c] - x))
            if k in rec:
                raise ValueError(f"INSTAD 2.1.2 {yr}: two {k}")
            rec[k] = _num(t)
        out[yr] = rec
    return out


def _table_213(page) -> dict[str, dict[str, dict[str, float]]]:
    """{year: {band: {total, male, female}}} for one page of 2.1.3."""
    rows = _rows(page)
    yline = max((ws for _, ws in rows),
                key=lambda ws: sum(bool(re.fullmatch(r"20[12]\d", t)) for _, _, t in ws))
    years = sorted((x, t) for x, _, t in yline if re.fullmatch(r"20[12]\d", t))
    sub = next(ws for _, ws in rows if sum(t in _SUB for _, _, t in ws) >= 6)
    subcols = sorted((x0, x1, t) for x0, x1, t in sub if t in _SUB)
    if len(subcols) != 3 * len(years):
        raise ValueError(f"INSTAD 2.1.3: {len(subcols)} columns for {len(years)} years")
    # column k -> (year, sex): columns in x order, three per year in x order
    colmap = [((x0 + x1) / 2, years[k // 3][1], _SUB[t])
              for k, (x0, x1, t) in enumerate(subcols)]
    out: dict = {}
    for _, ws in rows:
        lab = ws[0][2]
        if ws[0][0] > subcols[0][0] - 5:
            continue
        band = _AGE_FIX.get(lab, lab)
        if band not in _BANDS and band != "Total":
            continue
        vals = []
        for x0, x1, t in ws[1:]:
            ms = list(_NUM.finditer(t))
            step = (x1 - x0) / max(len(ms), 1)
            vals += [(x0 + step * (k + 0.5), m.group(0)) for k, m in enumerate(ms)]
        if len(vals) != len(colmap):
            raise ValueError(f"INSTAD 2.1.3 {band}: {len(vals)} values for {len(colmap)} columns")
        for (xc, v), (cx, yr, sex) in zip(sorted(vals), colmap):
            if abs(xc - cx) > 25:
                raise ValueError(f"INSTAD 2.1.3 {yr} {band} {sex}: value at {xc} vs column {cx}")
            cell = out.setdefault(yr, {}).setdefault(band, {})
            if sex in cell:
                raise ValueError(f"INSTAD 2.1.3 {yr} {band}: {sex} read twice")
            cell[sex] = _num(v)
    return out


def parse(local_path: str) -> pd.DataFrame:
    t212, t213 = None, {}
    with fitz.open(local_path) as doc:
        for page in doc:
            text = page.get_text()
            if "Tableau 2.1.2" in text and "par sexe et par ann" in text and "...." not in text:
                t212 = _table_212(page)
            elif "Tableau 2.1.3" in text and "Ensemble" in text and "...." not in text:
                for yr, d in _table_213(page).items():
                    if yr in t213:
                        raise ValueError(f"INSTAD 2.1.3 {yr}: on two pages")
                    t213[yr] = d
    years = [str(y) for y in range(2010, 2023)]
    if t212 is None or sorted(t212) != years[2:]:
        raise ValueError(f"INSTAD 2.1.2: years {sorted(t212 or {})}")
    if sorted(t213) != years:
        raise ValueError(f"INSTAD 2.1.3: years {sorted(t213)}")

    out = []
    issues: set = set()

    def emit(sex, age, yr, measure, v, unit, sc):
        out.append({"series_type": "projection", "sex": sex, "age_group": age,
                    "geography": "Total country", "period": yr,
                    "frequency": "annual", "measure": measure, "value": v,
                    "unit": unit, "series_code": sc})

    for yr in years:
        d = t213[yr]
        if set(d) != set(_BANDS) | {"Total"}:
            raise ValueError(f"INSTAD 2.1.3 {yr}: bands {sorted(set(d) ^ (set(_BANDS) | {'Total'}))}")
        for sex in ("total", "male", "female"):
            s = sum(d[b][sex] for b in _BANDS)
            if abs(s - d["Total"][sex]) > 10:
                issues.add((yr, "2.1.3 bands", sex, s, d["Total"][sex]))
        for b, c in d.items():
            if abs(c["male"] + c["female"] - c["total"]) > 3:
                issues.add((yr, "2.1.3 M+F", b, c["male"] + c["female"], c["total"]))
            if b == "Total" and yr in t212:
                for sex in ("total", "male", "female"):
                    if abs(c[sex] - t212[yr][sex]) > 5:
                        issues.add((yr, "2.1.3 vs 2.1.2", sex, c[sex], t212[yr][sex]))
                continue                      # 2.1.2's printing is filed
            for sex, v in c.items():
                emit(sex, b, yr, "count", v, "persons", _SC_AGE)
    for yr, rec in t212.items():
        if set(rec) != {"male", "female", "total", "growth"}:
            raise ValueError(f"INSTAD 2.1.2 {yr}: {rec}")
        if abs(rec["male"] + rec["female"] - rec["total"]) > 3:
            issues.add((yr, "2.1.2 M+F", "Total", rec["male"] + rec["female"], rec["total"]))
        for sex in ("total", "male", "female"):
            emit(sex, "Total", yr, "count", rec[sex], "persons", _SC_SEX)
        emit("total", "Total", yr, "growth_rate", rec["growth"], "percent", _SC_SEX)
    if issues != _KNOWN_ISSUES:
        raise ValueError(f"INSTAD: inconsistencies changed: new "
                         f"{sorted(issues - _KNOWN_ISSUES)}, gone "
                         f"{sorted(_KNOWN_ISSUES - issues)}")
    return pd.DataFrame(out)
