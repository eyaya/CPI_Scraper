"""Parser for the Niger INS IHPC monthly note PDF (Tier 3).

Niger (INS) publishes the WAEMU harmonised CPI (IHPC, base 2023 = 100) as a
monthly PDF. Its 'Tableau 1' national table reads as text, one row per
COICOP-2018 division plus an 'Indice global' all-items row:

  10 000)  Juin-  Mars-  Avril-  Mai-  Juin-   1 mois  3 mois  1 an
  Indice global  10 000  105,2  98,1  98,8  100,3  102,1   1,8  4,0  -2,9
  1 Produits alimentaires …  4 701  110,0  94,8  95,9  99,4  102,8   3,4  8,5  -6,6

Codes are single- or double-digit (1..13); the all-items row is 'Indice global'.
The column headers don't carry the year, so the report month is read from the
title ('… juin 2026 …'). Each row is <code> <label> <weight> <indices…> then
the 1-/3-/12-month variations. Weights carry thousands spaces ('4 701'); French
comma decimals.

ALL FIVE PRINTED MONTHS (added 2026-10-12). The five index columns are the
report month a year earlier, then the last four months. They are dated from
the report month and CHECKED against the header's printed month names; a note
whose header disagrees is refused, not guessed. The report month's MoM and YoY
are emitted as before.

BACK ISSUES. `parse` reads the newest note plus the descriptor's `extra_urls`
and lets the newest issue win on a shared month. Base-2014 notes (to 2024-12)
lay the divisions out differently and are skipped with a message: the index of
a month belongs only to the base current for it (ihpc_note_pdf.REBASE).
"""
from __future__ import annotations
import re
import unicodedata
import pdfplumber
import pandas as pd

from .togo_inseed import _DIVISIONS      # Roman -> (code, French label)

_BASE_PERIOD = "2023 = 100"
_CODE_LABEL = {code: label for code, label in _DIVISIONS.values()}
_FULL_MONTHS = {"janvier": "01", "fevrier": "02", "mars": "03", "avril": "04",
                "mai": "05", "juin": "06", "juillet": "07", "aout": "08",
                "septembre": "09", "octobre": "10", "novembre": "11",
                "decembre": "12"}
_TITLE = re.compile(
    r"(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|"
    r"octobre|novembre|d[eé]cembre)\s+(20\d\d)", re.IGNORECASE)
_NUM = r"-?\d+(?:,\d+)?"
_MON3 = {"jan": "01", "fev": "02", "mar": "03", "avr": "04", "mai": "05",
         "aou": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _nums(s: str) -> list[float]:
    s = re.sub(r"(\d)\s(\d{3})(?!,)", r"\1\2", s)   # join thousands spaces
    return [float(t.replace(",", ".")) for t in re.findall(_NUM, s)]


def _report_period(text: str) -> str:
    m = _TITLE.search(text)
    if not m:
        raise ValueError("Niger IHPC: report month not found in title")
    return f"{m.group(2)}-{_FULL_MONTHS[_norm(m.group(1))]}"


def _shift(period: str, months: int) -> str:
    y, m = int(period[:4]), int(period[5:])
    k = y * 12 + (m - 1) - months
    return f"{k // 12}-{k % 12 + 1:02d}"


def _month_of(word: str) -> str | None:
    w = _norm(word)
    if w.startswith("juin"):
        return "06"
    if w.startswith("juil"):
        return "07"
    return _MON3.get(w[:3])


def _header_months(text: str) -> list[str] | None:
    """The five month names of the index header ('Juin- Mars- ... Juin-')."""
    for ln in text.splitlines():
        words = re.findall(r"([A-Za-zÀ-ÿ]+)\s*-", ln)
        months = [_month_of(w) for w in words]
        if len(months) == 5 and all(months):
            return months
    return None


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """Newest note plus back issues; see the module docstring."""
    from . import ihpc_note_pdf as R
    return R.read_many([pdf_path, *(extras or [])], _parse_issue, "niger_ins")


def _parse_issue(pdf_path: str) -> pd.DataFrame:
    from .ihpc_note_pdf import REBASE
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    period = _report_period(text)
    if period < REBASE:
        raise ValueError(f"Niger IHPC {period}: base-2014 note, layout not read")
    cols = [_shift(period, 12), _shift(period, 3), _shift(period, 2),
            _shift(period, 1), period]
    header = _header_months(text)
    if header != [c[5:] for c in cols]:
        raise ValueError(f"Niger IHPC {period}: header months {header} do not "
                         f"match {[c[5:] for c in cols]}")

    rows = {}   # code -> (label, five indices, mom, yoy)
    misaligned: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        m = re.match(r"^(\d{1,2})\s+(.+)$", s)
        if m and 1 <= int(m.group(1)) <= 13:
            code, nums = f"{int(m.group(1)):02d}", _nums(m.group(2))
            label = _CODE_LABEL.get(code, "")
        elif re.match(r"indice global|indice national|ensemble", s, re.I):
            code, nums, label = "00", _nums(s), "All items"
        else:
            continue
        # weight + 5 indices + 3 variations, exactly
        if code in rows or len(nums) != 9:
            continue
        # A ROW WHOSE INDICES ARE NOT ALL POSITIVE IS MISALIGNED, not data: in
        # eleven 2025-26 notes the education row (10) shifts, putting its
        # variations (-24, -25) in the index columns. Drop that row, loudly;
        # the rest of the table is unaffected.
        if not all(v > 0 for v in nums[1:6]):
            misaligned.append(code)
            continue
        rows[code] = (label, nums[1:6], nums[-3], nums[-1])

    if misaligned:
        print(f"  [niger_ins] {period}: dropped misaligned row(s) {misaligned}")
    missing = [c for c, _ in _DIVISIONS.values()
               if c not in rows and c not in misaligned]
    if "00" not in rows or missing:
        raise ValueError(f"Niger IHPC {period}: table incomplete, got {sorted(rows)}")

    records = []
    for code, (label, five, mom, yoy) in rows.items():
        for per, v in zip(cols, five):
            if per >= REBASE:
                records.append((code, label, per, "index", v, "Index", _BASE_PERIOD))
        records.append((code, label, period, "inflation_mom", mom, "percent", ""))
        records.append((code, label, period, "inflation_yoy", yoy, "percent", ""))

    out = pd.DataFrame.from_records(
        records,
        columns=["coicop_code", "coicop_label", "period", "measure", "value",
                 "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    out["_issue"] = period
    return out
