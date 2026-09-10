"""Shared helpers for MPI parsers.

Two problems recur across every African MPI report and are solved once here.

**Number formats.** French, Portuguese and Spanish reports use a COMMA decimal
mark and a SPACE (often U+00A0) thousands separator — Mali writes `0,323` and
`5 532 715`, Angola writes `0,264`. English reports use the opposite. `to_number`
handles both from an explicit `decimal` hint, and returns None rather than 0 for
a dash, a footnote marker or an empty cell: a fabricated zero in a poverty rate
is worse than a missing row.

**Row construction.** `row()` builds one validated analytic row and refuses to
invent a metric outside the controlled vocabulary, or to emit a national measure
without the `k_cutoff` / `n_dimensions` / `n_indicators` that make it
interpretable.
"""
from __future__ import annotations
import re
import unicodedata

from ..schema import (METRICS, MPI_TYPES, UNITS, SEXES, LOCALITIES,
                      UNITS_OF_ANALYSIS)

# Every space-like character an NSO PDF has put inside a number.
_SPACES = "        "
_SPACE_RE = re.compile(f"[{_SPACES}]")

# Which metrics are percentages and which is the index, so a parser cannot
# mislabel a unit by accident.
_PERCENT_METRICS = {"incidence_H", "intensity_A", "censored_headcount",
                    "uncensored_headcount", "contribution", "vulnerable",
                    "severe_poverty",
                    "incidence_H_ci_low", "incidence_H_ci_high",
                    "intensity_A_ci_low", "intensity_A_ci_high"}


def to_number(text, decimal: str = ".") -> float | None:
    """Parse one published number. `decimal` is ',' for FR/PT/ES sources."""
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    s = _SPACE_RE.sub("", s)
    s = s.replace("%", "").replace("−", "-")      # U+2212 MINUS SIGN
    s = s.strip("*†‡()[]")
    if s in {"-", "--", "–", "—", "..", "...", "n/a", "N/A", "na", ":", "nan"}:
        return None
    if decimal == ",":
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
    """Every number on a line, in printed order.

    Note MPI tables mix scales on one line — Mali's region rows read
    `Mopti 13,9 0,491 69,9 70,1`, a population share, an index in [0,1] and two
    percentages. The parser maps them positionally, so the ORDER matters far
    more than the magnitude, and no magnitude-based filtering is applied here.
    """
    if decimal == ",":
        pat = rf"-?\d{{1,3}}(?:[{_SPACES}]\d{{3}})+(?:,\d+)?|-?\d+,\d+|-?\d+"
    else:
        pat = r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+\.\d+|-?\d+"
    out = []
    for tok in re.findall(pat, str(text)):
        v = to_number(tok, decimal=decimal)
        if v is not None:
            out.append(v)
    return out


def deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s))
                   if unicodedata.category(c) != "Mn")


def normalise_sex(text: str) -> str:
    """Map a published sex label (of the household head) to the vocabulary."""
    s = deaccent(text or "").strip().lower()
    if any(t in s for t in ("male-head", "male head", "homme", "masculin",
                            "hombre", "homem")) and "female" not in s:
        return "male"
    if s in {"male", "males", "m", "men"}:
        return "male"
    if any(t in s for t in ("female", "femme", "feminin", "mulher", "mujer",
                            "women")):
        return "female"
    return "total"


def normalise_locality(text: str) -> str:
    """Coarse locality for joining. A named stratum that is not a plain
    urban/rural/total split becomes 'other' — Somalia's NOMADIC population and
    Botswana's 'Cities/Towns' vs 'Urban Villages' are real categories that must
    not be flattened into urban."""
    s = deaccent(text or "").strip().lower()
    if not s or s in {"total", "national", "all", "ensemble", "republic",
                      "nacional", "pais", "country"}:
        return "all"
    # An explicit "everything" label that is not the bare word: Ghana
    # StatsBank's locality dimension calls its total "All locality types", and
    # FR/PT reports write "Ensemble du pays" / "Total do pais". Without this,
    # such a label falls through to 'other' and the NATIONAL row is silently
    # filed as an unnamed stratum -- the single most damaging mis-mapping this
    # function can make, because every headline figure lands in it.
    if re.match(r"^(all|total|ensemble|toutes?|tous|todos?|todas?|conjunto)\b",
                s) and not re.search(r"urban|urbain|urbano|urbana|rural", s):
        return "all"
    if "nomad" in s:
        return "other"
    if "rural" in s:
        return "rural"
    if "urban" in s or "urbain" in s or "urbano" in s or "urbana" in s:
        return "other" if ("autre" in s or "other" in s or "village" in s) else "urban"
    return "other"


def row(*, metric: str, value, mpi_type: str, survey: str, measure_name: str,
        k_cutoff, n_dimensions, n_indicators,
        period: str, reference_period: str, frequency: str,
        unit_of_analysis: str = "person",
        unit: str | None = None,
        dimension: str = "Total", mpi_indicator: str = "Total",
        topic: str = "total", characteristic: str = "Total",
        sex: str = "total", age_group: str = "Total",
        geography: str = "Total country",
        locality: str = "all", locality_label: str = "Total",
        series_code: str = "") -> dict:
    """Build one validated analytic row.

    `unit` defaults from the metric — percentages for the shares, `index` for
    M0, `persons` for a count — so a parser cannot mislabel one. A country that
    prints M0 as a PERCENTAGE (Morocco) must pass `unit="percent"` explicitly;
    the value is never rescaled to force it into [0, 1].
    """
    if metric not in METRICS:
        raise ValueError(f"unknown metric {metric!r}; add it to schema.METRICS "
                         f"deliberately rather than inventing one")
    if mpi_type not in MPI_TYPES:
        raise ValueError(f"unknown mpi_type {mpi_type!r}")
    if unit is None:
        unit = ("percent" if metric in _PERCENT_METRICS
                else "persons" if metric == "population_poor" else "index")
    if unit not in UNITS:
        raise ValueError(f"unknown unit {unit!r}")
    if sex not in SEXES:
        raise ValueError(f"unknown sex {sex!r}")
    if locality not in LOCALITIES:
        raise ValueError(f"unknown locality {locality!r}")
    if unit_of_analysis not in UNITS_OF_ANALYSIS:
        raise ValueError(f"unknown unit_of_analysis {unit_of_analysis!r}")
    for name, v in (("k_cutoff", k_cutoff), ("n_dimensions", n_dimensions),
                    ("n_indicators", n_indicators)):
        if v is None:
            raise ValueError(
                f"{name} is required: an MPI value cannot be interpreted "
                f"without the rule that produced it")
    return {
        "mpi_type": mpi_type, "survey": survey, "measure_name": measure_name,
        "metric": metric, "dimension": dimension, "mpi_indicator": mpi_indicator,
        "topic": topic, "characteristic": characteristic, "sex": sex,
        "age_group": age_group, "geography": geography, "locality": locality,
        "locality_label": locality_label, "k_cutoff": k_cutoff,
        "n_dimensions": n_dimensions, "n_indicators": n_indicators,
        "unit_of_analysis": unit_of_analysis, "period": period,
        "reference_period": reference_period, "frequency": frequency,
        "value": value, "unit": unit, "series_code": series_code,
    }
