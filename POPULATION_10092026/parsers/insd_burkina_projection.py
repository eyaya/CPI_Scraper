"""INSD Burkina Faso -- "Projections démographiques 2020-2035" (5e RGPH 2019,
Volume 4, édition 2, janvier 2023), MEDIUM scenario:

* Tableau A2.2 -- national population by single year of age (0 .. 79, 80+,
  Total) x sex, 2020-2035. Only the "Ensemble" (urban + rural) column group
  is emitted -- there is no residence column; Urbain/Rural are read and must
  add up to it.
* Chapitre 2 / 3 -- the 13 regions and 45 provinces by INSD's own age groups
  ("0 an", "1 - 4 ans", the school-age groups "3 - 5", "6 -11", "12 - 15",
  "16 - 18", the five-year bands "5 - 9" .. "75 - 79", "80 ans et +", Total)
  x sex, 2020-2035, three years per block. The sub-national projections are
  derived from the medium national one (Chapter 2, Step 1).

Added 2026-10-13 as a SECOND Burkina Faso descriptor
(burkina_faso_projections.yaml) beside the 2019 census report.

ONE SCENARIO: Tableaux A2.1 / A2.3 (low / high) are not read -- the merge key
has no scenario column; Medium is the central variant and the only one carried
to regions and provinces.

SPACE-THOUSAND SEPARATORS. "1 920 748" is three words. Digits within one figure
sit ~2.2pt apart, figures >= 7pt apart, so words are rejoined by x-gap
(threshold 4.5pt); every Homme + Femme = Ensemble triple then confirms the
split. Labels are normalised to the collection's notation ("1 - 4 ans" ->
"1-4", "0 an" -> "0", "80 ans et +" -> "80+"); the bands are INSD's.

Checks: Homme + Femme = Ensemble on every row (exact); Urbain + Rural =
Ensemble (national; fails on 2025 only, whose Rural columns repeat 2020's --
pinned); the exclusive bands (0, 1-4, 5-9 .. 75-79, 80+) sum to
Total; the 13 regions sum to the national Total each year.

Geography names are the page headers as printed: regions keep "Région de/du
..." (so "Région de la Boucle du Mouhoun" is never confused with the Mouhoun
province). Never sum regions with provinces or with "Total country".

series_type = projection.
"""
from __future__ import annotations

import re

import fitz
import pandas as pd

_SC_NAT = "INSD_PROJ_2020_2035_A2_2"
_SC_SUB = "INSD_PROJ_2020_2035_SUBNAT"
_GAP = 4.5
_YEAR = re.compile(r"^20[23]\d$")
_FIVE = ["5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44",
         "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79"]
_EXCL = ["0", "1-4"] + _FIVE + ["80+"]
_SUB_ROWS = set(_EXCL) | {"3-5", "6-11", "12-15", "16-18", "Total"}
# PUBLISHED DEFECT: Oudalan 2031 (p.466) prints, as its "Ensemble" column, the
# 2029 Homme column of the same block (3 189, 12 276, 9 025, ... -- Homme +
# Femme never equals it). Its both-sexes figures are therefore not emitted;
# Homme and Femme are, and still sum to the province's other years' pattern.
_BAD_ENSEMBLE = {("Oudalan", "2031")}


def _lines(page):
    ws = sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    out = []
    for x0, y0, x1, y1, w, *_ in ws:
        y = (y0 + y1) / 2
        if out and y - out[-1][0] <= 2.5:
            out[-1][1].append((x0, x1, w))
        else:
            out.append([y, [(x0, x1, w)]])
    return [(y, sorted(ws)) for y, ws in out]


def _age(label: str) -> str | None:
    lab = re.sub(r"\s+", " ", label).strip()
    if lab.lower() == "total":         # Oudalan prints "TOTAL"
        return "Total"
    if lab in ("80+", "80 ans et +"):
        return "80+"
    m = re.fullmatch(r"(\d+)\s*ans?", lab)
    if m:
        return m.group(1)
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)(\s*ans)?", lab)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    if re.fullmatch(r"\d+", lab):
        return lab
    return None


