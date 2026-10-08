"""Parser for the INSTAD Djibouti IPC monthly bulletin PDF (Tier 3).

Djibouti (INSTAD) publishes the AFRISTAT-style CPI (IPC, base 100 en 2022 since
the September 2023 issue) as a monthly PDF. 'Tableau 2' is the national table:
one row per COICOP-1999 function, numbered 1..12, with detailed consumption
items (Céréales non transformées, Pains, Bœuf, …) interleaved between them, and
a 'GLOBAL' all-items row at the end:

  <n> <LABEL> <weight> <idx m-12> <idx m-3> <idx m-2> <idx m-1> <idx m> <1m> <3m> <12m> <contrib>
  1 ALIMENTATION ET BOISSONS NON ALCOOLISÉES 4 619 102,8 105,1 106,6 108,8 108,3 -0,5 3,1 5,3 -0,3
  GLOBAL 10 000 102,8 104,5 105,6 106,9 106,7 -0,2 2,0 3,8 -0,2

The function number IS the COICOP division code, so rows need no label map and
the interleaved items — which carry no leading number — drop out on their own.

The column headers are typeset ROTATED 90° (each is a bottom-to-top glyph run),
so they arrive scrambled in the text layer ('5 iu 2 - j r 6 v a 2 - ia …'). We
recover them from the char matrices instead: rotated chars grouped by x band and
read bottom-to-top give 'juil-25 | avr-26 | mai-26 | juin-26 | juil-26', i.e.
the periods the five index columns carry — so one bulletin yields several months
rather than only its report month. The three variations and the contribution are
for the report month (the last index column) only; we emit index +
inflation_mom (1 mois) + inflation_yoy (12 mois). The 3-month variation and the
contribution have no measure in the CPI schema and are dropped.

French comma decimals; weights carry a thousands space ('4 619', '10 000'),
joined before parsing. Labels kept as published.
"""
from __future__ import annotations
import re
import unicodedata
import pdfplumber
import pandas as pd

_BASE_PERIOD = "2022 = 100"
_GEOGRAPHY = "National"
_ALL_ITEMS = "GLOBAL"

_MONTHS = {"janv": "01", "jan": "01", "fevr": "02", "fev": "02", "mars": "03",
           "avr": "04", "mai": "05", "juin": "06", "juil": "07", "aout": "08",
           "sept": "09", "sep": "09", "octo": "10", "oct": "10", "nove": "11",
           "nov": "11", "dece": "12", "dec": "12"}
_MONTH_TOK = re.compile(r"^([A-Za-zéûôàè]{3,5})\.?-(\d{2})$")
_NUM = r"-?\d+(?:,\d+)?"
_ROW = re.compile(r"^(\d{1,2})\s+(.+?)\s+((?:" + _NUM + r"\s+)+" + _NUM + r")$")
_ALL_ROW = re.compile(r"^" + _ALL_ITEMS + r"\s+((?:" + _NUM + r"\s+)+" + _NUM + r")$", re.I)
_TRAILING = 4          # variations 1m / 3m / 12m + monthly contribution


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _join_thousands(line: str) -> str:
    """'4 619 102,8' -> '4619 102,8': close the weight's thousands space without
    swallowing the space that separates two decimal values."""
    return re.sub(r"(?<=\d)\s(?=\d{3}(?![\d,]))", "", line)


def _nums(s: str) -> list[float]:
    return [float(t.replace(",", ".")) for t in re.findall(_NUM, s)]


def _rotated_periods(page) -> list[str]:
    """The index columns' periods, read off the rotated column headers: group
    the 90°-rotated chars into x bands and read each band bottom-to-top."""
    rot = [c for c in page.chars
           if abs(c["matrix"][0]) < 0.1 and abs(c["matrix"][1]) > 0.9]
    bands: dict[int, list] = {}
    for c in rot:
        bands.setdefault(round(c["x0"] / 5), []).append(c)

    periods = []
    for key in sorted(bands):
        text = "".join(c["text"] for c in
                       sorted(bands[key], key=lambda c: -c["top"])).strip()
        m = _MONTH_TOK.match(text)
        if not m:
            continue
        code = _MONTHS.get(_norm(m.group(1))[:4]) or _MONTHS.get(_norm(m.group(1))[:3])
        if code:
            periods.append(f"20{m.group(2)}-{code}")
    return periods


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            periods = _rotated_periods(page)
            if len(periods) < 3:
                continue
            lines = [_join_thousands(ln.strip())
                     for ln in (page.extract_text() or "").splitlines()]
            n = len(periods)

            rows = {}
            for ln in lines:
                m = _ROW.match(ln)
                if m and 1 <= int(m.group(1)) <= 12:
                    code, label, nums = (f"{int(m.group(1)):02d}", m.group(2).strip(),
                                         _nums(m.group(3)))
                elif (a := _ALL_ROW.match(ln)):
                    code, label, nums = "00", _ALL_ITEMS, _nums(a.group(1))
                else:
                    continue
                if code in rows or len(nums) != 1 + n + _TRAILING:
                    continue                       # weight + N indices + trailing
                rows[code] = (label, nums)

            if len(rows) == 13:                    # GLOBAL + the 12 functions
                break
        else:
            raise ValueError("INSTAD Djibouti: Tableau 2 not found in the bulletin")

    report = periods[-1]
    records = []
    for code, (label, nums) in rows.items():
        for k, period in enumerate(periods):
            records.append((code, label, period, "index",
                            round(nums[1 + k], 4), "Index", _BASE_PERIOD))
        records.append((code, label, report, "inflation_mom",
                        round(nums[1 + n], 4), "percent", ""))
        records.append((code, label, report, "inflation_yoy",
                        round(nums[3 + n], 4), "percent", ""))

    out = pd.DataFrame.from_records(
        records,
        columns=["coicop_code", "coicop_label", "period", "measure", "value",
                 "unit", "base_period"])
    out["geography"] = _GEOGRAPHY
    out["frequency"] = "monthly"
    return out
