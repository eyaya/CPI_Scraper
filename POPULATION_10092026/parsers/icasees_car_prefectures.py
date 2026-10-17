"""ICASEES Central African Republic -- population projections for 2021 and
2024 by region and prefecture, a SECOND CAR descriptor
(central_african_republic_prefectures.yaml) beside central_african_republic.yaml
(national age x sex, 2022-2023).

Two ICASEES HTML pages (droptables), RGPH-4 section of icasees.org:
* 190 "Population RCA par Préfecture en 2021 et 2024" -- regions and
  prefectures, both sexes, 2021 and 2024 (source "ICASEES/DSDSGE");
* 199 "Population de la RCA par sexe selon la subdivision administrative en
  2024" -- regions and prefectures by sex, plus area and density (source
  "ICASEES, projections démographiques 2024").

series_type projection (page 199's source line; the 2021-2024 figures run on
from the 2022-2023 projections already collected: 6 091 097, 6 214 316,
6 340 948, 6 470 307). The RGPH-4 census results are not yet published.

LABELS. The two pages spell prefectures differently (Ombella-M'Poko /
Ombella-Mpoko, Sangha-Mbaéré / Sangha-Mbaere, Haut-Mbomou / Haute-Mbomou,
"Yade" / "Yadé", "kaga" / "Kagas"); each is mapped to one label (_CANON).
Page 190 files Bangui under PREFECTURE "Bas-Oubangui"; page 199 names it
Bangui -- filed as the prefecture "Bangui" and the region "Bas-Oubangui"
(the region is Bangui alone, so the two rows are equal).

2024 both sexes is printed on both pages: page 199 (with its sexes) is filed,
page 190's 2024 column is only checked against it (within 1 person).

PUBLISHED INCONSISTENCIES, kept and pinned:
* page 190, Yadé region 2021: printed 910 945; its four prefectures sum to
  1 208 849, and with that figure the regions add up to the RCA total
  6 091 097 exactly. Filed as printed (_PINNED).
* page 190 vs 199, 2024: Plateaux 653 908 / 653 907, Kagas 889 155 / 889 154.
* page 199: M + F misses Total by 1 for some prefectures (rounding).

NOT READ: area (no schema measure); page 207 (communes, 2021/2024) and 211
(communes by sex, 2021) -- communes only, the schema has no level column.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

_REGIONS = {"plateaux": "Plateaux", "equateur": "Equateur", "yade": "Yadé",
            "kaga": "Kagas", "kagas": "Kagas", "fertit": "Fertit",
            "haut-oubangui": "Haut-Oubangui", "bas-oubangui": "Bas-Oubangui"}
_PREFS = {"ombella-m'poko": "Ombella-M'Poko", "ombella-mpoko": "Ombella-M'Poko",
          "lobaye": "Lobaye", "mambere-kadei": "Mambéré-Kadéï",
          "mambere": "Mambéré", "nana-mambere": "Nana-Mambéré",
          "sangha-mbaere": "Sangha-Mbaéré", "ouham-pende": "Ouham-Pendé",
          "lim-pende": "Lim-Pendé", "ouham": "Ouham", "ouham-fafa": "Ouham-Fafa",
          "kemo": "Kémo", "nana-gribizi": "Nana-Gribizi", "ouaka": "Ouaka",
          "bamingui-bangoran": "Bamingui-Bangoran", "haute-kotto": "Haute-Kotto",
          "vakaga": "Vakaga", "basse-kotto": "Basse-Kotto", "mbomou": "Mbomou",
          "haut-mbomou": "Haut-Mbomou", "haute-mbomou": "Haut-Mbomou",
          "bangui": "Bangui"}
_REGION_OF = {"Ombella-M'Poko": "Plateaux", "Lobaye": "Plateaux",
              "Mambéré-Kadéï": "Equateur", "Mambéré": "Equateur",
              "Nana-Mambéré": "Equateur", "Sangha-Mbaéré": "Equateur",
              "Ouham-Pendé": "Yadé", "Lim-Pendé": "Yadé", "Ouham": "Yadé",
              "Ouham-Fafa": "Yadé", "Kémo": "Kagas", "Nana-Gribizi": "Kagas",
              "Ouaka": "Kagas", "Bamingui-Bangoran": "Fertit",
              "Haute-Kotto": "Fertit", "Vakaga": "Fertit",
              "Basse-Kotto": "Haut-Oubangui", "Mbomou": "Haut-Oubangui",
              "Haut-Mbomou": "Haut-Oubangui", "Bangui": "Bas-Oubangui"}
# (year, region): printed region total that its prefectures do not sum to
_PINNED = {("2021", "Yadé"): 910945.0}
_PAGE_DIFF_2024 = {"Plateaux": (653908.0, 653907.0), "Kagas": (889155.0, 889154.0)}


def _key(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "", s.strip().lower())


def _num(v) -> float:
    if isinstance(v, (int, float)) and not pd.isna(v):
        return float(v)
    return float(str(v).replace("\xa0", "").replace(" ", "").replace(",", "."))


def _which(path: str) -> str:
    t = pd.read_html(path)[0]
    cols = [_key(c) for c in t.columns]
    if "2021" in cols and "2024" in cols and "commune" not in cols:
        return "p190"
    if "homme" in cols and "femme" in cols:
        return "p199"
    raise ValueError(f"ICASEES CAR: unrecognised page {path}: {list(t.columns)}")


def _p190(path: str):
    t = pd.read_html(path)[0]
    t.columns = [_key(c) for c in t.columns]
    pref, reg, nat = {}, {}, None
    for _, r in t.iterrows():
        rk, pk = _key(r["region"]), _key(r["prefecture"])
        vals = {"2021": _num(r["2021"]), "2024": _num(r["2024"])}
        if rk == "rca":
            nat = vals
        elif rk == "bas-oubangui":           # Bangui, printed under its region's name
            pref["Bangui"] = vals
            reg["Bas-Oubangui"] = vals
        elif pk == "nan":
            reg[_REGIONS[rk]] = vals
        else:
            pref[_PREFS[pk]] = vals
    return pref, reg, nat


def _p199(path: str):
    t = pd.read_html(path)[0]
    t.columns = ["region", "prefecture", "male", "female", "total", "area", "density"]
    t = t.dropna(subset=["total"])
    pref, reg, nat = {}, {}, None
    for _, r in t.iterrows():
        k = _key(r["prefecture"])
        vals = {s: _num(r[s]) for s in ("male", "female", "total", "density")}
        if k == "totalrca":
            nat = vals
        elif k in _PREFS:
            pref[_PREFS[k]] = vals
            if k == "bangui":
                continue
        elif k in _REGIONS or k == "yade":
            reg[_REGIONS[k]] = vals
        else:
            raise ValueError(f"ICASEES CAR page 199: unknown row {r['prefecture']!r}")
    return pref, reg, nat


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = {_which(p): p for p in [local_path] + list(extras or [])}
    if set(files) != {"p190", "p199"}:
        raise ValueError(f"ICASEES CAR: pages {sorted(files)}")
    p1, r1, n1 = _p190(files["p190"])
    p2, r2, n2 = _p199(files["p199"])
    if set(p1) != set(_REGION_OF) or set(p2) != set(_REGION_OF):
        raise ValueError(f"ICASEES CAR: prefectures {sorted(set(p1) ^ set(_REGION_OF))} "
                         f"{sorted(set(p2) ^ set(_REGION_OF))}")
    regions = set(_REGION_OF.values())
    if set(r1) != regions or set(r2) != regions or n1 is None or n2 is None:
        raise ValueError(f"ICASEES CAR: regions {sorted(r1)} / {sorted(r2)}")

    # page 190: prefectures -> regions -> nation, each year
    for y in ("2021", "2024"):
        for reg in regions:
            s = sum(v[y] for p, v in p1.items() if _REGION_OF[p] == reg)
            if s != r1[reg][y] and _PINNED.get((y, reg)) != r1[reg][y]:
                if not (y == "2024" and abs(s - r1[reg][y]) <= 1):
                    raise ValueError(f"ICASEES CAR 190 {y} {reg}: prefectures {s} != {r1[reg][y]}")
        s = sum(v[y] for v in p1.values())
        if s != n1[y]:
            raise ValueError(f"ICASEES CAR 190 {y}: prefectures {s} != RCA {n1[y]}")
    # page 199: sexes, prefectures -> regions -> nation
    for g, v in {**p2, **r2, "RCA": n2}.items():
        if abs(v["male"] + v["female"] - v["total"]) > 1:
            raise ValueError(f"ICASEES CAR 199 {g}: M + F != T {v}")
    for s in ("male", "female", "total"):
        for reg in regions:
            t = sum(v[s] for p, v in p2.items() if _REGION_OF[p] == reg)
            if abs(t - r2[reg][s]) > 1:
                raise ValueError(f"ICASEES CAR 199 {reg} {s}: {t} != {r2[reg][s]}")
        if abs(sum(v[s] for v in r2.values()) - n2[s]) > 2:
            raise ValueError(f"ICASEES CAR 199 RCA {s}")
    # 2024 printed on both pages
    for g, v in {**p1, **r1}.items():
        a, b = v["2024"], (p2.get(g) or r2[g])["total"]
        if a != b and _PAGE_DIFF_2024.get(g) != (a, b):
            raise ValueError(f"ICASEES CAR 2024 {g}: page 190 {a} vs page 199 {b}")
    if n1["2024"] != n2["total"]:
        raise ValueError("ICASEES CAR 2024 national: pages differ")

    out = []

    def rec(sex, geo, year, measure, value, unit, code):
        out.append({"series_type": "projection", "sex": sex, "age_group": "Total",
                    "geography": geo, "period": year, "frequency": "annual",
                    "measure": measure, "value": value, "unit": unit,
                    "series_code": code})

    for g, v in {**p1, **r1, "Total country": n1}.items():
        rec("total", g, "2021", "count", v["2021"], "persons", "CF_ICASEES_PROJ_PREF_2021_2024")
    for g, v in {**p2, **r2, "Total country": n2}.items():
        for s in ("male", "female", "total"):
            rec(s, g, "2024", "count", v[s], "persons", "CF_ICASEES_PROJ_2024_SEXE")
        rec("total", g, "2024", "density", v["density"], "per_km2", "CF_ICASEES_PROJ_2024_SEXE")
    return pd.DataFrame(out)