def _split_label(words):
    """Label words are those before the first figure. Age labels may start
    with digits ("1 - 4 ans", "6 -11 ans", national "37"), so the label ends
    at the first word after which only digit words follow AND the label
    parses as an age."""
    for k in range(1, len(words) + 1):
        lab = " ".join(w for _, _, w in words[:k])
        rest = words[k:]
        if _age(lab) and rest and all(w.isdigit() for _, _, w in rest) \
                and not (k < len(words) and words[k][2] in ("-",)) \
                and not (rest and rest[0][2].startswith("-")):
            # the label must not swallow a figure: next word is far right
            if rest[0][0] - words[k - 1][1] >= _GAP or _age(lab) == "Total":
                return _age(lab), rest
    return None, None


def _wrapped(lines, li, ly):
    """A Total row whose cells WRAP ("163" over "966" in one cell, Zondoma
    2032-2034): its figures sit on unlabelled digit-only lines just above and
    below the "Total" label. Returned ordered by cell (x) then line (y), with
    a wrapped tail tagged to join its head (same left edge)."""
    got = []
    for k in (li - 1, li + 1):
        if 0 <= k < len(lines) and abs(lines[k][0] - ly) < 12 and \
                all(w.isdigit() for _, _, w in lines[k][1]):
            got += [(x0, x1, w, lines[k][0]) for x0, x1, w in lines[k][1]]
    got.sort(key=lambda t: (round(t[0]), t[3]))
    out = []
    for x0, x1, w, _ in got:
        if out and abs(x0 - out[-1][0]) < 1 and len(w) == 3:
            # same left edge, next line: the wrapped tail of the figure
            out.append((out[-1][1] - 0.1, x1, w))
        else:
            out.append((x0, x1, w))
    return out


def _figures(rest):
    nums = []
    for x0, x1, w in rest:
        if nums and x0 - nums[-1][1] < _GAP and len(w) == 3:
            nums[-1] = [nums[-1][0], x1, nums[-1][2] + w]
        else:
            nums.append([x0, x1, w])
    return [float(n[2]) for n in nums]


