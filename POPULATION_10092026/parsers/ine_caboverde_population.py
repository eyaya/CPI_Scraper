"""INE Cabo Verde demographic projections 2010-2040 — population by concelho,
age group and sex (Tier-2 Excel).

INE publishes 'Projeções demográficas da população por concelho e idade simples'
as a workbook with one sheet per geography: 'CABO VERDE' (the national total)
followed by the 22 concelhos. Every sheet has the same three stacked blocks —

    POPULAÇÃO TOTAL - GRUPOS ETÁRIOS
    GRUPO ETÁRIO   2010   2011   …   2040
    Total         477859 480577  …  560359
    0-4            50199  50201  …   37224
    …
    90+             1634   1694  …    3741

    POPULAÇÃO HOMENS - GRUPOS ETÁRIOS      (same shape)
    POPULAÇÃO MULHERES - GRUPOS ETÁRIOS    (same shape)

— so the block caption gives the sex, the row under it gives the projection years,
and each following row is one age band. The parser walks the sheet in that order
rather than by fixed row numbers, so a sheet with an extra blank line or a moved
block still reads.

One workbook therefore yields 23 geographies x 3 sexes x 20 age bands x 31 years.
`series_type` is 'projection' throughout: the whole file is a projection, 2010
included (the base year is projected back onto the 2010 census). Age bands and
concelho names are kept exactly as published; the sheet named 'CABO VERDE' is
mapped to the schema's 'Total country'.

The companion 'Idade_Simples' workbook carries the same projection by single year
of age — same shape, so this parser would read it too if the descriptor pointed
at it; it is left for later because it is three times the size for the same
series.
"""
from __future__ import annotations
import re
import unicodedata
import pandas as pd

_NATIONAL_SHEET = "CABO VERDE"
_GEOGRAPHY_NATIONAL = "Total country"
_SERIES_CODE = "CV_PROJ_2010_2040"
# block caption -> sex
_SEXES = {"total": "total", "homens": "male", "mulheres": "female"}
_CAPTION = re.compile(r"POPULA[ÇC][ÃA]O\s+(TOTAL|HOMENS|MULHERES)", re.I)
_HEADER = "grupoetario"
_AGE = re.compile(r"^(\d{1,3}\s*-\s*\d{1,3}|\d{1,3}\s*\+|Total)$", re.I)


def _key(v) -> str:
    """Accent-stripped, lowercased, letters only — for caption/label matching."""
    s = unicodedata.normalize("NFKD", str(v))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def _label_col(sheet: pd.DataFrame) -> int:
    """The column holding the row labels — the one carrying 'GRUPO ETÁRIO'."""
    for col in sheet.columns:
        if any(_key(v) == _HEADER for v in sheet[col]):
            return col
    raise ValueError("Cabo Verde population: no 'GRUPO ETÁRIO' header column")


def _years(row: pd.Series) -> dict:
    """{column: 'YYYY'} for the projection years on a GRUPO ETÁRIO header row."""
    out = {}
    for col, v in row.items():
        if pd.isna(v):
            continue
        m = re.fullmatch(r"(19|20)\d\d(?:\.0)?", str(v).strip())
        if m:
            out[col] = str(v).strip().split(".")[0]
    return out


def parse(local_path: str) -> pd.DataFrame:
    book = pd.read_excel(local_path, sheet_name=None, header=None)
    records = []

    for name, sheet in book.items():
        try:
            lab = _label_col(sheet)
        except ValueError:
            continue                     # a notes/cover sheet, if INE adds one
        geography = (_GEOGRAPHY_NATIONAL
                     if _key(name) == _key(_NATIONAL_SHEET) else str(name).strip())

        sex, years = None, {}
        for i in sheet.index:
            label = sheet.at[i, lab]
            if pd.isna(label):
                continue
            text = re.sub(r"\s+", " ", str(label)).strip()

            cap = _CAPTION.search(text)
            if cap:
                sex = _SEXES[_key(cap.group(1))]
                years = {}
                continue
            if _key(text) == _HEADER:
                years = _years(sheet.loc[i])
                continue
            if not sex or not years or not _AGE.match(text):
                continue

            age = "Total" if text.lower() == "total" else text.replace(" ", "")
            for col, period in years.items():
                v = pd.to_numeric(sheet.at[i, col], errors="coerce")
                if pd.isna(v):
                    continue
                records.append({
                    "series_type": "projection", "sex": sex, "age_group": age,
                    "geography": geography, "period": period, "frequency": "annual",
                    "measure": "count", "value": float(v), "unit": "persons",
                    "series_code": _SERIES_CODE,
                })

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Cabo Verde population: no projection rows found")
    geos = df["geography"].nunique()
    if geos < 20 or df["sex"].nunique() < 3:
        raise ValueError(
            f"Cabo Verde population: expected the national sheet + 22 concelhos "
            f"x 3 sexes, got {geos} geographies / {df['sex'].nunique()} sexes")
    return df.drop_duplicates(["geography", "sex", "age_group", "period"])
