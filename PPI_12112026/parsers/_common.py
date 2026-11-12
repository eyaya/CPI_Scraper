"""Shared helpers for PPI parsers.

**Numbers.** `to_number("1 234,5", decimal=",")` -> 1234.5; a dash, "n.d.",
"..", a footnote marker or an empty cell is None, never 0 (a fabricated zero
in a price change is worse than a missing row). A leading comma/point is a lost
zero (",9" -> 0.9). Parentheses are NOT read as negatives unless asked.

**Periods.** `month_period("janv. 2024")`, `month_period("2024M03")`,
`month_period("March 2024")`, `month_period("Fev-24")` -> "2024-01" ...;
`quarter_period("T3 2024")`, `quarter_period("2024 Q3")`, `quarter_period("3e trim. 2024")`
-> "2024-Q3". English, French and Portuguese month names.

**Rows.** `row(...)` builds one row and refuses a measure, unit, frequency or
variant outside the schema vocabulary; the unit defaults from the measure.
"""
from __future__ import annotations

import re
import unicodedata

from ..schema import FREQUENCIES, INDEX_VARIANTS, MEASURES, UNITS

_SPACES = re.compile("[     ]")


def to_number(cell, decimal: str = ".", negative_parens: bool = False):
    if cell is None:
        return None
    if isinstance(cell, (int, float)):
        return None if cell != cell else float(cell)       # NaN from a pandas cell
    s = str(cell).strip()
    if not s or re.fullmatch(r"[-–—.…*/]+|n\.?d\.?|n\.?a\.?|nd|na|x|\.\.", s, re.I):
        return None
    neg = False
    if negative_parens and re.fullmatch(r"\(.*\)", s):
        neg, s = True, s[1:-1]
    s = s.replace("−", "-").replace("–", "-").rstrip("%").strip()
    s = re.sub(r"[*†‡a-z]+$", "", s, flags=re.I) if re.search(r"\d", s) else s
    s = _SPACES.sub("", s)
    if decimal == ",":
        s = s.replace(".", "") if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", s) else s
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "") if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", s) else s
    if re.fullmatch(r"-?\.\d+", s):
        s = s.replace(".", "0.", 1) if not s.startswith("-") else "-0" + s[1:]
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _fold(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


_MONTHS = {}
for i, names in enumerate([
        ("jan", "janv", "janvier", "january", "janeiro"),
        ("feb", "fev", "fevr", "fevrier", "february", "fevereiro"),
        ("mar", "mars", "march", "marco"),
        ("apr", "avr", "avril", "april", "abr", "abril"),
        ("may", "mai", "maio"),
        ("jun", "juin", "june", "junho"),
        ("jul", "juil", "juillet", "july", "julho"),
        ("aug", "aou", "aout", "august", "ago", "agosto"),
        ("sep", "sept", "september", "septembre", "set", "setembro"),
        ("oct", "octobre", "october", "out", "outubro"),
        ("nov", "novembre", "november", "novembro"),
        ("dec", "decembre", "december", "dez", "dezembro")], start=1):
    for n in names:
        _MONTHS[n] = i


def _year(y: str) -> int:
    y = int(y)
    return y + (2000 if y < 50 else 1900) if y < 100 else y


def month_period(text) -> str | None:
    t = _fold(text)
    m = re.fullmatch(r"((?:19|20)\d{2})\s*[m/-]\s*(\d{1,2})", t)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.fullmatch(r"(\d{1,2})\s*[/.-]\s*((?:19|20)\d{2})", t)
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    m = re.fullmatch(r"([a-z]+)\.?\s*[-'’ ]?\s*(\d{2}|\d{4})", t)
    if m and m.group(1) in _MONTHS:
        return f"{_year(m.group(2)):04d}-{_MONTHS[m.group(1)]:02d}"
    m = re.fullmatch(r"(\d{4})\s+([a-z]+)\.?", t)
    if m and m.group(2) in _MONTHS:
        return f"{m.group(1)}-{_MONTHS[m.group(2)]:02d}"
    return None


def quarter_period(text) -> str | None:
    t = _fold(text)
    for rx, qi, yi in ((r"(?:t|q|trim(?:estre)?\.?)\s*([1-4])\s*[-/ ]?\s*((?:19|20)?\d{2})", 1, 2),
                       (r"((?:19|20)\d{2})\s*[-/ ]?\s*(?:t|q)\s*([1-4])", 2, 1),
                       (r"([1-4])\s*(?:e|er|eme|st|nd|rd|th|o|º)?\s*(?:trim(?:estre)?\.?|quarter|qtr\.?)\s*((?:19|20)?\d{2})", 1, 2)):
        m = re.fullmatch(rx, t)
        if m:
            return f"{_year(m.group(yi)):04d}-Q{m.group(qi)}"
    return None


_UNIT_FOR = {"index": "index", "weight": "percent"}


def row(*, index_name: str, industry: str, period: str, frequency: str, measure: str, value,
        index_variant: str = "output", unit: str | None = None, base_period: str = "",
        industry_code_nso: str = "", series_code: str = "", currency_basis: str = "",
        ownership: str = "") -> dict:
    unit = unit or _UNIT_FOR.get(measure, "percent")
    for name, v, allowed in (("measure", measure, MEASURES), ("unit", unit, UNITS),
                             ("frequency", frequency, FREQUENCIES),
                             ("index_variant", index_variant, INDEX_VARIANTS)):
        if v not in allowed:
            raise ValueError(f"unknown {name} {v!r}")
    if value is None:
        raise ValueError(f"no value for {industry!r} {period} {measure} -- skip the cell, don't pass None")
    return {"index_name": index_name, "index_variant": index_variant, "industry": industry,
            "industry_code_nso": industry_code_nso, "period": period, "frequency": frequency,
            "measure": measure, "value": float(value), "unit": unit, "base_period": base_period,
            "ownership": ownership, "currency_basis": currency_basis, "series_code": series_code}
