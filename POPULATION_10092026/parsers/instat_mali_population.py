"""INSTAT Mali RGPH-5 2022 — population by region and by age group (Tier-3 PDF).

Parser for the census volume 'État et structure de la population', which carries
two tables of the same shape:

    Tableau 2.3  Répartition de la population résidente par région selon le sexe
        Région      Masculin   Féminin   Ensemble  Poids(%)  RM     %Femmes
        Kayes        921 044   919 285  1 840 329     8,2   100,2     50,0

    Tableau 3.1  … par groupes d'âge quinquennaux selon le sexe
        0-4 ans    2 084 863 1 948 632  4 033 495    18,0   107,0     48,3
        …
        Ensemble  11 256 555 11 138 934 22 395 489   100,0   101,1     49,7

so one row reader serves both; the caption decides whether a row's label is a
REGION (its own geography, age 'Total') or an AGE BAND (national). Table 3.1
spans a page break — its first three bands sit under the caption on one page and
the rest continue on the next — so the parser tracks which table it is inside
across pages rather than reading page by page.

The published RM (rapport de masculinité, males per 100 females) is emitted as
the schema's `sex_ratio`; it is taken as the SECOND decimal on the row, and only
when it falls in a plausible 50-200 range, so a mis-read cannot slip in as one.
The other two decimals — demographic weight and % female — are shares of a total
this schema does not model per row, and are dropped.

French space thousands separators mean counts are rebuilt from word x-gaps, and
every row is checked against masculin + féminin = ensemble.
"""
from __future__ import annotations
import re
import pandas as pd
import pdfplumber

_SERIES_CODE = "ML_RGPH5_2022"
_PERIOD = "2022"
_GEOGRAPHY_NATIONAL = "Total country"
_GAP = 8.0
_COL_GAP = 16.0
_TOLERANCE = 5
_RM_RANGE = (50.0, 200.0)

_T_REGION = re.compile(r"Tableau\s*2\.3\s*:", re.I)
_T_AGE = re.compile(r"Tableau\s*3\.1\s*:", re.I)
_OTHER_CAPTION = re.compile(r"(Tableau|Graphique)\s*\d+[.\d]*\s*:", re.I)
_AGE_LABEL = re.compile(r"^(?P<a>\d{1,3})\s*-\s*(?P<b>\d{1,3})\s*ans$"
                        r"|^(?P<c>\d{1,3})\s*ans\s*ou\s*\+$", re.I)
_TOTAL_LABEL = re.compile(r"^(Ensemble|Total|Mali)$", re.I)
_DECIMAL = re.compile(r"\d{1,3},\d")


def _rows(page, y_tol: float = 5.0):
    words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
    bands: list[list] = []
    for w in words:
        if bands and abs(w["top"] - bands[-1][0]) <= y_tol:
            bands[-1][1].append(w)
        else:
            bands.append([w["top"], [w]])
    return [sorted(ws, key=lambda x: x["x0"]) for _, ws in bands]


def _split(words):
    cut = len(words)
    for i in range(1, len(words)):
        if words[i]["x0"] - words[i - 1]["x1"] >= _COL_GAP:
            cut = i
            break
    label = re.sub(r"\s+", " ", " ".join(w["text"] for w in words[:cut])).strip()
    return label, words[cut:]


def _counts(words) -> list[int]:
    """Integers rebuilt from x-gaps; tokens carrying a comma are decimals and
    end the current number, so the percentage columns cannot join a count."""
    out, cur, prev_x1 = [], "", None
    for w in words:
        t = w["text"]
        if not t.isdigit():
            if cur:
                out.append(int(cur))
                cur, prev_x1 = "", None
            continue
        if cur and prev_x1 is not None and (w["x0"] - prev_x1) < _GAP:
            cur += t
        else:
            if cur:
                out.append(int(cur))
            cur = t
        prev_x1 = w["x1"]
    if cur:
        out.append(int(cur))
    return out


def _age_label(label: str) -> str | None:
    m = _AGE_LABEL.match(label)
    if not m:
        return None
    return f"{m.group('c')}+" if m.group("c") else f"{m.group('a')}-{m.group('b')}"


def parse(local_path: str) -> pd.DataFrame:
    records = []
    mode = None                    # 'region' | 'age' | None

    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages:
            for ws in _rows(page):
                line = re.sub(r"\s+", " ", " ".join(w["text"] for w in ws)).strip()

                if _T_REGION.search(line):
                    mode = "region"
                    continue
                if _T_AGE.search(line):
                    mode = "age"
                    continue
                if mode and _OTHER_CAPTION.search(line):
                    mode = None            # a different table/figure begins
                    continue
                if not mode:
                    continue

                label, data = _split(ws)
                if not label:
                    continue
                nums = _counts(data)
                if len(nums) < 3:
                    continue
                male, female, total = nums[0], nums[1], nums[2]
                if total < 1000 or abs(male + female - total) > _TOLERANCE:
                    continue

                is_total = bool(_TOTAL_LABEL.match(label))
                if mode == "age":
                    age = "Total" if is_total else _age_label(label)
                    if not age:
                        continue
                    geography = _GEOGRAPHY_NATIONAL
                else:
                    if not re.match(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '\-]*$", label):
                        continue
                    age = "Total"
                    geography = _GEOGRAPHY_NATIONAL if is_total else label

                for sex, v in (("male", male), ("female", female), ("total", total)):
                    records.append({
                        "series_type": "census", "sex": sex, "age_group": age,
                        "geography": geography, "period": _PERIOD,
                        "frequency": "annual", "measure": "count",
                        "value": float(v), "unit": "persons",
                        "series_code": _SERIES_CODE,
                    })

                # RM is the second decimal on the row (poids, RM, % femmes)
                decs = _DECIMAL.findall(line)
                if len(decs) >= 2:
                    rm = float(decs[1].replace(",", "."))
                    if _RM_RANGE[0] <= rm <= _RM_RANGE[1]:
                        records.append({
                            "series_type": "census", "sex": "total",
                            "age_group": age, "geography": geography,
                            "period": _PERIOD, "frequency": "annual",
                            "measure": "sex_ratio", "value": rm, "unit": "ratio",
                            "series_code": _SERIES_CODE,
                        })

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Mali population: neither Tableau 2.3 nor 3.1 parsed")
    counts = df[df["measure"] == "count"]
    if counts["geography"].nunique() < 10:
        raise ValueError(
            f"Mali population: only {counts['geography'].nunique()} geographies — "
            f"Tableau 2.3 (regions) did not parse")
    if counts["age_group"].nunique() < 10:
        raise ValueError(
            f"Mali population: only {counts['age_group'].nunique()} age bands — "
            f"Tableau 3.1 did not parse")
    return df.drop_duplicates(["geography", "sex", "age_group", "period", "measure"])
