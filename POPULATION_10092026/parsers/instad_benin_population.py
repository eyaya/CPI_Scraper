"""INStaD Benin — population by sex and density across four censuses
(Tier-2 Excel).

INStaD publishes a 'STATISTIQUES DEMOGRAPHIQUES' workbook from which its
demographic PDFs are extracted. Two of its sheets carry the population series:

  STRUCTURE — population by sex for BENIN, its departments and its communes,
    across all four censuses at once:

      Divisions administratives | RGPH4, 2013 |     | RGPH3, 2002 |     | …
                                | Total | Masculin | Féminin | Total | …
      BENIN                     9983884  4868180   5115704   6769914  …

  DENSITE — the published density (hab/km²) for the same geographies and the same
    four censuses, emitted as the schema's `density` measure.

Both sheets carry the census labels in one header row and, for STRUCTURE, the
sex labels in the row beneath, so the parser reads the years and the sex bindings
from the sheet rather than assuming them. Note the sex order here is Total,
Masculin, Féminin — total FIRST, unlike most sources — which is exactly why the
header is read rather than trusted.

`series_type` is 'census': every column is an RGPH enumeration. The 2013 column is
labelled 'Résultats provisoires' by INStaD and is kept as published.

The other sheets (EFFECT_POP's intercensal annual estimates, ACCR_POP, FECON,
MORTA, MIGRAT, MENAGE, POP_ACTIVE) are left for later: EFFECT_POP mixes census
counts with modelled annual values in one row without labelling which is which,
so splitting them would mean inferring the method.
"""
from __future__ import annotations
import re
import unicodedata
import pandas as pd

_SERIES_CODE = "BJ_RGPH"
_NATIONAL = "benin"
_GEOGRAPHY_NATIONAL = "Total country"
_TOLERANCE = 5

_CENSUS = re.compile(r"RGPH\s*\d?\s*,?\s*(?P<year>(?:19|20)\d{2})", re.I)
_SEXES = {"total": "total", "masculin": "male", "feminin": "female"}


def _key(v) -> str:
    v = unicodedata.normalize("NFKD", str(v))
    v = "".join(c for c in v if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", v.lower())


def _census_row(sheet: pd.DataFrame):
    """(row index, {column: 'YYYY'}) for the row naming the censuses."""
    for i in sheet.index:
        years = {}
        for col in sheet.columns:
            v = sheet.at[i, col]
            m = _CENSUS.search(str(v)) if pd.notna(v) else None
            if m:
                years[col] = m.group("year")
        if len(years) >= 2:
            return i, years
    return None, {}


def _geography(label: str) -> str | None:
    name = re.sub(r"\s+", " ", str(label)).strip()
    if not name or _key(name) in ("", "nan"):
        return None
    if _key(name) == _NATIONAL:
        return _GEOGRAPHY_NATIONAL
    # skip header-ish text
    if _key(name).startswith(("divisionsadministratives", "departements",
                              "structure", "densite", "effectif")):
        return None
    return name


def _num(v):
    if pd.isna(v):
        return None
    try:
        return float(str(v).replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def parse(local_path: str) -> pd.DataFrame:
    book = pd.read_excel(local_path, sheet_name=None, header=None)
    records = []

    # ---- STRUCTURE: counts by geography x sex x census ----
    sheet = book.get("STRUCTURE")
    if sheet is not None:
        hdr, years = _census_row(sheet)
        if hdr is not None:
            # each census block is followed by its Total/Masculin/Féminin columns;
            # bind them from the row beneath rather than assuming an order
            bindings = {}          # column -> (year, sex)
            current_year = None
            for col in sheet.columns:
                if col in years:
                    current_year = years[col]
                sex = _SEXES.get(_key(sheet.at[hdr + 1, col]))
                if sex and current_year:
                    bindings[col] = (current_year, sex)

            for i in range(hdr + 2, len(sheet)):
                geography = _geography(sheet.at[i, sheet.columns[0]])
                if not geography:
                    continue
                by_period: dict[str, dict] = {}
                for col, (year, sex) in bindings.items():
                    v = _num(sheet.at[i, col])
                    if v is not None:
                        by_period.setdefault(year, {})[sex] = v
                for year, vals in by_period.items():
                    if {"male", "female", "total"} <= vals.keys():
                        if abs(vals["male"] + vals["female"] - vals["total"]) > _TOLERANCE:
                            continue
                    for sex, v in vals.items():
                        records.append({
                            "series_type": "census", "sex": sex,
                            "age_group": "Total", "geography": geography,
                            "period": year, "frequency": "annual",
                            "measure": "count", "value": v, "unit": "persons",
                            "series_code": _SERIES_CODE,
                        })

    # ---- DENSITE: published density by geography x census ----
    sheet = book.get("DENSITE")
    if sheet is not None:
        hdr, years = _census_row(sheet)
        if hdr is not None:
            for i in range(hdr + 1, len(sheet)):
                geography = _geography(sheet.at[i, sheet.columns[0]])
                if not geography:
                    continue
                for col, year in years.items():
                    v = _num(sheet.at[i, col])
                    if v is None or v <= 0:
                        continue
                    records.append({
                        "series_type": "census", "sex": "total",
                        "age_group": "Total", "geography": geography,
                        "period": year, "frequency": "annual",
                        "measure": "density", "value": v, "unit": "per_km2",
                        "series_code": _SERIES_CODE,
                    })

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Benin population: STRUCTURE/DENSITE sheets not parsed")
    counts = df[df["measure"] == "count"]
    if counts.empty or _GEOGRAPHY_NATIONAL not in set(counts["geography"]):
        raise ValueError("Benin population: national row not found in STRUCTURE")
    if counts["period"].nunique() < 3:
        raise ValueError(
            f"Benin population: only {counts['period'].nunique()} censuses parsed")
    return df.drop_duplicates(["geography", "sex", "age_group", "period", "measure"])
