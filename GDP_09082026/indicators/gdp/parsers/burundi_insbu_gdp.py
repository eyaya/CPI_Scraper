"""Parser for the INSBU Burundi quarterly national-accounts note (CNT PDF, French).

The note publishes the quarterly PIB (production approach) by branch of activity,
at current prices and in chained volumes (reference year 2005, SCN 1993). The
annex tables (p12-19) have no ruling lines and wrap the branch labels across the
line above/below their row of eight quarterly figures, so pdfplumber's default
table extractor fails. We use its TEXT-based table strategy, which yields a grid
where each value row carries its eight figures and the wrapped label appears as
separate text rows immediately above/below it:

    'Secteur primaire' | 4,7 | 1,5 | …          (label inline)
    'Agriculture'      |     |     |             (label part 1)
                       | 8,6 | 8,8 | …           (values, empty label)
    "d'exportation"    |     |     |             (label part 2)

So a value row with a non-empty first cell keeps that label; a value row with an
empty first cell is 'sandwiched' and takes the nearest non-empty text cell above
plus the one below (skipping blank separators). Captions ('Tableau N: …') are read
from the same grid (words are split across cells, so keywords are matched on the
space-stripped caption), so tables that share a page are handled.

We capture the two tables that parse COMPLETELY and reconcile at the PIB row:
T5 taux de croissance reel (real growth %, all 21 branches, PIB row = the headline
growth) and T4 structure du PIB aux prix courants (shares %, hierarchical:
sector + sub-branch, so they do not sum to 100). The level tables (T2 volumes /
T3 courant) come out of this wrapped PDF only partially and are DEFERRED, along
with the contribution, nominal-growth and deflator tables. Periods are the 8
quarters from the 'Activité T2-2024 … T1-2026' header. Verified: PIB real growth
2026-Q1 = 3.4% (2024Q2-2026Q1 range 3.1-5.2%), PIB share = 100. Labels are
best-effort: ~18 of 21 branch names reconstruct cleanly; a few multi-line labels
(Transports, SIFIM, public administration) remain partial but their VALUES are
correct. Nothing derived.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]

_PERIOD_RE = re.compile(r"T([1-4])[-\s]?(20\d\d)")
_NUM_RE = re.compile(r"^\(?-?\s?\d[\d ]*(?:,\d+)?\)?$")
_TS = {"vertical_strategy": "text", "horizontal_strategy": "text",
       "min_words_vertical": 3, "min_words_horizontal": 1}


def _spec(caption: str):
    # We capture the two tables that parse completely and reconcile at the PIB row:
    # the real growth rates and the current-price structure (shares). The level
    # tables (T2/T3) come out only partially from this wrapped PDF and, with the
    # contribution/nominal/deflator tables, are deferred.
    c = caption.lower().replace(" ", "")            # cells split words: 'cou rant' -> 'courant'
    if "structure" in c:
        return ("share", "current", "", "percent")
    if "croissance" in c:
        return None if "nominal" in c else ("growth_yoy", "constant", "2005", "percent")
    return None                                     # levels / contribution / deflateur / agregats


def _num(cell):
    if not cell or not _NUM_RE.match(cell.strip()):
        return None
    s = cell.strip()
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(" ", "").replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _is_aggregate(label):
    low = label.lower()
    return low == "pib" or "produit int" in low or low.startswith("va ") \
        or "valeur ajout" in low or low.startswith("imp") or "taxes net" in low


def parse(pdf_path: str) -> pd.DataFrame:
    rows = []
    periods = []
    with pdfplumber.open(pdf_path) as pdf:
        # the quarter columns are the same across the note; read them once
        for page in pdf.pages:
            hrow = next((l for l in (page.extract_text() or "").split("\n")
                         if len(_PERIOD_RE.findall(l)) >= 5), "")
            if hrow:
                periods = [f"{m.group(2)}-Q{m.group(1)}" for m in _PERIOD_RE.finditer(hrow)]
                break
        if len(periods) < 5:
            raise ValueError("no quarter header found in INSBU note")
        np = len(periods)

        for page in pdf.pages:
            if not re.search(r"tableau\s*\d", page.extract_text() or "", re.I):
                continue
            for table in page.extract_tables(_TS):
                grid = [[(c or "").strip() for c in row] for row in table]
                spec = None
                for i, row in enumerate(grid):
                    joined = " ".join(row)
                    if re.search(r"ableau\s*\d", joined, re.I):
                        spec = _spec(joined)
                        continue
                    if spec is None:
                        continue
                    nums = [_num(c) for c in row[1:]]
                    nums = [x for x in nums if x is not None]
                    if len(nums) < np - 1:
                        continue
                    # label: inline first cell, else the sandwich (row above + below)
                    label = row[0].strip()
                    if not re.search(r"[A-Za-z]", label):
                        # sandwiched label: nearest non-empty text cell above + below,
                        # skipping blank separator rows and other value rows
                        def _txt(rng):
                            for j in rng:
                                if 0 <= j < len(grid):
                                    t = grid[j][0].strip()
                                    if re.search(r"[A-Za-z]", t):
                                        # not itself a value row's stray label
                                        if sum(1 for c in grid[j][1:] if _num(c) is not None) < 3:
                                            return t
                            return ""
                        label = " ".join(x for x in (_txt((i - 1, i - 2)),
                                                     _txt((i + 1, i + 2))) if x)
                    label = re.sub(r"\s+", " ", label).strip()
                    if not label or "activit" in label.lower():
                        continue
                    measure, basis, base, unit = spec
                    approach = "aggregate" if _is_aggregate(label) else "production"
                    for period, v in zip(periods, nums[:np]):
                        rows.append({
                            "approach": approach, "category": label,
                            "category_group": "", "series_code": "",
                            "geography": "National", "period": period,
                            "frequency": "quarterly", "price_basis": basis,
                            "seasonal_adjustment": "nsa", "measure": measure,
                            "value": v, "unit": unit, "base_period": base,
                        })
    if not rows:
        raise ValueError("no GDP rows parsed from INSBU Burundi note")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "measure", "price_basis"])
