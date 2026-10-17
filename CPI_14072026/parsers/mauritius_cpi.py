"""Parser for the Statistics Mauritius monthly CPI note PDF (Tier 3).

Statistics Mauritius publishes a monthly CPI note (base Jan–Dec 2023 = 100) whose
'Division' table extracts cleanly with pdfplumber's table extraction:

  Division                      | January 2026 | February 2026 | % change
  1. Food and non-alcoholic …   | 109.8        | 110.6         | +0.8
  …
  13. Personal care, social …   | 109.5        | 111.0         | +1.4
  All Divisions                 | 109.1        | 109.5         | +0.4

Rows carry a leading COICOP-2018 division number (1..13); 'All Divisions' is All
items (00) — but NOT 'All Divisions, excluding …'. The table shows two dated
index columns, so one note yields two months (previous + current). We emit index
levels; labels use the canonical COICOP-2018 map (the PDF spaces some letters,
e.g. 'H e a lth'). Base Jan–Dec 2023 = 100.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

from ..coicop import DIVISIONS

_BASE_PERIOD = "Jan-Dec 2023 = 100"
_MONTHS = {"january": "01", "february": "02", "march": "03", "april": "04",
           "may": "05", "june": "06", "july": "07", "august": "08",
           "september": "09", "october": "10", "november": "11", "december": "12"}
_PERIOD = re.compile(r"(january|february|march|april|may|june|july|august|"
                     r"september|october|november|december)\s+(\d{4})", re.IGNORECASE)


def _period(cell) -> str | None:
    if not isinstance(cell, str):
        return None
    m = _PERIOD.search(cell.replace("\n", " "))
    return f"{m.group(2)}-{_MONTHS[m.group(1).lower()]}" if m else None


def _value(cell) -> float | None:
    if isinstance(cell, (int, float)):
        return float(cell)
    if isinstance(cell, str) and re.fullmatch(r"-?\d+(?:\.\d+)?", cell.strip()):
        return float(cell.strip())
    return None


_BASE_RE = re.compile(r"January\s*[–-]\s*December\s*(\d{4})\s*=\s*100")
_COMPARED = re.compile(
    r"for the month of\s+(" + _PERIOD.pattern + r")\s+compared to\s+(" + _PERIOD.pattern + r")",
    re.IGNORECASE)
_NUMS = re.compile(r"(\d+\.\d)\s+(\d+\.\d)\s+(?:[+\-]\s*\d*\s*\.?\s*\d+|-)\s*$")


def _base_of(text: str) -> tuple[int, str]:
    """The note's own base, e.g. (2017, 'Jan-Dec 2017 = 100')."""
    m = _BASE_RE.search(text)
    if not m:
        raise ValueError("Mauritius CPI note: no 'Base: January - December YYYY = 100'")
    return int(m.group(1)), f"Jan-Dec {m.group(1)} = 100"


