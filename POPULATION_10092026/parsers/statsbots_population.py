"""Statistics Botswana (Statsbots) — 2022 census population by age & sex (Tier-3 PDF).

Parser for the "Analytical Report Volume 1 - Demographic", Table 5.4 (Population by
Age Group, Citizenship and Sex). Each age row carries four Male/Female pairs —
Batswana, Non-Batswana, Not-Stated and Total — so the last pair is the total by
sex. We emit male, female and total (M+F) per age group for the 2022 census.

    AGE GRP | Bats M | Bats F | NonBats M | NonBats F | NotStated M/F | TOTAL M | TOTAL F
    0-4     | 124,883 123,703 3,833 3,759 981 1,015 | 129,697 128,477
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_TITLE = "Population by Age Group, Citizenship and Sex"
# an age row: a label then exactly eight comma-grouped numbers
_ROW_RE = re.compile(
    r"^\s*(\d{1,2}\s*-\s*\d{1,2}|\d{1,3}\+|Not\s*Stated|TOTAL|All ages)\s+"
    + r"\s+".join([r"([\d,]+)"] * 8) + r"\s*$", re.I)


def _n(x):
    return float(x.replace(",", ""))


def parse(local_path: str) -> pd.DataFrame:
    out = []
    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if _TITLE not in t:
                continue
            for ln in t.splitlines():
                m = _ROW_RE.match(ln)
                if not m:
                    continue
                label = m.group(1).strip()
                total_m, total_f = _n(m.group(8)), _n(m.group(9))
                if label.upper() == "TOTAL" or label.lower() == "all ages":
                    age = "Total"
                elif label.lower().startswith("not"):
                    age = "Not stated"
                else:
                    age = re.sub(r"\s*-\s*", "-", label)
                for sex, v in (("male", total_m), ("female", total_f),
                               ("total", total_m + total_f)):
                    out.append({
                        "series_type": "census", "sex": sex, "age_group": age,
                        "geography": "Total country", "period": "2022",
                        "frequency": "annual", "measure": "count", "value": v,
                        "unit": "persons", "series_code": "BW_PHC2022_T5.4",
                    })
            if out:
                break                       # Table 5.4 is on a single page
    df = pd.DataFrame(out)
    if df.empty:
        raise ValueError("statsbots_population: Table 5.4 not parsed")
    return df.drop_duplicates(["age_group", "sex", "period"])
