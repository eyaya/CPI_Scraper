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
# A month word in a filename or title; prefixes, because INS abbreviates
# freely ('Oct', 'Sept', 'Juil', 'Fev'; 'Fvrier', 'Aot', 'Dcembre' with the accent lost).
_MONTH_WORDS = [("janv", "01"), ("jan", "01"), ("fev", "02"), ("fév", "02"),
                ("fvr", "02"), ("mars", "03"), ("avr", "04"), ("mai", "05"),
                ("juin", "06"), ("juil", "07"), ("aou", "08"), ("aoû", "08"), ("aot", "08"),
                ("sep", "09"), ("oct", "10"), ("nov", "11"), ("dec", "12"), ("dcem", "12"),
                ("déc", "12")]
_MONTH_RX = re.compile(
    r"(?<![a-zéû])(" + "|".join(w for w, _ in _MONTH_WORDS) + r")[a-zéû]*"
    r"[-_ ]*(?:guin[a-zé]*[-_ ]*)?(20\d\d)")
_TITLE_RX = re.compile(r"\(INHPC\)\s*[–-]\s*([A-Za-zÉÛéû]+)\s*(20\d\d)")
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


def _month(word: str, year: str) -> str | None:
    w = word.lower()
    for key, mm in _MONTH_WORDS:
        if w.startswith(key):
            return f"{year}-{mm}"
    return None


def _period(path: str) -> str | None:
    m = _MONTH_RX.search(os.path.basename(path).lower())
    return _month(m.group(1), m.group(2)) if m else None


def _code(label: str):
    low = label.lower()
    for c, lab, kw in _DIVS:
        if kw in low:
            return c, lab
    return None


def _nums(ln: str):
    return [float(x.replace(",", ".")) for x in _NUM.findall(ln)]


def _parse_issue(pdf_path: str) -> pd.DataFrame:
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
    # the page footer names the month too; a file whose two disagree is refused
    t = _TITLE_RX.search(text)
    if t and _month(t.group(1), t.group(2)) not in (None, period):
        raise ValueError(f"Guinea INHPC: filename month {period} but the note "
                         f"says {t.group(1)} {t.group(2)}")

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


# BACK ISSUES (added 2026-10-12): the newest note plus the descriptor's
# `extra_urls`, newest issue winning on a shared month. Only the report month
# is read from each: the header's year-ago / earlier-month labels carry
# publisher typos ('Jan-24' over a February-2025 column), so those columns are
# not dated from it. Notes whose table is an image fail and are skipped.
from . import ihpc_note_pdf as _R          # noqa: E402
parse = _R.over_issues(_parse_issue, "guinea_ins")
