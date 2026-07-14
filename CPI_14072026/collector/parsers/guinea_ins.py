"""Parser for the Institut National de la Statistique (Guinea) INHPC note PDF (Tier 3).

Guinea publishes a harmonised CPI (INHPC, base 100 en 2019) using the UEMOA
methodology. 'Tableau 2 : Evolution … par fonction' is one row per COICOP-1999
function (Roman I–XII) + INDICE GLOBAL:

  Libellé  Poids  <idx m-12> <idx m-2> <idx m-1> <idx current>  <M%>  <Y%>  <contrib>
  INDICE GLOBAL 10 000 155,2 162,8 163,3 163,5 0,1 5,4 0,1

Numbers use comma decimals; the Poids column is an integer (often with a
thousands space, '10 000'), so matching only comma-decimals drops it and the
four monthly indices become nums[0..3]. Front-anchored: current index = nums[3],
MoM nums[4], YoY nums[5]. Function labels wrap across up to three lines (label,
Roman numeral, remainder) so a label is carried forward. Base 2019 = 100.
"""
from __future__ import annotations
import os
import re
import pdfplumber
import pandas as pd

_BASE_PERIOD = "2019 = 100"
_FR_MONTHS = {"janv": "01", "fevr": "02", "fév": "02", "mars": "03", "avri": "04",
              "mai": "05", "juin": "06", "juil": "07", "aout": "08", "aoû": "08",
              "sept": "09", "octo": "10", "nove": "11", "dece": "12", "déce": "12"}
# (code, label, keyword) — first match wins, checked in this order
_DIVS = [
    ("00", "Indice global (Ensemble)", "indice global"),
    ("01", "Produits alimentaires et boissons non alcoolisées", "aliment"),
    ("02", "Boissons alcoolisées, tabacs et stupéfiants", "tabac"),
    ("03", "Articles d'habillement et chaussures", "habillement"),
    ("04", "Logement, eau, gaz, électricité et autres combustibles", "logement"),
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


def _period(path: str) -> str | None:
    base = os.path.basename(path).lower()
    for key, mm in _FR_MONTHS.items():
        if re.search(key + r"[-_ ]*20\d\d", base):
            yr = re.search(key + r"[-_ ]*(20\d\d)", base).group(1)
            return f"{yr}-{mm}"
    return None


def _code(label: str):
    low = label.lower()
    for c, lab, kw in _DIVS:
        if kw in low:
            return c, lab
    return None


def _nums(ln: str):
    return [float(x.replace(",", ".")) for x in _NUM.findall(ln)]


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    # 'Tableau 2 … par fonction' is the national-level table; take the first page
    # carrying it so regional / secondary-nomenclature tables can't shadow a code.
    text = next((t for t in pages
                 if "par fonction" in t.lower() and "indice global" in t.lower()),
                "\n".join(pages))
    period = _period(pdf_path)
    if not period:
        raise ValueError("Guinea INHPC: report month not found in filename")

    picked, pending = {}, ""
    for ln in text.splitlines():
        nums = _nums(ln)
        m = _NUM.search(ln)
        label_part = ln[:m.start()].strip() if m else ln.strip()
        # strip a leading Roman-numeral marker so it doesn't pollute the label
        label_part = re.sub(r"^(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)\b", "", label_part).strip()
        if len(nums) >= 6:                        # 4 monthly indices + MoM + YoY (+ contrib)
            hit = _code((pending + " " + label_part).strip())
            pending = ""
            if hit and hit[0] not in picked:
                picked[hit[0]] = (hit[1], nums[3], nums[4], nums[5])
        elif label_part:
            pending = (pending + " " + label_part).strip()

    missing = [c for c, _, _ in _DIVS if c not in picked]
    if missing:
        raise ValueError(f"Guinea INHPC incomplete: missing {missing}")

    records = []
    for code, (label, idx, mom, yoy) in picked.items():
        records.append((code, label, period, "index", round(idx, 4), "Index", _BASE_PERIOD))
        records.append((code, label, period, "inflation_mom", round(mom, 4), "percent", ""))
        records.append((code, label, period, "inflation_yoy", round(yoy, 4), "percent", ""))
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
