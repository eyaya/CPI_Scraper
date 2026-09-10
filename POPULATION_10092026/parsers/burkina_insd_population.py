"""INSD Burkina Faso RGPH-5 2019 — national population by age & sex (Tier-3 PDF).

Parser for the "Rapport des resultats definitifs" synthesis, Tableau 5
("Repartition de la population residente par groupe d'ages quinquennaux selon le
sexe et rapport de masculinite"). The table is fully ruled, so pdfplumber's
lines strategy recovers clean columns: age group | Masculin | Feminin |
Ensemble (Effectif) | Proportion (%) | Rapport de masculinite. French numbers are
space-grouped; spaces are stripped. The national total row is labelled "Total".
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_AGE_RE = re.compile(r"^\d{1,2}\s*-\s*\d{1,2}$|^\d{1,2}\+$")
_TABLE_SETTINGS = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}


def _num(cell):
    """Strip French thousands spaces -> int, or None if not a count."""
    if cell is None:
        return None
    s = re.sub(r"\s+", "", str(cell))
    return int(s) if re.fullmatch(r"\d+", s) else None


def parse(local_path: str) -> pd.DataFrame:
    rows = None
    with pdfplumber.open(local_path) as pdf:
        for p in pdf.pages:
            tbl = p.extract_table(_TABLE_SETTINGS)
            if not tbl:
                continue
            labels = [(r[0] or "").strip() for r in tbl]
            has_ages = any(_AGE_RE.match(re.sub(r"\s*-\s*", "-", l)) for l in labels)
            if has_ages and any(l.lower() == "total" for l in labels):
                rows = tbl
                break
    if rows is None:
        raise ValueError("burkina_insd_population: Tableau 5 age-sex table not found")

    out = []
    for r in rows:
        label = (r[0] or "").strip()
        norm = re.sub(r"\s*-\s*", "-", label)
        is_total = label.lower() == "total"
        if not (is_total or _AGE_RE.match(norm)):
            continue
        male, female, total = _num(r[1]), _num(r[2]), _num(r[3])
        if male is None or female is None or total is None:
            continue
        if abs(male + female - total) > 5:
            continue
        age = "Total" if is_total else norm
        for sex, v in (("male", male), ("female", female), ("total", total)):
            out.append({
                "series_type": "census", "sex": sex, "age_group": age,
                "geography": "Total country", "period": "2019",
                "frequency": "annual", "measure": "count", "value": float(v),
                "unit": "persons", "series_code": "BF_RGPH5_T5",
            })

    df = pd.DataFrame(out)
    if df.empty:
        raise ValueError("burkina_insd_population: no rows parsed")
    return df
