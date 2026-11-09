"""Sierra Leone -- Stats SL "2011 Integrated Household Survey Report",
Table 12.5.8 "Objective and subjective poverty estimates": the ORIGINAL
SLIHS 2003/04 and SLIHS 2011 national headcounts on the absolute (overall)
line and on the food line (total consumption below the food line, filed
extreme, like the 2018 report's "Food poverty line").

These are each round's own published estimates; the 2018 report's 2011
figures (already collected) are a RE-ESTIMATE on an aggregate made
comparable with 2018 and carry their own survey label.

PUBLISHED INCONSISTENCY kept as printed: the prose above the table says
the 2011 food-line rate is 47.7%, the table prints 13.9% -- the table is
read (47.7 is not consistent with an absolute rate of 53.9 and the 2018
report's 2011 extreme rate). Subjective measures are not consumption
poverty and are not read. The SLIHS 2003/04 main report itself has no
consumption-poverty table (Stats SL published that round's profile
separately -- see sources_blocked notes in the descriptor).
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

LAYOUT = {"survey": "SLIHS 2011", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
          "frequency": "ad_hoc", "line_type": "national", "line_level": "overall",
          "line_name": "Absolute poverty line (ABPL), SLIHS", "period": "2011",
          "reference_period": "2011", "tables": []}


def parse(path: str) -> pd.DataFrame:
    import fitz
    doc = fitz.open(path)
    page = [doc[i].get_text() for i in range(doc.page_count)
            if "Table 12.5.8" in doc[i].get_text() and "Objective and subjective poverty" in doc[i].get_text()][-1]
    txt = " ".join(page[page.index("Table 12.5.8"):].split())
    rows = []
    for lab, level, name in (("Food poverty line", "extreme", "Food poverty line, SLIHS"),
                             ("Absolute poverty line (ABPL)", "overall", "Absolute poverty line (ABPL), SLIHS")):
        m = re.search(re.escape(lab) + r"\s+(\d+\.\d)%\s+(\d+\.\d)%", txt)
        if not m:
            raise ValueError(f"Table 12.5.8: {lab} not found")
        for (survey, period, ref), v in zip((("SLIHS 2003/04 (as republished 2011)", "2003", "2003/04"),
                                              ("SLIHS 2011", "2011", "2011")), m.groups()):
            rows.append(C.row(metric="headcount", value=float(v), survey=survey,
                              welfare_aggregate="consumption", line_type="national", line_level=level,
                              line_name=name, period=period, reference_period=ref,
                              frequency="ad_hoc", unit_of_analysis="person"))
    return pd.DataFrame(rows)
