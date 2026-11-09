"""Somalia -- district poverty rates (SNBS, "District-Level Poverty Estimates in
Somalia: A Fay Herriot Model Approach", 2025; SIHBS 2022).

A joint SNBS / World Bank note published on nbs.gov.so (the acknowledgements
name the World Bank Poverty and Equity GP's technical assistance and the SNBS
team), the same arrangement as the other NSO-hosted joint reports kept.

WHAT IT MEASURES. Poverty at the national poverty line ("Poverty Rate (NPL)",
Table 1) for the RURAL AND URBAN population only: nomadic households, IDPs and
refugee camps are left out (Table 1, note 2: "This also explains the
disparity between the poverty rate displayed and the official national
poverty rate"). So every row carries locality "other" / "Rural and urban
population (excl. nomadic, IDPs)" and can never share an ID with the
Poverty Report 2023's whole-population rates (Awdal 0.357 here vs 39.4 there).
Printed as 0-1 FRACTIONS: unit "index", kept as printed.

Table 8 ("Final FH Estimates") -- read:
  * district P0 from the Fay-Herriot model with its 95% CI: survey label
    "SIHBS 2022 (Fay-Herriot small-area estimates, SNBS 2025)";
  * the regional DIRECT survey rate with its 95% CI: "SIHBS 2022 (direct
    regional estimates, SNBS 2025)". Middle Juba prints no direct rate.
  CI bounds above 1 (Bulo Burto 1.094, Jalalaqsi 1.087: symmetric normal
  intervals) are not shares and are not read; the point estimates are.
Not read: Table A1 / A2 / Table 9's INITIAL model (superseded after SNBS
flagged Garbahaarey, Laasqoray and Zeylac), A2's district DIRECT estimates
(the note says they are not reliable enough for SNBS to publish), the
regression tables. Table 9 files Bu'aale, Jilib and Saakow under Gedo;
Table 8 under Middle Juba, which is followed here.

Period 2022 (SIHBS 2022 fieldwork).

CROSS-CHECK (verbatim): Borama 0.308 (0.224-0.391); Banadir district 0.458,
Banadir region direct 0.44 (0.374-0.505); Hiraan direct 0.815; Jamaame 0.468;
74 districts (Table 1: "Number of Targets (Population) 74").
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T

_LINE = {"line_type": "national", "line_level": "overall",
         "line_name": "Poverty line (SNBS, CBN, SIHBS 2022)"}
_POP = {"topic": "locality", "locality": "other",
        "locality_label": "Rural and urban population (excl. nomadic, IDPs)"}
_SAE = "SIHBS 2022 (Fay-Herriot small-area estimates, SNBS 2025)"
_DIR = "SIHBS 2022 (direct regional estimates, SNBS 2025)"
LAYOUT = {"survey": _SAE, "welfare_aggregate": "consumption", "unit_of_analysis": "person",
          "frequency": "ad_hoc", **_LINE, "period": "2022", "reference_period": "2022",
          "tables": []}
_REGIONS = ["Awdal", "Woqooyi Galbeed", "Togdheer", "Sool", "Sanaag", "Bari", "Nugaal",
            "Mudug", "Galgaduud", "Hiraan", "Middle Shabelle", "Banadir", "Lower Shabelle",
            "Bay", "Bakool", "Gedo", "Middle Juba", "Lower Juba"]
# The SIHBS report (somalia.yaml) spells it "Waqooyi Galbeed".
_GEO = {"Woqooyi Galbeed": "Waqooyi Galbeed"}
_N = r"(\d?\.\d+|1\.\d+)"


def _base(survey, geography):
    return dict(survey=survey, welfare_aggregate="consumption", unit_of_analysis="person",
                period="2022", reference_period="2022", frequency="ad_hoc",
                geography=geography, **_LINE, **_POP)


def _emit(out, survey, geo, p0, lo, hi):
    b = _base(survey, geo)
    out.append(C.row(metric="headcount", value=p0, unit="index", **b))
    for metric, v in (("headcount_ci_low", lo), ("headcount_ci_high", hi)):
        if v <= 1:
            out.append(C.row(metric=metric, value=v, unit="index", **b))


def parse(path: str) -> pd.DataFrame:
    P = T._pages(path, halves=False)["full"]
    pages = [i for i, p in enumerate(P) if "Table 8: Final FH Estimates" in p]
    if not pages:
        raise ValueError("Table 8 not found")
    i0 = pages[-1]
    lines = []
    for i in range(i0, i0 + 3):
        s = P[i]
        if i == i0:
            s = s[s.index("Table 8: Final FH Estimates"):]
        s = re.split(r"Figure 8:", s)[0]
        lines += s.splitlines()
    regs = sorted(_REGIONS, key=len, reverse=True)
    out, region, districts = [], None, []
    for l in lines:
        s = l.strip()
        reg = next((r for r in regs if s.startswith(r + " ")), None)
        rest = s[len(reg) + 1:] if reg else s
        if reg:
            m = re.match(rf"^{_N} {_N} {_N} (.+)$", rest)
            region = reg
            if m:
                _emit(out, _DIR, _GEO.get(reg, reg), *map(float, m.group(1, 2, 3)))
                rest = m.group(4)
        m = re.fullmatch(rf"([A-Z][A-Za-z' ]+?) {_N} {_N} {_N}", rest)
        if not m or region is None:
            continue
        d = m.group(1)
        districts.append(d)
        _emit(out, _SAE, f"{d} district, {_GEO.get(region, region)}", *map(float, m.group(2, 3, 4)))
    if len(districts) != 74 or len(set(districts)) != 74:
        raise ValueError(f"Table 8: expected 74 distinct districts, got {len(districts)}")
    if sum(r["survey"] == _DIR and r["metric"] == "headcount" for r in out) != 17:
        raise ValueError("Table 8: expected 17 regional direct rates")
    return pd.DataFrame(out)
