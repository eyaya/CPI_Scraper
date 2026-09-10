"""DGS Gabon — EGEP II 2017 survey, population by age group and sex (Tier-3 PDF).

Parser for the synthesis report of the 'Enquête Gabonaise pour le Suivi et
l'Evaluation de la Pauvreté de 2017' (EGEP II 2017), whose Tableau 3 gives the
national population by five-year age band and sex:

    Groupe d'âges   Masculin   Féminin    Total    <percentages…>
    0 - 4            148 983    153 259   302 242  15,614,915,315,397
    …
    80 et +            5 408     11 013    16 421
    Total            952 974  1 028 605 1 981 579

`series_type` is 'estimate', NOT 'census': EGEP II is a household SAMPLE survey
(666 clusters drawn from the RGPL-2013 frame, with its population reweighted and
projected forward from that census), so the counts are survey estimates for 2017
rather than an enumeration.

The table is a spreadsheet pasted into the page with per-glyph letter spacing.
`extract_words()` mangles it — age labels break apart ('10 - 14' loses its leading
digit to a separate glyph column) and adjacent columns fuse — so the parser works
from the raw CHAR stream instead: characters ordered by x reconstruct the line
exactly, and digit characters group into numbers by x-delta (~4 pt between digits
of one number, ~6 pt across a French thousands space, ~25 pt across a column).

Which groups are the counts still varies by row — an age row begins with the two
digits of its band, '80 et +' with one, the Total row with none — so rather than
trusting a position we search for the first triple satisfying the table's own
identity, masculin + féminin = total. The trailing percentage columns cannot be
mistaken for counts because they do not satisfy it.

Tableau 4's national rows also give the published mean and median age by sex; the
median is emitted as the schema's `median_age` measure. Its mean age has no
schema measure and is dropped, as are that table's residence and region blocks,
whose rows are survey strata ('Ouest rural', 'Est') rather than administrative
units.
"""
from __future__ import annotations
import re
import pandas as pd
import pdfplumber

_SERIES_CODE = "GA_EGEP2_2017"
_PERIOD = "2017"
_GEOGRAPHY_NATIONAL = "Total country"
_GAP = 12.0            # pt: below this, a gap is a thousands separator
_COL_GAP = 20.0        # pt: at least this wide separates the label from the data
_TOLERANCE = 5

_T3 = re.compile(r"Tableau\s*3\s*:\s*R[ée]partition\s+de\s+la\s+population\s+par\s+"
                 r"groupes?\s+d[’']?\s*[âa]ges?\s+selon\s+le\s+sexe", re.I)
_T4 = re.compile(r"Tableau\s*4\s*:\s*[ÂA]ges?\s+moyen\s+et\s+m[ée]dian", re.I)
_AGE = re.compile(r"^(?P<a>\d{1,3})\s*-\s*(?P<b>\d{1,3})$|^(?P<c>\d{1,3})\s*et\s*\+$"
                  r"|^(?P<t>Total)$", re.I)
_SEX_ROW = re.compile(r"^(?P<sex>Masculin|F[ée]minin|Total)\s+"
                      r"(?P<mean>\d{1,3},\d)\s+(?P<median>\d{1,3},\d)\b", re.I)
_SEXES = {"masculin": "male", "feminin": "female", "féminin": "female",
          "total": "total"}


def _rows(page, y_tol: float = 6.0):
    words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
    bands: list[list] = []
    for w in words:
        if bands and abs(w["top"] - bands[-1][0]) <= y_tol:
            bands[-1][1].append(w)
        else:
            bands.append([w["top"], [w]])
    return [sorted(ws, key=lambda x: x["x0"]) for _, ws in bands]


def _char_bands(page, y_tol: float = 3.0):
    """Page characters grouped into visual rows, each ordered left to right."""
    bands: dict[int, list] = {}
    for c in page.chars:
        bands.setdefault(round(c["top"] / y_tol), []).append(c)
    return [sorted(v, key=lambda c: c["x0"]) for _, v in sorted(bands.items())]


def _line(chars) -> str:
    return "".join(c["text"] for c in chars)


def _digit_groups(chars) -> list[int]:
    """Numbers rebuilt from digit-character x-deltas (see module docstring)."""
    out, cur, prev_x0 = [], "", None
    for c in chars:
        if not c["text"].isdigit():
            continue
        if cur and prev_x0 is not None and (c["x0"] - prev_x0) < _GAP:
            cur += c["text"]
        else:
            if cur:
                out.append(int(cur))
            cur = c["text"]
        prev_x0 = c["x0"]
    if cur:
        out.append(int(cur))
    return out


def _counts(groups: list[int]):
    """The first (male, female, total) triple satisfying male + female = total.

    The count columns are not at a fixed index: an age row is preceded by the two
    digits of its band, '80 et +' by one, and the Total row by none."""
    for i in range(len(groups) - 2):
        a, b, t = groups[i], groups[i + 1], groups[i + 2]
        if t > 1000 and abs(a + b - t) <= _TOLERANCE:
            return a, b, t
    return None


def _age_label(label: str) -> str | None:
    m = _AGE.match(re.sub(r"\s+", " ", label).strip())
    if not m:
        return None
    if m.group("t"):
        return "Total"
    if m.group("c"):
        return f"{m.group('c')}+"
    return f"{m.group('a')}-{m.group('b')}"


def parse(local_path: str) -> pd.DataFrame:
    records = []
    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages:
            text = re.sub(r"\s+", " ", page.extract_text() or "")

            if _T3.search(text):
                for chars in _char_bands(page):
                    line = _line(chars)
                    # the label is what precedes the first run of spaces
                    label = re.split(r"\s{2,}", line.strip(), maxsplit=1)[0]
                    age = _age_label(label)
                    if not age:
                        continue
                    got = _counts(_digit_groups(chars))
                    if got is None:
                        continue
                    male, female, total = got
                    for sex, v in (("male", male), ("female", female),
                                   ("total", total)):
                        records.append({
                            "series_type": "estimate", "sex": sex,
                            "age_group": age, "geography": _GEOGRAPHY_NATIONAL,
                            "period": _PERIOD, "frequency": "annual",
                            "measure": "count", "value": float(v),
                            "unit": "persons", "series_code": _SERIES_CODE,
                        })

            if _T4.search(text):
                for line in (page.extract_text() or "").splitlines():
                    m = _SEX_ROW.match(re.sub(r"\s+", " ", line).strip())
                    if not m:
                        continue
                    sex = _SEXES.get(m.group("sex").lower())
                    if not sex:
                        continue
                    records.append({
                        "series_type": "estimate", "sex": sex,
                        "age_group": "Total", "geography": _GEOGRAPHY_NATIONAL,
                        "period": _PERIOD, "frequency": "annual",
                        "measure": "median_age",
                        "value": float(m.group("median").replace(",", ".")),
                        "unit": "years", "series_code": _SERIES_CODE,
                    })

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Gabon population: Tableau 3 (age x sex) not found")
    counts = df[df["measure"] == "count"]
    if counts["age_group"].nunique() < 10 or "Total" not in set(counts["age_group"]):
        raise ValueError(
            f"Gabon population: only {counts['age_group'].nunique()} age bands parsed")
    return df.drop_duplicates(["geography", "sex", "age_group", "period", "measure"])
