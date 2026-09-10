"""ANSD Senegal RGPH-5 2023 census — national population by age & sex (Tier-3 PDF).

Parser for Chapter 1 ("Etat et structure de la population"), national age-sex table
(Tableau I-14): by five-year age group, Masculin / Féminin / Ensemble counts, then
percentage and sex-ratio columns; it spans two pages ending in a "Total" row.

French numbers use a space thousands separator and pdfplumber emits each triple as
a separate word, so we reconstruct numbers from word x-positions: a small gap
(< 15 pt) is a thousands separator (same number); a large gap starts a new column.
The three count columns come before the comma-decimal percentage columns. Only the
first (national) table is read, stopping at its "Total" row.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_AGE_RE = re.compile(r"^(\d{1,2}-\d{1,2}|\d{1,2}\+|Total)$", re.I)
_GAP = 15          # pt; smaller gap = thousands separator within one number


def _rows_by_line(words):
    rows = {}
    for w in words:
        rows.setdefault(round(w["top"] / 3.0), []).append(w)
    return [sorted(v, key=lambda x: x["x0"]) for _, v in sorted(rows.items())]


def _numbers(ws):
    """Reconstruct integer columns from digit words, merging by x-gap; stop at the
    first comma-decimal (the percentage columns)."""
    nums, cur, prev_x1 = [], "", None
    for w in ws:
        t = w["text"]
        if "," in t or "%" in t:
            break
        if not re.fullmatch(r"\d+", t):
            continue
        if cur and prev_x1 is not None and (w["x0"] - prev_x1) < _GAP:
            cur += t
        else:
            if cur:
                nums.append(int(cur))
            cur = t
        prev_x1 = w["x1"]
    if cur:
        nums.append(int(cur))
    return nums


def parse(local_path: str) -> pd.DataFrame:
    out = []
    started = False
    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages:
            for ws in _rows_by_line(page.extract_words()):
                if not ws:
                    continue
                label = ws[0]["text"].strip()
                if not _AGE_RE.match(label):
                    continue
                nums = _numbers(ws[1:])
                if len(nums) < 3:
                    continue
                male, female, total = nums[0], nums[1], nums[2]
                # M+F should equal the published total (allow ±5 for the source's
                # own rounding); a gross mismatch means a mis-parsed row -> skip.
                if abs(male + female - total) > 5:
                    continue
                age = "Total" if label.lower() == "total" else label
                for sex, v in (("male", male), ("female", female), ("total", total)):
                    out.append({
                        "series_type": "census", "sex": sex, "age_group": age,
                        "geography": "Total country", "period": "2023",
                        "frequency": "annual", "measure": "count", "value": float(v),
                        "unit": "persons", "series_code": "SN_RGPH5_2023",
                    })
                started = True
                if age == "Total":
                    return pd.DataFrame(out)
    df = pd.DataFrame(out)
    if df.empty or not started:
        raise ValueError("ansd_senegal_population: national age-sex table not found")
    return df
