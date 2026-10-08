"""Row builder and shared helpers for the labour parsers.

Every parser here returns the same dict shape, and this is the one place that
knows it. The builder is deliberately strict: it raises on an unknown sex,
locality, measure, unit or classification rather than letting a typo through to
the validator, because a mislabelled category is far harder to spot downstream
than a missing one.

THE CLASSIFICATION IS REQUIRED FOR A CATEGORY TOPIC. An industry or occupation
label is not comparable across countries without the scheme that produced it --
Stats SA's "Trade" is one of ten national groups, while Malawi's
"Wholesale and retail trade..." is an ISIC Rev.4 section. The builder refuses a
row that names a category without naming its scheme.
"""
from __future__ import annotations

import re
import unicodedata

from ..schema import (CLASSIFICATIONS, FREQUENCIES, LOCALITIES, MEASURES,
                      SEXES, TOPICS, UNITS)

_SPACES = "      "
_SPACE_RE = re.compile(f"[{_SPACES}]")

# Topics whose `characteristic` is a category drawn from a classification.
_CATEGORY_TOPICS = {"industry", "occupation", "employment_status"}


def deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s))
                   if unicodedata.category(c) != "Mn")


def to_number(text, decimal: str = ".") -> float | None:
    """Parse one published number, or None if the cell is not one."""
    if text is None:
        return None
    if isinstance(text, float) and text != text:
        # NaN. `pandas.read_excel` returns it for every EMPTY cell, and letting
        # it through emitted a row per blank -- which also swept the sheets'
        # FOOTNOTE lines in as categories ("Due to rounding, numbers do not
        # necessarily add up to totals."), because a footnote with no values
        # still looked like it had produced some.
        return None
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text)
    s = _SPACE_RE.sub("", str(text)).strip()
    if not s or s in {"-", "–", "—", "..", "...", "n.a.", "N/A", "*"}:
        return None
    s = s.replace("%", "")
    if decimal == ",":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    s = s.strip("()")
    try:
        return float(s)
    except ValueError:
        return None


def numbers_in(text: str, decimal: str = ".", keep_dash: bool = False,
               space_thousands: bool = True) -> list[float | None]:
    """Every number on a line, in printed order.

    Order matters far more than magnitude here: a status-in-employment row
    carries a count and a percentage for each of three sexes, and they are
    mapped positionally. No magnitude-based filtering is applied, because a
    percentage and a count are both plausible numbers.

    With `decimal: ","` a SPACE is a thousands separator, which is how French
    and Portuguese sources print "1 234 567".

    With `keep_dash` a free-standing dash is returned as None IN ITS POSITION
    rather than dropped. A dash is not a zero, but it IS a cell: Statistics
    Botswana prints "Plant & Machine Operators 33,165 6,564 39,729 613 - 613 ..."
    and dropping the dash slides every later value one column to the left.
    """
    # A LEADING COMMA IS A LOST ZERO, NOT A SEPARATE NUMBER. HCP Morocco drops
    # the leading zero on small decimals in Tableau 5 -- ",0", ",1", ",3" for
    # 0,0 / 0,1 / 0,3 -- and the plain patterns below match only the DIGITS
    # after the comma. That does not skip the row, which is the failure that
    # would at least be visible: it returns 1.0 where the report prints 0,1, a
    # TENFOLD error at full column width, and nothing downstream can see it.
    # Rewritten to an explicit leading zero before any number is read.
    if decimal == ",":
        text = re.sub(r"(?<![\d,])(,\d)", r"0\1", str(text))

    if decimal == "," and not space_thousands:
        # A SPACE IS NOT ALWAYS A THOUSANDS SEPARATOR, even in a French table.
        # HCP Morocco's percentage blocks end on "Total 100 100 100 100 100",
        # five whole numbers -- and the space-grouping rule reads that as the
        # single value 100100100100100, because every group happens to be three
        # digits. A table whose values are all percentages says so with
        # `space_thousands: False` and gets five numbers back.
        pat = r"-?\d+,\d+|-?\d+"
    elif decimal == ",":
        pat = rf"-?\d{{1,3}}(?:[{_SPACES}]\d{{3}})+(?:,\d+)?|-?\d+,\d+|-?\d+"
    else:
        pat = r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+\.\d+|-?\d+"
    if keep_dash:
        pat = rf"(?<!\S)[-–—](?!\S)|{pat}"
    out: list[float | None] = []
    for tok in re.findall(pat, str(text)):
        if keep_dash and tok in {"-", "–", "—"}:
            out.append(None)
            continue
        v = to_number(tok, decimal=decimal)
        if v is not None:
            out.append(v)
    return out


def normalise_sex(text: str) -> str:
    """Map a published sex label to the vocabulary.

    "Women"/"Men" are as common as "Female"/"Male" in these tables (Stats SA
    uses them), and francophone and lusophone sources use their own words.
    """
    s = deaccent(text or "").strip().lower()
    if s in {"both sexes", "total", "all", "ensemble", "ambos os sexos",
             "both", "total both sexes"}:
        return "total"
    if any(t in s for t in ("female", "women", "femme", "feminin", "mulher",
                            "feminino")):
        return "female"
    if any(t in s for t in ("male", "men", "homme", "masculin", "homem",
                            "masculino")):
        return "male"
    return "total"


