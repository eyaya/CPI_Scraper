"""South Sudan -- county poverty estimates for 2008 (SSNBS with the World Bank).

"South Sudan Poverty Estimates at the County Level for 2008", Table 1: P0 and
its 95% confidence interval for 79 counties. SMALL-AREA ESTIMATES (Elbers-
Lanjouw-Lanjouw: NBHS 2009 consumption model imputed onto the 2008 census),
dated to the CENSUS (2008), on the NBHS 2009 line (SDG 72.9 per person per
month) -- filed under their own survey label, never as survey estimates.
Values are printed as whole percentages. Places carry their level
("Juba (county)"); the state is printed only on a state's first row.

CROSS-CHECK (verbatim): Malakal 12% (5%, 19%) lowest, Aweil South 82%
(76%, 87%) highest; Juba 36%.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C

LAYOUT = {"survey": "Small-area estimates 2008 (census 2008 x NBHS 2009)",
          "welfare_aggregate": "consumption", "unit_of_analysis": "person",
          "frequency": "ad_hoc", "decimal": ".", "line_type": "national",
          "line_level": "overall", "line_name": "National poverty line (NBHS 2009)",
          "line_value": 72.9, "line_unit": "SDG per person per month",
          "period": "2008", "reference_period": "2008", "tables": []}
_STATE = re.compile(r"^(?:Central Equatoria|Eastern Equatoria|Jonglei|Lakes|Northern|"
                    r"Bahr El Ghazal|Unity|Upper Nile|Warrap|Western|Equatoria)\s+")
_ROW = re.compile(r"^(.+?)\s+(\d{1,3})%\s+\((\d{1,3})%\s*,\s*(\d{1,3})%\)\s*$")


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    base = {k: LAYOUT[k] for k in ("survey", "welfare_aggregate", "unit_of_analysis", "frequency",
                                   "line_type", "line_level", "line_name", "line_value",
                                   "line_unit", "period", "reference_period")}
    out, seen = [], []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if "County Poverty Estimates" not in t and "95% confidence interval" not in t:
                continue
            for ln in t.splitlines():
                m = _ROW.match(ln.strip())
                if not m:
                    continue
                name = _STATE.sub("", m.group(1)).strip()
                name = _STATE.sub("", name).strip()       # "Northern Bahr El Ghazal" spans two words
                if name in seen:
                    raise ValueError(f"county printed twice: {name}")
                seen.append(name)
                g = {"geography": f"{name} (county)"}
                for metric, v in (("headcount", m.group(2)), ("headcount_ci_low", m.group(3)),
                                  ("headcount_ci_high", m.group(4))):
                    out.append(C.row(metric=metric, value=float(v), **base, **g))
    if len(seen) != 79:
        raise ValueError(f"Table 1: expected 79 counties, got {len(seen)}")
    return pd.DataFrame(out)
