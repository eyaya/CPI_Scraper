"""Parser for the ANSADE Mauritania monthly INPC note PDF (Tier 3).

ANSADE publishes a monthly 'Indice National des Prix à la Consommation' note.
Its national table lists the 12 COICOP-1999 functions (with sub-items) +
'Indice général', each row carrying a code, weight, the monthly indices, then
the variations:

  01 Produits alimentaires … 5 030  134,7 142,3 147,1 149,1 150,5  +0,9 +5,8 +11,7 +5,9
  Indice général      10 000  125,6 130,8 134,8 136,4 137,2  +0,5 +4,9  +9,2 +4,4

Function rows begin with a two-digit code; sub-item rows begin with 'v' (or a
label, or a bare weight) and are skipped. Mauritania's function 02 is 'Tabac et
stupéfiants' (no alcohol).

BACK ISSUES (2026-10-13). `parse` reads the newest note plus the back issues
listed as `extra_urls` (ANSADE's media library holds every note from 2016-01)
through `ihpc_note_pdf.read_many`; the newest issue wins on overlap. Three
layouts, all handled by one reader:

  * 2016-01 .. 2022-07, base 2014 (bilingual French/Arabic): 'Tableau 1' is the
    national INPC; 4 indices (m-12, m-3, m-1, m) + 3 variations (1 month,
    3 months, year). 'Tableau 2' is the Nouakchott IHPC -- NOT read. Arabic
    extraction garbles some codes ('21' for 01, '29' for 09) and drops labels,
    so the 12 function rows are taken IN ORDER and checked against the labels
    that survive.
  * 2022-08 .. , base 2019: 4 indices + 4 variations (… + 12-month average).
  * the current note: 5 indices (m-12, m-3, m-2, m-1, m) + 4 variations.

Indices are the unsigned figures, variations the signed ones. EVERY PRINTED
MONTH is emitted, dated from the report month -- and the dating is checked by
arithmetic on every row: the printed 1-month, 3-month and 12-month variations
must match the indices they sit beside (within index rounding). A row that
fails is dropped loudly; if 'Indice général' fails the issue is rejected.
MoM / YoY belong to the report month. The report month is the latest
'<mois> <année>' the note names (the Sept-2026 note's Tableau 1 caption still
says 'août 2026'); base_period is read per issue ('Base 100 en 2014' /
'Base 100 = 2019'; a note naming both takes the later, the earlier being the
replaced base) and left empty where a note does not state it. Never chained.
"""
from __future__ import annotations
import os
import re
import pdfplumber
import pandas as pd

_FR = {"janvier": "01", "fevrier": "02", "février": "02", "mars": "03", "avril": "04",
       "mai": "05", "juin": "06", "juillet": "07", "aout": "08", "août": "08",
       "septembre": "09", "octobre": "10", "novembre": "11", "decembre": "12",
       "décembre": "12"}
_LABELS = {
    "00": "Indice général (Ensemble)",
    "01": "Produits alimentaires et boissons non alcoolisées",
    "02": "Tabac et stupéfiants",
    "03": "Articles d'habillement et chaussures",
    "04": "Logement, eau, gaz, électricité et autres combustibles",
    "05": "Meubles, articles de ménage et entretien courant du foyer",
    "06": "Santé",
    "07": "Transports",
    "08": "Communication",
    "09": "Loisirs et culture",
    "10": "Enseignement",
    "11": "Restaurants et hôtels",
    "12": "Biens et services divers",
}
# a surviving label must agree with the function's position in the table
_KEYS = {"01": "aliment", "02": "tabac", "03": "habillement", "04": "logement",
         "06": "santé", "07": "transport", "08": "communication", "09": "loisirs",
         "10": "enseignement", "11": "restaurant", "12": "biens et services"}
_NUM = re.compile(r"[+-]?\d+,\d+")
_MONTH_YEAR = re.compile(r"\b(" + "|".join(_FR) + r")\s*[–-]?\s*(20\d\d)\b")
_BASE = re.compile(r"base\s*100\s*(?:=|en)\s*((?:19|20)\d\d)", re.IGNORECASE)


