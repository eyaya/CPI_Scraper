"""NBS South Sudan — population projections 2020-2040 by state, year, age and sex
(Tier-3 PDF).

The projections report carries two families of table, both captioned in the same
style and both laid out TWO PER ROW across the page:

    Table 2:  South Sudan population projections, 2020-2040   -> rows are YEARS
              Year   Males      Females    Total
              2020   6,775,160  6,474,764  13,249,924

    Table 13: South Sudan population projection, 2020         -> rows are AGE BANDS
              Age group  Males      Females    Total
              0-4        1,369,805  1,350,378  2,720,183

so the caption alone says which it is: the plural 'projections, <range>' keys its
rows by year (age_group 'Total'), the singular 'projection, <year>' keys its rows
by age band for that one year. 185 captions across the report give the country and
its ten states, 2020-2040, by year and by five-year age band.

The side-by-side layout is why this cannot be read from `extract_text()` — a line
there reads '2020 6,775,160 6,474,764 13,249,924 2020 1,076,072 988,494 2,064,566',
two tables' rows concatenated. We therefore split each page down the middle by word
x-position and read each column independently, walking it top-to-bottom so that a
page holding four tables (two across, two down) resolves correctly: a caption sets
the context and the rows beneath it belong to that table until the next caption.

Every row is checked against males + females = total; a row that does not
reconcile is dropped rather than guessed at. Counts use comma thousands
separators. `series_type` is 'projection' throughout — the whole report is a
projection, including its 2020 base year.
"""
from __future__ import annotations
import re
import pandas as pd
import pdfplumber

_SERIES_CODE = "SS_NBS_PROJ_2020_2040"
_NATIONAL = "South Sudan"
_GEOGRAPHY_NATIONAL = "Total country"
_TOLERANCE = 2                      # persons: rounding slack on males+females

_CAPTION = re.compile(
    r"Table\s+\d+\s*:\s*(?P<geo>.+?)\s+population\s+projections?\s*,?\s*"
    r"(?P<span>\d{4}\s*-\s*\d{4}|\d{4})",
    re.I)
_NUM = r"[\d,]{1,15}"
_YEAR_ROW = re.compile(rf"^(?P<label>(?:19|20)\d{{2}})\s+(?P<a>{_NUM})\s+(?P<b>{_NUM})\s+(?P<c>{_NUM})$")
_AGE_ROW = re.compile(
    rf"^(?P<label>\d{{1,3}}\s*-\s*\d{{1,3}}|\d{{1,3}}\s*\+|Total)\s+"
    rf"(?P<a>{_NUM})\s+(?P<b>{_NUM})\s+(?P<c>{_NUM})$", re.I)


def _int(tok: str):
    tok = tok.replace(",", "").strip()
    return int(tok) if tok.isdigit() else None


def _columns(page, gutter: float = 0.5):
    """The page's words split into left and right halves, each as text lines.

    Tables are printed two across, so a text line spans both; splitting on the
    page midpoint keeps each table's rows intact."""
    mid = page.width * gutter
    halves = ([], [])
    for w in page.extract_words():
        halves[0 if w["x0"] < mid else 1].append(w)

    out = []
    for words in halves:
        bands: dict[int, list] = {}
        for w in words:
            bands.setdefault(round(w["top"] / 3.0), []).append(w)
        lines = []
        for _, ws in sorted(bands.items()):
            text = " ".join(w["text"] for w in sorted(ws, key=lambda x: x["x0"]))
            lines.append(re.sub(r"\s+", " ", text).strip())
        out.append(lines)
    return out


def _geography(name: str) -> str:
    geo = re.sub(r"\s+", " ", name).strip(" .,:")
    return _GEOGRAPHY_NATIONAL if geo.lower() == _NATIONAL.lower() else geo


def parse(local_path: str) -> pd.DataFrame:
    records = []

    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages:
            for lines in _columns(page):
                geography, span_year = None, None
                for i, line in enumerate(lines):
                    # A caption wraps mid-range ('… projections, 2020-' / '2040'),
                    # and on the truncated line alone the span regex would match
                    # the bare '2020' and mistake a year-keyed table for a
                    # single-year age table. Matching the joined pair FIRST
                    # recovers the full range; a caption that fits on one line
                    # matches identically either way, since the span is read from
                    # the position right after 'projection(s),'.
                    joined = f"{line} {lines[i + 1]}" if i + 1 < len(lines) else line
                    cap = _CAPTION.match(joined) or _CAPTION.match(line)
                    if cap:
                        geography = _geography(cap.group("geo"))
                        span = cap.group("span")
                        span_year = None if "-" in span else span
                        continue
                    if geography is None:
                        continue

                    m = _AGE_ROW.match(line) if span_year else _YEAR_ROW.match(line)
                    if not m:
                        continue
                    male, female, total = (_int(m.group("a")), _int(m.group("b")),
                                           _int(m.group("c")))
                    if None in (male, female, total):
                        continue
                    if abs(male + female - total) > _TOLERANCE:
                        continue

                    if span_year:
                        period, age = span_year, m.group("label").replace(" ", "")
                        age = "Total" if age.lower() == "total" else age
                    else:
                        period, age = m.group("label"), "Total"

                    for sex, v in (("male", male), ("female", female),
                                   ("total", total)):
                        records.append({
                            "series_type": "projection", "sex": sex,
                            "age_group": age, "geography": geography,
                            "period": period, "frequency": "annual",
                            "measure": "count", "value": float(v),
                            "unit": "persons", "series_code": _SERIES_CODE,
                        })

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("South Sudan population: no projection table parsed")
    if _GEOGRAPHY_NATIONAL not in set(df["geography"]):
        raise ValueError("South Sudan population: national table not found")
    if df["geography"].nunique() < 8:
        raise ValueError(
            f"South Sudan population: only {df['geography'].nunique()} geographies "
            f"— expected the country plus its ten states")
    return df.drop_duplicates(["geography", "sex", "age_group", "period", "measure"])
