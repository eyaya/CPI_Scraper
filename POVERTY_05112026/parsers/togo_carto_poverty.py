"""Togo -- INSEED, "Cartographie de la pauvreté 2017" (inseed.tg/download/2626/).

SMALL-AREA ESTIMATES: consumption is modelled on QUIBB 2015 and imputed into
a 2017 listing survey; P0 / P1 / P2 are then computed for the 5 regions, 39
prefectures and the 5 arrondissements of Lomé commune (p.15-16). They are
INSEED's published estimates ("seul l'INSEED est responsable des résultats"),
kept under their own survey label so they are never read as a household-
survey round. The national 53,5% is printed in prose only.

Annexe Tableau 3 prints, per area, P0 2011 | P0 2017 | P1 2011 | P1 2017 | P2
2011 | P2 2017. 2017 values are whole numbers as printed. The 2011 columns
are the 2011 poverty map (QUIBB 2011 based), filed "Cartographie de la
pauvreté 2011 (républiée, cartographie 2017)". Prefectures created after 2011
(Agoènyive, Kpendjal Ouest, Oti Sud) print 2017 only; Kpendjal's and Oti's
2011 values sit on an unlabelled line between the old and the new
prefecture and are NOT taken (they cover the pre-split area).

CROSS-CHECK (verbatim): Golfe 47 / 18 / 9 (2017), 32,6 / 10,4 / 4,7 (2011);
Savanes 65 (2017), 87,3 (2011); Lomé commune 30; Tandjoare 2011 94,0.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T

LAYOUT = {"survey": "Cartographie de la pauvreté 2017 (petits domaines, QUIBB 2015)",
          "welfare_aggregate": "consumption", "unit_of_analysis": "person", "line_type": "national",
          "line_level": "overall", "line_name": "Seuil national de pauvreté (cartographie)",
          "period": "2017", "frequency": "ad_hoc", "decimal": ",", "tables": []}
_REGIONS = {"Maritime", "Plateaux", "Centrale", "Kara", "Savanes"}


def parse(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)["full"]
    text = "\n".join(t for t in pages[52:56])
    k = text.index("Tableau 3: Tableau comparatif")
    end = text.index("Annexe 5")
    rows = []
    for ln in text[k:end].splitlines():
        s = ln.strip()
        m = re.match(r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\- ]*?(?: I{1,3}| IV| V)?)\s+(\d.*)$", s)
        if not m or m.group(1).startswith(("Préfecture", "Tableau")):
            continue
        name = m.group(1).strip()
        nums = C.numbers_in(m.group(2), decimal=",")
        if len(nums) == 6:
            pairs = [("2011", nums[0::2]), ("2017", nums[1::2])]
        elif len(nums) == 3:
            pairs = [("2017", nums)]
        else:
            raise ValueError(f"{name}: {nums}")
        geo = name if name != "Lomé commune" else "Lomé commune"
        for per, vals in pairs:
            sv = LAYOUT["survey"] if per == "2017" else "Cartographie de la pauvreté 2011 (républiée, cartographie 2017)"
            for metric, v in zip(("headcount", "gap", "severity"), vals):
                rows.append(C.row(metric=metric, value=v, survey=sv, welfare_aggregate="consumption",
                                  line_type="national", line_level="overall", line_name=LAYOUT["line_name"],
                                  period=per, reference_period=per, frequency="ad_hoc", geography=geo))
    df = pd.DataFrame.from_records(rows)
    if df["geography"].nunique() < 50:
        raise ValueError(f"only {df['geography'].nunique()} areas read")
    return df
