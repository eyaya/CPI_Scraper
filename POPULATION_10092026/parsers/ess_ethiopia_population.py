"""ESS Ethiopia — projected population by region, zone and wereda (Tier-3 PDF).

Parser for 'Population Size by Sex, Area and Density by Region, Zone and Wereda',
the Ethiopian Statistical Service's annual projection. Every data row carries NINE
counts — three residence blocks of male / female / both:

    <geography>            Total                 Urban                Rural
                        M       F       T      M      F      T     M      F      T
    TIGRAY Region  2,983,000 3,052,000 6,035,000 1,016,000 … 1,967,000 …

and the blocks reconcile exactly: urban + rural = total, and male + female = both
within each block.

The document is a flat list of three administrative levels, distinguished by the
suffix the source itself prints — '<name> Region', '<name>-Wereda', and zones,
whose NAME sits on its own line above a 'Zone Total' row:

    North Western Tigray-Zone          <- name only, no numbers
    Zone Total   489,221  493,956  …   <- the zone's counts

so the zone name is carried forward onto its total row. Each geography keeps the
label the source gives it, suffix included, which is what preserves the level
(region / zone / wereda) in a schema whose `geography` is a single flat column.

ONLY THE TOTAL BLOCK IS EMITTED. The urban and rural columns are a residence
split, and this schema has no residence dimension — encoding it into `geography`
("TIGRAY Region (Urban)") would invent a place that does not exist, so the split
is dropped rather than misrepresented. Density, which the title mentions, is not
in the table body of this edition.
"""
from __future__ import annotations
import re
import pandas as pd
import pdfplumber

_SERIES_CODE = "ET_ESS_PROJ"
_GEOGRAPHY_NATIONAL = "Total country"
_TOLERANCE = 5

_TITLE_YEAR = re.compile(r"Population\s+Size\s+by\s+Sex.*?:\s*\w+\s+(?P<year>\d{4})", re.I | re.S)
_NUM = r"[\d,]{1,15}"
# a data row ends in nine counts: total M/F/T, urban M/F/T, rural M/F/T
_ROW = re.compile(rf"^(?P<label>.+?)\s+(?P<nums>(?:{_NUM}\s+){{8}}{_NUM})$")
_ZONE_NAME = re.compile(r"^(?P<name>[^\d,]{3,60}?)\s*-?\s*Zone\s*\**$", re.I)
_ZONE_TOTAL = re.compile(r"^Zone\s+Total\**$", re.I)
# Most regions print their NAME on its own line and their counts on a generic
# 'Region Total' row beneath it (only the first region carries both on one line),
# and a footnote marker '*' or '**' may be appended to either.
_REGION_NAME = re.compile(r"^(?P<name>[^\d,]{3,60}?)\s+Region\s*\**$", re.I)
_REGION_TOTAL = re.compile(r"^Region\s+Total\**$", re.I)
_COUNTRY = re.compile(r"^(Ethiopia|Country\s+Total|Grand\s+Total)\**$", re.I)


def _int(tok: str):
    tok = tok.replace(",", "").strip()
    return int(tok) if tok.isdigit() else None


def parse(local_path: str) -> pd.DataFrame:
    with pdfplumber.open(local_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    text = "\n".join(pages)

    m = _TITLE_YEAR.search(re.sub(r"\s+", " ", text))
    if not m:
        raise ValueError("Ethiopia population: projection year not found in the title")
    period = m.group("year")

    records, seen = [], set()
    pending_zone = pending_region = None
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue

        zone = _ZONE_NAME.match(line)
        if zone:
            pending_zone = f"{zone.group('name').strip(' -')} Zone"
            continue
        region = _REGION_NAME.match(line)
        if region:
            pending_region = f"{region.group('name').strip(' -')} Region"
            continue

        row = _ROW.match(line)
        if not row:
            continue
        label = row.group("label").strip(" -")
        nums = [_int(t) for t in row.group("nums").split()]
        if len(nums) != 9 or any(v is None for v in nums):
            continue

        male, female, total = nums[0], nums[1], nums[2]
        if abs(male + female - total) > _TOLERANCE:
            continue
        # urban + rural must reproduce the total block, else the row mis-parsed
        if abs((nums[5] + nums[8]) - total) > _TOLERANCE:
            continue

        if _ZONE_TOTAL.match(label):
            if not pending_zone:
                continue
            geography, pending_zone = pending_zone, None
        elif _REGION_TOTAL.match(label):
            if not pending_region:
                continue
            geography, pending_region = pending_region, None
        elif _COUNTRY.match(label):
            geography = _GEOGRAPHY_NATIONAL
        else:
            geography = label

        if geography in seen:
            continue                       # a locality repeated across pages
        seen.add(geography)
        for sex, v in (("male", male), ("female", female), ("total", total)):
            records.append({
                "series_type": "projection", "sex": sex, "age_group": "Total",
                "geography": geography, "period": period, "frequency": "annual",
                "measure": "count", "value": float(v), "unit": "persons",
                "series_code": _SERIES_CODE,
            })

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Ethiopia population: no projection rows parsed")
    if df["geography"].nunique() < 50:
        raise ValueError(
            f"Ethiopia population: only {df['geography'].nunique()} geographies — "
            f"expected regions, zones and weredas")
    return df.drop_duplicates(["geography", "sex", "age_group", "period", "measure"])
