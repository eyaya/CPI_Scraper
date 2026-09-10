"""INSTAT Madagascar RGPH-3 2018 — national population by age & sex (Tier-3 PDF).

Parser for the RGPH-3 Global Results (Tome 1), Tableau 69 ("Répartition de la
population résidente par milieu de résidence et groupe d'âges"). The table gives,
per five-year age group, urban (Masculin/Féminin/Ensemble) then rural
(Masculin/Féminin/Ensemble) counts, each followed by a percentage. The national
figure is urban + rural. French numbers are space-grouped and each count is
followed by a comma-decimal percentage, so counts are recovered by a token walk:
digit tokens accumulate into a count; a comma token ends it (the percentage).
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_AGE_RE = re.compile(r"^(\d{1,2}\s*-\s*\d{1,2})\s*ans|^(Ensemble)", re.I)
# the data page has a "0-4 ans" line carrying the urban+rural counts (>=6 numbers).
_DATA_ROW = re.compile(r"^\s*0\s*-\s*4\s*ans(?:\s+[\d,]+){6,}")


def _counts(tokens):
    """Return the counts on a line: digit tokens accumulate; a comma token
    (a percentage) closes the current count."""
    out, cur = [], ""
    for t in tokens:
        if re.fullmatch(r"\d+", t):
            cur += t
        elif re.fullmatch(r"\d+,\d+", t):      # percentage -> close count
            if cur:
                out.append(int(cur)); cur = ""
        else:
            if cur:
                out.append(int(cur)); cur = ""
    if cur:
        out.append(int(cur))
    return out


def parse(local_path: str) -> pd.DataFrame:
    out = []
    lines = None
    with pdfplumber.open(local_path) as pdf:
        for p in pdf.pages:
            txt = p.extract_text() or ""
            if any(_DATA_ROW.match(ln) for ln in txt.splitlines()):
                lines = txt.splitlines()
                break
    if lines is None:
        raise ValueError("instat_madagascar_population: age-sex data table not found")

    for ln in lines:
        m = _AGE_RE.match(ln.strip())
        if not m:
            continue
        counts = _counts(ln.split()[1:] if not m.group(2) else ln.split()[1:])
        # need urban (M,F,Ens) + rural (M,F,Ens) = 6 counts
        if len(counts) < 6:
            continue
        um, uf, ue, rm, rf, re_ = counts[:6]
        male, female, total = um + rm, uf + rf, ue + re_
        if abs(male + female - total) > 5:
            continue
        if m.group(2):                          # Ensemble row = national total
            age = "Total"
        else:
            age = re.sub(r"\s*-\s*", "-", m.group(1))
        for sex, v in (("male", male), ("female", female), ("total", total)):
            out.append({
                "series_type": "census", "sex": sex, "age_group": age,
                "geography": "Total country", "period": "2018",
                "frequency": "annual", "measure": "count", "value": float(v),
                "unit": "persons", "series_code": "MG_RGPH3_T69",
            })
        if age == "Total":
            break
    df = pd.DataFrame(out)
    if df.empty:
        raise ValueError("instat_madagascar_population: no rows parsed")
    return df
