"""INS Niger RGPH 2012 census — national population by age & sex (Tier-3 PDF).

Parser for the "Etat et structure de la population" report, Annexe Tableau A1
(population by five-year age group and sex, by residence). Each row lists nine
integers — Urbain (M, F, T), Rural (M, F, T), Total (M, F, T); we take the last
triple (the national Total by sex). Numbers are plain space-separated integers
(no thousands grouping), so text extraction is used directly.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_AGE_RE = re.compile(
    r"^(\d{1,2}\s*-\s*\d{1,2}\s*ans|\d{1,2}\s*ans\s*et\s*plus|Total)\s+(.+)$", re.I)


def _norm_age(label: str) -> str:
    label = label.strip()
    if label.lower() == "total":
        return "Total"
    m = re.match(r"(\d{1,2})\s*ans\s*et\s*plus", label, re.I)
    if m:
        return f"{m.group(1)}+"
    m = re.match(r"(\d{1,2})\s*-\s*(\d{1,2})", label)
    return f"{m.group(1)}-{m.group(2)}" if m else label


def parse(local_path: str) -> pd.DataFrame:
    out = []
    started = False
    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if "Tableau A1" not in t and not started:
                continue
            for ln in t.splitlines():
                m = _AGE_RE.match(ln)
                if not m:
                    continue
                nums = re.findall(r"\d+", m.group(2))
                if len(nums) < 9:                 # need Urbain/Rural/Total x M/F/T
                    continue
                male, female, total = int(nums[6]), int(nums[7]), int(nums[8])
                if abs(male + female - total) > 5:
                    continue
                age = _norm_age(m.group(1))
                for sex, v in (("male", male), ("female", female), ("total", total)):
                    out.append({
                        "series_type": "census", "sex": sex, "age_group": age,
                        "geography": "Total country", "period": "2012",
                        "frequency": "annual", "measure": "count", "value": float(v),
                        "unit": "persons", "series_code": "NE_RGPH2012_A1",
                    })
                started = True
                if age == "Total":
                    return pd.DataFrame(out)
    df = pd.DataFrame(out)
    if df.empty or not started:
        raise ValueError("niger_ins_population: Tableau A1 not found")
    return df
