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

BACK ISSUES (2026-10-13). `parse` reads the newest note plus the back issues
listed as `extra_urls` (INS's WordPress media library holds the national notes
from 2023-05) through `ihpc_note_pdf.read_many`; the newest issue wins on
overlap. Tableau 2 prints a run of consecutive months ending at the report month
(10 in 2023, 12 since). Every printed month's index is emitted, dated backwards
from the report month -- but only when the table's own header names most of
those months (the labels wrap across lines, so a few are split); otherwise only
the report month. MoM/YoY belong to the report month only. Notes that predate
the base-2022 layout (2023-05, 2023-08) or whose table loses a division label
are skipped loudly; their months are reprinted by the next issue.
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


_HDR_MONTH = re.compile(r"(janv|f[eé]v|mars|avr|mai|juin|juil|ao[uû]t|sept|oct|nov|d[eé]c)"
                        r"[a-zéû]*\s?-\s?(\d{2})\b", re.IGNORECASE)
_HDR_MM = {"janv": "01", "fev": "02", "mars": "03", "avr": "04", "mai": "05", "juin": "06",
           "juil": "07", "aout": "08", "sept": "09", "oct": "10", "nov": "11", "dec": "12"}


def _back(period: str, n: int) -> str:
    y, m = int(period[:4]), int(period[5:]) - n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y}-{m:02d}"


def _header_months(text: str) -> set[str]:
    out = set()
    for mon, yy in _HDR_MONTH.findall(text):
        mm = _HDR_MM.get(_norm(mon).lower())
        if mm:
            out.add(f"{2000 + int(yy)}-{mm}")
    return out


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    from .ihpc_note_pdf import read_many
    return read_many([pdf_path, *(extras or [])], _parse_issue, "cameroon_ins")


def _parse_issue(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        period = None
        m = _TITLE.search(" ".join((p.extract_text() or "") for p in pdf.pages[:2]))
        if m:
            period = f"{m.group(2)}-{_MONTHS[_norm(m.group(1))]}"
        # the IHPC table is the page with the most numeric words
        page = max(pdf.pages, key=lambda p: len(re.findall(r"\d,\d", p.extract_text() or "")))
        words = page.extract_words()
        page_text = page.extract_text() or ""
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
                picked[hit[0]] = (hit[1], [_val(x) for x in nums[:-3]],
                                  _val(nums[-3]), _val(nums[-1]))
        elif labs:
            pending = (pending + " " + labs).strip() if pending else labs

    missing = [c for c, _, _ in _DIVS if c not in picked]
    if missing:
        raise ValueError(f"Cameroon IHPC table incomplete: missing {missing}")

    # DATE THE PRINTED MONTHS: a run of n consecutive months ending at the
    # report month, accepted only when the header names most of them.
    n = min(len(v[1]) for v in picked.values())
    window = [_back(period, k) for k in range(n - 1, -1, -1)]
    head = []
    for ln in page_text.splitlines():
        if len(re.findall(r"\d,\d", ln)) >= 8:      # the first data row ends the header
            break
        head.append(ln)
    named = _header_months("\n".join(head))
    if n < 2 or len(set(window) & named) < n - 4:
        window = [period]

    records = []
    for code, (label, idxs, mom, yoy) in picked.items():
        for per, idx in zip(window, idxs[-len(window):]):
            records.append((code, label, per, "index", idx, "Index", "2022 = 100"))
        records.append((code, label, period, "inflation_mom", mom, "percent", ""))
        records.append((code, label, period, "inflation_yoy", yoy, "percent", ""))
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    out["_issue"] = period
    return out
