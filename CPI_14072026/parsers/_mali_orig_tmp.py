"""Parser for the Mali INSTAT IHPC monthly note PDF (Tier 3).

Mali (INSTAT) publishes the WAEMU harmonised CPI (IHPC, base 2023 = 100) as a
monthly PDF. Its national division table reads cleanly as text — one row per
COICOP-2018 division plus an 'INDICE NATIONAL' all-items row:

  Pondération  juin.-25  mars.-26  avr.-26  mai.-26  juin.-26   1m  3m  12m
  INDICE NATIONAL  10 000  105,9  105,7  106,2  107,0  108,0    …
  01 Produits alimentaires …  4464  105,5  104,6  104,8  106,6  109,4  …

Each row is <code> <label> <weight> <N monthly indices> <3 variations>. We read
the header's month tokens to get the N periods (newest last), then the index for
every dated column of each division (codes 01..13) and the all-items row (00).
So one note yields several months. French comma decimals; the national weight
'10 000' carries a thousands space, normalised before parsing. Labels from a
fixed COICOP map (the PDF labels wrap across lines).
"""
from __future__ import annotations
import re
import unicodedata
import pdfplumber
import pandas as pd

from .togo_inseed import _DIVISIONS      # Roman -> (code, French label)

_BASE_PERIOD = "2023 = 100"
_CODE_LABEL = {code: label for code, label in _DIVISIONS.values()}
_MONTHS = {"janv": "01", "jan": "01", "fevr": "02", "fev": "02", "mars": "03",
           "avr": "04", "mai": "05", "juin": "06", "juil": "07", "aout": "08",
           "sept": "09", "sep": "09", "oct": "10", "nov": "11", "dec": "12"}
_MONTH_TOK = re.compile(r"([A-Za-zûéèêàâäîïôùç]+)\.?\s*-\s*(\d{2})")
_NUM = r"-?\d+(?:,\d+)?"
_ROW = re.compile(r"^(\d{2})\s+(.+?)\s+((?:" + _NUM + r"\s+)+" + _NUM + r")\s*$")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _period(mon: str, yy: str) -> str | None:
    code = _MONTHS.get(_norm(mon)[:4]) or _MONTHS.get(_norm(mon)[:3])
    return f"20{yy}-{code}" if code else None


def _nums(s: str) -> list[float]:
    # join thousands spaces ('10 000' -> '10000') but not decimals ('105,9')
    s = re.sub(r"(\d)\s(\d{3})(?!,)", r"\1\2", s)
    return [float(t.replace(",", ".")) for t in re.findall(_NUM, s)]


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        lines = "\n".join((p.extract_text() or "") for p in pdf.pages).splitlines()

    periods = None
    for ln in lines:
        toks = [p for m in _MONTH_TOK.finditer(ln) if (p := _period(*m.groups()))]
        if len(toks) >= 3:
            periods = toks
            break
    if not periods:
        raise ValueError("Mali IHPC: month header not found")
    n = len(periods)

    records, seen = [], set()
    for ln in lines:
        s = ln.strip()
        m = _ROW.match(s)
        if m and 1 <= int(m.group(1)) <= 13:
            code, nums = f"{int(m.group(1)):02d}", _nums(m.group(3))
        elif re.match(r"indice national|indice global|ensemble", s, re.I):
            code, nums = "00", _nums(s)
        else:
            continue
        if code in seen or len(nums) < 1 + n:      # weight + N indices
            continue
        seen.add(code)
        label = "All items" if code == "00" else _CODE_LABEL.get(code, "")
        for k, period in enumerate(periods):
            records.append((code, label, period, round(nums[1 + k], 4)))

    divisions = {c for c, *_ in records if c != "00"}
    if "00" not in seen or len(divisions) < 12:
        raise ValueError(f"Mali IHPC table incomplete: got {sorted(seen)}")

    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "value"])
    out = out.drop_duplicates(["coicop_code", "period"])
    out["geography"] = "National"
    out["measure"] = "index"
    out["unit"] = "Index"
    out["base_period"] = _BASE_PERIOD
    out["frequency"] = "monthly"
    return out
