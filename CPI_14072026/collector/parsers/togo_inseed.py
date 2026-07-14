"""Parser for the Togo INSEED IHPC monthly note PDF (Tier 3).

Togo (INSEED) publishes the WAEMU harmonised CPI (IHPC, base 2023 = 100) as a
monthly PDF — no série-de-données Excel on the site — so, unlike Senegal/Benin,
this is a Tier-3 parse. The note's division table (spanning the first two pages)
lists each COICOP-2018 division by Roman numeral:

  <Roman> <label> <weight> <idx ...> <idx current> | <1 mois> <3 mois> <12 mois>
  I Produits alimentaires ... 2797 116,0 108,1 109,0 110,1 112,8  2,4 4,3 -2,8

and 'Tableau 3' carries the 'Global' all-items row in the same shape. Whatever
the number of index columns shown, the trailing three numbers are the 1-/3-/12-
month % variations, so the current index is nums[-4], MoM nums[-3], YoY nums[-1].
We emit index + inflation_mom + inflation_yoy for the report month (one PDF =
one month; history accumulates across monthly runs). Numbers use French comma
decimals. Division labels are supplied from a fixed COICOP-2018 map (the PDF
labels wrap across lines), All-items = 'Global' (00).
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_BASE_PERIOD = "2023 = 100"

# Roman numeral -> (COICOP-2018 code, French label as published by INSEED)
_ROMAN = ["XIII", "XII", "XI", "X", "IX", "VIII", "VII", "VI", "V", "IV", "III", "II", "I"]
_DIVISIONS = {
    "I": ("01", "Produits alimentaires et boissons non alcoolisées"),
    "II": ("02", "Boissons alcoolisées, tabac et stupéfiants"),
    "III": ("03", "Articles d'habillement et chaussures"),
    "IV": ("04", "Logement, eau, gaz, électricité et autres combustibles"),
    "V": ("05", "Meubles, articles de ménage et entretien courant du foyer"),
    "VI": ("06", "Santé"),
    "VII": ("07", "Transports"),
    "VIII": ("08", "Information et Communication"),
    "IX": ("09", "Loisirs et culture"),
    "X": ("10", "Enseignement"),
    "XI": ("11", "Restaurants et services d'hébergement"),
    "XII": ("12", "Assurance et services financiers"),
    "XIII": ("13", "Soins personnels, protection sociale et biens divers"),
}
_ROMAN_RE = re.compile(r"^(" + "|".join(_ROMAN) + r")\b")
_NUM_RE = re.compile(r"-?\d+(?:,\d+)?")
_MONTHS = {"janv": "01", "jan": "01", "févr": "02", "févr": "02", "fevr": "02", "fev": "02",
           "mars": "03", "avr": "04", "mai": "05", "juin": "06", "juil": "07",
           "août": "08", "aout": "08", "sept": "09", "sep": "09", "oct": "10",
           "nov": "11", "déc": "12", "dec": "12"}
_MONTH_TOKEN = re.compile(r"([A-Za-zàâäéèêëîïôûùç]+)-(\d{2})")


def _nums(s: str) -> list[float]:
    return [float(t.replace(",", ".")) for t in _NUM_RE.findall(s)]


def _report_period(text: str) -> str:
    """Latest '<mois>-YY' token in the note = the report month (YYYY-MM)."""
    best = None
    for mon, yy in _MONTH_TOKEN.findall(text):
        code = _MONTHS.get(mon.lower())
        if not code:
            continue
        key = (2000 + int(yy), code)
        if best is None or key > best:
            best = key
    if best is None:
        raise ValueError("could not determine report month from note")
    return f"{best[0]}-{best[1]}"


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    lines = text.splitlines()
    period = _report_period(text)

    rows = {}   # code -> (label, current_index, mom, yoy)

    def take(code, label, nums):
        if len(nums) >= 5 and code not in rows:      # weight + >=1 index + 3 variations
            rows[code] = (label, nums[-4], nums[-3], nums[-1])

    for ln in lines:
        s = ln.strip()
        m = _ROMAN_RE.match(s)
        if m:
            code, label = _DIVISIONS[m.group(1)]
            take(code, label, _nums(s))
        elif s.lower().startswith("global"):
            take("00", "All items", _nums(s))

    missing = [c for c in list(_DIVISIONS.values()) if c[0] not in rows]
    if "00" not in rows or missing:
        raise ValueError(f"IHPC table incomplete: got {sorted(rows)} for {period}")

    records = []
    for code, (label, idx, mom, yoy) in rows.items():
        records.append((code, label, period, "index", idx, "Index", _BASE_PERIOD))
        records.append((code, label, period, "inflation_mom", mom, "percent", ""))
        records.append((code, label, period, "inflation_yoy", yoy, "percent", ""))

    out = pd.DataFrame.from_records(
        records,
        columns=["coicop_code", "coicop_label", "period", "measure", "value",
                 "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
