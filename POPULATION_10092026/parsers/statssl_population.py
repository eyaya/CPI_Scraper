"""Stats SL Sierra Leone — 2015 census national population by sex (Tier-2 docx).

Parser for the Word document "Sierra Leone 2015 population census data for 16
districts / 5 regions". Its tables list chiefdom populations (REGION | DISTRICT |
CHIEFDOM | MALE | FEMALE | TOTAL) but the chiefdom coverage is incomplete and the
region subtotals mix old (4-region) and new (5-region incl. North-West) boundaries,
so the sub-national detail does NOT reconcile to the national total. We therefore
emit only the authoritative national row ("SIERRA LEONE" = 7,092,113), which is the
published 2015 PHC total. Sub-national/age detail is left out (not reconciled).
"""
from __future__ import annotations
import re
from docx import Document
import pandas as pd


def _num(cell):
    s = re.sub(r"[^\d]", "", str(cell))
    return int(s) if s else None


def parse(local_path: str) -> pd.DataFrame:
    doc = Document(local_path)
    national = None
    for tbl in doc.tables:
        for r in tbl.rows:
            cells = [c.text.strip() for c in r.cells]
            if len(cells) < 6:
                continue
            if cells[2].strip().upper() != "SIERRA LEONE":
                continue
            male, female, total = _num(cells[3]), _num(cells[4]), _num(cells[5])
            if None in (male, female, total) or abs(male + female - total) > 5:
                continue
            national = (male, female, total)
            break
        if national:
            break

    if national is None:
        raise ValueError("statssl_population: national 'SIERRA LEONE' row not found")

    out = []
    for sex, v in (("male", national[0]), ("female", national[1]), ("total", national[2])):
        out.append({
            "series_type": "census", "sex": sex, "age_group": "Total",
            "geography": "Total country", "period": "2015", "frequency": "annual",
            "measure": "count", "value": float(v), "unit": "persons",
            "series_code": "SL_PHC2015",
        })
    return pd.DataFrame(out)
