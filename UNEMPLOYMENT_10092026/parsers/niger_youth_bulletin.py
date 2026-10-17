"""Niger -- ERI-ESI 2017 report PLUS INS Niger's quarterly youth bulletin.

The primary (ERI-ESI 2017 final report) is read by `niger_pdf`. Since 2025
INS Niger publishes a quarterly "Bulletin national de suivi de l'emploi et du
chômage des jeunes" (Division de la Conjoncture), from a telephone panel of
4 800 young people aged 15-35. Its Annexe 1 prints nine tables, each with
the CURRENT AND PREVIOUS quarters as rows:

    Trimestre | Agadez Diffa Dosso Maradi Niamey Tahoua Tillabéri Zinder
              | National | Homme Femme | National
    2T 2025   | 43,2 ...                                          | 34,5
    3T 2025   | ...
    4T 2025   | ...

The first block is the eight regions and the national figure (both sexes);
the second is national by sex, repeating the national figure -- which must
equal the first block's, and is checked. Read here (topic mapping):

    1  taux d'emploi (REPOP)              employment_to_population_ratio
    3  taux d'emploi informel (TINF)      informal_employment_share
    5  sous-emploi lié au temps (SEMP)    underemployment_rate
    6  SU2 (sous-emploi + chômage)        labour_underutilisation_rate, broad
    7  chômage au sens du BIT (TCHO)      youth_unemployment_rate, strict
    8  chômage élargi (TCHOE)             youth_unemployment_rate, broad
    9  NEET                               neet_rate

NOT READ: Tableau 2 (vulnerable employment) and 4 (multiple job-holding),
which no topic here covers.

THIS IS NOT THE ERI-ESI SERIES. Different population (15-35 only, recorded
in `age_group` and `working_age_base`), different mode (telephone panel),
different survey name. It is filed beside the 2017 figures, never chained to
them.

ONE BULLETIN CARRIES THE WHOLE SERIES: the newest issue prints every quarter
since the panel started (the 4th-quarter 2025 issue: 2T-4T 2025), so only
the newest is listed; a later issue that revises a quarter replaces it on
merge.
"""
from __future__ import annotations

import re

import pandas as pd

from . import niger_unemployment

_SURVEY = "Bulletin national de suivi de l'emploi et du chômage des jeunes (INS Niger, panel téléphonique)"
_REGIONS = ["Agadez", "Diffa", "Dosso", "Maradi", "Niamey", "Tahoua", "Tillabéri", "Zinder"]
_TABLES = {
    1: ("employment_to_population_ratio", "not_applicable", "Taux d'emploi (REPOP)"),
    3: ("informal_employment_share", "not_applicable", "Taux d'emploi informel (TINF)"),
    5: ("underemployment_rate", "not_applicable", "Taux de sous-emploi lié au temps de travail (SEMP)"),
    6: ("labour_underutilisation_rate", "broad", "Taux combiné sous-emploi + chômage (SU2)"),
    7: ("youth_unemployment_rate", "strict", "Taux de chômage au sens du BIT (TCHO)"),
    8: ("youth_unemployment_rate", "broad", "Taux de chômage élargi (TCHOE)"),
    9: ("neet_rate", "not_applicable", "Jeunes ni en emploi ni en éducation (NEET)"),
}
_ROW = re.compile(r"^([1-4])T\s*(20\d{2})$")


def _tokens(path: str) -> list[str]:
    import fitz
    out = []
    for p in fitz.open(path):
        out += [t.strip() for t in p.get_text().splitlines() if t.strip()]
    return out


def _bulletin(path: str) -> pd.DataFrame:
    tok = _tokens(path)
    annex = next((i for i, t in enumerate(tok) if t.startswith("Annexe 1")), None)
    if annex is None:
        raise ValueError(f"{path}: no 'Annexe 1' tables")
    starts = {}
    for i, t in enumerate(tok[annex:], start=annex):
        m = re.match(r"^Tableau\s*:\s*(\d)\s*\.", t)
        if m:
            starts.setdefault(int(m.group(1)), i)
    rows = []
    for no, (topic, definition, label) in _TABLES.items():
        if no not in starts:
            raise ValueError(f"{path}: Annexe table {no} not found")
        i = starts[no]
        hdr = tok.index("Trimestre", i)
        cols = tok[hdr + 1: hdr + 13]
        if cols[:8] != _REGIONS or cols[8:] != ["National", "Homme", "Femme", "National"]:
            raise ValueError(f"{path}: table {no} header changed: {cols}")
        j = hdr + 13
        nrows = 0
        while j < len(tok) and _ROW.match(tok[j]):
            q, y = _ROW.match(tok[j]).groups()
            vals = [float(v.replace(",", ".")) for v in tok[j + 1: j + 13]]
            if len(vals) != 12:
                raise ValueError(f"{path}: table {no} row {tok[j]} is short")
            if vals[8] != vals[11]:
                raise ValueError(f"{path}: table {no} {tok[j]}: the two national "
                                 f"columns differ ({vals[8]} vs {vals[11]})")
            period = f"{y}-Q{q}"
            cells = [(g, "total", v) for g, v in zip(_REGIONS, vals[:8])]
            cells += [("Total country", "total", vals[8]),
                      ("Total country", "male", vals[9]),
                      ("Total country", "female", vals[10])]
            for geo, sex, v in cells:
                rows.append({
                    "survey": _SURVEY, "topic": topic, "definition": definition,
                    "series_label": label, "sex": sex, "age_group": "15-35",
                    "education": "Total", "geography": geo, "locality": "all",
                    "locality_label": "Total", "working_age_base": "15-35",
                    "period": period, "reference_period": f"{q}T {y}",
                    "frequency": "quarterly", "measure": "rate", "value": v,
                    "unit": "percent", "series_code": f"INS Niger bulletin jeunes T{no}",
                })
            nrows += 1
            j += 13
        if nrows == 0:
            raise ValueError(f"{path}: table {no} has no quarter rows")
    return pd.DataFrame(rows)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = [niger_unemployment.parse(path)]
    frames += [_bulletin(p) for p in extras or []]
    return pd.concat(frames, ignore_index=True)