def _parse_text_layout(pdf_path: str) -> pd.DataFrame:
    """Notes up to December 2023 (bases 2012 and 2017 = 100).

    THE TWELVE-DIVISION NOTES (COICOP 1999) print the division table as plain
    lines that pdfplumber's table finder does not see:

        Sub-indices for the twelve divisions ... for the month of December 2018
        compared to November 2018 are shown below:
        1. Food and non-alcoholic beverages 102.6 101.6 -0.9
        4. Housing, water, electricity, gas and
        97.7 97.7 -
        other fuels

    The two index columns are (previous month, current month), named by that
    sentence. A wrapped label puts its numbers on the NEXT line (2018) or keeps
    them and wraps the tail (2022); the numbers are assigned to the most recent
    numbered line still waiting for them. Labels are kept as printed (the
    1999 classification's names, e.g. "Communication", "Miscellaneous goods and
    services"), never the COICOP-2018 names of the newer notes.
    """
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages[:4])
    base_year, base = _base_of(text)
    m = _COMPARED.search(text.replace("\n", " "))
    if not m:
        raise ValueError("Mauritius CPI division table not found in note")
    cur, prev = _period(m.group(1)), _period(m.group(4))
    start = text.find("Sub-indices for the twelve divisions")
    # "110 .4" -- the text layer splits a decimal around its point; rejoined.
    # Garbled glyphs ("13383. 2" for Health, January 2024) are NOT repaired:
    # the plausibility check below refuses them and the note is skipped.
    lines = [re.sub(r"(\d) \.(\d)", r"\1.\2", ln.strip())
             for ln in text[start:].splitlines()[1:]]
    rows, pending = [], None          # pending = [code, label] awaiting numbers
    for ln in lines:
        if ln.startswith("1/") or ln.lower().startswith("notes"):
            break
        # A digit-free line starting lower-case is the tail of a wrapped label
        # ("other fuels", "household maintenance"): join it to its division,
        # whether the numbers came before it (2018) or with the head (2022).
        if (re.match(r"^[a-z]", ln) and not re.search(r"\d", ln)):
            if pending and pending[0] != "00":
                pending[1] = f"{pending[1]} {ln}"
            elif rows and rows[-1][0] != "00":
                code = rows[-1][0]
                rows = [(c, f"{l} {ln}" if c == code else l, p, v) for c, l, p, v in rows]
            continue
        lab = re.match(r"^(\d{1,2})\.\s+(.*)$", ln)
        if lab and 1 <= int(lab.group(1)) <= 12:
            pending = [f"{int(lab.group(1)):02d}", lab.group(2)]
        elif ln.lower().startswith("all divisions"):
            pending = None if "exclud" in ln.lower() else ["00", "All items"]
        nm = _NUMS.search(ln)
        if nm and pending:
            label = _NUMS.sub("", pending[1]).strip() if pending[0] != "00" else "All items"
            rows.append((pending[0], label, prev, float(nm.group(1))))
            rows.append((pending[0], label, cur, float(nm.group(2))))
            pending = None
    codes = {c for c, *_ in rows}
    bad = [(c, p, v) for c, _, p, v in rows if not 20 <= v <= 500]
    if bad:
        raise ValueError(f"Mauritius CPI {cur}: implausible index {bad[:2]} (garbled text layer)")
    if len(codes) != 13:
        raise ValueError(f"Mauritius CPI {cur}: read {sorted(codes)} (want 01-12 + 00)")
    out = pd.DataFrame.from_records(rows, columns=["coicop_code", "coicop_label", "period", "value"])
    out["geography"] = "National"
    out["measure"] = "index"
    out["unit"] = "Index"
    out["base_period"] = base
    out["frequency"] = "monthly"
    out["_base_year"] = base_year
    return out


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """Every note handed in -- the current one and the archive's back issues.

    ONE MONTH, ONE BASE. Each note prints the previous and the current month,
    and the note after a rebase prints the previous month AGAIN on the new base
    (December 2023 appears on base 2017 in the December note and on base 2023
    in the January 2024 note). The output's merge key has no base column, so
    where two bases cover a month the NEWEST base is kept -- it is the series
    the NSO now publishes -- and older bases fill only the months it does not
    reach. Never chained: each row keeps its own `base_period`.
    """
    frames = []
    for p in [pdf_path, *(extras or [])]:
        try:
            frames.append(_parse_one(p))
        except ValueError as e:
            name = p.replace("\\", "/").rsplit("/", 1)[-1]
            print(f"  [mauritius_cpi] skipped {name}: {e}")
    if not frames:
        raise ValueError("Mauritius CPI: no note could be read")
    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values("_base_year", kind="stable").drop_duplicates(
        ["coicop_code", "period", "measure"], keep="last")
    return df.drop(columns="_base_year").reset_index(drop=True)


def _parse_one(pdf_path: str) -> pd.DataFrame:
    try:
        out = _parse_table_layout(pdf_path)
    except ValueError:
        return _parse_text_layout(pdf_path)
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages[:3])
    year, base = _base_of(text)
    out["base_period"] = base
    out["_base_year"] = year
    return out


def _parse_table_layout(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for tb in page.extract_tables():
                hi = next((i for i, r in enumerate(tb)
                           if any(isinstance(c, str) and c.strip().lower() == "division" for c in r)), None)
                if hi is None:
                    continue
                cols = {ci: p for ci, c in enumerate(tb[hi]) if (p := _period(c))}
                if not cols:
                    continue

                records = []
                for row in tb[hi + 1:]:
                    first = str(row[0]).replace("\n", " ").strip() if row and row[0] else ""
                    m = re.match(r"^(\d{1,2})\.", first)
                    if m and 1 <= int(m.group(1)) <= 13:
                        code = f"{int(m.group(1)):02d}"
                    elif first.lower().startswith("all divisions") and "exclud" not in first.lower():
                        code = "00"
                    else:
                        continue
                    label = DIVISIONS.get(code, "All items" if code == "00" else "")
                    for ci, period in cols.items():
                        v = _value(row[ci] if ci < len(row) else None)
                        if v is not None:
                            records.append((code, label, period, round(v, 4)))

                if len({c for c, *_ in records if c != "00"}) >= 13:
                    out = pd.DataFrame.from_records(
                        records, columns=["coicop_code", "coicop_label", "period", "value"])
                    out = out.drop_duplicates(["coicop_code", "period"])
                    out["geography"] = "National"
                    out["measure"] = "index"
                    out["unit"] = "Index"
                    out["base_period"] = _BASE_PERIOD
                    out["frequency"] = "monthly"
                    return out

    raise ValueError("Mauritius CPI division table not found in note")
