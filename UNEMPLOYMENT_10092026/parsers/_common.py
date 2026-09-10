"""Shared helpers for unemployment parsers.

Three problems recur in every African LFS source and are solved once here:

* **Number formats.** French, Portuguese and Spanish reports use a COMMA
  decimal mark and a SPACE (often U+00A0 or U+202F) thousands separator --
  Angola writes `9 562 740` and `21,3%`, Morocco writes thousands with a
  PERIOD (`193.000 postes`). English reports use the opposite convention.
  `to_number` handles all of them from an explicit `decimal` hint.
* **Periods.** LFS reference periods arrive as `Q2 2026`, `2026Q2`,
  `Apr-Jun 2026`, `T2 2026`, `2e trimestre 2026`, `2.º semestre 2025`,
  `Jan-Mar 2024`, or a bare year. `parse_period` normalises to the schema's
  `YYYY` / `YYYY-Qn` / `YYYY-Hn` and keeps the original as `reference_period`.
* **Row construction.** Every parser emits the same analytic columns, so
  `row()` builds one and refuses to invent a topic that is not in the
  controlled vocabulary.
"""
from __future__ import annotations
import re
import unicodedata

from ..schema import TOPICS, DEFINITIONS, MEASURES, UNITS, SEXES, LOCALITIES

# Every space-like character an NSO PDF has ever put inside a number.
_SPACES = "        "
_SPACE_RE = re.compile(f"[{_SPACES}]")

# Rates are percents; counts are people. Which topic is which, so a parser
# cannot accidentally emit a rate as a count.
RATE_TOPICS = {t for t in TOPICS if t.endswith(("_rate", "_ratio", "_share"))}
COUNT_TOPICS = TOPICS - RATE_TOPICS


