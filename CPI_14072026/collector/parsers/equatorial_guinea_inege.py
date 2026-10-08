"""Parser for the INEGE Equatorial Guinea monthly IPC report PDF (Tier 3).

INEGE publishes a Spanish-language monthly note whose annexes carry the tabular
data, each a full function x geography grid (national + the 5 surveyed cities):

  Índice general y de funciones   Nacional  Malabo  Bata  Ebibeyin  Mongomo  Evinayong
  IPC general                        169,5   187,6  159,5    159,3    164,4      146,1
  Productos alimenticios …           171,2   191,2  166,8    161,3    162,6      142,7

We take two of them — 'Índices de precios mensuales' (index, base 2008) and
'Variación mensual del IPC' (MoM) — matched on their CAPTION TEXT, never their
number: INEGE ships two different annexes both labelled 'Anexo 4'.

NOT captured: the 'Inflación nacional y por ciudad' annex. Despite the name it is
NOT year-on-year — it is the CEMAC multilateral-surveillance measure, a 12-month
moving average (May 2026: 2,3%, against a true interanual of 3,5% stated in the
same report). The schema has no measure for it, and mapping it onto inflation_yoy
would be wrong, so it is dropped rather than mislabelled.

Layout notes:
* A row's label sits at whichever side has room — above its numbers for the first
  row, below for the rest — so each numeric row is matched to its NEAREST label
  rather than an assumed reading order.
* Numbers of one row can land on two baselines a few points apart, so numeric
  tokens are clustered by `top` rather than taken line by line.
* Cells are matched to geographies by position, and a row must carry exactly one
  token per geography or the whole parse fails — a silently dropped cell would
  shift every later column onto the wrong city.
* A token may still be malformed in the source ('-1,' with no decimal digit —
  Ropa y calzados / Nacional in the May 2026 issue is a genuine typo in INEGE's
  PDF, not an extraction artefact). Such a cell is skipped: it holds the column
  alignment but the missing digit is not invented.
"""
from __future__ import annotations
import re
import unicodedata

import pdfplumber
import pandas as pd

_BASE_PERIOD = "2008 = 100"
_ES_MONTHS = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05",
    "junio": "06", "julio": "07", "agosto": "08", "septiembre": "09",
    "octubre": "10", "noviembre": "11", "diciembre": "12",
}
# The published national aggregate is normalised to the repo-wide 'National';
# the five cities keep INEGE's own spelling.
_CITIES = ["malabo", "bata", "ebibeyin", "mongomo", "evinayong"]
_GEO_LABELS = {"nacional": "National", "malabo": "Malabo", "bata": "Bata",
               "ebibeyin": "Ebibeyin", "mongomo": "Mongomo",
               "evinayong": "Evinayong"}

# (code, label as published, normalised prefix). CEMAC's NCAC = COICOP-1999 with
# 12 functions. 'Espaciamiento' is INEGE's own spelling of 'Esparcimiento'.
_FUNCTIONS = [
    ("00", "IPC general", "ipc general"),
    ("01", "Productos alimenticios y bebidas no alcohólicas",
     "productos alimenticios y bebidas no alcoholicas"),
    ("02", "Bebidas alcohólicas y tabaco", "bebidas alcoholicas y tabaco"),
    ("03", "Ropa y calzados", "ropa y calzados"),
    ("04", "Viviendas, agua, electricidad, gas y otros combustibles",
     "viviendas, agua, electricidad, gas y otros"),
    ("05", "Muebles, equipos de hogar y mantenimiento corriente del hogar",
     "muebles, equipos de hogar y mantenimiento"),
    ("06", "Salud", "salud"),
    ("07", "Transporte", "transporte"),
    ("08", "Comunicación", "comunicacion"),
    ("09", "Espaciamiento, espectáculos y cultura", "espaciamiento, espectaculos"),
    ("10", "Educación", "educacion"),
    ("11", "Restaurantes y hoteles", "restaurantes y hoteles"),
    ("12", "Bienes y servicios diversos", "bienes y servicios diversos"),
]
# Keyword in an 'Anexo N:' caption -> measure. Keyed on wording, NOT on the number
# (two different annexes are both called 'Anexo 4'), and deliberately loose: the
# index caption reads 'Índices de precios mensuales nacional…' in some issues and
# 'Índices de precios nacional…' in others. Only these two are wanted; 'Inflación'
# (a 12-month moving average) and 'Ponderaciones' (weights) are ignored.
_ANNEXES = [
    ("indices de precios", "index"),
    ("variacion mensual del ipc", "inflation_mom"),
]
# Deliberately tolerant, so that a cell INEGE typo'd still occupies its column and
# the row stays aligned: '\d*' admits a missing decimal ('-1,'), '%?' a stray unit
# ('0,2%'). Whether the token yields a number is decided later, in _value().
_RE_TOKEN = re.compile(r"^-?\d+,\d*%?$")
# A token that is actually a number: at least one digit after the comma.
_RE_VALUE = re.compile(r"^-?\d+,\d+%?$")
# Only a real annex caption — the same wording also appears in the body prose
# ('3. Variación mensual del IPC en el mes de junio 2026'), which has no table.
_RE_CAPTION = re.compile(r"anexo\s*\d+\s*:\s*([^\n]*)")
_RE_CAPTION_DATE = re.compile(r"([a-z]+)\s+de\s+(\d{4})")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).replace("\xa0", " "))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def _cluster(items, tol: float):
    """Group page items into visual rows, tolerating baseline jitter."""
    out, cur = [], []
    for it in sorted(items, key=lambda z: z["top"]):
        if cur and it["top"] - cur[0]["top"] > tol:
            out.append(cur)
            cur = []
        cur.append(it)
    if cur:
        out.append(cur)
    return [sorted(g, key=lambda z: z["x0"]) for g in out]


