"""Statistics Mauritius CMPHS workbook — a TRANSPOSED quarterly release.

`excel_wide_series` reads a workbook whose PERIODS RUN ACROSS THE COLUMNS, which
is what Stats SA's QLFS Trends file does. Mauritius publishes the opposite
shape, and every sheet failed the same way:

    Table 1: no period header row found in the first 30 rows
    Table 2: no period header row found in the first 30 rows
    ... (all nine sheets)

Nine identical failures are not nine layout changes; they are one wrong model.
Here the periods run DOWN column A and the indicators run across, so this reads
the workbook directly.

Two sheets are taken:

**Table 1** — five quarters of counts, in three sex blocks:

        Population aged 16+ | In employment ...        | Unem- | Total econ. | Total econ.
                            | Employees .. Total       | ployed| active      | inactive
    Both sexes
    2025 Q1        993.0      436.9 ..  547.6            35.2     582.8         410.2

**Table 2** — the current quarter only, but by SEX x AGE GROUP and, crucially,
carrying the RATES Statistics Mauritius publishes (employment, unemployment and
activity). Those are read as published; nothing here divides one column by
another.

EVERY COUNT IS IN THOUSANDS and is emitted as `thousand_persons` rather than
being multiplied out — the workbook says "In thousands" and that is what is
recorded.

WORKING-AGE BASE IS 16+, not 15+. Mauritius is one of four countries here that
does not use 15+, so the base travels on every row.

CROSS-CHECK (2026 Q1, both sexes): population 16+ 990.8; in employment 553.7;
unemployed 33.3; labour force 587.0; outside labour force 403.8; unemployment
rate 5.7; activity rate 59.2; employment rate 94.3. Youth 16-24 unemployment
19.1. Male unemployment 14.3 thousand against female 19.0.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_SERIES = "MU_CMPHS"
_BASE = "16+"
_SURVEY = "Continuous Multi Purpose Household Survey (CMPHS)"

# Column positions in Table 1, left to right, as printed.
_T1 = {
    2: ("working_age_population", "count"),
    7: ("employed", "count"),
    8: ("unemployed", "count"),
    9: ("labour_force", "count"),
    10: ("outside_labour_force", "count"),
}

# Row labels in Table 2 -> (topic, measure, definition).
_T2_ROWS = {
    "in employment": ("employed", "count", "not_applicable"),
    "unemployed": ("unemployed", "count", "not_applicable"),
    "labour force": ("labour_force", "count", "not_applicable"),
    "population outside labour force": ("outside_labour_force", "count",
                                        "not_applicable"),
    "total population": ("working_age_population", "count", "not_applicable"),
    "employment rate (%)": ("employment_to_population_ratio", "rate",
                            "not_applicable"),
    "unemployment rate (%)": ("unemployment_rate", "rate", "strict"),
    "activity rate (%)": ("labour_force_participation_rate", "rate", "strict"),
}

_SEX = {"both sexes": "total", "male": "male", "female": "female"}
_PERIOD = re.compile(r"^(20\d{2})\s*Q([1-4])$")
# Table 2's age header, as printed: a total column then five bands.
_T2_AGES = ["Total", "16-24", "25-29", "30-39", "40-49", "50+"]


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return C.to_number(v)


def _row(**kw) -> dict:
    kw.setdefault("survey", _SURVEY)
    kw.setdefault("working_age_base", _BASE)
    kw.setdefault("series_code", _SERIES)
    kw.setdefault("frequency", "quarterly")
    kw.setdefault("geography", "Total country")
    kw.setdefault("locality", "all")
    kw.setdefault("locality_label", "Total")
    kw.setdefault("education", "Total")
    kw.setdefault("age_group", "Total")
    kw.setdefault("definition", "not_applicable")
    return kw


def _table1(path: str) -> list[dict]:
    d = pd.read_excel(path, sheet_name="Table 1", header=None)
    out, sex = [], None
    for _, r in d.iterrows():
        label = str(r.iloc[0]).strip()
        if label.lower() in _SEX:
            sex = _SEX[label.lower()]
            continue
        m = _PERIOD.match(label)
        if not (m and sex):
            continue
        period = f"{m.group(1)}-Q{m.group(2)}"
        for col, (topic, measure) in _T1.items():
            v = _num(r.iloc[col]) if col < len(r) else None
            if v is None:
                continue
            out.append(_row(topic=topic, measure=measure, value=v,
                            unit="thousand_persons", sex=sex, period=period,
                            reference_period=f"{m.group(1)} Q{m.group(2)}",
                            series_label=topic.replace("_", " ").title()))
    return out


def _table2(path: str) -> list[dict]:
    d = pd.read_excel(path, sheet_name="Table 2", header=None)
    # The quarter is in the sheet's own caption, e.g.
    # "Table 2: Labour force characteristics by age and sex, 1st Quarter 2026".
    caption = " ".join(str(v) for v in d.iloc[:3, 0].tolist())
    m = re.search(r"(\d)(?:st|nd|rd|th)\s+Quarter\s+(20\d{2})", caption, re.I)
    if not m:
        raise ValueError(
            "Mauritius Table 2: no quarter in the sheet caption -- refusing to "
            "date it from the filename, which is the RELEASE date, not the "
            f"reference quarter. Caption was {caption[:120]!r}")
    period = f"{m.group(2)}-Q{m.group(1)}"
    reference = f"{m.group(2)} Q{m.group(1)}"

    out, sex = [], None
    for _, r in d.iterrows():
        label = str(r.iloc[0]).strip()
        if label.lower() in _SEX:
            sex = _SEX[label.lower()]
            continue
        spec = _T2_ROWS.get(label.lower())
        if not (spec and sex):
            continue
        topic, measure, definition = spec
        unit = "percent" if measure == "rate" else "thousand_persons"
        for i, age in enumerate(_T2_AGES):
            v = _num(r.iloc[i + 1]) if i + 1 < len(r) else None
            if v is None:
                continue
            out.append(_row(topic=topic, measure=measure, value=v, unit=unit,
                            definition=definition, sex=sex, age_group=age,
                            period=period, reference_period=reference,
                            series_label=label))
    return out


def parse(path: str) -> pd.DataFrame:
    rows = _table1(path) + _table2(path)
    if not rows:
        raise ValueError(
            f"{path}: neither Table 1 nor Table 2 yielded a row. Statistics "
            f"Mauritius publishes periods DOWN column A and indicators across; "
            f"if that has changed, fix it here rather than loosening the match.")
    df = pd.DataFrame(rows)
    got = set(df["topic"])
    for need in ("unemployment_rate", "unemployed", "labour_force"):
        if need not in got:
            raise ValueError(
                f"{path}: {need!r} missing -- the workbook's row labels have "
                f"changed. Read the sheet before editing the map.")
    # Tables 1 and 2 BOTH carry the current quarter's counts -- identical
    # values under different printed labels ("Employed" / "In employment").
    # Deduping on the row's identity rather than on its label keeps one of
    # each, so a filter on topic+period+sex+age returns a single figure.
    return df.drop_duplicates(
        ["topic", "definition", "sex", "age_group", "period", "measure"])