def _period(text: str) -> str | None:
    found = [(y, _FR[m]) for m, y in _MONTH_YEAR.findall(text.lower())]
    return f"{max(found)[0]}-{max(found)[1]}" if found else None


def _back(period: str, n: int) -> str:
    y, m = int(period[:4]), int(period[5:]) - n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y}-{m:02d}"


def _split(line: str):
    """(indices, variations) from a row, or None if the shape is not 4-5 + 3-4."""
    toks = _NUM.findall(line)
    idx = []
    for t in toks:
        if t[0] in "+-":
            break
        idx.append(float(t.replace(",", ".")))
    var = [float(t.replace(",", ".")) for t in toks[len(idx):]]
    if len(idx) not in (4, 5) or len(var) not in (3, 4):
        return None
    return idx, var


def _consistent(idx: list[float], var: list[float]) -> bool:
    tol = 100 * 0.1 / min(idx) + 0.06            # one-decimal index rounding
    pct = lambda a, b: (a / b - 1) * 100          # noqa: E731
    return (abs(pct(idx[-1], idx[-2]) - var[0]) <= tol
            and abs(pct(idx[-1], idx[1]) - var[1]) <= tol
            and abs(pct(idx[-1], idx[0]) - var[2]) <= tol)


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    from .ihpc_note_pdf import read_many
    return read_many([pdf_path, *(extras or [])], _parse_issue, "mauritania_ansade")


def _parse_issue(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    text = "\n".join(pages)
    period = _period(text)
    if not period:
        raise ValueError("Mauritania INPC: report month not found")
    # Notes since the 2022-08 rebasing also name the replaced base (2014);
    # the index is in the LATEST base the note states.
    bases = _BASE.findall(text)
    base = f"{max(bases)} = 100" if bases else ""

    # The national table: function rows (leading two-digit code) up to the first
    # 'Indice général' row. Anything after it (the Nouakchott IHPC) is ignored.
    funcs, total = [], None
    for ln in text.splitlines():
        s = ln.strip()
        shape = _split(s)
        if not shape:
            continue
        if "indice g" in s.lower():
            if funcs:
                total = (s, shape)
                break
            continue
        if re.match(r"\d{2}\s", s):
            funcs.append((s, shape))
    if total is None or len(funcs) != 12:
        raise ValueError(f"Mauritania INPC: national table not found "
                         f"({len(funcs)} function rows, total={'yes' if total else 'no'})")

    rows = {"00": total[1]}
    for (s, shape), code in zip(funcs, [f"{i:02d}" for i in range(1, 13)]):
        key = _KEYS.get(code)
        label = re.sub(r"[\d\s,+-]+", " ", s).lower()
        others = [c for c, k in _KEYS.items() if c != code and k in label]
        if key and key not in label and others:
            raise ValueError(f"Mauritania INPC: row {code} is labelled as {others}")
        rows[code] = shape

    n = len(total[1][0])
    cols = ([_back(period, 12), _back(period, 3), _back(period, 1), period] if n == 4 else
            [_back(period, 12), _back(period, 3), _back(period, 2), _back(period, 1), period])
    records, dropped = [], []
    for code, (idx, var) in rows.items():
        if len(idx) != n or not _consistent(idx, var):
            if code == "00":
                raise ValueError("Mauritania INPC: 'Indice général' variations do not "
                                 "match its indices -- columns not as expected")
            dropped.append(code)
            continue
        label = _LABELS[code]
        for per, v in zip(cols, idx):
            records.append((code, label, per, "index", round(v, 4), "Index", base))
        records.append((code, label, period, "inflation_mom", round(var[0], 4), "percent", ""))
        records.append((code, label, period, "inflation_yoy", round(var[2], 4), "percent", ""))
    if dropped:
        print(f"  [mauritania_ansade] {os.path.basename(pdf_path)}: dropped row(s) "
              f"{dropped} -- variations do not match the printed indices")
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    out["_issue"] = period
    return out
