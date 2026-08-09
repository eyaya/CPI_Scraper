"""Parser for the ONS Algeria 'Comptes économiques' national-accounts PDF.

The detailed by-branch tables don't extract cleanly, but the GDP summary page does
via plain text: it gives GDP (PIB) by the expenditure approach ('Produit Intérieur
Brut et ses emplois') and the income approach ('… approche revenu'), annual, at
current prices in millions of dinars, under a '2021 2022 2023 2024' header.

Each data line reads 'label  n1  n2  n3  n4' with French space-grouped integers
('10 658 276' = 10658276); we take the label and the four year values. The income
section repeats the PIB total (same value) — kept as the aggregate. GNI ('Revenu
National Brut') is not GDP and is skipped. Everything as published; nothing derived.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_YEARS_RE = re.compile(r"\b(20\d\d)\b")
_FRINT_RE = re.compile(r"\d{1,3}(?: \d{3})+|\d{4,}")

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _num(tok: str):
    return float(tok.replace(" ", ""))


def parse(pdf_path: str) -> pd.DataFrame:
    rows, approach, years = [], None, None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").split("\n"):
                low = line.lower()
                # section context
                if "produit intérieur brut et ses emplois" in low:
                    approach = "expenditure"
                    continue
                if "approche revenu" in low:
                    approach = "income"
                    continue
                if "revenu national brut" in low:
                    approach = None            # GNI section — not GDP
                    continue
                # year header line
                yrs = _YEARS_RE.findall(line)
                if len(yrs) >= 4 and not _FRINT_RE.search(re.sub(r"20\d\d", "", line)):
                    years = yrs[:4] if len(yrs) == 4 else yrs[-4:]
                    continue
                if approach is None or years is None:
                    continue
                nums = _FRINT_RE.findall(line)
                if len(nums) < 4:
                    continue
                label = re.sub(r"\s+", " ", line[:line.find(nums[0])]).strip(" .:-()")
                if not label or len(label) < 4:
                    continue
                vals = [_num(t) for t in nums[-4:]]
                is_pib = "produit intérieur brut" in low
                for year, v in zip(years, vals):
                    rows.append({
                        "approach": "aggregate" if is_pib else approach,
                        "category": label, "category_group": "", "series_code": "",
                        "geography": "National", "period": year, "frequency": "annual",
                        "price_basis": "current", "seasonal_adjustment": "not_applicable",
                        "measure": "level", "value": v, "unit": "DZD million",
                        "base_period": "",
                    })
    if not rows:
        raise ValueError("no GDP rows parsed from ONS Algeria report")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "measure", "price_basis"])
