"""INS Guinea — population by age group and sex, 2015-2024 (Tier-3 PDF).

Parser for the Annuaire Statistique 2024, Tableau 3.26 ("Evolution de la population
par sexe selon la tranche d'âge"): population by five-year age group and sex, for
each year 2015-2024. The ten year-columns are packed tightly (~44 pt apart) with
French space-grouped numbers, so numbers are reconstructed by BINNING each digit
word into the nearest year column (gap-based merging fails at this spacing).

Rows come in triples per age group: the "X à Y ans" row is the total, followed by
the male and female rows (their labels are garbled in extraction, so they are typed
by position: first sub-row = male, second = female).
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_TITLE = "par sexe selon la tranche"
_YEARS = [(2015, 118), (2016, 163), (2017, 208), (2018, 252), (2019, 295),
          (2020, 339), (2021, 383), (2022, 427), (2023, 470), (2024, 513)]
_LABEL_X = 112          # words left of this x are the row label
_AGE_RE = re.compile(r"(\d{1,2})\s*[aà]\s*(\d{1,2})|(\d{1,2})\s*ans?\s*et\s*plus")


def _row_numbers(digit_words):
    """Bin digit words into year columns by nearest header x, concatenate per bin."""
    bins = {y: [] for y, _ in _YEARS}
    for w in sorted(digit_words, key=lambda x: x["x0"]):
        cx = (w["x0"] + w["x1"]) / 2
        year = min(_YEARS, key=lambda y: abs(y[1] - cx))[0]
        bins[year].append(w["text"])
    return {y: int("".join(v)) for y, v in bins.items() if v}


def _norm_age(label):
    m = _AGE_RE.search(label)
    if not m:
        return None
    if m.group(3):
        return f"{m.group(3)}+"
    return f"{m.group(1)}-{m.group(2)}"


def parse(local_path: str) -> pd.DataFrame:
    with pdfplumber.open(local_path) as pdf:
        page = next((p for p in pdf.pages if _TITLE in (p.extract_text() or "")), None)
        if page is None:
            raise ValueError("guinea_ins_population: Tableau 3.26 not found")
        words = page.extract_words()

    rows = {}
    for w in words:
        rows.setdefault(round(w["top"] / 3.0), []).append(w)

    out = []
    cur_age = None
    sub = 0
    for k in sorted(rows):
        ws = rows[k]
        label = "".join(w["text"] for w in sorted(ws, key=lambda x: x["x0"])
                        if x_left(w) < _LABEL_X)
        nums = _row_numbers([w for w in ws if x_left(w) >= _LABEL_X
                             and re.fullmatch(r"\d+", w["text"])])
        if len(nums) < 5:
            continue
        age = _norm_age(label)
        if age:                              # age-group row = total for both sexes
            cur_age, sub = age, 0
            sex = "total"
        elif cur_age is not None:            # sub-row: 1st = male, 2nd = female
            sex = "male" if sub == 0 else "female"
            sub += 1
        else:
            continue
        for year, val in nums.items():
            out.append({
                "series_type": "estimate", "sex": sex, "age_group": cur_age,
                "geography": "Total country", "period": str(year),
                "frequency": "annual", "measure": "count", "value": float(val),
                "unit": "persons", "series_code": "GN_ANNUAIRE2024_T3.26",
            })
    df = pd.DataFrame(out)
    if df.empty:
        raise ValueError("guinea_ins_population: no rows parsed")
    return df.drop_duplicates(["age_group", "sex", "period"])


def x_left(w):
    return w["x0"]