def parse(local_path: str) -> pd.DataFrame:
    nat: dict[tuple[str, str], list] = {}            # (year, age) -> [H, F, E]
    sub: dict[tuple[str, str, str], list] = {}       # (geo, year, age)
    ur_breaks: list[tuple[str, str]] = []
    with fitz.open(local_path) as doc:
        section = None
        for page in doc:
            text = page.get_text("text")
            if re.search(r"Tableau A2\.\s*2\s*:", text) and "....." not in text:
                section = "nat"
            elif re.search(r"Tableau A2\.\s*3\s*:", text) and "....." not in text:
                section = None
            elif re.search(r"CHAPITRE 2", text):
                section = "sub"
            elif re.search(r"BIBLIOGRAPHIE", text):
                section = None
            if section is None:
                continue
            lines = _lines(page)
            if section == "sub":
                if not lines:
                    continue
                first = " ".join(w for _, _, w in lines[0][1])
                if first.startswith("_") or first.isupper() or len(lines) < 20:
                    continue
                geo = first.strip()
            years: list[str] = []
            for li, (ly, words) in enumerate(lines):
                toks = [w for _, _, w in words]
                ys = [w for w in toks if _YEAR.match(w)]
                if ys and all(_YEAR.match(w) or not w[0].isdigit() for w in toks):
                    years = ys
                    continue
                if not years:
                    continue
                if words[0][0] > 130:
                    continue        # no label in the label column (a wrapped tail)
                if [w.lower() for _, _, w in words] == ["total"]:
                    words = words + _wrapped(lines, li, ly)
                age, rest = _split_label(words)
                if age is None:
                    continue
                vals = _figures(rest)
                per = 9 if section == "nat" else 3
                if len(vals) != per * len(years):
                    raise ValueError(f"INSD projection p{page.number+1} {age}: "
                                     f"{len(vals)} figures for {years}")
                for j, y in enumerate(years):
                    v = vals[j * per:(j + 1) * per]
                    for g in range(0, per, 3):
                        if section == "sub" and (geo, y) in _BAD_ENSEMBLE:
                            # the Ensemble column repeats another block's
                            # Homme column: not emitted (see _BAD_ENSEMBLE)
                            if v[2] != vals[0]:      # = the block's first Homme
                                raise ValueError(f"INSD projection {geo} {y} {age}: "
                                                 f"pinned defect changed")
                            v = [v[0], v[1], None]
                            continue
                        if v[g] + v[g + 1] != v[g + 2]:
                            raise ValueError(f"INSD projection p{page.number+1} {y} "
                                             f"{age}: {v[g]} + {v[g+1]} != {v[g+2]}")
                    if section == "nat":
                        if v[0] + v[3] != v[6] or v[1] + v[4] != v[7]:
                            ur_breaks.append((y, age))
                        key, store = (y, age), nat
                        v = v[6:9]
                    else:
                        key, store = (geo, y, age), sub
                    if key in store:
                        raise ValueError(f"INSD projection {key}: read twice")
                    store[key] = v
    # PUBLISHED DEFECT: in Tableau A2.2 for 2025 the Rural columns repeat 2020's
    # (age 0: 315 123 / 302 982 / 618 105 both years), so Urbain + Rural !=
    # Ensemble on all 82 rows of 2025 only. Ensemble itself checks (Homme +
    # Femme, ages sum to Total, regions sum to it) and is what is emitted.
    if {y for y, _ in ur_breaks} - {"2025"}:
        raise ValueError(f"INSD projection: urban + rural != ensemble outside "
                         f"2025: {ur_breaks[:5]}")
    bad = [k for k in _BAD_ENSEMBLE if (k[0], k[1], "Total") not in sub]
    if bad:
        raise ValueError(f"INSD projection: pinned defect {bad} not found")
    years = [str(y) for y in range(2020, 2036)]
    out = []
    nat_ages = [str(a) for a in range(80)] + ["80+"]
    for y in years:
        missing = [a for a in nat_ages + ["Total"] if (y, a) not in nat]
        if missing:
            raise ValueError(f"INSD projection national {y}: missing {missing[:5]}")
        for k in range(3):
            s = sum(nat[(y, a)][k] for a in nat_ages)
            if s != nat[(y, "Total")][k]:
                raise ValueError(f"INSD projection national {y}: ages {s} != Total")
        for a in nat_ages + ["Total"]:
            for sex, v in zip(("male", "female", "total"), nat[(y, a)]):
                out.append(_r(sex, a, "Total country", y, v, _SC_NAT))
    geos = sorted({g for g, _, _ in sub})
    regions = [g for g in geos if g.startswith("Région")]
    if len(regions) != 13 or len(geos) != 58:
        raise ValueError(f"INSD projection: {len(regions)} regions, {len(geos)} geographies")
    for g in geos:
        for y in years:
            missing = [a for a in _SUB_ROWS if (g, y, a) not in sub]
            if missing:
                raise ValueError(f"INSD projection {g} {y}: missing {missing}")
            for k in range(3):
                if sub[(g, y, "Total")][k] is None:
                    continue
                s = sum(sub[(g, y, a)][k] for a in _EXCL)
                if abs(s - sub[(g, y, "Total")][k]) > 3:
                    raise ValueError(f"INSD projection {g} {y}: bands {s} != Total "
                                     f"{sub[(g, y, 'Total')][k]}")
            for a in _SUB_ROWS:
                for sex, v in zip(("male", "female", "total"), sub[(g, y, a)]):
                    if v is not None:
                        out.append(_r(sex, a, g, y, v, _SC_SUB))
    for y in years:
        s = sum(sub[(g, y, "Total")][2] for g in regions)
        if abs(s - nat[(y, "Total")][2]) > 20:
            raise ValueError(f"INSD projection {y}: regions {s} != national "
                             f"{nat[(y, 'Total')][2]}")
    return pd.DataFrame(out)


def _r(sex, age, geo, year, value, sc):
    return {"series_type": "projection", "sex": sex, "age_group": age,
            "geography": geo, "period": year, "frequency": "annual",
            "measure": "count", "value": float(value), "unit": "persons",
            "series_code": sc}
