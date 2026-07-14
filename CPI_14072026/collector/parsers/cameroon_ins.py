"""Parser for the Cameroon INS monthly price note PDF (Tier 3).

INS Cameroun publishes a monthly 'Note sur les prix' (the CEMAC harmonised IHPC).
Its 'Tableau 2' lists, by COICOP function, ~12 monthly index columns followed by
1-/3-/12-month % variations. pdfplumber can't extract it as a grid (many columns,
wrapped labels), so we reconstruct rows from word coordinates:

  * words are grouped into visual rows by their y-position;
  * a row with >=12 numbers is a data row; the trailing three numbers are the
    variations, so the current index is nums[-4], MoM nums[-3], YoY nums[-1];
  * some division labels wrap onto their own (number-less) rows, so a label is
    carried forward to the next data row that has none of its own.

Division vs sub-group is resolved by keyword + first-match (divisions precede
their sub-groups), giving the 12 COICOP functions + 'INDICE GENERAL' (00). We
emit index + inflation_mom + inflation_yoy for the report month (from the title).
"""
from __future__ import annotations
import re
import unicodedata
import pdfplumber
import pandas as pd

_MONTHS = {"janvier": "01", "fevrier": "02", "mars": "03", "avril": "04",
           "mai": "05", "juin": "06", "juillet": "07", "aout": "08",
           "septembre": "09", "octobre": "10", "novembre": "11", "decembre": "12"}
_TITLE = re.compile(r"(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|"
                    r"septembre|octobre|novembre|d[eé]cembre)\s+(20\d\d)", re.IGNORECASE)
# (code, canonical label, keyword on the normalised label) — divisions precede
# their sub-groups in the table, so first match wins.
_DIVS = [
    ("00", "All items", "indice general"),
    ("01", "Produits alimentaires et boissons non alcoolisées", "aliment"),
    ("02", "Boissons alcoolisées, tabac et stupéfiants", "tabac"),
    ("03", "Habillement et chaussures", "habillement"),
    ("04", "Logement, eau, gaz, électricité et autres combustibles", "logement"),
    ("05", "Meubles, articles de ménage et entretien courant du foyer", "meubles"),
    ("06", "Santé", "sante"),
    ("07", "Transports", "transport"),
    ("08", "Communications", "communication"),
    ("09", "Loisirs et culture", "loisirs"),
    ("10", "Enseignement", "enseignement"),
    ("11", "Restaurants et hôtels", "restaurant"),
    ("12", "Biens et services divers", "biens et services divers"),
]
_IS_NUM = re.compile(r"-?\d+(?:,\d+)?%?$")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _val(tok: str) -> float:
    return float(tok.replace(",", ".").replace("%", ""))


def _code(label: str):
    n = _norm(label)
    for code, clabel, kw in _DIVS:
        if kw in n:
            return code, clabel
    return None


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        period = None
        m = _TITLE.search(" ".join((p.extract_text() or "") for p in pdf.pages[:2]))
        if m:
            period = f"{m.group(2)}-{_MONTHS[_norm(m.group(1))]}"
        # the IHPC table is the page with the most numeric words
        page = max(pdf.pages, key=lambda p: len(re.findall(r"\d,\d", p.extract_text() or "")))
        words = page.extract_words()
    if not period:
        raise ValueError("Cameroon note: report month not found")

    rows = {}
    for w in words:
        rows.setdefault(round(w["top"]), []).append(w)
    merged = []
    for k in sorted(rows):
        if merged and k - merged[-1][0] <= 3:
            merged[-1][1].extend(rows[k])
        else:
            merged.append([k, list(rows[k])])

    picked, pending = {}, ""
    for _, ws in merged:
        ws = sorted(ws, key=lambda w: w["x0"])
        nums = [w["text"] for w in ws if _IS_NUM.match(w["text"])]
        labs = " ".join(w["text"] for w in ws if not _IS_NUM.match(w["text"])).strip()
        if len(nums) >= 12:
            label = labs or pending
            pending = ""
            hit = _code(label)
            if hit and hit[0] not in picked and len(nums) >= 4:
                picked[hit[0]] = (hit[1], _val(nums[-4]), _val(nums[-3]), _val(nums[-1]))
        elif labs:
            pending = (pending + " " + labs).strip() if pending else labs

    missing = [c for c, _, _ in _DIVS if c not in picked]
    if missing:
        raise ValueError(f"Cameroon IHPC table incomplete: missing {missing}")

    records = []
    for code, (label, idx, mom, yoy) in picked.items():
        records.append((code, label, period, "index", idx, "Index", "2022 = 100"))
        records.append((code, label, period, "inflation_mom", mom, "percent", ""))
        records.append((code, label, period, "inflation_yoy", yoy, "percent", ""))
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
