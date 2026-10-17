"""Parser for the INS Congo (Republic of Congo) INHPC bulletin PDF (Tier 3).

Congo publishes the CEMAC harmonised CPI (INHPC, base 100 = 2018). 'Tableau 1.1 :
… par fonction' is one row per COICOP-1999 function (Roman-less CEMAC list) +
INDICE GLOBAL:

  Libellé  Pond.  <idx m-12> <idx m-3> <idx m-2> <idx m-1> <idx current>  1m  3m  12m
  INDICE GLOBAL 100,0 119,0 118,6 121,2 120,4 122,5 1,7 3,2 2,9

Nine comma-decimal numbers per row: weight, five monthly indices, then 1-/3-/12-
month variations. So current index = nums[-4], MoM nums[-3], YoY nums[-1]. Function
labels wrap across the number row (part above, part below), so each division is
matched on a prev+own+next line window. We scope to the national 'par fonction'
page. Base 2018 = 100.

BACK ISSUES (2026-10-14). `parse` reads the newest bulletin plus the back issues
listed as `extra_urls` (INS's publications API, backend/api/publications/
list.php?sous_secteur=stat-prix, serves 2026-01 on; the 2024-25 entries it
lists answer 404 'Fichier introuvable') through `ihpc_note_pdf.read_many`; the
newest issue wins on overlap. The five index columns (m-12, m-3, m-2, m-1, m)
are all emitted, dated from the report month, for every row whose printed
1-/3-/12-month variations match those indices (within rounding) -- the
arithmetic is the check on the dating. A row that does not match keeps only
the report month, as before.
"""
from __future__ import annotations
import os
import re
import pdfplumber
import pandas as pd

_BASE_PERIOD = "2018 = 100"
_FR_MONTHS = {"janv": "01", "fevr": "02", "fév": "02", "mars": "03", "avri": "04",
              "mai": "05", "juin": "06", "juil": "07", "aout": "08", "aoû": "08",
              "sept": "09", "octo": "10", "nove": "11", "dece": "12", "déce": "12"}
# (code, canonical label, keyword) — first match wins, checked in this order
_DIVS = [
    ("00", "Indice global (Ensemble)", "indice global"),
    ("01", "Produits alimentaires et boissons non alcoolisées", "aliment"),
    ("02", "Boissons alcoolisées, tabacs et stupéfiants", "tabac"),
    ("03", "Articles d'habillement et chaussures", "habillement"),
    ("04", "Logement, eau, électricité, gaz et autres combustibles", "logement"),
    ("05", "Meubles, articles de ménage et entretien courant du foyer", "meubles"),
    ("06", "Santé", "sant"),
    ("07", "Transports", "transport"),
    ("08", "Communication", "communication"),
    ("09", "Loisirs et culture", "loisirs"),
    ("10", "Enseignement", "enseignement"),
    ("11", "Restaurants et hôtels", "restaurant"),
    ("12", "Biens et services divers", "biens et services divers"),
]
_NUM = re.compile(r"-?\d+,\d+")


def _period_from(s: str, sep: str) -> str | None:
    for key, mm in _FR_MONTHS.items():
        m = re.search(key + r"[a-zûé]*" + sep + r"(20\d\d)", s.lower())
        if m:
            return f"{m.group(1)}-{mm}"
    return None


def _period(path: str, text: str) -> str | None:
    # prefer the report month stated in the bulletin ("du mois d'avril 2026" /
    # "Base 100 : 2018, avril 2026"); fall back to the filename/slug.
    for anchor in [r"du mois d[e'’\s]+", r"base\s*100\s*:\s*2018,?\s*"]:
        m = re.search(anchor, text.lower())
        if m:
            p = _period_from(text[m.end():m.end() + 24], r"\s+")
            if p:
                return p
    return _period_from(os.path.basename(path), r"[-_ ]*")


def _code(label: str):
    low = label.lower()
    for c, lab, kw in _DIVS:
        if kw in low:
            return c, lab
    return None


def _back(period: str, n: int) -> str:
    y, m = int(period[:4]), int(period[5:]) - n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y}-{m:02d}"


def _consistent(five: list[float], mom: float, q: float, yoy: float) -> bool:
    tol = 100 * 0.1 / min(five) + 0.06            # one-decimal index rounding
    pct = lambda a, b: (a / b - 1) * 100          # noqa: E731
    return (abs(pct(five[-1], five[-2]) - mom) <= tol
            and abs(pct(five[-1], five[1]) - q) <= tol
            and abs(pct(five[-1], five[0]) - yoy) <= tol)


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    from .ihpc_note_pdf import read_many
    return read_many([pdf_path, *(extras or [])], _parse_issue, "congo_ins")


def _parse_issue(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    text = next((t for t in pages
                 if "par fonction" in t.lower() and "indice global" in t.lower()),
                "\n".join(pages))
    period = _period(pdf_path, text)
    if not period:
        raise ValueError("Congo INHPC: report month not found")

    lines = text.splitlines()

    def label_only(i):
        if 0 <= i < len(lines) and len(_NUM.findall(lines[i])) == 0:
            return lines[i].strip()
        return ""

    picked = {}
    for i, ln in enumerate(lines):
        nums = _NUM.findall(ln)
        if len(nums) < 8:                          # weight + 5 indices + 3 variations
            continue
        own = ln[:_NUM.search(ln).start()].strip()
        window = f"{label_only(i-1)} {own} {label_only(i+1)}"
        hit = _code(window)
        if hit and hit[0] not in picked:
            vals = [float(x.replace(",", ".")) for x in nums]
            picked[hit[0]] = (hit[1], vals[-8:-3], vals[-3], vals[-2], vals[-1])

    missing = [c for c, _, _ in _DIVS if c not in picked]
    if missing:
        raise ValueError(f"Congo INHPC incomplete: missing {missing}")

    cols = [_back(period, 12), _back(period, 3), _back(period, 2), _back(period, 1), period]
    records = []
    for code, (label, five, mom, q, yoy) in picked.items():
        dated = list(zip(cols, five)) if _consistent(five, mom, q, yoy) else [(period, five[-1])]
        for per, idx in dated:
            records.append((code, label, per, "index", round(idx, 4), "Index", _BASE_PERIOD))
        records.append((code, label, period, "inflation_mom", round(mom, 4), "percent", ""))
        records.append((code, label, period, "inflation_yoy", round(yoy, 4), "percent", ""))
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    out["_issue"] = period
    return out
