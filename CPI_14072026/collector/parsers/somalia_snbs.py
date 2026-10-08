"""Parser for the SNBS Somalia monthly CPI report PDF (Tier 3).

Somalia rebased in January 2025 onto COICOP 2018 (13 divisions, index reference
2022) covering Mogadishu + all Federal Member States. The index itself is only
ever drawn as a chart, so the tabular data are the rates: four tables, each a
3-month window, captioned '<Table N>. <Division|State> level <annual|monthly>
percentage change':

  Division                                       Mar-26 Apr-26 May-26
  CPI TOTAL                                       7.9%   8.1%   8.4%
  01 - FOOD AND NON-ALCOHOLIC BEVERAGES           8.0%   8.1%   8.0%

The caption gives both the breakdown (division -> COICOP, state -> geography) and
the measure (annual -> YoY, monthly -> MoM), so the report month never has to be
read from the filename — it is the last column header.

Long division labels are set in a box that overruns the first value column, and
pdfplumber merges the overlapping glyphs into one token ('MAINTEN6A.N3C%E' =
'MAINTENANCE' + '6.3%'). Label letters and value characters are disjoint classes,
so we read values at the character level from the value zone (right of the first
month header) and drop anything alphabetic, which recovers the buried number.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_MONTHS = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
           "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
           "nov": "11", "dec": "12"}
_LABELS = {
    "00": "CPI TOTAL",
    "01": "FOOD AND NON-ALCOHOLIC BEVERAGES",
    "02": "ALCOHOLIC BEVERAGES, TOBACCO AND NARCOTICS",
    "03": "CLOTHING AND FOOTWEAR",
    "04": "HOUSING, WATER, ELECTRICITY, GAS AND OTHER FUELS",
    "05": "FURNISHINGS, HOUSEHOLD EQUIPMENT AND ROUTINE HOUSEHOLD MAINTENANCE",
    "06": "HEALTH",
    "07": "TRANSPORT",
    "08": "INFORMATION AND COMMUNICATION",
    "09": "RECREATION, SPORT AND CULTURE",
    "10": "EDUCATION SERVICES",
    "11": "RESTAURANTS AND ACCOMMODATION SERVICES",
    "12": "INSURANCE AND FINANCIAL SERVICES",
    "13": "PERSONAL CARE, SOCIAL PROTECTION AND MISCELLANEOUS GOODS AND SERVICES",
}

_RE_HDR = re.compile(r"^([A-Za-z]{3})[a-z]*-(\d{2})$")
_RE_CAPTION = re.compile(
    r"Table\s+\d+\.\s+(Division|State)\s+level\s+(annual|monthly)", re.I)
_RE_VAL = re.compile(r"-?\d+(?:\.\d+)?%")
_RE_CODE = re.compile(r"^(\d{2})\s*-")
_VAL_CHARS = set("-0123456789.%")


def _bucket(items, tol: float = 3.0) -> list[list[dict]]:
    """Group page items into visual rows by their `top` coordinate."""
    rows: dict[int, list[dict]] = {}
    for it in items:
        rows.setdefault(round(it["top"] / tol), []).append(it)
    return [sorted(v, key=lambda z: z["x0"]) for _, v in sorted(rows.items())]


def _periods(page) -> tuple[list[str], float] | None:
    """The 'Mar-26 Apr-26 May-26' header: the table's periods, and the x where
    the value zone starts."""
    for row in _bucket(page.extract_words()):
        hits, out = [], []
        for w in row:
            m = _RE_HDR.match(w["text"])
            if not m:
                continue
            mm = _MONTHS.get(m.group(1).lower())
            if not mm:      # same shape, not a month ('CPI-26') — not the header
                hits, out = [], []
                break
            hits.append(w)
            out.append(f"20{m.group(2)}-{mm}")
        if len(hits) >= 2:
            return out, min(h["x0"] for h in hits) - 8
    return None


def _table(page) -> list[tuple[str, list[float]]]:
    """Rows of (label, values) for the one table on this page."""
    found = _periods(page)
    if not found:
        return []
    periods, left = found
    rows = []
    for row in _bucket(page.chars):
        nums = "".join(c["text"] for c in row
                       if c["x0"] >= left and c["text"] in _VAL_CHARS)
        vals = _RE_VAL.findall(nums)
        if len(vals) != len(periods):
            continue
        label = "".join(c["text"] for c in row if c["x0"] < left).strip()
        if label:
            rows.append((label, [float(v.rstrip("%")) for v in vals]))
    return rows


def parse(pdf_path: str) -> pd.DataFrame:
    records = []
    seen_captions = set()
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            cap = _RE_CAPTION.search(page.extract_text() or "")
            if not cap:
                continue
            kind, measure = cap.group(1).lower(), cap.group(2).lower()
            seen_captions.add((kind, measure))
            measure = "inflation_yoy" if measure == "annual" else "inflation_mom"
            found = _periods(page)
            if not found:
                raise ValueError(f"Somalia CPI: no month header on {kind}/{measure} table")
            periods, _ = found

            for label, vals in _table(page):
                is_total = label.upper().startswith("CPI TOTAL")
                if kind == "division":
                    m = _RE_CODE.match(label)
                    code = "00" if is_total else (m.group(1) if m else None)
                    if code is None or code not in _LABELS:
                        continue
                    geo = "National"
                else:
                    # the state tables repeat the national total — already captured
                    if is_total:
                        continue
                    code, geo = "00", re.sub(r"\s*\(\w\)\s*$", "", label).strip()
                for period, val in zip(periods, vals):
                    records.append((code, _LABELS[code], geo, period, measure,
                                    round(val, 4), "percent", ""))

    # SNBS varies which tables an issue carries — the July 2026 report dropped the
    # division-level ANNUAL table (its numbers survive only in the prose summary)
    # while keeping the division monthly and both state tables. Require a division
    # breakdown of some kind, since without one there is no COICOP detail at all,
    # and report what was absent rather than failing the whole country over it.
    divisions = {m for k, m in seen_captions if k == "division"}
    if not divisions:
        raise ValueError(
            f"Somalia CPI: no division-level table in the report "
            f"(captions found: {sorted(seen_captions)})")
    for absent in sorted({"annual", "monthly"} - divisions):
        print(f"[Somalia] note: no division-level {absent} table in this issue")

    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "geography", "period",
                          "measure", "value", "unit", "base_period"])
    if out.empty:
        raise ValueError("Somalia CPI: no rows extracted")
    out["frequency"] = "monthly"
    return out.drop_duplicates(
        subset=["coicop_code", "geography", "period", "measure"])
