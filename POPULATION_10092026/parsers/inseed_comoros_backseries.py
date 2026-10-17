"""INSEED Comores -- the census back-series 1980-2003, a SECOND Comoros
descriptor (comoros_backseries.yaml) beside comoros.yaml (the 2017 RGPH4).

Two INSEED documents, both on INSEED's NADA (nada.inseed-comores.org):

* RGPH04 "Thème 0 : Résultats globaux" (2017 census), Tableau 9 "Évolution de
  la population résidante par île et milieu de résidence de 1980 à 2017" --
  resident population of each island and of the Union at the 1980, 1991 and
  2003 censuses (both sexes). 2017 is left to comoros.yaml (Tableau 2.4 of
  the Thème 1 report), and is only CHECKED here against it: Tableau 9's 2017
  column must equal the 2017 totals both reports print (Union 758 316).
* RGPH 2003 "Principaux indicateurs socio-démographiques" (DNS, 2005),
  "Population totale" -- 2003 by sex, for the Union and each island (printed
  as Mohéli / Anjouan / Grande Comore, filed under the RGPH4 island names
  MWALI / NDZUWANI / NGAZIDJA that comoros.yaml uses). Its 2003 totals must
  equal Tableau 9's 2003 column; they do, so 2003 total rows carry the
  Tableau 9 series code and the sex rows the 2003 report's.

NOT READ: Tableau 9's urban/rural rows (no locality column) and its
intercensal growth rates (a rate over a period, not a mid-year value); the
2003 report's age rows ("Population de 0-4 ans" by island sums to 78 087,
while the same report's "Enfants de moins de 5 ans" sums to 70 256 -- the two
printings disagree, so neither is filed).

Checks: islands sum to the Union in every year (exactly); M + F = T in 2003
(exactly).
"""
from __future__ import annotations

import os
import re

import fitz
import pandas as pd

_ISL9 = {"Mwali": "MWALI", "Ndzuwani": "NDZUWANI", "Ngazidja": "NGAZIDJA",
         "Comores": "Total country"}
_YEARS9 = ["1980", "1991", "2003", "2017"]
_CHECK_2017 = {"MWALI": 51567, "NDZUWANI": 327382, "NGAZIDJA": 379367,
               "Total country": 758316}
# the 2003 report's column groups, in print order (T M F each)
_GROUPS03 = ["Total country", "_urbain", "_rural", "MWALI", "NDZUWANI", "NGAZIDJA"]


def _num(s: str) -> float:
    return float(s.replace(" ", "").replace("\xa0", ""))


def _lines(page) -> list[str]:
    return [x.strip() for x in page.get_text().splitlines()]


def _tableau9(path: str) -> dict[str, dict[str, float]]:
    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text()
            if not re.search(r"Tableau 9\s*:\s*.volution de la population r.sidante", text):
                continue
            L = _lines(page)
            start = next((i for i, x in enumerate(L) if x.startswith("Tableau 9")), None)
            if start is None:
                continue
            out: dict[str, dict[str, float]] = {}
            for i in range(start, len(L)):
                geo = _ISL9.get(L[i])
                if geo is None or geo in out:
                    continue
                vals = [x for x in L[i + 1:i + 9] if x][:4]
                if not all(re.fullmatch(r"\d[\d ]*", v) for v in vals):
                    raise ValueError(f"INSEED Comores Tableau 9 {geo}: {vals}")
                out[geo] = dict(zip(_YEARS9, map(_num, vals)))
            if not out:          # the list of tables names it too
                continue
            if set(out) != set(_ISL9.values()):
                raise ValueError(f"INSEED Comores Tableau 9: rows {sorted(out)}")
            return out
    raise ValueError(f"INSEED Comores: Tableau 9 not found in {path}")


def _rgph2003(path: str) -> dict[str, dict[str, float]]:
    with fitz.open(path) as doc:
        for page in doc:
            L = _lines(page)
            if "Population totale" not in L or "Chiffres de la population" not in L:
                continue
            i = L.index("Population totale")
            vals = L[i + 1:i + 19]
            if len(vals) != 18 or not all(re.fullmatch(r"\d+", v) for v in vals):
                raise ValueError(f"INSEED Comores RGPH 2003: {vals}")
            out = {}
            for k, geo in enumerate(_GROUPS03):
                t, m, f = (_num(v) for v in vals[3 * k:3 * k + 3])
                if m + f != t:
                    raise ValueError(f"INSEED Comores 2003 {geo}: {m} + {f} != {t}")
                if not geo.startswith("_"):
                    out[geo] = {"total": t, "male": m, "female": f}
            return out
    raise ValueError(f"INSEED Comores: 2003 'Population totale' not found in {path}")


def _which(path: str) -> str:
    with fitz.open(path) as doc:
        head = " ".join(doc[0].get_text().split())
    if "2003" in head and "PRINCIPAUX INDICATEURS" in head.upper():
        return "rgph2003"
    return "theme0"


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = {_which(p): p for p in [local_path] + list(extras or [])}
    if set(files) != {"theme0", "rgph2003"}:
        raise ValueError(f"INSEED Comores back-series: files {sorted(files)}")
    t9 = _tableau9(files["theme0"])
    s03 = _rgph2003(files["rgph2003"])

    for y in _YEARS9:
        isl = sum(t9[g][y] for g in ("MWALI", "NDZUWANI", "NGAZIDJA"))
        if isl != t9["Total country"][y]:
            raise ValueError(f"INSEED Comores Tableau 9 {y}: islands {isl} != "
                             f"{t9['Total country'][y]}")
    for g, v in _CHECK_2017.items():
        if t9[g]["2017"] != v:
            raise ValueError(f"INSEED Comores Tableau 9 2017 {g}: {t9[g]['2017']} != {v}")
    for g, row in s03.items():
        if row["total"] != t9[g]["2003"]:
            raise ValueError(f"INSEED Comores 2003 {g}: report {row['total']} "
                             f"!= Tableau 9 {t9[g]['2003']}")

    def rec(sex, geo, year, value, code):
        return {"series_type": "census", "sex": sex, "age_group": "Total",
                "geography": geo, "period": year, "frequency": "annual",
                "measure": "count", "value": value, "unit": "persons",
                "series_code": code}

    out = []
    for geo, years in t9.items():
        for y in ("1980", "1991", "2003"):
            out.append(rec("total", geo, y, years[y], "KM_RGPH2017_T9"))
    for geo, row in s03.items():
        for sex in ("male", "female"):
            out.append(rec(sex, geo, "2003", row[sex], "KM_RGPH2003_INDICATEURS"))
    return pd.DataFrame(out)
