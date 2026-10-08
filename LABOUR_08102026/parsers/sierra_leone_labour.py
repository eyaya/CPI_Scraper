"""Sierra Leone — Stats SL: 2015 Population and Housing Census thematic report on
economic characteristics, and the 2014 Labour Force Survey report.

TWO SOURCES, TWO UNIVERSES, EACH CARRIED IN `survey`.

* PHC 2015, "Thematic Report on Economic Characteristics" (census, employed
  persons 15-64):
    - Table 3.7  occupation by sex, counts, plus the Total % column;
    - Table 3.8  occupation by region, counts.
* SLLFS 2014 report (household LFS, July-August 2014, 15-64) -- the file
  `unemployment/` already retains:
    - Table 2 "Key Employment Statistics": for each population group, the
      distribution of the employed across three JOB TYPES (agricultural self-
      employment / non-agricultural self-employment / wage employment) and
      across five SECTORS. Each group row is a distribution (both blocks sum to
      100), not a row percentage.

The earlier sweep recorded the 2014 report as "analytical, one composition
table" and left it: that one table is Table 2, and it is clean.

TABLE 3.7'S "% distribution" COLUMNS ARE NOT COLLECTED. They are shares of the
GRAND total (659,992 / 2,454,296 = 26.89), i.e. cells of a joint sex x
occupation distribution -- filed as "male, share" they would read as the
distribution of MEN across occupations (which would be 53.9 for agriculture,
not 26.89). The counts carry the same information without that ambiguity. The
trailing "Total %" column IS a distribution of all employed (sums to 100) and
is collected, as printed (whole percents).

LABELS AS PRINTED, PER TABLE: 3.7 prints "Legislators senior officials and
managers", 3.8 "Legislators, senior officials and managers". Both are kept as
Stats SL prints them; they denote the same group.

CHECKS: 3.7's counts sum to each sex's printed Total; 3.8's to each region's
Total; the four regional totals sum to the same 2,454,296 as 3.7's two sexes
(a cross-table identity the census satisfies exactly); every Table 2 block sums
to 100 (to 0.2).

NOT COLLECTED:
* SLIHS 2018 Table 5.10 (employment type by sex and locality): its total,
  3,187,847, exceeds the 2,428,053 employed the same report states; its female
  total (1,644,324) exceeds the 1,258,442 employed women; and "Self-employed
  WITH regular employees" is 52% of the table -- the share Table 5.1 gives to
  self-employed WITHOUT employees (52.5%, "with" being 3.9%). The labels
  appear swapped and the universe is unknown; nothing in the report settles
  either, so the table is refused (the Zimbabwe 4.8 rule). SLIHS Table 5.1 is
  itself inconsistent (national employment rate 88 against 41.5 / 46.5 by sex).
* PHC Figure 3.7 (industry by district) and 3.8/3.9: charts without values.
  Tables 3.1-3.6: labour force and rates (`unemployment`'s territory).
* SLLFS Table 2's "Unpaid Labor" column (a ratio to the employed, outside the
  job-type distribution by the report's own footnote), and its Disabled /
  Migrant rows (no column in this schema holds them). Table 3 is row %.
  Tables 12-17 are regression output.

No scheme is named against any table -> National.

CROSS-CHECK: PHC 2015 agriculture, forestry and fishing 659,992 men / 762,029
women (58%); Western region service workers 209,379. SLLFS 2014 overall
agricultural self-employment 59.2%, wage 9.5%, services 33.4%; Western Area
wage 37.5%.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_PHC = "Population and Housing Census 2015 (PHC 2015)"
_LFS = "Sierra Leone Labour Force Survey 2014 (SLLFS)"
_PHC_BASE = dict(survey=_PHC, period="2015", reference_period="PHC 2015",
                 frequency="ad_hoc", working_age_base="15-64")
_LFS_BASE = dict(survey=_LFS, period="2014", reference_period="July-August 2014",
                 frequency="ad_hoc", working_age_base="15-64")

_T37 = ["Agriculture, forestry and fishing",
        "Service workers, shop and market sales workers",
        "Technicians and associate professionals (including police and armed forces)",
        "Professionals and clerks", "Craft and related trade workers",
        "Plant and machine operators and assemblers",
        "Legislators senior officials and managers", "Elementary occupations",
        "Total"]
_T38 = ["Agriculture, forestry and fishing",
        "Service workers, shop and market sales workers",
        "Technicians and associate professionals (including police and armed forces)",
        "Professionals and clerks", "Craft and related trade workers",
        "Plant and machine operators and assemblers",
        "Legislators, senior officials and managers", "Elementary occupations",
        "Total"]
_REGIONS = ["Eastern", "Northern", "Southern", "Western"]
_N = r"(\d{1,3}(?:,\d{3})*)"

# SLLFS Table 2: columns in printed order; None = not collected.
_T2_COLS = [("employment_status", "Agricultural Self-Employment"),
            ("employment_status", "Non-Agricultural Self-Employment"),
            ("employment_status", "Wage Employment"),
            None,                                  # Unpaid Labor* (a ratio)
            ("industry", "Agriculture, Fishing and Forestry"),
            ("industry", "Mining and Extractive Industries"),
            ("industry", "Manufacturing and Utilities"),
            ("industry", "Construction"),
            ("industry", "Services")]
_T2_ROWS = {
    "Overall": {}, "Youth (AFR)": {"age_group": "15-35"},
    "Men": {"sex": "male"}, "Women": {"sex": "female"},
    "Disabled": None, "Not Disabled": None, "Migrant": None, "Not Migrant": None,
    "Never Went to School": {"education": "Never Went to School"},
    "Incomplete Primary": {"education": "Incomplete Primary"},
    "Completed Primary": {"education": "Completed Primary"},
    "Completed Lower Secondary": {"education": "Completed Lower Secondary"},
    "Completed Upper Secondary": {"education": "Completed Upper Secondary"},
    "Tech Degrees + Certificates": {"education": "Tech Degrees + Certificates"},
    "Tertiary Degree": {"education": "Tertiary Degree"},
    "Urban Freetown": {"locality": "urban", "locality_label": "Urban Freetown"},
    "Other Urban": {"locality": "urban", "locality_label": "Other Urban"},
    "Rural": {"locality": "rural", "locality_label": "Rural"},
    "Eastern": {"geography": "Eastern"}, "Northern": {"geography": "Northern"},
    "Southern": {"geography": "Southern"},
    "Western Area": {"geography": "Western Area"},
}


def _region(pages: list[str], caption: str) -> list[str] | None:
    for text in pages:
        m = re.search(caption, text, re.M)
        if m:
            out = []
            for ln in text[m.end():].splitlines():
                if ln.strip().startswith("Source"):
                    return out
                out.append(ln.strip())
            return out
    return None


def _rows_by_labels(lines, num_re, labels, where):
    """Values rows in order; label fragments checked word-by-word against the
    stated labels (they wrap above, beside and below their numbers)."""
    rows, text = [], []
    for ln in lines:
        m = re.search(num_re, ln)
        if m:
            rows.append(m.groups())
            ln = ln[:m.start()]
        if ln.strip():
            text.append(ln.strip())
    if len(rows) != len(labels):
        raise ValueError(f"{where}: {len(rows)} value rows for {len(labels)} labels")
    flat, pos = " ".join(text), 0
    for lab in labels:
        for word in lab.split():
            k = flat.find(word, pos)
            if k < 0:
                raise ValueError(f"{where}: label {lab!r} not found in order")
            pos = k + len(word)
    return list(zip(labels, rows))


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _phc(pages: list[str]) -> list[dict]:
    out = []
    t37 = _region(pages, r"^Table 3\.7\. Occupational distribution of the working age")
    t38 = _region(pages, r"^Table 3\.8\. Occupational distribution of working age")
    if t37 is None or t38 is None:
        raise ValueError("PHC 2015: Tables 3.7/3.8 not found")

    r37 = _rows_by_labels(t37, rf"{_N}\s+([\d.]+)\s+{_N}\s+([\d.]+)\s+(\d+)%$",
                          _T37, "PHC T3.7")
    *cats, (_, tot) = r37
    for j, (idx, sexname) in enumerate(((0, "male"), (2, "female"))):
        if sum(_num(r[idx]) for _, r in cats) != _num(tot[idx]):
            raise ValueError(f"PHC T3.7: {sexname} counts do not sum to Total")
    if abs(sum(_num(r[4]) for _, r in cats) - 100) > 2:
        raise ValueError("PHC T3.7: Total % column does not sum to 100")
    for lab, r in r37:
        for sex, v in (("male", r[0]), ("female", r[2])):
            out.append(C.row(topic="occupation", characteristic=lab,
                             classification="National", value=_num(v), sex=sex,
                             measure="count", unit="persons",
                             series_code="PHC2015 T3.7", **_PHC_BASE))
        out.append(C.row(topic="occupation", characteristic=lab,
                         classification="National", value=_num(r[4]),
                         measure="share", unit="percent",
                         series_code="PHC2015 T3.7", **_PHC_BASE))

    r38 = _rows_by_labels(t38, rf"{_N}\s+{_N}\s+{_N}\s+{_N}$", _T38, "PHC T3.8")
    *cats8, (_, tot8) = r38
    for j, reg in enumerate(_REGIONS):
        if sum(_num(r[j]) for _, r in cats8) != _num(tot8[j]):
            raise ValueError(f"PHC T3.8: {reg} does not sum to its Total")
    if sum(_num(v) for v in tot8) != _num(tot[0]) + _num(tot[2]):
        raise ValueError("PHC: regional totals (3.8) differ from sex totals (3.7)")
    for lab, r in r38:
        for reg, v in zip(_REGIONS, r):
            out.append(C.row(topic="occupation", characteristic=lab,
                             classification="National", value=_num(v),
                             geography=reg, measure="count", unit="persons",
                             series_code="PHC2015 T3.8", **_PHC_BASE))
    return out


def _lfs(pages: list[str]) -> list[dict]:
    lines = _region(pages, r"^Table 2: Key Employment Statistics\s*$")
    if lines is None:
        raise ValueError("SLLFS 2014: Table 2 not found")
    pct = r"(\d{1,3}\.\d)%"
    out, seen = [], set()
    for ln in lines:
        m = re.fullmatch(rf"(.+?)\s+{pct}(?:\s+{pct}){{8}}", ln)
        if not m:
            continue
        label = m.group(1).strip()
        vals = [float(v) for v in re.findall(pct, ln[len(m.group(1)):])]
        if label not in _T2_ROWS:
            raise ValueError(f"SLLFS T2: unknown row {label!r}")
        seen.add(label)
        ctx = _T2_ROWS[label]
        if ctx is None:
            continue
        for block, cols in (("status", range(0, 3)), ("sector", range(4, 9))):
            s = sum(vals[c] for c in cols)
            if abs(s - 100) > 0.2:
                raise ValueError(f"SLLFS T2 {label}: {block} sums to {s}")
        for spec, v in zip(_T2_COLS, vals):
            if spec is None:
                continue
            topic, cat = spec
            out.append(C.row(topic=topic, characteristic=cat,
                             classification="National", value=v,
                             measure="share", unit="percent",
                             series_code="SLLFS2014 T2", **_LFS_BASE, **ctx))
    if seen != set(_T2_ROWS):
        raise ValueError(f"SLLFS T2: missing rows {set(_T2_ROWS) - seen}")
    return out


def _pages(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages[:60]]


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows, done = [], set()
    for p in [path, *(extras or [])]:
        pages = _pages(p)
        joined = "\n".join(pages)
        if re.search(r"^Table 3\.7\. Occupational distribution", joined, re.M):
            rows += _phc(pages)
            done.add("phc")
        elif re.search(r"^Table 2: Key Employment Statistics\s*$", joined, re.M):
            rows += _lfs(pages)
            done.add("lfs")
        else:
            raise ValueError(f"Sierra Leone: unrecognised file {p!r}")
    if "phc" not in done:
        raise ValueError("Sierra Leone: the PHC 2015 report was not among the files")
    return pd.DataFrame(rows)
