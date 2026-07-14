"""Parser for the INSBU (Burundi) monthly IPC report PDF (Tier 3).

Burundi's NSO (formerly ISTEEBU, now INSBU — insbu.bi) publishes a monthly
'Indice des Prix à la Consommation des ménages', base 100 = 2016/2017, COICOP-1999.
'Tableau 1' lists 'TOUS LES PRODUITS' (code 0) + the 12 functions (codes 1–12),
with detailed sub-items (01.1, 01.2, …) interleaved:

  Rubriques  Poids  mai-25 mai-26 juin-26 | moyenne-ann. Mensuel glissement-Ann.
  0 TOUS LES PRODUITS 1 000,0 315,2 355,2 346,3  18,4 -2,5 9,9
  7 Transports        58,8   234,2 254,9 253,5  12,1 -0,5 8,2

Three monthly indices then three inflation columns, so current index = nums[-4],
MoM (mensuel) nums[-2], YoY (glissement annuel) nums[-1]. Functions start with a
leading code digit (0–12); wrapped functions 4 and 5 show only the digit, and
sub-items begin with a dotted code that the number regex swallows, leaving an
empty label — both are handled. Report month is read from the header text.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_BASE_PERIOD = "2016/2017 = 100"
_FR = {"janvier": "01", "fevrier": "02", "février": "02", "mars": "03", "avril": "04",
       "mai": "05", "juin": "06", "juillet": "07", "aout": "08", "août": "08",
       "septembre": "09", "octobre": "10", "novembre": "11", "decembre": "12",
       "décembre": "12"}
_LABELS = {
    "00": "Ensemble (Tous les produits)",
    "01": "Produits alimentaires et boissons non alcoolisées",
    "02": "Boissons alcoolisées et tabac",
    "03": "Articles d'habillement et chaussures",
    "04": "Logement, eau, électricité, gaz et autres combustibles",
    "05": "Ameublement, équipement ménager et entretien courant de la maison",
    "06": "Santé",
    "07": "Transports",
    "08": "Communications",
    "09": "Loisirs et culture",
    "10": "Enseignement",
    "11": "Restaurants et hôtels",
    "12": "Biens et services divers",
}
_NUM = re.compile(r"-?\d+,\d+")
_CODE = re.compile(r"^(\d{1,2})(?:\s|$)")


def _period(text: str) -> str | None:
    m = re.search(r"mois de\s+([a-zûéà]+)\s+(20\d\d)", text.lower()) \
        or re.search(r"\ben\s+([a-zûéà]+)\s+(20\d\d)", text.lower())
    if m and m.group(1) in _FR:
        return f"{m.group(2)}-{_FR[m.group(1)]}"
    return None


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    text = "\n".join(pages)
    period = _period(text)
    if not period:
        raise ValueError("Burundi IPC: report month not found")
    table = next((t for t in pages
                  if "tous les produits" in t.lower() and "transport" in t.lower()), text)

    picked = {}
    for ln in table.splitlines():
        nums = _NUM.findall(ln)
        if len(nums) < 6:                          # 3 indices + 3 inflation columns
            continue
        own = ln[:_NUM.search(ln).start()].strip()
        m = _CODE.match(own)
        if not m:                                  # sub-item (dotted code) or aggregate
            continue
        code = f"{int(m.group(1)):02d}"
        if code not in _LABELS or code in picked:
            continue
        vals = [float(x.replace(",", ".")) for x in nums]
        picked[code] = (vals[-4], vals[-2], vals[-1])

    missing = [c for c in _LABELS if c not in picked]
    if missing:
        raise ValueError(f"Burundi IPC incomplete: missing {missing}")

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
