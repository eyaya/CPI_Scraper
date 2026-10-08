"""Burundi — INSBU Annuaire statistique du Burundi, chapter VI "Emploi",
Tableau 6.01 "Population active occupée selon le statut dans l'emploi".

ONE TABLE, FOUR HOUSEHOLD-SURVEY ROUNDS. The yearbook reprints the employed
population by status in employment from INSBU's household living-conditions
surveys -- the source line names ECVMB 2013-2014, ERCVMB 2017 and EICVMB
2019-2020 -- as counts under the year INSBU heads each column with (2010,
2013, 2017, 2020). Each column is dated by that header and each carries its
own survey in `survey`; they are four separate surveys, NOT a chained series.
The swings between them (aides familiaux 236 101 in 2010, 1 537 917 in 2013)
are what different instruments measure, and should be read as such.

THE 2010 COLUMN'S SOURCE IS NOT STATED -- the source line lists three surveys
for four columns. It is collected, since INSBU publishes it, under a survey
name that says exactly that rather than a guessed one.

EVERYTHING ELSE IN THE CHAPTER IS ADMINISTRATIVE, and excluded: Tableaux
6.02-6.04 count employers and enterprises registered with the INSS (social
security) and 6.05-6.08 civil-service staff -- establishment/payroll records,
the Kenya trap.

WHY PyMuPDF. The counts use SPACE thousands separators, so pdfplumber's line
"Salariés 188 097 481 672 631 986 717 117" reads more than one way (the Algeria
trap). PyMuPDF returns one cell per line ("188 097" / "481 672" / ...), so
each value is read whole; the reading is then held to the table's own
arithmetic: the five statuses must sum to the printed TOTAL of their column
(to within 1 -- 2017 and 2020 are one person off, a rounding residue kept as
published).

ONLY THE CURRENT EDITION IS READ. Earlier editions add no rounds, and the 2018
edition misprints the table (eight year headers 2010-2017 over seven values,
so its 2017 figures sit under "2016").

Categories are INSBU's (no ICSE named) -> National. Working-age base not stated
anywhere in the chapter -> "not stated", as for Algeria.

CROSS-CHECK: salariés 717 117 (2020); indépendants 2 349 758 (2020); total
4 883 049 (2020), 3 165 560 (2010).
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd

from . import _common as C

_CAPTION = re.compile(r"Tableau 6\.\s*01\.\s*Population active occup.e selon le "
                      r"statut dans l.emploi")
_COUNT = re.compile(r"^\d{1,3}(?: \d{3})*$")
# column header -> (what the source line must still name, survey)
_SURVEYS = {
    "2013": ("ECVMB 2013", "Enquête sur les Conditions de Vie des Ménages au "
                           "Burundi (ECVMB) 2013-2014"),
    "2017": ("ERCVMB 2017", "Enquête sur les Conditions de Vie des Ménages au "
                            "Burundi, round 2017 (ERCVMB 2017)"),
    "2020": ("EICVMB 2019", "Enquête Intégrée sur les Conditions de Vie des "
                            "Ménages au Burundi (EICVMB) 2019-2020"),
}
_UNSTATED = "INSBU household survey, source not stated in the yearbook"


def _table_lines(path: str) -> list[str]:
    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text()
            for m in _CAPTION.finditer(text):
                body = text[m.end():]
                # The list of tables carries the caption too, followed by a
                # page number instead of the header.
                if re.match(r"\.?\s*Statut dans l.emploi", body):
                    return [ln.strip() for ln in body.splitlines() if ln.strip()]
    raise ValueError("INSBU Annuaire: Tableau 6.01 not found")


def parse(path: str) -> pd.DataFrame:
    lines = _table_lines(path)
    i = 1                                   # past "Statut dans l'emploi"
    years = []
    while re.fullmatch(r"20\d\d", lines[i]):
        years.append(lines[i])
        i += 1
    if len(years) < 2:
        raise ValueError(f"INSBU 6.01: header years {years}")
    rows = []
    while i < len(lines) and not lines[i].startswith("Source"):
        label = lines[i]
        vals = lines[i + 1:i + 1 + len(years)]
        if not all(_COUNT.match(v) or v == "-" for v in vals):
            raise ValueError(f"INSBU 6.01: {label!r} reads {vals}")
        rows.append((label, [None if v == "-" else float(v.replace(" ", ""))
                             for v in vals]))
        i += 1 + len(years)
    source = lines[i] if i < len(lines) else ""

    labels = [r[0] for r in rows]
    if labels[-1].upper() != "TOTAL" or len(labels) < 5:
        raise ValueError(f"INSBU 6.01: rows {labels}")
    *cats, (_, total) = rows
    for j, y in enumerate(years):
        s = sum(v[j] for _, v in cats if v[j] is not None)
        if total[j] is None or abs(s - total[j]) > 1:
            raise ValueError(f"INSBU 6.01 {y}: statuses sum to {s}, TOTAL "
                             f"{total[j]}")
    for y in years:
        if y in _SURVEYS and _SURVEYS[y][0] not in source:
            raise ValueError(f"INSBU 6.01: source line no longer names the "
                             f"{y} survey: {source!r}")

    out = []
    for label, vals in rows:
        lab = "Total" if label.upper() == "TOTAL" else label
        for y, v in zip(years, vals):
            if v is None:
                continue
            out.append(C.row(topic="employment_status", characteristic=lab,
                             classification="National", value=v,
                             survey=_SURVEYS.get(y, (None, _UNSTATED))[1], period=y,
                             reference_period=f"Annuaire statistique, column {y}",
                             frequency="ad_hoc", measure="count",
                             unit="persons", working_age_base="not stated",
                             series_code="INSBU Annuaire T6.01"))
    return pd.DataFrame(out)
