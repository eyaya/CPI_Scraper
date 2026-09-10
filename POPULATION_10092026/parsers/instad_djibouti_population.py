"""INSTAD Djibouti RGPH-3 census — population by age group, sex and region
(Tier-3 PDF).

Parser for Thématique 1 of the census report, 'État et structure de la
population', which carries the five-year age-by-sex distribution once for the
country and once for each of the six regions:

    Tableau n°16 … par groupe d'âges quinquennal selon le sexe          -> national
    Tableau n°23 … selon le sexe dans la région de Djibouti-Ville
    Tableau n°24 … dans la région d'Ali-Sabieh          (then Dikhil,
    Tableau n°25 …                                       Tadjourah, Obock, Arta)

The geography therefore comes from the table's own caption — 'dans la région
de/d' <name>' when present, national when absent — so the parser never depends on
page numbers, which move whenever INSTAD re-flows the report.

Each row is
    0 - 4 ans   63 217  12,7   57 989  11,4   121 206  12,1   109
    <age>       <male>  <%>    <female> <%>   <total>  <%>    <sex ratio>

French numbers use a SPACE thousands separator, and a percentage can be written
without a decimal ('15'), so splitting the line on whitespace is ambiguous —
'5 454 15 5 026' could group several ways. We therefore rebuild each number from
word x-positions: within one number the gap between words is ~3 pt, between
columns it is 16 pt or more, so a gap under `_GAP` continues the current number.
Counts are the 1st, 3rd and 5th groups; the 7th is the sex ratio (males per 100
females), emitted as its own `sex_ratio` measure since the schema has one.

Rows whose male + female does not reconcile to the published total are dropped
rather than guessed at — that is the check that a mis-grouped number cannot pass.
"""
from __future__ import annotations
import re
import unicodedata
import pdfplumber
import pandas as pd

_SERIES_CODE = "DJ_RGPH3"
# RGPH-3 is the 2024 census (the report, published Nov 2025, sources every table
# to "INSTAD (2024) RGPH-3"); the period is the census reference year, not the
# publication year.
_PERIOD = "2024"
_GEOGRAPHY_NATIONAL = "Total country"
_GAP = 8.0            # pt: gap below this continues one number (thousands space)
_TOLERANCE = 5        # persons: allowed male+female vs total rounding slack

_CAPTION = re.compile(
    r"Tableau\s*n[°ºo]\s*\d+\.?\s*R[ée]partition.{0,120}?"
    r"groupe\s*d[’']?\s*[âa]ges?\s*quinquennal\s*selon\s*le\s*sexe"
    r"(?:\s*dans\s*la\s*r[ée]gion\s*d[e’']?\s*(?P<region>[^\n,.]{2,40}))?",
    re.I | re.S)
_AGE = re.compile(r"^(\d{1,3})\s*-\s*(\d{1,3})\s*ans?$|^(\d{1,3})\s*(?:ans\s*)?et\s*plus$"
                  r"|^(\d{1,3})\s*\+$", re.I)
_TOTAL_ROW = re.compile(r"^(Ensemble|Total)$", re.I)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def _clean_region(name: str) -> str:
    """Tidy a caption's region name ('Djibouti-Ville Sexe' -> 'Djibouti-Ville')."""
    out = _norm(name)
    out = re.sub(r"\s+(Sexe|Effectif|Total)\b.*$", "", out, flags=re.I)
    return out.strip(" .:-")


def _rows(page) -> list[list[dict]]:
    """Page words grouped into visual rows, each left-to-right."""
    bands: dict[int, list] = {}
    for w in page.extract_words():
        bands.setdefault(round(w["top"] / 3.0), []).append(w)
    return [sorted(v, key=lambda x: x["x0"]) for _, v in sorted(bands.items())]


_COL_GAP = 20.0       # pt: a gap this wide separates the label from the data


def _split_row(words):
    """(label, data words). The age label itself contains digits ('0 - 4 ans'),
    so it cannot be found by dropping numeric words; instead we cut at the first
    wide gap, which is the rule the table's own layout follows."""
    cut = len(words)
    for i in range(1, len(words)):
        if words[i]["x0"] - words[i - 1]["x1"] >= _COL_GAP:
            cut = i
            break
    label = _norm(" ".join(w["text"] for w in words[:cut]))
    return label, words[cut:]


