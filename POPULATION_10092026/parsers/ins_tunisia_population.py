"""INS Tunisia — mid-year population estimates by age group and governorate
(Tier-2 HTML tables).

The INS statistics page for demography server-renders its tables into the page
(the same shape the Tunisian CPI source uses), so `pandas.read_html` reads them
directly — no API and no file download. Three tables are published:

    Population au 1er janvier                    2021-2026, national only
    Population au 1er Juillet par tranche d'âge  2016-2024, national by age band
    Population au 1er Juillet par gouvernorat    2016-2024, Tunisie + 24 governorates

Each table is laid out with its caption and unit/source notes in the first
column's opening rows, the years as the column header, and the data rows below;
the first data row is the aggregate ('Population au 1er Juillet' / 'Tunisie') and
the rest are the breakdown. A cell that INS has not published is written '--'
and is skipped rather than zero-filled.

ONLY THE MID-YEAR (1er Juillet) TABLES ARE EMITTED. The schema defines `period`
as a mid-year year, and the 1 January table is a different reference date for the
same country and year — emitting both would put two different values under one
key, so the January series is deliberately left out rather than silently spliced
onto the July one. That does cost the 2025 and 2026 figures, which INS so far
publishes only on the January basis.

INS gives no sex split in these tables, so every row is `sex = total`;
`series_type` is 'estimate' throughout (these are intercensal estimates, not the
RGPH count). Governorate names and age bands are kept exactly as published.
"""
from __future__ import annotations
import io
import re
import unicodedata
import pandas as pd

_SERIES_CODE = "TN_INS_POP"
_NATIONAL = "Total country"
_MISSING = {"--", "-", "", "nan", "none", "n/a"}
_YEAR = re.compile(r"^(19|20)\d{2}$")
# INS writes an open-ended top band as '80 & +' (and has used '80 et plus'), so
# the pattern has to accept the ampersand form too — missing it silently drops the
# oldest band, which is exactly the size of the gap it leaves in the age total.
_AGE_ROW = re.compile(
    r"^\d{1,3}\s*-\s*\d{1,3}$"
    r"|^\d{1,3}\s*(?:&\s*)?\+$"
    r"|^\d{1,3}\s*(?:ans\s*)?et\s*plus$", re.I)


def _age_label(label: str) -> str:
    """'00-04' -> '00-04'; '80 & +' / '80 et plus' -> '80+'."""
    text = re.sub(r"\s+", " ", label).strip()
    m = re.match(r"^(\d{1,3})\s*-\s*(\d{1,3})$", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"^(\d{1,3})", text)
    return f"{m.group(1)}+" if m else text


def _key(s) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def _years(frame: pd.DataFrame) -> dict:
    """{column: 'YYYY'} for the year columns of a table."""
    out = {}
    for col in frame.columns:
        text = str(col).strip().split(".")[0]
        if _YEAR.match(text):
            out[col] = text
    return out


def _caption(frame: pd.DataFrame, label_col) -> str:
    """The table's own title — the first label cell mentioning 'Population'."""
    for v in frame[label_col]:
        if pd.notna(v) and "population" in _key(v):
            return _key(v)
    return ""


def _value(cell):
    if pd.isna(cell) or _key(cell) in _MISSING:
        return None
    text = re.sub(r"[\s ]", "", str(cell)).replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def parse(local_path: str) -> pd.DataFrame:
    with open(local_path, "r", encoding="utf-8", errors="replace") as fh:
        html = fh.read()
    tables = pd.read_html(io.StringIO(html))

    records = []
    for frame in tables:
        if frame.empty:
            continue
        label_col = frame.columns[0]
        years = _years(frame)
        if not years:
            continue
        caption = _caption(frame, label_col)
        if "1er juillet" not in caption:
            continue                       # see module docstring: mid-year only

        by_governorate = "gouvernorat" in caption
        by_age = "age" in caption or "tranche" in caption
        if not (by_governorate or by_age):
            continue

        seen_aggregate = False
        for i in frame.index:
            raw = frame.at[i, label_col]
            if pd.isna(raw):
                continue
            label = re.sub(r"\s+", " ", str(raw)).strip()
            key = _key(label)
            if not key or key.startswith(("nofilter", "unite", "source")):
                continue
            if key == caption:
                continue                   # the table's own title row

            # The first data row is the aggregate; the rest are the breakdown.
            is_aggregate = (not seen_aggregate
                            and (key.startswith("population") or key == "tunisie"))
            if is_aggregate:
                geography, age = _NATIONAL, "Total"
                seen_aggregate = True
            elif by_governorate:
                geography, age = label, "Total"
            elif _AGE_ROW.match(label):
                geography, age = _NATIONAL, _age_label(label)
            else:
                continue

            for col, period in years.items():
                v = _value(frame.at[i, col])
                if v is None:
                    continue
                records.append({
                    "series_type": "estimate", "sex": "total", "age_group": age,
                    "geography": geography, "period": period, "frequency": "annual",
                    "measure": "count", "value": v, "unit": "persons",
                    "series_code": _SERIES_CODE,
                })

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Tunisia population: no mid-year table found on the page")
    if df["geography"].nunique() < 10:
        raise ValueError(
            f"Tunisia population: only {df['geography'].nunique()} geographies — "
            f"the governorate table did not parse")
    return df.drop_duplicates(["geography", "sex", "age_group", "period", "measure"])
