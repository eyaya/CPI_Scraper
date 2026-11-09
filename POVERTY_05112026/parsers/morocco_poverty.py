"""Morocco -- monetary poverty (HCP), from the HCP's own MDG indicator workbook.

hcp.ma's indicator page "Taux de pauvreté monétaire (%)" (Développement
durable > OMD > Indicateurs, /Taux-de-pauvrete-monetaire_a2917.html) links
"Télécharger le fichier de données" to a Google Sheets export -- HCP's own
file, the same arrangement as population/sources/morocco.yaml. Its one
sheet: Année | Rural | Urbain | National for 1985, 2001, 2007, 2014.

WHAT THIS IS AND IS NOT. The workbook names no survey and no line; the years
are the HCP consumption-survey rounds (ENCDM 1984/85, 2000/01, ENNVM 2007,
ENCDM 2013/14), but the survey is NOT invented here -- every row carries the
workbook's own description. Its 2014 figures (national 4,2 / urban 1,1 /
rural 8,9) DIFFER from HCP's ENCDM 2014 note (4,8 / 1,6 / 9,5, prose and chart
only), which uses the 2014 updated line (4 667 DH urban / 4 312 DH rural per
person per year); 2001 and 2007 agree with that note. So the line is named as
the workbook's series, not as the 2014 line.

Not collected: the ENCDM 2014 note's own figures (prose + chart labels only)
and "Evolution du niveau de vie ... COVID-19" (2021; a Word file, prose only;
the 2019 survey switched to consumption units and gave no poverty table).

CROSS-CHECK (verbatim): national 21,0 / 15,3 / 8,9 / 4,2; rural 26,8 / 25,1
/ 14,4 / 8,9; urban 13,3 / 7,6 / 4,8 / 1,1.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_SURVEY = "HCP, série OMD du taux de pauvreté monétaire"
LAYOUT = {
    "survey": _SURVEY, "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté monétaire (série OMD du HCP)",
    "period_patterns": [r"(19\d{2}|20\d{2})"], "tables": [],
}
# The workbook's years are HCP's labels for its consumption-survey rounds
# (docstring); a split-year round is dated by its first year like every
# other row, the workbook's label kept in reference_period.
_ROUND = {"1985": ("1984", "1984/85 (the workbook labels it 1985)"),
          "2001": ("2000", "2000/01 (the workbook labels it 2001)"),
          "2014": ("2013", "2013/14 (the workbook labels it 2014)")}
_COLS = {"Rural": dict(topic="locality", locality="rural", locality_label="Rural",
                       characteristic="Rural"),
         "Urbain": dict(topic="locality", locality="urban", locality_label="Urbain",
                        characteristic="Urbain"),
         "National": {}}


def parse(path: str) -> pd.DataFrame:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    # The sheet whose title cell reads "Taux de pauvreté monétaire(%)".
    ws = next((w for w in wb if any("pauvreté monétaire" in str(v) for r in w.iter_rows(
        max_row=5, values_only=True) for v in r if v)), None)
    if ws is None:
        raise ValueError(f"no 'Taux de pauvreté monétaire' sheet in {path}: {wb.sheetnames}")
    rows = [r for r in ws.iter_rows(values_only=True)]
    hdr = next(i for i, r in enumerate(rows) if "Année" in [str(x).strip() for x in r if x is not None])
    cols = {str(v).strip(): j for j, v in enumerate(rows[hdr]) if v is not None}
    if set(_COLS) - set(cols):
        raise ValueError(f"header changed: {rows[hdr]!r}")
    out = []
    for r in rows[hdr + 1:]:
        year = str(r[cols["Année"]] or "").strip()
        if not re.fullmatch(r"(19|20)\d{2}", year):
            continue
        for name, attrs in _COLS.items():
            v = r[cols[name]]
            if v is None:
                continue
            out.append(C.row(metric="headcount", value=float(v), survey=_SURVEY,
                             welfare_aggregate="consumption", line_type="national",
                             line_level="overall", line_name=LAYOUT["line_name"],
                             period=_ROUND.get(year, (year, year))[0],
                             reference_period=_ROUND.get(year, (year, year))[1],
                             frequency="ad_hoc", **attrs))
    if len(out) < 12:
        raise ValueError(f"only {len(out)} values read from {path}")
    return pd.DataFrame(out)
