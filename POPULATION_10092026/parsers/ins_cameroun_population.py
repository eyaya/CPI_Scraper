"""INS Cameroun — demographic projections 2016-2025 by region and sex
(Tier-3 PDF).

Parser for section II.1 ('Résultats des projections démographiques') of
'Projections démographiques et estimations des cibles des programmes de santé',
which gives one table per geography:

    Population estimée du Cameroun
    Tableau 12 : Répartition de la population du Cameroun par sexe et par année …
    Année   Les deux sexes   Masculin     Féminin
    2016      23 642 400    11 935 961   11 706 439
    …

    Population estimée de la région de l'Adamaoua
    Année   Les deux sexes   Féminin      Masculin        <- NOTE the swap
    2016       1 205 681       614 593      591 088

**The sex column order is not constant.** The national table lists Masculin then
Féminin; the regional tables list Féminin then Masculin. So the header of each
table is read to bind the columns — assuming a fixed order would silently swap
every region's male and female counts, a mistake that no row-count or total check
would reveal because male + female = total either way.

Geography comes from the 'Population estimée …' caption above each table, so
Yaoundé and Douala (reported separately from their regions, which are then given
'sans Yaoundé' / 'sans Douala') are kept as the source labels them.

French numbers use a SPACE thousands separator, so counts are rebuilt from word
x-gaps rather than by splitting on whitespace; each row is checked against
male + female = les deux sexes.
"""
from __future__ import annotations
import re
import unicodedata
import pandas as pd
import pdfplumber

_SERIES_CODE = "CM_PROJ_2016_2025"
_NATIONAL_KEY = "cameroun"
_GEOGRAPHY_NATIONAL = "Total country"
_GAP = 8.0            # pt: below this, a gap is a thousands separator
_COL_GAP = 18.0       # pt: at least this wide separates label from data
_TOLERANCE = 5

_CAPTION = re.compile(
    r"^Population\s+estim[ée]e\s+(?:du|de\s+la|de\s+l['’]|des|de)\s+(?P<geo>.+?)\s*$",
    re.I)
_HEADER = re.compile(
    r"^Ann[ée]e\s+(?P<c1>Les\s+deux\s+sexes|Masculin|F[ée]minin)\s+"
    r"(?P<c2>Les\s+deux\s+sexes|Masculin|F[ée]minin)\s+"
    r"(?P<c3>Les\s+deux\s+sexes|Masculin|F[ée]minin)\s*$", re.I)
_YEAR = re.compile(r"^(19|20)\d{2}$")


def _key(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


_SEX_OF = {"lesdeuxsexes": "total", "masculin": "male", "feminin": "female"}


_Y_TOL = 6.0          # pt: words within this vertical distance are one row


def _rows(page):
    """Page words grouped into visual rows.

    Grouped SEQUENTIALLY by vertical distance, not by rounding `top` into fixed
    buckets: in these tables the year label is set ~2.5 pt below its own numbers
    while consecutive rows are ~17 pt apart, so a bucket boundary can fall between
    a year and its data — which silently splits some rows and not others, and cost
    most of this table before it was caught by a per-geography year count."""
    words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
    bands: list[list] = []
    for w in words:
        if bands and abs(w["top"] - bands[-1][0]) <= _Y_TOL:
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


def _groups(words) -> list[int]:
    out, cur, prev_x1 = [], "", None
    for w in words:
        t = w["text"]
        if not t.isdigit():
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


def _geography(name: str) -> str:
    geo = re.sub(r"^(r[ée]gion|ville)\s+(?:du|de\s+la|de\s+l['’]|des|de)?\s*", "",
                 name.strip(), flags=re.I)
    geo = re.sub(r"\s+", " ", geo).strip(" .:;")
    return _GEOGRAPHY_NATIONAL if _key(geo) == _NATIONAL_KEY else geo


def parse(local_path: str) -> pd.DataFrame:
    records = []
    geography, order = None, None

    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages:
            rows = [ws for ws in _rows(page) if ws]
            texts = [re.sub(r"\s+", " ", " ".join(w["text"] for w in ws)).strip()
                     for ws in rows]
            for i, ws in enumerate(rows):
                line = texts[i]
                # The column header wraps on some pages — 'Année' alone, its sex
                # labels on the next line — so try the joined pair too. Getting
                # this wrong loses the whole table, since the bind of columns to
                # sexes comes from the header and nothing else.
                joined = f"{line} {texts[i + 1]}" if i + 1 < len(texts) else line

                cap = _CAPTION.match(line)
                if cap:
                    geography = _geography(cap.group("geo"))
                    order = None            # its header follows
                    continue

                head = _HEADER.match(line) or _HEADER.match(joined)
                if head:
                    order = [_SEX_OF[_key(head.group(g))] for g in ("c1", "c2", "c3")]
                    continue

                if not geography or not order:
                    continue
                label, data = _split(ws)
                if not _YEAR.match(label):
                    continue
                nums = _groups(data)
                if len(nums) != 3:
                    continue

                by_sex = dict(zip(order, nums))
                if {"male", "female", "total"} - by_sex.keys():
                    continue
                if abs(by_sex["male"] + by_sex["female"] - by_sex["total"]) > _TOLERANCE:
                    continue

                for sex, v in by_sex.items():
                    records.append({
                        "series_type": "projection", "sex": sex,
                        "age_group": "Total", "geography": geography,
                        "period": label, "frequency": "annual", "measure": "count",
                        "value": float(v), "unit": "persons",
                        "series_code": _SERIES_CODE,
                    })

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("Cameroon population: no projection table parsed")
    if _GEOGRAPHY_NATIONAL not in set(df["geography"]):
        raise ValueError("Cameroon population: national table not found")
    if df["geography"].nunique() < 10:
        raise ValueError(
            f"Cameroon population: only {df['geography'].nunique()} geographies — "
            f"expected the country plus its regions")
    return df.drop_duplicates(["geography", "sex", "age_group", "period", "measure"])