def normalise_locality(text: str) -> str:
    """Coarse locality for joining; the published stratum is kept separately."""
    s = deaccent(text or "").strip().lower()
    if s in {"", "total", "all", "all locality types", "urban and rural",
             "ensemble", "national"}:
        return "all"
    if "urban" in s or "urbain" in s or "urbano" in s:
        return "urban"
    if "rural" in s:
        return "rural"
    return "other"


def row(*, topic: str, characteristic: str, classification: str, value,
        survey: str, period: str, frequency: str,
        measure: str = "count", unit: str = "persons",
        sex: str = "total", age_group: str = "Total", education: str = "Total",
        geography: str = "Total country", locality: str = "all",
        locality_label: str = "Total", working_age_base: str = "15+",
        reference_period: str | None = None, series_code: str = "") -> dict:
    if topic not in TOPICS:
        raise ValueError(f"unknown topic {topic!r}")
    if classification not in CLASSIFICATIONS:
        raise ValueError(
            f"unknown classification {classification!r} -- add it to "
            f"schema.CLASSIFICATIONS, or use 'National' where the NSO uses its "
            f"own grouping")
    if topic in _CATEGORY_TOPICS and classification == "Not applicable":
        raise ValueError(
            f"topic {topic!r} names a category ({characteristic!r}) but "
            f"declares no classification. Record the NSO's own scheme, or "
            f"'National' where the grouping is its own -- the label alone is "
            f"not comparable across countries.")
    for name, val, allowed in (("sex", sex, SEXES),
                               ("locality", locality, LOCALITIES),
                               ("measure", measure, MEASURES),
                               ("unit", unit, UNITS),
                               ("frequency", frequency, FREQUENCIES)):
        if val not in allowed:
            raise ValueError(f"unknown {name} {val!r}")
    if not str(characteristic).strip():
        raise ValueError(f"empty characteristic for topic {topic!r}")
    return {
        "topic": topic, "characteristic": str(characteristic).strip(),
        "classification": classification,
        "sex": sex, "age_group": age_group, "education": education,
        "geography": geography, "locality": locality,
        "locality_label": locality_label,
        "working_age_base": working_age_base,
        "period": period, "reference_period": reference_period or period,
        "survey": survey, "frequency": frequency,
        "measure": measure, "value": float(value), "unit": unit,
        "series_code": series_code,
    }


_MONTH_Q = {"jan": 1, "feb": 1, "mar": 1, "apr": 2, "may": 2, "jun": 2,
            "jul": 3, "aug": 3, "sep": 3, "oct": 4, "nov": 4, "dec": 4}

# ORDINAL QUARTER NAMES, kept in step with `unemployment/parsers/_common.py`.
# Matched AFTER deaccenting, so "première" arrives here as "premiere".
_FR_ORDINAL = {
    "premier": 1, "premiere": 1, "1er": 1, "1ere": 1,
    "deuxieme": 2, "2e": 2, "2eme": 2, "second": 2, "seconde": 2,
    "troisieme": 3, "3e": 3, "3eme": 3,
    "quatrieme": 4, "4e": 4, "4eme": 4,
    "primer": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4,
    "primeiro": 1, "terceiro": 3, "quarto": 4,
    "i": 1, "ii": 2, "iii": 3, "iv": 4,
}


def parse_period(text: str) -> str | None:
    """Normalise a published reference period to YYYY, YYYY-Qn or YYYY-Hn.

    Returns None when none can be read, so the caller falls back to the
    layout's declared period rather than guessing -- dating a series wrongly is
    silently corrupting, and these workbooks carry 70+ period columns.
    """
    if text is None:
        return None
    raw = str(text).strip()
    low = deaccent(raw).lower()
    m = re.search(r"\bq\s*([1-4])\D{0,5}(20\d{2})\b", low)
    if m:
        return f"{m.group(2)}-Q{m.group(1)}"
    m = re.search(r"\b(20\d{2})\s*[-_ ]?\s*q\s*([1-4])\b", low)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}"
    # "T2 2026" -- the short French/Portuguese form.
    m = re.search(r"\bt\s*([1-4])\s*[-_ ]?\s*(20\d{2})\b", low)
    if m:
        return f"{m.group(2)}-Q{m.group(1)}"
    # AN ORDINAL NAMES THE QUARTER: "2e trimestre 2026", "II trimestre de 2026"
    # and INS Tunisie's hyphenated column headers, "première-trimestre 2024".
    # Without this the bare-year fallback below would date all nine of INS's
    # quarterly columns as three ANNUAL periods, which then collide on the
    # merge key -- values that look right, under the wrong period.
    m = re.search(r"\b([a-z0-9]+)[-\s]+trimestre\D{0,4}(20\d{2})\b", low)
    if m and m.group(1) in _FR_ORDINAL:
        return f"{m.group(2)}-Q{_FR_ORDINAL[m.group(1)]}"
    # "Jan-Mar 2008" -- the form Stats SA's QLFS Trends workbook uses.
    m = re.search(r"\b([a-z]{3})[a-z]*\s*[-–to]{1,3}\s*[a-z]{3}[a-z]*\D{0,4}"
                  r"(20\d{2})\b", low)
    if m and m.group(1) in _MONTH_Q:
        return f"{m.group(2)}-Q{_MONTH_Q[m.group(1)]}"
    m = re.fullmatch(r"(19|20)\d{2}", low)
    if m:
        return low
    m = re.search(r"\b((?:19|20)\d{2})\b", low)
    return m.group(1) if m else None
