"""ICASEES Central African Republic — national population by age & sex (HTML table).

Parser for the ICASEES RGPH-4 web page "Projection de la population de la RCA par
groupe d'age et par sexe" (icasees.org). The page carries one HTML table whose
left column-group (age | Total | M | F) holds two clearly year-labelled blocks:
2023 (first) and 2022 (introduced by a full-row "2022" marker). French thousands
use a non-breaking space (\\xa0). A third, right-hand column-block carries no
assignable year label and is deliberately left out (no guessing).

These are ICASEES's published *projections* (RGPH-4), so series_type = projection.
"""
from __future__ import annotations
import re
import pandas as pd

_AGE_RE = re.compile(r"^\d{1,2}\s*-\s*\d{1,2}$|^\d{1,2}\+$")
_YEAR_RE = re.compile(r"^20[12]\d$")


def _num(cell):
    s = re.sub(r"[^\d]", "", str(cell))
    return int(s) if s else None


def parse(local_path: str) -> pd.DataFrame:
    html = open(local_path, encoding="utf-8", errors="replace").read()
    years_seq = re.findall(r">\s*(20[12]\d)\s*<", html)
    first_year = years_seq[0] if years_seq else "2023"

    tbl = pd.read_html(local_path, header=None)[0]
    out, current = [], first_year
    for i in range(len(tbl)):
        c0 = str(tbl.iloc[i, 0]).strip()
        if _YEAR_RE.match(c0):
            current = c0
            continue
        norm = re.sub(r"\s*-\s*", "-", c0)
        is_total = c0.lower() == "total"
        if not (is_total or _AGE_RE.match(norm)):
            continue
        total, male, female = _num(tbl.iloc[i, 1]), _num(tbl.iloc[i, 2]), _num(tbl.iloc[i, 3])
        if total is None or male is None or female is None:
            continue
        if abs(male + female - total) > 5:
            continue
        age = "Total" if is_total else norm
        for sex, v in (("male", male), ("female", female), ("total", total)):
            out.append({
                "series_type": "projection", "sex": sex, "age_group": age,
                "geography": "Total country", "period": current,
                "frequency": "annual", "measure": "count", "value": float(v),
                "unit": "persons", "series_code": "CF_ICASEES_RGPH4_PROJ",
            })

    df = pd.DataFrame(out)
    if df.empty:
        raise ValueError("icasees_car_population: no rows parsed")
    return df