def _value(tok: str) -> float | None:
    """'-0,5' -> -0.5, '0,2%' -> 0.2 (stray unit), '-1,' -> None (the source is
    missing the decimal digit — the cell is dropped, never guessed).

    The shape is checked before converting, because float() would quietly accept
    the truncated cell: float('-1,'.replace(',', '.')) == -1.0 would invent a
    digit INEGE never printed.
    """
    if not _RE_VALUE.match(tok):
        return None
    return float(tok.rstrip("%").replace(",", "."))


def _geographies(words, grid_top: float, first_value_top: float) -> tuple[list[str], float]:
    """Column order, read off the header (which splits 'Nacional' and the five
    cities across two lines), plus the x where the value zone starts.

    Bounded to the header band: the annex CAPTION also contains the word
    'nacional' ('Índices de precios nacional y por ciudad'), and picking that up
    instead of the column header would mis-order the columns.
    """
    hits = [w for w in words
            if _norm(w["text"]) in _GEO_LABELS
            and w["top"] < first_value_top and abs(w["top"] - grid_top) <= 30]
    order, seen = [], set()
    for w in sorted(hits, key=lambda z: z["x0"]):
        key = _norm(w["text"])
        if key not in seen:
            seen.add(key)
            order.append(w)
    if len(order) != len(_GEO_LABELS):
        raise ValueError(
            f"Equatorial Guinea IPC: expected {len(_GEO_LABELS)} geography columns, "
            f"found {[w['text'] for w in order]}")
    return ([_GEO_LABELS[_norm(w["text"])] for w in order],
            min(w["x0"] for w in order) - 5)


def _annex(page, grid_top: float, measure: str, period: str) -> list[tuple]:
    words = page.extract_words()
    nums_all = [w for w in words
                if _RE_TOKEN.match(w["text"]) and w["top"] > grid_top]
    if not nums_all:
        return []
    geos, left = _geographies(words, grid_top, min(w["top"] for w in nums_all))

    nums = [w for w in nums_all if w["x0"] >= left]
    labels = _cluster([w for w in words if w["x0"] < left], tol=3)
    records = []
    seen = set()
    for row in _cluster(nums, tol=5):
        if len(row) != len(geos):
            raise ValueError(
                f"Equatorial Guinea IPC ({measure}): row has {len(row)} values, "
                f"expected {len(geos)}: {[w['text'] for w in row]}")
        top = row[0]["top"]
        near = min(labels, key=lambda g: abs(g[0]["top"] - top))
        text = _norm(" ".join(w["text"] for w in near))
        hit = next(((c, lab) for c, lab, pref in _FUNCTIONS
                    if text.startswith(pref)), None)
        if not hit or hit[0] in seen:
            continue
        code, label = hit
        seen.add(code)
        for geo, w in zip(geos, row):
            v = _value(w["text"])
            if v is None:
                continue          # malformed in the source — don't invent it
            records.append((
                code, label, geo, period, measure, round(v, 4),
                "Index" if measure == "index" else "percent",
                _BASE_PERIOD if measure == "index" else "",
            ))

    missing = [c for c, _, _ in _FUNCTIONS if c not in seen]
    if missing:
        raise ValueError(
            f"Equatorial Guinea IPC ({measure}): missing function(s) {missing}")
    return records


def _grids(pdf) -> list[tuple[int, float]]:
    """(page index, top of the city header row) for each annex grid in the file.

    Anchored on the row of CITY names: unlike 'nacional', they appear neither in
    the annex captions nor as a row of their own in the body prose, so a row
    carrying most of them is the real column header of a grid.
    """
    out = []
    for i, page in enumerate(pdf.pages):
        for row in _cluster(page.extract_words(), tol=3):
            if len({_norm(w["text"]) for w in row} & set(_CITIES)) >= 4:
                out.append((i, row[0]["top"]))
                break
    return out


def _captions(pdf) -> list[tuple[int, float, str]]:
    """(page index, top, caption text) for every 'Anexo N:' caption."""
    out = []
    for i, page in enumerate(pdf.pages):
        for row in _cluster(page.extract_words(), tol=3):
            m = _RE_CAPTION.match(_norm(" ".join(w["text"] for w in row)))
            if m:
                out.append((i, row[0]["top"], m.group(1)))
    return out


def parse(pdf_path: str) -> pd.DataFrame:
    records = []
    found = set()
    with pdfplumber.open(pdf_path) as pdf:
        grids = _grids(pdf)
        for pi, top, caption in _captions(pdf):
            measure = next((m for kw, m in _ANNEXES if kw in caption), None)
            if measure is None or measure in found:
                continue
            # The caption does not always share a page with its table: some issues
            # end a page on the caption and open the next with the grid. Take the
            # first grid that starts after this caption.
            grid = next(((gi, gt) for gi, gt in grids
                         if gi > pi or (gi == pi and gt > top)), None)
            if grid is None:
                raise ValueError(
                    f"Equatorial Guinea IPC: no table after caption {caption!r}")
            m = _RE_CAPTION_DATE.search(caption)
            mm = _ES_MONTHS.get(m.group(1)) if m else None
            if not mm:
                raise ValueError(
                    f"Equatorial Guinea IPC: no month in caption {caption!r}")
            found.add(measure)
            records += _annex(pdf.pages[grid[0]], grid[1], measure,
                              f"{m.group(2)}-{mm}")

    missing = [m for _, m in _ANNEXES if m not in found]
    if missing:
        raise ValueError(f"Equatorial Guinea IPC: annex(es) not found for {missing}")

    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "geography", "period",
                          "measure", "value", "unit", "base_period"])
    out["frequency"] = "monthly"
    return out
