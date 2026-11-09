"""Shared helpers for monetary-poverty parsers.

**Number formats.** French and Portuguese poverty profiles use a COMMA decimal
and a SPACE thousands separator ("29 809 425"), drop the leading zero on small
shares (",9%"), and -- in the EHCVM profiles -- print a percentage straight
after a space-grouped count:

    Total 37,5% 100,0% ... 29 809 425 100,0%

Read naively, the thousands rule takes "425 100,0" as one group and returns
29 809 425 100,0 as a single number. With `percent_cells=True` every cell that
carries its own "%" is split off from whatever precedes it first, which is
safe precisely because a percentage never needs a thousands group.

`to_number` returns None, never 0, for a dash, a footnote marker or an empty
cell: a fabricated zero in a poverty rate is worse than a missing row.

**Row construction.** `row()` builds one analytic row and refuses a metric,
line type, unit or locality outside the controlled vocabulary. It dates a
split-year round ("2013/14") by its first year.
"""
from __future__ import annotations
import re
import unicodedata

from ..schema import (METRICS, UNITS, SEXES, LOCALITIES, UNITS_OF_ANALYSIS,
                      LINE_TYPES, LINE_LEVELS, WELFARE, TOPICS, split_year)

# Every space-like character an NSO PDF has put inside a number.
_SPACES = "     "
_SPACE_RE = re.compile(f"[{_SPACES}]")

_UNIT_FOR = {"headcount": "percent", "poor_share": "percent",
             "population_share": "percent", "headcount_ci_low": "percent",
             "headcount_ci_high": "percent", "gap": "percent",
             "severity": "percent", "gap_contribution": "percent",
             "severity_contribution": "percent",
             "absolute_contribution": "percentage_points",
             "poor_count": "persons"}


def to_number(text, decimal: str = ".") -> float | None:
    """Parse one published number. `decimal` is ',' for FR/PT sources."""
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    s = _SPACE_RE.sub("", s)
    s = s.replace("%", "").replace("−", "-")
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


def numbers_in(text: str, decimal: str = ".", percent_cells: bool = False) -> list[float]:
    """Every number on a line, in printed order (order matters, not magnitude)."""
    text = str(text)
    if decimal == ",":
        # A LEADING COMMA IS A LOST ZERO ("N'ZI ... 258 171 ,9%"); read as 0,9
        # rather than as the integer 9 -- a tenfold error (see labour/_common).
        text = re.sub(r"(?<![\d,])(,\d)", r"0\1", text)
    if percent_cells:
        # Split a %-cell off the number before it: "425 100,0%" -> "425 | 100,0%".
        text = re.sub(rf"(\d)[{_SPACES}](?=-?\d{{1,3}}(?:[.,]\d+)?%)", r"\1 | ", text)
    if decimal == ",":
        pat = rf"-?\d{{1,3}}(?:[{_SPACES}]\d{{3}}(?!\d))+(?:,\d+)?|-?\d+,\d+|-?\d+"
    else:
        pat = r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+\.\d+|-?\d+"
    out = []
    for tok in re.findall(pat, text):
        v = to_number(tok, decimal=decimal)
        if v is not None:
            out.append(v)
    return out


def deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s))
                   if unicodedata.category(c) != "Mn")


def row(*, metric: str, value, survey: str, welfare_aggregate: str,
        line_type: str, line_level: str, line_name: str,
        period: str, reference_period: str, frequency: str,
        unit_of_analysis: str = "person", unit: str | None = None,
        line_value="", line_unit: str = "",
        topic: str = "total", characteristic: str = "Total",
        sex: str = "total", age_group: str = "Total",
        geography: str = "Total country",
        locality: str = "all", locality_label: str = "Total",
        series_code: str = "") -> dict:
    """Build one analytic row. `unit` defaults from the metric; a report that
    prints P1/P2 on 0-1 passes unit="index" -- the value is never rescaled."""
    if metric not in METRICS:
        raise ValueError(f"unknown metric {metric!r}; add it to schema.METRICS "
                         f"deliberately rather than inventing one")
    unit = unit or _UNIT_FOR.get(metric)
    for name, v, allowed in (("unit", unit, UNITS), ("sex", sex, SEXES),
                             ("locality", locality, LOCALITIES),
                             ("unit_of_analysis", unit_of_analysis, UNITS_OF_ANALYSIS),
                             ("line_type", line_type, LINE_TYPES),
                             ("line_level", line_level, LINE_LEVELS),
                             ("welfare_aggregate", welfare_aggregate, WELFARE),
                             ("topic", topic, TOPICS)):
        if v not in allowed:
            raise ValueError(f"unknown {name} {v!r}")
    # A split-year round is dated by its first year (schema.split_year); a
    # report that dates it by the last (NISR, HCP, Stats SA) is re-dated here.
    span = split_year(reference_period)
    if span and str(period) == span[1]:
        period = span[0]
    return {
        "survey": survey, "welfare_aggregate": welfare_aggregate,
        "unit_of_analysis": unit_of_analysis, "line_type": line_type,
        "line_level": line_level, "line_name": line_name,
        "line_value": line_value, "line_unit": line_unit,
        "metric": metric, "topic": topic, "characteristic": characteristic,
        "sex": sex, "age_group": age_group, "geography": geography,
        "locality": locality, "locality_label": locality_label,
        "period": period, "reference_period": reference_period,
        "frequency": frequency, "value": value, "unit": unit,
        "series_code": series_code,
    }