def to_number(text, decimal: str = ".") -> float | None:
    """Parse one published number. `decimal` is ',' for FR/PT/ES sources.

    Returns None when the token is not a number (a footnote marker, a dash used
    for 'not applicable', an empty cell) -- callers skip those rather than
    coercing them to 0, because a fabricated zero is worse than a missing row.
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    s = _SPACE_RE.sub("", s)
    s = s.replace("%", "").replace("−", "-")     # U+2212 MINUS SIGN
    # Strip footnote markers and stray punctuation around the number.
    s = s.strip("*†‡()[]")
    if s in {"-", "--", "–", "—", "..", "...", "n/a", "N/A", "na", ":"}:
        return None
    if decimal == ",":
        # ',' is the decimal mark, so '.' can only be a thousands separator.
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    if not re.fullmatch(r"-?\d*\.?\d+", s):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def numbers_in(text: str, decimal: str = ".") -> list[float]:
    """Every number on a line, in order. Used by the trailing-offset PDF
    pattern (`nums[-1]`, `nums[-3]`, ...) that dominates WAEMU/CEMAC-style
    tables -- see DEVELOPER_GUIDE section 7.1."""
    if decimal == ",":
        # Match comma-decimals AND bare integers, keeping space-grouped
        # thousands together so '9 562 740' is one number, not three.
        pat = rf"-?\d{{1,3}}(?:[{_SPACES}]\d{{3}})+(?:,\d+)?|-?\d+,\d+|-?\d+"
    else:
        pat = r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+\.\d+|-?\d+"
    out = []
    for tok in re.findall(pat, str(text)):
        v = to_number(tok, decimal=decimal)
        if v is not None:
            out.append(v)
    return out


# --- periods --------------------------------------------------------------

_MONTH_TO_Q = {
    "jan": 1, "feb": 1, "mar": 1, "apr": 2, "may": 2, "jun": 2,
    "jul": 3, "aug": 3, "sep": 3, "oct": 4, "nov": 4, "dec": 4,
    "janv": 1, "fev": 1, "fév": 1, "avr": 2, "mai": 2, "juin": 2,
    "juil": 3, "aou": 3, "aoû": 3, "sept": 3, "oct.": 4, "déc": 4, "dec.": 4,
}
_FR_ORDINAL = {
    "premier": 1, "premiere": 1, "1er": 1, "1ere": 1, "1ère": 1,
    "deuxieme": 2, "2e": 2, "2eme": 2, "2ème": 2, "second": 2, "seconde": 2,
    "troisieme": 3, "3e": 3, "3eme": 3, "3ème": 3,
    "quatrieme": 4, "4e": 4, "4eme": 4, "4ème": 4,
    "primer": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4,
    "primeiro": 1, "terceiro": 3, "quarto": 4,
    # Roman numerals, as INE Angola prints them ("II trimestre de 2026")
    "i": 1, "ii": 2, "iii": 3, "iv": 4,
}


def _deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def parse_period(text: str) -> str | None:
    """Normalise a published reference period to YYYY, YYYY-Qn or YYYY-Hn.

    Returns None when no period can be read -- the caller must then fall back
    to the descriptor's declared period rather than guessing, because dating a
    series wrongly is silently corrupting.
    """
    if not text:
        return None
    raw = str(text).strip()
    low = _deaccent(raw).lower()

    # 'Q2 2026' / '2026Q2' / '2026-Q2' / 'quarter 2 2026'
    # '\D{0,5}' rather than {0,3} so "Q1 of 2024" and "Q1 -- 2024" parse;
    # still short enough that it cannot bridge two unrelated sentences.
    m = re.search(r"\bq\s*([1-4])\D{0,5}(20\d{2})\b", low)
    if m:
        return f"{m.group(2)}-Q{m.group(1)}"
    m = re.search(r"\b(20\d{2})\s*[-_ ]?\s*q\s*([1-4])\b", low)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}"
    m = re.search(r"\bquarter\s*([1-4])\D{0,8}(20\d{2})\b", low)
    if m:
        return f"{m.group(2)}-Q{m.group(1)}"
    # English ordinals: 'second quarter of 2024', '1st quarter 2026'
    m = re.search(r"\b(first|second|third|fourth|1st|2nd|3rd|4th)\s+quarter"
                  r"\D{0,6}(20\d{2})\b", low)
    if m:
        n = {"first": 1, "1st": 1, "second": 2, "2nd": 2,
             "third": 3, "3rd": 3, "fourth": 4, "4th": 4}[m.group(1)]
        return f"{m.group(2)}-Q{n}"
    # ... and the reverse order: '2025 SECOND QUARTER' (ZIMSTAT cover)
    m = re.search(r"\b(20\d{2})\s+(first|second|third|fourth)\s+quarter\b", low)
    if m:
        n = {"first": 1, "second": 2, "third": 3, "fourth": 4}[m.group(2)]
        return f"{m.group(1)}-Q{n}"
    # A MONTH RANGE NAMES ITS QUARTER: CAPMAS Egypt heads every page of the
    # bulletin "Bulletinof Labour Force ( April -June) 2026" and never prints
    # "Q2" anywhere. KNBS and Statistics Botswana use the same form in their
    # covers. The FIRST month fixes the quarter; the pair is required so a
    # stray month name in a sentence cannot date a report.
    m = re.search(r"\b(jan\w*|feb\w*|mar\w*|apr\w*|may|jun\w*|jul\w*|aug\w*|"
                  r"sep\w*|oct\w*|nov\w*|dec\w*)\s*[-–to]{1,3}\s*"
                  r"(jan\w*|feb\w*|mar\w*|apr\w*|may|jun\w*|jul\w*|aug\w*|"
                  r"sep\w*|oct\w*|nov\w*|dec\w*)\D{0,4}(20\d{2})\b", low)
    if m:
        first = m.group(1)[:3]
        q = {"jan": 1, "feb": 1, "mar": 1, "apr": 2, "may": 2, "jun": 2,
             "jul": 3, "aug": 3, "sep": 3, "oct": 4, "nov": 4, "dec": 4}.get(first)
        if q:
            return f"{m.group(3)}-Q{q}"
    # French/Portuguese 'T2 2026' / 'T2-2026'
    m = re.search(r"\bt\s*([1-4])\s*[-_ ]?\s*(20\d{2})\b", low)
    if m:
        return f"{m.group(2)}-Q{m.group(1)}"
    # '2e trimestre 2026' / 'segundo trimestre de 2026' / 'II trimestre de 2026'
    # and INS Tunisie's hyphenated column headers, 'premiere-trimestre 2024'.
    m = re.search(r"\b([a-z0-9]+)[-\s]+trimestre\D{0,4}(20\d{2})\b", low)
    if m and m.group(1) in _FR_ORDINAL:
        return f"{m.group(2)}-Q{_FR_ORDINAL[m.group(1)]}"
    # semester: '2e semestre 2025' / '2.º semestre de 2025' / 'semester 1 2025'
    m = re.search(r"\b([a-z0-9.ºèéêr]+)\s+semestre\D{0,4}(20\d{2})\b", low)
    if m:
        key = m.group(1).replace(".", "").replace("º", "")
        if key in _FR_ORDINAL:
            return f"{m.group(2)}-H{min(_FR_ORDINAL[key], 2)}"
    m = re.search(r"\bs\s*([12])\s*[-_ ]?\s*(20\d{2})\b", low)
    if m:
        return f"{m.group(2)}-H{m.group(1)}"
    # month range: 'Apr-Jun 2026', 'Jan - Mar 2024' (Stats SA table headers)
    m = re.search(r"\b([a-z]{3,4})\s*[-–/]\s*([a-z]{3,4})\D{0,4}(20\d{2})\b", low)
    if m:
        q = _MONTH_TO_Q.get(m.group(2)[:3])
        if q:
            return f"{m.group(3)}-Q{q}"
    # bare year, last resort
    m = re.search(r"\b(19\d{2}|20\d{2})\b", low)
    if m:
        return m.group(1)
    return None


def normalise_sex(text: str) -> str:
    """Map a published sex label onto the controlled vocabulary."""
    s = _deaccent(str(text or "")).strip().lower()
    if s in {"male", "males", "men", "homme", "hommes", "masculin", "masculino",
             "homens", "hombres", "m"}:
        return "male"
    if s in {"female", "females", "women", "femme", "femmes", "feminin",
             "feminino", "mulheres", "mujeres", "f"}:
        return "female"
    return "total"


def normalise_locality(text: str) -> str:
    """Coarse locality for joining. Anything that is a named stratum rather
    than a plain urban/rural/total split becomes 'other' -- the NSO's own name
    is preserved separately in `locality_label`."""
    s = _deaccent(str(text or "")).strip().lower()
    if not s or s in {"total", "national", "all", "ensemble", "both",
                      "all locality types", "urban and rural", "conjunto"}:
        return "all"
    if "urbain" in s or "urban" in s or "urbano" in s or "urbana" in s:
        return "other" if ("autre" in s or "other" in s) else "urban"
    if s.startswith("rural") or "rural" in s:
        return "rural"
    return "other"


def row(*, topic: str, value, series_label: str, survey: str,
        period: str, reference_period: str, frequency: str,
        working_age_base: str,
        measure: str | None = None, unit: str | None = None,
        definition: str = "not_applicable",
        sex: str = "total", age_group: str = "Total", education: str = "Total",
        geography: str = "Total country",
        locality: str = "all", locality_label: str = "Total",
        series_code: str = "") -> dict:
    """Build one validated analytic row.

    `measure` and `unit` default from the topic (rates are percents, counts are
    persons), so a parser cannot mislabel one. Raises immediately on an unknown
    topic rather than letting an invented series reach the CSV.
    """
    if topic not in TOPICS:
        raise ValueError(f"unknown topic {topic!r}; add it to schema.TOPICS "
                         f"deliberately rather than inventing one")
    if definition not in DEFINITIONS:
        raise ValueError(f"unknown definition {definition!r}")
    if measure is None:
        measure = "rate" if topic in RATE_TOPICS else "count"
    if unit is None:
        unit = "percent" if measure in ("rate", "share") else "persons"
    if measure not in MEASURES:
        raise ValueError(f"unknown measure {measure!r}")
    if unit not in UNITS:
        raise ValueError(f"unknown unit {unit!r}")
    if sex not in SEXES:
        raise ValueError(f"unknown sex {sex!r}")
    if locality not in LOCALITIES:
        raise ValueError(f"unknown locality {locality!r}")
    return {
        "survey": survey, "topic": topic, "definition": definition,
        "series_label": series_label, "sex": sex, "age_group": age_group,
        "education": education, "geography": geography, "locality": locality,
        "locality_label": locality_label, "working_age_base": working_age_base,
        "period": period, "reference_period": reference_period,
        "frequency": frequency, "measure": measure, "value": value,
        "unit": unit, "series_code": series_code,
    }
