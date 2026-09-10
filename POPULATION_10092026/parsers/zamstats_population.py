"""ZamStats Zambia — projected mid-year population by province and sex
(Tier-3 PDF).

Parser for Table 1 of the national projections report, 'Projected Mid-year
Population by Province, Sex and year of projection (Medium Variant), Zambia,
2023-2047':

    Province     Sex      2023        2030        2035    2040    2045    2047
    Zambia       Total  20,986,170  25,902,763   …
                 Male   10,351,499  12,822,132   …
                 Female 10,634,671  13,080,631   …
    Central      Total   2,423,651   3,198,834   …

The province name appears only on its 'Total' row and is implied for the Male and
Female rows beneath it, so the parser carries it forward. The reported years are
the six the table prints (2023, 2030, 2035, 2040, 2045, 2047), not every year of
the span.

A second table — variant projections by year — is printed to the RIGHT of this
one, so its rows interleave with Table 1's in `extract_text()`. We therefore keep
only the words left of the page's table gutter before rebuilding lines.

Every province block is checked against male + female = total.

WHAT IS DELIBERATELY NOT READ: Table A1 ('Total Population by Sex, Age (5 Year
Age Groups) and Year of Projection') would add the age dimension over all 25
years, but it is printed as three stacked residence sections — Zambia, Rural and
Urban — whose labels appear in a merged cell that is absent from the text layer
and is not rotated text either, so there is no way to tell a national section from
a rural one except by arithmetic. Emitting it would risk labelling a rural
subtotal as the national population, so the age detail is left for a source that
states its own geography. That is why this parser emits `age_group = Total` only.
"""
from __future__ import annotations
import re
import pandas as pd
import pdfplumber

_SERIES_CODE = "ZM_PROJ_2023_2047"
_NATIONAL = "Zambia"
_GEOGRAPHY_NATIONAL = "Total country"
_TOLERANCE = 2
_GUTTER = 0.62          # fraction of page width: Table 1 sits left of this

_CAPTION = re.compile(
    r"Table\s*1\s*:\s*Projected\s+Mid-?year\s+Population\s+by\s+Province", re.I)
_HEADER_YEARS = re.compile(r"^((?:(?:19|20)\d{2}\s+){3,}(?:19|20)\d{2})$")
_NUM = r"[\d,]{3,15}"
# The province name, when present, is a whole word followed by whitespace: without
# demanding that separator the lazy group splits 'Female' into 'Fe' + 'male' and
# invents a province.
_ROW = re.compile(
    rf"^(?:(?P<province>[A-Za-z][A-Za-z .'\-]*?)\s+)?"
    rf"(?P<sex>Total|Male|Female)\s+(?P<nums>(?:{_NUM}\s+)*{_NUM})$", re.I)
_SEXES = {"total": "total", "male": "male", "female": "female"}


def _lines(page, gutter: float = _GUTTER):
    """Text lines rebuilt from the words left of the table gutter."""
    limit = page.width * gutter
    bands: dict[int, list] = {}
    for w in page.extract_words():
        if w["x0"] < limit:
            bands.setdefault(round(w["top"] / 3.0), []).append(w)
    out = []
    for _, ws in sorted(bands.items()):
        text = " ".join(w["text"] for w in sorted(ws, key=lambda x: x["x0"]))
        out.append(re.sub(r"\s+", " ", text).strip())
    return out


def parse(local_path: str) -> pd.DataFrame:
    records, pending = [], {}

    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages:
            lines = _lines(page)
            if not any(_CAPTION.search(ln) for ln in lines):
                continue

            years, province = [], None
            for line in lines:
                head = _HEADER_YEARS.match(line)
                if head:
                    years = head.group(1).split()
                    continue
                if not years:
                    continue
                m = _ROW.match(line)
                if not m:
                    continue

                name = (m.group("province") or "").strip()
                if name:
                    province = (_GEOGRAPHY_NATIONAL
                                if name.lower() == _NATIONAL.lower() else name)
                if province is None:
                    continue

                nums = [int(t.replace(",", "")) for t in m.group("nums").split()]
                if len(nums) != len(years):
                    continue
                sex = _SEXES[m.group("sex").lower()]
                pending.setdefault(province, {})[sex] = nums

                for period, v in zip(years, nums):
                    records.append({
                        "series_type": "projection", "sex": sex,
                        "age_group": "Total", "geography": province,
                        "period": period, "frequency": "annual",
                        "measure": "count", "value": float(v), "unit": "persons",
                        "series_code": _SERIES_CODE,
                    })

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Zambia population: Table 1 (province x sex) not found")

    # male + female must reconcile to the province's own published total
    for province, byset in pending.items():
        if {"male", "female", "total"} <= byset.keys():
            for m, f, t in zip(byset["male"], byset["female"], byset["total"]):
                if abs(m + f - t) > _TOLERANCE:
                    raise ValueError(
                        f"Zambia population: {province} does not reconcile "
                        f"({m} + {f} != {t})")

    if _GEOGRAPHY_NATIONAL not in set(df["geography"]):
        raise ValueError("Zambia population: national row not found")
    if df["geography"].nunique() < 8:
        raise ValueError(
            f"Zambia population: only {df['geography'].nunique()} geographies — "
            f"expected the country plus its ten provinces")
    return df.drop_duplicates(["geography", "sex", "age_group", "period", "measure"])
