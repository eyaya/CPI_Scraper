"""Parser for the ANSADE Mauritania monthly INPC note PDF (Tier 3).

ANSADE publishes a monthly 'Indice National des Prix à la Consommation' note.
'Tableau 2 : Evolution de l'indice par fonction' lists the 12 COICOP-1999
functions (with sub-items) + 'Indice général', each row carrying a code, weight,
five monthly indices, then four variations (monthly, 3-month, year-on-year,
12-month average):

  01 Produits alimentaires … 5 030  134,7 142,3 147,1 149,1 150,5  +0,9 +5,8 +11,7 +5,9
  Indice général      10 000  125,6 130,8 134,8 136,4 137,2  +0,5 +4,9  +9,2 +4,4

So current index = nums[-5], MoM nums[-4], YoY (glissement annuel) nums[-2].
Function rows begin with a two-digit code; sub-item rows begin with 'v' and are
skipped. Mauritania's function 02 is 'Tabac et stupéfiants' (no alcohol). Report
month is read from the note text.
"""
from __future__ import annotations
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
_NUM = re.compile(r"-?\d+,\d+")


def _period(text: str) -> str | None:
    m = re.search(r"consommation en ([a-zûéà]+)\s+(20\d\d)", text.lower())
    if m and m.group(1) in _FR:
        return f"{m.group(2)}-{_FR[m.group(1)]}"
    return None


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    text = "\n".join(pages)
    period = _period(text)
    if not period:
        raise ValueError("Mauritania INPC: report month not found")
    table = next((t for t in pages
                  if "par fonction" in t.lower() and "indice g" in t.lower()), text)

    picked = {}
    for ln in table.splitlines():
        nums = _NUM.findall(ln)
        if len(nums) < 9:                       # 5 indices + 4 variations
            continue
        own = ln[:_NUM.search(ln).start()].strip()
        m = re.match(r"(\d{2})\b", own)
        if m and m.group(1) in _LABELS and m.group(1) != "00":
            code = m.group(1)
        elif "indice g" in own.lower():
            code = "00"
        else:
            continue                            # sub-item ('v …') or noise
        if code in picked:
            continue
        vals = [float(x.replace(",", ".")) for x in nums]
        picked[code] = (vals[-5], vals[-4], vals[-2])

    missing = [c for c in _LABELS if c not in picked]
    if missing:
        raise ValueError(f"Mauritania INPC incomplete: missing {missing}")

    records = []
    for code, (idx, mom, yoy) in picked.items():
        label = _LABELS[code]
        records.append((code, label, period, "index", round(idx, 4), "Index", ""))
        records.append((code, label, period, "inflation_mom", round(mom, 4), "percent", ""))
        records.append((code, label, period, "inflation_yoy", round(yoy, 4), "percent", ""))
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
