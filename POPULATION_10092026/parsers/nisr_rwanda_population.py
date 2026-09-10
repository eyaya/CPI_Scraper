"""NISR Rwanda RPHC5 2022 — mid-year population by age & sex (clean Excel).

Parser for the RPHC5 Population Projections thematic report workbook (.xls),
Table 3 ("Mid-Year Population as of 1st July, 2022"). The Total block gives Both
sexes / Male / Female by five-year age group; we emit those as the national mid-year
2022 population (series_type = estimate). Values are the projection model's
fractional persons, kept as published.
"""
from __future__ import annotations
import re
import pandas as pd

_SHEET = "Table 3"
_AGE_RE = re.compile(r"^(\d{1,2}\s*-\s*\d{1,2}|\d{1,2}\+|Total)$", re.I)


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse(local_path: str) -> pd.DataFrame:
    df = pd.ExcelFile(local_path).parse(_SHEET, header=None)
    rows = df.values.tolist()

    # find the age-label column and the Total block's Both/Male/Female columns.
    # Layout: [_, age, Total-Both, Total-Male, Total-Female, Urban..., Rural...]
    out = []
    for r in rows:
        cells = [("" if (c is None or (isinstance(c, float) and pd.isna(c))) else str(c).strip())
                 for c in r]
        # age label is the first cell matching the age pattern
        ai = next((i for i, c in enumerate(cells) if _AGE_RE.match(c)), None)
        if ai is None:
            continue
        nums = [_num(r[j]) for j in range(ai + 1, len(r))]
        nums = [x for x in nums if x is not None]
        if len(nums) < 3:
            continue
        total, male, female = nums[0], nums[1], nums[2]
        if total <= 0 or abs(male + female - total) > max(5, 0.01 * total):
            continue
        label = cells[ai]
        age = "Total" if label.lower() == "total" else re.sub(r"\s*-\s*", "-", label)
        for sex, v in (("total", total), ("male", male), ("female", female)):
            out.append({
                "series_type": "estimate", "sex": sex, "age_group": age,
                "geography": "Total country", "period": "2022",
                "frequency": "annual", "measure": "count", "value": v,
                "unit": "persons", "series_code": "RW_RPHC5_T3",
            })
    if not out:
        raise ValueError("nisr_rwanda_population: Table 3 not parsed")
    return pd.DataFrame.from_records(out).drop_duplicates(["age_group", "sex", "period"])
