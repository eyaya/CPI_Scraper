"""Parser for the ANStat Côte d'Ivoire IHPC bulletin PDF (Tier 3).

ANStat publishes the UEMOA/WAEMU harmonised CPI (IHPC) under the **new COICOP-2018
nomenclature** (14 categories: INDICE GLOBAL + divisions 01–13), rebased 100 = 2023.
The national table lists each division with (weight +) five monthly indices then
1-/3-/12-month variations, with detailed sub-items interleaved:

  Libellé  Pondération  juin-25 mars-26 avr-26 mai-26 juin-26  1m 3m 12m
  INDICE GLOBAL 10 000   105,0 105,3 … 105,8  0,5 0,8 1,8
  07 - Transports 1 004  100,7 103,6 … 104,2  0,6 3,5 2,0

So current index = nums[-4], MoM nums[-3], YoY nums[-1]. A division's code comes
from its 'NN -' prefix; two divisions (04, 05) wrap so the code sits on the line
above the numbers. Sub-item rows have no such code and are skipped. Report month
is read from the 'Mois de <MONTH> <YEAR>' header. Base 2023.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_BASE_PERIOD = "2023 = 100"
_FR = {"janvier": "01", "fevrier": "02", "février": "02", "mars": "03", "avril": "04",
       "mai": "05", "juin": "06", "juillet": "07", "aout": "08", "août": "08",
       "septembre": "09", "octobre": "10", "novembre": "11", "decembre": "12",
       "décembre": "12"}
_LABELS = {
    "00": "Indice global (Ensemble)",
    "01": "Produits alimentaires et boissons non alcoolisées",
    "02": "Tabacs et stupéfiants",
    "03": "Articles d'habillement et chaussures",
    "04": "Logement, eau, gaz, électricité et autres combustibles",
    "05": "Meubles, articles de ménage et entretien courant du foyer",
    "06": "Santé",
    "07": "Transports",
    "08": "Information et communication",
    "09": "Loisirs et culture",
    "10": "Enseignement",
    "11": "Restaurants et hôtels",
    "12": "Assurance et services financiers",
    "13": "Protection sociale et soins personnels",
}
_NUM = re.compile(r"-?\d+,\d+")
_CODE = re.compile(r"^(\d{2})\s*-")


def _period(text: str) -> str | None:
    m = re.search(r"mois de\s+([a-zûéà]+)\s+(20\d\d)", text.lower())
    if m and m.group(1) in _FR:
        return f"{m.group(2)}-{_FR[m.group(1)]}"
    return None


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    text = "\n".join(pages)
    period = _period(text)
    if not period:
        raise ValueError("Côte d'Ivoire IHPC: report month not found")
    table = next((t for t in pages
                  if "indice global" in t.lower() and "transport" in t.lower()), text)
    lines = table.splitlines()

    picked = {}
    for k, ln in enumerate(lines):
        nums = _NUM.findall(ln)
        if len(nums) < 8:                          # 5 indices + 3 variations
            continue
        own = ln[:_NUM.search(ln).start()].strip()
        prev = lines[k - 1].strip() if k and not _NUM.search(lines[k - 1]) else ""
        m = _CODE.match(own)
        if m:
            code = m.group(1)
        elif own.upper().startswith("INDICE GLOBAL") or "10 000" in own:
            code = "00"
        elif _CODE.match(prev):                    # wrapped division (04, 05)
            code = _CODE.match(prev).group(1)
        else:
            continue                               # sub-item
        if code not in _LABELS or code in picked:
            continue
        vals = [float(x.replace(",", ".")) for x in nums]
        picked[code] = (vals[-4], vals[-3], vals[-1])

    missing = [c for c in _LABELS if c not in picked]
    if missing:
        raise ValueError(f"Côte d'Ivoire IHPC incomplete: missing {missing}")

    records = []
    for code, (idx, mom, yoy) in picked.items():
        label = _LABELS[code]
        records.append((code, label, period, "index", round(idx, 4), "Index", _BASE_PERIOD))
        records.append((code, label, period, "inflation_mom", round(mom, 4), "percent", ""))
        records.append((code, label, period, "inflation_yoy", round(yoy, 4), "percent", ""))
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
