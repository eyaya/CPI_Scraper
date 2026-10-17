"""Tunisia -- INS theme pages PLUS INS's 2006-2026 employment workbook.

The descriptor's primary and its HTML extras are INS's server-rendered theme
pages (/statistiques/151-153), read by the `tunisia_html` layout. They show a
rolling window of about eight quarters. The back series comes from the
workbook INS attaches to every quarterly note ("Indicateurs de l'emploi et du
chômage", e.g. /publication/indicateurs-de-lemploi-et-du-chomage-deuxieme-
trimestre-2026):

    Statistiques_Emploi_Tunisie_2006_2026.xlsx

Source line on every sheet: "Institut National de la Statistique (INS),
Enquête Nationale sur la Population et l'Emploi". Read here:

    Tableau 1   population aged 15+ by sex              working_age_population
    Tableau 2   population active by sex                labour_force
    Tableau 3   population active occupée by sex        employed
    Tableau 7   population en chômage by sex            unemployed
    Tableau 8   taux de chômage by sex                  unemployment_rate
    Tableau 9   unemployed higher-education graduates
                by diploma                              unemployed (education)
    Tableau 10  graduate unemployment rate by sex       unemployment_rate
                                                        (education)

NOT READ: Tableau 4 (job creations -- a flow, not a stock or rate) and
Tableaux 5/5.bis/6 (employment by sector and status -- `labour` reads them).

PERIODS AS PRINTED. 2006-2010 are ANNUAL columns ("année 2006"); the
footnote says the annual survey was collected in April-June each year, and
the column header is kept as `reference_period`. From 2011 the columns are
QUARTERS ("Trimestre 2- 2011", sometimes "Trimestrre"). INS publishes no
column for 2011 Q1 and Q3, 2014 Q2 or 2024 Q4; none is filled.

UNITS: thousands ("Unité: le millier") for counts, percent for rates. Cell
values are kept as stored, with binary float noise removed (341.599999 stays;
1778.8250000000003 becomes 1778.825). "-" and blank cells are not published
and are skipped.

THE THEME PAGES WIN WHERE THEY OVERLAP. For a (topic, sex, education) the
workbook supplies only periods the theme pages do not carry, so no quarter is
filed twice under two labels. The workbook's `series_label` is its table
title, never the theme page's.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from .html_layouts import HTML_LAYOUTS
from . import html_wide_series

_html_parse = html_wide_series.make_parser(HTML_LAYOUTS["tunisia"])

_SURVEY = "Enquête Nationale sur la Population et l'Emploi"
_SHEETS = {
    # sheet-name prefix: (table no, topic, definition, measure, unit, by)
    "Evol_Pop_15Plus_Sexe": ("1", "working_age_population", "not_applicable", "count", "thousand_persons", "sex"),
    "Evol_Pop_Active": ("2", "labour_force", "not_applicable", "count", "thousand_persons", "sex"),
    "Evol_Pop_Occ_Sexe": ("3", "employed", "not_applicable", "count", "thousand_persons", "sex"),
    "Evol_Pop_Chomage_Sexe": ("7", "unemployed", "not_applicable", "count", "thousand_persons", "sex"),
    "Taux_Chomage_Sexe": ("8", "unemployment_rate", "strict", "rate", "percent", "sex"),
    "Chom_Dipl_Sup_Diplome": ("9", "unemployed", "not_applicable", "count", "thousand_persons", "diploma"),
    "Taux_Chom_DiplSup_Sexe": ("10", "unemployment_rate", "strict", "rate", "percent", "sex"),
}
_SEX = {"masculin": "male", "féminin": "female", "feminin": "female", "total": "total"}
_GRADUATES = "Diplômés de l'enseignement supérieur"
_ANNUAL = re.compile(r"^\s*(?:année\s*)?((?:19|20)\d{2})(?:\s*année)?\s*$", re.I)
_QUARTER = re.compile(r"^\s*Trimest?r+e\s*([1-4])\s*-\s*((?:19|20)\d{2})\s*$", re.I)


def _clean(v) -> str:
    return re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else ""


def _num(v):
    t = _clean(v).replace(" ", "")
    if not t or t.lower() == "nan" or t in {"-", "–"}:
        return None
    neg = t.endswith("-")
    t = t.rstrip("-").replace(",", ".")
    try:
        x = round(float(t), 9)
    except ValueError:
        return None
    return -x if neg else x


def _period(h: str):
    m = _QUARTER.match(h)
    if m:
        return f"{m.group(2)}-Q{m.group(1)}", "quarterly"
    m = _ANNUAL.match(h)
    if m:
        return m.group(1), "annual"
    return None


def _sheet(xl: pd.ExcelFile, sheet: str, spec) -> list[dict]:
    no, topic, definition, measure, unit, by = spec
    d = xl.parse(sheet, header=None, dtype=str)
    title = _clean(d.iloc[0, 0])
    if not title.lower().startswith(f"tableau {no}"):
        raise ValueError(f"INS workbook {sheet!r}: title {title[:60]!r} is not Tableau {no}")
    label = re.sub(r"^Tableau\s*\d+\s*:\s*", "", title, flags=re.I)
    hdr = next(i for i in range(len(d))
               if sum(_period(_clean(v)) is not None for v in d.iloc[i]) >= 5)
    cols = {j: (_period(_clean(v)), _clean(v)) for j, v in enumerate(d.iloc[hdr])
            if _period(_clean(v))}
    rows = []
    for i in range(hdr + 1, len(d)):
        name = _clean(d.iloc[i, 0])
        if not name or name.startswith(("*", "Source")):
            continue
        if by == "sex":
            sex = _SEX.get(name.lower())
            if sex is None:
                continue
            edu = _GRADUATES if no == "10" else "Total"
        else:
            # Tableau 9 is graduates only, so its "Total" row is the total of
            # unemployed GRADUATES, not of all unemployed (Tableau 7).
            sex, edu = "total", (_GRADUATES if name.lower() == "total" else name)
        for j, ((period, freq), head) in cols.items():
            v = _num(d.iloc[i, j])
            if v is None:
                continue
            rows.append({
                "survey": _SURVEY, "topic": topic, "definition": definition,
                "series_label": label, "sex": sex, "age_group": "Total",
                "education": edu, "geography": "Total country",
                "locality": "all", "locality_label": "Total",
                "working_age_base": "15+", "period": period,
                "reference_period": head, "frequency": freq,
                "measure": measure, "value": v, "unit": unit,
                "series_code": f"INS Emploi 2006-2026 T{no}",
            })
    if not rows:
        raise ValueError(f"INS workbook {sheet!r}: no rows read")
    return rows


def _workbook(path: str) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    rows = []
    for prefix, spec in _SHEETS.items():
        sheet = next((s for s in xl.sheet_names if s.startswith(prefix)), None)
        if sheet is None:
            raise ValueError(f"INS workbook: no sheet starting {prefix!r}")
        rows += _sheet(xl, sheet, spec)
    df = pd.DataFrame(rows)
    dup = df.duplicated(["topic", "sex", "education", "period", "series_code"])
    if dup.any():
        raise ValueError(f"INS workbook: {int(dup.sum())} period column(s) printed twice")
    return df


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    html = [p for p in extras or [] if not p.lower().endswith(".xlsx")]
    books = [p for p in extras or [] if p.lower().endswith(".xlsx")]
    base = _html_parse(path, extras=html)
    frames = [base]
    have = set(zip(base["topic"], base["sex"], base["education"], base["period"].astype(str)))
    for b in books:
        wb = _workbook(b)
        keep = [(t, s, e, p) not in have for t, s, e, p in
                zip(wb["topic"], wb["sex"], wb["education"], wb["period"].astype(str))]
        frames.append(wb[keep])
    return pd.concat(frames, ignore_index=True)
