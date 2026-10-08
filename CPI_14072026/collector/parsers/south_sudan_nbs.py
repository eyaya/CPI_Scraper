"""Parser for the NBS South Sudan CPI monthly release PDF (Tier 3).

South Sudan (NBS) publishes the CPI as a short press release whose three tables
carry everything it discloses, each in a clean text layer:

  Table 1  Overall CPI and Rates of Inflation — the all-items INDEX and monthly
           inflation for every month back to the base month, e.g.
             May-25 189.24 2.30
           so one release yields the whole series of the current base.
  Table 2  Monthly changes by COICOP division — weight and MoM % for the two most
           recent months only. No index levels and no year-on-year by division.
  Table 3  Monthly inflation by geographical area — the same two months' MoM %
           for the ten state capitals, which we emit as `geography` rows.

The release is the rebased series (UNCOICOP 2018, base prices from August 2024,
Aug-24 = 100), computed from the World Bank 2021/22 Household Budget Survey
weights and collected in the ten state capitals. It disseminates only 11 of the
13 divisions — restaurants/accommodation and insurance/financial services are
absent from Table 2 — so we emit what is published rather than filling the gaps.

Only the two months named in the release are available by division, so we check
them rather than assume: the report month comes from the title, the previous
month is derived from it, and both tables' headers must name exactly those two
months in that order or the parse fails. Division labels are mapped by the shared
COICOP-2018 helper; the all-items row of Table 2 is dropped as a duplicate of the
richer Table 1 series.
"""
from __future__ import annotations
import re
import pandas as pd
import pdfplumber

from .. import coicop

_GEOGRAPHY = "National"
_MONTHS = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
           "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
           "nov": "11", "dec": "12"}
_TITLE = re.compile(r"consumer price index for ([a-z]+)\s+(20\d\d)", re.I)
_BASE = re.compile(r"\(base:?\s*([^)]+?)\s*\)", re.I)
# 'May-25 189.24 2.30'
_T1_ROW = re.compile(r"^([A-Za-z]{3})-(\d{2})\s+(\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)$")
# '<label> <weight> <MoM m-1> <MoM m>'
_DATA_ROW = re.compile(
    r"^(.+?)\s+(\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)$")
_T3_HEAD = re.compile(r"([A-Za-z]{3})-(\d{2})")


def _month_name(period: str) -> str:
    """'2025-04' -> 'apr' (the stem both 'Apr-25' and 'April-2025' start with)."""
    return next(k for k, v in _MONTHS.items() if v == period[5:])


def _prev(period: str) -> str:
    y, m = int(period[:4]), int(period[5:])
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def _section(lines: list[str], start: str, end: str | None) -> list[str]:
    """The lines between two captions (end exclusive; to the end if None)."""
    try:
        i = next(k for k, ln in enumerate(lines) if ln.lower().startswith(start))
    except StopIteration:
        raise ValueError(f"South Sudan CPI: '{start}' not found in the release")
    rest = lines[i + 1:]
    if end:
        for k, ln in enumerate(rest):
            if ln.lower().startswith(end):
                return rest[:k]
    return rest


def _check_months(header: str, periods: list[str], table: str) -> None:
    """The header must name exactly `periods`' months, in that order."""
    found = [m.group(0)[:3].lower() for m in
             re.finditer(r"[A-Za-z]{3,9}", header) if m.group(0)[:3].lower() in _MONTHS]
    want = [_month_name(p) for p in periods]
    if found != want:
        raise ValueError(
            f"South Sudan CPI: {table} covers {found}, expected {want}")


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    t = _TITLE.search(text)
    if not t or t.group(1)[:3].lower() not in _MONTHS:
        raise ValueError("South Sudan CPI: report month not found in the title")
    report = f"{t.group(2)}-{_MONTHS[t.group(1)[:3].lower()]}"
    recent = [_prev(report), report]

    b = _BASE.search(text)
    base_period = re.sub(r"\s*=\s*", " = ", b.group(1)) if b else ""

    records = []

    # --- Table 1: all-items index + MoM, the full series of the current base ---
    series = []
    for ln in _section(lines, "table 1", "table 2"):
        m = _T1_ROW.match(ln)
        if m:
            period = f"20{m.group(2)}-{_MONTHS.get(m.group(1).lower(), '')}"
            series.append((period, float(m.group(3)), float(m.group(4))))
    if not series or series[0][0] != report:
        raise ValueError(
            f"South Sudan CPI: Table 1 starts at {series[0][0] if series else None}, "
            f"expected the report month {report}")
    for period, idx, mom in series:
        records.append(("00", "All Items Index", _GEOGRAPHY, period, "index",
                        idx, "Index", base_period))
        records.append(("00", "All Items Index", _GEOGRAPHY, period,
                        "inflation_mom", mom, "percent", ""))

    # --- Table 2: MoM by COICOP division, two months ---
    body = _section(lines, "table 2", "1.6")
    head = " ".join(ln for ln in body if not _DATA_ROW.match(ln))
    _check_months(head, recent, "Table 2")
    divisions = 0
    for ln in body:
        m = _DATA_ROW.match(ln)
        if not m:
            continue
        code = coicop.code_for_label(m.group(1))
        if not code or code == "00":       # all-items duplicates the Table 1 series
            continue
        divisions += 1
        for period, val in zip(recent, (float(m.group(3)), float(m.group(4)))):
            records.append((code, m.group(1).strip(), _GEOGRAPHY, period,
                            "inflation_mom", val, "percent", ""))
    if divisions < 10:
        raise ValueError(f"South Sudan CPI: Table 2 gave {divisions} divisions")

    # --- Table 3: MoM by state capital, same two months ---
    body = _section(lines, "table 3", "further information")
    head = " ".join(ln for ln in body if not _DATA_ROW.match(ln))
    states = [f"20{y}-{_MONTHS[mo.lower()]}" for mo, y in _T3_HEAD.findall(head)
              if mo.lower() in _MONTHS]
    if states != recent:
        raise ValueError(f"South Sudan CPI: Table 3 covers {states}, expected {recent}")
    for ln in body:
        m = _DATA_ROW.match(ln)
        if not m or not re.fullmatch(r"[A-Za-z][A-Za-z ]+", m.group(1).strip()):
            continue
        for period, val in zip(recent, (float(m.group(3)), float(m.group(4)))):
            records.append(("00", "All Items Index", m.group(1).strip(), period,
                            "inflation_mom", val, "percent", ""))

    out = pd.DataFrame.from_records(
        records,
        columns=["coicop_code", "coicop_label", "geography", "period", "measure",
                 "value", "unit", "base_period"])
    out["frequency"] = "monthly"
    return out.drop_duplicates(["coicop_code", "geography", "period", "measure"])
