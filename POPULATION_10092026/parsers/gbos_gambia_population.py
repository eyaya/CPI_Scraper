"""GBoS Gambia 2024 census — national population by age & sex (Tier-3 PDF).

Parser for the 2024 GPHC Preliminary Report, Table 13 ("Population Distribution by
Sex and Age Group"). Each row is: age group, Male count, Male %, Female count,
Female %, Total count, Total %. Counts carry a thousands comma ("167,088") while
percentages carry a decimal point, so the three counts are the comma-grouped /
4+-digit numbers in order (Male, Female, Total). We emit those per age group.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_TITLE = "Population Distribution by Sex and Age Group"
_AGE_RE = re.compile(r"^(T\s*otal|\d{1,2}\s*-\s*\d{1,2}|\d{1,2}\+)\s+(.+)$", re.I)
_COUNT_RE = re.compile(r"\d{1,3}(?:,\d{3})+|\d{4,}")   # comma-grouped or >=4 digits


def parse(local_path: str) -> pd.DataFrame:
    with pdfplumber.open(local_path) as pdf:
        page = next((p for p in pdf.pages if _TITLE in (p.extract_text() or "")), None)
    if page is None:
        raise ValueError("gbos_gambia_population: Table 13 not found")

    out = []
    for ln in (page.extract_text() or "").splitlines():
        m = _AGE_RE.match(ln)
        if not m:
            continue
        counts = [int(x.replace(",", "")) for x in _COUNT_RE.findall(m.group(2))]
        if len(counts) < 3:
            continue
        male, female, total = counts[0], counts[1], counts[2]
        if abs(male + female - total) > 5:
            continue
        label = m.group(1).replace(" ", "")
        age = "Total" if label.lower() == "total" else re.sub(r"\s*-\s*", "-", label)
        for sex, v in (("male", male), ("female", female), ("total", total)):
            out.append({
                "series_type": "census", "sex": sex, "age_group": age,
                "geography": "Total country", "period": "2024",
                "frequency": "annual", "measure": "count", "value": float(v),
                "unit": "persons", "series_code": "GM_GPHC2024_T13",
            })
    df = pd.DataFrame(out)
    if df.empty:
        raise ValueError("gbos_gambia_population: no rows parsed")
    return df.drop_duplicates(["age_group", "sex", "period"])