def _groups(words) -> list[str]:
    """Rebuild columns from word x-gaps: < _GAP continues the current number."""
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


def _age_label(label: str) -> str:
    """'0 - 4 ans' -> '0-4'; '95 ans et plus' -> '95+'."""
    text = _norm(label)
    m = re.match(r"^(\d{1,3})\s*-\s*(\d{1,3})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"^(\d{1,3})\s*(?:ans\s*)?(?:et\s*plus|\+)", text, re.I)
    return f"{m.group(1)}+" if m else text.replace(" ", "")


def _counts(cols: list[str]):
    """(male, female, total) for a row, or None.

    Normally the counts are groups 1, 3 and 5 — count, percent, count, percent,
    count, percent, sex ratio. When the PDF's text layer garbles a cell (the
    national 90-94 row comes through as '192 (0)9 494 …', an overlapping glyph
    swallowing the male percentage) that positional read fails, so we fall back
    to the table's own identity: the first ordered triple of integers where
    male + female equals the total. Both paths are checked against that identity,
    so a mis-grouped number still cannot get through."""
    vals = [_int(c) for c in cols]
    if len(vals) > 4 and None not in (vals[0], vals[2], vals[4]):
        m, f, t = vals[0], vals[2], vals[4]
        if abs(m + f - t) <= _TOLERANCE:
            return m, f, t
    ints = [(i, v) for i, v in enumerate(vals) if v is not None]
    for a in range(len(ints)):
        for b in range(a + 1, len(ints)):
            for c in range(b + 1, len(ints)):
                m, f, t = ints[a][1], ints[b][1], ints[c][1]
                if t > 0 and abs(m + f - t) <= _TOLERANCE:
                    return m, f, t
    return None


def _int(tok: str):
    return int(tok) if re.fullmatch(r"\d+", tok) else None


def _dec(tok: str):
    try:
        return float(tok.replace(",", "."))
    except ValueError:
        return None


def parse(local_path: str) -> pd.DataFrame:
    records, seen = [], set()

    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            cap = _CAPTION.search(_norm(text))
            if not cap:
                continue
            region = cap.group("region")
            geography = _clean_region(region) if region else _GEOGRAPHY_NATIONAL
            if geography in seen:          # a caption repeated in the contents list
                continue

            emitted = 0
            for ws in _rows(page):
                if not ws:
                    continue
                label, data = _split_row(ws)
                is_total = bool(_TOTAL_ROW.match(label))
                if not is_total and not _AGE.match(label):
                    continue

                cols = _groups(data)
                # A percentage that rounds to zero is printed as '(0)' or '*',
                # which is not numeric and so drops out of the groups — the
                # oldest age rows can therefore carry as few as three numbers.
                if len(cols) < 3:
                    continue
                got = _counts(cols)
                if got is None:
                    continue               # a mis-grouped number cannot reconcile
                male, female, total = got

                age = "Total" if is_total else _age_label(label)
                for sex, v in (("male", male), ("female", female), ("total", total)):
                    records.append({
                        "series_type": "census", "sex": sex, "age_group": age,
                        "geography": geography, "period": _PERIOD,
                        "frequency": "annual", "measure": "count",
                        "value": float(v), "unit": "persons",
                        "series_code": _SERIES_CODE,
                    })
                ratio = _dec(cols[6]) if len(cols) > 6 else None
                if ratio is not None:
                    records.append({
                        "series_type": "census", "sex": "total", "age_group": age,
                        "geography": geography, "period": _PERIOD,
                        "frequency": "annual", "measure": "sex_ratio",
                        "value": ratio, "unit": "ratio",
                        "series_code": _SERIES_CODE,
                    })
                emitted += 1

            if emitted:
                seen.add(geography)

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Djibouti population: no age-by-sex table found")
    if _GEOGRAPHY_NATIONAL not in set(df["geography"]):
        raise ValueError(
            f"Djibouti population: national table missing (got {sorted(seen)})")
    return df.drop_duplicates(["geography", "sex", "age_group", "period", "measure"])
