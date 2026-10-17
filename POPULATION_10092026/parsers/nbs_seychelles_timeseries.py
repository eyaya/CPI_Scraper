"""NBS Seychelles -- "Population & Vital Statistics" time series workbook:
"MID-YEAR POPULATION ESTIMATES, REGISTERED BIRTHS AND DEATHS, 1971-2016". A
SECOND Seychelles descriptor (seychelles_timeseries.yaml) beside
seychelles.yaml (the 2026 mid-year estimated resident population by age).

Read: Year x "Mid-year Population" -> count (persons), national, series_type
estimate, 1971-2016. Year cells can carry a footnote marker ("2010(10)").

AS PUBLISHED, WITH ITS BREAKS. The workbook's own notes say the series was
rebased on the 1987 census (1987-1993), the 1994 census, the 2002 census and
the 2010 census, adjusted for misreported births, and that one census figure
was raised 2.4 % for undercount. Those are NBS's published values; nothing is
re-chained here.

NOT READ: births, deaths, infant deaths and the crude/infant rates (no
schema measure for vital events).

Checks: years run 1971-2016 without gaps; values are whole numbers between
50 000 and 120 000.
"""
from __future__ import annotations

import re

import pandas as pd


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    t = pd.read_excel(local_path, header=None)
    title = str(t.iloc[0, 0])
    if not title.upper().startswith("MID-YEAR POPULATION ESTIMATES"):
        raise ValueError(f"NBS Seychelles: unexpected title {title!r}")
    head = next(i for i in range(len(t)) if str(t.iloc[i, 0]).strip() == "Year")
    if str(t.iloc[head, 1]).strip() != "Population" or "Mid-year" not in str(t.iloc[head - 1, 1]):
        raise ValueError("NBS Seychelles: column 1 is not 'Mid-year Population'")
    out = []
    for i in range(head + 1, len(t)):
        cell = str(t.iloc[i, 0]).strip()
        if cell.startswith("Source"):
            break
        m = re.fullmatch(r"((?:19|20)\d\d)(?:\s*\(\s*\d+\s*\))?(?:\.0)?", cell)   # "1987( 3)"
        if not m:
            continue
        v = t.iloc[i, 1]
        if isinstance(v, str) and re.fullmatch(r"\s*\d+\s*", v):
            v = int(v)                    # some cells are text ("  56029")
        if not isinstance(v, (int, float)) or v != int(v) or not 50000 <= v <= 120000:
            raise ValueError(f"NBS Seychelles {m.group(1)}: population {v!r}")
        out.append({"series_type": "estimate", "sex": "total", "age_group": "Total",
                    "geography": "Total country", "period": m.group(1),
                    "frequency": "annual", "measure": "count", "value": float(v),
                    "unit": "persons", "series_code": "SC_NBS_POP_VITAL_TS"})
    years = [int(r["period"]) for r in out]
    if years != list(range(1971, max(years) + 1)) or max(years) < 2016:
        raise ValueError(f"NBS Seychelles: years {years[:3]}...{years[-3:]}")
    return pd.DataFrame(out)
