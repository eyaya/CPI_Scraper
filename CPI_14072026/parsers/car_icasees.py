"""Parser for the ICASEES (Central African Republic) IHPC bulletin PDF (Tier 3).

CAR publishes the CEMAC harmonised CPI (IHPC, base 2019). The national table lists
the 12 COICOP-1999 functions + INDICE NATIONAL, with detailed sub-items (Céréales,
Pains, …) interleaved between functions and the table spanning two pages:

  N°  Libellé  Pond.  <idx m-13> <idx m-3> <idx m-2> <idx m-1> <idx current>  1m 3m 12m
      INDICE NATIONAL 10000 … 115,9 118,3 119,7  1,2 4,6 4,1
  3   Articles d'habillement et chaussures … 111,1 113,5 114,4  0,8 3,1 2,6

Eight comma-decimal numbers per function row (five monthly indices + three
variations), so current index = nums[-4], MoM nums[-3], YoY nums[-1]. Function
labels wrap around the number row and some carry only an N° digit, so a number row
whose own label is empty or a bare digit is matched on a prev+own+next window;
rows with a real own label (the sub-items) are matched on that label alone and so
never collide with a function keyword. Base 2019 = 100.

BACK SERIES (2026-10-14). ICASEES also posts a monthly long table,
'Indice des prix à la consommation (IHPC) mensuel de 2015-2026'
(JD_ODP_IPC_Mensuel_National_RCA_ODP1.0.xlsx), listed as an `extra_url` with
the back bulletins. `parse` reads the bulletin(s) and the workbook through
`ihpc_note_pdf.read_many`:

  * 2020M1 on: sheet 'Données', IND1 (INDICE GLOBAL -> 00) and IND2-IND13
    (functions 01-12), base 2019 = 100, values as given.
  * 2015M1-2019M12: sheet 'Archive_Base1981_Brute' -- the ORIGINAL published
    old-base (1981 = 100) levels. The 'Données' cells for those years are NOT
    read: the workbook's own notes say they were divided by the 4,12919 linking
    coefficient (cells marked as computed) -- chained values, which we never
    take. base_period says which base each row is in.
  * IND14 'Inflation' is not read: the sheet does not say which rate it is,
    and it matches neither the month-on-month nor the year-on-year change of
    IND1 (2025M7: 2,15 vs 0,3 and 0,4).

The workbook carries index levels only. Where a bulletin prints the same
month, the BULLETIN wins (its issue date sorts after the workbook's), so rows
already emitted from bulletins are unchanged; the workbook's 2020+ values agree
with the bulletins to their one printed decimal.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_BASE_PERIOD = "2019 = 100"
_FR = {"janvier": "01", "fevrier": "02", "février": "02", "mars": "03", "avril": "04",
       "mai": "05", "juin": "06", "juillet": "07", "aout": "08", "août": "08",
       "septembre": "09", "octobre": "10", "novembre": "11", "decembre": "12",
       "décembre": "12"}
# (code, canonical label, keyword) — first match wins, checked in this order
_DIVS = [
    ("00", "Indice national (Ensemble)", "indice national"),
    ("01", "Produits alimentaires et boissons non alcoolisées", "produits alimentaires et boissons"),
    ("02", "Boissons alcoolisées, tabacs et stupéfiants", "boissons alcool"),
    ("03", "Articles d'habillement et chaussures", "habillement"),
    ("04", "Logement, eau, gaz, électricité et autres combustibles", "logement"),
    ("05", "Meubles, articles de ménage et entretien courant de la maison", "meubles"),
    ("06", "Santé", "sant"),
    ("07", "Transports", "transport"),
    ("08", "Communication", "communication"),
    ("09", "Loisirs et culture", "loisirs"),
    ("10", "Enseignement", "enseignement"),
    ("11", "Restaurants et hôtels", "restaurant"),
    ("12", "Biens et services divers", "biens et services divers"),
]
_NUM = re.compile(r"-?\d+,\d+")


def _period(text: str) -> str | None:
    m = re.search(r"bulletin mensuel d[e'’\s]+([a-zûéà]+)\s+(20\d\d)", text.lower())
    if m and m.group(1) in _FR:
        return f"{m.group(2)}-{_FR[m.group(1)]}"
    return None


def _code(label: str):
    low = label.lower()
    for c, lab, kw in _DIVS:
        if kw in low:
            return c, lab
    return None


_WB_CODES = {f"IND{i}": f"{i - 1:02d}" for i in range(1, 14)}


def _read_workbook(path: str) -> pd.DataFrame:
    def sheet(name, first, last, base):
        d = pd.read_excel(path, sheet_name=name, header=None)
        head = [str(v).strip() for v in d.iloc[0]]
        if head[:3] != ["Code", "Sous-catégorie", "Indicateur"]:
            raise ValueError(f"CAR workbook: unexpected header in {name!r}: {head[:4]}")
        recs = []
        for _, row in d.iloc[1:].iterrows():
            code = _WB_CODES.get(str(row[0]).strip())
            if not code:
                continue
            label = " ".join(str(row[2]).split())
            for j, col in enumerate(head):
                m = re.fullmatch(r"(20\d\d)M(\d{1,2})", col)
                if not m or pd.isna(row[j]):
                    continue
                per = f"{m.group(1)}-{int(m.group(2)):02d}"
                if first <= per <= last:
                    recs.append((code, label, per, "index", round(float(row[j]), 4),
                                 "Index", base))
        return recs

    recs = (sheet("Archive_Base1981_Brute", "2015-01", "2019-12", "1981 = 100")
            + sheet("Données", "2020-01", "2099-12", _BASE_PERIOD))
    codes = {r[0] for r in recs}
    if codes != set(_WB_CODES.values()):
        raise ValueError(f"CAR workbook: functions missing {sorted(set(_WB_CODES.values()) - codes)}")
    out = pd.DataFrame.from_records(
        recs, columns=["coicop_code", "coicop_label", "period", "measure",
                       "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    out["_issue"] = "0000"            # any bulletin printing the month wins
    return out


def _read_any(path: str) -> pd.DataFrame:
    return _read_workbook(path) if path.lower().endswith(".xlsx") else _parse_issue(path)


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    from .ihpc_note_pdf import read_many
    return read_many([pdf_path, *(extras or [])], _read_any, "car_icasees")


def _parse_issue(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    text = "\n".join(pages)
    period = _period(text)
    if not period:
        raise ValueError("CAR IHPC: report month not found in bulletin text")

    lines = text.splitlines()

    def label_only(i):
        return lines[i].strip() if 0 <= i < len(lines) and not _NUM.search(lines[i]) else ""

    picked = {}
    for i, ln in enumerate(lines):
        nums = _NUM.findall(ln)
        if len(nums) < 8:                          # 5 monthly indices + 3 variations
            continue
        own = ln[:_NUM.search(ln).start()].strip()
        # a real own label = a sub-item (match on it alone); empty / bare-N° = wrapped function
        context = own if (own and not re.fullmatch(r"\d+", own)) \
            else f"{label_only(i-1)} {own} {label_only(i+1)}"
        hit = _code(context)
        if hit and hit[0] not in picked:
            vals = [float(x.replace(",", ".")) for x in nums]
            picked[hit[0]] = (hit[1], vals[-4], vals[-3], vals[-1])

    missing = [c for c, _, _ in _DIVS if c not in picked]
    if missing:
        raise ValueError(f"CAR IHPC incomplete: missing {missing}")

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
    out["_issue"] = period
    return out
