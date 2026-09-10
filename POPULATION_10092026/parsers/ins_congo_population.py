"""INS Congo RGPH-5 2023 census — resident population by department and sex
(Tier-3 PDF).

Parser for 'Tableau 2 : Répartition de la population par département selon le
sexe' in the RGPH-5 report 'Populations résidentes des localités du Congo':

    Département   Hommes    Femmes    Ensemble   RM
    Kouilou       52 111    45 251     97 362    115,2
    Niari        160 761   174 102    334 863     92,3
    …
    Congo      2 …          …          …           …

giving the twelve departments and the national ('Congo') row. The published sex
ratio (RM — hommes pour 100 femmes) is emitted alongside the counts as the
schema's `sex_ratio` measure.

French numbers use a SPACE thousands separator, so the counts are rebuilt from
word x-gaps rather than by splitting on whitespace: a gap under `_GAP` continues
the current number, a wider one starts the next column. Every row is checked
against hommes + femmes = ensemble, which is what makes a mis-grouped number
impossible to accept.

DELIBERATELY NOT READ: the rest of the report is the same breakdown for every
LOCALITY — district, commune, arrondissement, quartier and village, thousands of
rows per department (Tableaux 4, 6, 8 …). That detail is real and published, but
it is a different granularity from the province/region level this indicator
carries, and each department's table repeats its own total, so taking Tableau 2
alone keeps the output at one consistent level. The locality tables are a
worthwhile later addition if sub-department geography is wanted.
"""
from __future__ import annotations
import re
import pandas as pd
import pdfplumber

_SERIES_CODE = "CG_RGPH5_2023"
_PERIOD = "2023"
_NATIONAL = "congo"
_GEOGRAPHY_NATIONAL = "Total country"
_GAP = 8.0            # pt: gap below this continues one number
_COL_GAP = 18.0       # pt: gap this wide separates the label from the data
_TOLERANCE = 5

_CAPTION = re.compile(
    r"Tableau\s*2\s*:\s*R[ée]partition\s+de\s+la\s+population\s+par\s+"
    r"d[ée]partement\s+selon\s+le\s+sexe", re.I)
_STOP = re.compile(r"Tableau\s*3\s*:", re.I)


def _rows(page):
    bands: dict[int, list] = {}
    for w in page.extract_words():
        bands.setdefault(round(w["top"] / 3.0), []).append(w)
    return [(t, sorted(v, key=lambda x: x["x0"])) for t, v in sorted(bands.items())]


def _split(words):
    """(label, data words), cut at the first wide gap."""
    cut = len(words)
    for i in range(1, len(words)):
        if words[i]["x0"] - words[i - 1]["x1"] >= _COL_GAP:
            cut = i
            break
    label = re.sub(r"\s+", " ", " ".join(w["text"] for w in words[:cut])).strip()
    return label, words[cut:]


def _groups(words) -> list[str]:
    out, cur, prev_x1 = [], "", None
    for w in words:
        t = w["text"]
        if not re.fullmatch(r"[\d,]+", t):
            continue
        if cur and prev_x1 is not None and (w["x0"] - prev_x1) < _GAP:
            cur += t
        else:
            if cur:
                out.append(cur)
            cur = t
        prev_x1 = w["x1"]
    if cur:
        out.append(cur)
    return out


def _int(tok: str):
    return int(tok) if re.fullmatch(r"\d+", tok) else None


def parse(local_path: str) -> pd.DataFrame:
    records = []

    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if not _CAPTION.search(re.sub(r"\s+", " ", text)):
                continue

            started = False
            for _, ws in _rows(page):
                line = " ".join(w["text"] for w in ws)
                if _CAPTION.search(re.sub(r"\s+", " ", line)):
                    started = True
                    continue
                if not started:
                    continue
                if _STOP.search(line):
                    break

                label, data = _split(ws)
                if not label or not re.match(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ '\-]*$", label):
                    continue
                cols = _groups(data)
                if len(cols) < 3:
                    continue
                male, female, total = _int(cols[0]), _int(cols[1]), _int(cols[2])
                if None in (male, female, total):
                    continue
                if abs(male + female - total) > _TOLERANCE:
                    continue

                geography = (_GEOGRAPHY_NATIONAL
                             if label.strip().lower() == _NATIONAL else label.strip())
                for sex, v in (("male", male), ("female", female), ("total", total)):
                    records.append({
                        "series_type": "census", "sex": sex, "age_group": "Total",
                        "geography": geography, "period": _PERIOD,
                        "frequency": "annual", "measure": "count",
                        "value": float(v), "unit": "persons",
                        "series_code": _SERIES_CODE,
                    })
                if len(cols) > 3:
                    try:
                        ratio = float(cols[3].replace(",", "."))
                    except ValueError:
                        ratio = None
                    if ratio is not None:
                        records.append({
                            "series_type": "census", "sex": "total",
                            "age_group": "Total", "geography": geography,
                            "period": _PERIOD, "frequency": "annual",
                            "measure": "sex_ratio", "value": ratio, "unit": "ratio",
                            "series_code": _SERIES_CODE,
                        })
            if records:
                break                       # Tableau 2 sits on a single page

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Congo population: 'Tableau 2' (department x sex) not found")
    if _GEOGRAPHY_NATIONAL not in set(df["geography"]):
        raise ValueError("Congo population: national ('Congo') row not found")
    if df["geography"].nunique() < 12:
        raise ValueError(
            f"Congo population: {df['geography'].nunique()} geographies — expected "
            f"the twelve departments plus the national total")
    return df.drop_duplicates(["geography", "sex", "age_group", "period", "measure"])
