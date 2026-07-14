"""Parser for the INSEED Chad INHPC bulletin PDF (Tier 3).

Chad publishes the CEMAC harmonised CPI (INHPC, base 2022). 'Tableau 2' lists the
12 COICOP-1999 functions (labelled with Roman numerals I–XII) + INDICE GLOBAL,
with detailed sub-items (I.1, I.1.1, …) interleaved:

  Libellé      Pond.   <idx m-12> … <idx current>   1m   3m   12m
  INDICE GLOBAL 10000  106,4 103,4 103,3 102,8 104,0  1,2  0,5 -2,3
  VII Transports 713,5 124,9 126,0 125,1 124,8 124,9  0,1 -0,8  0,0

Each function row carries (weight +) five monthly indices then 1-/3-/12-month
variations, so current index = nums[-4], MoM nums[-3], YoY nums[-1]. Functions are
identified by a leading Roman numeral (not followed by a dot, which marks a
sub-item). The report month is the latest 'mois-YY' token in the table. Base 2022.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_BASE_PERIOD = "2022 = 100"
_ROMAN = {"I": "01", "II": "02", "III": "03", "IV": "04", "V": "05", "VI": "06",
          "VII": "07", "VIII": "08", "IX": "09", "X": "10", "XI": "11", "XII": "12"}
_LABELS = {
    "00": "Indice global (Ensemble)",
    "01": "Produits alimentaires et boissons non alcoolisées",
    "02": "Boissons alcoolisées, tabacs et stupéfiants",
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
_FR3 = {"jan": "01", "fev": "02", "fév": "02", "mar": "03", "avr": "04", "mai": "05",
        "jui": "06", "jul": "07", "aou": "08", "aoû": "08", "sep": "09", "oct": "10",
        "nov": "11", "dec": "12", "déc": "12"}
_NUM = re.compile(r"-?\d+,\d+")
# a leading Roman numeral not part of a dotted sub-code (I.1) — longest first
_RE_ROMAN = re.compile(r"^(XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)(?=\s|$)")
_RE_MONTH = re.compile(r"\b(janv?|f[eé]vr?|mars|avr|mai|juin|juil|ao[uû]t?|sept?|oct|nov|d[eé]c)[a-zûéà]*[-\s](\d{2})\b", re.I)


def _period(table: str) -> str | None:
    best = None
    for word, yy in _RE_MONTH.findall(table):
        mm = _FR3.get(word.lower()[:3])
        if not mm:
            continue
        # 'juil' is July, not June — disambiguate the shared 'jui' prefix
        if word.lower().startswith("juil"):
            mm = "07"
        key = (2000 + int(yy), int(mm))
        if best is None or key > best[0]:
            best = (key, f"{2000 + int(yy)}-{mm}")
    return best[1] if best else None


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    table = next((t for t in pages
                  if "indice global" in t.lower() and "transport" in t.lower()), "\n".join(pages))
    period = _period(table)
    if not period:
        raise ValueError("Chad INHPC: report month not found")

    picked = {}
    for ln in table.splitlines():
        nums = _NUM.findall(ln)
        if len(nums) < 8:                          # 5 indices + 3 variations
            continue
        own = ln[:_NUM.search(ln).start()].strip()
        if own.upper().startswith("INDICE GLOBAL") and "10000" in own:
            code = "00"                            # the Tableau 2 row (has the 10000 weight)
        else:
            m = _RE_ROMAN.match(own)
            code = _ROMAN.get(m.group(1)) if m else None
        if not code or code in picked:
            continue
        vals = [float(x.replace(",", ".")) for x in nums]
        picked[code] = (vals[-4], vals[-3], vals[-1])

    missing = [c for c in _LABELS if c not in picked]
    if missing:
        raise ValueError(f"Chad INHPC incomplete: missing {missing}")

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
