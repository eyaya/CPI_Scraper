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
    est = pd.DataFrame.from_records(out).drop_duplicates(["age_group", "sex", "period"])
    return pd.concat([est, pd.DataFrame.from_records(_projection(local_path))],
                     ignore_index=True)


# Table 35 -- the MEDIUM scenario of the 2022-2052 projections (added
# 2026-10-06). The same workbook prints high (T34) and low (T36) scenarios too;
# this schema has no scenario column, so only one can be held without the
# three overwriting each other, and the medium variant is the one this corpus
# takes everywhere (Zambia, Ghana). Urban and rural (T37-T42) are deferred: no
# locality column. Its 2022 column is the projection BASE (13,206,731), kept
# beside Table 3's estimate (13,206,728) -- different series_type, and both
# are what NISR prints.
_PROJ_SHEET = "Table 35"
_PROJ_TITLE = "medium projections scenario"


def _projection(local_path: str) -> list[dict]:
    df = pd.ExcelFile(local_path).parse(_PROJ_SHEET, header=None, dtype=str)
    title = " ".join(str(v) for v in df.iloc[:3].values.ravel() if str(v) != "nan")
    if _PROJ_TITLE not in title.lower():
        raise ValueError(f"nisr_rwanda_population: {_PROJ_SHEET} is not the "
                         f"medium scenario: {title[:90]!r}")
    hdr = next(i for i in range(len(df)) if str(df.iat[i, 1]).startswith("5 year age"))
    years, sexes = df.iloc[hdr].tolist(), df.iloc[hdr + 1].tolist()
    cols, year = [], None
    for j in range(2, df.shape[1]):
        if re.fullmatch(r"20\d\d", str(years[j]).strip()):
            year = str(years[j]).strip()
        sx = {"Both sexes": "total", "Male": "male", "Female": "female"}.get(
            str(sexes[j]).strip())
        if year and sx:
            cols.append((j, year, sx))
    if len(cols) != 31 * 3:
        raise ValueError(f"nisr_rwanda_population: {len(cols)} year x sex columns, "
                         f"expected 93 (2022-2052)")
    out, bands, totals = [], {}, {}
    for i in range(hdr + 2, len(df)):
        label = str(df.iat[i, 1]).strip()
        if not _AGE_RE.match(label.replace(" ", "")) and label != "80 +":
            continue
        age = "Total" if label.lower() == "total" else re.sub(r"\s+", "", label)
        for j, yr, sx in cols:
            v = _num(df.iat[i, j])
            if v is None:
                continue
            if age == "Total":
                totals[(yr, sx)] = v
            else:
                bands[(yr, sx)] = bands.get((yr, sx), 0) + v
            out.append({"series_type": "projection", "sex": sx, "age_group": age,
                        "geography": "Total country", "period": yr,
                        "frequency": "annual", "measure": "count", "value": v,
                        "unit": "persons", "series_code": "RW_RPHC5_T35_MEDIUM"})
    # The 17 bands must reproduce each printed Total, and both sexes must sum.
    for key, tot in totals.items():
        if abs(bands.get(key, 0) - tot) > 3:
            raise ValueError(f"nisr_rwanda_population T35 {key}: bands "
                             f"{bands.get(key)} vs Total {tot}")
    for yr in {y for y, _ in totals}:
        m, f, t = (totals.get((yr, s)) for s in ("male", "female", "total"))
        if abs(m + f - t) > 3:
            raise ValueError(f"nisr_rwanda_population T35 {yr}: M+F {m + f} != {t}")
    return out
